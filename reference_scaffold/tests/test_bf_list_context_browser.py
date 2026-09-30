"""BF-E2 list context: T01 density, T13 URL context, T19 page clamp, T12 scroll gap."""
from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria.component_catalog_store import AdminScope
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.workflow_partial_store import persist_week_header
from test_master_data_browser import master_server  # noqa: F401
from test_master_data_db import payload as food_payload, signed_in
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_recipe_store_db import payload as recipe_payload
from test_rendered_ui import browser  # noqa: F401


def _parts(b3):
    app, _owner, client, actor = b3
    return app, client, actor, app.extensions['cafeteria_db']


def _location(engine, actor) -> int:
    from cafeteria import recipe_store as store
    with signed_in(engine, actor):
        return store.get_location(engine)


def _recipes(engine, actor, count: int, prefix: str) -> None:
    from cafeteria import recipe_store as store
    with signed_in(engine, actor):
        location = store.get_location(engine)
        for index in range(count):
            store.create_recipe(
                engine, actor, recipe_payload(title=f'{prefix} {index:03d}'), expected_location_id=location,
            )


def _cookbooks(engine, actor, count: int, prefix: str) -> list:
    from cafeteria import recipe_store as store
    created = []
    with signed_in(engine, actor):
        location = store.get_location(engine)
        for index in range(count):
            created.append(store.create_cookbook(
                engine, actor, name=f'{prefix} {index:03d}', expected_location_id=location,
            ))
    return created


def _foods(engine, actor, count: int, prefix: str) -> None:
    from cafeteria import master_data_store as masters
    with signed_in(engine, actor):
        for index in range(count):
            masters.create_food(engine, actor, food_payload(f'{prefix} {index:03d}'))


def _weeks(engine, actor, count: int) -> None:
    scope = AdminScope(actor.user_id, _location(engine, actor), 'staff_guest', actor.authz_version)
    start = date(2026, 1, 5)
    for index in range(count):
        persist_week_header(
            engine, scope, start + timedelta(days=7 * index),
            {'title': f'BFWoche {index:02d}', 'shared_note': ''}, 0,
        )


def _shown(client, url: str) -> str:
    """Out-of-range pages render the last occupied page in place and keep the request URL."""
    response = client.get(url)
    assert response.status_code == 200, (url, response.status_code)
    assert 'Location' not in response.headers
    return response.get_data(as_text=True)


def _open(browser, base, cookie, javascript: bool, width: int = 1280, height: int = 800):
    context = browser.new_context(
        viewport={'width': width, 'height': height}, java_script_enabled=javascript,
        reduced_motion='reduce', service_workers='block',
    )
    context.add_init_script('localStorage.clear(); sessionStorage.clear();')
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
    return context


@pytest.mark.parametrize('javascript', [False, True])
def test_t01_single_recipe_row_stays_compact(b3, master_server, browser, tmp_path, javascript):  # noqa: F811
    """T01: one real row stays a row. The missing-data warning is not filler."""
    _app, _client, actor, engine = _parts(b3)
    _recipes(engine, actor, 1, 'BFEinzeln')
    base, cookie = master_server
    context = _open(browser, base, cookie, javascript, height=700)
    try:
        page = context.new_page()
        page.goto(base + '/admin/rezepte?q=BFEinzeln', wait_until='load')
        expect(page.locator('.recipe-row')).to_have_count(1)
        expect(page.locator('[data-empty-kind]')).to_have_count(0)
        expect(page.locator('.recipe-row')).to_contain_text('Angaben fehlen')
        expect(page.locator('.recipe-row')).to_contain_text('BFEinzeln 000')
        card = page.locator('.recipe-list-card').bounding_box()
        assert card is not None and card['height'] < 350
        page.screenshot(path=str(tmp_path / f't01-js-{javascript}.png'))
    finally:
        context.close()


