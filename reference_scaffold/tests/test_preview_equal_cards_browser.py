from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser
from sqlalchemy import Engine

from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_all_saved_menu_cards_share_size_without_hiding_long_content(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    options = [option for day in values['days'] for service in day['services'] for option in service['options']]
    # Put the tallest card late in the week, across a row and meal boundary.
    options[-1]['description'] = 'Frisch zubereitet mit saisonalem Gemüse. ' * 8
    options[-1]['note'] = 'Vollständiger langer Zubereitungshinweis bleibt sichtbar.'
    options[-1]['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    options[-1]['allergen_review_status'] = 'not_checked'
    _save(admin_app.extensions['cafeteria_db'], profile, values)
    cookie = client.get_cookie('session')
    assert cookie is not None
    with browser.new_context(base_url=live_server, java_script_enabled=False) as context:
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
        page = context.new_page()
        for width, height in [(390, 844), (768, 1024), (1024, 768), (1440, 1100)]:
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto(f'/admin/{family}/preview?week={DAY}')
            assert response is not None and response.status == 200
            page.evaluate('document.fonts.ready')
            assert page.locator('.preview-option h5').all_text_contents() == [option['title'] for option in options]
            assert options[-1]['description'].strip() in page.locator('.preview-option').last.inner_text()
            assert options[-1]['note'] in page.locator('.preview-option').last.inner_text()
            assert 'Enthält: Milch' in page.locator('.preview-option').last.inner_text()
            if width == 1024:
                page.screenshot(path=str(tmp_path / f'{family}-equal-cards.png'), full_page=True)
            dimensions = page.locator('.preview-option').evaluate_all('''elements => elements.map(element => {
                const box = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return {height: box.height, width: box.width,
                    overflowY: style.overflowY, overflowX: style.overflowX,
                    clientHeight: element.clientHeight, scrollHeight: element.scrollHeight,
                    clientWidth: element.clientWidth, scrollWidth: element.scrollWidth};
            })''')
            assert len(dimensions) == (10 if profile == 'staff_guest' else 28)
            for axis in ('height', 'width'):
                sizes = [item[axis] for item in dimensions]
                assert max(sizes) - min(sizes) <= 1, (family, width, axis, sizes)
            assert all(item['scrollHeight'] <= item['clientHeight'] + 1 for item in dimensions)
            assert all(item['scrollWidth'] <= item['clientWidth'] + 1 for item in dimensions)
            assert all(item['overflowY'] != 'hidden' and item['overflowX'] != 'hidden' for item in dimensions)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert page.locator('script, style, [style]').count() == 0
