"""CAL-EVENTS-UI: kitchen event form routes."""
from __future__ import annotations

from pathlib import Path

from flask import Flask, url_for

import cafeteria

TEMPLATE = Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin'


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
    text = (TEMPLATE / 'kuechenkalender.html').read_text(encoding='utf-8')
    assert 'kitchen_event_new' in text
    assert 'kitchen_event_edit' in text
    assert 'kitchen-cal-event' in text
    form = (TEMPLATE / 'kuechenkalender_anlass.html').read_text(encoding='utf-8')
    assert 'Gästezahl' in form
    assert 'skaliert keine Mengen' in form
    assert '<script' not in form.lower()
