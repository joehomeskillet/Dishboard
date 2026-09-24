"""Global density stays server-owned across devices, JS modes, CSV states and old storage."""
from __future__ import annotations

from pathlib import Path
import json
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect, sync_playwright

from cafeteria.admin import display_routes  # noqa: F401 - complete shared blueprint
from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import DAY, _login

PATH = '/admin/design/darstellung'


def _display_metrics(page):
    return page.evaluate('''() => {
        const form = document.querySelector('#display-settings-form');
        const row = form.querySelector('.row > div');
        const image = document.querySelector('.display-preview img');
        return {
            width: innerWidth, height: document.documentElement.scrollHeight,
            row_height: row.getBoundingClientRect().height,
            form_height: form.getBoundingClientRect().height,
            image_height: image ? image.getBoundingClientRect().height : 0,
            primary: document.querySelectorAll('main .btn-primary').length,
            open_details: document.querySelectorAll('main details[open]').length,
            overflow: document.documentElement.scrollWidth > innerWidth + 1,
            fields: [...new FormData(form)].filter(([key]) => key !== '_csrf'),
        };
    }''')


def test_display_frame_viewports_nojs_and_keyboard(
    live_server, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    measurements = []
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        try:
            for javascript in (True, False):
                with _context(instance, live_server, client, javascript=javascript) as context:
                    page = context.new_page()
                    for width in (360, 768, 1024, 1440):
                        page.set_viewport_size({'width': width, 'height': 900})
                        page.goto(PATH)
                        page.evaluate('document.fonts.ready')
                        metrics = _display_metrics(page)
                        measurements.append({**metrics, 'javascript': javascript})
                        assert not metrics['overflow'], metrics
                        assert metrics['primary'] == 1
                        assert metrics['open_details'] == 0
                        assert metrics['image_height'] <= 120
                        assert metrics['fields'] == [
                            ['admin_density', 'compact'], ['admin_font_size', 'normal'],
                            ['admin_content_width', 'contained'], ['admin_menu_images', 'show'],
                        ]
                        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
                        help_trigger = page.locator('.admin-hint > summary').first
                        help_trigger.focus()
                        expect(help_trigger).to_be_focused()
                        help_trigger.press('Enter')
                        expect(page.locator('#admin-density-hint')).to_be_visible()
                        help_trigger.press('Enter')
                        expect(page.locator('#admin-density-hint')).to_be_hidden()
                        assert _display_metrics(page)['fields'] == metrics['fields']
                        expect(page.get_by_role('heading', level=1)).to_have_text('Darstellung')
                        status = page.locator('.admin-statusbar')
                        expect(status).to_contain_text('Aktiv')
                        expect(status).to_contain_text('Kompakt')
                        expect(status).to_contain_text('Anzeigen')
                        expect(page.locator('main .btn-primary')).to_have_text('Speichern')
                        _assert_controls(page)
                        page.screenshot(path=str(tmp_path / f'display-frame-{width}-{javascript}.png'), full_page=True)
                        summary = page.locator('#display-more > summary')
                        summary.focus()
                        page.keyboard.press('Enter')
                        expect(page.locator('#display-reset-btn')).to_be_visible()
                        assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
                        assert summary.bounding_box()['height'] >= 48
                        page.keyboard.press('Enter')
                        expect(page.locator('#display-reset-btn')).to_be_hidden()
                        page.get_by_label('Abstände', exact=True).select_option('comfortable')
                        page.get_by_label('Schriftgrösse', exact=True).select_option('large')
                        page.get_by_label('Inhaltsbreite', exact=True).select_option('full')
                        page.get_by_label('Menübilder', exact=True).select_option('hide')
                        preview = page.get_by_role('button', name='Vorschau', exact=True)
                        preview.focus()
                        with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith(PATH)) as posted:
                            page.keyboard.press('Enter')
                        assert posted.value.status == 200
                        payload = parse_qs(posted.value.request.post_data)
                        assert set(payload) == {'_csrf', 'action', 'admin_density', 'admin_font_size', 'admin_content_width', 'admin_menu_images'}
                        assert payload.pop('_csrf')
                        assert payload == {
                            'action': ['preview'], 'admin_density': ['comfortable'],
                            'admin_font_size': ['large'], 'admin_content_width': ['full'],
                            'admin_menu_images': ['hide'],
                        }
                        expect(status).to_contain_text('Vorschau der Auswahl – noch nicht gespeichert.')
                        expect(status.locator('.admin-statusbar-item--warning')).to_have_count(1)
                        expect(status).to_contain_text('Komfortabel')
                        expect(status).to_contain_text('Ausblenden')
                        expect(page.locator('.display-preview img')).to_have_count(0)
                        expect(page.get_by_text('Enthält: Milch · Allergene noch prüfen.', exact=True)).to_be_visible()
                        expect(page.locator('main')).to_have_attribute('data-density', 'compact')
                        _assert_controls(page)
                        page.screenshot(path=str(tmp_path / f'display-preview-{width}-{javascript}.png'), full_page=True)
                        page.goto(PATH)
                        expect(page.get_by_label('Abstände', exact=True)).to_have_value('compact')
                    page.evaluate("document.documentElement.style.zoom = '2'")
                    _assert_controls(page)
                    page.screenshot(path=str(tmp_path / f'display-zoom-200-{javascript}.png'), full_page=True)
        finally:
            instance.close()
    (tmp_path / 'display-metrics.json').write_text(json.dumps(measurements, indent=2))
    print('DISPLAY_METRICS=' + json.dumps(measurements))
    print('DISPLAY_EVIDENCE=' + str(tmp_path))


