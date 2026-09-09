"""Actual factory pages, native forms, conflicts and local Tabler assets."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from werkzeug.serving import make_server

from test_master_data_routes import (  # noqa: F401
    app_engine, b3, create, installed_pg16, pg16, save, seeded_pg16, snapshot,
)
from test_rendered_ui import browser  # noqa: F401


@pytest.fixture
def master_server(b3):  # noqa: F811
    app, _, client, _ = b3
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    try:
        yield f'http://127.0.0.1:{server.server_port}', cookie
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def targets(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('main style, main [style]').count() == 0
    for control in page.locator('main :is(.btn, .form-control, .form-select)').all():
        if control.is_visible():
            box = control.bounding_box()
            assert box is not None and box['height'] >= 48
            control.focus()
            expect(control).to_be_focused()


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_native_food_save_conflict_archive_and_framework(b3, master_server, browser, width, javascript, tmp_path):  # noqa: F811
    _, _, client, _ = b3
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        errors = []
        responses = {}
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('response', lambda response: responses.setdefault(urlsplit(response.url).path, []).append(response.status))
        page.goto(base + '/admin/grundlagen')
        expect(page.get_by_role('heading', level=1)).to_have_text('Grundlagen')
        expect(page.get_by_text('Keine passenden Stammdaten')).to_be_visible()
        page.get_by_role('link', name='Neu anlegen', exact=True).click()
        page.get_by_label('Name', exact=True).fill('Karotte Browser')
        page.get_by_label('Testlager', exact=True).check()
        page.get_by_role('button', name='Zutat anlegen', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Zutat bearbeiten')
        path = urlsplit(page.url).path
        core = page.locator('form[action$="/stammdaten"]')
        token = core.locator('input[name="_form_context"]').input_value()
        assert save(client, path, 'stammdaten', name='Andere Sitzung').status_code == 303
        page.get_by_label('Name', exact=True).fill('Mein ursprünglicher Entwurf')
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Stammdaten speichern', exact=True).click()
        assert outcome.value.status == 409
        expect(page.locator('.error-region')).to_be_visible()
        expect(page.get_by_label('Name', exact=True)).to_have_value('Mein ursprünglicher Entwurf')
        assert core.locator('input[name="_form_context"]').input_value() == token
        page.get_by_role('link', name='Aktuellen Stand neu laden').click()
        expect(page.get_by_label('Name', exact=True)).to_have_value('Andere Sitzung')
        page.get_by_role('button', name='Allergenangaben als geprüft bestätigen').click()
        expect(page.get_by_role('button', name='Prüfung zurücknehmen')).to_be_visible()
        page.get_by_role('button', name='Archivieren', exact=True).click()
        expect(page.get_by_role('button', name='Reaktivieren', exact=True)).to_be_visible()
        page.get_by_role('button', name='Reaktivieren', exact=True).click()
        targets(page)
        assets = page.locator('link[rel="stylesheet"], script[src]').evaluate_all(
            'els => els.map(el => new URL(el.href || el.src).pathname)')
        assert any('tabler' in asset and asset.endswith('.css') for asset in assets)
        # With JS disabled scripts are not requested; styles still must be real responses.
        assert all(200 in responses.get(asset, []) and set(responses[asset]) <= {200, 304}
                   for asset in assets if javascript or asset.endswith('.css'))
        assert not any(asset.endswith('/app.css') for asset in assets)
        assert page.locator('.card').first.evaluate('el => getComputedStyle(el).display') == 'flex'
        expected_conflict = 'Failed to load resource: the server responded with a status of 409 (CONFLICT)'
        assert all(error == expected_conflict for error in errors) and len(errors) <= 1
        evidence = Path(os.environ.get('MASTER_DATA_EVIDENCE_DIR', str(tmp_path)))
        evidence.mkdir(parents=True, exist_ok=True)
        evidence.chmod(0o700)
        page.get_by_role('heading', level=1).click()
        screenshot = evidence / f'food-{width}-js-{javascript}.png'
        page.screenshot(path=str(screenshot), full_page=True)
        screenshot.chmod(0o600)
        page.get_by_role('link', name='Zur Zutatenliste', exact=True).click()
        expect(page.get_by_role('link', name='Andere Sitzung bearbeiten')).to_be_visible()
        targets(page)


def test_browser_vocabulary_unit_forms_and_error_focus(b3, master_server, browser):  # noqa: F811
    base, cookie = master_server
    with browser.new_context(viewport={'width': 390, 'height': 1000}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        for kind in ('kategorien', 'tags', 'einheiten', 'lagerorte'):
            page.goto(f'{base}/admin/grundlagen/{kind}/neu')
            page.get_by_label('Anzeigename' if kind == 'einheiten' else 'Name', exact=True).fill('Browser ' + kind)
            page.get_by_label('Code (Grossbuchstaben, Ziffern, Unterstrich)', exact=True).fill('BROWSER')
            if kind in {'kategorien', 'lagerorte'}:
                page.get_by_label('Reihenfolge (1 bis 9999)', exact=True).fill('2')
            if kind == 'einheiten':
                page.get_by_label('Dimension', exact=True).select_option('count')
                page.get_by_label('Basisfaktor (bei kontextabhängiger Einheit leer lassen)', exact=True).fill('2')
            page.locator('main button[type="submit"]').click()
            expect(page.get_by_role('button', name='Archivieren', exact=True)).to_be_visible()
            targets(page)
        page.goto(base + '/admin/grundlagen/zutaten/neu')
        page.get_by_label('Name', exact=True).fill('<unzulässig>')
        page.get_by_label('Testlager', exact=True).check()
        page.get_by_role('button', name='Zutat anlegen', exact=True).click()
        expect(page.locator('.error-region')).to_be_visible()
        expect(page.get_by_label('Name', exact=True)).to_have_attribute('aria-invalid', 'true')
        expect(page.get_by_label('Name', exact=True)).to_be_focused()


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('existing', [False, True])
def test_location_conflict_native_recovery(b3, master_server, browser, width, javascript, existing, tmp_path):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, name='Original') if existing else '/admin/grundlagen/zutaten/neu'
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path)
        page.get_by_label('Name', exact=True).fill('Mein erhaltener Entwurf')
        page.get_by_label('Testlager', exact=True).check()
        note = page.get_by_label('Notiz', exact=True)
        # A person scrolls to the field before typing, then back to the header action.
        # Do not race offscreen fill's native smooth focus-scroll with click's auto-scroll.
        note_box = note.bounding_box()
        assert note_box is not None
        page.mouse.move(width - 24, 550)
        page.mouse.wheel(0, note_box['y'] - 550)
        expect(note).to_be_in_viewport(ratio=1)
        note.fill('\nNotiz mit führendem Zeilenumbruch\nZweite Zeile')
        action = path + '/stammdaten' if existing else path
        form = page.locator(f'form[method="post"][action="{action}"]')
        original = form.evaluate('el => Array.from(new FormData(el).entries())')
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('NEW','Neuer Standort',true)"))
        before = snapshot(owner)
        submit = page.get_by_role('button', name='Stammdaten speichern' if existing else 'Zutat anlegen', exact=True)
        page.mouse.wheel(0, -page.evaluate('window.scrollY'))
        expect(submit).to_be_in_viewport(ratio=1)
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            submit.click()
        assert outcome.value.status == 409
        expect(page.get_by_role('heading', level=1)).to_have_text('Ursprüngliche Eingaben')
        expect(page.locator('#master-error')).to_be_focused()
        expect(page.get_by_label('Name', exact=True)).to_have_value('Mein erhaltener Entwurf')
        expect(page.get_by_label('Name', exact=True)).to_have_attribute('readonly', '')
        expect(page.get_by_label('Notiz', exact=True)).to_have_value('\nNotiz mit führendem Zeilenumbruch\nZweite Zeile')
        assert form.evaluate('el => Array.from(new FormData(el).entries())') == original
        assert page.locator('main button[type="submit"]').count() == 0
        expect(page.get_by_role('link', name='Aktuellen Stand neu laden')).to_have_attribute('href', path)
        targets(page)
        evidence = Path(os.environ.get('MASTER_DATA_EVIDENCE_DIR', str(tmp_path)))
        evidence.mkdir(parents=True, exist_ok=True)
        evidence.chmod(0o700)
        screenshot = evidence / f'location-conflict-{width}-js-{javascript}-existing-{existing}.png'
        page.screenshot(path=str(screenshot), full_page=True)
        screenshot.chmod(0o600)
        page.get_by_role('link', name='Zur aktuellen Liste').click()
        expect(page.get_by_text('Keine passenden Stammdaten')).to_be_visible()
        assert snapshot(owner) == before


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('purpose', ['stammdaten', 'tags', 'metadaten', 'allergenpruefung'])
def test_location_conflict_selections_are_visible_and_copyable(b3, master_server, browser, width, javascript, purpose, tmp_path):  # noqa: F811
    _, owner, client, _ = b3
    category = create(client, 'kategorien', name='Gemüse', code='VEG', sort_order='1').rsplit('/', 1)[1]
    tags = [create(client, 'tags', name=name, code=name.upper()).rsplit('/', 1)[1] for name in ('Regional', 'Saisonal')]
    path = create(client, name='Original')
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path)
        form = page.locator(f'form[action="{path}/{purpose}"]')
        expected = []
        if purpose == 'stammdaten':
            form.get_by_label('Kategorie', exact=True).select_option(category)
            expected = [('Kategorie', 'Ursprüngliche Referenz: ' + category)]
        elif purpose == 'tags':
            for tag in tags:
                form.locator(f'input[value="{tag}"]').check()
            expected = [('Tag · ursprüngliche Referenz', 'Ursprüngliche Referenz: ' + tag) for tag in tags]
        elif purpose == 'metadaten':
            for code in ['VEGETARIAN', 'VEGAN']:
                form.locator(f'input[value="{code}"]').check()
            form.locator('select[name="allergen_MILK"]').select_option('may_contain')
            expected = [('Kostform', 'Vegetarisch (VEGETARIAN)'), ('Kostform', 'Vegan (VEGAN)'),
                        ('Allergen · Milch (MILK)', 'Kann enthalten (may_contain)')]
        else:
            expected = [('Allergenprüfung', 'Als geprüft bestätigen (true)')]
        original = form.evaluate('el => Array.from(new FormData(el).entries())')
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('NEW','Neuer Standort',true)"))
        before = snapshot(owner)
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            if purpose == 'stammdaten':
                page.get_by_role('button', name='Stammdaten speichern', exact=True).click()
            else:
                form.get_by_role('button').click()
        assert outcome.value.status == 409
        expect(page.locator('#master-error')).to_be_focused()
        assert form.evaluate('el => Array.from(new FormData(el).entries())') == original
        for label, value in expected:
            control = page.get_by_label(label, exact=True)
            matches = [item for item in control.all() if item.input_value() == value]
            assert len(matches) == 1, (label, value)
            expect(matches[0]).to_be_visible()
            expect(matches[0]).to_have_attribute('readonly', '')
            matches[0].focus()
            page.keyboard.press('Control+A')
            assert matches[0].evaluate('el => el.value.slice(el.selectionStart, el.selectionEnd)') == value
        targets(page)
        assert page.locator('main button[type="submit"]').count() == 0
        page.screenshot(path=str(tmp_path / f'visible-selection-{purpose}-{width}-js{javascript}.png'), full_page=True)
        assert snapshot(owner) == before
