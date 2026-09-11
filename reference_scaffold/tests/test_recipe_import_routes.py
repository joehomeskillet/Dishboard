"""HTTP contracts for recipe-import preview: CSRF, no-store, 409, NoJS."""
from __future__ import annotations

from io import BytesIO
from urllib.parse import urlsplit

from sqlalchemy import text

from cafeteria import roles
from test_master_data_routes import (  # noqa: F401
    Forms, app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_import import json_bytes, recipe


def snapshot(owner):
    with owner.connect() as connection:
        return {
            table: connection.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
            )).all()
            for table in ('recipe_import_batches', 'recipe_import_candidates', 'recipes', 'audit_events')
        }


def upload_fields(client, **extra):
    response = client.get('/admin/rezepte/import')
    assert response.status_code == 200, response.text
    assert response.headers['Cache-Control'] == 'no-store'
    form = Forms(response.text).forms['/admin/rezepte/import']
    form['source_file'] = (BytesIO(json_bytes(recipe())), 'rezepte.json')
    form.update(extra)
    return form


def create(client, **extra):
    response = client.post('/admin/rezepte/import', data=upload_fields(client, **extra))
    assert response.status_code == 303, response.text
    return urlsplit(response.headers['Location']).path


def test_get_is_no_store_and_write_free(b3):  # noqa: F811
    _, owner, client, _ = b3
    before = snapshot(owner)
    response = client.get('/admin/rezepte/import')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'Noch keine Importstapel' in response.text
    assert snapshot(owner) == before


def test_upload_creates_draft_without_recipes(b3):  # noqa: F811
    _, owner, client, _ = b3
    before = snapshot(owner)
    path = create(client, annotation='unreviewed')
    assert '/admin/rezepte/import/' in path
    detail = client.get(path)
    assert detail.status_code == 200
    assert detail.headers['Cache-Control'] == 'no-store'
    assert 'ungeprüft' in detail.text
    assert 'Kartoffelsuppe' in detail.text
    assert snapshot(owner)['recipes'] == before['recipes']
    assert snapshot(owner)['recipe_import_batches']


def test_csrf_conflict_and_capability(b3, monkeypatch):  # noqa: F811
    app, owner, client, _ = b3
    data = upload_fields(client)
    before = snapshot(owner)
    invalid = dict(data)
    invalid['_csrf'] = 'wrong'
    assert client.post('/admin/rezepte/import', data=invalid).status_code == 400
    assert snapshot(owner) == before
    path = create(client)
    stale = Forms(client.get(path).text).forms[path]
    fresh = Forms(client.get(path).text).forms[path]
    fresh['row.1.title'] = 'Erste Sitzung'
    assert client.post(path, data=fresh).status_code == 303
    stale['row.1.title'] = 'Zweite Sitzung'
    conflict = client.post(path, data=stale)
    assert conflict.status_code == 409
    assert conflict.headers['Cache-Control'] == 'no-store'
    assert 'Zweite Sitzung' in conflict.text
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    assert client.get('/admin/rezepte/import').status_code == 403
    assert client.post(path, data=stale).status_code == 403
    assert app.test_client().get('/admin/rezepte/import').status_code == 401
