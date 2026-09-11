"""v28 upgrade, fresh schema equality and exact grants for recipe import commit."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from test_component_metadata_master_lock_db import (  # noqa: F401
    PERMISSIONS, SCHEMA, app_engine, installed_pg16, pg16, seeded_pg16,
)

PUBLIC = {'commit_recipe_import_batch_v29'}
PRIVATE = {'recipe_import_head_source_v29', 'recipe_import_recipe_payload_v29'}


def structure(c):
    return (
        c.execute(text("""SELECT proname,pg_get_function_identity_arguments(oid),prosrc,prosecdef,proconfig,
            has_function_privilege('cafeteria_app',oid,'EXECUTE') FROM pg_proc
            WHERE pronamespace='cafeteria'::regnamespace AND proname LIKE '%_v29' ORDER BY proname""")).all(),
        c.execute(text("""SELECT column_name,data_type,is_nullable FROM information_schema.columns
            WHERE table_schema='cafeteria' AND table_name='recipe_import_batches'
            AND column_name='imported_result'""")).all(),
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
        if migration.version <= 28:
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
                    'WHERE version<=28 ORDER BY to_jsonb(t)::text'
                )).all() == rows
            else:
                assert c.execute(text(
                    f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
                )).all() == rows
        assert c.execute(text('SELECT max(version) FROM cafeteria.schema_migrations')).scalar_one() == 29
        migrated = structure(c)
        assert c.execute(text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='cafeteria' AND table_name='recipe_import_batches' "
            "AND column_name='imported_result')"
        )).scalar_one()
    after_sequences = dict(rows_and_sequences(pg16)[1])
    assert dict(before[1]).items() <= after_sequences.items()
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
            WHERE n.nspname='cafeteria' AND p.proname LIKE '%_v29'""")).mappings().all()
        assert {r['proname'] for r in rows} == PUBLIC | PRIVATE
        for row in rows:
            assert row['app'] == (row['proname'] in PUBLIC)
            assert row['prosecdef'] == (row['proname'] in PUBLIC)
            assert row['proconfig'] == ['search_path=pg_catalog, cafeteria, pg_temp'] and row['same_owner']
            assert not any(row[key] for key in ('backup', 'issuer', 'public'))
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as c:
            c.execute(text('UPDATE cafeteria.recipe_import_batches SET imported_result=NULL WHERE false'))
    assert error.value.orig.sqlstate == '42501'
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as c:
            c.execute(text(
                'SELECT cafeteria.recipe_import_head_source_v29('
                'NULL::cafeteria.recipe_import_batches,NULL::cafeteria.recipe_import_candidates)'
            ))
    assert error.value.orig.sqlstate == '42501'
