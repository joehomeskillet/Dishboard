from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from cafeteria import db as database
from cafeteria.auth import issuer as auth_issuer
from cafeteria.auth.service import authenticate_local_user
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
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


def _provision_entra_admin(issuer_engine: Engine, suffix: str) -> tuple[int, str]:
    actor = f'admin.{suffix}@example.invalid'
    user_id = database.upsert_entra_user(
        issuer_engine,
        {
            'tid': '00000000-0000-0000-0000-000000000811',
            'oid': f'00000000-0000-0000-0000-{int(suffix):012d}',
            'sub': f'admin-actor-{suffix}',
            'name': f'Admin Actor {suffix}',
            'preferred_username': actor,
        },
        ['Cafeteria.Admin'],
    )
    return user_id, actor


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


def test_role_reprovision_removes_powerful_attributes_and_memberships(
    owner_engine: Engine,
) -> None:
    with owner_engine.begin() as connection:
        connection.execute(text('DROP ROLE IF EXISTS auth_parent_test'))
        connection.execute(text('CREATE ROLE auth_parent_test NOLOGIN'))
        connection.execute(
            text(
                'ALTER ROLE cafeteria_app WITH CREATEDB CREATEROLE INHERIT '
                'REPLICATION BYPASSRLS'
            )
        )
        connection.execute(
            text(
                'ALTER ROLE cafeteria_backup WITH CREATEDB CREATEROLE INHERIT '
                'REPLICATION BYPASSRLS'
            )
        )
        connection.execute(
            text(
                'ALTER ROLE cafeteria_auth_issuer WITH CREATEDB CREATEROLE INHERIT '
                'REPLICATION BYPASSRLS'
            )
        )
        connection.execute(
            text(
                'GRANT auth_parent_test TO cafeteria_app, cafeteria_backup, '
                'cafeteria_auth_issuer'
            )
        )
        connection.execute(text('GRANT cafeteria_auth_issuer TO cafeteria_app'))
    try:
        database.provision_database_roles(
            owner_engine,
            app_password=APP_PASSWORD,
            backup_password=BACKUP_PASSWORD,
            auth_issuer_password=ISSUER_PASSWORD,
        )
        with owner_engine.connect() as connection:
            roles = connection.execute(
                text(
                    '''
                    SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolinherit,
                           rolreplication, rolbypassrls,
                           (SELECT count(*) FROM pg_auth_members m
                            WHERE m.member=r.oid OR m.roleid=r.oid) AS membership_count
                    FROM pg_roles r
                    WHERE rolname IN (
                        'cafeteria_app', 'cafeteria_backup', 'cafeteria_auth_issuer'
                    )
                    ORDER BY rolname
                    '''
                )
            ).mappings().all()
        assert [role.rolname for role in roles] == [
            'cafeteria_app',
            'cafeteria_auth_issuer',
            'cafeteria_backup',
        ]
        assert all(
            role.rolsuper is False
            and role.rolcreatedb is False
            and role.rolcreaterole is False
            and role.rolinherit is False
            and role.rolreplication is False
            and role.rolbypassrls is False
            and role.membership_count == 0
            for role in roles
        )
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text('DROP ROLE IF EXISTS auth_parent_test'))


def test_local_admin_actions_require_and_persist_verified_actor(owner_engine: Engine) -> None:
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        database.upsert_entra_user(
            issuer_engine,
            {
                'tid': '00000000-0000-0000-0000-000000000955',
                'oid': '00000000-0000-0000-0000-000000000956',
                'sub': 'non-admin-actor',
                'name': 'Non Admin Actor',
                'preferred_username': 'not.admin@example.invalid',
            },
            ['Cafeteria.Editor'],
        )
        with pytest.raises(DBAPIError, match='keinen eindeutigen aktiven Administrator'):
            auth_issuer.provision_local_user(
                issuer_engine,
                actor_identifier='not.admin@example.invalid',
                username='denied.local',
                display_name='Denied Local',
                password='Crimson-Lake-2026!P8',
                roles=['Cafeteria.Editor'],
            )
        actor_id, actor = _provision_entra_admin(issuer_engine, '933')
        user_id = auth_issuer.provision_local_user(
            issuer_engine,
            actor_identifier=actor,
            username='audited.local',
            display_name='Audited Local',
            password='Olive-Mountain-2026!K9',
            roles=['Cafeteria.Editor'],
        )
        auth_issuer.set_local_password(
            issuer_engine,
            actor_identifier=actor,
            username='audited.local',
            password='Quartz-River-2027!L8',
        )
        auth_issuer.disable_local_user(
            issuer_engine,
            actor_identifier=actor,
            username='audited.local',
        )
    finally:
        issuer_engine.dispose()
    with owner_engine.connect() as connection:
        events = connection.execute(
            text(
                '''
                SELECT action, actor_user_id, details
                FROM cafeteria.audit_events
                WHERE (details->>'target_user_id')::bigint=:user_id
                  AND action LIKE 'auth.local_%'
                ORDER BY id
                '''
            ),
            {'user_id': user_id},
        ).mappings().all()

    assert {event.action for event in events} == {
        'auth.local_user_provisioned',
        'auth.local_role_granted',
        'auth.local_password_changed',
        'auth.local_user_disabled',
    }
    assert all(event.actor_user_id == actor_id for event in events)
    assert all(event.details['target_user_id'] == user_id for event in events)


def test_expired_local_lock_relocks_and_audits_once_per_lock_cycle(
    owner_engine: Engine,
) -> None:
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        _, actor = _provision_entra_admin(issuer_engine, '944')
        user_id = auth_issuer.provision_local_user(
            issuer_engine,
            actor_identifier=actor,
            username='relock.local',
            display_name='Relock Local',
            password='Cedar-Valley-2026!M7',
            roles=['Cafeteria.Editor'],
        )
        for _ in range(5):
            assert authenticate_local_user(
                app_engine,
                username='relock.local',
                password='Wrong-Relock-2026!',
            ) is None
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE cafeteria.local_credentials "
                    "SET locked_until=clock_timestamp() - interval '1 second' "
                    "WHERE user_id=:user_id"
                ),
                {'user_id': user_id},
            )
        for _ in range(2):
            assert authenticate_local_user(
                app_engine,
                username='relock.local',
                password='Wrong-Relock-2026!',
            ) is None
    finally:
        app_engine.dispose()
        issuer_engine.dispose()
    with owner_engine.connect() as connection:
        audit_count = connection.execute(
            text(
                '''
                SELECT count(*) FROM cafeteria.audit_events
                WHERE action='auth.local_login_locked'
                  AND (details->>'user_id')::bigint=:user_id
                '''
            ),
            {'user_id': user_id},
        ).scalar_one()

    assert audit_count == 2
