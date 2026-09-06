"""Real HTTP, production CSP and native forms across two browser sessions."""
from __future__ import annotations

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
        _targets(page)
        page.get_by_label('Vorlagenname', exact=True).fill('Herbst am Südhang')
        page.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Guten Appetit')
        page.get_by_label('Farbpalette', exact=True).select_option('brand')
        page.get_by_label('Druckschrift', exact=True).select_option('fira')
        page.get_by_role('button', name='Entwurf speichern und prüfen', exact=True).click()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Revision 2', exact=True)).to_be_visible()
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
        page.get_by_role('button', name='Revision 2 prüfen und aktivieren', exact=True).click()
        expect(page.get_by_text('Aktive Druckvorlage', exact=True)).to_be_visible()
        assert 'Guten Appetit' in pdf_text(client.get(f'/admin/{family}/preview/print?week={DAY}'))
        page.get_by_label('Name der Kopie', exact=True).fill('Herbst Kopie')
        page.get_by_role('button', name='Kopie erstellen', exact=True).click()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Herbst Kopie')
        page.get_by_label('Vorlage', exact=True).select_option('standard')
        page.get_by_role('button', name='Anzeigen', exact=True).click()
        page.get_by_role('button', name='Revision 1 wiederherstellen', exact=True).click()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Revision 3', exact=True)).to_be_visible()
        expect(page.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('')
        assert 'Guten Appetit' in pdf_text(client.get(f'/admin/{family}/preview/print?week={DAY}'))
        _targets(page)
        assert pdfs and not failures
        page.get_by_label('Vorlagenname', exact=True).focus()
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
        a.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Erste Sitzung')
        a.get_by_role('button', name='Entwurf speichern und prüfen', exact=True).click()
        expect(a.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Erste Sitzung')
        b.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Zweite Sitzung')
        with b.expect_response(lambda response: response.request.method == 'POST') as result:
            b.get_by_role('button', name='Entwurf speichern und prüfen', exact=True).click()
        assert result.value.status == 409
        expect(b.get_by_role('alert')).to_contain_text('zwischenzeitlich geändert')
        expect(b.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Zweite Sitzung')
        b.get_by_role('link', name='Aktuellen Stand neu laden', exact=True).click()
        expect(b.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Erste Sitzung')
        b.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Zweite Sitzung bestätigt')
        b.get_by_role('button', name='Entwurf speichern und prüfen', exact=True).click()
        b.get_by_role('button', name='Revision 3 prüfen und aktivieren', exact=True).click()
        expect(b.get_by_text('Aktive Druckvorlage', exact=True)).to_be_visible()
        _targets(b)
        b.screenshot(path=str(tmp_path / 'print-editor-second-session-no-js.png'), full_page=True)
