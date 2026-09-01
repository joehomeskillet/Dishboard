from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psycopg import sql
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

SCHEMA_VERSION = 5
APPLICATION_VERSION = 'dishboard-schema-v5'
SYSTEM_USER_PUBLIC_ID = '00000000-0000-0000-0000-000000000001'
DEMO_USER_PUBLIC_ID = '00000000-0000-0000-0000-000000000002'
PROFILES = {'patient', 'staff_guest'}
PATIENT_FORBIDDEN_KEYS = {
    'price', 'prices', 'preis', 'preise', 'internal_rappen', 'external_rappen',
    'preis_intern', 'preis_extern', 'currency', 'chf', 'rappen',
    'cost', 'costs', 'amount', 'amounts', 'kosten', 'betrag', 'fee', 'tarif', 'tariff', 'charge',
}


@dataclass(frozen=True)
class Migration:
    version: int
    path: Path
    checksum_sha256: str


MIGRATION_FILES = (
    (4, '0001_initial_postgresql.sql'),
    (5, '0002_profile_publication_and_local_auth.sql'),
)
MIGRATION_LOCK_ID = 731_905_005


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


def provision_database_roles(engine: Engine, *, app_password: str, backup_password: str) -> None:
    if not app_password or not backup_password:
        raise RuntimeError('PostgreSQL-App- oder Backup-Passwort fehlt.')
    raw = engine.raw_connection()
    try:
        connection = _driver_connection(raw)
        with connection.cursor() as cursor:
            for role_name, password in (('cafeteria_app', app_password), ('cafeteria_backup', backup_password)):
                exists = cursor.execute(
                    'SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)', (role_name,)
                ).fetchone()[0]
                if exists:
                    statement = sql.SQL(
                        'ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD {}'
                    ).format(sql.Identifier(role_name), sql.Literal(password))
                else:
                    statement = sql.SQL(
                        'CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD {}'
                    ).format(sql.Identifier(role_name), sql.Literal(password))
                cursor.execute(statement)
                cursor.execute(sql.SQL('ALTER ROLE {} SET search_path = cafeteria, public').format(sql.Identifier(role_name)))
                cursor.execute(sql.SQL("ALTER ROLE {} SET timezone = 'UTC'").format(sql.Identifier(role_name)))
                read_only = 'on' if role_name == 'cafeteria_backup' else 'off'
                cursor.execute(
                    sql.SQL('ALTER ROLE {} SET default_transaction_read_only = {}').format(
                        sql.Identifier(role_name), sql.SQL(read_only)
                    )
                )
        connection.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def init_database(
    database_url: str,
    schema_path: str,
    seed_path: str,
    *,
    permissions_path: str | None = None,
    demo_seed_path: str | None = None,
    app_password: str = '',
    backup_password: str = '',
    seed_demo: bool = False,
) -> dict[str, Any]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        if app_password and backup_password:
            provision_database_roles(engine, app_password=app_password, backup_password=backup_password)
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
    result = dict(row)
    result['ready'] = (
        result['schema_version'] >= SCHEMA_VERSION
        and result['profile_count'] == 2
        and result['allergen_count'] == 14
        and result['invalid_index_count'] == 0
        and result['unvalidated_constraint_count'] == 0
    )
    return result


