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


def _close_sidebar_menu(page) -> None:
    if page.locator('#sidebar-menu.show').count():
        page.evaluate("""() => {
          const menu = document.getElementById('sidebar-menu');
          const offcanvas = window.tabler?.Offcanvas?.getInstance(menu);
          if (offcanvas) offcanvas.hide();
        }""")
        page.wait_for_selector('#sidebar-menu', state='hidden')


def sidebar(page, width, javascript, label):
    disclosure = page.locator('.admin-nojs-nav:visible')
    if disclosure.count() and disclosure.get_attribute('open') is None:
        disclosure.locator('summary').click()
    nav = page.locator('nav[aria-label="Backend"]:visible')
    if javascript and width < 992 and nav.count() == 0:
        page.get_by_role('button', name='Menü', exact=True).click()
        page.wait_for_selector('#sidebar-menu.show:not(.showing)')
    if nav.get_by_role('link', name=label, exact=True).count() == 0:
        with page.expect_navigation(wait_until='load'):
            nav.get_by_role('link', name='Menüs & Bausteine', exact=True).click()
        nav = page.locator('nav[aria-label="Backend"]:visible')
        if javascript and width < 992:
            page.get_by_role('button', name='Menü', exact=True).click()
            page.wait_for_selector('#sidebar-menu.show:not(.showing)')
        elif disclosure.count():
            disclosure.locator('summary').click()
    link = nav.get_by_role('link', name=label, exact=True)
    expect(link).to_be_visible()
    link.focus()
    expect(link).to_be_focused()
    with page.expect_navigation(wait_until='load'):
        page.keyboard.press('Enter')
    if javascript and width < 992:
        _close_sidebar_menu(page)


