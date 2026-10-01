"""DELTA-3-05: visible course fields, search and atomic native submission."""
from __future__ import annotations

from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import live_server, page_context
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY
from test_delta_renderer_browser import VISIBILITY
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height,touch', [(1440, 900, False), (1440, 900, True), (390, 844, False), (390, 844, True)])
@pytest.mark.parametrize('javascript', [True, False])
def test_course_fields_and_atomic_submission(
    browser, live_server, page_context, admin_engine, tmp_path, family, profile,
    width, height, touch, javascript,
):
    _save(admin_engine, profile, _staff_values() if family == 'cafeteria' else _patient_values())
    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=touch, java_script_enabled=javascript, reduced_motion='reduce',
        storage_state=page_context.context.storage_state(),
    ) as context:
        page = context.new_page()
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        page.evaluate('document.fonts.ready')
        editor = page.locator('.admin-week-course-editor').first
        editor.scroll_into_view_if_needed()
        page.screenshot(path=str(tmp_path / f'{family}-{width}-{touch}-js{javascript}.png'))
        expect(editor.locator('details, summary')).to_have_count(0)
        assert editor.evaluate('el => el.tagName') == 'SECTION'
        search = editor.locator('form[method="get"]')
        expect(search.locator('[name="recipe_search"]')).to_be_visible()
        form = editor.locator('form[method="post"]')
        expect(form.locator('select')).to_have_count(12)
        for control in form.locator('select').all():
            expect(control).to_be_visible()
            assert control.evaluate('el => el.form === el.closest("form")')
        before = form.evaluate('el => Object.fromEntries(new FormData(el))')
        form.locator('[name="soup_state"]').select_option('not_offered')
        form.locator('[name="dessert_state"]').select_option('not_offered')
        form.locator('[name="MENU_1_soup_state"]').select_option('not_offered')
        save = form.locator('[data-semantic="actions.save"]')
        visible = save.evaluate(VISIBILITY)
        assert visible['icons'] == 1 and not visible['text'], visible
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            save.click()
        assert saved.value.status == 303
        payload = parse_qs(saved.value.request.post_data, keep_blank_values=True)
        assert set(payload) == set(before)
        for key in before:
            assert payload[key] == [
                'not_offered' if key in ('soup_state', 'dessert_state', 'MENU_1_soup_state') else before[key]
            ], key
        page.wait_for_load_state()
        expect(page.locator('.admin-week-course[data-course="soup"]').first).to_contain_text('Keine Suppe')
        expect(page.locator('.admin-week-course[data-course="dessert"]').first).to_contain_text('Kein Dessert')
        expect(page.locator('details.admin-week-course-editor')).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
