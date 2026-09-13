from __future__ import annotations

# Imported fixtures are intentionally exposed to pytest in this module.
# ruff: noqa: F401, F811

from copy import deepcopy

import pytest
from sqlalchemy import text

from cafeteria.workflow import import_draft
from cafeteria.workflow_copy_store import copy_previous_week
from cafeteria.workflow_partial_store import (
    PartialWorkflowConflictError,
    PartialWorkflowValidationError,
    persist_menu_item,
)
from cafeteria.workflow_review import _review_payload
from cafeteria.workflow_store import load_draft_connection
from review_support import write_expectations
from test_component_catalog_db import CatalogDatabase
from test_workflow_copy_store_db import (
    TARGET_WEEK,
    _scope as copy_scope,
    _seed_source,
    catalog_database,
)
from test_workflow_partial_store_db import (
    WEEK,
    WorkflowDatabase,
    _full_values,
    _payload,
    _scope,
    workflow_database,
)


def _first_option(db: WorkflowDatabase, week=WEEK) -> dict[str, object]:
    with db.app.connect() as connection:
        return load_draft_connection(connection, "patient", week)["days"][0]["services"][0][
            "options"
        ][0]


def _item_id(db: WorkflowDatabase) -> int:
    with db.owner.connect() as connection:
        return int(connection.execute(text("SELECT id FROM cafeteria.menu_items")).scalar_one())


def _saved_receipts(db: WorkflowDatabase) -> list[tuple[int, dict[str, object]]]:
    with db.owner.connect() as connection:
        return [
            (int(row[0]), dict(row[1]))
            for row in connection.execute(
                text(
                    "SELECT actor_user_id,details FROM cafeteria.audit_events "
                    "WHERE action='workflow.menu_saved' ORDER BY id"
                )
            )
        ]


def test_partial_writer_round_trips_and_missing_field_preserves_accompaniment(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db)
    soup = {**_payload(), "accompaniment_code": "soup"}

    assert persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), "LUNCH", "MENU_1", soup, 0) == 1
    assert _first_option(db)["accompaniment_code"] == "soup"
    assert _first_option(db)["accompaniment_name"] == "Suppe"

    assert persist_menu_item(
        db.app, scope, WEEK, WEEK.isoformat(), "LUNCH", "MENU_1", _payload(), 1
    ) == 2
    assert _first_option(db)["accompaniment_code"] == "soup"
    assert _first_option(db)["accompaniment_name"] == "Suppe"
    receipts = _saved_receipts(db)
    assert [actor for actor, _details in receipts] == [db.actor_id, db.actor_id]
    assert [
        (details["row_version_before"], details["row_version_after"])
        for _actor, details in receipts
    ] == [(0, 1), (1, 2)]


def test_accompaniment_only_change_has_one_version_step_and_review_payload_delta(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db)
    base = {**_payload(), "accompaniment_code": "soup"}
    assert persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), "LUNCH", "MENU_1", base, 0) == 1
    item_id = _item_id(db)
    with db.owner.connect() as connection:
        before = _review_payload(connection, None, item_id)

    changed = {**base, "accompaniment_code": "salad"}
    assert persist_menu_item(
        db.app, scope, WEEK, WEEK.isoformat(), "LUNCH", "MENU_1", changed, 1
    ) == 2
    with db.owner.connect() as connection:
        after = _review_payload(connection, None, item_id)

    assert {key for key in before if before[key] != after[key]} == {"item_row_version"}
    assert (before["item_row_version"], after["item_row_version"]) == (1, 2)
    assert len(_saved_receipts(db)) == 2
    assert _first_option(db)["accompaniment_name"] == "Salat (gemischt und grün)"

    with pytest.raises(PartialWorkflowConflictError):
        persist_menu_item(
            db.app, scope, WEEK, WEEK.isoformat(), "LUNCH", "MENU_1", changed, 0
        )
    assert len(_saved_receipts(db)) == 2


def test_partial_writer_rejects_unknown_accompaniment_before_writing(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    with pytest.raises(PartialWorkflowValidationError):
        persist_menu_item(
            db.app,
            _scope(db),
            WEEK,
            WEEK.isoformat(),
            "LUNCH",
            "MENU_1",
            {**_payload(), "accompaniment_code": "both"},
            0,
        )
    with db.owner.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.menu_items")).scalar_one() == 0


def test_full_replace_defaults_missing_accompaniment_and_writes_selected_value(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    values = deepcopy(_full_values("IMPORT"))
    values["days"][0]["services"][0]["options"][0]["accompaniment_code"] = "salad"

    assert import_draft(
        db.app,
        "patient",
        WEEK,
        expected_row_version=0,
        actor_id=db.actor_id,
        values=values,
        **write_expectations(db.app, db.actor_id),
    ) == 2

    with db.app.connect() as connection:
        draft = load_draft_connection(connection, "patient", WEEK)
    assert draft["days"][0]["services"][0]["options"][0]["accompaniment_code"] == "salad"
    assert draft["days"][0]["services"][0]["options"][1]["accompaniment_code"] == "none"
    assert draft["days"][0]["services"][0]["options"][1]["accompaniment_name"] == ""


def test_previous_week_copy_preserves_accompaniment(
    catalog_database: CatalogDatabase,
) -> None:
    source = _seed_source(catalog_database, catalog_component=False)
    with catalog_database.owner.begin() as connection:
        connection.execute(
            text("UPDATE cafeteria.menu_items SET accompaniment='soup' WHERE id=:id"),
            {"id": source.item_id},
        )

    assert copy_previous_week(
        catalog_database.app,
        copy_scope(catalog_database),
        TARGET_WEEK,
        0,
        source_row_version=1,
    ) == 1
    with catalog_database.owner.connect() as connection:
        copied = connection.execute(
            text(
                "SELECT i.accompaniment FROM cafeteria.menu_items i "
                "JOIN cafeteria.menu_services s ON s.id=i.service_id "
                "JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id "
                "WHERE w.week_start=:week"
            ),
            {"week": TARGET_WEEK},
        ).scalar_one()
    assert copied == "soup"
