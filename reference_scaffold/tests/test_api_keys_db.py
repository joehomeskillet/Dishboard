from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from psycopg.errors import InsufficientPrivilege
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.api_keys import (
    API_KEY_SCOPES,
    ApiKeyValidationError,
    authenticate_api_key,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


def _role_database_url(role_name: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role_name,
        password=password,
    ).render_as_string(hide_password=False)


@pytest.fixture
def database_engines() -> Iterator[tuple[Engine, Engine]]:
    assert DATABASE_URL is not None
    owner_engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(owner_engine)
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        yield owner_engine, app_engine
    finally:
        app_engine.dispose()
        _drop_schema(owner_engine)
        owner_engine.dispose()


def _create_user(engine: Engine, *, suffix: str, roles: list[str]) -> int:
    return database.upsert_entra_user(
        engine,
        {
            'tid': '00000000-0000-0000-0000-000000000001',
            'oid': f'00000000-0000-0000-0000-{suffix:0>12}',
            'sub': f'api-key-{suffix}',
            'name': f'API Key {suffix}',
            'preferred_username': f'api-key-{suffix}@example.invalid',
        },
        roles,
    )


def _assert_insufficient_privilege(error: DBAPIError) -> None:
    assert isinstance(error.orig, InsufficientPrivilege)
    assert error.orig.sqlstate == '42501'


def test_admin_can_create_list_and_revoke_with_safe_audit(
    database_engines: tuple[Engine, Engine],
) -> None:
    owner_engine, app_engine = database_engines
    admin_id = _create_user(owner_engine, suffix='101', roles=['Cafeteria.Admin'])

    record, plaintext = create_api_key(
        app_engine,
        actor_id=admin_id,
        label='FHIR Vorschau',
        scopes=API_KEY_SCOPES,
        # PostgreSQL JSON trims trailing fractional zeroes; make that case deterministic.
        expires_at=(datetime.now(UTC) + timedelta(days=30)).replace(microsecond=364700),
    )

    assert plaintext.startswith('dbk_')
    assert len(plaintext) == 36
    assert record.label == 'FHIR Vorschau'
    assert record.key_prefix == plaintext[:12]
    assert record.scopes == API_KEY_SCOPES
    assert record.created_by_name == 'API Key 101'
    assert record.state == 'active'
    assert list_api_keys(app_engine) == [record]

    with owner_engine.connect() as connection:
        audit_rows = connection.execute(
            text(
                '''
                SELECT action, details
                FROM cafeteria.audit_events
                WHERE entity_public_id=:public_id
                ORDER BY id
                '''
            ),
            {'public_id': record.public_id},
        ).mappings().all()
    assert [row['action'] for row in audit_rows] == ['api.key_created']
    details = dict(audit_rows[0]['details'])
    assert isinstance(details['expires_at'], str)
    details['expires_at'] = datetime.fromisoformat(details['expires_at'])
    assert details == {
        'label': 'FHIR Vorschau',
        'scopes': ['preview.read'],
        'expires_at': record.expires_at,
        'key_prefix': record.key_prefix,
    }
    assert 'key_hash' not in audit_rows[0]['details']
    assert plaintext not in str(audit_rows[0]['details'])

    assert revoke_api_key(app_engine, actor_id=admin_id, public_id=record.public_id) is True
    assert revoke_api_key(app_engine, actor_id=admin_id, public_id=record.public_id) is False
    revoked = list_api_keys(app_engine)[0]
    assert revoked.state == 'revoked'

    with owner_engine.connect() as connection:
        audit_rows = connection.execute(
            text(
                '''
                SELECT action, details
                FROM cafeteria.audit_events
                WHERE entity_public_id=:public_id
                ORDER BY id
                '''
            ),
            {'public_id': record.public_id},
        ).mappings().all()
    assert [row['action'] for row in audit_rows] == ['api.key_created', 'api.key_revoked']
    assert all('key_hash' not in row['details'] for row in audit_rows)


def test_editor_cannot_create_or_revoke_api_keys(
    database_engines: tuple[Engine, Engine],
) -> None:
    owner_engine, app_engine = database_engines
    admin_id = _create_user(owner_engine, suffix='201', roles=['Cafeteria.Admin'])
    editor_id = _create_user(owner_engine, suffix='202', roles=['Cafeteria.Editor'])
    record, _ = create_api_key(
        app_engine,
        actor_id=admin_id,
        label='Admin key',
        scopes=API_KEY_SCOPES,
        expires_at=None,
    )

    with pytest.raises(PermissionError):
        create_api_key(
            app_engine,
            actor_id=editor_id,
            label='Editor key',
            scopes=API_KEY_SCOPES,
            expires_at=None,
        )
    with pytest.raises(PermissionError):
        revoke_api_key(app_engine, actor_id=editor_id, public_id=record.public_id)


def test_cafeteria_app_cannot_insert_or_set_revocation_directly(
    database_engines: tuple[Engine, Engine],
) -> None:
    owner_engine, app_engine = database_engines
    admin_id = _create_user(owner_engine, suffix='301', roles=['Cafeteria.Admin'])
    record, _ = create_api_key(
        app_engine,
        actor_id=admin_id,
        label='Protected key',
        scopes=API_KEY_SCOPES,
        expires_at=None,
    )

    with pytest.raises(DBAPIError) as insert_error:
        with app_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.api_keys(
                        label, key_prefix, key_hash, scopes, created_by
                    ) VALUES (
                        'Direct', 'dbk_12345678', :key_hash,
                        ARRAY['preview.read']::text[], :created_by
                    )
                    '''
                ),
                {'key_hash': 'sha256:' + ('0' * 64), 'created_by': admin_id},
            )
    _assert_insufficient_privilege(insert_error.value)

    with pytest.raises(DBAPIError) as revoke_error:
        with app_engine.begin() as connection:
            connection.execute(
                text('UPDATE cafeteria.api_keys SET revoked_at=clock_timestamp() WHERE public_id=:public_id'),
                {'public_id': record.public_id},
            )
    _assert_insufficient_privilege(revoke_error.value)


def test_authenticate_api_key_handles_valid_expired_revoked_and_unknown_keys(
    database_engines: tuple[Engine, Engine],
) -> None:
    owner_engine, app_engine = database_engines
    admin_id = _create_user(owner_engine, suffix='401', roles=['Cafeteria.Admin'])
    valid_record, valid_plaintext = create_api_key(
        app_engine,
        actor_id=admin_id,
        label='Valid key',
        scopes=API_KEY_SCOPES,
        expires_at=None,
    )

    identity = authenticate_api_key(app_engine, valid_plaintext)
    assert identity is not None
    assert identity.public_id == valid_record.public_id
    assert identity.label == 'Valid key'
    assert identity.scopes == API_KEY_SCOPES
    with owner_engine.connect() as connection:
        last_used_at = connection.execute(
            text('SELECT last_used_at FROM cafeteria.api_keys WHERE public_id=:public_id'),
            {'public_id': valid_record.public_id},
        ).scalar_one()
    assert last_used_at is not None

    expired_record, expired_plaintext = create_api_key(
        app_engine,
        actor_id=admin_id,
        label='Expired key',
        scopes=API_KEY_SCOPES,
        expires_at=None,
    )
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                '''
                UPDATE cafeteria.api_keys
                SET created_at=clock_timestamp() - interval '2 hours',
                    expires_at=clock_timestamp() - interval '1 hour'
                WHERE public_id=:public_id
                '''
            ),
            {'public_id': expired_record.public_id},
        )
    assert authenticate_api_key(app_engine, expired_plaintext) is None

    revoked_record, revoked_plaintext = create_api_key(
        app_engine,
        actor_id=admin_id,
        label='Revoked key',
        scopes=API_KEY_SCOPES,
        expires_at=None,
    )
    assert revoke_api_key(app_engine, actor_id=admin_id, public_id=revoked_record.public_id)
    assert authenticate_api_key(app_engine, revoked_plaintext) is None
    assert authenticate_api_key(app_engine, 'not-an-api-key') is None
    assert authenticate_api_key(app_engine, f'dbk_ZZZZZZZZ{valid_plaintext[12:]}') is None
    assert authenticate_api_key(app_engine, None) is None


def test_create_api_key_rejects_invalid_input(
    database_engines: tuple[Engine, Engine],
) -> None:
    owner_engine, app_engine = database_engines
    admin_id = _create_user(owner_engine, suffix='501', roles=['Cafeteria.Admin'])

    with pytest.raises(ApiKeyValidationError):
        create_api_key(
            app_engine,
            actor_id=admin_id,
            label=' ',
            scopes=API_KEY_SCOPES,
            expires_at=None,
        )
    with pytest.raises(ApiKeyValidationError):
        create_api_key(
            app_engine,
            actor_id=admin_id,
            label='Wrong scope',
            scopes=['preview.write'],
            expires_at=None,
        )


def test_database_permission_errors_are_mapped(
    database_engines: tuple[Engine, Engine],
) -> None:
    _, _ = database_engines
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with pytest.raises(PermissionError):
            list_api_keys(issuer_engine)
        with pytest.raises(PermissionError):
            authenticate_api_key(issuer_engine, 'dbk_12345678901234567890123456789012')
    finally:
        issuer_engine.dispose()
