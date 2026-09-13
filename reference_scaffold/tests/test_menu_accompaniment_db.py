from __future__ import annotations

# Imported fixtures are intentionally exposed to pytest in this module.
# ruff: noqa: F401, F811

from copy import deepcopy
import hashlib
import json

import pytest
from sqlalchemy import text

from cafeteria.db import active_snapshot
from cafeteria.patient_payload import validate_snapshot_payload
from cafeteria.workflow import (
    WorkflowValidationError,
    import_draft,
    publish_draft_scoped,
)
from cafeteria.workflow_copy_store import copy_previous_week
from cafeteria.workflow_partial_store import (
    PartialWorkflowConflictError,
    PartialWorkflowValidationError,
    persist_menu_item,
)
from cafeteria.workflow_review import _review_payload
from cafeteria.workflow_snapshot import build_snapshot
from cafeteria.workflow_store import load_draft_connection
from review_support import review_saved_week, write_expectations
from test_admin_workflow_db import _staff_values
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


def test_partial_create_without_accompaniment_defaults_to_none(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database

    assert persist_menu_item(
        db.app,
        _scope(db),
        WEEK,
        WEEK.isoformat(),
        "LUNCH",
        "MENU_1",
        _payload(),
        0,
    ) == 1

    option = _first_option(db)
    assert option["accompaniment_code"] == "none"
    assert option["accompaniment_name"] == ""


def test_full_replace_without_accompaniment_resets_existing_selection(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    selected = deepcopy(_full_values("SELECTED"))
    selected["days"][0]["services"][0]["options"][0]["accompaniment_code"] = "soup"
    first_week_version = import_draft(
        db.app,
        "patient",
        WEEK,
        expected_row_version=0,
        actor_id=db.actor_id,
        values=selected,
        **write_expectations(db.app, db.actor_id),
    )
    with db.owner.connect() as connection:
        before = connection.execute(
            text(
                "SELECT i.row_version,i.accompaniment FROM cafeteria.menu_items i "
                "JOIN cafeteria.menu_services s ON s.id=i.service_id "
                "JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id "
                "JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id "
                "WHERE w.week_start=:week AND s.service_date=:day "
                "AND mt.code='MENU_1' ORDER BY i.id LIMIT 1"
            ),
            {"week": WEEK, "day": WEEK},
        ).one()

    import_draft(
        db.app,
        "patient",
        WEEK,
        expected_row_version=first_week_version,
        actor_id=db.actor_id,
        values=_full_values("RESET"),
        **write_expectations(db.app, db.actor_id),
    )

    with db.owner.connect() as connection:
        after = connection.execute(
            text(
                "SELECT i.row_version,i.accompaniment FROM cafeteria.menu_items i "
                "JOIN cafeteria.menu_services s ON s.id=i.service_id "
                "JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id "
                "JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id "
                "WHERE w.week_start=:week AND s.service_date=:day "
                "AND mt.code='MENU_1' ORDER BY i.id LIMIT 1"
            ),
            {"week": WEEK, "day": WEEK},
        ).one()
    assert before.accompaniment == "soup"
    assert after.accompaniment == "none"
    assert after.row_version == before.row_version + 1
    assert _first_option(db)["accompaniment_code"] == "none"


@pytest.mark.parametrize("invalid", ["both", 7])
def test_full_writer_rejects_invalid_accompaniment_without_writing(
    workflow_database: WorkflowDatabase,
    invalid: object,
) -> None:
    db = workflow_database
    values = deepcopy(_full_values("INVALID"))
    values["days"][0]["services"][0]["options"][0]["accompaniment_code"] = invalid

    with pytest.raises(WorkflowValidationError, match="Beilagenwahl ist ungültig"):
        import_draft(
            db.app,
            "patient",
            WEEK,
            expected_row_version=0,
            actor_id=db.actor_id,
            values=values,
            **write_expectations(db.app, db.actor_id),
        )

    with db.owner.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM cafeteria.menu_weeks")
        ).scalar_one() == 0


@pytest.mark.parametrize("profile", ["patient", "staff_guest"])
def test_slot_writer_accompaniment_reaches_valid_active_snapshot(
    workflow_database: WorkflowDatabase,
    profile: str,
) -> None:
    db = workflow_database
    values = (
        deepcopy(_full_values("E2E"))
        if profile == "patient"
        else _staff_values("E2E")
    )
    week_version = import_draft(
        db.app,
        profile,
        WEEK,
        expected_row_version=0,
        actor_id=db.actor_id,
        values=values,
        **write_expectations(db.app, db.actor_id),
    )
    payload = {**_payload(staff=profile == "staff_guest"), "accompaniment_code": "soup"}

    assert persist_menu_item(
        db.app,
        _scope(db, profile),
        WEEK,
        WEEK.isoformat(),
        "LUNCH",
        "MENU_1",
        payload,
        1,
    ) == 2
    with db.app.connect() as connection:
        draft = load_draft_connection(connection, profile, WEEK)
    draft_option = draft["days"][0]["services"][0]["options"][0]
    assert draft_option["accompaniment_code"] == "soup"
    assert draft_option["accompaniment_name"] == "Suppe"

    reviewed_version = review_saved_week(db.app, profile, WEEK, db.actor_id)
    assert reviewed_version > week_version
    snapshot = publish_draft_scoped(
        db.app,
        profile,
        WEEK,
        expected_row_version=reviewed_version,
        actor_id=db.actor_id,
        issuer_engine=db.owner,
        expected_location_id=db.location_id,
    )
    snapshot_option = snapshot["days"][0]["services"][0]["options"][0]
    assert snapshot_option["accompaniment_code"] == "soup"
    assert snapshot_option["accompaniment_name"] == "Suppe"
    validate_snapshot_payload(profile, snapshot)
    assert active_snapshot(db.app, profile, WEEK.isoformat()) == snapshot


def test_unselected_database_publication_matches_legacy_snapshot_hash(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    import_draft(
        db.app,
        "patient",
        WEEK,
        expected_row_version=0,
        actor_id=db.actor_id,
        values=_full_values("UNCHANGED"),
        **write_expectations(db.app, db.actor_id),
    )
    with db.app.connect() as connection:
        draft = load_draft_connection(connection, "patient", WEEK)
    legacy_draft = deepcopy(draft)
    for day in legacy_draft["days"]:
        for service in day["services"]:
            for option in service["options"]:
                option.pop("accompaniment_code")
                option.pop("accompaniment_name")

    reviewed_version = review_saved_week(db.app, "patient", WEEK, db.actor_id)
    snapshot = publish_draft_scoped(
        db.app,
        "patient",
        WEEK,
        expected_row_version=reviewed_version,
        actor_id=db.actor_id,
        issuer_engine=db.owner,
        expected_location_id=db.location_id,
    )
    legacy_snapshot = build_snapshot("patient", legacy_draft, snapshot["revision_id"])
    snapshot_bytes = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    legacy_bytes = json.dumps(
        legacy_snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()

    assert snapshot_bytes == legacy_bytes
    digest = hashlib.sha256(snapshot_bytes).hexdigest()
    with db.app.connect() as connection:
        stored_hash = connection.execute(
            text(
                "SELECT content_hash_sha256 FROM cafeteria.publication_revisions "
                "WHERE revision_code=:revision"
            ),
            {"revision": snapshot["revision_id"]},
        ).scalar_one()
    assert stored_hash == digest
    assert active_snapshot(db.app, "patient", WEEK.isoformat()) == snapshot


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
