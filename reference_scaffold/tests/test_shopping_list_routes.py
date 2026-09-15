"""HTTP contracts for the shopping-list admin routes (MP-REC-SHOPPING-PERSIST, SP-UI).

Real Flask test client against the same PostgreSQL fixtures as the store's own
``test_shopping_list_db.py`` (``store``, real bound recipe/component helpers).
"""
from __future__ import annotations

from html.parser import HTMLParser

import pytest
from sqlalchemy import event, text

import cafeteria
from cafeteria import roles
from cafeteria.shopping_list_store import add_manual_item, compute_revision, create_shopping_list, update_manual_item
from prepared_food_fixtures import food_payload, update_food
from test_shopping_list_db import (  # noqa: F401
    _bound_component, _compute, _ingredient, _item_public, _scope, app_engine, create_food,
    installed_pg16, pg16, seeded_pg16, store,
)

TABLES = ('shopping_lists', 'shopping_list_revisions', 'shopping_list_manual_items', 'shopping_list_line_status')
CSRF = 'sp-ui-routes-csrf'


def _state(owner):
    with owner.connect() as connection:
        return {table: connection.execute(
            text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY 1')
        ).scalars().all() for table in TABLES}


class _Markup(HTMLParser):
    """Attributes by element id, every link target and each select's selected values, from the rendered page."""

    def __init__(self, markup: str) -> None:
        super().__init__()
        self.by_id: dict[str, dict[str, str]] = {}
        self.links: list[str] = []
        self.selected: dict[str, list[str]] = {}
        self._select = ''
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attributes = {name: value or '' for name, value in attrs}
        if 'id' in attributes:
            self.by_id[attributes['id']] = attributes
        if tag == 'a' and 'href' in attributes:
            self.links.append(attributes['href'])
        if tag == 'select':
            self._select = attributes.get('id', '')
        if tag == 'option' and 'selected' in attributes:
            self.selected.setdefault(self._select, []).append(attributes.get('value', ''))


def _assert_field_error(markup: _Markup, element_id: str, value: str | None = None) -> None:
    element = markup.by_id[element_id]
    assert 'is-invalid' in element['class'].split() and element.get('aria-invalid') == 'true', element
    assert f'{element_id}-error' in element.get('aria-describedby', '').split(), element
    assert f'{element_id}-error' in markup.by_id and f'#{element_id}' in markup.links
    if value is not None:
        assert element['value'] == value


@pytest.fixture
def client(store, monkeypatch, tmp_path):  # noqa: F811
    owner, engine, ids = store
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda app: None)
    application = cafeteria.create_app()
    application.config.update(TESTING=True, SECRET_KEY='sp-ui-routes-test', LAST_GOOD_DIR=str(tmp_path))
    application.extensions['cafeteria_db'] = engine
    application.extensions['cafeteria_auth_issuer_db'] = engine
    test_client = application.test_client()
    with test_client.session_transaction() as session:
        session['user'] = {'id': ids['actor'], 'name': 'Küche Test'}
        session['authz_version'] = ids['authz']
        session['_csrf_token'] = CSRF
    return owner, engine, test_client, ids


def test_capabilities_enforce_read_and_write(client, monkeypatch):
    owner, engine, test_client, ids = client
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', set())
    assert test_client.get('/admin/einkaufslisten').status_code == 403
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    assert test_client.get('/admin/einkaufslisten').status_code == 200
    before = _state(owner)
    response = test_client.post('/admin/einkaufslisten', data={'_csrf': CSRF, 'title': 'Verboten'})
    assert response.status_code == 403
    assert _state(owner) == before


def test_csrf_missing_on_create_is_400_and_writes_nothing(client):
    owner, engine, test_client, ids = client
    before = _state(owner)
    response = test_client.post('/admin/einkaufslisten', data={'title': 'Ohne CSRF'})
    assert response.status_code == 400
    assert _state(owner) == before


def test_get_routes_write_nothing(client):
    owner, engine, test_client, ids = client
    list_id = create_shopping_list(engine, _scope(ids), title='Lesetest')
    before = _state(owner)
    assert test_client.get('/admin/einkaufslisten').status_code == 200
    assert test_client.get(f'/admin/einkaufslisten/{list_id}').status_code == 200
    assert _state(owner) == before