def _forbidden_patient_paths(value: Any, path: str = '$') -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lower = key.lower()
            if (
                lower in PATIENT_FORBIDDEN_KEYS
                or lower.endswith('_rappen')
                or '_price' in lower or 'price_' in lower
                or '_preis' in lower or 'preis_' in lower
                or '_cost' in lower or 'cost_' in lower
                or '_amount' in lower or 'amount_' in lower
            ):
                found.append(f'{path}.{key}')
            found.extend(_forbidden_patient_paths(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_patient_paths(child, f'{path}[{index}]'))
    return found


def _validate_service_states(services: list[Any]) -> None:
    for service in services:
        if not isinstance(service, dict):
            raise ValueError('Service-Eintrag im Snapshot ist ungültig.')
        state = service.get('service_state', 'open')
        if state not in {'open', 'closed', 'holiday', 'company_holiday'}:
            raise ValueError('service_state muss open, closed, holiday oder company_holiday sein.')
        options = service.get('options')
        if not isinstance(options, list):
            raise ValueError('Jede Mahlzeit braucht ein Options-Array.')
        if state == 'open' and len(options) != 2:
            raise ValueError('Eine offene Mahlzeit braucht genau zwei Menüoptionen.')
        if state != 'open' and options:
            raise ValueError('Eine geschlossene Mahlzeit darf keine Gerichte enthalten.')


def validate_snapshot_payload(profile_code: str, snapshot: dict[str, Any]) -> None:
    if profile_code not in PROFILES:
        raise ValueError('Unbekanntes Profil.')
    if snapshot.get('profile_code') != profile_code:
        raise ValueError('Snapshot-Profil stimmt nicht mit dem angeforderten Kanal überein.')
    days = snapshot.get('days')
    if not isinstance(days, list) or len(days) != 7:
        raise ValueError('Snapshot muss sieben Tage enthalten.')
    if profile_code == 'patient':
        paths = _forbidden_patient_paths(snapshot)
        if paths:
            raise ValueError('Patienten-Snapshot enthält unzulässige Kostenschlüssel: ' + ', '.join(paths[:5]))
        text_payload = json.dumps(snapshot, ensure_ascii=False)
        if 'CHF' in text_payload or '0.00' in text_payload:
            raise ValueError('Patienten-Snapshot enthält unzulässige Kostenwerte.')
        for day in days:
            services = day.get('services', [])
            meals = {service.get('meal_code') for service in services}
            if meals != {'LUNCH', 'DINNER'}:
                raise ValueError(f"Patiententag {day.get('date')} ist unvollständig.")
            _validate_service_states(services)
    else:
        services = [service for day in days for service in day.get('services', [])]
        if len(services) != 5 or any(service.get('meal_code') != 'LUNCH' for service in services):
            raise ValueError('Cafeteria-Snapshot muss fünf Mittagsservices enthalten.')
        _validate_service_states(services)
        for service in services:
            if service.get('service_state', 'open') != 'open':
                continue
            for option in service.get('options', []):
                costs = option.get('prices')
                if not isinstance(costs, dict) or not {'internal_rappen', 'external_rappen'} <= set(costs):
                    raise ValueError('Cafeteria-Menü ohne vollständige Kostenstruktur.')
                if type(costs.get('internal_rappen')) is not int or type(costs.get('external_rappen')) is not int:
                    raise ValueError('Cafeteria-Rappenbeträge müssen JSON-Ganzzahlen sein.')


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


def upsert_entra_user(engine: Engine, claims: dict[str, Any], roles: list[str]) -> int:
    roles_json = json.dumps(sorted(set(roles)), ensure_ascii=False)
    with engine.begin() as connection:
        user_id = connection.execute(
            text(
                '''
                INSERT INTO cafeteria.users(
                    auth_provider, entra_tenant_id, entra_object_id, entra_subject_id,
                    display_name, email, preferred_username, last_seen_roles, last_login_at
                )
                VALUES ('entra', CAST(:tenant_id AS uuid), CAST(:object_id AS uuid), :subject_id,
                        :display_name, :email, :preferred_username, CAST(:roles AS jsonb), clock_timestamp())
                ON CONFLICT (entra_tenant_id, entra_object_id) WHERE auth_provider='entra' DO UPDATE
                SET entra_subject_id=EXCLUDED.entra_subject_id,
                    display_name=EXCLUDED.display_name,
                    email=EXCLUDED.email,
                    preferred_username=EXCLUDED.preferred_username,
                    last_seen_roles=EXCLUDED.last_seen_roles,
                    last_login_at=clock_timestamp(),
                    disabled_at=NULL
                RETURNING id
                '''
            ),
            {
                'tenant_id': claims['tid'],
                'object_id': claims['oid'],
                'subject_id': claims.get('sub'),
                'display_name': claims.get('name') or claims.get('preferred_username') or 'Unbekannt',
                'email': claims.get('email'),
                'preferred_username': claims.get('preferred_username'),
                'roles': roles_json,
            },
        ).scalar_one()
        connection.execute(
            text("DELETE FROM cafeteria.user_role_cache WHERE user_id=:user_id AND source='entra_token'"),
            {'user_id': user_id},
        )
        for role in sorted(set(roles)):
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.user_role_cache(user_id, role_code, source, first_seen_at, last_seen_at)
                    VALUES (:user_id, :role, 'entra_token', clock_timestamp(), clock_timestamp())
                    ON CONFLICT (user_id, role_code) DO UPDATE
                    SET source='entra_token', last_seen_at=clock_timestamp()
                    '''
                ),
                {'user_id': user_id, 'role': role},
            )
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
