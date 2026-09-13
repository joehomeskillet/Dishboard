from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from cafeteria.admin import workflow_routes
from cafeteria.admin.rendering import _cells, menu_form_values
from cafeteria.workflow import WorkflowValidationError, _validate_values
from cafeteria.workflow_partial_form import parse_menu_item_form
from test_workflow_form import _menu_form
from test_workflow_partial_store_db import _full_values


@pytest.mark.parametrize("code", ["none", "soup", "salad"])
def test_menu_form_accepts_exactly_one_accompaniment_code(code: str) -> None:
    parsed = parse_menu_item_form("patient", _menu_form(accompaniment=code))

    assert parsed.payload["accompaniment_code"] == code


def test_menu_form_without_accompaniment_keeps_field_out_of_partial_payload() -> None:
    parsed = parse_menu_item_form("patient", _menu_form())

    assert "accompaniment_code" not in parsed.payload


def test_write_model_rejects_derived_accompaniment_name() -> None:
    values = _full_values("derived-name")
    option = values["days"][0]["services"][0]["options"][0]
    option["accompaniment_code"] = "soup"
    _validate_values("patient", date(2026, 8, 31), values)

    option["accompaniment_name"] = "Suppe"
    with pytest.raises(
        WorkflowValidationError,
        match="Unzulässiges Menüfeld: accompaniment_name",
    ):
        _validate_values("patient", date(2026, 8, 31), values)


@pytest.mark.parametrize("value", ["", "both", "soup,salad", " soup "])
def test_menu_form_rejects_invalid_accompaniment_on_its_field(value: str) -> None:
    with pytest.raises(WorkflowValidationError) as raised:
        parse_menu_item_form("patient", _menu_form(accompaniment=value))

    assert raised.value.field_name == "accompaniment"


def test_menu_form_and_week_cell_project_saved_accompaniment() -> None:
    option = {
        "type_code": "MENU_1",
        "title": "Rindsragout",
        "accompaniment_code": "salad",
        "accompaniment_name": "Salat (gemischt und grün)",
    }
    assert menu_form_values("patient", option)["accompaniment"] == "salad"

    app = Flask(__name__)
    app.add_url_rule(
        "/<family>/<week>/<day>/<meal>/<option>",
        endpoint="admin.menu_get",
        view_func=lambda **_values: "",
    )
    draft = {
        "days": [
            {
                "date": "2026-08-31",
                "services": [
                    {
                        "meal_code": "LUNCH",
                        "service_state": "open",
                        "options": [option, {"type_code": "VEGGIE", "title": "Gemüse"}],
                    },
                    {
                        "meal_code": "DINNER",
                        "service_state": "open",
                        "options": [
                            {"type_code": "MENU_1", "title": "Abendmenü"},
                            {"type_code": "VEGGIE", "title": "Abendgemüse"},
                        ],
                    },
                ],
            }
        ]
    }
    with app.test_request_context():
        cell = _cells("patient", "patienten", date(2026, 8, 31), draft, {}, {})[0]

    assert cell["accompaniment_code"] == "salad"
    assert cell["accompaniment_name"] == "Salat (gemischt und grün)"


def test_invalid_form_redisplay_retains_accompaniment() -> None:
    app = Flask(__name__)
    with app.test_request_context(
        method="POST",
        data={"title": "Eigene Eingabe", "accompaniment": "both"},
    ):
        values = workflow_routes._request_menu_values()

    assert values["title"] == "Eigene Eingabe"
    assert values["accompaniment"] == "both"


def test_template_proposal_prefills_accompaniment_without_overriding_later_form_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = {
        "id": 7,
        "public_id": "00000000-0000-4000-8000-000000000007",
        "title": "Rösti",
        "description": "Mit Gemüse",
        "active": True,
        "accompaniment_default": "salad",
    }

    @contextmanager
    def transaction(*_args: object, **_kwargs: object):
        yield object()

    monkeypatch.setattr(workflow_routes, "_db", lambda: object())
    monkeypatch.setattr(workflow_routes, "write_transaction", transaction)
    monkeypatch.setattr(workflow_routes, "lock_templates", lambda *_args, **_kwargs: {7: source})
    monkeypatch.setattr(workflow_routes, "require_template_source", lambda *_args: None)
    monkeypatch.setattr(workflow_routes, "require_empty_template_target", lambda *_args: None)
    monkeypatch.setattr(workflow_routes, "validate_template_target", lambda *_args: None)
    context = SimpleNamespace(
        template_public_id=source["public_id"],
        recipe_public_id=None,
        require_source=Mock(),
    )

    option = workflow_routes._proposal_values(context, Mock())

    assert option["accompaniment_code"] == "salad"
    assert menu_form_values("patient", option)["accompaniment"] == "salad"
    assert menu_form_values("patient", {**option, "accompaniment_code": "none"})[
        "accompaniment"
    ] == "none"
