"""Real PG authorization, original form expectations and mutation-free row recovery."""
import pytest
from flask import jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict

from cafeteria import recipe_store as store, roles
from cafeteria.admin import recipe_forms as forms
from cafeteria.admin.recipe_errors import protected
from cafeteria.admin.recipe_form_rows import apply_row_action
from cafeteria.master_data_types import ObjectExpectation
from test_master_data_routes import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, b3,
)
from test_recipe_store_db import snapshot
from test_recipe_forms import form_values


@pytest.fixture
def harness(b3):  # noqa: F811
    app, owner, client, actor = b3
    @app.context_processor
    def forbidden_context_read():
        raise AssertionError('Recovery must not invoke context processors')
    @app.route('/a1/new', methods=['GET', 'POST'])
    @protected
    def create():
        if request.method == 'GET':
            return jsonify(token=forms.sign_context(action='recipe.create', target=None,
                expected_location_id=store.get_location(app.extensions['cafeteria_db'])))
        expected = forms.read_context(action='recipe.create', target_public_id=None)
        row = store.create_recipe(app.extensions['cafeteria_db'], expected.actor, forms.parse_recipe_form(request.form),
                                  expected_location_id=expected.expected_location_id)
        return jsonify(public_id=row.public_id), 201
    @app.route('/a1/<public_id>', methods=['GET', 'POST'])
    @protected
    def edit(public_id):
        if request.method == 'GET':
            row = store.get_recipe(app.extensions['cafeteria_db'], public_id)
            return jsonify(token=forms.sign_context(action='recipe.update', target=ObjectExpectation(row.public_id, row.row_version),
                expected_location_id=store.get_location(app.extensions['cafeteria_db'])), version=row.row_version)
        expected = forms.read_context(action='recipe.update', target_public_id=public_id)
        row = store.update_recipe(app.extensions['cafeteria_db'], expected.actor, expected.target,
            forms.parse_recipe_form(request.form), expected_location_id=expected.expected_location_id)
        return jsonify(version=row.row_version)
    @app.post('/a1/rows')
    @protected
    def rows():
        return jsonify(list(apply_row_action(request.form, action='recipe.create', target_public_id=None).items(multi=True)))
    @app.post('/a1/<public_id>/rows')
    @protected
    def edit_rows(public_id):
        return jsonify(list(apply_row_action(request.form, action='recipe.update', target_public_id=public_id).items(multi=True)))
    return app, owner, client, actor


def fresh(client):
    token = client.get('/a1/new').json['token']
    data = form_values()
    data['_csrf'] = 'b3-test-csrf'
    data['_form_context'] = token
    return data


def test_real_create_original_cas_and_copyable_conflict(harness):
    _, owner, client, _ = harness
    data = fresh(client)
    created = client.post('/a1/new', data=data)
    assert created.status_code == 201
    path = '/a1/' + created.json['public_id']
    original = client.get(path).json
    data['_form_context'], data['row_version'] = original['token'], str(original['version'])
    data['title'] = 'Anderer Titel'
    assert client.post(path, data=data).status_code == 200
    before = snapshot(owner)
    data['description'] = '\nOriginal\nZweite Zeile'
    response = client.post(path, data=data)
    assert response.status_code == 409 and response.headers['Cache-Control'] == 'no-store'
    assert original['token'] in response.text and '\n\nOriginal\nZweite Zeile' in response.text
    assert 'Ursprüngliche Version' in response.text
    assert snapshot(owner) == before


def test_rows_preserve_incomplete_values_original_context_and_no_write(harness):
    _, owner, client, _ = harness
    data = fresh(client)
    data['steps.0.instruction'] = '\n'
    data.update({'row_kind': 'ingredients', 'row_action': 'add', 'row_index': '0'})
    before = snapshot(owner)
    response = client.post('/a1/rows', data=data)
    assert response.status_code == 200, response.text
    result = MultiDict(response.json)
    assert result['_form_context'] == data['_form_context'] and result['_csrf'] == data['_csrf']
    assert result['ingredients.0.line_public_id'] == '' and result['ingredients.1.ingredient_text'] == 'Karotte'
    assert result['steps.0.instruction'] == '\n'
    result.update({'row_kind': 'ingredients', 'row_action': 'up', 'row_index': '1'})
    response = client.post('/a1/rows', data=result)
    assert MultiDict(response.json)['ingredients.0.ingredient_text'] == 'Karotte'
    assert snapshot(owner) == before


