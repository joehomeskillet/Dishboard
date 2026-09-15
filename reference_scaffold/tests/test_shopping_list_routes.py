"""HTTP contracts for the shopping-list admin routes (MP-REC-SHOPPING-PERSIST, SP-UI).

Real Flask test client against the same PostgreSQL fixtures as the store's own
``test_shopping_list_db.py`` (``store``, real bound recipe/component helpers).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

import cafeteria
from cafeteria import roles
from cafeteria.shopping_list_store import create_shopping_list
from test_shopping_list_db import (  # noqa: F401
    _bound_component, _ingredient, _item_public, _scope, app_engine, create_food,
    installed_pg16, pg16, seeded_pg16, store,
)

TABLES = ('shopping_lists', 'shopping_list_revisions', 'shopping_list_manual_items', 'shopping_list_line_status')
CSRF = 'sp-ui-routes-csrf'


def _state(owner):
    with owner.connect() as connection:
        return {table: connection.execute(
            text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY 1')
        ).scalars().all() for table in TABLES}


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
        data={'_csrf': CSRF, 'action': 'check', 'item_text': '', 'quantity': '', 'unit_code': ''},
    )
    assert checked.status_code == 303
    with owner.connect() as connection:
        assert connection.execute(
            text('SELECT checked FROM cafeteria.shopping_list_manual_items WHERE public_id=CAST(:id AS uuid)'),
            {'id': item_public},
        ).scalar_one() is True
    before = _state(owner)
    deleted = test_client.post(
        f'/admin/einkaufslisten/{list_id}/positionen/{item_public}',
        data={'_csrf': CSRF, 'action': 'delete', 'item_text': '', 'quantity': '', 'unit_code': ''},
    )
    assert deleted.status_code == 303
    after = _state(owner)
    assert len(after['shopping_list_manual_items']) == len(before['shopping_list_manual_items']) - 1


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