def test_create_persists_and_redirects_to_detail(client):
    owner, engine, test_client, ids = client
    before = _state(owner)
    response = test_client.post('/admin/einkaufslisten', data={
        '_csrf': CSRF, 'title': 'Neue Liste', 'note': 'Testnotiz', 'menu_week_public_id': '',
    })
    assert response.status_code == 303
    assert response.location.startswith('/admin/einkaufslisten/')
    after = _state(owner)
    assert len(after['shopping_lists']) == len(before['shopping_lists']) + 1
    detail = test_client.get(response.location)
    assert detail.status_code == 200 and 'Neue Liste' in detail.text and 'Testnotiz' in detail.text


def test_create_validation_error_preserves_note_and_writes_nothing(client):
    owner, engine, test_client, ids = client
    before = _state(owner)
    response = test_client.post('/admin/einkaufslisten', data={
        '_csrf': CSRF, 'title': '', 'note': 'Mein unveröffentlichter Text bleibt erhalten',
    })
    assert response.status_code == 400
    assert 'Mein unveröffentlichter Text bleibt erhalten' in response.text
    _assert_field_error(_Markup(response.text), 'title', '')
    assert _state(owner) == before


def test_compute_conflict_on_stale_row_version_reloads_and_writes_nothing(client):
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    item_public = _item_public(owner, ids['item'])
    list_id = create_shopping_list(engine, _scope(ids), title='Konflikt')
    before = _state(owner)
    response = test_client.post(f'/admin/einkaufslisten/{list_id}/berechnen', data={
        '_csrf': CSRF, 'row_version': '999', 'policy': 'leaf',
        'menu_week_public_id': '', 'component_ids': f'{item_public}:1',
    })
    assert response.status_code == 409
    assert 'zwischenzeitlich geändert' in response.text
    assert _state(owner) == before


def test_compute_without_selection_is_400_with_preserved_week(client):
    owner, engine, test_client, ids = client
    with owner.connect() as connection:
        week_public = str(connection.execute(
            text('SELECT public_id FROM cafeteria.menu_weeks WHERE id=:week'), ids,
        ).scalar_one())
    list_id = create_shopping_list(engine, _scope(ids), title='Ohne Auswahl')
    before = _state(owner)
    response = test_client.post(f'/admin/einkaufslisten/{list_id}/berechnen', data={
        '_csrf': CSRF, 'row_version': '1', 'policy': 'leaf', 'menu_week_public_id': week_public,
    })
    assert response.status_code == 400
    assert 'Mindestens ein Baustein' in response.text
    assert _state(owner) == before


def test_manual_item_add_check_and_delete(client):
    owner, engine, test_client, ids = client
    list_id = create_shopping_list(engine, _scope(ids), title='Manuell')
    response = test_client.post(f'/admin/einkaufslisten/{list_id}/positionen', data={
        '_csrf': CSRF, 'item_text': 'Servietten', 'quantity': '2', 'unit_code': 'STK',
    })
    assert response.status_code == 303
    detail = test_client.get(f'/admin/einkaufslisten/{list_id}')
    assert 'Servietten' in detail.text
    with owner.connect() as connection:
        item_public = str(connection.execute(
            text("SELECT public_id FROM cafeteria.shopping_list_manual_items WHERE item_text='Servietten'"),
        ).scalar_one())
    checked = test_client.post(
        f'/admin/einkaufslisten/{list_id}/positionen/{item_public}',
        data={'_csrf': CSRF, 'action': 'check', 'expected_row_version': '1', 'item_text': '', 'quantity': '', 'unit_code': ''},
    )
    assert checked.status_code == 303
    with owner.connect() as connection:
        assert connection.execute(
            text('SELECT checked, row_version FROM cafeteria.shopping_list_manual_items WHERE public_id=CAST(:id AS uuid)'),
            {'id': item_public},
        ).one() == (True, 2)
    before = _state(owner)
    deleted = test_client.post(
        f'/admin/einkaufslisten/{list_id}/positionen/{item_public}',
        data={'_csrf': CSRF, 'action': 'delete', 'expected_row_version': '2', 'item_text': '', 'quantity': '', 'unit_code': ''},
    )
    assert deleted.status_code == 303
    after = _state(owner)
    assert len(after['shopping_list_manual_items']) == len(before['shopping_list_manual_items']) - 1


