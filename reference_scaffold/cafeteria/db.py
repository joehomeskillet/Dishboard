from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .database_roles import (
    provision_database_roles as _provision_database_roles,
    runtime_role_hardening_status,
    terminate_role_sessions as _default_terminate_role_sessions,
)
from .patient_payload import PROFILES, validate_snapshot_payload

SCHEMA_VERSION = 16
APPLICATION_VERSION = 'dishboard-schema-v16'
SYSTEM_USER_PUBLIC_ID = '00000000-0000-0000-0000-000000000001'
DEMO_USER_PUBLIC_ID = '00000000-0000-0000-0000-000000000002'


@dataclass(frozen=True)
class Migration:
    version: int
    path: Path
    checksum_sha256: str


MIGRATION_FILES = (
    (4, '0001_initial_postgresql.sql'),
    (5, '0002_profile_publication_and_local_auth.sql'),
    (6, '0003_patient_key_and_withdrawal_contracts.sql'),
    (7, '0004_patient_key_lock_and_capability_contracts.sql'),
    (8, '0005_least_privilege_identity_contracts.sql'),
    (9, '0006_auth_issuer_and_local_login.sql'),
    (10, '0007_auth_security_hardening.sql'),
    (11, '0008_auth_final_hardening.sql'),
    (12, '0009_bootstrap_first_local_admin.sql'),
    (13, '0010_v12_to_v13.sql'),
    (14, '0011_v13_to_v14.sql'),
    (15, '0012_v14_to_v15.sql'),
    (16, '0013_v15_to_v16.sql'),
)
MIGRATION_LOCK_ID = 731_905_005
DEFAULT_CAPABILITY_TTL = timedelta(minutes=5)
MAX_CAPABILITY_TTL = timedelta(minutes=15)
ENTRA_APPLICATION_ROLES = frozenset({
    'Cafeteria.Editor',
    'Cafeteria.Publisher',
    'Cafeteria.Admin',
})
LOCAL_USERNAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9._-]{2,63}$')
_terminate_role_sessions = _default_terminate_role_sessions


def create_database_engine(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: int = 10,
    statement_timeout_ms: int = 15_000,
    lock_timeout_ms: int = 5_000,
    idle_in_transaction_timeout_ms: int = 30_000,
) -> Engine:
    options = (
        '-c search_path=cafeteria,public '
        '-c timezone=UTC '
        f'-c statement_timeout={statement_timeout_ms} '
        f'-c lock_timeout={lock_timeout_ms} '
        f'-c idle_in_transaction_session_timeout={idle_in_transaction_timeout_ms}'
    )
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        connect_args={'options': options, 'application_name': 'suedhang-menuplanung'},
    )


def init_app_database(app: Any) -> Engine:
    engine = create_database_engine(
        app.config['DATABASE_URL'],
        pool_size=app.config['DB_POOL_SIZE'],
        max_overflow=app.config['DB_MAX_OVERFLOW'],
        pool_timeout=app.config['DB_POOL_TIMEOUT_SECONDS'],
        statement_timeout_ms=app.config['DB_STATEMENT_TIMEOUT_MS'],
        lock_timeout_ms=app.config['DB_LOCK_TIMEOUT_MS'],
        idle_in_transaction_timeout_ms=app.config['DB_IDLE_IN_TRANSACTION_TIMEOUT_MS'],
    )
    app.extensions['cafeteria_db'] = engine
    issuer_url = app.config.get('AUTH_ISSUER_DATABASE_URL')
    if issuer_url:
        app.extensions['cafeteria_auth_issuer_db'] = create_database_engine(
            issuer_url,
            pool_size=max(1, min(2, app.config['DB_POOL_SIZE'])),
            max_overflow=1,
            pool_timeout=app.config['DB_POOL_TIMEOUT_SECONDS'],
            statement_timeout_ms=app.config['DB_STATEMENT_TIMEOUT_MS'],
            lock_timeout_ms=app.config['DB_LOCK_TIMEOUT_MS'],
            idle_in_transaction_timeout_ms=app.config['DB_IDLE_IN_TRANSACTION_TIMEOUT_MS'],
        )
    return engine


