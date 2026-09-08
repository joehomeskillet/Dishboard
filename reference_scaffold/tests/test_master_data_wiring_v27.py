"""Offline command and rendered-form contracts; real PostgreSQL gates are separate."""
from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import g, session
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest, Unauthorized

import cafeteria
from cafeteria.admin import master_data_forms as forms, master_data_routes as routes
from cafeteria.auth.local_users import ActorExpectation
from cafeteria import master_data_commands as commands, master_data_reads as reads
from cafeteria.master_data_types import (
    FoodDTO, MasterDataConfigurationError, MasterDataValidationError, ObjectExpectation,
    PreparedRecipeDTO, SourceDTO, UnitDTO, VocabularyDTO,
)
from test_master_data_routes import Forms

FOOD = '11111111-1111-4111-8111-111111111111'
STORAGE = '22222222-2222-4222-8222-222222222222'
RECIPE = '33333333-3333-4333-8333-333333333333'
REVISION = '44444444-4444-4444-8444-444444444444'
ACTOR = ActorExpectation(7, 9)


@pytest.mark.parametrize('name,target', [('create_food', None), ('update_food', ObjectExpectation(FOOD, 12))])
def test_food_aggregate_uses_one_v27_call_with_original_expectations(monkeypatch, name, target):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = {'public_id': FOOD, 'row_version': 13}
    resolver = MagicMock(return_value=17)
    monkeypatch.setattr(commands, 'resolve_single_active_location_connection', resolver)
    payload = {'name': 'Hummus', 'base_unit_code': 'G', 'storage_location_public_ids': [STORAGE],
        'prepared_recipe_revision_public_id': REVISION, 'prepared_recipe_content_hash_sha256': 'a' * 64}
    result = commands.mutation(engine, name, ACTOR, target, payload, original_location=17)
    assert result.public_id == FOOD and result.row_version == 13
    engine.begin.assert_called_once_with()
    resolver.assert_called_once_with(connection)
    connection.execute.assert_called_once()
    sql, values = connection.execute.call_args.args
    assert ('cafeteria.' + name + '_v27(') in str(sql)
    assert '_v21' not in str(sql)
    assert (values['actor'], values['actor_version'], values['location']) == (7, 9, 17)
    assert (values['target'], values['target_version']) == ((FOOD, 12) if target else (None, None))
    assert json.loads(values['payload']) == payload


def test_scope_race_rejects_before_command_and_missing_storage_before_transaction(monkeypatch):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    monkeypatch.setattr(commands, 'resolve_single_active_location_connection', lambda _: 18)
    with pytest.raises(MasterDataConfigurationError):
        commands.command(engine, 'create_food', ACTOR, None,
                         {'storage_location_public_ids': [STORAGE]}, original_location=17)
    connection.execute.assert_not_called()
    engine.reset_mock()
    with pytest.raises(MasterDataValidationError):
        commands.command(engine, 'create_food', ACTOR, None, {'name': 'Hummus'}, original_location=17)
    engine.begin.assert_not_called()


def test_prepared_search_is_read_only_scoped_bounded_and_uses_frozen_values(monkeypatch):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value = [{
        'recipe_public_id': RECIPE, 'revision_public_id': REVISION, 'revision_number': 2,
        'content_hash_sha256': 'a' * 64, 'title': 'Historischer Titel',
        'yield_quantity': '1000.000001', 'yield_unit_code': 'G', 'recipe_active': True,
    }]
    resolver = MagicMock(return_value=17)
    monkeypatch.setattr(reads, 'resolve_single_active_location_connection', resolver)
    result = reads.list_prepared_revisions(engine, search='50%_\\', limit=26, offset=25)
    assert str(connection.execute.call_args_list[0].args[0]) == 'SET TRANSACTION READ ONLY'
    sql, values = connection.execute.call_args_list[1].args
    assert 'v.location_id=:location AND r.active' in str(sql)
    assert "v.snapshot_json->'recipe'->>'title'" in str(sql)
    assert 'LIMIT :limit OFFSET :offset' in str(sql)
    assert values == {'limit': 26, 'offset': 25, 'archived': False, 'location': 17, 'search': '50\\%\\_\\\\'}
    resolver.assert_called_once_with(connection)
    assert result[0].yield_quantity == Decimal('1000.000001')
    assert result[0].title == 'Historischer Titel' and result[0].revision_public_id == REVISION


@pytest.mark.parametrize('options', [{'search': '\x00'}, {'search': 'x' * 201}, {'limit': 0}, {'offset': -1}])
def test_invalid_search_never_opens_database(options):
    engine = MagicMock()
    with pytest.raises(MasterDataValidationError):
        reads.list_prepared_revisions(engine, **options)
    engine.begin.assert_not_called()


def test_food_search_rejects_nul_before_database():
    engine = MagicMock()
    with pytest.raises(MasterDataValidationError):
        reads.list_foods(engine, search='\x00')
    engine.begin.assert_not_called()


@pytest.fixture
def offline_app(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _: None)
    app = cafeteria.create_app()
    app.config.update(TESTING=True, SECRET_KEY='isolated-v27-offline-fixture')
    app.extensions['cafeteria_db'] = MagicMock()
    return app


