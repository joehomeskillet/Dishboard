from __future__ import annotations

from datetime import timedelta

from playwright.sync_api import expect

from test_admin_ux_browser import (
    admin_app as admin_app, admin_engine as admin_engine, browser as browser,
    live_server as live_server, page_context as page_context,
)
from test_admin_workflow_routes import WEEK, _login, _payload
from test_menu_collection import _save, _scope


def test_collection_navigation_search_and_mobile_layout(page_context, admin_app, admin_engine):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(client, admin_engine)
    payload = _payload()
    payload['description'] = 'Zubereitung mit Kartoffeln und frischen Kräutern. ' * 5
    _save(admin_engine, scope, title='Kartoffelgratin mit Gemüse', payload=payload)
    _save(admin_engine, scope, week=WEEK + timedelta(days=7), title='Tomatensuppe')
    page = page_context
    page.goto('/admin/patienten')
    page.get_by_role('navigation', name='Backend').get_by_role('link', name='Menüs', exact=True).click()
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