def _driver_connection(raw: Any) -> Any:
    connection = raw.driver_connection
    if connection is None:
        raise RuntimeError('Kein nativer Datenbanktreiber verbunden.')
    return connection


def _execute_script(engine: Engine, path: str) -> None:
    script = Path(path).read_text(encoding='utf-8')
    raw = engine.raw_connection()
    try:
        driver_connection = _driver_connection(raw)
        driver_connection.execute(script, prepare=False)
        driver_connection.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def migration_plan(schema_path: str | Path) -> tuple[Migration, ...]:
    migration_dir = Path(schema_path).resolve().parent / 'migrations'
    plan: list[Migration] = []
    for version, filename in MIGRATION_FILES:
        path = migration_dir / filename
        if not path.is_file():
            raise RuntimeError(f'Migrationsdatei fehlt: {path}')
        plan.append(
            Migration(
                version=version,
                path=path,
                checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return tuple(plan)


def _applied_migrations(engine: Engine) -> dict[int, str]:
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT to_regclass('cafeteria.schema_migrations') IS NOT NULL")
        ).scalar_one()
        if not exists:
            return {}
        rows = connection.execute(
            text('SELECT version, checksum_sha256 FROM cafeteria.schema_migrations ORDER BY version')
        ).all()
    return {int(row.version): str(row.checksum_sha256) for row in rows}


def _execute_migration(engine: Engine, migration: Migration) -> None:
    script = migration.path.read_text(encoding='utf-8').rstrip()
    if not script.endswith('COMMIT;'):
        raise RuntimeError(f'Migration endet nicht mit COMMIT: {migration.path.name}')
    script_without_commit = script[:-len('COMMIT;')]
    raw = engine.raw_connection()
    try:
        driver_connection = _driver_connection(raw)
        driver_connection.execute(script_without_commit, prepare=False)
        driver_connection.execute(
            '''
            INSERT INTO cafeteria.schema_migrations(
                version, name, checksum_sha256, application_version, applied_at
            )
            VALUES (%s, %s, %s, %s, clock_timestamp())
            ''',
            (
                migration.version,
                migration.path.name,
                migration.checksum_sha256,
                APPLICATION_VERSION,
            ),
        )
        driver_connection.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def run_migrations(engine: Engine, schema_path: str | Path) -> tuple[Migration, ...]:
    plan = migration_plan(schema_path)
    lock_raw = engine.raw_connection()
    try:
        lock_connection = _driver_connection(lock_raw)
        lock_connection.execute('SELECT pg_advisory_lock(%s)', (MIGRATION_LOCK_ID,))
        applied = _applied_migrations(engine)
        known_versions = {migration.version for migration in plan}
        unknown_versions = sorted(set(applied) - known_versions)
        if unknown_versions:
            raise RuntimeError(f'Unbekannte Schema-Migrationsversionen: {unknown_versions}')

        for migration in plan:
            recorded_checksum = applied.get(migration.version)
            if recorded_checksum is not None:
                if recorded_checksum != migration.checksum_sha256:
                    raise RuntimeError(
                        f'Checksum-Abweichung für {migration.path.name}: '
                        f'erwartet {recorded_checksum}, gefunden {migration.checksum_sha256}'
                    )
                continue
            if any(version > migration.version for version in applied):
                raise RuntimeError(f'Migrationslücke vor {migration.path.name}.')
            _execute_migration(engine, migration)
            applied[migration.version] = migration.checksum_sha256
    finally:
        _driver_connection(lock_raw).execute('SELECT pg_advisory_unlock(%s)', (MIGRATION_LOCK_ID,))
        lock_raw.close()
    return plan


def provision_database_roles(
    engine: Engine,
    *,
    app_password: str,
    backup_password: str,
    auth_issuer_password: str = '',
) -> None:
    _provision_database_roles(
        engine,
        app_password=app_password,
        backup_password=backup_password,
        auth_issuer_password=auth_issuer_password,
        terminate_sessions=_terminate_role_sessions,
    )


def init_database(
    database_url: str,
    schema_path: str,
    seed_path: str,
    *,
    permissions_path: str | None = None,
    demo_seed_path: str | None = None,
    app_password: str = '',
    backup_password: str = '',
    auth_issuer_password: str = '',
    seed_demo: bool = False,
) -> dict[str, Any]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        provision_database_roles(
            engine,
            app_password=app_password,
            backup_password=backup_password,
            auth_issuer_password=auth_issuer_password,
        )
        run_migrations(engine, schema_path)
        _execute_script(engine, seed_path)
        if seed_demo:
            if not demo_seed_path:
                raise RuntimeError('DEMO_SEED_PATH fehlt.')
            _execute_script(engine, demo_seed_path)
        if permissions_path:
            _execute_script(engine, permissions_path)
        return validate_database(engine)
    finally:
        engine.dispose()


def validate_database(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        connection.execute(text('SET search_path TO cafeteria, public'))
        row = connection.execute(
            text(
                '''
                SELECT
                    current_setting('server_version') AS server_version,
                    COALESCE((SELECT max(version) FROM schema_migrations), 0) AS schema_version,
                    (SELECT count(*) FROM information_schema.tables
                     WHERE table_schema='cafeteria' AND table_type='BASE TABLE') AS table_count,
                    (SELECT count(*) FROM offer_profiles) AS profile_count,
                    (SELECT count(*) FROM allergens) AS allergen_count,
                    (SELECT count(*) FROM active_publications) AS active_publication_count,
                    (SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
                     JOIN pg_namespace n ON n.oid=c.relnamespace
                     WHERE n.nspname='cafeteria' AND NOT i.indisvalid) AS invalid_index_count,
                    (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
                     WHERE n.nspname='cafeteria' AND NOT c.convalidated) AS unvalidated_constraint_count
                '''
            )
        ).mappings().one()
        issuer = connection.execute(
            text(
                '''
                WITH issuer AS (
                    SELECT oid, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                           rolinherit, rolreplication, rolbypassrls, rolconnlimit,
                           rolvaliduntil, rolconfig
                    FROM pg_roles WHERE rolname='cafeteria_auth_issuer'
                ), allowed_functions(signature) AS (
                    VALUES
                      ('cafeteria.sync_entra_user(uuid,uuid,text,text,text,text,text[])'),
                      ('cafeteria.issue_publication_capability(bigint,bigint,interval)'),
                      ('cafeteria.provision_local_user(text,text,text,text,text[])'),
                      ('cafeteria.set_local_password(text,text,text)'),
                      ('cafeteria.disable_local_user(text,text)')
                )
                SELECT
                    EXISTS (SELECT 1 FROM issuer) AS role_exists,
                    COALESCE((SELECT rolcanlogin FROM issuer), false) AS can_login,
                    COALESCE((SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit
                                      OR rolreplication OR rolbypassrls FROM issuer), true)
                        AS has_powerful_attribute,
                    (SELECT count(*) FROM pg_auth_members m, issuer i
                     WHERE m.member=i.oid OR m.roleid=i.oid) AS membership_count,
                    (SELECT count(*) FROM pg_class c
                     JOIN pg_namespace n ON n.oid=c.relnamespace
                     WHERE n.nspname='cafeteria' AND c.relkind IN ('r','p','v','m','f')
                       AND has_table_privilege(
                           'cafeteria_auth_issuer', c.oid,
                           'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
                       )) AS table_privilege_count,
                    (SELECT count(*) FROM pg_class c
                     JOIN pg_namespace n ON n.oid=c.relnamespace
                        WHERE n.nspname='cafeteria'
                          AND CASE WHEN c.relkind='S' THEN has_sequence_privilege(
                              'cafeteria_auth_issuer', c.oid, 'USAGE,SELECT,UPDATE'
                          ) ELSE false END) AS sequence_privilege_count,
                    (SELECT count(*) FROM allowed_functions f
                     WHERE has_function_privilege(
                         'cafeteria_auth_issuer', to_regprocedure(f.signature), 'EXECUTE'
                     )) AS allowed_execute_count,
                    (SELECT count(*) FROM pg_proc p
                     JOIN pg_namespace n ON n.oid=p.pronamespace
                     WHERE n.nspname='cafeteria'
                       AND has_function_privilege('cafeteria_auth_issuer', p.oid, 'EXECUTE')
                       AND p.oid <> ALL(
                           ARRAY(SELECT to_regprocedure(f.signature) FROM allowed_functions f)
                       )) AS unexpected_execute_count
                    ,CASE WHEN EXISTS (SELECT 1 FROM issuer)
                          THEN has_schema_privilege(
                              'cafeteria_auth_issuer', 'cafeteria', 'CREATE'
                          ) ELSE true END AS can_create_cafeteria_schema
                    ,CASE WHEN EXISTS (SELECT 1 FROM issuer)
                          THEN has_schema_privilege(
                              'cafeteria_auth_issuer', 'public', 'CREATE'
                          ) ELSE true END AS can_create_public_schema
                    ,COALESCE((SELECT rolconnlimit FROM issuer), 0) AS connection_limit
                    ,COALESCE(
                        (SELECT rolvaliduntil='infinity'::timestamptz FROM issuer),
                        false
                    ) AS valid_until_infinity
                '''
            )
        ).mappings().one()
        runtime_role_hardening_ready, runtime_role_config_valid = (
            runtime_role_hardening_status(connection)
        )
    result = dict(row)
    result['auth_issuer_direct_table_privilege_count'] = int(issuer.table_privilege_count)
    result['auth_issuer_direct_sequence_privilege_count'] = int(issuer.sequence_privilege_count)
    result['auth_issuer_membership_count'] = int(issuer.membership_count)
    result['auth_issuer_can_create_cafeteria_schema'] = bool(
        issuer.can_create_cafeteria_schema
    )
    result['auth_issuer_can_create_public_schema'] = bool(issuer.can_create_public_schema)
    result['auth_issuer_connection_limit'] = int(issuer.connection_limit)
    result['auth_issuer_valid_until_infinity'] = bool(issuer.valid_until_infinity)
    result['auth_issuer_role_config_valid'] = runtime_role_config_valid.get(
        'cafeteria_auth_issuer', False
    )
    result['runtime_role_hardening_ready'] = runtime_role_hardening_ready
    result['auth_issuer_ready'] = (
        issuer.role_exists
        and issuer.can_login
        and not issuer.has_powerful_attribute
        and issuer.membership_count == 0
        and issuer.table_privilege_count == 0
        and issuer.sequence_privilege_count == 0
        and issuer.allowed_execute_count == 5
        and issuer.unexpected_execute_count == 0
        and not issuer.can_create_cafeteria_schema
        and not issuer.can_create_public_schema
        and issuer.connection_limit == -1
        and issuer.valid_until_infinity
        and result['auth_issuer_role_config_valid']
    )
    result['ready'] = (
        result['schema_version'] >= SCHEMA_VERSION
        and result['profile_count'] == 2
        and result['allergen_count'] == 14
        and result['invalid_index_count'] == 0
        and result['unvalidated_constraint_count'] == 0
        and result['auth_issuer_ready']
        and result['runtime_role_hardening_ready']
    )
    return result


def _cache_path(cache_dir: str | Path, profile_code: str) -> Path:
    return Path(cache_dir) / f'{profile_code}.json'


def _write_last_good(cache_dir: str | Path, profile_code: str, snapshot: dict[str, Any]) -> None:
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = _cache_path(directory, profile_code)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    os.replace(temporary, target)


def _read_last_good(cache_dir: str | Path, profile_code: str) -> dict[str, Any] | None:
    target = _cache_path(cache_dir, profile_code)
    if not target.is_file():
        return None
    snapshot = json.loads(target.read_text(encoding='utf-8'))
    validate_snapshot_payload(profile_code, snapshot)
    return snapshot


def active_snapshot(
    engine: Engine,
    profile_code: str,
    requested_date: str | None = None,
    *,
    last_good_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    if profile_code not in PROFILES:
        raise ValueError('Unbekanntes Profil.')
    try:
        with engine.connect() as connection:
            if requested_date:
                row = connection.execute(
                    text(
                        '''
                        SELECT snapshot_json
                        FROM cafeteria.active_publications
                        WHERE profile_code=:profile_code
                          AND CAST(:requested_date AS date) BETWEEN week_start AND week_end
                        ORDER BY published_at DESC
                        LIMIT 1
                        '''
                    ),
                    {'profile_code': profile_code, 'requested_date': requested_date},
                ).mappings().first()
            else:
                row = connection.execute(
                    text(
                        '''
                        SELECT snapshot_json
                        FROM cafeteria.active_publications
                        WHERE profile_code=:profile_code
                        ORDER BY week_start DESC, published_at DESC
                        LIMIT 1
                        '''
                    ),
                    {'profile_code': profile_code},
                ).mappings().first()
        if not row:
            return None
        snapshot = row['snapshot_json']
        snapshot = snapshot if isinstance(snapshot, dict) else json.loads(snapshot)
        validate_snapshot_payload(profile_code, snapshot)
        if last_good_dir:
            _write_last_good(last_good_dir, profile_code, snapshot)
        return snapshot
    except (SQLAlchemyError, OSError, json.JSONDecodeError):
        if last_good_dir:
            return _read_last_good(last_good_dir, profile_code)
        raise


def upsert_entra_user(issuer_engine: Engine, claims: dict[str, Any], roles: list[str]) -> int:
    """Synchronize an Entra identity through an owner/issuer database connection."""

    if not isinstance(roles, list):
        raise ValueError('Entra-Rollen müssen als Liste übergeben werden.')
    if any(not isinstance(role, str) or role not in ENTRA_APPLICATION_ROLES for role in roles):
        raise ValueError('Entra-Rollenliste enthält unbekannte oder ungültige Rollen.')
    if len(set(roles)) != len(roles):
        raise ValueError('Entra-Rollenliste enthält doppelte Rollen.')

    with issuer_engine.begin() as connection:
        user_id = connection.execute(
            text(
                '''
                SELECT cafeteria.sync_entra_user(
                    CAST(:tenant_id AS uuid),
                    CAST(:object_id AS uuid),
                    :subject_id,
                    :display_name,
                    :email,
                    :preferred_username,
                    CAST(:roles AS text[])
                )
                '''
            ),
            {
                'tenant_id': claims['tid'],
                'object_id': claims['oid'],
                'subject_id': claims.get('sub'),
                'display_name': claims.get('name') or claims.get('preferred_username') or 'Unbekannt',
                'email': claims.get('email'),
                'preferred_username': claims.get('preferred_username'),
                'roles': roles,
            },
        ).scalar_one()
    return int(user_id)


def demo_user(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        row = connection.execute(
            text('SELECT id, display_name FROM cafeteria.users WHERE public_id=CAST(:id AS uuid)'),
            {'id': DEMO_USER_PUBLIC_ID},
        ).mappings().first()
        if row is None:
            row = connection.execute(
                text('SELECT id, display_name FROM cafeteria.users WHERE public_id=CAST(:id AS uuid)'),
                {'id': SYSTEM_USER_PUBLIC_ID},
            ).mappings().one()
    return {'id': int(row['id']), 'name': row['display_name']}


def issue_publication_capability(
    issuer_engine: Engine,
    actor_user_id: int,
    revision_id: int,
    ttl: timedelta = DEFAULT_CAPABILITY_TTL,
) -> str:
    """Issue a withdrawal capability through an owner/issuer connection."""

    if not isinstance(ttl, timedelta) or not timedelta(0) < ttl <= MAX_CAPABILITY_TTL:
        raise ValueError('Capability-Gültigkeit muss > 0 und höchstens 15 Minuten sein.')
    with issuer_engine.begin() as connection:
        token = connection.execute(
            text(
                'SELECT cafeteria.issue_publication_capability('
                ':actor, :revision, CAST(:ttl AS interval))'
            ),
            {'actor': actor_user_id, 'revision': revision_id, 'ttl': ttl},
        ).scalar_one()
    return str(token)


def withdraw_publication_revision(
    engine: Engine,
    revision_id: int,
    capability: str,
    reason: str,
) -> Any:
    with engine.begin() as connection:
        return connection.execute(
            text(
                'SELECT cafeteria.withdraw_publication_revision(:revision, :capability, :reason)'
            ),
            {'revision': revision_id, 'capability': capability, 'reason': reason},
        ).scalar_one()
