"""D19: week context precedes accessible, grouped check warnings."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine

from test_admin_ux_browser import live_server, page_context
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']


@pytest.mark.parametrize('family,profile,slots', [
    ('cafeteria', 'staff_guest', 10), ('patienten', 'patient', 28),
])
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('coarse', [False, True], ids=['fine', 'coarse'])
def test_week_header_precedes_check_summary_with_keyboard_and_anchors(
    browser: Browser, live_server: str, page_context: Page, admin_engine: Engine,
    tmp_path: Path, family: str, profile: str, slots: int,
    width: int, height: int, coarse: bool,
) -> None:
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    for day in values['days']:
        for service in day['services']:
            service['service_start'] = ''
            service['service_end'] = ''
            for option in service['options']:
                option['allergens'] = []
                option['allergen_review_status'] = 'not_checked'
    _save(admin_engine, profile, values)

    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=coarse, reduced_motion='reduce',
        storage_state=page_context.context.storage_state(),
    ) as context:
        page = context.new_page()
        response = page.goto(f'/admin/{family}?week={DAY}', wait_until='networkidle')
        assert response is not None and response.status == 200
        page.evaluate('document.fonts.ready')
        assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
        expect(page.locator('h1')).to_have_count(1)
        heading = page.locator('h1')
        checks = page.locator('#week-check-summary')
        expect(heading).to_be_in_viewport()
        expect(checks).to_be_visible()
        expect(checks).to_be_in_viewport(ratio=1)
        expect(checks.locator('[role="status"]')).to_contain_text(
            f'{slots} Menüs: Allergenangaben nicht erfasst (nicht allergenfrei).',
        )
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        layout = checks.evaluate('''checks => {
            const heading = document.querySelector('h1');
            const header = heading.closest('.page-header');
            return {
                headingBottom: heading.getBoundingClientRect().bottom,
                headerBottom: header.getBoundingClientRect().bottom,
                checksTop: checks.getBoundingClientRect().top,
                headingFirst: Boolean(heading.compareDocumentPosition(checks)
                    & Node.DOCUMENT_POSITION_FOLLOWING),
            };
        }''')
        (tmp_path / 'header-check-layout.json').write_text(json.dumps(layout, indent=2))
        page.screenshot(path=str(tmp_path / f'{family}-{width}-{coarse}.png'))

        details = checks.locator('dialog')
        trigger = checks.locator('#week-check-entries-trigger')
        expect(trigger).to_have_attribute('data-semantic', 'ui.read_detail.review')
        expect(details).to_be_hidden()
        for _ in range(60):
            page.keyboard.press('Tab')
            if trigger.evaluate('element => element === document.activeElement'):
                break
        expect(trigger).to_be_focused()
        page.keyboard.press('Enter')
        expect(details).to_have_attribute('open', '')
        links = details.locator('.ui-read-detail-content a')
        for link in links.all():
            expect(page.locator(link.get_attribute('href'))).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        missing = links.filter(has_text='Allergenangaben nicht erfasst')
        expect(missing).to_have_count(slots)
        anchor = missing.last
        href = anchor.get_attribute('href')
        assert href is not None
        anchor.focus()
        page.keyboard.press('Enter')
        expect(details).to_be_hidden()
        expect(page.locator(href)).to_be_focused()
        expect(page.locator(href)).to_be_in_viewport()
        assert page.evaluate('scrollY > 0')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        trigger.focus()
        page.keyboard.press('Enter')
        expect(details).to_be_visible()
        page.keyboard.press('Escape')
        expect(details).to_be_hidden()
        expect(trigger).to_be_focused()

        # Last assertion preserves screenshots and exercises warnings on the red baseline.
        assert layout['headingFirst'], layout
        assert layout['checksTop'] >= layout['headingBottom'], layout
        assert layout['checksTop'] >= layout['headerBottom'], layout
