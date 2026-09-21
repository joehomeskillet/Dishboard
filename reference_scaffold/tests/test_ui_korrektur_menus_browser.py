from __future__ import annotations

import base64
from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.workflow import publish_draft
from cafeteria.workflow_partial_store import persist_week_header
from cafeteria.workflow_review import get_component_review_token, review_component
from test_admin_workflow_db import _save_reviewed, _staff_values
from test_admin_workflow_routes import (
    WEEK, _payload, _scope, database_engine as database_engine, app as workflow_app,  # noqa: F401
)
from test_branding_browser import live_branding as live_branding
from test_menu_collection import _save
from test_rendered_ui import browser as browser
from test_recipe_freeze_v2_browser import native_full_page_capture

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / '.claude' / 'evidence' / 'density-lists-0913' / 'after'
VIEWPORTS = [
    (1440, 900),
    (1024, 768),
    (1920, 1080),
    (2560, 1440),
    (768, 1024),
    (390, 844),
    (320, 844),
]


def _shot(page, name: str, *, native=False, viewport_only=False) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    page.evaluate('document.fonts.ready')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    for action in page.locator('main .btn, main summary').all():
        if action.is_visible():
            box = action.bounding_box()
            assert box['height'] >= 48 and box['width'] >= 48
            assert box['x'] >= 0 and box['x'] + box['width'] <= page.evaluate('innerWidth') + 1
    destination = EVIDENCE_DIR / f'{name}.png'
    if native and viewport_only:
        # Chromium full-page captures lay out children of closed details. Preserve
        # the real viewport instead, using the established shell capture method.
        geometry = '''() => ({innerWidth,innerHeight,outerWidth,outerHeight,devicePixelRatio,
            scrollX,scrollY,visualHeight:visualViewport.height,
            main:document.querySelector('main').getBoundingClientRect().toJSON()})'''
        before = page.evaluate(geometry)
        cdp = page.context.new_cdp_session(page)
        try:
            metrics = cdp.send('Page.getLayoutMetrics')
            png = base64.b64decode(cdp.send('Page.captureScreenshot', {
                'format': 'png', 'captureBeyondViewport': False,
            })['data'], validate=True)
        finally:
            cdp.detach()
        destination.write_bytes(png)
        after = page.evaluate(geometry)
        assert before == after
        assert int.from_bytes(png[16:20], 'big') == before['outerWidth']
        assert int.from_bytes(png[20:24], 'big') == round(before['visualHeight'] * 2)
        destination.with_suffix('.capture.json').write_text(json.dumps({
            'cdp_layout_metrics': metrics, 'layout_before': before, 'layout_after': after,
            'captureBeyondViewport': False,
        }, indent=2))
    elif native:
        native_full_page_capture(page, destination)
    else:
        page.screenshot(path=str(destination), full_page=True)
    destination.with_suffix('.json').write_text(json.dumps({
        'route': page.url, 'viewport': page.viewport_size,
        'capture_mode': 'native-viewport' if viewport_only else 'native-full-page' if native else 'full-page',
        'geometry': page.evaluate('({innerWidth,innerHeight,outerWidth,outerHeight,devicePixelRatio})'),
    }, indent=2))


