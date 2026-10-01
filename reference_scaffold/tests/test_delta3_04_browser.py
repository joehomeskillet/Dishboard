"""DELTA-3-04: static week forms and full, stable menu-note dialogs."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import live_server, page_context
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY
from test_delta_renderer_browser import VISIBILITY, source_revision
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']
LONG_NOTE = 'Vollständiger Hinweis für das gewählte Menü. ' * 12
GEOMETRY = '''() => ({scroll: scrollY, scrollbar: innerWidth-document.documentElement.clientWidth,
    boxes: ['.page-wrapper', '.admin-week-controls', '.menu-slot', '.admin-week-service'].map(s => {
        const r = document.querySelector(s).getBoundingClientRect();
        return {x:r.x, y:r.y, width:r.width, height:r.height};
    })})'''


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_static_forms_and_full_note_dialog(
    browser, live_server, page_context, admin_engine, tmp_path, family, profile,
    width, height, touch,
):
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    values['days'][0]['services'][0]['options'][0]['note'] = LONG_NOTE
    _save(admin_engine, profile, values)
    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=touch, reduced_motion='reduce',
        storage_state=page_context.context.storage_state(),
    ) as context:
        page = context.new_page()
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(tmp_path / f'{family}-{width}-{touch}.png'))
        expect(page.locator('details.admin-week-settings, details.admin-week-service')).to_have_count(0)
        expect(page.locator('.admin-week-settings [name="title"]')).to_be_visible()
        expect(page.locator('.admin-week-service [name="notice"]').first).to_be_visible()
        trigger = page.locator('.menu-slot [data-read-detail]').first
        trigger.scroll_into_view_if_needed()
        trigger.focus()
        before = page.evaluate(GEOMETRY)
        visible = trigger.evaluate(VISIBILITY)
        assert visible['icons'] == 1 and not visible['text'], visible
        page.keyboard.press('Enter')
        dialog = page.locator('dialog.ui-read-detail[open]')
        expect(dialog.locator('.shared-note')).to_have_text(LONG_NOTE.strip())
        expect(dialog.locator('details, summary, form')).to_have_count(0)
        expect(dialog.locator('h2')).to_be_focused()
        during = page.evaluate(GEOMETRY)
        page.screenshot(path=str(tmp_path / f'{family}-{width}-{touch}-dialog.png'))
        page.keyboard.press('Escape')
        expect(dialog).to_have_count(0)
        expect(trigger).to_be_focused()
        after = page.evaluate(GEOMETRY)
        (tmp_path / 'geometry.json').write_text(json.dumps(
            {'viewport': [width, height], 'revision': source_revision(),
             'before': before, 'during': during, 'after': after}, indent=2))
        for actual in (during, after):
            assert abs(actual['scroll'] - before['scroll']) <= 1
            for expected, found in zip(before['boxes'], actual['boxes'], strict=True):
                assert all(abs(found[key] - expected[key]) <= 1 for key in expected), (expected, found)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
