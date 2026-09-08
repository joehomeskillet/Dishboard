"""Measured blocking in the real PostgreSQL pool, including both graph winner orders."""
from concurrent.futures import ThreadPoolExecutor
import json
from queue import Queue

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prepared_food_fixtures import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, create_food, create_recipe,
    food_payload, freeze, legacy_freeze, preview, revision_snapshot, execute, state,
)
from prepared_food_fixtures import prepared as prepared
from test_prepared_food_migration_db import wait_blocked

UPDATE = '''SELECT cafeteria.update_food_v27(:actor,:authz,:location,CAST(:target AS uuid),
    :version,CAST(:payload AS jsonb))'''
FREEZE = '''SELECT cafeteria.freeze_recipe_v27(:actor,:authz,:location,CAST(:target AS uuid),
    :version,:dependency)'''
ARCHIVE = '''SELECT cafeteria.set_active_storage_location_v21(:actor,:authz,:location,CAST(:target AS uuid),
    :version,CAST(:payload AS jsonb))'''


def arguments(ids, target, payload):
    return ids | {'target': target['public_id'], 'version': target['row_version'], 'payload': json.dumps(payload)}


def worker(engine, sql, args, started):
    try:
        with engine.begin() as c:
            started.put(c.execute(text('SELECT pg_backend_pid()')).scalar_one())
            return c.execute(text(sql), args).scalar_one()
    except DBAPIError as error:
        return error.orig.sqlstate


@pytest.mark.parametrize('reverse', [False, True])
def test_opposite_v1_current_pins_serialize_and_only_one_commits(prepared, reverse):
    owner, engine, ids = prepared
    first, second = create_food(engine, ids, 'F'), create_food(engine, ids, 'G')
    left = legacy_freeze(owner, ids, create_recipe(engine, ids, [second], name='R enthält G'))
    right = legacy_freeze(owner, ids, create_recipe(engine, ids, [first], name='S enthält F'))
    choices = [(first, left, 'F'), (second, right, 'G')]
    if reverse:
        choices.reverse()
    first_args, second_args = [arguments(ids, food, food_payload(ids, name, pin=pin)) for food, pin, name in choices]
    before = state(owner)
    started = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as c:
            assert c.execute(text(UPDATE), first_args).scalar_one()['row_version'] == 2
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            future = pool.submit(worker, engine, UPDATE, second_args, started)
            assert blocker in wait_blocked(owner, started.get(timeout=3))
        assert future.result(timeout=8) == '55000'
    after = state(owner)
    assert len(after['audit_events']) == len(before['audit_events']) + 1
    with owner.connect() as c:
        assert c.execute(text('SELECT count(*) FROM cafeteria.foods WHERE prepared_recipe_revision_id IS NOT NULL')).scalar_one() == 1


@pytest.mark.parametrize('freeze_first', [False, True])
def test_pin_change_and_freeze_compare_original_dependency_after_wait(prepared, freeze_first):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Roh')
    left = freeze(engine, ids, create_recipe(engine, ids, [raw], name='Alte Zubereitung'))
    right = freeze(engine, ids, create_recipe(engine, ids, [raw], name='Andere Zubereitung'))
    food = create_food(engine, ids, 'Vorbereitet', pin=left)
    recipe = create_recipe(engine, ids, [food], name='Elternrezept')
    original = preview(engine, ids, recipe)
    update_args = arguments(ids, food, food_payload(ids, 'Vorbereitet', pin=right))
    freeze_args = ids | {'target': recipe['public_id'], 'version': recipe['row_version'],
                         'dependency': original['dependency_hash_sha256']}
    first_sql, first_args, second_sql, second_args = ((FREEZE, freeze_args, UPDATE, update_args)
        if freeze_first else (UPDATE, update_args, FREEZE, freeze_args))
    started = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as c:
            result = c.execute(text(first_sql), first_args).scalar_one()
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            future = pool.submit(worker, engine, second_sql, second_args, started)
            assert blocker in wait_blocked(owner, started.get(timeout=3))
        second = future.result(timeout=8)
    if freeze_first:
        assert second['row_version'] == 2
        assert revision_snapshot(owner, result) == original['snapshot']
    else:
        assert second == '55000'
        assert execute(owner, 'SELECT count(*) FROM cafeteria.recipe_revisions r JOIN cafeteria.recipes h ON h.id=r.recipe_id WHERE h.public_id=CAST(:id AS uuid)',
                       {'id': recipe['public_id']}) == 0


