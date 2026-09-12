from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.workflow import publish_draft
from cafeteria.workflow_partial_store import persist_week_header
from cafeteria.workflow_review import get_component_review_token, review_component
from test_admin_workflow_db import _save_reviewed, _staff_values
from test_admin_workflow_routes import (
    WEEK, _payload, _scope, database_engine as database_engine,
)
from test_branding_browser import live_branding as live_branding
from test_menu_collection import _save
from test_rendered_ui import browser as browser

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / '.claude' / 'evidence' / 'ui-korrektur-0912' / 'menus'
VIEWPORTS = [
    (1366, 768),
    (1920, 1080),
    (768, 1024),
    (390, 844),
]


def _shot(page, name: str) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE_DIR / f'{name}.png'), full_page=True)


def test_menu_collection_ui_korrektur(live_branding, database_engine, browser):
    origin, _, client, actor, _ = live_branding
    scope = _scope(database_engine, actor, 'patient')

    # Menu 1: Reviewed and checked, with allergens
    payload_reviewed = _payload(staff=False)
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
    payload_missing = _payload(staff=False)
    payload_missing['allergens'] = []
    payload_missing['description'] = long_desc
    payload_missing['note'] = long_note
    _save(database_engine, scope, week=WEEK + timedelta(days=7), title='Kartoffelgratin mit Gemüse', payload=payload_missing)

    session_cookie = client.get_cookie('session').value

    for width, height in VIEWPORTS:
        with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
            context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
            page = context.new_page()
            response = page.goto(f'{origin}/admin/patienten/menues')
            assert response.status == 200

            # 1. No horizontal scrollbar
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')

            # 2. First card visible without scrolling on 1366x768 and 1920x1080
            first_card = page.locator('#menu-cards [data-menu-id]').first
            expect(first_card).to_be_visible()
            box = first_card.bounding_box()
            assert box is not None
            if height >= 768:
                assert box['y'] < height, f'Card top {box["y"]} is below viewport {height}'

            # 3. Screenshot normal state
            _shot(page, f'menues-normal-{width}x{height}')

            # 4. Status separation on cards
            # Tomatensuppe has verified review badge
            soup_card = page.locator('#menu-cards [data-menu-id]').filter(has_text='Tomatensuppe')
            expect(soup_card.locator('[data-review="checked"]')).to_contain_text('Geprüft · gespeicherter Stand bestätigt')

            # Kartoffelgratin has open review badge AND missing allergens warning directly on card
            gratin_card = page.locator('#menu-cards [data-menu-id]').filter(has_text='Kartoffelgratin')
            expect(gratin_card.locator('[data-review="open"]')).to_contain_text('Prüfung offen')
            expect(gratin_card).to_contain_text('Allergenangaben nicht erfasst')

            # 5. Long description/note is under collapsible "Hinweis anzeigen"
            details = gratin_card.locator('details.menu-note-details')
            expect(details).to_have_count(1)
            summary = details.locator('summary')
            expect(summary).to_contain_text('Hinweis anzeigen')

            # Before open, description is inside details content
            expect(details.locator('.menu-description')).to_contain_text(long_desc)
            expect(details.locator('.shared-note')).to_contain_text(long_note)

            # Click to open details
            summary.click()
            expect(details).to_have_attribute('open', '')

            # 6. Exactly one action button per card
            actions = gratin_card.locator('.card-footer .btn')
            expect(actions).to_have_count(1)
            expect(actions).to_contain_text('Öffnen')
            assert actions.bounding_box()['height'] >= 44

    # Test 200% zoom
    with browser.new_context(viewport={'width': 1366, 'height': 768}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/patienten/menues')
        page.evaluate("document.documentElement.style.zoom = '2'")
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        _shot(page, 'menues-zoom200-1366x768')
        page.evaluate("document.documentElement.style.zoom = ''")

    # Test Empty / No-match search screenshots
    with browser.new_context(viewport={'width': 1366, 'height': 768}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/patienten/menues?q=UnbekanntesGericht')
        expect(page.locator('#menu-cards [data-empty-kind="no_match"]')).to_be_visible()
        _shot(page, 'menues-nomatch-1366x768')

    # Test without JavaScript
    with browser.new_context(viewport={'width': 1366, 'height': 768}, java_script_enabled=False) as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/patienten/menues')
        expect(page.locator('#menu-cards')).to_be_visible()
        # Open action link has correct href
        link = page.locator('#menu-cards [data-menu-id]').first.locator('.card-footer a')
        dest = link.get_attribute('href')
        assert '/admin/patienten/menu?week=' in dest


def test_week_management_ui_korrektur(live_branding, database_engine, browser):
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
            response = page.goto(f'{origin}/admin/patienten/wochen')
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
            _shot(page, f'wochen-normal-{width}x{height}')

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
            expect(primary_btn).to_contain_text('Woche öffnen')
            assert primary_btn.bounding_box()['height'] >= 44

            secondary_btns = first_row.locator('.week-actions .btn-list .btn')
            if secondary_btns.count() > 0:
                for idx in range(secondary_btns.count()):
                    btn = secondary_btns.nth(idx)
                    expect(btn).not_to_have_class('btn-primary')
                    assert btn.bounding_box()['height'] >= 44

            # 6. Scoped profile tabs inside card-header
            card_header = page.locator('.card-header')
            expect(card_header.locator('.profile-tabs')).to_be_visible()

    # Test published week on cafeteria
    with browser.new_context(viewport={'width': 1366, 'height': 768}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/cafeteria/wochen')
        live_row = page.locator('tr[data-status="live"]')
        expect(live_row).to_be_visible()
        expect(live_row.locator('td[data-label="Status"]')).to_contain_text('Veröffentlicht · entspricht dem gespeicherten Stand')
        _shot(page, 'wochen-live-1366x768')

    # Test 200% zoom
    with browser.new_context(viewport={'width': 1366, 'height': 768}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/patienten/wochen')
        page.evaluate("document.documentElement.style.zoom = '2'")
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        _shot(page, 'wochen-zoom200-1366x768')
        page.evaluate("document.documentElement.style.zoom = ''")

    # Test "Neue Woche anlegen" details interaction and error handling
    with browser.new_context(viewport={'width': 1366, 'height': 768}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/patienten/wochen')

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
        _shot(page, 'wochen-fehler-1366x768')

    # Test without JavaScript
    with browser.new_context(viewport={'width': 1366, 'height': 768}, java_script_enabled=False) as context:
        context.add_cookies([{'name': 'session', 'value': session_cookie, 'url': origin}])
        page = context.new_page()
        page.goto(f'{origin}/admin/patienten/wochen')
        row = page.locator('tr[data-week-id]').first
        link = row.locator('.week-action-primary')
        dest = link.get_attribute('href')
        assert '/admin/patienten?week=' in dest
