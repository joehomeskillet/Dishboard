from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool
from werkzeug.security import check_password_hash

import manage
from cafeteria import db as database
from cafeteria.auth import issuer as auth_issuer


ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
LIVE_DATABASE = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


def _role_database_url(role: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role,
        password=password,
    ).render_as_string(hide_password=False)


@pytest.fixture
def owner_engine() -> Iterator[Engine]:
    if not DATABASE_URL:
        pytest.skip('TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.')
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password='test-app-secret',
        backup_password='test-backup-secret',
        auth_issuer_password='test-auth-issuer-secret',
    )
    try:
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


def test_migration_plan_contains_auth_issuer_contract() -> None:
    plan = database.migration_plan(ROOT / 'database' / 'schema.sql')

    assert database.SCHEMA_VERSION == 9
    assert (plan[-1].version, plan[-1].path.name) == (
        9,
        '0006_auth_issuer_and_local_login.sql',
    )


@LIVE_DATABASE
def test_auth_issuer_role_has_function_only_identity_privileges(owner_engine: Engine) -> None:
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', 'test-auth-issuer-secret'),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with issuer_engine.connect() as connection:
            privileges = connection.execute(
                text(
                    '''
                    SELECT
                        has_function_privilege(
                            current_user,
                            'cafeteria.sync_entra_user(uuid,uuid,text,text,text,text,text[])',
                            'EXECUTE'
                        ) AS sync_execute,
                        has_function_privilege(
                            current_user,
                            'cafeteria.issue_publication_capability(bigint,bigint,interval)',
                            'EXECUTE'
                        ) AS issue_execute,
                        has_function_privilege(
                            current_user,
                            'cafeteria.provision_local_user(text,text,text,text[])',
                            'EXECUTE'
                        ) AS provision_execute,
                        has_function_privilege(
                            current_user,
                            'cafeteria.set_local_password(text,text)',
                            'EXECUTE'
                        ) AS password_execute,
                        has_function_privilege(
                            current_user,
                            'cafeteria.disable_local_user(text)',
                            'EXECUTE'
                        ) AS disable_execute,
                        has_table_privilege(current_user, 'cafeteria.users', 'SELECT') AS users_select,
                        has_table_privilege(
                            current_user, 'cafeteria.local_credentials', 'SELECT'
                        ) AS credentials_select
                    '''
                )
            ).mappings().one()
    finally:
        issuer_engine.dispose()

    assert privileges == {
        'sync_execute': True,
        'issue_execute': True,
        'provision_execute': True,
        'password_execute': True,
        'disable_execute': True,
        'users_select': False,
        'credentials_select': False,
    }


@LIVE_DATABASE
def test_local_user_provisioning_hashes_password_and_rejects_duplicate_roles(
    owner_engine: Engine,
) -> None:
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', 'test-auth-issuer-secret'),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        user_id = auth_issuer.provision_local_user(
            issuer_engine,
            username='kueche.admin',
            display_name='Küche Admin',
            password='Kueche-2026!Sicher',
            roles=['Cafeteria.Editor', 'Cafeteria.Admin'],
        )
        with owner_engine.connect() as connection:
            row = connection.execute(
                text(
                    '''
                    SELECT u.auth_provider, u.disabled_at, c.username, c.password_hash,
                           array_agg(r.role_code ORDER BY r.role_code) AS roles
                    FROM cafeteria.users u
                    JOIN cafeteria.local_credentials c ON c.user_id=u.id
                    JOIN cafeteria.user_role_cache r ON r.user_id=u.id
                    WHERE u.id=:user_id
                    GROUP BY u.auth_provider, u.disabled_at, c.username, c.password_hash
                    '''
                ),
                {'user_id': user_id},
            ).mappings().one()

        assert row.auth_provider == 'local'
        assert row.disabled_at is None
        assert row.username == 'kueche.admin'
        assert row.password_hash != 'Kueche-2026!Sicher'
        assert check_password_hash(row.password_hash, 'Kueche-2026!Sicher')
        assert row.roles == ['Cafeteria.Admin', 'Cafeteria.Editor']

        with pytest.raises(ValueError, match='doppelte'):
            auth_issuer.provision_local_user(
                issuer_engine,
                username='zweiter.admin',
                display_name='Zweiter Admin',
                password='Zweiter-2026!Sicher',
                roles=['Cafeteria.Admin', 'Cafeteria.Admin'],
            )
    finally:
        issuer_engine.dispose()


