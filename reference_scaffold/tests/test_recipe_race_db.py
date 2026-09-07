"""Observe actual PostgreSQL blocking, without sleeps or refreshed expectations."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from cafeteria import recipe_store as store
from cafeteria import master_data_store as masters
from test_recipe_store_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, payload, mutable, target, snapshot, make_actor,
)
from test_recipe_store_db import master as master
from test_master_data_race_db import worker, blocked, UPDATE_FOOD
from test_recipe_store_db import line

UPDATE = 'SELECT cafeteria.update_recipe_v22(:actor,:version,:location,CAST(:target AS uuid),:target_version,CAST(:payload AS jsonb))'
FREEZE = 'SELECT cafeteria.freeze_recipe_revision_v22(:actor,:version,:location,CAST(:target AS uuid),:target_version,CAST(:payload AS jsonb))'


def arguments(actor, recipe, location, data):
    return {'actor': actor.user_id, 'version': actor.authz_version, 'location': location,
            'target': recipe.public_id, 'target_version': recipe.row_version, 'payload': json.dumps(data)}


@pytest.mark.parametrize('second_freeze', [False, True])
def test_original_cas_serializes_edit_and_freeze(master, second_freeze):
    owner, engine, actor = master
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    data = mutable(store.get_recipe(engine, recipe.public_id).payload)
    first = arguments(actor, recipe, location, {**data, 'title': 'First winner'})
    second = arguments(actor, recipe, location, {} if second_freeze else {**data, 'title': 'Lost writer'})
    before = snapshot(owner)
    started, state = threading.Event(), {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as current:
            blocker = current.execute(text('SELECT pg_backend_pid()')).scalar_one()
            assert current.execute(text(UPDATE), first).scalar_one()['row_version'] == 2
            future = pool.submit(worker, engine, FREEZE if second_freeze else UPDATE, second, started, state)
            blocked(owner, started, state, blocker)
        assert future.result(10) == '55000'
    read = store.get_recipe(engine, recipe.public_id)
    assert read.row_version == 2 and read.payload['title'] == 'First winner'
    after = snapshot(owner)
    assert len(after['audit_events']) == len(before['audit_events']) + 1
    assert after['recipe_revisions'] == before['recipe_revisions']


@pytest.mark.parametrize('change', ['role_revoke', 'password_reset', 'role_definition'])
def test_original_actor_is_rechecked_after_serialized_authorization_change(master, change):
    owner, engine, actor = master
    location = store.get_location(engine)
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    data = mutable(store.get_recipe(engine, recipe.public_id).payload)
    if change == 'password_reset':
        admin = make_actor(owner, 'Cafeteria.Admin')
        with owner.begin() as current:
            for person, name in [(actor.user_id, 'recipe.actor'), (admin.user_id, 'recipe.admin')]:
                current.execute(text('INSERT INTO cafeteria.local_credentials(user_id,username,password_hash) VALUES(:id,:name,:hash)'),
                    {'id': person, 'name': name, 'hash': generate_password_hash('Isolated-recipe-test-passphrase')})
            public_id = current.execute(text('SELECT public_id FROM cafeteria.users WHERE id=:id'), {'id': actor.user_id}).scalar_one()
    params = arguments(actor, recipe, location, {**data, 'title': 'Must not save'})
    started, state = threading.Event(), {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        with owner.begin() as current:
            blocker = current.execute(text('SELECT pg_backend_pid()')).scalar_one()
            if change == 'role_revoke':
                current.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
            elif change == 'password_reset':
                current.execute(text('SELECT * FROM cafeteria.reset_local_password_v19(:admin,:authz,:target,:version,:hash)'),
                    {'admin': admin.user_id, 'authz': admin.authz_version, 'target': public_id,
                     'version': actor.authz_version, 'hash': generate_password_hash('Isolated-new-recipe-passphrase')})
            else:
                current.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Publisher'"))
            future = pool.submit(worker, engine, UPDATE, params, started, state)
            blocked(owner, started, state, blocker)
        assert future.result(10) == ('P1902' if change == 'role_definition' else 'P1903')
    with owner.connect() as current:
        assert current.execute(text('SELECT title,row_version FROM cafeteria.recipes WHERE public_id=CAST(:id AS uuid)'),
            {'id': recipe.public_id}).one() == ('Suppe', 1)
        assert current.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE 'recipe.%'")).scalar_one() == 1


@pytest.mark.parametrize('freeze_first', [False, True])
def test_food_factor_change_and_freeze_use_one_serialized_snapshot(master, freeze_first):
    owner, engine, actor = master
    location = store.get_location(engine)
    food = masters.create_food(engine, actor, {'name': 'Milch', 'base_unit_code': 'ML', 'density_g_per_ml': '1.03'})
    recipe = store.create_recipe(engine, actor, payload(ingredients=[line(food_public_id=food.public_id)]), expected_location_id=location)
    freeze = arguments(actor, recipe, location, {})
    change = arguments(actor, food, location, {'name': 'Milch', 'base_unit_code': 'ML', 'density_g_per_ml': '1.04'})
    first_sql, first_args, second_sql, second_args = (FREEZE, freeze, UPDATE_FOOD, change) if freeze_first else (UPDATE_FOOD, change, FREEZE, freeze)
    started, state = threading.Event(), {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as current:
            blocker = current.execute(text('SELECT pg_backend_pid()')).scalar_one()
            first = current.execute(text(first_sql), first_args).scalar_one()
            future = pool.submit(worker, engine, second_sql, second_args, started, state)
            blocked(owner, started, state, blocker)
        second = future.result(10)
    assert isinstance(second, dict)
    revision = store.get_revision(engine, (first if freeze_first else second)['public_id'])
    assert revision.snapshot['foods'][0]['density_g_per_ml'] == ('1.03' if freeze_first else '1.04')
    assert str(masters.get_food(engine, food.public_id).density_g_per_ml) == '1.04'


@pytest.mark.parametrize('archive_first', [False, True])
def test_food_archive_and_new_association_serialize(master, archive_first):
    owner, engine, actor = master
    location = store.get_location(engine)
    food = masters.create_food(engine, actor, {'name': 'Karotte', 'base_unit_code': 'G'})
    recipe = store.create_recipe(engine, actor, payload(), expected_location_id=location)
    data = mutable(store.get_recipe(engine, recipe.public_id).payload)
    data['ingredients'][0]['food_public_id'] = food.public_id
    assign = arguments(actor, recipe, location, data)
    archive = arguments(actor, food, location, {'active': False})
    archive_sql = 'SELECT cafeteria.set_food_active_v21(:actor,:version,:location,CAST(:target AS uuid),:target_version,CAST(:payload AS jsonb))'
    first_sql, first_args, second_sql, second_args = (archive_sql, archive, UPDATE, assign) if archive_first else (UPDATE, assign, archive_sql, archive)
    started, state = threading.Event(), {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as current:
            blocker = current.execute(text('SELECT pg_backend_pid()')).scalar_one()
            current.execute(text(first_sql), first_args).scalar_one()
            future = pool.submit(worker, engine, second_sql, second_args, started, state)
            blocked(owner, started, state, blocker)
        result = future.result(10)
    assert result == '55000' if archive_first else isinstance(result, dict)
    assert not masters.get_food(engine, food.public_id).active
    read = store.get_recipe(engine, recipe.public_id)
    assert read.payload['ingredients'][0]['food_public_id'] == (None if archive_first else food.public_id)
