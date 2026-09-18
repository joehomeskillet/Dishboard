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
    import re
    permissions = PERMISSIONS.read_text(encoding='utf-8')
    permissions = re.sub(r'[ \t]*menu_service_courses,\s*menu_item_course_exceptions,?', '', permissions)
    permissions = re.sub(r'[ \t]*kitchen_events,\s*kitchen_event_demand_items,?', '', permissions)
    permissions = re.sub(r',\s*TO cafeteria_app;', '\nTO cafeteria_app;', permissions)
    permissions = re.sub(r'GRANT SELECT, INSERT, UPDATE ON inventory_accounts TO cafeteria_app;\n', '', permissions)
    permissions = re.sub(r'GRANT SELECT, INSERT ON inventory_movements TO cafeteria_app;\n', '', permissions)
    permissions = re.sub(r'GRANT SELECT, INSERT ON prepared_batch_runs, calculation_receipts TO cafeteria_app;\n', '', permissions)
    permissions = re.sub(r'GRANT SELECT ON prepared_batch_runs, calculation_receipts TO cafeteria_backup;\n', '', permissions)
    permissions = re.sub(r'GRANT SELECT ON SEQUENCE prepared_batch_runs_id_seq, calculation_receipts_id_seq TO cafeteria_backup;\n', '', permissions)
    permissions = re.sub(r'REVOKE ALL ON FUNCTION calculation_receipt_protect_v41\(\) FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;\n', '', permissions)
    permissions = re.sub(r'GRANT SELECT ON TO cafeteria_backup;\n', '', permissions)
    permissions = re.sub(r'GRANT SELECT ON SEQUENCE menu_service_courses_id_seq, menu_item_course_exceptions_id_seq\nTO cafeteria_backup;\n', '', permissions)
    historical_sql = re.sub(r'-- Schema(3[2-9]|[4-9][0-9]).*?grants end\.\n*', '', permissions, flags=re.DOTALL)
    historical = tmp_path / 'permissions-v31.sql'
    historical.write_text(historical_sql, encoding='utf-8')
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
    patient_key_v31_sql = (
        SCHEMA.parent / 'migrations' / '0017_v19_to_v20.sql'
    ).read_text(encoding='utf-8')
    patient_key_v31_sql = patient_key_v31_sql[
        patient_key_v31_sql.index('CREATE OR REPLACE FUNCTION patient_key_is_forbidden(k text)'):
    ]
    patient_key_v31_body = patient_key_v31_sql.split('AS $$', 1)[1].split('$$;', 1)[0]
    migrated_patient_keys = [
        row for row in migrated if row.proname == 'patient_key_is_forbidden'
    ]
    assert len(migrated_patient_keys) == 1
    assert migrated_patient_keys[0].prosrc == patient_key_v31_body
    with pg16.begin() as c:
        c.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as c:
        assert_acl(c)
        bootstrap = structure(c)
        bootstrap_patient_keys = [
            row for row in bootstrap if row.proname == 'patient_key_is_forbidden'
        ]
        assert len(bootstrap_patient_keys) == 1
        assert bootstrap_patient_keys[0][:3] + bootstrap_patient_keys[0][4:] == (
            migrated_patient_keys[0][:3] + migrated_patient_keys[0][4:]
        )
        historical_exclusions = V32_FUNCTIONS | {'patient_key_is_forbidden'}
        migrated_names = {row.proname for row in migrated}
        bootstrap_names = {row.proname for row in bootstrap}
        historical_exclusions.update(bootstrap_names - migrated_names)
        assert [row for row in bootstrap if row.proname not in historical_exclusions] == [
            row for row in migrated if row.proname != 'patient_key_is_forbidden'
        ]


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
