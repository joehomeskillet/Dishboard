"""CAL-NAV: kitchen calendar menu, prev/next, date jump, draft.read."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from flask import Flask, url_for

import cafeteria
from cafeteria.admin.calendar_routes import _parse_year_month, _shift_month

ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD = Path(__file__).resolve().parents[1]
MATRIX = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-route-matrix.json'
TEMPLATE = SCAFFOLD / 'cafeteria' / 'templates' / 'admin' / 'kuechenkalender.html'
TABS = SCAFFOLD / 'cafeteria' / 'templates' / 'admin' / '_area_tabs.html'
SIDEBAR = SCAFFOLD / 'cafeteria' / 'templates' / 'admin' / '_workflow_sidebar.html'


def test_shift_month_wraps_year() -> None:
    assert _shift_month(2026, 1, -1) == (2025, 12)
    assert _shift_month(2026, 12, 1) == (2027, 1)
    assert _shift_month(2026, 9, 0) == (2026, 9)


def test_parse_year_month_jump_and_query() -> None:
    app = Flask('calendar-nav')
    today = date(2026, 9, 16)
    with app.test_request_context('/admin/kuechenkalender?jump=2026-11'):
        assert _parse_year_month(today) == (2026, 11)
    with app.test_request_context('/admin/kuechenkalender?jump=2027-01-15'):
        assert _parse_year_month(today) == (2027, 1)
    with app.test_request_context('/admin/kuechenkalender?year=2027&month=2'):
        assert _parse_year_month(today) == (2027, 2)
    with app.test_request_context('/admin/kuechenkalender?month=13'):
        assert _parse_year_month(today) == (2026, 9)
    with app.test_request_context('/admin/kuechenkalender'):
        assert _parse_year_month(today) == (2026, 9)


def test_kitchen_calendar_rule_is_registered() -> None:
    app = Flask('calendar-nav')
    from cafeteria.admin.routes import bp
    app.register_blueprint(bp)
    with app.test_request_context():
        assert url_for('admin.kitchen_calendar') == '/admin/kuechenkalender'


def test_anonymous_kitchen_calendar_is_401(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    application = cafeteria.create_app()
    application.config.update(
        TESTING=True, SECRET_KEY='cal-nav', LAST_GOOD_DIR=str(tmp_path), DEMO_MODE=True,
    )
    assert application.test_client().get('/admin/kuechenkalender').status_code == 401


def test_area_tabs_and_sidebar_expose_calendar() -> None:
    tabs = TABS.read_text(encoding='utf-8')
    sidebar = SIDEBAR.read_text(encoding='utf-8')
    assert 'kitchen_calendar' in tabs
    assert 'Küchenkalender' in tabs
    assert 'kitchen_calendar' in sidebar
    assert 'Küchenkalender' in sidebar


def test_template_has_prev_next_jump_and_calendar_layout() -> None:
    text = TEMPLATE.read_text(encoding='utf-8')
    assert "layout_variant = 'calendar'" in text
    assert 'admin.kitchen_calendar' in text
    assert 'prev_year' in text and 'next_year' in text
    assert 'name="jump"' in text
    assert 'data-autosubmit' in text
    assert 'Heute' in text
    assert 'kitchen-cal-toolbar' in text
    assert 'kitchen-cal-list' in text
    assert 'Keine Einträge' in text
    assert 'Zum Monat' not in text
    assert 'profiles=both' in text or "profiles='both'" in text
    assert '<script' not in text.lower()
    assert 'patient LUNCH' not in text
    assert 'staff_guest LUNCH' not in text


def test_matrix_documents_calendar_route_and_r11() -> None:
    matrix = json.loads(MATRIX.read_text(encoding='utf-8'))
    row = next(item for item in matrix['routes'] if item['endpoint'] == 'admin.kitchen_calendar')
    assert row['rule'] == '/admin/kuechenkalender'
    assert row['methods'] == ['GET']
    assert row['layout_variant'] == 'calendar'
    assert row['owning_mp'] == 'MP-CAL-NAV'
    assert row['capability'] == 'draft.read'
    assert {'M01', 'M20'} <= set(row['density']['mockups'])
    assert set(row['density']['rules']) == {f'R{i:02d}' for i in range(1, 11)}
    notes = row['density']['notes']
    for viewport in ('390×844', '1440×900', '1024×768', '768×1024', '1920×1080'):
        assert viewport in notes
    template = next(item for item in matrix['templates'] if item['path'] == 'admin/kuechenkalender.html')
    assert 'admin.kitchen_calendar' in template['used_by_endpoints']
    assert template['owning_mp'] == 'MP-CAL-MONTH'
    for path in ('admin/_area_tabs.html', 'admin/_workflow_sidebar.html'):
        partial = next(item for item in matrix['templates'] if item['path'] == path)
        assert 'admin.kitchen_calendar' in partial['used_by_endpoints']
        disk = SCAFFOLD / 'cafeteria' / 'templates' / path
        assert hashlib.sha256(disk.read_bytes()).hexdigest() == partial['sha256']
