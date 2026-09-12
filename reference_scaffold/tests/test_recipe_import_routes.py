"""HTTP contracts for recipe-import preview: CSRF, no-store, 409, NoJS."""
from __future__ import annotations

from io import BytesIO
from urllib.parse import urlsplit

from sqlalchemy import text

from cafeteria import master_data_store as masters
from cafeteria import roles
from test_master_data_db import STORAGE_PUBLIC_ID, make_actor, signed_in
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


def test_commit_creates_recipe_link_and_rejects_editor(b3):  # noqa: F811
    app, owner, client, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        food = masters.create_food(engine, actor, {
            'name': 'HTTP-Zutat', 'base_unit_code': 'KG',
            'storage_location_public_ids': [STORAGE_PUBLIC_ID],
        })
    path = create(client, annotation='unreviewed')
    form = Forms(client.get(path).text).forms[path]
    form['row.1.ingredient.0.food_public_id'] = food.public_id
    form['row.1.duplicate_decision'] = 'create_new'
    form['action'] = 'save'
    assert client.post(path, data=form).status_code == 303
    ack = Forms(client.get(path).text).forms[path]
    ack['action'] = 'acknowledge'
    assert client.post(path, data=ack).status_code == 303
    detail = client.get(path)
    assert detail.status_code == 200
    assert 'Importstapel übernehmen' in detail.text
    assert 'keine Veröffentlichung' in detail.text
    commit_path = f'{path}/commit'
    commit_form = Forms(detail.text).forms[commit_path]
    invalid = dict(commit_form)
    invalid['_csrf'] = 'wrong'
    before = snapshot(owner)
    assert client.post(commit_path, data=invalid).status_code == 400
    assert snapshot(owner) == before
    assert client.post(commit_path, data=commit_form).status_code == 303
    imported = client.get(path)
    assert imported.status_code == 200
    assert 'Rezept öffnen' in imported.text
    assert 'imported' in imported.text
    assert client.post(commit_path, data=commit_form).status_code == 409
    href = [line for line in imported.text.split('"') if line.startswith('/admin/rezepte/')]
    recipe_href = next(item for item in href if item.count('/') == 3 and 'import' not in item)
    assert client.get(recipe_href).status_code == 200
    editor = make_actor(owner, 'Cafeteria.Editor')
    other = app.test_client()
    with other.session_transaction() as session:
        session['user'] = {'id': editor.user_id, 'name': 'Editor'}
        session['authz_version'] = editor.authz_version
        session['_csrf_token'] = 'b3-test-csrf'
    path2 = create(client, annotation='unreviewed')
    save = Forms(client.get(path2).text).forms[path2]
    save['row.1.ingredient.0.food_public_id'] = food.public_id
    save['row.1.duplicate_decision'] = 'create_new'
    save['action'] = 'save'
    assert client.post(path2, data=save).status_code == 303
    ack2 = Forms(client.get(path2).text).forms[path2]
    ack2['action'] = 'acknowledge'
    assert client.post(path2, data=ack2).status_code == 303
    editor_page = other.get(path2)
    assert editor_page.status_code == 200
    assert 'Berechtigung zum Rezeptimport' in editor_page.text
    assert other.post(f'{path2}/commit', data={
        '_csrf': 'b3-test-csrf',
        'row_version': Forms(editor_page.text).forms[path2]['row_version'],
        'candidate_hash_sha256': '0' * 64,
    }).status_code == 403
