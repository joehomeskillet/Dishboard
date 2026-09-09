"""Fail-closed upgrade, explicit old-version backfill and exact schema27 privileges."""
from concurrent.futures import ThreadPoolExecutor
import json
from queue import Queue
import time

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from prepared_food_fixtures import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, SCHEMA, PERMISSIONS, execute, create_food,
)
from prepared_food_fixtures import prepared as prepared
from test_master_data_db import make_actor

PUBLIC = {'create_food_v27', 'update_food_v27', 'freeze_recipe_v27', 'recipe_dependency_preview_v27'}
PRIVATE = {'lock_prepared_graph_v27', 'recipe_snapshot_complete_v27', 'check_prepared_graph_v27',
           'assert_food_complete_v27', 'enforce_food_complete_v27', 'food_save_v27',
           'check_prepared_snapshot_v27', 'merge_prepared_node_v27'}


def structure(c):
    return (
        c.execute(text("""SELECT proname,pg_get_function_identity_arguments(oid),prosrc,prosecdef,proconfig,
            has_function_privilege('cafeteria_app',oid,'EXECUTE') FROM pg_proc
            WHERE pronamespace='cafeteria'::regnamespace AND proname LIKE '%_v27' ORDER BY proname""")).all(),
        c.execute(text("""SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid='cafeteria.foods'::regclass ORDER BY conname""")).all(),
        c.execute(text("""SELECT tgname,pg_get_triggerdef(oid) FROM pg_trigger WHERE tgname LIKE '%complete_v27'
            ORDER BY tgname""")).all(),
    )


def rows_and_sequences(owner):
    with owner.connect() as c:
        tables = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='cafeteria' ORDER BY tablename")).scalars().all()
        rows = {name: c.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{name} t ORDER BY to_jsonb(t)::text')).all()
                for name in tables}
        sequences = c.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='cafeteria' ORDER BY sequencename")).all()
        return rows, sequences


def old_schema(owner):
    for migration in database.migration_plan(SCHEMA):
        if migration.version <= 26:
            database._execute_migration(owner, migration)
    database._execute_script(owner, str(SCHEMA.parent / 'seed.sql'))
    actor = make_actor(owner)
    with owner.connect() as c:
        location = c.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one()
    return {'actor': actor.user_id, 'authz': actor.authz_version, 'location': location}


def wait_blocked(owner, pid):
    deadline = time.monotonic() + 3
    with owner.connect() as c:
        while time.monotonic() < deadline:
            blockers = c.execute(text('SELECT pg_blocking_pids(:pid)'), {'pid': pid}).scalar_one()
            if blockers:
                return blockers
            time.sleep(0.01)
    pytest.fail('Expected PostgreSQL blocking state was not observed.')


def test_old_food_gap_stops_before_ddl_ledger_sequences_then_explicit_backfill(pg16):  # noqa: F811
    ids = old_schema(pg16)
    old = execute(pg16, "SELECT cafeteria.create_food_v21(:actor,:authz,:location,NULL,NULL,'{\"name\":\"Altbestand\",\"base_unit_code\":\"G\"}')", ids)
    before = rows_and_sequences(pg16)
    migration = database.migration_plan(SCHEMA)[-1]
    with pytest.raises(psycopg.Error) as error:
        database._execute_migration(pg16, migration)
    assert error.value.sqlstate == '55000'
    assert error.value.diag.message_detail == 'food_storage_preflight'
    assert '1 Zutaten' in error.value.diag.message_primary and old['public_id'] in error.value.diag.message_primary
    assert rows_and_sequences(pg16) == before
    with pg16.connect() as c:
        assert not c.execute(text("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='cafeteria' AND table_name='foods' AND column_name='prepared_recipe_revision_id')")).scalar_one()
    with pg16.begin() as c:
        c.execute(text('SET LOCAL ROLE cafeteria_app'))
        storage = c.execute(text("SELECT cafeteria.create_storage_location_v21(:actor,:authz,:location,NULL,NULL,'{\"code\":\"REAL\",\"name\":\"Expliziter Lagerort\"}')"), ids).scalar_one()
        c.execute(text('''SELECT cafeteria.replace_food_storage_locations_v21(:actor,:authz,:location,
            CAST(:target AS uuid),:version,CAST(:payload AS jsonb))'''),
            ids | {'target': old['public_id'], 'version': old['row_version'],
                   'payload': json.dumps({'storage_locations': [storage['public_id']]})})
    before_upgrade = rows_and_sequences(pg16)
    database.run_migrations(pg16, SCHEMA)
    database._execute_script(pg16, str(PERMISSIONS))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        for table, rows in before_upgrade[0].items():
            if table == 'schema_migrations':
                assert c.execute(text('SELECT to_jsonb(t)::text FROM cafeteria.schema_migrations t WHERE version<=26 ORDER BY to_jsonb(t)::text')).all() == rows
            else:
                projection = "to_jsonb(t)-'prepared_recipe_revision_id'" if table == 'foods' else 'to_jsonb(t)'
                assert c.execute(text(f'SELECT ({projection})::text FROM cafeteria.{table} t ORDER BY ({projection})::text')).all() == rows
        assert c.execute(text('SELECT max(version) FROM cafeteria.schema_migrations')).scalar_one() == 27
        migrated = structure(c)
    assert rows_and_sequences(pg16)[1] == before_upgrade[1]
    with pg16.begin() as c:
        c.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        assert structure(c) == migrated