def _zoom_shot(browser, tmp_path, origin, session_cookie, route, name):
    with TemporaryDirectory(prefix='lists-native-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
            page.goto(origin + route)
            cdp = context.new_cdp_session(page)
            assert cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom'] == 2
            assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
            assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
            viewport_only = route.endswith('/wochen')
            _shot(page, name, native=True, viewport_only=viewport_only)
            if viewport_only:
                page.locator('.week-action-primary').first.scroll_into_view_if_needed()
                _shot(page, name + '-actions', native=True, viewport_only=True)
            cdp.detach()


@pytest.mark.parametrize('family,profile', [('patienten', 'patient'), ('cafeteria', 'staff_guest')])
def test_menu_collection_ui_korrektur(live_branding, database_engine, browser, tmp_path, family, profile):
    origin, _, client, actor, _ = live_branding
    scope = _scope(database_engine, actor, profile)

    # Menu 1: Reviewed and checked, with allergens
    payload_reviewed = _payload(staff=profile == 'staff_guest')
    payload_reviewed['allergens'] = [{'code': 'GLUTEN', 'presence': 'contains'}]
    payload_reviewed['labels'] = ['VEGETARIAN']
    _save(database_engine, scope, title='Tomatensuppe mit Basilikum', payload=payload_reviewed)
    with database_engine.begin() as conn:
        conn.execute(text("UPDATE cafeteria.menu_items SET allergen_review_status='checked' WHERE title='Tomatensuppe mit Basilikum'"))
        item_id, version = conn.execute(text("SELECT id, row_version FROM cafeteria.menu_items WHERE title='Tomatensuppe mit Basilikum'")).one()
    review_component(database_engine, scope, item_id, get_component_review_token(database_engine, scope, item_id), version)

    # Menu 2: Missing allergens and long description/note
    long_desc = 'Sorgfältig zubereitetes Gemüse mit frischen Gartenkräutern aus regionalem Anbau nach Hausrezept.'
    long_note = 'Bitte beachten: Hinweis für die Küchenausgabe zur Portionsgrösse und Beilagenwahl.'
    payload_missing = _payload(staff=profile == 'staff_guest')
    payload_missing['allergens'] = []
    payload_missing['description'] = long_desc
    payload_missing['note'] = long_note
    _save(database_engine, scope, week=WEEK + timedelta(days=7), title='Kartoffelgratin mit Gemüse', payload=payload_missing)

    session_cookie = client.get_cookie('session').value

    for width, height in VIEWPORTS:
        with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
            context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
            page = context.new_page()
            response = page.goto(f'{origin}/admin/{family}/menues')
            assert response.status == 200

            # 1. No horizontal scrollbar
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')

            # Text comes first, including narrow screens and the NoJS DOM order.
            expect(page.get_by_role('tab', name='Liste', exact=True)).to_have_attribute('aria-selected', 'true')
            expect(page.locator('.tab-content > .tab-pane').first).to_have_attribute('id', 'menu-list')
            first_row = page.locator('[data-menu-list-id]').first
            expect(first_row).to_be_visible()
            box = first_row.bounding_box()
            assert box is not None
            if height >= 768:
                assert box['y'] < height, f'Row top {box["y"]} is below viewport {height}'
            for cell in page.locator('[data-menu-list-id] > *').all():
                bounds = cell.bounding_box()
                assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width + 1

            # 3. Screenshot normal state
            _shot(page, f'{family}-menues-normal-{width}x{height}')
            page.get_by_role('tab', name='Karten', exact=True).click()

            # 4. Status separation on cards
            # Tomatensuppe has verified review badge
            soup_card = page.locator('#menu-cards [data-menu-id]').filter(has_text='Tomatensuppe')
            expect(soup_card.locator('[data-review="checked"]')).to_contain_text('Geprüft · gespeicherter Stand bestätigt')

            # Kartoffelgratin has open review badge AND missing allergens warning directly on card
            gratin_card = page.locator('#menu-cards [data-menu-id]').filter(has_text='Kartoffelgratin')
            expect(gratin_card.locator('[data-review="open"]')).to_contain_text('Prüfung offen')
            expect(gratin_card).to_contain_text('Allergenangaben nicht erfasst')

            # Long description/note stays available in a native disclosure.
            details = gratin_card.locator('details.menu-note-details')
            expect(details).to_have_count(1)
            summary = details.locator('summary')
            expect(summary).to_contain_text('Details')

            # Before open, description is inside details content
            expect(details.locator('.menu-description')).to_contain_text(long_desc)
            expect(details.locator('.shared-note')).to_contain_text(long_note)

            # Click to open details
            summary.click()
            expect(details).to_have_attribute('open', '')

            # 6. Exactly one action button per card
            actions = gratin_card.locator('.card-footer .btn')
            expect(actions).to_have_count(1)
            expect(actions).to_contain_text('Bearbeiten')
            assert actions.bounding_box()['height'] >= 48
            if width in (390, 1440):
                _shot(page, f'{family}-menues-cards-{width}x{height}')

    _zoom_shot(browser, tmp_path, origin, session_cookie,
               f'/admin/{family}/menues', f'{family}-menues-native-200')

    # Test Empty / No-match search screenshots
    with browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/{family}/menues?q=UnbekanntesGericht')
        expect(page.locator('#menu-list [data-empty-kind="no_match"]')).to_be_visible()
        _shot(page, f'{family}-menues-nomatch-1440x900')

    # Test without JavaScript
    with browser.new_context(viewport={'width': 1366, 'height': 768}, java_script_enabled=False) as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/{family}/menues')
        expect(page.locator('#menu-list')).to_be_visible()
        expect(page.locator('#menu-cards')).to_be_visible()
        # Open action link has correct href
        link = page.locator('#menu-list [data-admin-icon-action]').first
        dest = link.get_attribute('href')
        assert f'/admin/{family}/menu?week=' in dest


@pytest.mark.parametrize('family', ['patienten', 'cafeteria'])
def test_week_management_ui_korrektur(live_branding, database_engine, browser, tmp_path, family):
    origin, _, client, actor, _ = live_branding
    scope = _scope(database_engine, actor, 'patient')

    # Setup a week in various states
    persist_week_header(database_engine, scope, WEEK, {'title': 'Herbstplan Woche 1', 'shared_note': 'Hinweis'}, 0)

    # Make another week ready/published
    scope_staff = _scope(database_engine, actor, 'staff_guest')
    persist_week_header(database_engine, scope_staff, WEEK, {'title': 'Cafeteria Standard', 'shared_note': ''}, 0)
    version = _save_reviewed(database_engine, 'staff_guest', _staff_values())
    publish_draft(database_engine, 'staff_guest', WEEK, expected_row_version=version,
                  actor_id=actor, issuer_engine=database_engine)

    session_cookie = client.get_cookie('session').value

    for width, height in VIEWPORTS:
        with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
            context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
            page = context.new_page()
            response = page.goto(f'{origin}/admin/{family}/wochen')
            assert response.status == 200

            # 1. No horizontal scrollbar
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')

            # 2. First list row visible without scrolling on 1366x768 and 1920x1080
            first_row = page.locator('tr[data-week-id]').first
            expect(first_row).to_be_visible()
            box = first_row.bounding_box()
            assert box is not None
            if height >= 768:
                assert box['y'] < height, f'Row top {box["y"]} is below viewport {height}'

            # 3. Screenshot normal state
            _shot(page, f'{family}-wochen-normal-{width}x{height}')

            # 4. Status statement with table Klartext
            status_cell = first_row.locator('td[data-label="Status"]')
            expect(status_cell.locator('.badge')).to_be_visible()
            # Status should contain clear text explanation
            status_text = status_cell.inner_text()
            assert any(term in status_text for term in (
                'Veröffentlicht', 'Noch nicht veröffentlicht', 'Prüfung offen', 'Unvollständig', 'Noch keine Menüs erfasst',
            ))

            # 5. Exactly ONE primary action ("Woche öffnen"), secondary grouped
            primary_btn = first_row.locator('.week-actions .week-action-primary')
            expect(primary_btn).to_be_visible()
            expect(primary_btn).to_have_class('btn btn-primary week-action-primary text-wrap')
            expect(primary_btn).to_have_text('Öffnen')
            assert primary_btn.bounding_box()['height'] >= 48

            secondary_btns = first_row.locator('.week-actions [data-admin-icon-action]')
            if secondary_btns.count() > 0:
                for idx in range(secondary_btns.count()):
                    btn = secondary_btns.nth(idx)
                    expect(btn).not_to_have_class('btn-primary')
                    assert btn.bounding_box()['height'] >= 48

            # The creation form is closed while selecting a week; copy effects open on demand.
            expect(page.locator('.week-toolbar .profile-tabs')).to_be_visible()
            expect(page.locator('#new-week-date')).to_be_hidden()
            copy = first_row.locator('.week-copy')
            expect(copy.locator('p')).to_be_hidden()
            copy.locator('summary').focus()
            copy.locator('summary').press('Enter')
            expect(copy.locator('p')).to_contain_text('Quelle: 31.08.2026 → Ziel: 07.09.2026')
            expect(copy.locator('p')).to_contain_text('Ziel muss leer und unveröffentlicht sein')
            expect(copy.get_by_role('link')).to_have_attribute('href', f'/admin/{family}/copy?week=2026-09-07')
            if width in (390, 1440):
                _shot(page, f'{family}-wochen-copy-{width}x{height}')

    # Test published week on cafeteria
    with browser.new_context(viewport={'width': 1366, 'height': 768}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/cafeteria/wochen')
        live_row = page.locator('tr[data-status="live"]')
        expect(live_row).to_be_visible()
        expect(live_row.locator('td[data-label="Status"]')).to_contain_text('Veröffentlicht · entspricht dem gespeicherten Stand')
        _shot(page, f'{family}-wochen-live-1366x768')

    _zoom_shot(browser, tmp_path, origin, session_cookie,
               f'/admin/{family}/wochen', f'{family}-wochen-native-200')

    # Test "Neue Woche anlegen" details interaction and error handling
    with browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/{family}/wochen')

        # Details is collapsed by default
        details = page.locator('details.card')
        expect(details).to_have_count(1)
        expect(page.locator('#new-week-date')).to_be_hidden()

        # Open details
        page.locator('#new-week-title').click()
        expect(page.locator('#new-week-date')).to_be_visible()

        # Submit invalid date to trigger error state
        page.locator('#new-week-date').fill('2026-09-02')  # Not a Monday
        page.locator('#new-week-name').fill('Ungültige Woche')
        page.get_by_role('button', name='Woche anlegen').click()

        # Error state preserves input and leaves details open
        expect(page.locator('#new-week-error')).to_be_visible()
        expect(page.locator('#new-week-date')).to_be_visible()
        expect(page.locator('#new-week-name')).to_have_value('Ungültige Woche')
        _shot(page, f'{family}-wochen-fehler-390x844')

    # Test without JavaScript
    with browser.new_context(viewport={'width': 1366, 'height': 768}, java_script_enabled=False) as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/{family}/wochen')
        row = page.locator('tr[data-week-id]').first
        link = row.locator('.week-action-primary')
        dest = link.get_attribute('href')
        assert f'/admin/{family}?week=' in dest
        requests = []
        page.on('request', lambda request: requests.append(request.method))
        with database_engine.connect() as connection:
            before_copy = connection.execute(text('SELECT id,row_version FROM cafeteria.menu_weeks ORDER BY id')).all()
        row.locator('.week-copy summary').click()
        row.get_by_role('link', name='Kopieren vorbereiten').click()
        expect(page.locator('main')).to_have_attribute('data-source-week', '2026-08-31')
        expect(page.locator('main')).to_have_attribute('data-target-week', '2026-09-07')
        expect(page.locator('input[name="source_week"]')).to_have_value('2026-08-31')
        expect(page.locator('input[name="target_week"]')).to_have_value('2026-09-07')
        assert page.locator('.admin-copy-actions input[name="_csrf"]').input_value()
        expect(page.get_by_role('button', name='Vorwoche kopieren')).to_be_visible()
        assert requests and set(requests) == {'GET'}
        with database_engine.connect() as connection:
            assert before_copy == connection.execute(text('SELECT id,row_version FROM cafeteria.menu_weeks ORDER BY id')).all()
