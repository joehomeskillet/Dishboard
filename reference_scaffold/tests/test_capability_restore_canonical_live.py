"""Real product backup/controller recovery; no toy or replacement SQL helpers."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest
from psycopg import sql
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from test_database_invariants import (
    APP_PASSWORD, BACKUP_PASSWORD, ISSUER_PASSWORD, DATABASE_URL, ROOT,
    _dated_snapshot, _insert_revision, _insert_week, _user_id,
)

pytestmark = pytest.mark.skipif(
    not os.getenv('CANONICAL_RESTORE_CONTAINER') or not DATABASE_URL,
    reason='Requires explicitly owned disposable Docker PostgreSQL and TEST_DATABASE_URL.',
)


def business_hashes(engine: Engine) -> dict[str, str]:
    result = {}
    with engine.connect() as connection:
        names = connection.execute(text("""SELECT tablename FROM pg_tables
            WHERE schemaname='cafeteria' AND tablename NOT IN
            ('auth_capability_secrets','auth_capability_nonces','schema_migrations','audit_events')
            ORDER BY tablename""")).scalars().all()
        for name in names:
            query = sql.SQL("SELECT md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'')) FROM {} t").format(sql.Identifier('cafeteria', name))
            result[name] = connection.exec_driver_sql(query.as_string()).scalar_one()
    return result


def test_canonical_backup_migrate_ensure_permissions_reset(tmp_path: Path) -> None:
    assert DATABASE_URL
    container = os.environ['CANONICAL_RESTORE_CONTAINER']
    assert container.startswith('menuplan-pg') and 'restore-fix' in container
    source_name = 'restore_guard_' + uuid4().hex[:8]
    run_id = 'canonical'
    candidate_name = source_name + '_restore_candidate_' + run_id
    base = make_url(DATABASE_URL)
    owner = create_engine(base, poolclass=NullPool)
    source = create_engine(base.set(database=source_name), poolclass=NullPool)
    candidate = create_engine(base.set(database=candidate_name), poolclass=NullPool)
    holder = None
    token = None

    def command(*args: str, role: str = 'postgres') -> list[str]:
        return ['docker', 'exec', '-e', 'POSTGRES_HOST=/socket', '-e',
                'POSTGRES_USER=' + role, '-e', 'POSTGRES_DB=' + source_name,
                '-e', 'POSTGRES_PASSWORD_FILE=/dev/null', '-e',
                'BACKUP_DIR=/tmp/' + source_name, container,
                '/bin/sh', '/source/deployment/postgres-backup.sh', *args]

    def script(*args: str, role: str = 'postgres') -> str:
        result = subprocess.run(command(*args, role=role), capture_output=True, text=True)
        # Do not include argv or controller ownership tokens in failures.
        if result.returncode:
            pytest.fail(result.stderr, pytrace=False)
        return result.stdout.strip()

    with owner.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.exec_driver_sql(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(source_name)).as_string())
    try:
        database.provision_database_roles(source, app_password=APP_PASSWORD,
            backup_password=BACKUP_PASSWORD, auth_issuer_password=ISSUER_PASSWORD)
        plan = database.migration_plan(ROOT / 'database/schema.sql')
        for migration in plan:
            if migration.version < 24:
                database._execute_migration(source, migration)
        database._execute_script(source, str(ROOT / 'database/seed.sql'))
        database._execute_script(source, str(ROOT / 'database/permissions.sql'))
        revisions = []
        for start, code in [('2026-11-16', 'PAT-2026-KW47-R1'), ('2026-11-23', 'PAT-2026-KW48-R1')]:
            week = _insert_week(source, 'patient', 'published', start)
            payload = _dated_snapshot('patient', start)
            payload['revision_id'] = code
            revisions.append(_insert_revision(source, week, 'patient', snapshot=payload))
        actor = _user_id(source, database.DEMO_USER_PUBLIC_ID)
        used = database.issue_publication_capability(source, actor, revisions[0])
        database.withdraw_publication_revision(source, revisions[0], used, 'Before canonical backup')
        unused = database.issue_publication_capability(source, actor, revisions[1])
        expected = business_hashes(source)
        with source.connect() as connection:
            server = connection.execute(text('SHOW server_version_num')).scalar_one()
            old_ledger = connection.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m ORDER BY version')).all()
        archive = script('once', role='cafeteria_backup')
        toc = subprocess.run(['docker', 'exec', container, 'pg_restore', '--list', archive],
                             capture_output=True, text=True, check=True).stdout
        assert 'auth_capability_secrets' not in toc and 'auth_capability_nonces' not in toc
        token = script('restore-acquire', run_id)
        holder = subprocess.Popen(command('restore-hold', run_id, token),
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with owner.connect() as connection:
                held = connection.execute(text("""SELECT last_event IN ('lease_held','lease_heartbeat')
                    FROM public.menuplan_restore_control WHERE database_name=:name"""), {'name': source_name}).scalar_one()
            if held:
                break
            time.sleep(0.1)
        assert held, 'Owned restore holder did not acquire its lease'
        assert script('restore-stage', archive, archive + '.sha256', run_id, token) == candidate_name
        with candidate.connect() as connection:
            assert connection.execute(text("""SELECT to_regclass('cafeteria.auth_capability_secrets') IS NULL
                AND to_regclass('cafeteria.auth_capability_nonces') IS NULL""")).scalar_one()
        assert business_hashes(candidate) == expected
        # This is the supported migration path, never a post-restore function patch.
        database.run_migrations(candidate, ROOT / 'database/schema.sql')
        script('restore-state', run_id, token, 'migrated')
        script('restore-ensure-auth-capabilities', run_id, token, candidate_name)
        script('restore-ensure-auth-capabilities', run_id, token, candidate_name)
        database._execute_script(candidate, str(ROOT / 'database/permissions.sql'))
        script('restore-reset-auth-capabilities', run_id, token, candidate_name)
        assert business_hashes(candidate) == expected
        with candidate.connect() as connection:
            assert connection.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m WHERE version<24 ORDER BY version')).all() == old_ledger
            assert connection.execute(text('SELECT max(version) FROM cafeteria.schema_migrations')).scalar_one() == 24
            assert connection.execute(text("""SELECT (SELECT count(*) FROM cafeteria.auth_capability_secrets)=1
                AND (SELECT count(*) FROM cafeteria.auth_capability_secrets WHERE id=1 AND active AND octet_length(secret)=32)=1
                AND NOT EXISTS (SELECT 1 FROM cafeteria.auth_capability_nonces)
                AND (SELECT count(*) FROM cafeteria.audit_events WHERE action='auth_capability.hard_reset')=1""")).scalar_one()
            for role in ('cafeteria_app', 'cafeteria_backup', 'cafeteria_auth_issuer'):
                assert connection.execute(text("""SELECT
                    NOT has_table_privilege(:role,'cafeteria.auth_capability_secrets','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')
                    AND NOT has_table_privilege(:role,'cafeteria.auth_capability_nonces','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')
                    AND NOT has_function_privilege(:role,'cafeteria.ensure_auth_capability_state()','EXECUTE')
                    AND NOT has_function_privilege(:role,'cafeteria.hard_reset_auth_capability_state()','EXECUTE')"""), {'role': role}).scalar_one()
        for revision, old_token in zip(revisions, (used, unused), strict=True):
            with pytest.raises(DBAPIError, match='ungültig oder abgelaufen'):
                database.withdraw_publication_revision(candidate, revision, old_token, 'Old capability rejected')
        fresh = database.issue_publication_capability(candidate, actor, revisions[1])
        database.withdraw_publication_revision(candidate, revisions[1], fresh, 'Fresh capability accepted')
        with pytest.raises(DBAPIError, match='Nonce wurde bereits verwendet'):
            database.withdraw_publication_revision(candidate, revisions[1], fresh, 'Fresh replay rejected')
        evidence = {
            'server_version_num': server, 'business_tables_preserved': len(expected),
            'source_schema_sha256': hashlib.sha256((ROOT / 'database/schema.sql').read_bytes()).hexdigest(),
            'migration_sha256': hashlib.sha256(plan[-1].path.read_bytes()).hexdigest(),
            'historical_ledger_preserved': len(old_ledger), 'canonical_controller_restore': 'passed',
        }
        print(evidence)
        (tmp_path / 'canonical-restore-receipt.txt').write_text(repr(evidence), encoding='utf-8')
    finally:
        source.dispose()
        candidate.dispose()
        if token is not None and holder is not None:
            with owner.connect() as connection:
                lifecycle = connection.execute(text('SELECT lifecycle FROM public.menuplan_restore_control WHERE database_name=:name'), {'name': source_name}).scalar_one()
            if lifecycle != 'aborted':
                script('restore-abort', run_id, token)
        if holder is not None:
            holder.terminate()
            holder.wait(timeout=10)
        with owner.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(source_name)).as_string())
        owner.dispose()
