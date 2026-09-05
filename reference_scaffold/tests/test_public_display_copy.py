from __future__ import annotations

import re

import pytest
from flask import Flask, render_template
from playwright.sync_api import Browser, Page

from test_rendered_ui import _page
from test_rendered_ui import app as app
from test_rendered_ui import browser as browser


PUBLIC_PAGES = (
    '/cafeteria/heute/',
    '/cafeteria/wochenangebot/',
    '/patienten/heute/',
    '/patienten/wochenplan/',
    '/druck/cafeteria/woche',
    '/druck/patienten/woche',
    '/cafeteria/legende/',
)
SIGNAGE_PAGES = (
    '/signage/cafeteria/tag',
    '/signage/cafeteria/woche',
    '/signage/patienten/tag',
    '/signage/patienten/woche',
)
TECHNICAL_COPY = re.compile(
    r'\b(?:Kanal|Revision|Datenstand|Player|Publikation|Freigabe|Query-Parameter)\b'
    r'|Produktiver Wochenplayer|3840\s*[×x]\s*2160',
    re.IGNORECASE,
)


def _assert_plain_display(page: Page) -> str:
    assert page.locator('main').is_visible()
    visible_text = page.locator('body').inner_text()
    assert visible_text.strip()
    assert TECHNICAL_COPY.search(visible_text) is None, visible_text
    assert TECHNICAL_COPY.search(page.title()) is None
    return visible_text


@pytest.mark.parametrize('path', (*PUBLIC_PAGES, *SIGNAGE_PAGES))
@pytest.mark.parametrize('compact', (True, False))
def test_public_pages_show_menu_information_without_technical_copy(
    app: Flask, browser: Browser, path: str, compact: bool,
) -> None:
    response = app.test_client().get(path)
    assert response.status_code == 200
    if path != '/cafeteria/legende/':
        profile = 'patient' if 'patienten' in path else 'staff_guest'
        revision = app.config['TEST_SNAPSHOTS'][profile]['revision_id']
        assert response.headers['X-Snapshot-Revision'] == revision
    width, height = ((1920, 1080) if compact else (3840, 2160)) if path in SIGNAGE_PAGES else (
        (390, 844) if compact else (1440, 1100)
    )
    page = _page(browser, response.get_data(as_text=True), width, height)
    try:
        if path.startswith('/druck/'):
            page.emulate_media(media='print')
        visible_text = _assert_plain_display(page)
        if path != '/cafeteria/legende/':
            assert revision not in visible_text
        else:
            assert 'Allergene und Herkunft' in visible_text
            assert 'Eine leere Allergenliste bedeutet nicht automatisch allergenfrei.' in visible_text
        if path in ('/cafeteria/wochenangebot/', '/patienten/wochenplan/'):
            assert page.locator('.date-chip').inner_text() == 'Kalenderwoche 36'
    finally:
        page.close()


@pytest.mark.parametrize('path', SIGNAGE_PAGES)
@pytest.mark.parametrize('missing_snapshot', (True, False))
def test_signage_failure_keeps_status_and_cache_contract_without_diagnostics(
    app: Flask, browser: Browser, path: str, missing_snapshot: bool,
) -> None:
    if missing_snapshot:
        profile = 'patient' if 'patienten' in path else 'staff_guest'
        app.config['TEST_SNAPSHOTS'][profile] = None
    response = app.test_client().get(path if missing_snapshot else f'{path}?date=2026-09-03')
    assert response.status_code == (404 if missing_snapshot else 400)
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'X-Snapshot-Revision' not in response.headers
    page = _page(browser, response.get_data(as_text=True), 1920, 1080)
    try:
        assert 'Speiseplan\nnicht verfügbar' in _assert_plain_display(page)
    finally:
        page.close()


@pytest.mark.parametrize('path', ('/cafeteria/heute/', '/signage/cafeteria/tag'))
def test_closed_cafeteria_keeps_business_notice_without_technical_copy(
    app: Flask, browser: Browser, path: str,
) -> None:
    app.config['DEMO_TODAY'] = '2026-09-06'
    response = app.test_client().get(path)
    assert response.status_code == 200
    page = _page(browser, response.get_data(as_text=True), 1920, 1080)
    try:
        assert 'Cafeteria geschlossen' in _assert_plain_display(page)
        assert '6. September 2026' in page.locator('body').inner_text()
    finally:
        page.close()


@pytest.mark.parametrize(('path', 'missing_snapshot'), (
    *((path, False) for path in ('/', *PUBLIC_PAGES)),
    *((path, True) for path in PUBLIC_PAGES if path != '/cafeteria/legende/'),
))
def test_public_failure_keeps_status_and_cache_contract_without_diagnostics(
    app: Flask, browser: Browser, path: str, missing_snapshot: bool,
) -> None:
    if missing_snapshot:
        profile = 'patient' if 'patienten' in path else 'staff_guest'
        app.config['TEST_SNAPSHOTS'][profile] = None
    response = app.test_client().get(path if missing_snapshot else f'{path}?date=2026-09-03')
    assert response.status_code == (404 if missing_snapshot else 400)
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'X-Snapshot-Revision' not in response.headers
    page = _page(browser, response.get_data(as_text=True), 390, 844)
    try:
        assert 'Speiseplan nicht verfügbar' in _assert_plain_display(page)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    finally:
        page.close()


@pytest.mark.parametrize('template', (
    'public/cafeteria_week.html',
    'public/patient_today.html',
    'public/patient_week.html',
    'public/print_cafeteria_week.html',
    'public/print_patient_week.html',
    'signage/patient_day.html',
    'signage/patient_week.html',
))
def test_template_empty_states_keep_availability_notice_without_diagnostics(
    app: Flask, browser: Browser, template: str,
) -> None:
    with app.test_request_context('/'):
        html = render_template(
            template, snapshot=None, day=None, lunch=None, dinner=None,
            today='2026-09-02', open_days=[],
        )
    page = _page(browser, html, 1920, 1080)
    try:
        assert 'verfügbar' in _assert_plain_display(page)
    finally:
        page.close()
