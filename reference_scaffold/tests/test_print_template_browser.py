"""Real HTTP, production CSP and native forms across two browser sessions."""
from __future__ import annotations

import json
import threading
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from test_print_template_routes import database_engine, editor_app, pdf_text  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _login
from test_admin_operations_routes import PATH as OPERATIONS_PATH, _get as _operations_form


@pytest.mark.parametrize('width', [360, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_p3_editor_pages_polish(editor_app, editor_server, database_engine, browser, width, javascript, tmp_path):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, 'staff_guest', _staff_values())
    _save(database_engine, 'patient', _patient_values())
    paths = {
        'menu': f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1',
        'print': f'/admin/vorlagen/cafeteria?week={DAY}',
        'vorlagen': f'/admin/vorlagen?week={DAY}',
        'assignment': '/admin/screens/cafeteria/wochenvorlage',
        'cafeteria': f'/admin/cafeteria?week={DAY}',
    }
    with _context(browser, editor_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        for name, path in paths.items():
            assert page.goto(path).status == 200
            page.evaluate('document.fonts.ready')
            metrics = page.evaluate('''() => ({
                height: document.documentElement.scrollHeight,
                width: document.documentElement.scrollWidth,
                primary: [...document.querySelectorAll('main .btn-primary')].filter(e => e.checkVisibility()).length,
                hints: [...document.querySelectorAll('main .form-hint')].filter(e => e.checkVisibility()).length,
                tables: document.querySelectorAll('main table').length
            })''')
            print('P3_METRICS', name, width, javascript, json.dumps(metrics))
            assert metrics['width'] <= width + 1
            expect(page.locator('main .btn-primary:visible')).to_have_count(1)
            # These editors use native lists/grids, not desktop tables or duplicate mobile DOM.
            expect(page.locator('main table')).to_have_count(0)
            if name == 'menu' and not javascript:
                for row in page.locator('.menu-editor-component-row').all():
                    legend = row.locator(':scope > legend').bounding_box()
                    label = row.locator('[data-component-edit-view] label:visible').first.bounding_box()
                    assert label['y'] >= legend['y'] + legend['height']
            page.screenshot(path=str(tmp_path / f'p3-{name}-{width}-{javascript}.png'), full_page=True)
            page.screenshot(path=str(tmp_path / f'p3-{name}-{width}-{javascript}-viewport.png'))
            print('P3_SCREENSHOT', tmp_path / f'p3-{name}-{width}-{javascript}.png')
            if name != 'cafeteria':
                forms_before = page.locator('main form').evaluate_all(
                    'forms => forms.map(form => Array.from(new FormData(form)))'
                )
                help_details = page.locator('main .admin-hint:visible').first
                trigger = help_details.locator(':scope > summary')
                expect(help_details).not_to_have_attribute('open', '')
                trigger.focus()
                expect(trigger).to_be_focused()
                page.keyboard.press('Enter')
                expect(help_details).to_have_attribute('open', '')
                expect(help_details.locator('.form-hint')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                assert trigger.evaluate('e => parseFloat(getComputedStyle(e).outlineWidth)') >= 2
                page.keyboard.press('Enter')
                expect(help_details).not_to_have_attribute('open', '')
                assert page.locator('main form').evaluate_all(
                    'forms => forms.map(form => Array.from(new FormData(form)))'
                ) == forms_before
            else:
                # Planning remains one chronological day structure at mobile width.
                expect(page.locator('.admin-week-days')).to_have_count(1)
                if width < 768:
                    days = page.locator('.admin-day-card').evaluate_all(
                        'els => els.map(e => e.getBoundingClientRect().toJSON())'
                    )
                    assert all(b['top'] >= a['bottom'] for a, b in zip(days, days[1:]))
                weekend_form = _operations_form(client, 'weekend-form')
                assert client.post(OPERATIONS_PATH, data={**weekend_form, 'allows_weekend': 'on'}).status_code == 303
                # The seeded five-day draft retains its original scope; the setting
                # applies to a new week, not retroactively to existing menu data.
                assert page.goto('/admin/cafeteria?week=2026-09-07').status == 200
                expect(page.locator('.admin-day-card')).to_have_count(7)
                expect(page.locator('main .btn-primary:visible')).to_have_count(1)
                weekend_help = page.locator('#weekend-hint')
                expect(weekend_help).not_to_have_attribute('open', '')
                weekend_help.locator('summary').focus()
                page.keyboard.press('Enter')
                expect(weekend_help.locator('.form-hint')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                page.keyboard.press('Enter')
                expect(weekend_help).not_to_have_attribute('open', '')


@pytest.fixture(scope='module')
def browser():
    # Full Chromium's new headless mode includes the native PDF viewer. The
    # separate Playwright headless shell intentionally does not render PDFs.
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(executable_path='/opt/google/chrome/chrome', headless=True,
                                               ignore_default_args=['--disable-extensions'],
                                               args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            yield instance
        finally:
            instance.close()


@pytest.fixture
def editor_server(editor_app):  # noqa: F811
    server = make_server('127.0.0.1', 0, editor_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _context(playwright_browser, server, client, width, javascript=True):
    cookie = client.get_cookie(client.application.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    context = playwright_browser.new_context(base_url=server, viewport={'width': width, 'height': 1100},
                                  java_script_enabled=javascript, reduced_motion='reduce')
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server}])
    return context


def _targets(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('main style, main [style]').count() == 0
    for control in page.locator('main :is(.btn, .form-control, .form-select)').all():
        if control.is_visible():
            box = control.bounding_box()
            assert box is not None and box['height'] >= 48
            assert control.evaluate('el => parseFloat(getComputedStyle(el).fontSize)') >= 16


def _wait_for_pdf_paint(page, frame, path: Path) -> None:
    # Native viewer internals are not a web API. Wait for paper plus rendered
    # content instead of accepting a uniform blank frame or an HTTP receipt.
    for _ in range(40):
        pixels = Image.open(BytesIO(frame.screenshot(path=str(path)))).convert('RGB')
        colors = pixels.getcolors(pixels.width * pixels.height) or []
        total = pixels.width * pixels.height
        paper = sum(count for count, color in colors if min(color) >= 245)
        ink = sum(count for count, color in colors if max(color) < 140)
        if len(colors) > 32 and paper > total * 0.15 and ink > total * 0.02:
            return
        page.wait_for_timeout(100)
    raise AssertionError(f'PDF viewer did not paint document content: {path}')


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_real_editor_save_preview_activate_copy_restore(editor_app, editor_server, database_engine, browser, width, family, profile, tmp_path: Path):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    path = f'/admin/vorlagen/{family}?week={DAY}'
    with _context(browser, editor_server, client, width) as context:
        page = context.new_page()
        failures: list[str] = []
        pdfs: list[str] = []
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
        page.on('response', lambda response: pdfs.append(response.url) if 'vorschau.pdf' in response.url and response.status == 200 else None)
        response = page.goto(path)
        assert response is not None and response.status == 200
        assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Standard')
        expect(page.locator('.admin-statusbar')).to_be_visible()
        expect(page.locator('.admin-statusbar-item')).to_have_count(3)
        expect(page.locator('main .btn-primary')).to_have_count(1)
        _targets(page)
        page.locator('details[data-template-appearance] summary').click()
        page.locator('details[data-template-texts] > summary').click()
        page.get_by_label('Vorlagenname', exact=True).fill('Herbst am Südhang')
        page.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Guten Appetit')
        page.get_by_label('Farbpalette', exact=True).select_option('brand')
        page.get_by_label('Druckschrift', exact=True).select_option('fira')
        page.get_by_role('button', name='Vorlage speichern', exact=True).click()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Version 2', exact=True)).to_be_visible()
        frame = page.locator('iframe')
        expect(frame).to_be_visible()
        preview = frame.get_attribute('src')
        assert preview is not None
        assert 'Guten Appetit' in pdf_text(client.get(preview))
        frame.scroll_into_view_if_needed()
        _wait_for_pdf_paint(page, frame, tmp_path / f'print-editor-pdf-{family}-{width}.png')
        page.screenshot(path=str(tmp_path / f'print-editor-preview-{family}-{width}.png'), full_page=True)
        # Chrome's native PDF viewer has private DOM. Inspect its real pixels;
        # the PDF response/text contract is independently asserted above.
        assert page.evaluate('navigator.pdfViewerEnabled')
        page.locator('details[data-template-activation] summary').click()
        page.get_by_role('button', name='Diese Version aktivieren', exact=True).click()
        expect(page.locator('[data-template-status-scope]')).to_contain_text('Version 2')
        assert 'Guten Appetit' in pdf_text(client.get(f'/admin/{family}/preview/print?week={DAY}'))
        page.locator('details[data-template-more-actions] summary').click()
        page.get_by_label('Name der Kopie', exact=True).fill('Herbst Kopie')
        page.get_by_role('button', name='Kopie erstellen', exact=True).click()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Herbst Kopie')
        page.locator('details[data-template-more-actions] > summary').click()
        confirmation = page.get_by_role('checkbox', name='Ich möchte diese Vorlage archivieren.', exact=True)
        page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
        expect(confirmation).to_be_focused()
        assert confirmation.evaluate('e => e.validity.valueMissing')
        confirmation.check()
        page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_be_disabled()
        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
        expect(page.locator('main .btn-primary')).to_have_text('Archivierte Vorlage prüfen')
        page.get_by_label('Vorlage', exact=True).select_option('standard')
        page.get_by_role('button', name='Woche öffnen', exact=True).click()
        page.locator('details[data-template-versions] summary').click()
        page.get_by_role('button', name='Version 1 wiederherstellen: als neuen Entwurf laden', exact=True).click()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Version 3', exact=True)).to_be_visible()
        expect(page.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('')
        assert 'Guten Appetit' in pdf_text(client.get(f'/admin/{family}/preview/print?week={DAY}'))
        _targets(page)
        assert pdfs and not failures
        page.get_by_label('Vorlagenname', exact=True).focus()
        page.keyboard.press('Tab')
        expect(page.locator('details[data-template-appearance] summary')).to_be_focused()
        page.keyboard.press('Enter')
        page.keyboard.press('Tab')
        expect(page.get_by_label('Druckschrift', exact=True)).to_be_focused()
        page.screenshot(path=str(tmp_path / f'print-editor-{family}-{width}.png'), full_page=True)


def test_two_sessions_get_conflict_and_native_no_js_flow(editor_app, editor_server, database_engine, browser, tmp_path: Path):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, 'patient', _patient_values())
    with _context(browser, editor_server, client, 1440) as first, _context(browser, editor_server, client, 390, javascript=False) as second:
        a, b = first.new_page(), second.new_page()
        for page in (a, b):
            page.goto(f'/admin/vorlagen/patienten?week={DAY}')
            page.locator('details[data-template-texts] > summary').click()
        a.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Erste Sitzung')
        a.get_by_role('button', name='Vorlage speichern', exact=True).click()
        expect(a.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Erste Sitzung')
        b.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Zweite Sitzung')
        with b.expect_response(lambda response: response.request.method == 'POST') as result:
            b.get_by_role('button', name='Vorlage speichern', exact=True).click()
        assert result.value.status == 409
        expect(b.get_by_role('alert')).to_contain_text('zwischenzeitlich geändert')
        expect(b.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Zweite Sitzung')
        b.get_by_role('link', name='Aktuellen Stand neu laden', exact=True).click()
        expect(b.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Erste Sitzung')
        b.locator('details[data-template-texts] > summary').click()
        b.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Zweite Sitzung bestätigt')
        b.get_by_role('button', name='Vorlage speichern', exact=True).click()
        b.locator('details[data-template-activation] summary').click()
        b.get_by_role('button', name='Diese Version aktivieren', exact=True).click()
        expect(b.locator('[data-template-status-scope]')).to_contain_text('Version 3')
        _targets(b)
        b.screenshot(path=str(tmp_path / 'print-editor-second-session-no-js.png'), full_page=True)


@pytest.mark.parametrize('width,javascript', [(360, False), (360, True), (768, True), (1024, True), (1440, True)])
def test_hub_and_editor_statusbar_viewports_keyboard_and_no_js(
    editor_app, editor_server, database_engine, browser, width, javascript, tmp_path: Path,  # noqa: F811
) -> None:
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, 'staff_guest', _staff_values())
    _save(database_engine, 'patient', _patient_values())
    with _context(browser, editor_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        response = page.goto(f'/admin/vorlagen?week={DAY}')
        assert response is not None and response.status == 200
        expect(page.get_by_role('heading', level=1)).to_have_text('Vorlagen')
        expect(page.locator('.admin-statusbar')).to_be_visible()
        expect(page.locator('.admin-statusbar-item')).to_have_count(4)
        expect(page.locator('main .btn-primary')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        _targets(page)
        if width == 1440:
            row_height = page.locator('#output-cafeteria [data-current-template]').evaluate(
                'el => el.getBoundingClientRect().height'
            )
            assert row_height <= 96
        week_submit = page.get_by_role('button', name='Woche öffnen', exact=True)
        week_submit.focus()
        expect(week_submit).to_be_focused()
        page.screenshot(path=str(tmp_path / f'vorlagen-hub-{width}-js{javascript}.png'), full_page=True)
        editor = page.goto(f'/admin/vorlagen/cafeteria?week={DAY}')
        assert editor is not None and editor.status == 200
        expect(page.locator('.admin-statusbar')).to_be_visible()
        expect(page.locator('.admin-statusbar-item')).to_have_count(3)
        expect(page.locator('main .btn-primary')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        _targets(page)
        page.get_by_label('Vorlagenname', exact=True).focus()
        page.keyboard.press('Tab')
        expect(page.locator('details[data-template-appearance] summary')).to_be_focused()
        page.screenshot(path=str(tmp_path / f'vorlagen-editor-{width}-js{javascript}.png'), full_page=True)
