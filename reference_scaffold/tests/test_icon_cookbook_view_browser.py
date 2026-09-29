"""D13: read-only cookbook navigation through real PostgreSQL, HTTP and Chromium."""
from __future__ import annotations

from uuid import uuid4

import pytest
from playwright.sync_api import expect
from sqlalchemy.exc import SQLAlchemyError

from cafeteria import recipe_store as store, roles
from test_cookbooks_browser import cookbook_server  # noqa: F401
from test_master_data_db import signed_in
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_recipe_store_db import snapshot, target
from test_rendered_ui import browser  # noqa: F401


BOOK_NAME = 'Saisonküche mit Gemüse, Kräutern und gemeinsamen Lieblingsrezepten'
DESCRIPTION = 'Rezepte für die Gemeinschaftsküche mit Gemüse und Kräutern aus dem Garten.'
LONG_RECIPE = 'Geröstetes Sommergemüse mit Kräuterkartoffeln und hausgemachter Zitronensauce für die Gemeinschaftsküche'
VIEWPORTS = [(1440, 900, False), (390, 844, False), (390, 844, True)]


@pytest.fixture
def reading_book(cookbook_server):  # noqa: F811
    data = cookbook_server
    engine, actor = data['engine'], data['actor']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        first = store.get_recipe(engine, data['first'])
        store.update_recipe(engine, actor, target(first), {**first.payload, 'title': LONG_RECIPE},
                            expected_location_id=location)
        book = store.create_cookbook(
            engine, actor, name=BOOK_NAME, description=DESCRIPTION, expected_location_id=location,
        )
        book = store.replace_cookbook_recipes(
            engine, actor, target(book), [data['second'], data['first']], expected_location_id=location,
        )
        recipe = store.get_recipe(engine, data['second'])
        store.set_recipe_active(engine, actor, target(recipe), active=False, expected_location_id=location)
    return {**data, 'book': book, 'path': '/admin/kochbuecher/' + book.public_id}


