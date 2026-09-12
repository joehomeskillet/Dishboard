"""Global density stays server-owned across devices, JS modes, CSV states and old storage."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect

from cafeteria.admin import display_routes  # noqa: F401 - complete shared blueprint
from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import DAY, _login

PATH = '/admin/design/darstellung'


def _context(playwright_browser, server_url, client, *, javascript=True):
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = playwright_browser.new_context(base_url=server_url, java_script_enabled=javascript, reduced_motion='reduce')
    context.add_cookies([{'name': 'session', 'value': cookie.value, 'domain': '127.0.0.1', 'path': '/'}])
    return context


def _assert_controls(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    for locator in page.locator('main :is(.btn, .form-select, .form-control)').all():
        if locator.is_visible():
            box = locator.bounding_box()
            assert box is not None and box['height'] >= 48
            assert locator.evaluate('el => parseFloat(getComputedStyle(el).fontSize)') >= 16


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_compact_default_without_local_control_preserves_help_and_targets(
    browser, live_server, admin_app, admin_engine, width, javascript, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _context(browser, live_server, client, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': 1100})
        for family in ('cafeteria', 'patienten'):
            page.goto(f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
            expect(page.locator('main')).to_have_attribute('data-density', 'compact')
            expect(page.get_by_label('Kompakte Ansicht', exact=True)).to_have_count(0)
            for summary in page.locator('details:not([open]) > summary').all():
                summary.click()
            for hint in page.locator('.form-hint').all():
                expect(hint).to_be_visible()
            _assert_controls(page)
        page.goto(PATH)
        expect(page.get_by_label('Abstände', exact=True)).to_have_value('compact')
        expect(page.locator('#admin-density-hint')).to_be_visible()
        expect(page.get_by_label('Inhaltsbreite', exact=True)).to_have_value('contained')
        expect(page.locator('#admin-content-width-hint')).to_contain_text('volle Breite')
        # K7-A, Entscheidungsdokument §10: compact = Master-Card-Inset (16 px mobil, 24 px ab 768 px)
        expected_compact = '16px' if width < 768 else '24px'
        assert page.locator('#display-settings-form .card-body').evaluate('el => getComputedStyle(el).paddingTop') == expected_compact
        _assert_controls(page)
        page.screenshot(path=str(tmp_path / f'display-compact-{width}-js-{javascript}.png'), full_page=True)
        if not javascript:
            page.get_by_label('Abstände', exact=True).select_option('comfortable')
            page.get_by_role('button', name='Darstellung speichern', exact=True).click()
            expect(page.locator('main')).to_have_attribute('data-density', 'comfortable')
            # K7-A, Entscheidungsdokument §10: comfortable = nächste Stufe (24 px mobil, 32 px ab 768 px)
            expected_comfortable = '24px' if width < 768 else '32px'
            assert page.locator('#display-settings-form .card-body').evaluate('el => getComputedStyle(el).paddingTop') == expected_comfortable
            _assert_controls(page)
            page.screenshot(path=str(tmp_path / f'display-comfortable-{width}-no-js.png'), full_page=True)


def test_native_save_is_global_in_second_browser_and_ignores_old_storage(
    browser, live_server, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _context(browser, live_server, client) as first, _context(browser, live_server, client) as second:
        first.add_init_script("localStorage.setItem('admin-dense', 'true')")
        second.add_init_script("localStorage.setItem('admin-dense', 'false')")
        a, b = first.new_page(), second.new_page()
        a.set_viewport_size({'width': 1440, 'height': 1100})
        b.set_viewport_size({'width': 390, 'height': 844})
        for density in ('comfortable', 'compact'):
            a.goto(PATH)
            a.get_by_label('Abstände', exact=True).select_option(density)
            with a.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith(PATH)) as saved:
                a.get_by_role('button', name='Darstellung speichern', exact=True).click()
            assert saved.value.status == 303
            a.wait_for_load_state()
            expect(a.locator('main')).to_have_attribute('data-density', density)
            expect(a.get_by_text('Darstellung für alle Benutzer und Geräte gespeichert.', exact=True)).to_be_visible()
            for family in ('cafeteria', 'patienten'):
                b.goto(f'/admin/{family}')
                expect(b.locator('main')).to_have_attribute('data-density', density)
                # K7-A, Entscheidungsdokument §10: b has mobile width 390 px (compact: 16 px, comfortable: 24 px)
                expected = '16px' if density == 'compact' else '24px'
                assert b.locator('.card-body').first.evaluate('el => getComputedStyle(el).paddingTop') == expected
                assert b.locator('main').get_attribute('data-state') is None
                _assert_controls(b)
            assert a.evaluate("localStorage.getItem('admin-dense')") == 'true'
            assert b.evaluate("localStorage.getItem('admin-dense')") == 'false'
            a.screenshot(path=str(tmp_path / f'display-global-{density}-1440.png'), full_page=True)
        b.goto(PATH)
        b.screenshot(path=str(tmp_path / 'display-global-second-browser.png'), full_page=True)


def test_csv_states_remain_independent_of_density_and_old_local_storage(page_context):  # noqa: F811
    page = page_context
    page.add_init_script("localStorage.setItem('admin-dense', 'true')")
    page.goto('/admin/import-preview')
    expect(page.locator('main')).to_have_attribute('data-state', 'empty')
    expect(page.locator('main')).to_have_attribute('data-density', 'compact')
    page.locator('input[type="file"]').set_input_files({
        'name': 'invalid.csv', 'mimeType': 'text/csv', 'buffer': b'not,a,valid,header\n',
    })
    page.get_by_role('button', name='Vorschau prüfen', exact=True).click()
    expect(page.locator('main')).to_have_attribute('data-state', 'error')
    expect(page.locator('.error-region')).to_be_visible()
    page.locator('input[type="file"]').set_input_files(
        str(Path(__file__).resolve().parents[2] / 'csv' / 'menu_patient_example.csv'),
    )
    page.get_by_role('button', name='Vorschau prüfen', exact=True).click()
    expect(page.locator('main')).to_have_attribute('data-state', 'ready')
    expect(page.locator('main')).to_have_attribute('data-density', 'compact')
    expect(page.get_by_role('button', name='Geprüfte Datei importieren')).to_be_visible()
    expect(page.get_by_label('Kompakte Ansicht', exact=True)).to_have_count(0)
