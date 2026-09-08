"""Real app-role SQL helpers for the schema27 contract; no HTTP or mocked writes."""
import json

import pytest
from sqlalchemy import text

from test_master_data_db import make_actor
from test_component_metadata_master_lock_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, SCHEMA, PERMISSIONS,
)


@pytest.fixture
def prepared(seeded_pg16, app_engine):  # noqa: F811
    actor = make_actor(seeded_pg16)
    with seeded_pg16.connect() as c:
        location = c.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one()
    ids = {'actor': actor.user_id, 'authz': actor.authz_version, 'location': location}
    storage = execute(app_engine, '''SELECT cafeteria.create_storage_location_v21(
        :actor,:authz,:location,NULL,NULL,CAST(:payload AS jsonb))''', ids,
        {'code': 'REAL_STORE', 'name': 'Realer Testlagerort', 'sort_order': 1})
    ids['storage'] = storage['public_id']
    return seeded_pg16, app_engine, ids


def execute(engine, sql, ids, payload=None):
    parameters = dict(ids)
    if payload is not None:
        parameters['payload'] = json.dumps(payload)
    with engine.begin() as c:
        return c.execute(text(sql), parameters).scalar_one()


def food_payload(ids, name='Gemüse', unit='G', pin=None):
    result = {'name': name, 'base_unit_code': unit, 'note': '',
              'storage_location_public_ids': [ids['storage']]}
    if pin is not None:
        result.update(prepared_recipe_revision_public_id=pin['public_id'],
                      prepared_recipe_content_hash_sha256=pin['content_hash_sha256'])
    return result


def create_food(engine, ids, name='Gemüse', unit='G', pin=None, **extra):
    return execute(engine, 'SELECT cafeteria.create_food_v27(:actor,:authz,:location,CAST(:payload AS jsonb))',
                   ids, {**food_payload(ids, name, unit, pin), **extra})


def update_food(engine, ids, food, payload):
    return execute(engine, '''SELECT cafeteria.update_food_v27(:actor,:authz,:location,
        CAST(:target AS uuid),:version,CAST(:payload AS jsonb))''',
        {**ids, 'target': food['public_id'], 'version': food['row_version']}, payload)


def recipe_payload(foods, *, name='Testzubereitung', unit='G', quantity='1'):
    return {'title': name, 'description': None, 'servings': quantity, 'servings_unit_code': unit,
            'prep_minutes': None, 'cook_minutes': None,
            'source': {'kind': 'manual', 'reference': None, 'url': None, 'note': None, 'fetched_at': None},
            'ingredients': [{'line_public_id': None, 'ingredient_text': 'Echte Zutat',
                             'group_label': None, 'food_public_id': food['public_id'] if food else None,
                             'quantity': '1', 'unit_code': unit, 'note': None, 'source_kind': 'manual',
                             'source_reference': None, 'fetched_at': None} for food in foods],
            'steps': [], 'tag_public_ids': [], 'images': []}


def create_recipe(engine, ids, foods, **options):
    return execute(engine, '''SELECT cafeteria.create_recipe_v22(:actor,:authz,:location,NULL,NULL,
        CAST(:payload AS jsonb))''', ids, recipe_payload(foods, **options))


def preview(engine, ids, recipe):
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        with c.begin():
            c.execute(text('SET TRANSACTION READ ONLY'))
            return c.execute(text('''SELECT cafeteria.recipe_dependency_preview_v27(
                :location,CAST(:target AS uuid),:version)'''),
                {**ids, 'target': recipe['public_id'], 'version': recipe['row_version']}).scalar_one()


def freeze(engine, ids, recipe, dependency=None):
    if dependency is None:
        dependency = preview(engine, ids, recipe)['dependency_hash_sha256']
    return execute(engine, '''SELECT cafeteria.freeze_recipe_v27(:actor,:authz,:location,
        CAST(:target AS uuid),:version,:dependency)''',
        {**ids, 'target': recipe['public_id'], 'version': recipe['row_version'], 'dependency': dependency})


def legacy_freeze(owner, ids, recipe):
    return execute(owner, '''SELECT cafeteria.freeze_recipe_revision_v22(:actor,:authz,:location,
        CAST(:target AS uuid),:version,'{}')''',
        {**ids, 'target': recipe['public_id'], 'version': recipe['row_version']})


def revision_snapshot(owner, revision):
    return execute(owner, 'SELECT snapshot_json FROM cafeteria.recipe_revisions WHERE public_id=CAST(:id AS uuid)',
                   {'id': revision['public_id']})


def state(owner):
    with owner.connect() as c:
        return {table: c.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).scalars().all()
                for table in ('foods', 'food_storage_locations', 'recipes', 'recipe_ingredients', 'recipe_revisions', 'audit_events')}