@pytest.mark.parametrize('state', ['writer', 'reader', 'archived'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('width,height,touch', VIEWPORTS, ids=['desktop', 'mobile-fine', 'mobile-coarse'])
def test_cookbook_view_order_and_entries(reading_book, browser, monkeypatch, tmp_path, state, javascript,  # noqa: F811
                                       width, height, touch):
    data = reading_book
    path, base, book = data['path'], data['base'], data['book']
    if state == 'archived':
        with signed_in(data['engine'], data['actor']):
            store.set_cookbook_active(data['engine'], data['actor'], target(book), active=False,
                                      expected_location_id=store.get_location(data['engine']))
    if state == 'reader':
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    before = snapshot(data['owner'])
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch,
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        cookie = data['cookie']
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, posts = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        response = page.goto(base + path + '/ansicht')
        assert response.status == 200
        assert response.headers['cache-control'] == 'no-store'
        expect(page.get_by_role('heading', level=1)).to_have_text(BOOK_NAME)
        main = page.locator('main')
        expect(main.get_by_text(DESCRIPTION, exact=True)).to_be_visible()
        expect(main.locator('form, input, select, textarea')).to_have_count(0)
        expect(main.get_by_text('2 Rezepte', exact=True)).to_be_visible()
        rows = main.locator('tbody tr')
        expect(rows).to_have_count(2)
        expect(rows.locator('th a')).to_have_text(['Beta', LONG_RECIPE])
        for index, recipe_id in enumerate((data['second'], data['first'])):
            expect(rows.nth(index).locator('th a')).to_have_attribute('href', f'/admin/rezepte/{recipe_id}/ansicht')
            expect(rows.nth(index).get_by_text(str(index + 1), exact=True)).to_be_visible()
            expect(rows.nth(index).get_by_text('4 PORTION', exact=True)).to_be_visible()
        expect(rows.nth(0).get_by_text('Archiviert', exact=True)).to_be_visible()
        expect(rows.nth(1).get_by_text('Archiviert', exact=True)).to_have_count(0)
        expect(page.locator('.page-header').get_by_text('Archiviert', exact=True)).to_have_count(
            1 if state == 'archived' else 0)
        edit = page.locator('.page-header [data-semantic="actions.edit"]')
        expect(edit).to_have_count(0 if state == 'reader' else 1)
        if state != 'reader':
            expect(edit).to_have_attribute('href', path)
        assert page.evaluate('matchMedia("(pointer: coarse)").matches') == touch
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        for control in main.locator('.ui-sem-control').all():
            if control.is_visible():
                box = control.bounding_box()
                minimum = 44 if touch else 36
                assert box and box['width'] >= minimum and box['height'] >= minimum
                name = control.get_attribute('aria-label')
                assert name and control.get_attribute('data-ui-tooltip') == name
                control.focus()
                expect(control).to_be_focused()
        for row in rows.all():
            assert row.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
        expect(page.locator('.admin-nav-subitems [aria-current="page"]:visible')).to_have_count(
            1 if width >= 992 else 0)
        page.screenshot(path=str(tmp_path / f'view-{state}-{width}-{touch}-js{javascript}.png'), full_page=True)
        rows.nth(0).locator('th a').click()
        expect(page).to_have_url(base + f'/admin/rezepte/{data["second"]}/ansicht')
        expect(page.locator('main')).to_contain_text('Beta')

        page.goto(base + '/admin/kochbuecher?archived=1')
        row = page.locator('.admin-list-row').filter(has=page.get_by_text(BOOK_NAME, exact=True))
        expect(row.locator('.admin-list-primary a')).to_have_count(0)
        primary = row.locator('.cookbook-row-action')
        expect(primary).to_have_attribute('href', path if state == 'writer' else path + '/ansicht')
        if state == 'writer':
            summary = row.locator('summary')
            summary.focus()
            page.keyboard.press('Enter')
            view = row.get_by_role('link', name=f'{BOOK_NAME} öffnen', exact=True)
            expect(view).to_be_visible()
            if not javascript:
                page.keyboard.press('Tab')
            expect(view).to_be_focused()
            if javascript:
                tooltip = page.get_by_role('tooltip', name=f'{BOOK_NAME} öffnen', exact=True)
                expect(tooltip).to_be_visible()
                page.keyboard.press('Escape')
                expect(page.get_by_role('tooltip')).to_have_count(0)
                expect(row.locator('details')).to_have_attribute('open', '')
                expect(view).to_be_focused()
                page.keyboard.press('Escape')
                expect(summary).to_be_focused()
                page.keyboard.press('Enter')
                expect(view).to_be_focused()
            page.keyboard.press('Enter')
        else:
            expect(row.locator('summary')).to_have_count(0)
            primary.click()
        expect(page).to_have_url(base + path + '/ansicht')
        page.goto(base + path)
        view = page.locator('.page-header').get_by_role('link', name=f'{BOOK_NAME} öffnen', exact=True)
        expect(view).to_have_count(1)
        view.click()
        expect(page).to_have_url(base + path + '/ansicht')
        assert not errors and not posts
    assert snapshot(data['owner']) == before


def test_cookbook_view_access_and_methods(reading_book, b3, monkeypatch):  # noqa: F811
    data = reading_book
    app, _, client, _ = b3
    path = data['path'] + '/ansicht'
    before = snapshot(data['owner'])
    assert client.get(path).status_code == 200
    assert client.post(path, data={'_csrf': 'b3-test-csrf'}).status_code == 405
    for identifier in ('invalid', str(uuid4())):
        response = client.get(f'/admin/kochbuecher/{identifier}/ansicht')
        assert response.status_code == 404
    assert app.test_client().get(path).status_code == 401
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', set())
    assert client.get(path).status_code == client.get(data['path']).status_code == 403
    assert snapshot(data['owner']) == before


def test_cookbook_view_empty_and_unavailable_recipe(reading_book, browser, monkeypatch):  # noqa: F811
    data = reading_book
    engine, actor = data['engine'], data['actor']
    with signed_in(engine, actor):
        book = store.create_cookbook(engine, actor, name='Leeres Kochbuch',
                                     expected_location_id=store.get_location(engine))
    read_recipes = store.list_recipes

    def without_first(*args, **kwargs):
        return tuple(row for row in read_recipes(*args, **kwargs) if row.public_id != data['first'])

    monkeypatch.setattr(store, 'list_recipes', without_first)
    with browser.new_context(viewport={'width': 390, 'height': 844}, java_script_enabled=False) as context:
        cookie = data['cookie']
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': data['base']}])
        page = context.new_page()
        assert page.goto(data['base'] + data['path'] + '/ansicht').status == 200
        missing = page.locator('main tbody tr').nth(1)
        expect(missing).to_contain_text('Rezept nicht verfügbar')
        expect(missing.locator('a')).to_have_count(0)
        expect(missing.locator('.admin-empty-value')).to_have_text('—')
        assert page.goto(data['base'] + f'/admin/kochbuecher/{book.public_id}/ansicht').status == 200
        expect(page.locator('main').get_by_text('0 Rezepte', exact=True)).to_be_visible()
        expect(page.locator('main').get_by_text('Noch keine Rezepte zugeordnet.', exact=True)).to_be_visible()
        expect(page.locator('main form, main table')).to_have_count(0)


def test_cookbook_view_english(reading_book, b3, monkeypatch):  # noqa: F811
    app, _, client, _ = b3
    monkeypatch.setitem(app.config, 'UI_LOCALE', 'en')
    path = reading_book['path']
    response = client.get(path + '/ansicht')
    assert response.status_code == 200
    assert '2 Rezepte' in response.text and 'Archiviert' in response.text
    assert 'Ausbeute' in response.text and 'Recipes' in response.text
    assert f'aria-label="Edit {BOOK_NAME}"' in response.text
    for source in (path, '/admin/kochbuecher'):
        html = client.get(source).text
        assert f'aria-label="Open {BOOK_NAME}"' in html
        assert 'Ansicht öffnen' not in html


@pytest.mark.parametrize('failure', ['location_changed', 'database_unavailable'])
def test_cookbook_view_read_errors_fail_closed(reading_book, monkeypatch, failure):
    data = reading_book
    original_location = store.get_location
    reads = []

    def changed_location(*args, **kwargs):
        location = original_location(*args, **kwargs)
        reads.append(location)
        return location if len(reads) == 1 else location + 1

    def offline(*args, **kwargs):
        raise SQLAlchemyError('private database detail')

    if failure == 'location_changed':
        monkeypatch.setattr(store, 'get_location', changed_location)
    else:
        monkeypatch.setattr(store, 'list_recipes', offline)
    response = data['client'].get(data['path'] + '/ansicht')
    assert response.status_code == (409 if failure == 'location_changed' else 503)
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'private database detail' not in response.text and BOOK_NAME not in response.text