def test_t13_return_link_is_the_url_in_each_tab(b3, master_server, browser):  # noqa: F811
    """T13: a second tab and a fresh context read only their own from= query."""
    from cafeteria import recipe_store as store
    _app, _client, actor, engine = _parts(b3)
    with signed_in(engine, actor):
        location = store.get_location(engine)
        alpha = store.create_recipe(engine, actor, recipe_payload(title='Alpha BF'), expected_location_id=location)
        beta = store.create_recipe(engine, actor, recipe_payload(title='Beta BF'), expected_location_id=location)
    base, cookie = master_server
    alpha_url = f'{base}/admin/rezepte/{alpha.public_id}?from=recipes&q=Alpha+BF&archived=0&page=2'
    beta_url = f'{base}/admin/rezepte/{beta.public_id}?from=recipes&q=Beta+BF&archived=1&page=3'

    def back_query(page, url: str) -> dict[str, list[str]]:
        page.goto(url, wait_until='load')
        href = page.get_by_role('link', name='Zur Liste der Rezepte', exact=True).get_attribute('href')
        assert href
        return parse_qs(urlsplit(href).query)

    context = _open(browser, base, cookie, True)
    try:
        first = context.new_page()
        second = context.new_page()
        alpha_query = back_query(first, alpha_url)
        beta_query = back_query(second, beta_url)
        assert back_query(first, first.url) == alpha_query
    finally:
        context.close()
    fresh = _open(browser, base, cookie, True)
    try:
        alone = back_query(fresh.new_page(), beta_url)
    finally:
        fresh.close()
    assert alpha_query['q'] == ['Alpha BF'] and alpha_query['page'] == ['2'] and alpha_query['archived'] == ['0']
    assert beta_query['q'] == ['Beta BF'] and beta_query['page'] == ['3'] and beta_query['archived'] == ['1']
    assert alone == beta_query


def test_t13_editor_query_still_rejects_unknown_and_duplicate_keys(b3):  # noqa: F811
    from cafeteria import recipe_store as store
    _app, client, actor, engine = _parts(b3)
    with signed_in(engine, actor):
        location = store.get_location(engine)
        created = store.create_recipe(engine, actor, recipe_payload(title='BFKontext'), expected_location_id=location)
    path = f'/admin/rezepte/{created.public_id}'
    assert client.get(path + '?from=recipes&bogus=1').status_code == 400
    assert client.get(path + '?from=recipes&page=2&page=3').status_code == 400
    assert client.get('/admin/rezepte?page=2&page=3').status_code == 400
    assert client.get('/admin/rezepte?profile=patient').status_code == 400


def test_t19_pages_past_the_end_clamp_without_dropping_context(b3):  # noqa: F811
    """T19 HTTP: page 5 of a two-page result renders page 2 and keeps the filter in the form."""
    from cafeteria.admin import cookbook_routes as cookbooks
    from cafeteria import recipe_store as store
    app, client, actor, engine = _parts(b3)
    cookbooks.register_on(app, url_prefix='/admin', endpoint_prefix='admin.')
    _recipes(engine, actor, 51, 'BFKlemme')
    books = _cookbooks(engine, actor, 51, 'BFBuch')
    _foods(engine, actor, 51, 'BFZutat')
    _weeks(engine, actor, 13)
    direct = client.get('/admin/rezepte?q=BFKlemme&page=2')
    assert direct.status_code == 200 and 'BFKlemme 050' in direct.get_data(as_text=True)
    recipes = _shown(client, '/admin/rezepte?q=BFKlemme&page=5')
    assert 'BFKlemme 050' in recipes and 'Seite 2' in recipes and 'value="BFKlemme"' in recipes
    books_page = _shown(client, '/admin/kochbuecher?q=BFBuch&page=5')
    assert 'BFBuch 050' in books_page and 'BFBuch 000' not in books_page and 'value="BFBuch"' in books_page
    foods = _shown(client, '/admin/grundlagen?q=BFZutat&page=5')
    assert 'BFZutat 050' in foods and 'BFZutat 000' not in foods and 'value="BFZutat"' in foods
    weeks = _shown(client, '/admin/cafeteria/wochen?page=5')
    assert 'BFWoche 00' in weeks and 'Seite 2' in weeks
    assert client.get('/admin/cafeteria/wochen?page=2').status_code == 200
    with signed_in(engine, actor):
        store.set_cookbook_active(
            engine, actor, ObjectExpectation(books[-1].public_id, books[-1].row_version),
            active=False, expected_location_id=store.get_location(engine),
        )
    remaining = _shown(client, '/admin/kochbuecher?q=BFBuch&page=2')
    # Each row repeats the name in accessible labels; count the primary cell only.
    assert remaining.count('admin-list-primary">BFBuch 050<') == 0
    assert remaining.count('admin-list-primary">BFBuch ') == 50
    assert 'Seite ' not in remaining