def active(page, label):
    disclosure = page.locator('.admin-nojs-nav:visible')
    if disclosure.count() and disclosure.get_attribute('open') is None:
        disclosure.locator('summary').click()
    toggle = page.get_by_role('button', name='Menü', exact=True)
    if page.locator('nav[aria-label="Backend"]:visible').count() == 0:
        toggle.click()
        page.wait_for_selector('#sidebar-menu.show:not(.showing)')
    selected = page.locator('nav[aria-label="Backend"]:visible a[aria-current="page"]')
    expect(selected).to_have_count(1)
    expect(selected).to_have_text(label)
    expect(page.locator('nav[aria-label="Backend"]:visible .admin-nav-area.active > .nav-link')).to_have_text(
        'Menüs & Bausteine',
    )
    if toggle.is_visible() and page.locator('#sidebar-menu.show').count():
        _close_sidebar_menu(page)
        expect(toggle).to_have_attribute('aria-expanded', 'false')
        expect(toggle).to_be_focused()
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
        rows = cards.locator('.admin-list-row')
        expect(rows).to_have_count(4)
        assert rows.evaluate_all('''els => els.every(el =>
            el.scrollHeight <= el.clientHeight + 1 && el.scrollWidth <= el.clientWidth + 1)''')
        metrics = rows.evaluate_all('''els => els.map(el => {
            const title = el.querySelector('.admin-list-name strong');
            const lineHeight = parseFloat(getComputedStyle(title).lineHeight);
            return {height: el.closest('article').getBoundingClientRect().height,
                titleLines: Math.round(title.getBoundingClientRect().height / lineHeight),
                parts: [...el.children].map(child => ({height: child.getBoundingClientRect().height,
                    top: child.getBoundingClientRect().top - el.getBoundingClientRect().top})),
                padding: getComputedStyle(el).padding, gap: getComputedStyle(el).gap};
        })''')
        (tmp_path / f'recipe-rows-{width}-js{javascript}.json').write_text(json.dumps(metrics, indent=2))
        if width >= 1024:
            single_line = [row for row in metrics if row['titleLines'] == 1]
            assert single_line
            assert all(row['height'] <= 96 for row in single_line), metrics
        for action in rows.locator('.btn:visible').all():
            box = action.bounding_box()
            assert box and box['width'] >= 48 and box['height'] >= 48, box
        page.screenshot(path=str(tmp_path / f'recipe-list-{width}-js{javascript}.png'), full_page=True)
        # Native disclosure grows only its own row, with and without JavaScript.
        more = cards.first.locator('details > summary')
        more.click()
        expanded = [card.bounding_box() for card in cards.all()]
        assert expanded[0]['height'] > boxes[0]['height']
        assert all(abs(after['height'] - before['height']) <= 1
                   for before, after in zip(boxes[1:], expanded[1:]))
        more.click()
        editor = page.locator(f'main a[href="/admin/rezepte/{public_id}"]')
        expect(editor).to_have_attribute('data-semantic', 'actions.edit')
        expect(editor).to_have_attribute('aria-label', 'Suppe bearbeiten')
        box = editor.bounding_box()
        assert box and box['width'] >= 48 and box['height'] >= 48
        editor.focus()
        page.keyboard.press('Tab')
        page.keyboard.press('Shift+Tab')
        expect(editor).to_be_focused()
        assert editor.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.keyboard.press('Escape')
        expect(editor).to_be_focused()
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        active(page, 'Rezepte')
        expect(page.locator('#recipe-editor')).to_be_visible()
        menu = page.locator('.admin-compact-toolbar .admin-compact-actions > summary')
        expect(menu).to_contain_text('Mehr')
        menu.click()
        images = page.locator('.admin-compact-toolbar').get_by_role('link', name='Bild', exact=True)
        expect(images).to_contain_text('Bild')
        assert 'Bild' in (images.get_attribute('aria-label') or '')
        images.click()
        active(page, 'Rezepte')
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte')
        expect(page.locator('.page-header-subtitle')).to_have_text('Suppe')
        expect(page.get_by_role('heading', name='Gespeicherte Bilder', exact=True)).to_be_visible()
        assert not errors and not console_errors
        image = page.get_by_role('link', name='Bild 1 in voller Grösse öffnen', exact=True)
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
        back = page.get_by_role('link', name='Zum Rezept', exact=True)
        expect(back).to_have_text('Zum Rezept')
        expect(back).to_have_accessible_name('Zum Rezept')
        back.click()
        page.locator('.admin-compact-toolbar .admin-compact-actions > summary').click()
        page.get_by_role('link', name='Rezept-History', exact=True).click()
        active(page, 'Rezepte')
        page.get_by_role('link', name='Gespeicherten Stand 1 ansehen', exact=True).click()
        assert urlsplit(page.url).path.endswith('/revisionen/' + revision_id)
        active(page, 'Rezepte')
        page.get_by_role('link', name='Zur Rezept-History', exact=True).click()
        page.get_by_role('link', name='Aktuellen Entwurf ansehen', exact=True).click()
        expect(page.get_by_text('Entwurf · nicht festgeschrieben', exact=True)).to_be_visible()
        page.get_by_role('link', name='Bearbeiten', exact=True).click()
        page.locator('.admin-compact-toolbar .admin-compact-actions > summary').click()
        page.get_by_role('link', name='Mengen berechnen', exact=True).click()
        active(page, 'Rezepte')
        page.get_by_role('link', name='Rezept ansehen', exact=True).click()
        page.get_by_role('link', name='Bearbeiten', exact=True).click()
        page.locator('.admin-compact-toolbar .admin-compact-actions > summary').click()
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
    for path in ('/admin/rezepte', '/admin/kochbuecher', f'/admin/rezepte/{public_id}/bilder', f'/admin/rezepte/{public_id}/ansicht'):
        result = client.get(path)
        assert result.status_code == 200
        assert 'href="/admin/rezepte"' in result.text and 'href="/admin/kochbuecher"' in result.text
        assert 'Rezept anlegen</a>' not in result.text and 'Bild hochladen</button>' not in result.text
    listing = client.get('/admin/rezepte').text
    assert f'href="/admin/rezepte/{public_id}/ansicht"' in listing
    assert f'href="/admin/rezepte/{public_id}"' not in listing
    assert 'PDF öffnen · Stand 1' in listing
    assert client.post('/admin/rezepte/neu', data={}).status_code == 403
    assert client.post('/admin/kochbuecher/neu', data={}).status_code == 403
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', set())
    for path in ('/admin/rezepte', '/admin/kochbuecher'):
        assert client.get(path).status_code == 403
    with app.test_request_context():
        from cafeteria.admin import recipe_navigation_context
        assert recipe_navigation_context() == {'can_browse_recipes': False}
    assert snapshot(owner) == before
