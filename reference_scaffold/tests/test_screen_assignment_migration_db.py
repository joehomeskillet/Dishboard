"""Schema22→23/fresh parity without changing any existing business rows."""
import hashlib

from sqlalchemy import text

from cafeteria import db as database
from test_component_metadata_master_lock_db import pg16 as pg16, SCHEMA, PERMISSIONS
from test_master_data_db import make_actor
from test_screen_assignment_writer_db import SIGNATURE, state, isolated_database as isolated_database


def contract(connection):
    return connection.execute(text("""SELECT p.prosrc,p.prosecdef,p.proconfig,p.proowner=n.nspowner,
        has_function_privilege('cafeteria_app',p.oid,'EXECUTE'),
        has_function_privilege('cafeteria_backup',p.oid,'EXECUTE'),
        has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE'),
        has_function_privilege('public',p.oid,'EXECUTE'),
        has_table_privilege('cafeteria_app','cafeteria.audit_events','INSERT'),
        has_sequence_privilege('cafeteria_app','cafeteria.audit_events_id_seq','USAGE,UPDATE')
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE p.oid=to_regprocedure(:signature)"""), {'signature': SIGNATURE}).one()


def test_schema22_upgrade_preserves_settings_identity_and_migrations_matches_fresh(pg16):
    plan = database.migration_plan(SCHEMA)
    assert plan[-1].version == 23 and plan[-1].path.name == '0020_v22_to_v23.sql'
    for migration in plan:
        if migration.version <= 22:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    make_actor(pg16, 'Cafeteria.Admin')
    with pg16.begin() as connection:
        connection.execute(text("""INSERT INTO cafeteria.settings(setting_key,setting_value)
            VALUES('screen_assignment.v1.patient.web.week',CAST(:assignment AS jsonb)),
                  ('unrelated.sentinel',CAST(:unrelated AS jsonb))"""),
            {'assignment': '{"unchanged_invalid_sentinel":true}', 'unrelated': '{"unchanged":true}'})
        entries = connection.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m ORDER BY version')).all()
    before = state(pg16)
    database.run_migrations(pg16, SCHEMA)
    database._execute_script(pg16, str(PERMISSIONS))
    database._execute_script(pg16, str(PERMISSIONS))
    assert state(pg16) == before
    with pg16.connect() as connection:
        assert connection.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m WHERE version<=22 ORDER BY version')).all() == entries
        assert connection.execute(text('SELECT name,checksum_sha256 FROM cafeteria.schema_migrations WHERE version=23')).one() == (
            plan[-1].path.name, hashlib.sha256(plan[-1].path.read_bytes()).hexdigest())
        expected = contract(connection)
    with pg16.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert contract(connection) == expected
