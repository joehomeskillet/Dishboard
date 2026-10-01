"""UI-DELTA: static publication fallback and exclusive confirmation actions."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import live_server, page_context
from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import DAY
from test_delta_renderer_browser import VISIBILITY
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_confirmation_modes_and_native_fallback(
    browser, live_server, page_context, admin_engine, tmp_path, family, profile,
    width, height, touch,
):
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    _save_reviewed(admin_engine, profile, values)
    for js in (True, False):
        with browser.new_context(
            base_url=live_server, viewport={'width': width, 'height': height},
            has_touch=touch, java_script_enabled=js, reduced_motion='reduce',
            storage_state=page_context.context.storage_state(),
        ) as context:
            page = context.new_page()
            assert page.goto(f'/admin/{family}?week={DAY}').status == 200
            page.evaluate('document.fonts.ready')
            if js:
                trigger = page.locator('[data-bs-target="#week-publish-modal"]')
                trigger.click()
                area = page.locator('#week-publish-modal')
                expect(area).to_be_visible()
                expect(area.locator('[data-bs-dismiss="modal"]')).to_have_count(1)
                controls = area.locator('.modal-footer button')
            else:
                area = page.locator('.admin-week-nojs-publish')
                expect(area).to_be_visible()
                expect(area.locator('details, summary')).to_have_count(0)
                controls = area.locator('button')
                expect(controls).to_have_attribute('form', 'week-publish-form')
            for control in controls.all():
                visible = control.evaluate(VISIBILITY)
                assert visible['icons'] == 0, visible
                assert visible['text'], visible
                assert visible['text'] in control.get_attribute('aria-label')
            page.screenshot(path=str(tmp_path / f'{family}-{width}-{touch}-js{js}.png'))
            if js:
                area.get_by_role('button', name='Abbrechen', exact=True).click()
                expect(area).to_be_hidden()
                expect(trigger).to_be_focused()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def test_empty_week_has_one_first_slot_action(page_context):
    page = page_context
    assert page.goto('/admin/cafeteria?week=2026-09-07').status == 200
    first = page.locator('.menu-slot').first.locator('a[data-semantic="actions.add"]')
    expect(first).to_be_visible()
    href = first.get_attribute('href')
    expect(page.locator(f'a[href="{href}"]')).to_have_count(1)
    first.click()
    expect(page.locator('form[data-menu-editor]')).to_be_visible()
