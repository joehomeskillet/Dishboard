from __future__ import annotations

import re

from playwright.sync_api import expect

from test_admin_ux_browser import (
    admin_app as admin_app, admin_engine as admin_engine, browser as browser,
    live_server as live_server, page_context as page_context,
)


def test_week_creation_and_tablet_layout(page_context):
    page = page_context
    page.goto('/admin/patienten')
    page.get_by_role('navigation', name='Backend').get_by_role('link', name='Wochenverwaltung', exact=True).click()
    expect(page.get_by_role('heading', name='Wochenverwaltung', exact=True)).to_be_visible()
    for width, height in [(768, 1024), (800, 1280), (1024, 768), (1280, 800), (390, 844)]:
        page.set_viewport_size({'width': width, 'height': height})
        toggle = page.get_by_role('button', name='Menü', exact=True)
        if width < 1200:
            expect(toggle).to_be_visible()
            toggle.click()
            expect(page.locator('#sidebar-menu')).to_have_class(re.compile(r'\bshow\b'))
            expect(page.get_by_role('navigation', name='Backend')).to_be_visible()
            toggle.click()
            expect(page.get_by_role('navigation', name='Backend')).to_be_hidden()
        assert not page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
        for selector in ['input[type="date"]', 'input[name="title"]', 'textarea', 'button[type="submit"]']:
            for control in page.locator(selector).all():
                if control.is_visible():
                    assert control.bounding_box()['height'] >= 48
    page.get_by_label('Wochenbeginn (Montag)').fill('2027-01-04')
    page.get_by_label('Wochentitel', exact=True).fill('Tabletwoche')
    page.get_by_role('button', name='Woche anlegen').click()
    assert '/admin/patienten?week=2027-01-04' in page.url
    page.goto('/admin/patienten/wochen')
    expect(page.get_by_text('Tabletwoche', exact=True)).to_be_visible()