@pytest.mark.parametrize('javascript', [False, True])
def test_display_reset_and_error_keep_native_form_contract(
    browser, live_server, admin_app, admin_engine, javascript, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _context(browser, live_server, client, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 360, 'height': 900})
        page.goto(PATH)
        page.get_by_label('Abstände', exact=True).select_option('comfortable')
        page.get_by_label('Schriftgrösse', exact=True).select_option('large')
        page.get_by_label('Inhaltsbreite', exact=True).select_option('full')
        page.get_by_label('Menübilder', exact=True).select_option('hide')
        expected = {
            'admin_density': ['comfortable'], 'admin_font_size': ['large'],
            'admin_content_width': ['full'], 'admin_menu_images': ['hide'],
        }
        for action in ('save', 'reset'):
            csrf = page.locator('#display-settings-form > input[name="_csrf"]').input_value()
            if action == 'reset':
                summary = page.locator('#display-more > summary')
                summary.focus()
                page.keyboard.press('Enter')
                expect(page.locator('#display-reset-hint')).to_contain_text('für alle Benutzer')
                expect(page.locator('main')).to_have_attribute('data-density', 'comfortable')
            with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith(PATH)) as posted:
                page.locator(f'#display-settings-form button[value="{action}"]').click()
            assert posted.value.status == 303
            assert parse_qs(posted.value.request.post_data) == {
                '_csrf': [csrf], 'action': [action], **expected,
            }
            expect(page.locator('.admin-statusbar')).to_contain_text('Aktiv')
            expect(page.locator('main')).to_have_attribute('data-density', 'comfortable' if action == 'save' else 'compact')
        expect(page.get_by_label('Schriftgrösse', exact=True)).to_have_value('normal')
        expect(page.get_by_label('Inhaltsbreite', exact=True)).to_have_value('contained')
        expect(page.get_by_label('Menübilder', exact=True)).to_have_value('show')
        # Exercise server validation through a real POST, without replacing handlers.
        page.locator('#admin-density').evaluate("el => el.add(new Option('invalid', 'invalid'))")
        page.locator('#admin-density').select_option('invalid')
        page.get_by_label('Schriftgrösse', exact=True).select_option('large')
        with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith(PATH)) as invalid:
            page.get_by_role('button', name='Speichern', exact=True).click()
        assert invalid.value.status == 400
        expect(page.locator('.admin-statusbar-item--danger')).to_contain_text('Fehler')
        expect(page.locator('.admin-statusbar')).to_contain_text('Eingaben wurden nicht gespeichert.')
        expect(page.locator('#admin-density')).to_have_attribute('aria-invalid', 'true')
        expect(page.locator('#admin-density-error')).to_have_text('Bitte eine der angebotenen Optionen auswählen.')
        expect(page.get_by_label('Schriftgrösse', exact=True)).to_have_value('large')
        expect(page.locator('#display-more')).to_have_attribute('open', '')
        expect(page.locator('main')).to_have_attribute('data-density', 'compact')
        page.locator('.error-region a').first.click()
        if javascript:
            expect(page.locator('#admin-density')).to_be_focused()
        _assert_controls(page)
        page.screenshot(path=str(tmp_path / f'display-error-360-{javascript}.png'), full_page=True)
        page.goto(PATH)
        expect(page.get_by_label('Schriftgrösse', exact=True)).to_have_value('normal')


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
            while page.locator('details:not([open]) > summary:visible').count():
                page.locator('details:not([open]) > summary:visible').first.click()
            visible_hints = page.locator('.form-hint:visible')
            assert visible_hints.count() > 0
            for hint in visible_hints.all():
                expect(hint).to_be_visible()
            for row in page.locator('.menu-editor-component-row').all():
                hint = row.locator('.menu-editor-row-hint')
                if javascript:
                    expect(hint).to_be_hidden()
                    row.get_by_role('button', name='Bearbeiten', exact=True).click()
                    expect(hint).to_be_visible()
                    row.get_by_role('button', name='Fertig', exact=True).click()
                    expect(hint).to_be_hidden()
                else:
                    expect(hint).to_be_visible()
            _assert_controls(page)
        page.goto(PATH)
        expect(page.get_by_label('Abstände', exact=True)).to_have_value('compact')
        density_help = page.locator('.admin-hint > summary[aria-describedby="admin-density-hint"]')
        density_help.focus()
        density_help.press('Enter')
        expect(page.locator('#admin-density-hint')).to_be_visible()
        density_help.press('Enter')
        expect(page.get_by_label('Inhaltsbreite', exact=True)).to_have_value('contained')
        expect(page.locator('#admin-content-width-hint')).to_contain_text('volle Breite')
        # K7-A, Entscheidungsdokument §10: compact = Master-Card-Inset (16 px mobil, 24 px ab 768 px)
        expected_compact = '16px' if width < 768 else '24px'
        assert page.locator('#display-settings-form .card-body').evaluate('el => getComputedStyle(el).paddingTop') == expected_compact
        _assert_controls(page)
        page.screenshot(path=str(tmp_path / f'display-compact-{width}-js-{javascript}.png'), full_page=True)
        if not javascript:
            page.get_by_label('Abstände', exact=True).select_option('comfortable')
            page.get_by_role('button', name='Speichern', exact=True).click()
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
                a.get_by_role('button', name='Speichern', exact=True).click()
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
