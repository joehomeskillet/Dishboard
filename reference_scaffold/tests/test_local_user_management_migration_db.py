"""Schema19 keeps existing identities and the exact restricted issuer contract."""
from __future__ import annotations

import hashlib

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from cafeteria import db as database
from test_component_metadata_master_lock_db import PERMISSIONS, SCHEMA, pg16  # noqa: F401

SIGNATURES = {
    'sync_entra_user(uuid,uuid,text,text,text,text,text[])',
    'issue_publication_capability(bigint,bigint,interval)',
    'create_local_user_v19(bigint,bigint,text,text,text,text[])',
    'replace_local_roles_v19(bigint,bigint,uuid,bigint,text[])',
    'reset_local_password_v19(bigint,bigint,uuid,bigint,text)',
    'deactivate_local_user_v19(bigint,bigint,uuid,bigint)',
    'reactivate_local_user_v19(bigint,bigint,uuid,bigint)',
    'local_user_command_context_v19(bigint,text,uuid,text)',
}


def _functions(engine):
    with engine.connect() as connection:
        return connection.execute(text('''SELECT p.proname, pg_get_function_identity_arguments(p.oid),
            p.prosrc, p.prosecdef, p.proconfig,
            has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE'),
            has_function_privilege('cafeteria_app',p.oid,'EXECUTE'),
            has_function_privilege('public',p.oid,'EXECUTE')
            FROM pg_proc p WHERE p.pronamespace='cafeteria'::regnamespace
            AND (p.proname LIKE '%_v19' OR p.proname='bootstrap_first_local_admin')
            ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)''')).all()


def _identities(engine):
    with engine.connect() as connection:
        return {name: connection.execute(text('SELECT to_jsonb(t) FROM cafeteria.' + name +
            ' t ORDER BY to_jsonb(t)::text')).scalars().all()
            for name in ('users', 'local_credentials', 'user_role_cache', 'audit_events')}


def test_v18_upgrade_preserves_every_identity_field_and_matches_fresh_schema(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    assert [entry.version for entry in plan] == list(range(4, 21))
    historical = [migration for migration in plan if migration.version <= 18]
    assert historical[-1].version == 18
    for migration in historical:
        database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    with pg16.begin() as connection:
        user_id = connection.execute(text("INSERT INTO cafeteria.users(auth_provider,display_name) "
            "VALUES ('local','Existing Admin') RETURNING id")).scalar_one()
        connection.execute(text("INSERT INTO cafeteria.local_credentials(user_id,username,password_hash) "
            "VALUES (:id,'existing.admin',:hash)"),
            {'id': user_id, 'hash': generate_password_hash('Vorhandene!Wolken82Kette')})
        connection.execute(text("INSERT INTO cafeteria.user_role_cache(user_id,role_code,source) "
            "VALUES (:id,'Cafeteria.Admin','local')"), {'id': user_id})
        connection.execute(text("INSERT INTO cafeteria.audit_events(actor_user_id,action,entity_type,details) "
            "VALUES (:id,'auth.local_user_provisioned','user',jsonb_build_object('target_user_id',CAST(:id AS bigint)))"),
            {'id': user_id})
    before = _identities(pg16)
    database.run_migrations(pg16, SCHEMA)
    assert _identities(pg16) == before
    for _ in range(2):
        database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        ledger = connection.execute(text('SELECT version,name,checksum_sha256 '
            'FROM cafeteria.schema_migrations ORDER BY version')).all()
        assert ledger == [(entry.version, entry.path.name, hashlib.sha256(entry.path.read_bytes()).hexdigest())
                          for entry in plan]
        grants = connection.execute(text("SELECT p.oid::regprocedure::text FROM pg_proc p "
            "WHERE p.pronamespace='cafeteria'::regnamespace "
            "AND has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE')")).scalars().all()
        assert {signature.removeprefix('cafeteria.') for signature in grants} == SIGNATURES
        assert connection.execute(text("SELECT to_regprocedure('cafeteria.local_user_command_context_v19(text,text)')")).scalar_one() is None
    migrated = _functions(pg16)
    with pg16.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    assert _functions(pg16) == migrated