def test_signed_original_scope_actor_and_cas_are_mandatory(offline_app, monkeypatch):
    monkeypatch.setattr(forms, 'location', lambda _: 17)
    with offline_app.test_request_context(method='POST'):
        session['_csrf_token'] = 'isolated-csrf'
        g.auth_user = ACTOR
        row = SimpleNamespace(public_id=FOOD, row_version=12)
        token = forms.form_token('zutaten', 'stammdaten', row, 17)
        decoded = forms.signer().loads(token)
    data = MultiDict({'_csrf': 'isolated-csrf', '_form_context': token, 'row_version': '12'})
    with offline_app.test_request_context(method='POST', data=data):
        session['_csrf_token'] = 'isolated-csrf'
        g.auth_user = ACTOR
        assert forms.expectations('zutaten', 'stammdaten', FOOD) == (ACTOR, ObjectExpectation(FOOD, 12), 17)
    for missing in ('location', 'actor_version'):
        invalid = dict(decoded)
        del invalid[missing]
        with offline_app.test_request_context(method='POST'):
            data['_form_context'] = forms.signer().dumps(invalid)
        with offline_app.test_request_context(method='POST', data=data):
            session['_csrf_token'] = 'isolated-csrf'
            g.auth_user = ACTOR
            with pytest.raises(BadRequest):
                forms.expectations('zutaten', 'stammdaten', FOOD)
    data['_form_context'] = token
    with offline_app.test_request_context(method='POST', data=data):
        session['_csrf_token'] = 'isolated-csrf'
        g.auth_user = ActorExpectation(7, 10)
        with pytest.raises(Unauthorized):
            forms.expectations('zutaten', 'stammdaten', FOOD)


@pytest.fixture
def food_row():
    unit = UnitDTO(FOOD, 'G', 'Gramm', 'mass', Decimal(1), True, 1)
    storage = VocabularyDTO(STORAGE, 'storage_location', 'COOL', 'Kühlraum', 1, True, 1)
    prepared = PreparedRecipeDTO(RECIPE, REVISION, 2, 'a' * 64, 'Hummus alt', Decimal('1E+3'), 'G', False)
    return FoodDTO(FOOD, 'Hummus', None, unit, None, None, 'Eigener Entwurf', 'not_checked',
        SourceDTO('manual', None, None, None, None), True, 12, (), (), (), (storage,), prepared)


@pytest.mark.parametrize('writable', [True, False])
def test_rendered_history_and_storage_links_keep_exact_pin(offline_app, monkeypatch, food_row, writable):
    monkeypatch.setattr(forms, 'location', lambda _: 17)
    monkeypatch.setattr(forms, 'engine', lambda: None)
    monkeypatch.setattr(routes, 'choices', lambda _: {'units': [food_row.base_unit], 'categories': [],
        'storages': list(food_row.storage_locations), 'tags': [], 'labels': [], 'allergens': []})
    current = replace(food_row.prepared_recipe, revision_public_id='55555555-5555-4555-8555-555555555555',
                      revision_number=3, title='Hummus neu', recipe_active=True)
    reader = MagicMock(return_value=[current] * 26)
    monkeypatch.setattr(routes.store, 'list_prepared_revisions', reader)
    path = '/admin/grundlagen/zutaten/' + FOOD
    with offline_app.test_request_context(path + '?recipe_q=Hummus&recipe_page=2'):
        g.auth_user, g.auth_roles = ACTOR, ['Cafeteria.Admin'] if writable else []
        g.area_names = {'cafeteria': 'Cafeteria', 'patienten': 'Patienten'}
        response = routes.render_detail('zutaten', food_row)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '/admin/rezepte/' + RECIPE + '/revisionen/' + REVISION in html
    assert '/admin/grundlagen/lagerorte/' + STORAGE in html
    assert 'Kein Bestand erfasst' in html and '1000 G' in html and '1E+3' not in html
    reader.assert_called_once_with(None, search='Hummus', limit=26, offset=25)
    assert ('food-core-form' in html) is writable
    if writable:
        assert Forms(html).forms[path + '/stammdaten']['prepared_recipe_choice'] == REVISION + ':' + 'a' * 64
        assert 'admin.recipe_list' not in html and 'href="/admin/rezepte"' in html


def test_rejected_hash_preserves_original_post_and_signed_expectations(offline_app, monkeypatch, food_row):
    monkeypatch.setattr(forms, 'location', lambda _: 17)
    monkeypatch.setattr(forms, 'engine', lambda: None)
    monkeypatch.setattr(routes, 'choices', lambda _: {'units': [food_row.base_unit], 'categories': [],
        'storages': list(food_row.storage_locations), 'tags': [], 'labels': [], 'allergens': []})
    monkeypatch.setattr(routes.store, 'list_prepared_revisions', lambda *a, **k: [food_row.prepared_recipe])
    path = '/admin/grundlagen/zutaten/' + FOOD + '/stammdaten'
    data = {'prepared_recipe_choice': REVISION + ':' + 'b' * 64, 'row_version': '9',
            '_form_context': 'original-signed-context', 'storage_location_public_ids': STORAGE}
    with offline_app.test_request_context(path, method='POST', data=data):
        g.auth_user, g.auth_roles = ACTOR, ['Cafeteria.Admin']
        g.area_names = {'cafeteria': 'Cafeteria', 'patienten': 'Patienten'}
        response = routes.render_detail('zutaten', food_row,
            error=forms.FormError('Rezeptstand passt nicht.', 'prepared_recipe_choice'), purpose='stammdaten')
    returned = Forms(response.get_data(as_text=True)).forms[path]
    assert response.status_code == 400
    for key, value in data.items():
        assert returned[key] == value
