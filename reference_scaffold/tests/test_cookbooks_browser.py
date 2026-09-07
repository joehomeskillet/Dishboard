"""Native cookbook forms at 390/820/1440 with JavaScript on and off."""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from cafeteria import recipe_store as store
from test_cookbook_routes import Forms
from test_master_data_routes import b3, pg16, installed_pg16, seeded_pg16, app_engine  # noqa: F401
from test_master_data_db import signed_in
from test_recipe_store_db import payload, snapshot
from test_rendered_ui import browser  # noqa: F401

pytestmark = pytest.mark.skipif(
    not os.environ.get('TEST_DATABASE_URL'),
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


@pytest.fixture
def cookbook_server(b3):  # noqa: F811
    from cafeteria.admin import cookbook_routes as cookbooks
    app, owner, client, actor = b3
    cookbooks.register_on(app, url_prefix='/admin', endpoint_prefix='admin.')
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        first = store.create_recipe(engine, actor, payload(title='Alpha'), expected_location_id=location)
        second = store.create_recipe(engine, actor, payload(title='Beta'), expected_location_id=location)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    try:
        yield {
            'base': f'http://127.0.0.1:{server.server_port}',
            'cookie': cookie,
            'client': client,
            'first': first.public_id,
            'second': second.public_id,
            'owner': owner, 'engine': engine, 'actor': actor,
        }
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def targets(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('main [style]').count() == 0
    for control in page.locator('main :is(.btn, .form-control, .form-select)').all():
        if control.is_visible():
            box = control.bounding_box()
            assert box is not None and box['height'] >= 48
            control.focus()
            expect(control).to_be_focused()


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_native_cookbook_order_cancel_and_framework(cookbook_server, browser, width, javascript, tmp_path):  # noqa: F811
    base = cookbook_server['base']
    cookie = cookbook_server['cookie']
    client = cookbook_server['client']
    with browser.new_context(
        viewport={'width': width, 'height': 1100}, java_script_enabled=javascript,
        reduced_motion='reduce', service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors = []
        responses = {}
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('response', lambda response: responses.setdefault(urlsplit(response.url).path, []).append(response.status))
        page.goto(base + '/admin/kochbuecher')
        expect(page.get_by_role('heading', level=1)).to_have_text('Kochbücher')
        page.get_by_role('link', name='Kochbuch anlegen', exact=True).click()
        page.get_by_label('Name', exact=True).fill('Browserbuch')
        page.get_by_role('button', name='Anlegen', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Browserbuch')
        path = urlsplit(page.url).path
        recipes = page.locator(f'form[action="{path}/rezepte"]')
        recipes.locator('[name="recipe_public_ids"]').nth(0).select_option(cookbook_server['second'])
        recipes.locator('[name="recipe_positions"]').nth(0).fill('20')
        recipes.locator('[name="recipe_public_ids"]').nth(1).select_option(cookbook_server['first'])
        recipes.locator('[name="recipe_positions"]').nth(1).fill('10')
        recipes.get_by_role('button', name='Zuordnung speichern', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Browserbuch')
        saved = Forms(page.content()).forms[path + '/rezepte']
        assert saved.getlist('recipe_public_ids')[:2] == [cookbook_server['first'], cookbook_server['second']]
        page.get_by_role('link', name='Archivieren', exact=True).click()
        expect(page.get_by_role('heading', level=2, name='Kochbuch archivieren')).to_be_visible()
        before = client.get(path).text
        before_db, before_posts = snapshot(cookbook_server['owner']), list(posts)
        page.get_by_role('link', name='Abbrechen', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Browserbuch')
        assert 'Zuordnung speichern' in page.content()
        after = client.get(path).text
        # A GET legitimately signs a new timestamp; all remaining HTML stays identical.
        pattern = r'(name="_form_context" value=")[^"]*'
        assert re.sub(pattern, r'\1', after) == re.sub(pattern, r'\1', before)
        assert snapshot(cookbook_server['owner']) == before_db and posts == before_posts
        with signed_in(cookbook_server['engine'], cookbook_server['actor']):
            location = store.get_location(cookbook_server['engine'])
            for index in range(4):
                store.create_cookbook(cookbook_server['engine'], cookbook_server['actor'],
                                      name=('Langer Titel ' * 9) + str(index),
                                      description=('Lange Beschreibung ' * 80) if index == 0 else 'Kurz',
                                      expected_location_id=location)
        page.get_by_role('link', name='Zurück zur Liste').click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Kochbücher')
        expect(page.get_by_text('Browserbuch')).to_be_visible()
        expect(page.get_by_text('Symbole')).to_be_visible()
        targets(page)
        cards = page.locator('section[aria-label="Kochbücher"] article.card')
        boxes = [card.bounding_box() for card in cards.all()]
        assert len(boxes) == 5 and all(box is not None for box in boxes)
        assert max(box['height'] for box in boxes) - min(box['height'] for box in boxes) <= 1
        assert max(box['width'] for box in boxes) - min(box['width'] for box in boxes) <= 1
        assert cards.locator('.card-body').evaluate_all('els => els.every(el => el.scrollHeight <= el.clientHeight + 1)')
        destination = Path(os.environ.get('COOKBOOK_A4_EVIDENCE_DIR', str(tmp_path)))
        destination.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(destination / f'cookbooks-{width}-js{javascript}.png'), full_page=True)
        assets = page.locator('link[rel="stylesheet"], script[src]').evaluate_all(
            'els => els.map(el => new URL(el.href || el.src).pathname)')
        assert any('tabler' in asset and asset.endswith('.css') for asset in assets)
        assert all(
            200 in responses.get(asset, []) and set(responses[asset]) <= {200, 304}
            for asset in assets if javascript or asset.endswith('.css')
        )
        assert not any(asset.endswith('/app.css') for asset in assets)
        assert page.locator('.card').first.evaluate('el => getComputedStyle(el).display') == 'flex'
        assert not errors


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_stale_header_is_copyable_with_original_context(cookbook_server, browser, width, javascript):  # noqa: F811
    base, cookie, client = (cookbook_server[key] for key in ('base', 'cookie', 'client'))
    create = Forms(client.get('/admin/kochbuecher/neu').text).forms['/admin/kochbuecher/neu']
    create['name'] = 'Original'
    path = urlsplit(client.post('/admin/kochbuecher/neu', data=create).location).path
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path)
        form = page.locator(f'form[action="{path}"]')
        token = form.locator('[name="_form_context"]').input_value()
        version = form.locator('[name="row_version"]').input_value()
        form.get_by_label('Name', exact=True).fill('Mein Entwurf')
        form.locator('[name="description"]').fill('\nKopierbare Beschreibung')
        other = Forms(client.get(path).text).forms[path]
        other['name'] = 'Anderer Tab'
        assert client.post(path, data=other).status_code == 303
        before = snapshot(cookbook_server['owner'])
        with page.expect_response(lambda response: response.request.method == 'POST') as response:
            form.get_by_role('button', name='Speichern', exact=True).click()
        assert response.value.status == 409 and snapshot(cookbook_server['owner']) == before
        expect(page.locator('#recipe-error')).to_be_focused()
        expect(page.get_by_label('Name', exact=True)).to_have_value('Mein Entwurf')
        description = page.get_by_label('Beschreibung', exact=True)
        expect(description).to_have_value('\nKopierbare Beschreibung')
        description.focus()
        page.keyboard.press('Control+A')
        assert description.evaluate('el => el.value.slice(el.selectionStart, el.selectionEnd)') == '\nKopierbare Beschreibung'
        assert page.locator('[name="_form_context"]').input_value() == token
        assert page.locator('[name="row_version"]').input_value() == version
        assert page.locator('button[type="submit"]').count() == 0
        targets(page)
