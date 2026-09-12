from __future__ import annotations

# ruff: noqa: F811

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import Engine

from test_admin_ux_browser import admin_app, admin_engine, browser, live_server, page_context  # noqa: F401
from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


def _tab_to(page: Page, target, *, max_steps: int = 40) -> None:
    for _ in range(max_steps):
        page.keyboard.press('Tab')
        if target.evaluate('element => element === document.activeElement'):
            return
    pytest.fail(f'Tab did not reach {target}')


@pytest.mark.parametrize(('family', 'profile'), [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize(('width', 'height'), [(390, 844), (768, 1024)])
def test_week_form_keyboard_focus_after_modal_cancel_is_fully_visible(
    page_context: Page, admin_engine: Engine, family: str, profile: str, width: int, height: int,
) -> None:
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    _save_reviewed(admin_engine, profile, values)
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(f'/admin/{family}?week={DAY}')
    expect(page.locator('main')).to_have_attribute('data-status', 'ready')
    trigger = page.locator('[data-bs-target="#week-publish-modal"]')
    _tab_to(page, trigger)
    page.keyboard.press('Enter')
    modal = page.get_by_role('dialog')
    expect(modal).to_be_visible()
    cancel = modal.get_by_role('button', name='Abbrechen', exact=True)
    _tab_to(page, cancel, max_steps=8)
    page.keyboard.press('Enter')
    expect(modal).not_to_be_visible()
    expect(trigger).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('a[href*="/preview"]')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('link', name='Wochenangaben prüfen')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('details.admin-week-more > summary')).to_be_focused()
    page.keyboard.press('Tab')
    settings = page.locator('details.admin-week-settings > summary')
    expect(settings).to_be_focused()
    page.keyboard.press('Enter')
    expect(page.locator('details.admin-week-settings')).to_have_attribute('open', '')
    page.keyboard.press('Tab')
    title = page.locator('input[name="title"]')
    expect(title).to_be_focused()
    page.keyboard.press('Shift+Tab')
    expect(settings).to_be_focused()
    page.keyboard.press('Tab')
    expect(title).to_be_focused()
    title.fill('Angepasste Woche')
    expect(title).to_be_in_viewport(ratio=1)
    expect(title).to_be_focused()
    page.evaluate('''() => new Promise(resolve => requestAnimationFrame(() =>
        requestAnimationFrame(resolve)))''')
    scroll_y = page.evaluate('scrollY')
    page.keyboard.type(' ohne Fokuswechsel')
    expect(title).to_be_focused()
    expect(title).to_be_in_viewport(ratio=1)
    assert page.evaluate('scrollY') == scroll_y
