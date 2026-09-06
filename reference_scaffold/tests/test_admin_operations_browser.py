"""Native Tabler operations forms work with and without JavaScript."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_admin_display_browser import _assert_controls, _context
from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server,
)
from test_admin_workflow_routes import _login

PATH = '/admin/bereiche-zeiten'


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_native_operations_controls_save_focus_and_original_exception(
    browser, live_server, admin_app, admin_engine, width, javascript, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _context(browser, live_server, client, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': 1100})
        page.goto(PATH)
        expect(page.locator('a[href="/admin/bereiche-zeiten"]')).to_have_attribute('aria-current', 'page')
        _assert_controls(page)
        assert page.locator('[style], [onclick], script:not([src])').count() == 0
        page.screenshot(path=str(tmp_path / f'operations-{width}-js-{javascript}.png'), full_page=True)
        page.locator('#allows_weekend').check()
        page.get_by_role('button', name='Wochenendbetrieb speichern', exact=True).click()
        expect(page.locator('#allows_weekend')).to_be_checked()
        page.locator('#staff_guest-slot_6_LUNCH_state').select_option('open')
        page.locator('#staff_guest-slot_6_LUNCH_start').fill('11:30')
        page.locator('#staff_guest-slot_6_LUNCH_end').fill('13:30')
        page.locator('#schedule-staff_guest button[type="submit"]').click()
        expect(page.locator('#staff_guest-slot_6_LUNCH_start')).to_have_value('11:30')
        page.locator('#staff_guest-slot_6_LUNCH_end').fill('10:00')
        page.locator('#schedule-staff_guest button[type="submit"]').click()
        invalid = page.locator('#staff_guest-slot_6_LUNCH_end')
        expect(invalid).to_have_attribute('aria-invalid', 'true')
        expect(invalid).to_be_focused()
        expect(page.locator('#staff_guest-slot_6_LUNCH_start')).to_have_value('11:30')
        assert invalid.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.screenshot(path=str(tmp_path / f'operations-error-{width}-js-{javascript}.png'), full_page=True)
        page.goto(PATH)
        page.locator('#profile').select_option('staff_guest')
        page.locator('#date').fill('2026-09-05')
        page.locator('#meal').select_option('LUNCH')
        page.get_by_role('button', name='Service laden', exact=True).click()
        expect(page.locator('#exception-save input[name="row_version"]')).to_have_value('0')
        expect(page.locator('#service_start')).to_have_value('11:30')
        page.locator('#service_end').fill('14:00')
        _assert_controls(page)
        page.get_by_role('button', name='Ausnahme speichern', exact=True).click()
        expect(page.locator('[data-kind="time"]')).to_be_visible()
        page.screenshot(path=str(tmp_path / f'operations-saved-{width}-js-{javascript}.png'), full_page=True)