def test_manual_item_check_or_delete_with_stale_row_version_is_409_with_reloaded_state(client):
    owner, engine, test_client, ids = client
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Positionskonflikt')
    item = add_manual_item(engine, scope, list_id, item_text='Becher')
    update_manual_item(engine, scope, list_id, item, expected_row_version=1, item_text='Tassen')
    before = _state(owner)
    for action in ('check', 'uncheck', 'delete'):
        response = test_client.post(f'/admin/einkaufslisten/{list_id}/positionen/{item}', data={
            '_csrf': CSRF, 'action': action, 'expected_row_version': '1', 'item_text': 'Becher', 'quantity': '', 'unit_code': '',
        })
        assert response.status_code == 409, action
        assert 'zwischenzeitlich geändert' in response.text
        assert _Markup(response.text).by_id[f'item-text-{item}']['value'] == 'Tassen'
        assert _state(owner) == before


def test_detail_reads_captured_names_from_the_snapshot_with_constant_query_count(client):
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    letters = 'ABCDEFGHIJKLMNOPQRST'
    foods = [create_food(engine, ids, f'Zutat {letter}') for letter in letters]
    _bound_component(owner, engine, ids, [_ingredient(food, '10', 'G') for food in foods], sort_order=1, label='Zwanzig')
    _bound_component(owner, engine, ids, [_ingredient(foods[0], '10', 'G')], sort_order=2, label='Eine')
    item_public, scope = _item_public(owner, ids['item']), _scope(ids)
    one = create_shopping_list(engine, scope, title='Eine Zeile')
    compute_revision(engine, scope, one, component_ids=[f'{item_public}:2'], policy='leaf', expected_row_version=1)
    twenty = create_shopping_list(engine, scope, title='Zwanzig Zeilen')
    compute_revision(engine, scope, twenty, component_ids=[f'{item_public}:1'], policy='leaf', expected_row_version=1)
    statements: list[str] = []

    def count(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def page(list_id):
        statements.clear()
        event.listen(engine, 'before_cursor_execute', count)
        try:
            response = test_client.get(f'/admin/einkaufslisten/{list_id}')
        finally:
            event.remove(engine, 'before_cursor_execute', count)
        assert response.status_code == 200
        return response.text, len(statements)

    page(one)  # warm per-process caches so both measured requests take the same path
    single, single_count = page(one)
    many, many_count = page(twenty)
    assert single_count == many_count, (single_count, many_count)
    assert all(f'Zutat {letter}' in many for letter in letters)
    assert '10 Gramm' in single and not any('FROM cafeteria.foods' in statement for statement in statements)


def test_older_revision_shows_its_own_lines_read_only_after_a_food_rename(client):
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    food = create_food(engine, ids, 'Mehl vorher')
    _bound_component(owner, engine, ids, [_ingredient(food, '250', 'G')])
    list_id = create_shopping_list(engine, _scope(ids), title='Belegansicht')
    revision_1 = _compute(engine, ids, list_id)
    update_food(engine, ids, food, food_payload(ids, 'Mehl nachher'))
    _compute(engine, ids, list_id, expected_row_version=2)
    before = _state(owner)
    old = test_client.get(f'/admin/einkaufslisten/{list_id}?revision={revision_1}')
    assert old.status_code == 200 and _state(owner) == before
    assert 'Mehl vorher' in old.text and 'Mehl nachher' not in old.text and '250 Gramm' in old.text
    assert 'Beleg vom' in old.text and 'nicht aktuell' in old.text
    assert 'name="line_key"' not in old.text and '/berechnen' not in old.text and 'name="action"' not in old.text
    latest = test_client.get(f'/admin/einkaufslisten/{list_id}')
    assert 'Mehl nachher' in latest.text and 'name="line_key"' in latest.text and 'nicht aktuell' not in latest.text
    unknown = test_client.get(f'/admin/einkaufslisten/{list_id}?revision=11111111-1111-4111-8111-111111111111')
    assert unknown.status_code == 404


def test_manual_item_validation_marks_the_field_links_the_summary_and_keeps_inputs(client):
    owner, engine, test_client, ids = client
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Feldfehler')
    item = add_manual_item(engine, scope, list_id, item_text='Becher')
    before = _state(owner)
    created = test_client.post(f'/admin/einkaufslisten/{list_id}/positionen', data={
        '_csrf': CSRF, 'item_text': 'Servietten', 'quantity': 'viele', 'unit_code': 'STK',
    })
    assert created.status_code == 400 and _state(owner) == before
    markup = _Markup(created.text)
    _assert_field_error(markup, 'new-item-qty', 'viele')
    assert markup.by_id['new-item-text']['value'] == 'Servietten' and 'is-invalid' not in markup.by_id['new-item-text']['class']
    assert markup.selected['new-item-unit'] == ['STK']
    updated = test_client.post(f'/admin/einkaufslisten/{list_id}/positionen/{item}', data={
        '_csrf': CSRF, 'action': 'save', 'expected_row_version': '1', 'item_text': 'Tassen', 'quantity': '2', 'unit_code': '',
    })
    assert updated.status_code == 400 and _state(owner) == before
    markup = _Markup(updated.text)
    _assert_field_error(markup, f'item-unit-{item}')
    assert markup.by_id[f'item-text-{item}']['value'] == 'Tassen' and markup.by_id[f'item-qty-{item}']['value'] == '2'


def test_compute_selection_error_is_marked_on_the_components(client):
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    _bound_component(owner, engine, ids, [_ingredient(create_food(engine, ids, 'Zutat'), '100', 'G')])
    with owner.connect() as connection:
        week_public = str(connection.execute(text('SELECT public_id FROM cafeteria.menu_weeks WHERE id=:week'), ids).scalar_one())
    list_id = create_shopping_list(engine, _scope(ids), title='Auswahlfehler')
    before = _state(owner)
    response = test_client.post(f'/admin/einkaufslisten/{list_id}/berechnen', data={
        '_csrf': CSRF, 'row_version': '1', 'policy': 'prepared', 'menu_week_public_id': week_public,
    })
    assert response.status_code == 400 and _state(owner) == before
    markup = _Markup(response.text)
    _assert_field_error(markup, 'component_ids')
    assert markup.by_id['policy-prepared'].get('checked') == ''


def test_foreign_active_location_is_404(client):
    owner, engine, test_client, ids = client
    list_id = create_shopping_list(engine, _scope(ids), title='Fremdstandort')
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false WHERE id=:location'), ids)
        connection.execute(text('UPDATE cafeteria.locations SET active=true WHERE id=:other_location'), ids)
    response = test_client.get(f'/admin/einkaufslisten/{list_id}')
    assert response.status_code == 404


def test_archive_requires_cas_and_marks_the_row_archived(client):
    owner, engine, test_client, ids = client
    list_id = create_shopping_list(engine, _scope(ids), title='Archivbeispiel')
    before = _state(owner)
    stale = test_client.post(f'/admin/einkaufslisten/{list_id}/archivieren', data={'_csrf': CSRF, 'row_version': '999'})
    assert stale.status_code == 409
    assert _state(owner) == before
    response = test_client.post(f'/admin/einkaufslisten/{list_id}/archivieren', data={'_csrf': CSRF, 'row_version': '1'})
    assert response.status_code == 303
    default_view = test_client.get('/admin/einkaufslisten')
    assert 'Archivbeispiel' not in default_view.text
    archived_view = test_client.get('/admin/einkaufslisten?archived=1')
    assert 'Archivbeispiel' in archived_view.text and 'Archiviert</span>' in archived_view.text
    with owner.connect() as connection:
        assert connection.execute(
            text('SELECT archived_at IS NOT NULL FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid)'),
            {'id': list_id},
        ).scalar_one() is True
