"""Browser test suite for MP-UI-BRAND-OPS brand and operations settings pages.

Verifies admin.branding_editor, admin.branding_preview and admin.operations_settings
in matrix states: normal viewports, full-width layout, headers, preview labelling,
vocabulary, 401/403, keyboard, zoom 200 %, contrast and no document overflow.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Browser, expect

from cafeteria.admin import branding_routes, operations_routes  # noqa: F401 - blueprint registration
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login

BRAND_PATH = '/admin/design/marke'
BRAND_PREVIEW_PATH = '/admin/design/marke/vorschau/1'
OPS_PATH = '/admin/bereiche-zeiten'
VIEWPORTS = [
    (1440, 900),
    (1024, 768),
    (768, 1024),
    (390, 844),
    (1920, 1080),
]


def _create_context(playwright_browser: Browser, server_url: str, client, *, javascript: bool = True):
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = playwright_browser.new_context(
        base_url=server_url,
        java_script_enabled=javascript,
        reduced_motion='reduce',
    )
    context.add_cookies([{
        'name': 'session',
        'value': cookie.value,
        'domain': '127.0.0.1',
        'path': '/',
    }])
    return context


def _assert_page_container_width(page, width: int) -> None:
    if width < 1024:
        return
    layout = page.evaluate('''() => {
        const main = document.querySelector('main.admin-main');
        const container = document.querySelector('.page-body > .container-xl');
        const maxWidth = getComputedStyle(container).maxWidth;
        const containerWidth = container.getBoundingClientRect().width;
        const cap = maxWidth === 'none' ? null : parseFloat(maxWidth);
        return {
            maxWidth,
            cap,
            mainWidth: main.clientWidth,
            ratio: containerWidth / main.clientWidth,
            containerWidth,
        };
    }''')
    if layout['maxWidth'] == 'none':
        assert layout['ratio'] >= 0.9
    else:
        frame_width = min(layout['cap'], layout['mainWidth'])
        assert layout['containerWidth'] >= frame_width - 2


def _assert_no_overflow_and_min_targets(page, min_height: int = 44, scope: str = 'main'):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    for locator in page.locator(f'{scope} :is(.btn, .form-select, .form-control)').all():
        if locator.is_visible():
            box = locator.bounding_box()
            assert box is not None and box['height'] >= min_height
            assert locator.evaluate('el => parseFloat(getComputedStyle(el).fontSize)') >= 14


@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_brand_editor_normal_state_and_viewports(
    browser: Browser, live_server: str, admin_app, admin_engine, width: int, height: int, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(BRAND_PATH)
        assert response is not None and response.status == 200

        expect(page.locator('main.admin-main')).to_have_attribute('data-layout', 'standard')
        _assert_page_container_width(page, width)

        expect(page.locator('h1.page-title')).to_have_text('Erscheinungsbild')
        expect(page.locator('.page-header-subtitle')).to_contain_text('Logo, Farben und Schrift')
        expect(page.locator('.admin-page-header .btn-list')).to_have_count(0)

        expect(page.get_by_role('heading', name='Veröffentlichte Version', exact=True)).to_be_visible()
        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
        expect(page.locator('.admin-area-tabs a[aria-current="page"]')).to_have_text('Erscheinungsbild')
        expect(page.get_by_role('heading', name='Gespeicherte Vorschau · Version 1', exact=True)).to_be_visible()
        expect(page.get_by_text('Live-Vorschau', exact=False)).to_have_count(0)
        expect(page.locator('.brand-color-swatch')).to_have_count(4)
        expect(page.locator('iframe.brand-preview-frame')).to_have_count(1)
        expect(page.locator('details.brand-history-card summary')).to_contain_text('Weitere Aktionen')

        _assert_no_overflow_and_min_targets(page)
        page.screenshot(path=str(tmp_path / f'brand-ops-editor-{width}x{height}.png'), full_page=True)


def test_brand_preview_standalone_page(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        response = page.goto(BRAND_PREVIEW_PATH)
        assert response is not None and response.status == 200
        expect(page.locator('h1')).to_have_text('Frisch zubereitet')
        expect(page.locator('.brand-preview-example .card-title')).to_contain_text('Pouletbrust')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(tmp_path / 'brand-ops-preview.png'), full_page=True)


@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_operations_normal_state_and_viewports(
    browser: Browser, live_server: str, admin_app, admin_engine, width: int, height: int, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(OPS_PATH)
        assert response is not None and response.status == 200

        # Full-width shell: the operations page no longer uses the narrow variant (audit group A).
        expect(page.locator('main.admin-main')).to_have_attribute('data-layout', 'standard')
        _assert_page_container_width(page, width)

        expect(page.locator('h1.page-title')).to_have_text('Bereiche & Öffnungszeiten')
        expect(page.locator('.page-header-subtitle')).to_contain_text('Ausgabe und Öffnungszeiten')
        expect(page.locator('.text-secondary').first).to_contain_text('neue Ausgaben')
        expect(page.get_by_role('button', name='Ausgabe laden', exact=True)).to_be_visible()

        _assert_no_overflow_and_min_targets(page)
        page.screenshot(path=str(tmp_path / f'brand-ops-operations-{width}x{height}.png'), full_page=True)


def test_brand_editor_forbidden_for_non_admin(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Editor'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        response = page.goto(BRAND_PATH)
        assert response is not None and response.status == 403


def test_operations_forbidden_for_non_admin(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Editor'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        response = page.goto(OPS_PATH)
        assert response is not None and response.status == 403


def test_brand_ops_unauthenticated_returns_401(browser: Browser, live_server: str, admin_app):  # noqa: F811
    with browser.new_context(base_url=live_server, reduced_motion='reduce') as context:
        page = context.new_page()
        for path in (BRAND_PATH, OPS_PATH):
            response = page.goto(path)
            assert response is not None and response.status == 401


def test_brand_ops_keyboard_navigation_and_focus(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(BRAND_PATH)

        page.keyboard.press('Tab')
        expect(page.locator('.skip-link')).to_be_focused()

        page.locator('#brand-name').focus()
        expect(page.locator('#brand-name')).to_be_focused()
        outline = page.locator('#brand-name').evaluate('el => getComputedStyle(el).outlineColor')
        assert outline != 'rgba(0, 0, 0, 0)'

        page.goto(OPS_PATH)
        page.locator('#allows_weekend').focus()
        expect(page.locator('#allows_weekend')).to_be_focused()

        page.screenshot(path=str(tmp_path / 'brand-ops-keyboard-focus.png'), full_page=True)


def test_brand_ops_zoom200_and_reduced_motion(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 640, 'height': 480})
        page.goto(BRAND_PATH)
        _assert_no_overflow_and_min_targets(page)
        expect(page.locator('h1.page-title')).to_be_visible()

        page.goto(OPS_PATH)
        _assert_no_overflow_and_min_targets(page)
        expect(page.locator('h1.page-title')).to_be_visible()

        page.screenshot(path=str(tmp_path / 'brand-ops-zoom200.png'), full_page=True)


def test_brand_ops_nojs_operations_save(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client, javascript=False) as context:
        page = context.new_page()
        page.goto(OPS_PATH)
        page.locator('#allows_weekend').check()
        page.get_by_role('button', name='Wochenendbetrieb speichern', exact=True).click()
        expect(page.locator('#allows_weekend')).to_be_checked()
        page.screenshot(path=str(tmp_path / 'brand-ops-nojs-weekend.png'), full_page=True)