def test_migration_waits_for_old_writer_and_rechecks_committed_gap(pg16):  # noqa: F811
    ids = old_schema(pg16)
    started = Queue()
    migration = database.migration_plan(SCHEMA)[-1]
    def upgrade():
        try:
            with pg16.begin() as c:
                started.put(c.execute(text('SELECT pg_backend_pid()')).scalar_one())
                c.connection.driver_connection.execute(migration.path.read_text())
        except DBAPIError as error:
            return error.orig.sqlstate
        except Exception as error:
            return getattr(error, 'sqlstate', None)
        return 'unexpected success'
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pg16.begin() as c:
            c.execute(text("SELECT cafeteria.create_food_v21(:actor,:authz,:location,NULL,NULL,'{\"name\":\"Wartender Altwriter\",\"base_unit_code\":\"G\"}')"), ids)
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            future = pool.submit(upgrade)
            assert blocker in wait_blocked(pg16, started.get(timeout=3))
        assert future.result(timeout=8) == '55000'
    with pg16.connect() as c:
        assert c.execute(text('SELECT max(version) FROM cafeteria.schema_migrations')).scalar_one() == 26
        assert c.execute(text('SELECT count(*) FROM cafeteria.foods')).scalar_one() == 1


def test_exact_new_acl_and_legacy_final_invariant_closure(prepared):
    owner, engine, ids = prepared
    database._execute_script(owner, str(PERMISSIONS))
    database._execute_script(owner, str(PERMISSIONS))
    with owner.connect() as c:
        rows = c.execute(text("""SELECT p.proname,p.prosecdef,p.proconfig,
            pg_get_userbyid(p.proowner)=pg_get_userbyid(n.nspowner) AS same_owner,
            has_function_privilege('cafeteria_app',p.oid,'EXECUTE') AS app,
            has_function_privilege('cafeteria_backup',p.oid,'EXECUTE') AS backup,
            has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE') AS issuer,
            EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='cafeteria' AND p.proname LIKE '%_v27'""")).mappings().all()
        assert {r['proname'] for r in rows} == PUBLIC | PRIVATE
        for row in rows:
            assert row['app'] == (row['proname'] in PUBLIC)
            assert row['prosecdef'] == (row['proname'] in PUBLIC | {'food_save_v27', 'enforce_food_complete_v27'})
            assert row['proconfig'] == ['search_path=pg_catalog, cafeteria, pg_temp'] and row['same_owner']
            assert not any(row[key] for key in ('backup', 'issuer', 'public'))
    food = create_food(engine, ids)
    with owner.connect() as c:
        assert c.execute(text("SELECT confdeltype FROM pg_constraint WHERE conname='foods_prepared_recipe_scope_fk'")).scalar_one() == 'r'
    for table in ('foods', 'food_storage_locations', 'recipes', 'recipe_revisions', 'audit_events'):
        with pytest.raises(DBAPIError) as error:
            with engine.begin() as c:
                c.execute(text(f'DELETE FROM cafeteria.{table} WHERE false'))
        assert error.value.orig.sqlstate == '42501'
    for active in (False, True):
        food = execute(engine, '''SELECT cafeteria.set_food_active_v21(:actor,:authz,:location,
            CAST(:target AS uuid),:version,CAST(:payload AS jsonb))''',
            ids | {'target': food['public_id'], 'version': food['row_version']}, {'active': active})
        assert food['row_version'] == (2 if not active else 3)