@pytest.mark.parametrize('bad', ['csrf', 'unicode', 'token', 'actor', 'scope'])
def test_bad_context_never_writes_or_rebinds(harness, bad):
    app, owner, client, actor = harness
    data = fresh(client)
    if bad == 'csrf':
        data['_csrf'] = 'wrong'
    elif bad == 'unicode':
        data['_csrf'] = 'ä'
    elif bad == 'token':
        data['_form_context'] += 'tampered'
    elif bad == 'actor':
        with owner.begin() as current:
            current.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
    else:
        with owner.begin() as current:
            current.execute(text('UPDATE cafeteria.locations SET active=false'))
            current.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Anderes Haus',true)"))
    before = snapshot(owner)
    response = client.post('/a1/new', data=data)
    assert response.status_code == (401 if bad == 'actor' else 409 if bad == 'scope' else 400)
    assert snapshot(owner) == before
    if bad == 'scope':
        assert data['_form_context'] in response.text and 'Karotte' in response.text


def test_outage_covers_authorization_without_template_database_recursion(harness, monkeypatch):
    app, _, client, _ = harness
    def offline(*args, **kwargs):
        raise OperationalError('hidden', {}, Exception('secret detail'))
    monkeypatch.setattr(roles, 'load_user_authorization', offline)
    @app.context_processor
    def no_recursion():
        raise AssertionError('DB context called')
    response = client.get('/a1/new')
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'secret detail' not in response.text and 'tabler.min.css' in response.text


def test_real_line_identity_survives_insert_reorder_remove_without_persistence(harness):
    _, owner, client, _ = harness
    original = fresh(client)
    created = client.post('/a1/new', data=original).json['public_id']
    token = client.get('/a1/' + created).json
    with owner.connect() as current:
        stored = current.execute(text('SELECT cafeteria.recipe_payload_v22(id) FROM cafeteria.recipes WHERE public_id=CAST(:id AS uuid)'), {'id': created}).scalar_one()
    data = form_values(stored)
    data['_csrf'], data['_form_context'], data['row_version'] = original['_csrf'], token['token'], str(token['version'])
    line_id = data['ingredients.0.line_public_id']
    before = snapshot(owner)
    for operation, index in [('add', '0'), ('up', '1'), ('remove', '1')]:
        data.update({'row_kind': 'ingredients', 'row_action': operation, 'row_index': index})
        response = client.post('/a1/' + created + '/rows', data=data)
        assert response.status_code == 200, response.text
        data = MultiDict(response.json)
        assert data['_form_context'] == token['token'] and data['row_version'] == str(token['version'])
    assert data['ingredients.0.line_public_id'] == line_id
    assert 'ingredients.1.line_public_id' not in data and snapshot(owner) == before


def test_sixty_four_rows_and_no_post_signing(harness):
    app, owner, client, _ = harness
    data = fresh(client)
    initial = {key: value for key, value in data.items() if key.startswith('ingredients.0.')}
    for index in range(1, 64):
        for key, value in initial.items():
            data[key.replace('.0.', f'.{index}.')] = value
    data.update({'row_kind': 'ingredients', 'row_action': 'add', 'row_index': '64'})
    before = snapshot(owner)
    assert client.post('/a1/rows', data=data).status_code == 400
    assert snapshot(owner) == before
    with app.test_request_context(method='POST'):
        with pytest.raises(forms.FormError):
            forms.sign_context(action='recipe.create', target=None, expected_location_id=1)


def test_capability_and_original_token_action_target_version(harness, monkeypatch):
    _, owner, client, _ = harness
    data = fresh(client)
    created = client.post('/a1/new', data=data).json['public_id']
    path = '/a1/' + created
    token = client.get(path).json
    before = snapshot(owner)
    assert client.post(path, data=data).status_code == 400  # create token cannot edit
    data['_form_context'], data['row_version'] = token['token'], str(token['version'] + 1)
    assert client.post(path, data=data).status_code == 400
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    assert client.post('/a1/new', data=fresh(client)).status_code == 403
    assert snapshot(owner) == before