@pytest.mark.parametrize(
    'password',
    [
        'passwordpassword',
        'aaaaaaaaaaaaaa',
        'change-me-change-me',
        'kueche.admin-2026!',
    ],
)
def test_local_password_policy_rejects_weak_or_username_based_values(password: str) -> None:
    with pytest.raises(ValueError, match='Passwort'):
        auth_issuer.validate_local_password(password, 'kueche.admin')


def test_cli_rejects_password_argument_without_echoing_value(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv('APP_ENV', 'test')
    secret = 'Must-Not-Appear-2026!'
    with pytest.raises(RuntimeError, match='interaktiv'):
        manage.main(
            [
                'set-local-password', '--username', 'local.editor',
                '--password', secret,
            ]
        )
    output = capsys.readouterr()
    assert secret not in output.out + output.err


@LIVE_DATABASE
def test_app_role_cannot_provision_or_issue_identity_functions(owner_engine: Engine) -> None:
    app_engine = create_engine(
        _role_database_url('cafeteria_app', 'test-app-secret'),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with pytest.raises(DBAPIError, match='permission denied'):
            with app_engine.begin() as connection:
                connection.execute(
                    text(
                        '''
                        SELECT cafeteria.provision_local_user(
                            'app.attacker', 'App Attacker',
                            'scrypt:32768:8:1$salt$0123456789abcdef',
                            ARRAY['Cafeteria.Admin']::text[]
                        )
                        '''
                    )
                ).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied'):
            database.upsert_entra_user(
                app_engine,
                {
                    'tid': '00000000-0000-0000-0000-000000000111',
                    'oid': '00000000-0000-0000-0000-000000000222',
                    'name': 'Nicht erlaubt',
                },
                [],
            )
        with pytest.raises(DBAPIError, match='permission denied'):
            with app_engine.begin() as connection:
                connection.execute(
                    text("SELECT cafeteria.set_local_password('app.attacker', 'scrypt:1:1:1$s$x')")
                ).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied'):
            with app_engine.begin() as connection:
                connection.execute(
                    text("SELECT cafeteria.disable_local_user('app.attacker')")
                ).scalar_one()
    finally:
        app_engine.dispose()


@LIVE_DATABASE
def test_entra_empty_roles_purge_and_bump_without_reactivating_disabled_user(
    owner_engine: Engine,
) -> None:
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', 'test-auth-issuer-secret'),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    claims = {
        'tid': '00000000-0000-0000-0000-000000000311',
        'oid': '00000000-0000-0000-0000-000000000322',
        'sub': 'entra-subject',
        'name': 'Entzogene Person',
        'preferred_username': 'entzogen@example.invalid',
    }
    try:
        user_id = database.upsert_entra_user(
            issuer_engine,
            claims,
            ['Cafeteria.Editor'],
        )
        with owner_engine.begin() as connection:
            connection.execute(
                text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'),
                {'id': user_id},
            )
            disabled_version = int(
                connection.execute(
                    text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                    {'id': user_id},
                ).scalar_one()
            )

        assert database.upsert_entra_user(issuer_engine, claims, []) == user_id

        with owner_engine.connect() as connection:
            row = connection.execute(
                text(
                    '''
                    SELECT disabled_at, authz_version, last_seen_roles,
                           (SELECT count(*) FROM cafeteria.user_role_cache r
                            WHERE r.user_id=u.id) AS role_count
                    FROM cafeteria.users u
                    WHERE id=:id
                    '''
                ),
                {'id': user_id},
            ).mappings().one()
    finally:
        issuer_engine.dispose()

    assert row.disabled_at is not None
    assert row.authz_version > disabled_version
    assert row.last_seen_roles == []
    assert row.role_count == 0


@LIVE_DATABASE
def test_cli_provisions_local_user_via_getpass_without_logging_password(
    owner_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    issuer_url = _role_database_url('cafeteria_auth_issuer', 'test-auth-issuer-secret')
    monkeypatch.setenv('AUTH_ISSUER_DATABASE_URL', issuer_url)
    monkeypatch.setenv('DATABASE_URL', issuer_url)
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'false')
    passwords = iter(['CLI-Only-2026!Sicher', 'CLI-Only-2026!Sicher'])
    monkeypatch.setattr(manage.getpass, 'getpass', lambda prompt: next(passwords))

    result = manage.main(
        [
            'provision-local-user',
            '--username',
            'cli.admin',
            '--display-name',
            'CLI Admin',
            '--role',
            'Cafeteria.Admin',
        ]
    )

    output = capsys.readouterr()
    assert result == 0
    assert 'CLI-Only-2026!Sicher' not in output.out
    assert 'CLI-Only-2026!Sicher' not in output.err
    with owner_engine.connect() as connection:
        row = connection.execute(
            text(
                '''
                SELECT c.password_hash, r.role_code
                FROM cafeteria.local_credentials c
                JOIN cafeteria.user_role_cache r ON r.user_id=c.user_id
                WHERE c.username='cli.admin'
                '''
            )
        ).one()
    assert row.password_hash != 'CLI-Only-2026!Sicher'
    assert check_password_hash(row.password_hash, 'CLI-Only-2026!Sicher')
    assert row.role_code == 'Cafeteria.Admin'


@LIVE_DATABASE
def test_cli_sets_password_then_disables_local_user_with_audit_and_revocation(
    owner_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    issuer_url = _role_database_url('cafeteria_auth_issuer', 'test-auth-issuer-secret')
    monkeypatch.setenv('AUTH_ISSUER_DATABASE_URL', issuer_url)
    monkeypatch.setenv('DATABASE_URL', issuer_url)
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'false')
    original = iter(['Original-2026!Sicher', 'Original-2026!Sicher'])
    monkeypatch.setattr(manage.getpass, 'getpass', lambda prompt: next(original))
    assert manage.main(
        [
            'provision-local-user', '--username', 'cli.operator',
            '--display-name', 'CLI Operator', '--role', 'Cafeteria.Editor',
        ]
    ) == 0
    with owner_engine.connect() as connection:
        before = connection.execute(
            text(
                '''
                SELECT u.authz_version, c.password_hash
                FROM cafeteria.users u
                JOIN cafeteria.local_credentials c ON c.user_id=u.id
                WHERE c.username='cli.operator'
                '''
            )
        ).one()

    changed = iter(['Changed-2026!Sicher', 'Changed-2026!Sicher'])
    monkeypatch.setattr(manage.getpass, 'getpass', lambda prompt: next(changed))
    assert manage.main(['set-local-password', '--username', 'cli.operator']) == 0
    assert manage.main(['disable-local-user', '--username', 'cli.operator']) == 0

    output = capsys.readouterr()
    assert 'Original-2026!Sicher' not in output.out + output.err
    assert 'Changed-2026!Sicher' not in output.out + output.err
    with owner_engine.connect() as connection:
        after = connection.execute(
            text(
                '''
                SELECT u.authz_version, u.disabled_at, c.password_hash,
                       array_agg(DISTINCT a.action ORDER BY a.action) AS actions
                FROM cafeteria.users u
                JOIN cafeteria.local_credentials c ON c.user_id=u.id
                JOIN cafeteria.audit_events a
                  ON (a.details->>'user_id')::bigint=u.id
                WHERE c.username='cli.operator'
                GROUP BY u.authz_version, u.disabled_at, c.password_hash
                '''
            )
        ).one()
    assert after.authz_version >= before.authz_version + 2
    assert after.disabled_at is not None
    assert after.password_hash != before.password_hash
    assert check_password_hash(after.password_hash, 'Changed-2026!Sicher')
    assert after.actions == [
        'auth.local_password_changed',
        'auth.local_role_granted',
        'auth.local_user_disabled',
        'auth.local_user_provisioned',
    ]
