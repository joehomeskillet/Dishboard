"""Real PostgreSQL and native HTTP contracts for the privately wired A2 slice."""
import pytest
import io
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict

from cafeteria import roles
from cafeteria.admin import recipe_routes as routes
from test_master_data_routes import (  # noqa: F401
    Forms, app_engine, b3 as b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_forms import form_values
from test_recipe_store_db import line, payload, snapshot, target, mutable, complete_line, STORAGE_PUBLIC_ID
from test_master_data_db import signed_in
from test_recipe_image_identity_db import attach


def fields(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return parsed(response, path)


def parsed(response, path):
    data = Forms(response.text).forms[path]
    # HTML parsing consumes the first LF immediately after a textarea start tag.
    for key in ('description', *[key for key in data if key.endswith('.instruction')]):
        if key in data:
            data[key] = data[key].removeprefix('\n')
    return data


def create(client, title='Suppe'):
    path = '/admin/rezepte/neu'
    original = fields(client, path)
    data = form_values()
    data['_csrf'], data['_form_context'] = original['_csrf'], original['_form_context']
    data['title'] = title
    response = client.post(path, data=data)
    assert response.status_code == 303, response.text
    return response.location


def test_create_read_update_noop_archive_reactivate(b3):
    _, owner, client, _ = b3
    before = snapshot(owner)
    assert client.get('/admin/rezepte').status_code == 200
    assert client.get('/admin/rezepte/neu').status_code == 200
    assert snapshot(owner) == before
    path = create(client)
    original = fields(client, path)
    assert original['ingredients.0.line_public_id']
    before = snapshot(owner)
    assert client.post(path, data=original).status_code == 303
    assert snapshot(owner) == before
    original['title'] = 'Neue Suppe'
    assert client.post(path, data=original).status_code == 303
    changed = fields(client, path)
    assert changed['row_version'] == '2'
    assert changed['ingredients.0.line_public_id'] == original['ingredients.0.line_public_id']
    status = fields(client, path + '/status')
    before = snapshot(owner)
    assert client.get(path).status_code == 200  # cancel is only a GET
    assert snapshot(owner) == before
    assert client.post(path + '/status', data=status).status_code == 303
    assert 'Neue Suppe' not in client.get('/admin/rezepte').text
    assert 'Neue Suppe' in client.get('/admin/rezepte?archived=1').text
    assert 'Rezept speichern' not in client.get(path).text
    assert client.post(path + '/status', data=fields(client, path + '/status')).status_code == 303
    assert fields(client, path)['row_version'] == '4'


def test_native_rows_preserve_original_values_identity_and_database(b3):
    _, owner, client, _ = b3
    path = create(client)
    data = fields(client, path)
    original = data.copy()
    data['description'] = '\nNicht gespeichert\nZweite Zeile'
    data['steps.0.instruction'] = '\n'
    before = snapshot(owner)
    for operation, index in [('add', 0), ('up', 1), ('down', 0), ('remove', 0)]:
        response = client.post('/admin/rezepte/formular', query_string={
            'action': 'recipe.update', 'recipe_id': path.rsplit('/', 1)[1],
            'row_kind': 'ingredients', 'row_action': operation, 'row_index': index}, data=data)
        assert response.status_code == 200, response.text
        data = parsed(response, path)
        assert data['_form_context'] == original['_form_context']
        assert data['row_version'] == original['row_version']
        assert data['description'] == '\nNicht gespeichert\nZweite Zeile'
        assert data['steps.0.instruction'] == '\n'
        assert snapshot(owner) == before
    assert data['ingredients.0.line_public_id'] == original['ingredients.0.line_public_id']


@pytest.mark.parametrize('query', ['page=0', 'page=1&page=2', 'q=a&q=b', 'archived=true', 'profile=patient'])
def test_strict_list_queries(b3, query):
    assert b3[2].get('/admin/rezepte?' + query).status_code == 400


def test_stale_cas_and_scope_preserve_form_without_post_signing(b3, monkeypatch):
    _, owner, client, _ = b3
    path = create(client)
    stale = fields(client, path)
    fresh = stale.copy()
    fresh['title'] = 'Erste Sitzung'
    assert client.post(path, data=fresh).status_code == 303
    stale['description'] = '\nOriginal\nZweite Zeile'
    before = snapshot(owner)
    response = client.post(path, data=stale)
    assert response.status_code == 409 and response.headers['Cache-Control'] == 'no-store'
    assert stale['_form_context'] in response.text and '\n\nOriginal\nZweite Zeile' in response.text
    assert snapshot(owner) == before
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Anderes Haus',true)"))
    def forbidden(*args, **kwargs):
        pytest.fail('Changed location must not load choices or sign again')
    monkeypatch.setattr(routes, '_choices', forbidden)
    monkeypatch.setattr(routes.forms, 'sign_context', forbidden)
    before = snapshot(owner)
    response = client.post(path, data=stale)
    assert response.status_code == 409 and stale['_form_context'] in response.text
    assert snapshot(owner) == before


def test_authorization_csrf_ambiguous_rows_and_db_free_outage(b3, monkeypatch):
    app, owner, client, _ = b3
    path = create(client)
    data = fields(client, path)
    before = snapshot(owner)
    invalid = MultiDict(data)
    invalid['_csrf'] = 'wrong'
    assert client.post(path, data=invalid).status_code == 400
    invalid = MultiDict(data)
    invalid.add('title', 'Doppelt')
    assert client.post(path, data=invalid).status_code == 400
    invalid = MultiDict(data)
    invalid['row_kind'] = 'ingredients'
    assert client.post('/admin/rezepte/formular?action=recipe.update&row_kind=ingredients&row_action=add&row_index=0', data=invalid).status_code == 400
    assert snapshot(owner) == before
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    assert client.get(path).status_code == 200
    assert client.get(path + '/status').status_code == 403
    assert client.post(path, data=data).status_code == 403
    assert app.test_client().get('/admin/rezepte').status_code == 401
    def unavailable(*args, **kwargs):
        raise OperationalError('private', {}, RuntimeError('hidden'))
    monkeypatch.setattr(roles, 'load_user_authorization', unavailable)
    response = client.get('/admin/rezepte')
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'hidden' not in response.text


def test_literal_search_full_pagination_and_missing_object(b3):
    _, owner, client, actor = b3
    create(client, 'Vorlage')
    with owner.begin() as connection:
        connection.execute(text('''INSERT INTO cafeteria.recipes
            (location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
            SELECT location_id,:actor,:actor,'Rezept '||lpad(n::text,3,'0'),servings,servings_unit_id,'manual'
            FROM cafeteria.recipes CROSS JOIN generate_series(1,51) n'''), {'actor': actor.user_id})
    before = snapshot(owner)
    page = client.get('/admin/rezepte?q=Rezept')
    assert page.status_code == 200 and page.text.count('class="card recipe-card"') == 50
    page = client.get('/admin/rezepte?q=Rezept&page=2')
    assert page.status_code == 200 and 'Rezept 051' in page.text
    assert page.text.count('class="card recipe-card"') == 1
    assert 'Keine passenden Rezepte' in client.get('/admin/rezepte?q=%25').text
    assert client.get('/admin/rezepte/not-a-uuid').status_code == 404
    assert snapshot(owner) == before


def test_image_caption_step_binding_and_removal_preserve_history(b3):
    app, owner, client, actor = b3
    path = create(client)
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        row = routes.store.get_recipe(engine, path.rsplit('/', 1)[1])
        attach(engine, actor, row)
    data = fields(client, path)
    image_hash = data['images.0.sha256']
    data['images.0.caption'] = 'Fertige Suppe'
    data['steps.0.image_sha256'] = image_hash
    assert client.post(path, data=data).status_code == 303
    with signed_in(engine, actor):
        row = routes.store.get_recipe(engine, path.rsplit('/', 1)[1])
        location = routes.store.get_location(engine)
        complete = mutable(row.payload)
        complete['ingredients'] = [complete_line(engine, actor)]
        row = routes.store.update_recipe(engine, actor, target(row), complete, expected_location_id=location)
        preview = routes.store.get_dependency_preview(engine, target(row), expected_location_id=location)
        routes.store.freeze_revision(engine, actor, target(row), expected_location_id=location,
                                     expected_dependency_hash=preview.dependency_hash_sha256)
    data = fields(client, path)
    before = snapshot(owner)
    response = client.post('/admin/rezepte/formular', query_string={
        'action': 'recipe.update', 'recipe_id': path.rsplit('/', 1)[1],
        'row_kind': 'images', 'row_action': 'remove', 'row_index': '0'}, data=data)
    assert response.status_code == 200, response.text
    data = parsed(response, path)
    assert data['steps.0.image_sha256'] == image_hash
    assert 'images.0.sha256' not in data and snapshot(owner) == before
    conflict = client.post(path, data=data)
    assert conflict.status_code == 409
    assert 'Fertige Suppe' in conflict.text
    assert snapshot(owner) == before
    data['steps.0.image_sha256'] = ''
    assert client.post(path, data=data).status_code == 303
    after = snapshot(owner)
    assert after['recipe_revisions'] == before['recipe_revisions']
    assert after['recipe_assets'] == before['recipe_assets']
    with signed_in(engine, actor):
        assert routes.store.get_recipe_asset(engine, path.rsplit('/', 1)[1], image_hash).data


def test_sixty_four_rows_source_and_unknown_selection_roundtrip(b3):
    _, owner, client, _ = b3
    original = fields(client, '/admin/rezepte/neu')
    data = form_values()
    data['_csrf'], data['_form_context'] = original['_csrf'], original['_form_context']
    data['source.kind'] = 'url'
    data['source.reference'] = 'Originalbeleg'
    data['source.url'] = 'https://example.test/rezept'
    data['source.fetched_at'] = '2026-09-07T10:00:00+02:00'
    line = {key: value for key, value in data.items() if key.startswith('ingredients.0.')}
    for index in range(1, 64):
        for key, value in line.items():
            data[key.replace('.0.', f'.{index}.')] = value
    response = client.post('/admin/rezepte/neu', data=data)
    assert response.status_code == 303, response.text
    path = response.location
    data = fields(client, path)
    assert sum(key.endswith('.line_public_id') for key in data) == 64
    before = snapshot(owner)
    row_query = {'action': 'recipe.update', 'recipe_id': path.rsplit('/', 1)[1],
                 'row_kind': 'ingredients', 'row_action': 'add', 'row_index': '64'}
    assert client.post('/admin/rezepte/formular', query_string=row_query, data=data).status_code == 400
    assert snapshot(owner) == before
    data['tag_public_ids'] = '00000000-0000-0000-0000-000000000123'
    response = client.post('/admin/rezepte/formular', query_string=row_query | {'row_action': 'up', 'row_index': '1'}, data=data)
    assert response.status_code == 200, response.text
    retained = parsed(response, path)
    assert retained.getlist('tag_public_ids') == data.getlist('tag_public_ids')
    assert retained['source.reference'] == 'Originalbeleg'
    assert retained['_form_context'] == data['_form_context']
    assert snapshot(owner) == before


def test_stale_row_action_does_not_restore_editable_archived_state(b3):
    _, owner, client, _ = b3
    path = create(client)
    stale = fields(client, path)
    assert client.post(path + '/status', data=fields(client, path + '/status')).status_code == 303
    before = snapshot(owner)
    response = client.post('/admin/rezepte/formular', query_string={
        'action': 'recipe.update', 'recipe_id': path.rsplit('/', 1)[1],
        'row_kind': 'ingredients', 'row_action': 'add', 'row_index': '1'}, data=stale)
    assert response.status_code == 409
    assert stale['_form_context'] in response.text and snapshot(owner) == before


def test_maximum_aggregate_get_signing_preserves_all_values_with_bounded_names(b3):
    app, owner, client, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        ingredients, tags, selected_names = [], [], {}
        for index in range(65):
            code, name = f'R{index}', f'Einheit {index}'
            routes.masters.create_unit(engine, actor, code=code, display_name=name, dimension='count', base_factor='1')
            selected_names[code] = name
        for index in range(64):
            food = routes.masters.create_food(engine, actor, {'name': f'Zutat {index}', 'base_unit_code': 'G',
                'storage_location_public_ids': [STORAGE_PUBLIC_ID]})
            tag = routes.masters.create_vocabulary(engine, 'tag', actor, code=f'R{index}', name=f'Tag {index}')
            selected_names[food.public_id], selected_names[tag.public_id] = f'Zutat {index}', f'Tag {index}'
            ingredients.append(line(f'Zutat {index}', food_public_id=food.public_id, unit_code=f'R{index}'))
            tags.append(tag.public_id)
        complete = payload(servings_unit_code='R64', ingredients=ingredients, tag_public_ids=tags,
                           steps=[{'instruction': f'Schritt {index}', 'duration_minutes': None, 'image_sha256': None}
                                  for index in range(64)])
        row = routes.store.create_recipe(engine, actor, complete, expected_location_id=routes.store.get_location(engine))
        for index in range(64):
            stream = io.BytesIO()
            Image.new('RGB', (2, 2), (index, 40, 50)).save(stream, format='PNG')
            row = routes.store.add_recipe_image(engine, actor, target(row), data=stream.getvalue(),
                content_type='image/png', caption=f'Bild {index}', expected_location_id=routes.store.get_location(engine))
    before = snapshot(owner)
    data = fields(client, '/admin/rezepte/' + row.public_id)
    canonical = routes.forms.parse_recipe_form(data)
    assert all(len(canonical[kind]) == 64 for kind in ('ingredients', 'steps', 'images', 'tag_public_ids'))
    with app.test_request_context():
        signed = routes.forms._signer().loads(data['_form_context'])
    assert len(signed['labels']) == 256
    assert all(signed['labels'][key] == name for key, name in selected_names.items())
    assert len([key for key in signed['labels'] if len(key) == 64]) == 63
    assert snapshot(owner) == before
