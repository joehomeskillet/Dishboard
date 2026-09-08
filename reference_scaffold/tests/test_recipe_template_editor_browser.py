"""Native Tabler recipe choice/forms and real Chrome PDF paint."""
from io import BytesIO
from pathlib import Path
import threading

import pytest
from playwright.sync_api import expect
from pypdf import PdfReader
from werkzeug.serving import make_server

from cafeteria import recipe_store as recipes
from test_master_data_db import signed_in
from test_recipe_store_db import payload
from test_print_template_browser import browser, _context, _targets, _wait_for_pdf_paint  # noqa: F401
from test_recipe_template_editor_routes import (  # noqa: F401
    BASE, recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine, example, path,
)


@pytest.fixture
def recipe_server(recipe_editor):  # noqa: F811
    app, _, _, _ = recipe_editor
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('width,javascript', [(390, False), (1440, True)])
def test_recipe_choice_saved_pdf_activation_restore_archive_native_forms(recipe_editor, recipe_server, browser, width, javascript, tmp_path: Path):  # noqa: F811
    app, _, client, actor = recipe_editor
    _, revision, _ = example(recipe_editor)
    if width == 1440:
        engine = app.extensions['cafeteria_db']
        with signed_in(engine, actor):
            location = recipes.get_location(engine)
            for number in range(50):
                recipes.create_recipe(engine, actor, payload(title=f'Beispiel {number:02}'), expected_location_id=location)
    with _context(browser, recipe_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        failures, pdf_responses = [], []
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
        page.on('response', lambda response: pdf_responses.append(response)
                if '/vorlagen/rezepte/vorschau.pdf?' in response.url else None)
        response = page.goto(BASE)
        assert response.status == 200 and "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
        expect(page.get_by_role('heading', name='Rezepte · Vorlageneditor')).to_be_visible()
        assert page.locator('[name^="layout_"], [name="week"]').count() == 0
        if width == 1440:
            assert page.get_by_role('link', name='Revisionen für Suppe auswählen', exact=True).count() == 0
            page.get_by_role('navigation', name='Rezeptseiten', exact=True).get_by_role('link', name='Weiter', exact=True).click()
        page.get_by_role('link', name='Revisionen für Suppe auswählen', exact=True).click()
        expect(page.get_by_label('Festgeschriebene Rezeptrevision')).to_have_value('')
        assert page.locator('iframe').count() == 0
        page.get_by_label('Festgeschriebene Rezeptrevision').select_option(revision.public_id)
        page.get_by_role('button', name='Rezeptrevision verwenden', exact=True).click()
        page.get_by_label('Gewünschte Ausbeute', exact=True).fill('8')
        page.get_by_role('button', name='Ausbeute anwenden', exact=True).click()
        page.get_by_label('Vorlagenname', exact=True).fill('Unsere Rezeptvorlage')
        page.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Aus unserer Küche')
        page.get_by_role('button', name='Entwurf speichern', exact=True).click()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Revision 2', exact=True)).to_be_visible()
        expect(page.get_by_label('Gewünschte Ausbeute')).to_have_value('8')
        frame = page.locator('iframe')
        source = frame.get_attribute('src')
        # Match the existing browser gate: native iframe request/paint plus
        # authenticated factory-client byte inspection. Secure cookies on this
        # HTTP loopback fixture are not sent by Playwright's APIRequestContext.
        pdf = client.get(source.split('#')[0])
        assert pdf.status_code == 200 and pdf.headers['Cache-Control'] == 'no-store'
        assert pdf.headers['X-Recipe-Revision'] == revision.public_id
        document = PdfReader(BytesIO(pdf.data))
        assert any(list(sheet.images) for sheet in document.pages)
        assert all(value in '\n'.join(sheet.extract_text() for sheet in document.pages)
                   for value in ('Aus unserer Küche', 'Gewünscht: 8', 'Karotte'))
        expect(page.get_by_role('link', name='Vorschau als PDF öffnen', exact=True)).to_be_visible()
        _targets(page)
        if javascript:
            frame.scroll_into_view_if_needed()
            _wait_for_pdf_paint(page, frame, tmp_path / 'recipe-editor-native-pdf-1440.png')
        assert any(response.status == 200 and response.headers.get('x-print-template-revision') == 'standard:2'
                   for response in pdf_responses)
        page.get_by_role('heading', name='Rezepte · Vorlageneditor').scroll_into_view_if_needed()
        page.screenshot(path=str(tmp_path / f'recipe-editor-viewport-{width}.png'))
        page.screenshot(path=str(tmp_path / f'recipe-editor-selected-{width}.png'), full_page=True)
        # Screenshot caret hiding restores properties but leaves empty style
        # attributes. The unchanged page is checked above before that tool step.
        leftovers = page.locator('main [style]').evaluate_all('nodes => nodes.map(node => node.getAttribute("style"))')
        assert all(value == '' for value in leftovers), leftovers
        page.get_by_label('Vorlagenname', exact=True).focus()
        page.keyboard.press('Tab')
        expect(page.get_by_label('Druckschrift', exact=True)).to_be_focused()
        page.get_by_role('button', name='Revision 2 prüfen und aktivieren', exact=True).click()
        expect(page.get_by_text('Aktive Druckvorlage', exact=True)).to_be_visible()
        page.get_by_role('button', name='Revision 1 wiederherstellen', exact=True).click()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Revision 3', exact=True)).to_be_visible()
        page.get_by_label('Name der Kopie', exact=True).fill('Archivprobe')
        page.get_by_role('button', name='Kopie erstellen', exact=True).click()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Archivprobe')
        page.get_by_label('Ich möchte diese Vorlage archivieren.', exact=True).check()
        page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
        expect(page.get_by_text('Diese Vorlage ist archiviert.', exact=False)).to_be_visible()
        page.get_by_role('button', name='Vorlage reaktivieren', exact=True).click()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_be_enabled()
        _targets(page)
        page.screenshot(path=str(tmp_path / f'recipe-editor-final-{width}.png'), full_page=True)
        assert not failures


def test_nojs_conflict_retains_recipe_yield_original_version_and_focus(recipe_editor, recipe_server, browser, tmp_path: Path):  # noqa: F811
    _, _, client, _ = recipe_editor
    recipe, revision, _ = example(recipe_editor)
    with _context(browser, recipe_server, client, 1440) as first, _context(browser, recipe_server, client, 390, javascript=False) as second:
        a, b = first.new_page(), second.new_page()
        for page in (a, b):
            page.goto(path(recipe, revision.public_id, **{'yield': '8'}))
        a.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Gespeicherter Stand')
        a.get_by_role('button', name='Entwurf speichern', exact=True).click()
        b.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Mein Text bleibt erhalten')
        with b.expect_response(lambda response: response.request.method == 'POST') as result:
            b.get_by_role('button', name='Entwurf speichern', exact=True).click()
        assert result.value.status == 409 and result.value.headers['cache-control'] == 'no-store'
        expect(b.locator('#template-error')).to_be_focused()
        expect(b.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Mein Text bleibt erhalten')
        expect(b.get_by_label('Gewünschte Ausbeute', exact=True)).to_have_value('8')
        assert b.locator('input[name="version"]').first.input_value() == '0'
        assert recipe in b.url and revision.public_id in b.url
        _targets(b)
        b.screenshot(path=str(tmp_path / 'recipe-editor-conflict-nojs-390.png'), full_page=True)
        b.get_by_role('link', name='Aktuellen Stand neu laden', exact=True).click()
        expect(b.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Gespeicherter Stand')
        assert b.locator('input[name="version"]').first.input_value() == '1'
