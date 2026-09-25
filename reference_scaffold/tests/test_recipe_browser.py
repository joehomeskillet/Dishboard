"""Native recipe editing with real PostgreSQL, Chromium and no-JavaScript coverage."""
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

import pytest
from playwright.sync_api import expect

from test_master_data_browser import master_server, targets  # noqa: F401
from test_recipe_routes import (  # noqa: F401
    app_engine, b3, create, fields, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import line, payload, snapshot
from test_recipe_forms import form_values
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_native_editor_rows_save_cancel_and_tabler(b3, master_server, browser, width, javascript, tmp_path):  # noqa: F811
    _, owner, client, _ = b3
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, posts = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        page.goto(base + '/admin/rezepte/neu')
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte')
        expect(page.locator('.page-header-subtitle')).to_have_text('Anlegen')
        token = page.locator('[name="_form_context"]').input_value()
        page.get_by_label('Titel', exact=True).fill('Browser Suppe')
        page.get_by_label('Beschreibung', exact=True).fill('\nUngespeichert\nZweite Zeile')
        page.get_by_label('Ausbeute/Menge', exact=True).fill('4')
        page.get_by_label('Ausbeuteeinheit', exact=True).select_option('PORTION')
        before = snapshot(owner)
        page.get_by_role('button', name='Zutat hinzufügen', exact=True).click()
        expect(page.get_by_label('Beschreibung', exact=True)).to_have_value('\nUngespeichert\nZweite Zeile')
        assert page.locator('[name="_form_context"]').input_value() == token
        assert snapshot(owner) == before
        page.get_by_label('Zutatenbezeichnung', exact=True).fill('Karotte')
        page.get_by_label('Menge', exact=True).fill('1')
        page.get_by_label('Einheit', exact=True).select_option('G')
        page.get_by_role('button', name='Schritt hinzufügen', exact=True).click()
        page.get_by_label('Anleitung', exact=True).fill('Waschen\nKochen')
        assert snapshot(owner) == before
        page.get_by_role('button', name='Anlegen', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte')
        expect(page.locator('.page-header-subtitle')).to_have_text('Browser Suppe')
        path = urlsplit(page.url).path
        line = page.locator('[name="ingredients.0.line_public_id"]').input_value()
        assert line and fields(client, path)['ingredients.0.line_public_id'] == line
        targets(page)
        assert not errors
        assert page.locator('link[href*="tabler.min.css"]').count() == 1
        assert page.locator('main [style], main style').count() == 0
        actions = page.locator('#recipe-editor .admin-compact-actions > summary')
        sprite_url = '/static/vendor/tabler-icons/tabler-icons.svg'
        sprite = context.request.get(base + sprite_url)
        assert sprite.status == 200
        symbols = ElementTree.fromstring(sprite.body())
        for name in ('dots', 'arrow-up', 'arrow-down', 'arrow-left'):
            symbol = symbols.find(f"{{http://www.w3.org/2000/svg}}symbol[@id='tabler-{name}']")
            assert symbol is not None and len(symbol)
        expect(page.get_by_role('link', name='Zurück zur Rezeptliste', exact=True).locator('use')).to_have_attribute('href', sprite_url + '#tabler-arrow-left')
        expect(page.locator('.admin-compact-toolbar summary use')).to_have_attribute('href', sprite_url + '#tabler-dots')
        for summary in actions.all():
            expect(summary.locator('use')).to_have_attribute('href', sprite_url + '#tabler-dots')
            summary.click()
        for control in page.locator('#recipe-editor button[formaction]').all():
            expect(control).to_be_visible()
            assert control.inner_text().strip()
            operation = parse_qs(urlsplit(control.get_attribute('formaction')).query)['row_action'][0]
            symbol = {'add': 'plus', 'remove': 'trash', 'up': 'arrow-up', 'down': 'arrow-down'}[operation]
            expect(control.locator('use')).to_have_attribute('href', sprite_url + '#tabler-' + symbol)
        for summary in actions.all():
            summary.click()
        page.get_by_role('heading', level=1).click()
        page.screenshot(path=str(tmp_path / f'recipe-editor-{width}-js{javascript}.png'), full_page=True)
        before = snapshot(owner)
        more = page.locator('.admin-compact-toolbar .admin-compact-actions > summary')
        expect(more).to_contain_text('Mehr')
        assert 'Mehr' in (more.inner_text() or '')
        more.click()
        page.get_by_role('link', name='Archivieren', exact=True).click()
        expect(page.get_by_text('Archivieren erhält Zutaten, Bilder und gespeicherte Stände.', exact=False)).to_be_visible()
        expect(page.get_by_role('button', name='Bestätigen', exact=True)).to_be_visible()
        post_count = len(posts)
        page.get_by_role('link', name='Abbrechen', exact=True).focus()
        page.keyboard.press('Enter')
        expect(page.locator('#recipe-editor')).to_be_visible()
        assert len(posts) == post_count and snapshot(owner) == before
        long_title = 'Rezept ' + 'S' * 113
        create(client, long_title)
        page.get_by_role('link', name='Zurück zur Rezeptliste', exact=True).click()
        expect(page.get_by_role('link', name='Browser Suppe bearbeiten')).to_be_visible()
        title = page.locator('.recipe-card .admin-list-name strong', has_text=long_title)
        expect(title).to_be_visible()
        expect(title).to_have_text(long_title)
        assert page.locator('.recipe-card h2').count() == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        targets(page)
        page.get_by_role('heading', level=1).click()
        page.screenshot(path=str(tmp_path / f'recipe-list-{width}-js{javascript}.png'), full_page=True)


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_long_original_source_is_visible_without_overflow(b3, master_server, browser, width, javascript):  # noqa: F811
    _, owner, client, _ = b3
    original = fields(client, '/admin/rezepte/neu')
    source = 'Q' * 200
    data = form_values(payload(ingredients=[line(source_reference=source)]))
    data['_csrf'], data['_form_context'] = original['_csrf'], original['_form_context']
    response = client.post('/admin/rezepte/neu', data=data)
    assert response.status_code == 303, response.text
    before = snapshot(owner)
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + response.location)
        origin = page.locator('p').filter(has_text=source)
        expect(origin).to_be_visible()
        assert origin.inner_text().endswith(source)
        assert origin.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
        targets(page)
    assert snapshot(owner) == before
