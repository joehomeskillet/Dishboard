"""v27 upgrade, fresh schema equality and exact grants for recipe import batches."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from test_component_metadata_master_lock_db import (  # noqa: F401
    PERMISSIONS, SCHEMA, app_engine, installed_pg16, pg16, seeded_pg16,
)

PUBLIC = {'create_recipe_import_batch_v28', 'update_recipe_import_batch_v28'}
PRIVATE = {
    'recipe_import_protect_v28', 'recipe_import_hash_v28',
    'recipe_import_visible_note_v28', 'recipe_import_save_v28',
}


def structure(c):
    return (
        c.execute(text("""SELECT proname,pg_get_function_identity_arguments(oid),prosrc,prosecdef,proconfig,
            has_function_privilege('cafeteria_app',oid,'EXECUTE') FROM pg_proc
            WHERE pronamespace='cafeteria'::regnamespace AND proname LIKE '%_v28' ORDER BY proname""")).all(),
        c.execute(text("""SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid IN ('cafeteria.recipe_import_batches'::regclass,
                'cafeteria.recipe_import_candidates'::regclass) ORDER BY conname""")).all(),
        c.execute(text("""SELECT tgname,pg_get_triggerdef(oid) FROM pg_trigger
            WHERE tgrelid IN ('cafeteria.recipe_import_batches'::regclass,
                'cafeteria.recipe_import_candidates'::regclass) AND NOT tgisinternal
            ORDER BY tgname""")).all(),
    )


def rows_and_sequences(owner):
    with owner.connect() as c:
        tables = c.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='cafeteria' ORDER BY tablename"
        )).scalars().all()
        rows = {
            name: c.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{name} t ORDER BY to_jsonb(t)::text'
            )).all()
            for name in tables
        }
        sequences = c.execute(text(
            "SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='cafeteria' ORDER BY sequencename"
        )).all()
        return rows, sequences


def test_upgrade_preserves_rows_and_fresh_schema_contract(pg16):  # noqa: F811
    for migration in database.migration_plan(SCHEMA):
        if migration.version <= 27:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    before = rows_and_sequences(pg16)
    database.run_migrations(pg16, SCHEMA)
    database._execute_script(pg16, str(PERMISSIONS))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        for table, rows in before[0].items():
            if table == 'schema_migrations':
                assert c.execute(text(
                    'SELECT to_jsonb(t)::text FROM cafeteria.schema_migrations t '
                    'WHERE version<=27 ORDER BY to_jsonb(t)::text'
                )).all() == rows
            else:
                assert c.execute(text(
                    f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
                )).all() == rows
        assert c.execute(text('SELECT max(version) FROM cafeteria.schema_migrations')).scalar_one() == 28
        migrated = structure(c)
        assert c.execute(text(
            "SELECT to_regclass('cafeteria.recipe_import_batches') IS NOT NULL"
        )).scalar_one()
    after_sequences = dict(rows_and_sequences(pg16)[1])
    assert dict(before[1]).items() <= after_sequences.items()
    assert 'recipe_import_batches_id_seq' in after_sequences
    with pg16.begin() as c:
        c.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        assert structure(c) == migrated


def test_exact_acl_and_no_app_dml(seeded_pg16, app_engine):  # noqa: F811
    owner, engine = seeded_pg16, app_engine
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
            WHERE n.nspname='cafeteria' AND p.proname LIKE '%_v28'""")).mappings().all()
        assert {r['proname'] for r in rows} == PUBLIC | PRIVATE
        for row in rows:
            assert row['app'] == (row['proname'] in PUBLIC)
            assert row['prosecdef'] == (row['proname'] in PUBLIC | {'recipe_import_save_v28'})
            assert row['proconfig'] == ['search_path=pg_catalog, cafeteria, pg_temp'] and row['same_owner']
            assert not any(row[key] for key in ('backup', 'issuer', 'public'))
    for table in ('recipe_import_batches', 'recipe_import_candidates'):
        with pytest.raises(DBAPIError) as error:
            with engine.begin() as c:
                c.execute(text(f'DELETE FROM cafeteria.{table} WHERE false'))
        assert error.value.orig.sqlstate == '42501'
