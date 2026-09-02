from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from cafeteria import db as database
from psycopg import sql
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
RUNTIME_ROLE_CREDENTIALS = (
    ('cafeteria_app', APP_PASSWORD),
    ('cafeteria_backup', BACKUP_PASSWORD),
    ('cafeteria_auth_issuer', ISSUER_PASSWORD),
)
ROLE_ATTRIBUTE_DRIFTS = (
    ('superuser', 'SUPERUSER'),
    ('createdb', 'CREATEDB'),
    ('createrole', 'CREATEROLE'),
    ('inherit', 'INHERIT'),
    ('replication', 'REPLICATION'),
    ('bypassrls', 'BYPASSRLS'),
    ('nologin', 'NOLOGIN'),
    ('connection-limit', 'CONNECTION LIMIT 1'),
    ('valid-until', "VALID UNTIL '2030-01-01'"),
    ('unexpected-config', "SET statement_timeout = '1s'"),
    ('search-path', 'SET search_path = public'),
    ('timezone', "SET timezone = 'Europe/Zurich'"),
)
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


def _role_database_url(role: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role,
        password=password,
    ).render_as_string(hide_password=False)


def _alter_role(connection: Connection, role_name: str, attributes: str) -> None:
    connection.connection.driver_connection.execute(
        sql.SQL('ALTER ROLE {} {}').format(
            sql.Identifier(role_name),
            sql.SQL(attributes),
        )
    )


def _grant_role(connection: Connection, granted_role: str, member_role: str) -> None:
    connection.connection.driver_connection.execute(
        sql.SQL('GRANT {} TO {}').format(
            sql.Identifier(granted_role),
            sql.Identifier(member_role),
        )
    )


@pytest.fixture
def owner_engine() -> Iterator[Engine]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
        engine.dispose()


@pytest.mark.parametrize('role_name,password', RUNTIME_ROLE_CREDENTIALS)
@pytest.mark.parametrize(
    ('drift_name', 'drift_sql'),
    ROLE_ATTRIBUTE_DRIFTS,
    ids=[case[0] for case in ROLE_ATTRIBUTE_DRIFTS],
)
def test_validator_rejects_each_runtime_role_attribute_drift_until_reprovisioned(
    owner_engine: Engine,
    role_name: str,
    password: str,
    drift_name: str,
    drift_sql: str,
) -> None:
    with owner_engine.begin() as connection:
        _alter_role(connection, role_name, drift_sql)

    before_repair = database.validate_database(owner_engine)
    assert before_repair['runtime_role_hardening_ready'] is False, drift_name
    assert before_repair['ready'] is False, drift_name

    database.provision_database_roles(
        owner_engine,
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )

    after_repair = database.validate_database(owner_engine)
    assert after_repair['runtime_role_hardening_ready'] is True
    assert after_repair['ready'] is True
    role_engine = create_engine(
        _role_database_url(role_name, password),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with role_engine.connect() as connection:
            role_state = connection.execute(
                text(
                    '''
                    SELECT current_user,
                           current_setting('search_path') AS search_path,
                           current_setting('timezone') AS timezone,
                           current_setting('default_transaction_read_only') AS read_only,
                           has_schema_privilege(current_user, 'cafeteria', 'CREATE')
                               AS can_create_cafeteria,
                           has_schema_privilege(current_user, 'public', 'CREATE')
                               AS can_create_public
                    '''
                )
            ).mappings().one()
        assert role_state.current_user == role_name
        assert role_state.search_path == 'cafeteria, public'
        assert role_state.timezone == 'UTC'
        assert role_state.read_only == ('on' if role_name == 'cafeteria_backup' else 'off')
        assert role_state.can_create_cafeteria is False
        assert role_state.can_create_public is False
    finally:
        role_engine.dispose()


@pytest.mark.parametrize('role_name,_password', RUNTIME_ROLE_CREDENTIALS)
def test_validator_rejects_runtime_role_membership_drift_until_reprovisioned(
    owner_engine: Engine,
    role_name: str,
    _password: str,
) -> None:
    with owner_engine.begin() as connection:
        connection.execute(text('DROP ROLE IF EXISTS readiness_parent_test'))
        connection.execute(text('CREATE ROLE readiness_parent_test NOLOGIN'))
        _grant_role(connection, 'readiness_parent_test', role_name)
    try:
        before_repair = database.validate_database(owner_engine)
        assert before_repair['runtime_role_hardening_ready'] is False
        assert before_repair['ready'] is False

        database.provision_database_roles(
            owner_engine,
            app_password=APP_PASSWORD,
            backup_password=BACKUP_PASSWORD,
            auth_issuer_password=ISSUER_PASSWORD,
        )

        after_repair = database.validate_database(owner_engine)
        assert after_repair['runtime_role_hardening_ready'] is True
        assert after_repair['ready'] is True
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text('DROP ROLE IF EXISTS readiness_parent_test'))