@pytest.mark.parametrize('change', ['role_revoke', 'role_definition'])
def test_authorization_changes_block_then_prevent_food_and_freeze(prepared, change):
    owner, engine, ids = prepared
    food = create_food(engine, ids)
    recipe = create_recipe(engine, ids, [food])
    expected = preview(engine, ids, recipe)
    options = [(UPDATE, arguments(ids, food, food_payload(ids, 'Nicht speichern'))),
               (FREEZE, ids | {'target': recipe['public_id'], 'version': recipe['row_version'],
                               'dependency': expected['dependency_hash_sha256']})]
    before = state(owner)
    started = Queue()
    with ThreadPoolExecutor(max_workers=2) as pool:
        with owner.begin() as c:
            if change == 'role_revoke':
                c.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor'), ids)
            else:
                c.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Publisher'"))
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            futures = [pool.submit(worker, engine, sql, args, started) for sql, args in options]
            for _ in futures:
                assert blocker in wait_blocked(owner, started.get(timeout=3))
        assert [f.result(timeout=8) for f in futures] == [
            'P1903' if change == 'role_revoke' else 'P1902'] * 2
    assert state(owner) == before


@pytest.mark.parametrize('archive_first', [False, True])
def test_storage_archive_and_complete_assignment_have_one_winner(prepared, archive_first):
    owner, engine, ids = prepared
    food = create_food(engine, ids)
    other = execute(engine, "SELECT cafeteria.create_storage_location_v21(:actor,:authz,:location,NULL,NULL,'{\"code\":\"OTHER\",\"name\":\"Anderer Lagerort\"}')", ids)
    assign_args = arguments(ids, food, food_payload(ids | {'storage': other['public_id']}))
    archive_args = ids | {'target': other['public_id'], 'version': other['row_version'],
                          'payload': json.dumps({'active': False})}
    first_sql, first_args, second_sql, second_args = ((ARCHIVE, archive_args, UPDATE, assign_args)
        if archive_first else (UPDATE, assign_args, ARCHIVE, archive_args))
    before = state(owner)
    started = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as c:
            c.execute(text(first_sql), first_args).scalar_one()
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            future = pool.submit(worker, engine, second_sql, second_args, started)
            assert blocker in wait_blocked(owner, started.get(timeout=3))
        assert future.result(timeout=8) == ('P1901' if archive_first else '55000')
    assert len(state(owner)['audit_events']) == len(before['audit_events']) + 1
    with owner.connect() as c:
        assert c.execute(text('SELECT count(*) FROM cafeteria.food_storage_locations l JOIN cafeteria.storage_locations s ON s.id=l.storage_location_id WHERE s.active')).scalar_one() == 1


def test_r5_food_then_recipe_reader_does_not_need_late_graph_lock(prepared):
    owner, engine, ids = prepared
    food = create_food(engine, ids)
    recipe = create_recipe(engine, ids, [food])
    historical = legacy_freeze(owner, ids, recipe)
    recipe['row_version'] = historical['recipe_row_version']
    expected = preview(engine, ids, recipe)
    internal = ids | {'food_id': execute(owner, 'SELECT id FROM cafeteria.foods WHERE public_id=CAST(:id AS uuid)', {'id': food['public_id']}),
                      'revision_id': execute(owner, 'SELECT id FROM cafeteria.recipe_revisions WHERE public_id=CAST(:id AS uuid)', {'id': historical['public_id']})}
    started = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as c:
            c.execute(text('SELECT cafeteria.begin_menu_binding_write_v26(:actor,:authz,:location)'), ids)
            c.execute(text('SELECT * FROM cafeteria.lock_component_foods_v26(:actor,:authz,:location,ARRAY[:food_id]::bigint[])'), internal)
            c.execute(text('SELECT * FROM cafeteria.lock_menu_recipe_revisions_v26(:actor,:authz,:location,ARRAY[:revision_id]::bigint[])'), internal)
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            future = pool.submit(worker, engine, FREEZE, ids | {'target': recipe['public_id'],
                'version': recipe['row_version'], 'dependency': expected['dependency_hash_sha256']}, started)
            assert blocker in wait_blocked(owner, started.get(timeout=3))
        assert future.result(timeout=8)['recipe_row_version'] == recipe['row_version'] + 1
