"""v25 upgrade, fresh schema equality and exact grants for R5a."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from queue import Queue
import time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from test_component_metadata_master_lock_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, SCHEMA, PERMISSIONS,
)
from test_component_scope_invariants_db import _seed_scope_probe
from test_master_data_db import make_actor
from test_recipe_menu_binding_db import begin, assert_rejected
from test_operations_settings_db import _actor_id, _v19_week, _v19_snapshot, _INSERT_REVISION_SQL


@pytest.fixture
def binding(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as c:
        c.execute(text('UPDATE cafeteria.locations SET active=false WHERE id=:other_location'), ids)
        for key in ('location', 'other_location'):
            params = {'loc': ids[key], 'actor': actor.user_id}
            ids[key + '_recipe'] = c.execute(text("""INSERT INTO cafeteria.recipes(
                location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
                VALUES(:loc,:actor,:actor,'Suppe',4,(SELECT id FROM cafeteria.measurement_units
                WHERE code='PORTION'),'manual') RETURNING id"""), params).scalar_one()
            params['recipe'] = ids[key + '_recipe']
            ids[key + '_revision'] = c.execute(text("""INSERT INTO cafeteria.recipe_revisions(
                location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
                VALUES(:loc,:recipe,1,'{}',encode(pg_catalog.sha256(convert_to('{}','UTF8')),'hex'),:actor)
                RETURNING id"""), params).scalar_one()
            ids[key + '_food'] = c.execute(text("""INSERT INTO cafeteria.foods(
                location_id,created_by,updated_by,name,base_unit_id) VALUES(:loc,:actor,:actor,'Karotte',
                (SELECT id FROM cafeteria.measurement_units WHERE code='G')) RETURNING id"""), params).scalar_one()
            code = 'LAGER_LOC' if key == 'location' else 'LAGER_OTHER'
            storage_id = c.execute(text("""INSERT INTO cafeteria.storage_locations(
                location_id,code,name) VALUES(:loc,:code,'Testlager') RETURNING id"""),
                {'loc': ids[key], 'code': code}).scalar_one()
            c.execute(text("""INSERT INTO cafeteria.food_storage_locations(
                location_id,food_id,storage_location_id) VALUES(:loc,:food,:storage)"""),
                {'loc': ids[key], 'food': ids[key + '_food'], 'storage': storage_id})
    return seeded_pg16, app_engine, ids


PUBLIC_HELPERS = {'begin_menu_binding_write_v26', 'lock_menu_recipe_revisions_v26',
    'lock_component_foods_v26', 'record_menu_binding_write_v26', 'record_component_food_write_v26',
    'create_dish_template_v26', 'update_dish_template_v26', 'set_dish_template_active_v26'}
PRIVATE_HELPERS = {'dish_template_mutate_v26', 'validate_menu_recipe_scope_v26',
                   'validate_dish_recipe_scope_v26', 'validate_menu_dish_scope_v26'}


def structure(c):
    return (
        c.execute(text("""SELECT p.proname,pg_get_function_identity_arguments(p.oid),p.prosrc,
            p.prosecdef,p.proconfig,has_function_privilege('cafeteria_app',p.oid,'EXECUTE')
            FROM pg_proc p WHERE p.pronamespace='cafeteria'::regnamespace AND p.proname LIKE '%_v26'
            ORDER BY p.proname""")).all(),
        c.execute(text("""SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint
            WHERE connamespace='cafeteria'::regnamespace AND conrelid IN (
            'cafeteria.menu_components'::regclass,'cafeteria.menu_item_components'::regclass,
            'cafeteria.dish_templates'::regclass) ORDER BY conname""")).all(),
        c.execute(text("""SELECT tgname,pg_get_triggerdef(oid) FROM pg_trigger
            WHERE tgfoid IN (SELECT oid FROM pg_proc WHERE pronamespace='cafeteria'::regnamespace
            AND proname LIKE '%_v26') ORDER BY tgname""")).all(),
    )


def test_upgrade_preserves_all_existing_rows_and_fresh_schema_contract(pg16):  # noqa: F811
    for migration in database.migration_plan(SCHEMA):
        if migration.version <= 25:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    actor = _actor_id(pg16)
    week = _v19_week(pg16, actor)
    snapshot = _v19_snapshot(pg16, 'CAF-2026-KW36-R1')
    with pg16.begin() as c:
        c.execute(text("UPDATE cafeteria.menu_weeks SET workflow_state='published' WHERE id=:week"), {'week': week})
        c.execute(text(_INSERT_REVISION_SQL), {'week_id': week, 'revision_number': 1,
            'revision_code': snapshot['revision_id'], 'snapshot': json.dumps(snapshot), 'actor': actor})
        c.execute(text("""INSERT INTO cafeteria.audit_events(actor_user_id,action,entity_type,details)
            VALUES(:actor,'auth.logout.requested','authentication',CAST(:details AS jsonb))"""),
            {'actor': actor, 'details': json.dumps({'provider': 'local', 'reason': None, 'authz_version': None})})
        tables = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='cafeteria' AND tablename<>'schema_migrations' ORDER BY tablename")).scalars().all()
        before = {table: c.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).all() for table in tables}
        assert before['publication_revisions'] and before['menu_items'] and before['audit_events']
        ledger = c.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m ORDER BY version')).all()
    database.run_migrations(pg16, SCHEMA)
    database._execute_script(pg16, str(PERMISSIONS))
    database._execute_script(pg16, str(PERMISSIONS))
    new_columns = {'menu_components': 'food_id', 'menu_item_components': 'recipe_revision_id', 'dish_templates': 'recipe_id'}
    with pg16.connect() as c:
        for table in tables:
            projection = f"(to_jsonb(t)-'{new_columns[table]}')" if table in new_columns else 'to_jsonb(t)'
            assert c.execute(text(f'SELECT {projection}::text FROM cafeteria.{table} t ORDER BY {projection}::text')).all() == before[table]
        assert c.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m WHERE version<=25 ORDER BY version')).all() == ledger
        assert c.execute(text('SELECT max(version) FROM cafeteria.schema_migrations')).scalar_one() == 29
        migrated = structure(c)
    with pg16.begin() as c:
        c.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        assert structure(c) == migrated


def test_exact_acl_search_path_and_no_new_table_writes(binding):
    owner, engine, ids = binding
    with owner.connect() as c:
        rows = c.execute(text("""SELECT p.proname,p.prosecdef,p.proconfig,
            pg_get_userbyid(p.proowner)=pg_get_userbyid(n.nspowner) AS owner_matches,
            has_function_privilege('cafeteria_app',p.oid,'EXECUTE') AS app,
            has_function_privilege('cafeteria_backup',p.oid,'EXECUTE') AS backup,
            has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE') AS issuer,
            EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='cafeteria' AND p.proname LIKE '%_v26'""")).mappings().all()
        assert {r['proname'] for r in rows} == PUBLIC_HELPERS | PRIVATE_HELPERS
        for row in rows:
            assert row['app'] == (row['proname'] in PUBLIC_HELPERS)
            assert row['prosecdef'] == (row['proname'] in PUBLIC_HELPERS | {'dish_template_mutate_v26'})
            assert row['proconfig'] == ['search_path=pg_catalog, cafeteria, pg_temp'] and row['owner_matches']
            assert not row['backup'] and not row['issuer'] and not row['public']
        fks = c.execute(text("""SELECT confdeltype FROM pg_constraint WHERE contype='f' AND (
            conname='menu_components_food_scope_fk' OR conname='menu_item_components_recipe_revision_id_fkey'
            OR conname='dish_templates_recipe_id_fkey')""")).scalars().all()
        assert fks == ['r', 'r', 'r']
    for table in ('foods', 'recipes', 'recipe_revisions'):
        assert_rejected(engine, f'UPDATE cafeteria.{table} SET public_id=public_id WHERE false', ids, '42501')
    assert_rejected(engine, "INSERT INTO cafeteria.audit_events(action,entity_type,details) VALUES('forged','x','{}')", ids, '42501')
    assert_rejected(engine, "SELECT cafeteria.dish_template_mutate_v26('create',:actor,:authz,:location,NULL,NULL,'{}')", ids, '42501')


def test_template_reassignment_waits_for_concurrent_reference_then_rejects(binding):
    owner, engine, ids = binding
    with engine.begin() as c:
        ids['template'] = c.execute(text("INSERT INTO cafeteria.dish_templates(title) VALUES('Concurrent') RETURNING id")).scalar_one()
    started = Queue()
    def reassign():
        with pytest.raises(DBAPIError) as error:
            with engine.begin() as c:
                started.put(c.execute(text('SELECT pg_backend_pid()')).scalar_one())
                c.execute(text('UPDATE cafeteria.dish_templates SET recipe_id=:other_location_recipe WHERE id=:template'), ids)
        return error.value.orig.sqlstate
    with ThreadPoolExecutor(max_workers=1) as executor:
        with engine.begin() as c:
            c.execute(text('UPDATE cafeteria.menu_items SET dish_template_id=:template WHERE id=:item'), ids)
            future = executor.submit(reassign)
            wait_until_blocked(owner, started.get(timeout=3))
        assert future.result(timeout=8) == '23514'
    with engine.connect() as c:
        assert c.execute(text('SELECT recipe_id FROM cafeteria.dish_templates WHERE id=:template'), ids).scalar_one() is None


def test_food_receipt_creation_and_duplicate_under_concurrency(binding):
    owner, engine, ids = binding
    started = Queue()
    with engine.begin() as c:
        begin(c, ids)
        c.execute(text('SELECT * FROM cafeteria.lock_component_foods_v26(:actor,:authz,:location,ARRAY[:location_food]::bigint[])'), ids)
        ids['component'] = c.execute(text("""INSERT INTO cafeteria.menu_components(location_id,profile_scope,category,name,food_id)
            VALUES(:location,'common','side','Neue Bindung',:location_food) RETURNING id"""), ids).scalar_one()
        c.execute(text('SELECT cafeteria.record_component_food_write_v26(:actor,:authz,:location,:component,0,1)'), ids)
    def duplicate():
        with pytest.raises(DBAPIError) as error:
            with engine.begin() as c:
                begin(c, ids)
                started.put(c.execute(text('SELECT pg_backend_pid()')).scalar_one())
                c.execute(text('SELECT cafeteria.record_component_food_write_v26(:actor,:authz,:location,:component,1,2)'), ids)
        return error.value.orig.sqlstate
    with ThreadPoolExecutor(max_workers=1) as executor:
        with engine.begin() as c:
            begin(c, ids)
            c.execute(text('SELECT * FROM cafeteria.lock_component_foods_v26(:actor,:authz,:location,ARRAY[:location_food]::bigint[])'), ids)
            c.execute(text("UPDATE cafeteria.menu_components SET name='Geänderte Bindung', "
                           "row_version=row_version+1 WHERE id=:component"), ids)
            event = c.execute(text('SELECT cafeteria.record_component_food_write_v26(:actor,:authz,:location,:component,1,2)'), ids).scalar_one()
            future = executor.submit(duplicate)
            wait_until_blocked(owner, started.get(timeout=3))
        assert future.result(timeout=8) == '55000'
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action='component.food_saved'")).scalar_one() == 2
        details = c.execute(text('SELECT details FROM cafeteria.audit_events WHERE public_id=:id'), {'id': event}).scalar_one()
        assert details['food_public_id'] and details['row_version_before'] == 1 and details['row_version_after'] == 2


def wait_until_blocked(owner, pid):
    deadline = time.monotonic() + 3
    with owner.connect() as c:
        while time.monotonic() < deadline:
            if c.execute(text('SELECT pg_blocking_pids(:pid)'), {'pid': pid}).scalar_one():
                return
            time.sleep(0.01)
    pytest.fail('Concurrent writer did not actually wait on the held row lock.')


def test_historical_permissions_bytes_are_still_exact():
    permissions = PERMISSIONS.read_text()
    for begin_marker, end_marker in (
        ('-- Recipe import commit schema29 grants begin.\n', '-- Recipe import commit schema29 grants end.\n\n'),
        ('-- Recipe import batches schema28 grants begin.\n', '-- Recipe import batches schema28 grants end.\n\n'),
        ('-- Prepared foods schema27 grants begin.\n', '-- Prepared foods schema27 grants end.\n\n'),
        ('-- R5a schema26 grants begin.\n', '-- R5a schema26 grants end.\n\n'),
    ):
        prefix, rest = permissions.split(begin_marker, 1)
        permissions = prefix + rest.split(end_marker, 1)[1]
    historical = permissions.replace(',\n    record_auth_access_v25(uuid,text,text,text,bigint,bigint)', '')
    assert hashlib.sha256(historical.encode()).hexdigest() == '85c88b1b89bb511401709dcaaa56537f98a9e74588460a90c6d944246e2f00d1'
