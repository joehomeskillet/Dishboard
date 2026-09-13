from __future__ import annotations

# Imported fixtures are intentionally exposed to pytest in this module.
# ruff: noqa: F401, F811

from contextlib import contextmanager
from datetime import date
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy import Engine, text
from werkzeug.datastructures import MultiDict

from cafeteria.admin import workflow_routes
from cafeteria.admin.rendering import _cells, menu_form_values
from cafeteria.workflow import WorkflowValidationError, _validate_values
from cafeteria.workflow_partial_form import parse_menu_item_form
from cafeteria.workflow_store import load_draft_connection
from test_admin_workflow_routes import (
    DAY,
    _hidden,
    _login,
    _menu_form as _route_menu_form,
    _scope as _route_scope,
)
from test_menu_template_binding_routes import proposal, proposal_form
from test_rendered_ui import admin_app, admin_engine  # noqa: F401
from test_workflow_form import _menu_form
from test_workflow_partial_store_db import _full_values


def _template_v32(
    engine: Engine,
    actor_id: int,
    accompaniment_default: str,
    previous: dict[str, object] | None = None,
) -> dict[str, object]:
    scope = _route_scope(engine, actor_id)
    statement = text(
        "SELECT cafeteria.update_dish_template_v32("
        ":actor,:authz,:location,CAST(:target AS uuid),"
        "CAST(:expected AS timestamptz),CAST(:payload AS jsonb))"
        if previous
        else "SELECT cafeteria.create_dish_template_v32("
        ":actor,:authz,:location,CAST(:target AS uuid),"
        "CAST(:expected AS timestamptz),CAST(:payload AS jsonb))"
    )
    payload = {
        "menu_type_code": "MENU_1",
        "profile_scope": "common",
        "title": "Rösti",
        "description": "Mit Gemüse",
        "recipe_public_id": None,
        "accompaniment_default": accompaniment_default,
    }
    with engine.begin() as connection:
        result = connection.execute(
            statement,
            {
                "actor": actor_id,
                "authz": scope.expected_authz_version,
                "location": scope.location_id,
                "target": previous["public_id"] if previous else None,
                "expected": previous["updated_at"] if previous else None,
                "payload": json.dumps(payload),
            },
        ).scalar_one()
    assert isinstance(result, dict)
    return result


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


def test_invalid_accompaniment_route_returns_400_with_entered_values(
    admin_app: Flask,
    admin_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _actor_id = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    action = "/admin/patienten/menu"
    page = client.get(f"{action}?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1")
    csrf = _hidden(page.text, "_csrf", form_action=action)
    captured: dict[str, object] = {}
    render_menu_page = workflow_routes._render_menu_page

    def capture_render(*args: object, **kwargs: object):
        captured.update(kwargs)
        return render_menu_page(*args, **kwargs)

    monkeypatch.setattr(workflow_routes, "_render_menu_page", capture_render)
    response = client.post(
        action,
        data=_route_menu_form(
            _csrf=csrf,
            title="Erhaltene Eingabe",
            accompaniment="both",
        ),
    )

    assert response.status_code == 400
    assert captured["form_values"]["title"] == "Erhaltene Eingabe"
    assert captured["form_values"]["accompaniment"] == "both"
    assert captured["form_errors"] == {
        "accompaniment": (
            "Montag, Mittag, Menü 1: Beilage muss Keine, Suppe "
            "oder Salat (gemischt und grün) sein."
        )
    }


def test_duplicate_accompaniment_route_field_returns_400_without_write(
    admin_app: Flask,
    admin_engine: Engine,
) -> None:
    client, _actor_id = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    action = "/admin/patienten/menu"
    page = client.get(f"{action}?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1")
    csrf = _hidden(page.text, "_csrf", form_action=action)
    form = MultiDict(_route_menu_form(_csrf=csrf, accompaniment="soup"))
    form.add("accompaniment", "salad")

    response = client.post(action, data=form)

    assert response.status_code == 400
    with admin_engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM cafeteria.menu_items")
        ).scalar_one() == 0


def test_template_proposal_route_saves_explicit_none_over_salad_default(
    admin_app: Flask,
    admin_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, actor_id = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    template = _template_v32(admin_engine, actor_id, "salad")
    _source, token, url = proposal(admin_app, admin_engine, actor_id, template)
    captured: list[dict[str, object]] = []
    project_values = workflow_routes.menu_form_values

    def capture_values(profile: str, option: dict[str, object]) -> dict[str, object]:
        values = project_values(profile, option)
        captured.append(values)
        return values

    monkeypatch.setattr(workflow_routes, "menu_form_values", capture_values)
    form = proposal_form(client, url, token, template)

    assert captured[-1]["accompaniment"] == "salad"
    form["accompaniment"] = "none"
    assert client.post("/admin/patienten/menu", data=form).status_code == 303

    with admin_engine.connect() as connection:
        draft = load_draft_connection(connection, "patient", date.fromisoformat(DAY))
    option = draft["days"][0]["services"][0]["options"][0]
    assert option["accompaniment_code"] == "none"
    assert option["accompaniment_name"] == ""


def test_template_default_change_after_proposal_returns_409_without_menu_write(
    admin_app: Flask,
    admin_engine: Engine,
) -> None:
    client, actor_id = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    template = _template_v32(admin_engine, actor_id, "salad")
    _source, token, url = proposal(admin_app, admin_engine, actor_id, template)
    form = proposal_form(client, url, token, template)
    form["accompaniment"] = "none"

    _template_v32(admin_engine, actor_id, "soup", previous=template)
    response = client.post("/admin/patienten/menu", data=form)

    assert response.status_code == 409
    with admin_engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM cafeteria.menu_items")
        ).scalar_one() == 0


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
