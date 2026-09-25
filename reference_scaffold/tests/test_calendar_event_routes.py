"""CAL-EVENTS-UI: kitchen event form routes."""
from __future__ import annotations

import re
from pathlib import Path

from flask import Flask, url_for

import cafeteria

TEMPLATE = Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin'
CALENDAR_TEMPLATE = TEMPLATE / 'kuechenkalender.html'
ANLASS_TEMPLATE = TEMPLATE / 'kuechenkalender_anlass.html'


def test_event_routes_are_registered() -> None:
    app = Flask('calendar-events')
    from cafeteria.admin.routes import bp
    import cafeteria.admin.calendar_event_routes  # noqa: F401
    app.register_blueprint(bp)
    with app.test_request_context():
        assert url_for('admin.kitchen_event_new') == '/admin/kuechenkalender/anlass'
        assert url_for('admin.kitchen_event_edit', public_id='00000000-0000-4000-8000-000000000001').endswith('/anlass/00000000-0000-4000-8000-000000000001')


def test_anonymous_event_form_is_401(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    application = cafeteria.create_app()
    application.config.update(
        TESTING=True, SECRET_KEY='cal-event', LAST_GOOD_DIR=str(tmp_path), DEMO_MODE=True,
    )
    client = application.test_client()
    assert client.get('/admin/kuechenkalender/anlass').status_code == 401


def test_calendar_template_exposes_event_markers() -> None:
    text = CALENDAR_TEMPLATE.read_text(encoding='utf-8')
    assert 'kitchen_event_new' in text
    assert 'kitchen_event_edit' in text
    assert 'kitchen-cal-event' in text
    form = ANLASS_TEMPLATE.read_text(encoding='utf-8')
    assert 'Gästezahl' in form
    assert 'skaliert keine Mengen' in form
    assert '<script' not in form.lower()


def test_calendar_template_uses_shared_statusbar_and_primary_action() -> None:
    text = CALENDAR_TEMPLATE.read_text(encoding='utf-8')
    assert 'status_items=calendar_status' in text
    assert "'label': 'Monat'" in text
    assert "'label': 'Geplante Tage'" in text
    assert 'Anlass anlegen' in text
    assert "icon_button('actions.add'" in text


def test_calendar_template_keeps_mobile_list_for_narrow_viewports() -> None:
    text = CALENDAR_TEMPLATE.read_text(encoding='utf-8')
    assert 'kitchen-cal-list' in text
    assert 'kitchen-cal-grid' in text
    assert 'kitchen-cal-toolbar' in text
    assert 'aria-label="Kalendertage"' in text


def test_anlass_template_preserves_post_fields_and_shared_patterns() -> None:
    text = ANLASS_TEMPLATE.read_text(encoding='utf-8')
    for name in ('event_date', 'starts_at', 'ends_at', 'title', 'guest_count', 'note'):
        assert f"field('{name}'" in text or f"textarea('{name}'" in text or f"select('{name}'" in text
    assert "select('profile_scope'" in text
    assert 'name="row_version"' in text
    assert 'name="_csrf"' in text
    assert 'status_items=event_status' in text
    assert 'form_footer(' in text
    assert 'disclosure_section(' in text
    assert 'Anlass anlegen' in text
    assert 'Anlass bearbeiten' in text
    assert 'Weitere Optionen' in text
    assert 'Zum Kalender' not in text


def test_anlass_form_field_names_match_expected_contract() -> None:
    text = ANLASS_TEMPLATE.read_text(encoding='utf-8')
    macro_fields = {
        match.group(1)
        for match in re.finditer(r"(?:field|textarea|select)\('([^']+)'", text)
    }
    assert macro_fields == {
        'event_date', 'starts_at', 'ends_at', 'profile_scope', 'title', 'guest_count', 'note',
    }
    assert 'name="row_version"' in text
    assert 'name="_csrf"' in text
