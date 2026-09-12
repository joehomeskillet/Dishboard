"""HTTP and store contracts for dish-template writers; CAS is updated_at."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from cafeteria import dish_template_store as store
from cafeteria import recipe_store as recipes
from cafeteria.recipe_commands import ERRORS
from cafeteria.recipe_reads import get_location
from cafeteria.recipe_types import RecipeConflictError, RecipeNotFoundError, RecipeValidationError
from cafeteria.master_data_types import ObjectExpectation
from test_master_data_db import signed_in
from test_master_data_routes import (  # noqa: F401
    Forms, app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import payload as recipe_payload

COLUMNS = ('Titel', 'Menüart', 'Geltungsbereich', 'Gebundenes Rezept', 'Aktivstatus')


def snapshot(owner):
    with owner.connect() as connection:
        return {table: connection.execute(text(
            f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
        )).all() for table in ('dish_templates', 'audit_events')}


def fields(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert path in Forms(response.text).forms, Forms(response.text).forms.keys()
    return Forms(response.text).forms[path]


def create(client, title='Mittagssuppe', **values):
    path = '/admin/gerichtvorlagen/neu'
    data = fields(client, path)
    data['title'] = title
    for key, value in values.items():
        data[key] = value
    response = client.post(path, data=data)
    assert response.status_code == 303, response.text
    listing = client.get('/admin/gerichtvorlagen')
    match = re.search(rf'href="(/admin/gerichtvorlagen/[0-9a-f-]{{36}})">{re.escape(title)}', listing.text)
    assert match, listing.text
    return match.group(1)


def make_recipe(engine, actor, title='Gebundenes Rezept'):
    with signed_in(engine, actor):
        location = recipes.get_location(engine)
        return recipes.create_recipe(
            engine, actor, recipe_payload(title=title), expected_location_id=location,
        )


def foreign_recipe(owner, actor):
    with owner.begin() as connection:
        location = connection.execute(text(
            "INSERT INTO cafeteria.locations(code,name,active) VALUES('FOREIGN','Fremd',false) RETURNING id"
        )).scalar_one()
        public_id = connection.execute(text("""INSERT INTO cafeteria.recipes(
            location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
            VALUES(:loc,:actor,:actor,'Fremdsuppe',4,
            (SELECT id FROM cafeteria.measurement_units WHERE code='PORTION'),'manual')
            RETURNING public_id"""), {'loc': location, 'actor': actor.user_id}).scalar_one()
    return str(public_id)


def test_p1901_is_the_validation_class():
    assert ERRORS['P1901'] is RecipeValidationError
    assert ERRORS['55000'] is RecipeConflictError
    assert ERRORS['22023'] is RecipeNotFoundError


def test_list_columns_sidebar_and_create_without_target(b3):  # noqa: F811
    app, owner, client, _ = b3
    assert sum(rule.endpoint == 'admin.dish_templates_list' for rule in app.url_map.iter_rules()) == 1
    listing = client.get('/admin/gerichtvorlagen')
    assert listing.status_code == 200
    assert 'Gerichtvorlagen' in listing.text
    assert 'Noch keine Gerichtvorlagen' in listing.text
    before = snapshot(owner)
    path = create(client, title='Ohne Ziel')
    filled = client.get('/admin/gerichtvorlagen')
    assert path.startswith('/admin/gerichtvorlagen/')
    assert 'Ohne Ziel' in filled.text
    assert all(column in filled.text for column in COLUMNS)
    assert len(snapshot(owner)['dish_templates']) == len(before['dish_templates']) + 1
    assert len(snapshot(owner)['audit_events']) == len(before['audit_events']) + 1


def test_create_with_target_is_p1901(b3):  # noqa: F811
    _, owner, client, _ = b3
    data = fields(client, '/admin/gerichtvorlagen/neu')
    data['title'] = 'Mit Ziel'
    data['public_id'] = str(uuid4())
    data['updated_at'] = datetime.now(timezone.utc).isoformat()
    before = snapshot(owner)
    response = client.post('/admin/gerichtvorlagen/neu', data=data)
    assert response.status_code == 400
    assert 'Ungültige neue Gerichtvorlage' in response.text
    assert snapshot(owner) == before


def test_stale_updated_at_is_409_with_preserved_context(b3):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, title='Ursprung')
    stale = fields(client, path)
    fresh = fields(client, path)
    fresh['title'] = 'Erste Sitzung'
    assert client.post(path, data=fresh).status_code == 303
    stale['title'] = 'Zweite Sitzung'
    before = snapshot(owner)
    conflict = client.post(path, data=stale)
    assert conflict.status_code == 409
    assert conflict.headers['Cache-Control'] == 'no-store'
    assert 'Gerichtvorlage wurde geändert' in conflict.text
    assert 'Zweite Sitzung' in conflict.text
    assert 'Aktuellen Stand neu laden' in conflict.text
    returned = Forms(conflict.text).forms[path]
    assert returned['updated_at'] == stale['updated_at']
    assert snapshot(owner) == before


def test_noop_update_returns_same_row_without_second_audit(b3):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, title='Unverändert')
    data = fields(client, path)
    before = snapshot(owner)
    assert client.post(path, data=data).status_code == 303
    assert snapshot(owner) == before
    again = fields(client, path)
    assert again['updated_at'] == data['updated_at']
    assert again['title'] == 'Unverändert'


def test_unchanged_active_is_55000(b3):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, title='Schon aktiv')
    data = fields(client, path)
    data['action'] = 'reactivate'
    before = snapshot(owner)
    response = client.post(path, data=data)
    assert response.status_code == 409
    assert 'Aktivstatus ist unverändert' in response.text
    assert snapshot(owner) == before


def test_profile_scope_outside_contract_is_p1901(b3):  # noqa: F811
    _, owner, client, _ = b3
    data = fields(client, '/admin/gerichtvorlagen/neu')
    data['title'] = 'Falscher Scope'
    data['profile_scope'] = 'kitchen'
    before = snapshot(owner)
    response = client.post('/admin/gerichtvorlagen/neu', data=data)
    assert response.status_code == 400
    assert 'Ungültige Vorlagenfelder' in response.text
    assert snapshot(owner) == before


def test_archived_recipe_cannot_be_rebound(b3):  # noqa: F811
    _, owner, client, actor = b3
    engine = b3[0].extensions['cafeteria_db']
    recipe = make_recipe(engine, actor, 'Archivrezept')
    with signed_in(engine, actor):
        recipes.set_recipe_active(
            engine, actor, ObjectExpectation(recipe.public_id, recipe.row_version),
            active=False, expected_location_id=recipes.get_location(engine),
        )
    path = create(client, title='Ohne Rezept')
    data = fields(client, path)
    data['recipe_public_id'] = recipe.public_id
    before = snapshot(owner)
    response = client.post(path, data=data)
    assert response.status_code == 409
    assert 'Archiviertes Rezept kann nicht neu zugeordnet werden' in response.text
    assert snapshot(owner) == before


def test_recipe_of_other_location_is_22023(b3):  # noqa: F811
    _, owner, client, actor = b3
    foreign = foreign_recipe(owner, actor)
    data = fields(client, '/admin/gerichtvorlagen/neu')
    data['title'] = 'Fremdes Rezept'
    data['recipe_public_id'] = foreign
    before = snapshot(owner)
    response = client.post('/admin/gerichtvorlagen/neu', data=data)
    assert response.status_code == 400
    assert 'Unbekanntes Rezept' in response.text
    assert snapshot(owner) == before


def test_store_create_with_target_and_bad_scope(b3):  # noqa: F811
    app, _, _, actor = b3
    engine = app.extensions['cafeteria_db']
    location = get_location(engine)
    payload = {
        'menu_type_code': 'MENU_1', 'profile_scope': 'common', 'title': 'Direkt',
        'description': None, 'recipe_public_id': None,
    }
    with pytest.raises(RecipeValidationError, match='Ungültige neue Gerichtvorlage'):
        store.create_template(
            engine, actor, payload, expected_location_id=location, target=str(uuid4()),
        )
    created = store.create_template(engine, actor, payload, expected_location_id=location)
    assert created['active'] is True
    payload['profile_scope'] = 'kitchen'
    with pytest.raises(RecipeValidationError, match='Ungültige Vorlagenfelder'):
        store.create_template(engine, actor, payload, expected_location_id=location)
