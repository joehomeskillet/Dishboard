"""Real upgrade/fresh parity and preservation of existing application records."""
from sqlalchemy import text

from cafeteria import db as database
from test_master_data_db import make_actor
from test_component_metadata_master_lock_db import pg16 as pg16
from test_component_metadata_master_lock_db import SCHEMA, PERMISSIONS


def catalog(connection):
    return connection.execute(text('''SELECT p.proname,pg_get_function_identity_arguments(p.oid),p.prosrc,p.prosecdef,p.proconfig,
        has_function_privilege('cafeteria_app',p.oid,'EXECUTE'),has_function_privilege('public',p.oid,'EXECUTE')
        FROM pg_proc p WHERE p.pronamespace='cafeteria'::regnamespace AND p.proname LIKE '%_v22'
        ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)''')).all()


def test_schema21_upgrade_preserves_old_data_and_matches_fresh_schema22(pg16):
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 21:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    make_actor(pg16)
    tables = ('users', 'application_roles', 'user_role_cache', 'locations', 'menu_weeks', 'publication_revisions',
              'foods', 'measurement_units', 'audit_events', 'settings')
    with pg16.connect() as current:
        before = {table: current.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).all() for table in tables}
    database.run_migrations(pg16, SCHEMA)
    database._execute_script(pg16, str(PERMISSIONS))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as current:
        for table in tables:
            assert current.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).all() == before[table]
        expected = catalog(current)
        assert current.execute(text('SELECT max(version) FROM cafeteria.schema_migrations')).scalar_one() == 25
    with pg16.begin() as current:
        current.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as current:
        assert catalog(current) == expected
