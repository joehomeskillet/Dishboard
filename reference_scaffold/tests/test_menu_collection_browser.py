from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.workflow_review import get_component_review_token, review_component

from test_admin_ux_browser import (
    admin_app as admin_app, admin_engine as admin_engine, browser as browser,
    live_server as live_server, page_context as page_context,
)
from test_admin_workflow_routes import WEEK, _login, _payload
from test_menu_collection import _save, _scope
from test_branding_browser import live_branding as live_branding
from test_admin_workflow_routes import app as workflow_app, database_engine as database_engine  # noqa: F401


def test_collection_navigation_search_and_mobile_layout(page_context, admin_app, admin_engine):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(client, admin_engine)
    payload = _payload()
    payload['description'] = 'Zubereitung mit Kartoffeln und frischen Kräutern. ' * 5
    _save(admin_engine, scope, title='Kartoffelgratin mit Gemüse', payload=payload)
    _save(admin_engine, scope, week=WEEK + timedelta(days=7), title='Tomatensuppe')
    page = page_context
    page.goto('/admin/patienten')
    page.get_by_role('navigation', name='Backend').locator('.nav-link-title', has_text='Menüs').click()
    expect(page.get_by_role('heading', name='Menüs', exact=True)).to_be_visible()
    expect(page.locator('[data-menu-id]')).to_have_count(2)
    for width, height in [(390, 844), (1440, 1100), (2560, 1440)]:
        page.set_viewport_size({'width': width, 'height': height})
        assert not page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
        assert page.locator('[data-menu-id]').first.bounding_box()['width'] >= 250
    page.get_by_label('Menü oder Komponente suchen').fill('Kartoffelgratin')
    page.get_by_role('button', name='Suchen', exact=True).click()
    expect(page.locator('[data-menu-id]')).to_have_count(1)
    page.get_by_role('link', name='Kartoffelgratin mit Gemüse vom 31.08.2026 öffnen').click()
    assert '/admin/patienten/menu?' in page.url
    expect(page.locator('input[name="title"]')).to_have_value('Kartoffelgratin mit Gemüse')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height', [(390, 844), (1440, 1100)])
def test_icon_actions_use_tabler_tooltips_under_real_csp(
    live_branding, database_engine, browser, family, profile, width, height, tmp_path,
):
    origin, _, client, _, _ = live_branding
    _save(database_engine, _scope(client, database_engine, profile), title='Kartoffelgratin mit Gemüse')
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': origin}])
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        response = page.goto(origin + f'/admin/{family}/menues')
        assert response.status == 200
        assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
        for view in ('cards', 'list'):
            page.get_by_role('tab', name='Karten' if view == 'cards' else 'Liste', exact=True).click()
            link = page.locator(f'#menu-{view} [data-admin-icon-action]').first
            expect(link).to_have_attribute('aria-label', 'Kartoffelgratin mit Gemüse vom 31.08.2026 öffnen')
            assert link.inner_text() == 'Öffnen'
            expect(link.locator('use')).to_have_attribute('href', '/static/vendor/tabler-icons/tabler-icons.svg#tabler-pencil')
            assert link.evaluate('element => Boolean(window.tabler.Tooltip.getInstance(element))')
            link.hover()
            tooltip = page.get_by_role('tooltip')
            expect(tooltip).to_be_visible()
            expect(tooltip).to_have_text('Kartoffelgratin mit Gemüse vom 31.08.2026 öffnen')
            tooltip.hover()
            page.wait_for_timeout(150)  # Longer than Tabler's 50 ms hide delay.
            expect(tooltip).to_be_visible()
            page.mouse.move(0, 0)
            expect(tooltip).to_have_count(0)
            link.focus()
            page.keyboard.press('Shift+Tab')
            page.keyboard.press('Tab')
            expect(link).to_be_focused()
            expect(tooltip).to_be_visible()
            assert link.evaluate('element => getComputedStyle(element).outlineStyle !== "none"')
            assert link.get_attribute('aria-describedby') == tooltip.get_attribute('id')
            for target in (link, tooltip):
                box = target.bounding_box()
                assert box and box['x'] >= 0 and box['y'] >= 0
                assert box['x'] + box['width'] <= width + 1
                assert box['y'] + box['height'] <= height + 1
            box = link.bounding_box()
            assert box['width'] >= 48 and box['height'] >= 48
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
            page.screenshot(path=str(tmp_path / f'{family}-{view}-tooltip-{width}.png'), full_page=True)
            page.keyboard.press('Escape')
            expect(tooltip).to_have_count(0)
            expect(link).to_be_focused()
            assert link.get_attribute('aria-describedby') is None
        assert errors == []


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [True, False])
def test_icon_help_and_first_tap_work_with_and_without_javascript(
    live_branding, database_engine, browser, family, profile, javascript,
):
    origin, _, client, _, _ = live_branding
    _save(database_engine, _scope(client, database_engine, profile), title='Kartoffelgratin mit Gemüse')
    with browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True,
                             is_mobile=True, java_script_enabled=javascript) as context:
        context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': origin}])
        page = context.new_page()
        page.goto(origin + f'/admin/{family}/menues')
        link = page.locator('#menu-cards [data-admin-icon-action]').first
        destination = link.get_attribute('href')
        link.tap()
        page.wait_for_url(origin + destination)
        expect(page.locator('input[name="title"]')).to_have_value('Kartoffelgratin mit Gemüse')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height', [(390, 844), (1440, 1100)])
