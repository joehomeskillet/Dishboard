from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import (
    admin_app as admin_app, admin_engine as admin_engine, browser as browser,
    live_server as live_server, page_context as page_context,
)
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_rendered_ui import app as app


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_tabler_lists_preserve_navigation_and_tablet_layout(page_context, admin_engine, family):
    _save(admin_engine, 'staff_guest', _staff_values())
    _save(admin_engine, 'patient', _patient_values())
    page = page_context
    for route, row in [('menues', '[data-menu-id]'), ('wochen', '[data-week-id]')]:
        response = page.goto(f'/admin/{family}/{route}')
        assert response.status == 200
        expect(page.locator(row).first).to_be_visible()
        assert page.locator('link[href$="vendor/tabler/tabler.min.css"]').count() == 1
        assert page.locator('svg use[href*="tabler-icons.svg#"]').count() > 5
        assert page.locator('[style], script:not([src])').count() == 0
        if family == 'patienten':
            assert not re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I)
        for width, height in [(768, 1024), (800, 1280), (1024, 768), (1280, 800), (390, 844)]:
            page.set_viewport_size({'width': width, 'height': height})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (route, width)
            for control in page.locator('input[type="date"], input[name="title"], textarea, button[type="submit"]').all():
                assert control.bounding_box()['height'] >= 44, (width, control.evaluate('(el) => el.outerHTML'))
            for link in page.get_by_role('navigation', name='Backend').get_by_role('link').all():
                expect(link).to_be_visible()
                assert link.bounding_box()['height'] >= 44
            output = os.environ.get('TABLER_PROOF_DIR')
            if output:
                directory = Path(output)
                directory.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(directory / f'{family}-{route}-{width}x{height}.png'), full_page=True)
        page.locator(f'{row} a[href]').first.click()
        assert '/menu?' in page.url if route == 'menues' else f'/admin/{family}?' in page.url


def test_tabler_styles_do_not_load_on_public_or_login_pages(app):
    client = app.test_client()
    for route in ('/auth/local', '/cafeteria/wochenangebot/', '/patienten/wochenplan/'):
        response = client.get(route)
        assert response.status_code == 200, route
        assert 'tabler' not in response.get_data(as_text=True)
