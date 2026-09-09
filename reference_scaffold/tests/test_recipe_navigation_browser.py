"""Full factory navigation across the independently authored R2 modules."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria import recipe_store as store, roles
from cafeteria.master_data_types import ObjectExpectation
from test_master_data_db import signed_in
from test_recipe_store_db import payload, snapshot, target
from test_recipe_revision_routes import a3, b3, app_engine, pg16, installed_pg16, seeded_pg16, png, complete_a3  # noqa: F401
from test_recipe_images_browser import recipe_server  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


@pytest.fixture
def navigation(a3):  # noqa: F811
    complete_a3(a3)
    app, owner, client, actor, public_id = a3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        row = store.get_recipe(engine, public_id)
        image = store.add_recipe_image(engine, actor, target(row), data=png(), content_type='image/png',
                                       caption='Navigationsbild', expected_location_id=location)
        original = ObjectExpectation(image.public_id, image.row_version)
        preview = store.get_dependency_preview(engine, original, expected_location_id=location)
        revision = store.freeze_revision(engine, actor, original, expected_location_id=location,
                                         expected_dependency_hash=preview.dependency_hash_sha256)
        book = store.create_cookbook(engine, actor, name='Navigationskochbuch', expected_location_id=location)
        store.replace_cookbook_recipes(engine, actor, ObjectExpectation(book.public_id, book.row_version),
                                      [public_id], expected_location_id=location)
        for index in range(3):
            store.create_recipe(engine, actor, payload(title=('Langer Rezepttitel ' * 5) + str(index)),
                                expected_location_id=location)
    return public_id, book.public_id, revision.public_id


def sidebar(page, width, javascript, label):
    nav = page.locator('nav[aria-label="Backend"]:visible')
    if javascript and width < 1200 and nav.count() == 0:
        page.get_by_role('button', name='Menü', exact=True).click()
    link = nav.get_by_role('link', name=label, exact=True)
    expect(link).to_be_visible()
    link.focus()
    expect(link).to_be_focused()
    with page.expect_navigation(wait_until='load'):
        page.keyboard.press('Enter')


def active(page, label):
    if page.locator('nav[aria-label="Backend"]:visible').count() == 0:
        page.get_by_role('button', name='Menü', exact=True).click()
    selected = page.locator('nav[aria-label="Backend"]:visible a[aria-current="page"]')
    expect(selected).to_have_count(1)
    expect(selected).to_have_text(label)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_full_registered_navigation_is_native_and_read_only(navigation, a3, recipe_server, browser,  # noqa: F811
                                                           width, javascript, tmp_path):
    public_id, book_id, revision_id = navigation
    _, owner, _, _, _ = a3
    base, cookie = recipe_server
    before = snapshot(owner)
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, console_errors, posts, responses = [], [], [], {}
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: console_errors.append(
            {'text': message.text, 'page_url': page.url, 'location': message.location}
        ) if message.type == 'error' else None)
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        page.on('response', lambda response: responses.setdefault(urlsplit(response.url).path, []).append(response.status))
        assert page.goto(base + '/admin/cafeteria?week=2026-08-31').status == 200
        sidebar(page, width, javascript, 'Rezepte')
        active(page, 'Rezepte')
        cards = page.locator('.recipe-card-grid article')
        boxes = [card.bounding_box() for card in cards.all()]
        assert len(boxes) == 4 and all(box is not None for box in boxes)
        assert max(box['height'] for box in boxes) - min(box['height'] for box in boxes) <= 1
        assert cards.locator('.card-body').evaluate_all('els => els.every(el => el.scrollHeight <= el.clientHeight + 1)')
        summary = page.locator('summary').filter(has_text='Symbole')
        summary.focus()
        page.keyboard.press('Enter')
        expect(page.get_by_text('Stift: Rezept bearbeiten oder ansehen.')).to_be_visible()
        page.keyboard.press('Enter')
        expect(page.locator('details[open]')).to_have_count(0)
        editor = page.locator(f'main a[href="/admin/rezepte/{public_id}"]')
        assert editor.get_attribute('aria-label') and editor.get_attribute('data-bs-title')
        editor.focus()
        expect(editor).to_be_focused()
        if javascript:
            expect(page.get_by_role('tooltip')).to_be_visible()
        page.keyboard.press('Escape')
        expect(editor).to_be_focused()
        if javascript:
            expect(page.get_by_role('tooltip')).to_have_count(0)
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        active(page, 'Rezepte')
        expect(page.locator('#recipe-editor')).to_be_visible()
        page.get_by_role('link', name='Bilder verwalten', exact=True).click()
        active(page, 'Rezepte')
        expect(page.get_by_role('heading', name='Rezeptbilder', exact=True)).to_be_visible()
        assert not errors and not console_errors
        image = page.get_by_role('link', name='Bild 1 in voller Größe öffnen')
        asset_url = base + image.get_attribute('href')
        with page.expect_response(lambda response: response.url == asset_url) as asset_response:
            image.click()
        response = asset_response.value
        assert response.status == 200 and response.headers['content-type'] == 'image/png'
        assert response.headers['x-content-type-options'] == 'nosniff'
        # CDP may discard a cached image's body during ImageDocument navigation.
        # An authenticated real GET of the same clicked URL verifies exact bytes separately.
        byte_response = context.request.get(asset_url, max_redirects=0)
        assert byte_response.status == 200 and byte_response.headers['content-type'] == 'image/png'
        assert byte_response.headers['x-content-type-options'] == 'nosniff'
        assert byte_response.body() == png()
        assert page.evaluate('document.contentType') == 'image/png'
        assert page.locator('script').count() == 0
        expect(page.locator('img')).to_be_visible()
        assert page.locator('img').evaluate('el => el.complete && el.naturalWidth === 24')
        # Chromium's standalone ImageDocument adds its own styled wrapper to pure PNG bytes.
        # Preserve that viewer evidence separately; application HTML errors remain forbidden.
        viewer = {'url': asset_url, 'content_type': response.headers['content-type'],
                  'sha256': hashlib.sha256(byte_response.body()).hexdigest(),
                  'document': page.locator('html').evaluate('el => el.outerHTML'),
                  'console': list(console_errors)}
        (tmp_path / f'image-document-{width}-js{javascript}.json').write_text(json.dumps(viewer, indent=2))
        page.screenshot(path=str(tmp_path / f'image-document-{width}-js{javascript}.png'))
        page.go_back()
        page.get_by_role('link', name='Zum Rezept', exact=True).click()
        page.get_by_role('link', name='Revisionen', exact=True).click()
        active(page, 'Rezepte')
        page.get_by_role('link', name='Revision 1 öffnen', exact=True).click()
        assert urlsplit(page.url).path.endswith('/revisionen/' + revision_id)
        active(page, 'Rezepte')
        page.get_by_role('link', name='Alle Revisionen', exact=True).click()
        page.get_by_role('link', name='Zum Rezept', exact=True).click()
        page.get_by_role('link', name='Mengen berechnen', exact=True).click()
        active(page, 'Rezepte')
        page.get_by_role('link', name='Zum Rezept', exact=True).click()
        page.get_by_role('link', name='Archivieren', exact=True).click()
        page.keyboard.press('Escape')
        page.get_by_role('link', name='Abbrechen', exact=True).click()
        expect(page.locator('#recipe-editor')).to_be_visible()
        sidebar(page, width, javascript, 'Kochbücher')
        active(page, 'Kochbücher')
        page.locator(f'main a[href="/admin/kochbuecher/{book_id}"]').click()
        active(page, 'Kochbücher')
        page.locator(f'main a[href="/admin/rezepte/{public_id}"]').click()
        active(page, 'Rezepte')
        page.screenshot(path=str(tmp_path / f'navigation-{width}-js{javascript}.png'), full_page=True)
        assets = page.locator('link[rel="stylesheet"],script[src]').evaluate_all(
            'els => els.map(el => new URL(el.href || el.src).pathname)')
        assert any('tabler.min.css' in asset for asset in assets)
        assert all(any(code in (200, 304) for code in responses.get(asset, []))
                   for asset in assets if javascript or asset.endswith('.css'))
        viewer_errors = [entry for entry in console_errors if entry['page_url'] == asset_url]
        assert all(entry['page_url'] == asset_url for entry in console_errors), console_errors
        assert all(entry['location']['url'] == asset_url and
                   entry['text'].startswith('Applying inline style violates the following Content Security Policy')
                   for entry in viewer_errors), viewer_errors
        assert not errors and not posts
    assert snapshot(owner) == before


def test_navigation_respects_read_capability_without_granting_writes(navigation, a3, monkeypatch):  # noqa: F811
    app, owner, client, _, public_id = a3
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    before = snapshot(owner)
    for path in ('/admin/rezepte', '/admin/kochbuecher', f'/admin/rezepte/{public_id}/bilder'):
        result = client.get(path)
        assert result.status_code == 200
        assert 'href="/admin/rezepte"' in result.text and 'href="/admin/kochbuecher"' in result.text
        assert 'Rezept anlegen</a>' not in result.text and 'Bild hochladen</button>' not in result.text
    assert client.post('/admin/rezepte/neu', data={}).status_code == 403
    assert client.post('/admin/kochbuecher/neu', data={}).status_code == 403
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', set())
    for path in ('/admin/rezepte', '/admin/kochbuecher'):
        assert client.get(path).status_code == 403
    with app.test_request_context():
        from cafeteria.admin import recipe_navigation_context
        assert recipe_navigation_context() == {'can_browse_recipes': False}
    assert snapshot(owner) == before