def test_t19_empty_collection_clamps_to_page_one(b3):  # noqa: F811
    from cafeteria.admin import cookbook_routes as cookbooks
    app, client, _actor, _engine = _parts(b3)
    cookbooks.register_on(app, url_prefix='/admin', endpoint_prefix='admin.')
    recipes = _shown(client, '/admin/rezepte?q=BFKeine&page=4')
    assert 'Keine passenden Rezepte' in recipes and 'value="BFKeine"' in recipes and 'Seite ' not in recipes
    books = _shown(client, '/admin/kochbuecher?q=BFKeine&page=5')
    assert 'Keine passenden Kochbücher' in books and 'value="BFKeine"' in books and 'Seite ' not in books
    foods = _shown(client, '/admin/grundlagen?q=BFKeine&page=4')
    assert 'Keine passenden' in foods and 'value="BFKeine"' in foods and 'Seite ' not in foods
    weeks = _shown(client, '/admin/cafeteria/wochen?page=5')
    assert 'Noch keine gespeicherten Wochen' in weeks and 'Seite ' not in weeks
    assert client.get('/admin/rezepte?page=1').status_code == 200
    assert client.get('/admin/cafeteria/wochen?page=1').status_code == 200


def test_t19_unknown_and_duplicate_queries_stay_400(b3):  # noqa: F811
    from cafeteria.admin import cookbook_routes as cookbooks
    app, client, _actor, _engine = _parts(b3)
    cookbooks.register_on(app, url_prefix='/admin', endpoint_prefix='admin.')
    assert client.get('/admin/rezepte?page=9&bogus=1').status_code == 400
    assert client.get('/admin/kochbuecher?page=9&page=8').status_code == 400
    assert client.get('/admin/grundlagen?kind=nope').status_code == 400
    assert client.get('/admin/cafeteria/wochen?page=9&family=patienten').status_code == 400


@pytest.mark.parametrize('javascript', [False, True])
def test_t19_archive_last_recipe_returns_to_a_valid_page(b3, master_server, browser, javascript):  # noqa: F811
    """T19: archiving the only row on the last page shows the remaining rows and keeps the filter."""
    _app, _client, actor, engine = _parts(b3)
    _recipes(engine, actor, 51, 'BFKlemme')
    base, cookie = master_server
    context = _open(browser, base, cookie, javascript)
    try:
        page = context.new_page()
        page.goto(base + '/admin/rezepte?q=BFKlemme&page=2', wait_until='load')
        expect(page.locator('.recipe-row')).to_have_count(1)
        expect(page.locator('.recipe-row')).to_contain_text('BFKlemme 050')
        page.locator('.recipe-row a[aria-label$=" bearbeiten"]').click()
        back = page.get_by_role('link', name='Zur Liste der Rezepte', exact=True).get_attribute('href')
        assert back and 'BFKlemme' in back and 'page=2' in back
        page.locator('.admin-compact-toolbar [data-semantic="actions.archive"]').click()
        page.get_by_role('button', name='Archivieren', exact=True).click()
        page.goto(base + back, wait_until='load')
        query = parse_qs(urlsplit(page.url).query)
        assert query.get('q') == ['BFKlemme'] and query.get('page') == ['2']
        expect(page.locator('.recipe-row')).to_have_count(50)
        expect(page.locator('.recipe-row', has_text='BFKlemme 050')).to_have_count(0)
        expect(page.locator('[data-empty-kind]')).to_have_count(0)
        expect(page.locator('nav[aria-label="Rezeptseiten"]')).to_have_count(0)
    finally:
        context.close()
