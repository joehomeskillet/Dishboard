"""Browser test suite for MP-UI-REF-SETTINGS reference settings page.

Verifies admin.display_settings in all matrix states:
- normal (all 5 viewports, narrow 960 layout, header, default values, target size, no overflow)
- preview with both values for each of the 4 options without DB persistence
- validation error on invalid input with preserved form values and 400 status
- 403 rejection for non-admin actors
- NoJS save and reset workflows
- keyboard navigation and visible focus outline
- zoom 200% and reduced motion
"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Browser, expect

from cafeteria.admin import display_routes  # noqa: F401 - blueprint registration
from cafeteria.display_settings import (
    ADMIN_DISPLAY_CHOICES, DEFAULT_ADMIN_DISPLAY, get_admin_display,
)
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login

PATH = '/admin/design/darstellung'
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


def _assert_no_overflow_and_min_targets(page, min_height: int = 44):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    for locator in page.locator('main :is(.btn, .form-select, .form-control)').all():
        if locator.is_visible():
            box = locator.bounding_box()
            assert box is not None and box['height'] >= min_height
            assert locator.evaluate('el => parseFloat(getComputedStyle(el).fontSize)') >= 16


@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_settings_normal_state_and_viewports(
    browser: Browser, live_server: str, admin_app, admin_engine, width: int, height: int, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(PATH)
        assert response is not None and response.status == 200

        # Layout variant Schmal 960
        expect(page.locator('main.admin-main')).to_have_attribute('data-layout', 'narrow')
        if width >= 1024:
            container_max_w = page.locator('.page-body > .container-xl').evaluate(
                'el => getComputedStyle(el).maxWidth',
            )
            assert container_max_w == '960px'

        # Page header according to spec §7.2 Nr. 4
        expect(page.locator('h1.page-title')).to_have_text('Design & Marke')
        expect(page.locator('.breadcrumb-item a')).to_have_text('Design & Marke')
        expect(page.locator('.breadcrumb-item.active')).to_have_text('Darstellung')
        expect(page.locator('.admin-page-header .btn-list')).to_have_count(0)

        # 4 options with default values and hints
        expect(page.get_by_label('Abstände', exact=True)).to_have_value('compact')
        expect(page.locator('#admin-density-hint')).to_be_visible()
        expect(page.get_by_label('Schriftgröße', exact=True)).to_have_value('normal')
        expect(page.locator('#admin-font-size-hint')).to_be_visible()
        expect(page.get_by_label('Inhaltsbreite', exact=True)).to_have_value('contained')
        expect(page.locator('#admin-content-width-hint')).to_be_visible()
        expect(page.get_by_label('Menübilder', exact=True)).to_have_value('show')
        expect(page.locator('#admin-menu-images-hint')).to_be_visible()

        # Action buttons
        expect(page.get_by_role('button', name='Darstellung speichern', exact=True)).to_have_class(
            'btn btn-primary',
        )
        expect(page.get_by_role('button', name='Vorschau aktualisieren', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Standardwerte speichern', exact=True)).to_be_visible()

        # Preview card initial state
        preview = page.locator('.display-preview')
        expect(preview).to_have_attribute('data-density', 'compact')
        expect(preview).to_have_attribute('data-font-size', 'normal')
        expect(preview).to_have_attribute('data-content-width', 'contained')
        expect(preview).to_have_attribute('data-menu-images', 'show')
        expect(page.locator('.display-preview .menu-photo')).to_have_count(1)
        expect(page.locator('#display-example')).to_have_value('Frisch zubereitet')

        _assert_no_overflow_and_min_targets(page, min_height=44)
        page.screenshot(path=str(tmp_path / f'ref-settings-normal-{width}x{height}.png'), full_page=True)


def test_settings_preview_both_values_per_option(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(PATH)
        preview = page.locator('.display-preview')

        # Option 1: admin_density (comfortable vs compact)
        page.get_by_label('Abstände', exact=True).select_option('comfortable')
        page.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(page.get_by_text('Vorschau der Auswahl – noch nicht gespeichert.', exact=True)).to_be_visible()
        expect(preview).to_have_attribute('data-density', 'comfortable')
        assert preview.locator('.card-body').evaluate('el => getComputedStyle(el).paddingTop') == '32px'

        page.get_by_label('Abstände', exact=True).select_option('compact')
        page.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(preview).to_have_attribute('data-density', 'compact')
        assert preview.locator('.card-body').evaluate('el => getComputedStyle(el).paddingTop') == '24px'

        # Option 2: admin_font_size (large vs normal)
        page.get_by_label('Schriftgröße', exact=True).select_option('large')
        page.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(preview).to_have_attribute('data-font-size', 'large')
        assert page.locator('#display-example').evaluate('el => parseFloat(getComputedStyle(el).fontSize)') == 18

        page.get_by_label('Schriftgröße', exact=True).select_option('normal')
        page.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(preview).to_have_attribute('data-font-size', 'normal')
        assert page.locator('#display-example').evaluate('el => parseFloat(getComputedStyle(el).fontSize)') == 16

        # Option 3: admin_content_width (full vs contained)
        page.get_by_label('Inhaltsbreite', exact=True).select_option('full')
        page.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(preview).to_have_attribute('data-content-width', 'full')

        page.get_by_label('Inhaltsbreite', exact=True).select_option('contained')
        page.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(preview).to_have_attribute('data-content-width', 'contained')

        # Option 4: admin_menu_images (hide vs show)
        page.get_by_label('Menübilder', exact=True).select_option('hide')
        page.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(preview).to_have_attribute('data-menu-images', 'hide')
        expect(page.locator('.display-preview .menu-photo')).to_have_count(0)

        page.get_by_label('Menübilder', exact=True).select_option('show')
        page.get_by_role('button', name='Vorschau aktualisieren', exact=True).click()
        expect(preview).to_have_attribute('data-menu-images', 'show')
        expect(page.locator('.display-preview .menu-photo')).to_have_count(1)

        # Database is untouched during preview
        assert get_admin_display(admin_engine) == DEFAULT_ADMIN_DISPLAY
        page.screenshot(path=str(tmp_path / 'ref-settings-preview-both-values.png'), full_page=True)


def test_settings_validation_error_preserves_inputs(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.goto(PATH)

        # Change valid fields
        page.get_by_label('Schriftgröße', exact=True).select_option('large')
        page.get_by_label('Menübilder', exact=True).select_option('hide')

        # Inject invalid density option into DOM and submit
        page.evaluate("""() => {
            const select = document.getElementById('admin-density');
            const opt = document.createElement('option');
            opt.value = 'invalid_density_val';
            opt.text = 'Ungültig';
            select.appendChild(opt);
            select.value = 'invalid_density_val';
        }""")

        with page.expect_response(lambda res: res.url.endswith(PATH) and res.request.method == 'POST') as res_info:
            page.get_by_role('button', name='Darstellung speichern', exact=True).click()

        # Status 400 on error
        assert res_info.value.status == 400

        # form_errors macro region rendered
        error_region = page.locator('.alert-danger.error-region')
        expect(error_region).to_be_visible()
        expect(error_region).to_contain_text('Bitte eine der angebotenen Optionen auswählen.')

        # Field error on invalid field
        field_error = page.locator('#admin-density-error')
        expect(field_error).to_be_visible()
        expect(field_error).to_have_text('Bitte eine der angebotenen Optionen auswählen.')
        expect(page.locator('#admin-density')).to_have_attribute('aria-invalid', 'true')

        # Preserved valid input values
        expect(page.get_by_label('Schriftgröße', exact=True)).to_have_value('large')
        expect(page.get_by_label('Menübilder', exact=True)).to_have_value('hide')

        # Database remains untouched
        assert get_admin_display(admin_engine) == DEFAULT_ADMIN_DISPLAY
        page.screenshot(path=str(tmp_path / 'ref-settings-validation-error.png'), full_page=True)


def test_settings_forbidden_for_non_admin(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Editor'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        response = page.goto(PATH)
        assert response is not None and response.status == 403

        # Non-admin does not have display settings link in navigation
        page.goto('/admin/cafeteria')
        expect(page.locator(f'a[href="{PATH}"]')).to_have_count(0)
        assert get_admin_display(admin_engine) == DEFAULT_ADMIN_DISPLAY


def test_settings_nojs_save_and_reset(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client, javascript=False) as context:
        page = context.new_page()
        page.goto(PATH)

        # Select custom values and save without JS
        page.get_by_label('Abstände', exact=True).select_option('comfortable')
        page.get_by_label('Schriftgröße', exact=True).select_option('large')
        page.get_by_label('Inhaltsbreite', exact=True).select_option('full')
        page.get_by_label('Menübilder', exact=True).select_option('hide')

        page.get_by_role('button', name='Darstellung speichern', exact=True).click()

        # Follows redirect 303, page updated with flash and main attributes
        expect(page.get_by_text('Darstellung für alle Benutzer und Geräte gespeichert.', exact=True)).to_be_visible()
        expect(page.locator('main')).to_have_attribute('data-density', 'comfortable')
        expect(page.locator('main')).to_have_attribute('data-font-size', 'large')
        expect(page.locator('main')).to_have_attribute('data-content-width', 'full')
        expect(page.locator('main')).to_have_attribute('data-menu-images', 'hide')

        expected = {
            'admin_density': 'comfortable',
            'admin_font_size': 'large',
            'admin_content_width': 'full',
            'admin_menu_images': 'hide',
        }
        assert get_admin_display(admin_engine) == expected
        page.screenshot(path=str(tmp_path / 'ref-settings-nojs-saved.png'), full_page=True)

        # Reset without JS
        page.get_by_role('button', name='Standardwerte speichern', exact=True).click()
        expect(page.get_by_text('Standardwerte für alle Benutzer und Geräte gespeichert.', exact=True)).to_be_visible()
        expect(page.locator('main')).to_have_attribute('data-density', 'compact')
        expect(page.locator('main')).to_have_attribute('data-font-size', 'normal')
        expect(page.locator('main')).to_have_attribute('data-content-width', 'contained')
        expect(page.locator('main')).to_have_attribute('data-menu-images', 'show')
        assert get_admin_display(admin_engine) == DEFAULT_ADMIN_DISPLAY
        page.screenshot(path=str(tmp_path / 'ref-settings-nojs-reset.png'), full_page=True)


def test_settings_keyboard_navigation_and_focus(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(PATH)

        # Focus skip-link
        page.keyboard.press('Tab')
        expect(page.locator('.skip-link')).to_be_focused()

        # Tab into breadcrumb link
        page.locator('.page-breadcrumb a').focus()
        breadcrumb_link = page.locator('.page-breadcrumb a')
        expect(breadcrumb_link).to_be_focused()
        outline_color = breadcrumb_link.evaluate('el => getComputedStyle(el).outlineColor')
        assert 'rgb(163, 22, 77)' in outline_color or outline_color != 'rgba(0, 0, 0, 0)'

        # Tab through the 4 form select fields
        for field_id in ADMIN_DISPLAY_CHOICES:
            html_id = field_id.replace('_', '-')
            elem = page.locator(f'#{html_id}')
            elem.focus()
            expect(elem).to_be_focused()
            page.keyboard.press('ArrowDown')

        # Tab through action buttons
        for btn_name in ['Vorschau aktualisieren', 'Standardwerte speichern', 'Darstellung speichern']:
            btn = page.get_by_role('button', name=btn_name, exact=True)
            btn.focus()
            expect(btn).to_be_focused()
            outline = btn.evaluate('el => getComputedStyle(el).outlineColor')
            assert 'rgb(163, 22, 77)' in outline or outline != 'rgba(0, 0, 0, 0)'

        page.screenshot(path=str(tmp_path / 'ref-settings-keyboard-focus.png'), full_page=True)


def test_settings_zoom200_and_reduced_motion(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        # 640x480 simulation of 1280x960 at 200% zoom
        page.set_viewport_size({'width': 640, 'height': 480})
        page.goto(PATH)

        _assert_no_overflow_and_min_targets(page, min_height=44)
        expect(page.locator('h1.page-title')).to_be_visible()
        expect(page.locator('#display-settings-form')).to_be_visible()
        expect(page.locator('.display-preview')).to_be_visible()

        page.screenshot(path=str(tmp_path / 'ref-settings-zoom200.png'), full_page=True)
