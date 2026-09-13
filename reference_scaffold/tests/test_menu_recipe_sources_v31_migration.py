"""Historical schema30 -> 31 migration remains immutable and executable."""
# ruff: noqa: F401, F811
import hashlib

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from test_component_metadata_master_lock_db import (
    SCHEMA, PERMISSIONS, pg16, installed_pg16, seeded_pg16, app_engine,
)
from test_rec_import_commit_migration_db import rows_and_sequences

SIGNATURE = 'cafeteria.lock_menu_recipe_sources_v31(bigint,bigint,bigint,bigint[],uuid)'
V32_FUNCTIONS = {
    'create_dish_template_v32',
    'dish_template_mutate_v32',
    'reject_direct_dish_template_update_v32',
    'update_dish_template_v32',
}


def refresh_permissions_v31(engine, tmp_path):
    permissions = PERMISSIONS.read_text(encoding='utf-8')
    start = permissions.index('-- Schema32 accompaniment template grants begin.')
    end = permissions.index('-- Schema32 accompaniment template grants end.')
    historical = tmp_path / 'permissions-v31.sql'
    historical.write_text(
        permissions[:start] + permissions[end + len('-- Schema32 accompaniment template grants end.'):],
        encoding='utf-8',
    )
    database._execute_script(engine, str(historical))


def structure(c):
    return c.execute(text("""SELECT p.proname,pg_get_function_identity_arguments(p.oid),
        pg_get_function_result(p.oid),p.prosrc,p.prosecdef,p.proconfig,p.proowner,p.proacl
        FROM pg_proc p WHERE p.pronamespace='cafeteria'::regnamespace
        ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)""")).all()


def assert_acl(c):
    row = c.execute(text("""SELECT p.prosecdef,p.proconfig,p.proowner=n.nspowner AS same_owner,
        has_function_privilege('cafeteria_app',p.oid,'EXECUTE') AS app,
        has_function_privilege('cafeteria_backup',p.oid,'EXECUTE') AS backup,
        has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE') AS issuer,
        EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
            WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE p.oid=to_regprocedure(:signature)"""), {'signature': SIGNATURE}).mappings().one()
    assert row['prosecdef'] and row['same_owner'] and row['app']
    assert row['proconfig'] == ['search_path=pg_catalog, cafeteria, pg_temp']
    assert not any(row[key] for key in ('backup', 'issuer', 'public'))
    for table in ('recipes', 'recipe_revisions'):
        assert c.execute(text("SELECT has_table_privilege(:role,:table,'SELECT')"),
            {'role': 'cafeteria_app', 'table': 'cafeteria.' + table}).scalar_one()
        for privilege in ('UPDATE', 'DELETE', 'INSERT', 'TRUNCATE', 'TRIGGER', 'REFERENCES'):
            assert not c.execute(text('SELECT has_table_privilege(:role,:table,:privilege)'),
                {'role': 'cafeteria_app', 'table': 'cafeteria.' + table, 'privilege': privilege}).scalar_one()
        for privilege in ('UPDATE', 'INSERT', 'REFERENCES'):
            assert not c.execute(text('SELECT has_any_column_privilege(:role,:table,:privilege)'),
                {'role': 'cafeteria_app', 'table': 'cafeteria.' + table, 'privilege': privilege}).scalar_one()


def test_historical_schema30_upgrade_preserves_data_and_exact_function(
    pg16,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        database,
        'MIGRATION_FILES',
        tuple(entry for entry in database.MIGRATION_FILES if entry[0] <= 31),
    )
    plan = database.migration_plan(SCHEMA)
    assert (plan[-1].version, plan[-1].path.name) == (31, '0028_v30_to_v31.sql')
    for migration in plan[:-1]:
        database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    before = rows_and_sequences(pg16)
    with pg16.connect() as c:
        original_functions = structure(c)
    assert database.run_migrations(pg16, SCHEMA) == plan
    with pg16.connect() as c:
        assert_acl(c)  # The migration itself grants the function, before permissions refresh.
        assert [row for row in structure(c) if row.proname != 'lock_menu_recipe_sources_v31'] == original_functions
        for table, rows in before[0].items():
            predicate = ' WHERE version<=30' if table == 'schema_migrations' else ''
            assert c.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t'
                f'{predicate} ORDER BY to_jsonb(t)::text')).all() == rows
        assert c.execute(text('SELECT checksum_sha256 FROM cafeteria.schema_migrations WHERE version=31')).scalar_one() == hashlib.sha256(plan[-1].path.read_bytes()).hexdigest()
    assert rows_and_sequences(pg16)[1] == before[1]
    assert database.run_migrations(pg16, SCHEMA) == plan
    refresh_permissions_v31(pg16, tmp_path)
    refresh_permissions_v31(pg16, tmp_path)
    with pg16.connect() as c:
        assert_acl(c)
        migrated = structure(c)
    with pg16.begin() as c:
        c.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        assert_acl(c)
        assert [row for row in structure(c) if row.proname not in V32_FUNCTIONS] == migrated


def test_runtime_role_acl_cannot_be_replaced_by_direct_table_locks(seeded_pg16, app_engine):
    database._execute_script(seeded_pg16, str(PERMISSIONS))
    database._execute_script(seeded_pg16, str(PERMISSIONS))
    with seeded_pg16.connect() as c:
        assert_acl(c)
    for table in ('recipes', 'recipe_revisions'):
        for query in (f'SELECT id FROM cafeteria.{table} WHERE false FOR SHARE',
                      f'UPDATE cafeteria.{table} SET public_id=public_id WHERE false',
                      f'DELETE FROM cafeteria.{table} WHERE false'):
            with pytest.raises(DBAPIError) as error:
                with app_engine.begin() as c:
                    assert c.execute(text('SELECT current_user')).scalar_one() == 'cafeteria_app'
                    c.execute(text(query))
            assert error.value.orig.sqlstate == '42501'
