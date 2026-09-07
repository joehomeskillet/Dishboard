"""Native recipe editing with real PostgreSQL, Chromium and no-JavaScript coverage."""
from urllib.parse import urlsplit

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
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezept anlegen')
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
        page.get_by_role('button', name='Rezept anlegen', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezept bearbeiten')
        path = urlsplit(page.url).path
        line = page.locator('[name="ingredients.0.line_public_id"]').input_value()
        assert line and fields(client, path)['ingredients.0.line_public_id'] == line
        targets(page)
        assert not errors
        assert page.locator('link[href*="tabler.min.css"]').count() == 1
        assert page.locator('main [style], main style').count() == 0
        for control in page.locator('main [data-admin-icon-action]').all():
            assert control.get_attribute('aria-label')
            assert control.locator('use').get_attribute('href').split('#')[-1] in {
                'tabler-plus', 'tabler-trash', 'tabler-chevron-left', 'tabler-chevron-right'}
        page.get_by_role('heading', level=1).click()
        page.screenshot(path=str(tmp_path / f'recipe-editor-{width}-js{javascript}.png'), full_page=True)
        before = snapshot(owner)
        page.get_by_role('link', name='Archivieren', exact=True).click()
        expect(page.get_by_role('button', name='Archivieren bestätigen')).to_be_visible()
        post_count = len(posts)
        page.get_by_role('link', name='Abbrechen', exact=True).focus()
        page.keyboard.press('Enter')
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezept bearbeiten')
        assert len(posts) == post_count and snapshot(owner) == before
        long_title = 'Rezept ' + 'S' * 113
        create(client, long_title)
        page.get_by_role('link', name='Zur Rezeptliste', exact=True).click()
        expect(page.get_by_role('link', name='Browser Suppe bearbeiten')).to_be_visible()
        expect(page.get_by_role('heading', name=long_title, exact=True)).to_be_visible()
        heights = page.locator('.recipe-card').evaluate_all('els => els.map(el => el.getBoundingClientRect().height)')
        assert len(heights) == 2 and max(heights) - min(heights) <= 1
        assert page.locator('.recipe-card h2').evaluate_all('els => els.every(el => el.scrollHeight <= el.clientHeight + 1)')
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