def test_collection_card_list_switch_keeps_scope_search_and_editor_targets(
    page_context, admin_app, admin_engine, family, profile, width, height, tmp_path,
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(client, admin_engine, profile)
    _save(admin_engine, scope, title='Kartoffelgratin mit Gemüse')
    _save(admin_engine, scope, week=WEEK + timedelta(days=7), title='Tomatensuppe')
    with admin_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_items SET allergen_review_status='checked'"))
        reviewed = connection.execute(text(
            "SELECT id,row_version FROM cafeteria.menu_items WHERE title='Tomatensuppe'"
        )).one()
    review_component(admin_engine, scope, reviewed.id,
                     get_component_review_token(admin_engine, scope, reviewed.id), reviewed.row_version)
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(f'/admin/{family}/menues')
    cards, listing = page.get_by_role('tab', name='Karten', exact=True), page.get_by_role('tab', name='Liste', exact=True)
    expect(cards).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#menu-cards')).to_be_visible()
    expect(page.locator('#menu-list')).to_be_hidden()
    expect(page.locator('#menu-cards [data-menu-id]').filter(has_text='Kartoffelgratin').locator('[data-review]')).to_have_attribute('data-review', 'open')
    expect(page.locator('#menu-cards [data-menu-id]').filter(has_text='Tomatensuppe').locator('[data-review]')).to_have_attribute('data-review', 'checked')
    list_url = page.url
    listing.click()
    expect(listing).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#menu-cards')).to_be_hidden()
    expect(page.locator('#menu-list')).to_be_visible()
    assert page.url == list_url
    rows = page.locator('#menu-list tbody tr')
    expect(rows).to_have_count(2)
    expect(rows.filter(has_text='Kartoffelgratin')).to_contain_text('Prüfung offen')
    expect(rows.filter(has_text='Tomatensuppe')).to_contain_text('Geprüft')
    for row in rows.all():
        expect(row).to_contain_text('Mittag')
        expect(row).to_contain_text('Menü 1')
        link = row.get_by_role('link')
        destination = urlsplit(link.get_attribute('href'))
        assert destination.path == f'/admin/{family}/menu'
        fields = parse_qs(destination.query)
        assert set(fields) == {'week', 'day', 'meal', 'option'}
        assert fields['week'] == fields['day']
        assert fields['meal'] == ['LUNCH'] and fields['option'] == ['MENU_1']
        assert link.bounding_box()['height'] >= 48
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
    assert not page.locator('#menu-list img').count()
    if family == 'patienten':
        assert not any(word in page.content().lower() for word in ('price', 'rappen', 'chf'))
    page.screenshot(path=str(tmp_path / f'{family}-list-{width}.png'), full_page=True)
    listing.focus()
    page.keyboard.press('ArrowLeft')
    expect(cards).to_be_focused()
    expect(cards).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#menu-cards')).to_be_visible()
    page.get_by_label('Menü oder Komponente suchen').fill('Kartoffelgratin')
    page.get_by_role('button', name='Suchen', exact=True).click()
    assert parse_qs(urlsplit(page.url).query) == {'q': ['Kartoffelgratin']}
    listing.click()
    expect(rows).to_have_count(1)
    rows.get_by_role('link').click()
    expect(page.locator('input[name="title"]')).to_have_value('Kartoffelgratin mit Gemüse')
