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
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
DEFAULT_ACTOR = 'admin.801@example.invalid'
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
    if not DATABASE_URL:
        pytest.skip('TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.')
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        _provision_entra_admin(issuer_engine, '801')
    finally:
        issuer_engine.dispose()
    try:
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


def test_migration_plan_contains_auth_issuer_contract() -> None:
    plan = database.migration_plan(ROOT / 'database' / 'schema.sql')

    assert database.SCHEMA_VERSION == 11
    assert (plan[-1].version, plan[-1].path.name) == (
        11,
        '0008_auth_final_hardening.sql',
    )


@LIVE_DATABASE
def test_auth_issuer_role_has_function_only_identity_privileges(owner_engine: Engine) -> None:
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                'GRANT CREATE ON SCHEMA cafeteria, public TO '
                'cafeteria_app, cafeteria_backup, cafeteria_auth_issuer'
            )
        )
    database._execute_script(owner_engine, str(ROOT / 'database' / 'permissions.sql'))
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
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
                            'cafeteria.provision_local_user(text,text,text,text,text[])',
                            'EXECUTE'
                        ) AS provision_execute,
                        has_function_privilege(
                            current_user,
                            'cafeteria.set_local_password(text,text,text)',
                            'EXECUTE'
                        ) AS password_execute,
                        has_function_privilege(
                            current_user,
                            'cafeteria.disable_local_user(text,text)',
                            'EXECUTE'
                        ) AS disable_execute,
                        has_table_privilege(current_user, 'cafeteria.users', 'SELECT') AS users_select,
                        has_table_privilege(
                            current_user, 'cafeteria.local_credentials', 'SELECT'
                        ) AS credentials_select,
                        has_schema_privilege(current_user, 'cafeteria', 'USAGE')
                            AS cafeteria_usage,
                        has_schema_privilege(current_user, 'cafeteria', 'CREATE')
                            AS cafeteria_create,
                        has_schema_privilege(current_user, 'public', 'CREATE')
                            AS public_create,
                        (SELECT count(*)
                           FROM pg_proc p
                           JOIN pg_namespace n ON n.oid=p.pronamespace
                          WHERE n.nspname='cafeteria'
                            AND has_function_privilege(current_user, p.oid, 'EXECUTE'))
                            AS execute_count
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
        'cafeteria_usage': True,
        'cafeteria_create': False,
        'public_create': False,
        'execute_count': 5,
    }
    with pytest.raises(DBAPIError, match='permission denied'):
        with issuer_engine.begin() as connection:
            connection.execute(text('CREATE TABLE cafeteria.issuer_forged_table(id bigint)'))
    with pytest.raises(DBAPIError, match='permission denied'):
        with issuer_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE FUNCTION cafeteria.issuer_forged_function() "
                    "RETURNS integer LANGUAGE sql AS 'SELECT 1'"
                )
            )


@LIVE_DATABASE
def test_local_user_provisioning_hashes_password_and_rejects_duplicate_roles(
    owner_engine: Engine,
) -> None:
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        user_id = auth_issuer.provision_local_user(
            issuer_engine,
            actor_identifier=DEFAULT_ACTOR,
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
                actor_identifier=DEFAULT_ACTOR,
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
                'set-local-password', '--actor', DEFAULT_ACTOR, '--username', 'local.editor',
                '--password', secret,
            ]
        )
    output = capsys.readouterr()
    assert secret not in output.out + output.err


@pytest.mark.parametrize(
    'argv',
    (
        [
            'provision-local-user', '--username', 'missing.actor',
            '--display-name', 'Missing Actor', '--role', 'Cafeteria.Editor',
        ],
        ['set-local-password', '--username', 'missing.actor'],
        ['disable-local-user', '--username', 'missing.actor'],
    ),
)
def test_local_account_commands_require_verified_actor_argument(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        manage.main(argv)

    assert exc_info.value.code == 2
    assert '--actor' in capsys.readouterr().err


@LIVE_DATABASE
def test_app_role_cannot_provision_or_issue_identity_functions(owner_engine: Engine) -> None:
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
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
                            'admin.actor', 'app.attacker', 'App Attacker',
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
                    text(
                        "SELECT cafeteria.set_local_password("
                        "'admin.actor', 'app.attacker', 'scrypt:1:1:1$s$x')"
                    )
                ).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied'):
            with app_engine.begin() as connection:
                connection.execute(
                    text("SELECT cafeteria.disable_local_user('admin.actor', 'app.attacker')")
                ).scalar_one()
    finally:
        app_engine.dispose()


@LIVE_DATABASE
def test_entra_empty_roles_purge_and_bump_without_reactivating_disabled_user(
    owner_engine: Engine,
) -> None:
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
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
    assert DATABASE_URL is not None
    monkeypatch.setenv('DATABASE_URL', DATABASE_URL)
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD', ISSUER_PASSWORD)
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'false')
    passwords = iter(['CLI-Only-2026!Sicher', 'CLI-Only-2026!Sicher'])
    monkeypatch.setattr(manage.getpass, 'getpass', lambda prompt: next(passwords))

    result = manage.main(
        [
            'provision-local-user',
            '--actor',
            DEFAULT_ACTOR,
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
    assert DATABASE_URL is not None
    monkeypatch.setenv('DATABASE_URL', DATABASE_URL)
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD', ISSUER_PASSWORD)
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'false')
    original = iter(['Original-2026!Sicher', 'Original-2026!Sicher'])
    monkeypatch.setattr(manage.getpass, 'getpass', lambda prompt: next(original))
    assert manage.main(
        [
            'provision-local-user', '--actor', DEFAULT_ACTOR, '--username', 'cli.operator',
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
    assert manage.main(
        ['set-local-password', '--actor', DEFAULT_ACTOR, '--username', 'cli.operator']
    ) == 0
    assert manage.main(
        ['disable-local-user', '--actor', DEFAULT_ACTOR, '--username', 'cli.operator']
    ) == 0

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
                  ON (a.details->>'target_user_id')::bigint=u.id
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


@pytest.mark.parametrize(
    'password',
    (
        'ChangeMe-ChangeMe1!',
        'Default-Password1!',
        'Password-Password1!',
    ),
)
def test_local_password_policy_rejects_blocklisted_markers_with_suffixes(password: str) -> None:
    with pytest.raises(ValueError, match='Passwort'):
        auth_issuer.validate_local_password(password, 'kueche.operator')


@LIVE_DATABASE
def test_database_role_provisioning_rejects_weak_or_reused_issuer_secret(
    owner_engine: Engine,
) -> None:
    with pytest.raises(RuntimeError, match='Issuer|32|stark'):
        database.provision_database_roles(
            owner_engine,
            app_password=APP_PASSWORD,
            backup_password=BACKUP_PASSWORD,
            auth_issuer_password='x',
        )
    with pytest.raises(RuntimeError, match='eigene|unterscheiden|Issuer'):
        database.provision_database_roles(
            owner_engine,
            app_password=APP_PASSWORD,
            backup_password=BACKUP_PASSWORD,
            auth_issuer_password=APP_PASSWORD,
        )


@LIVE_DATABASE
def test_init_database_rejects_missing_role_credentials(owner_engine: Engine) -> None:
    assert DATABASE_URL is not None
    with pytest.raises(RuntimeError, match='cafeteria_app|32|stark'):
        database.init_database(
            DATABASE_URL,
            str(ROOT / 'database' / 'schema.sql'),
            str(ROOT / 'database' / 'seed.sql'),
            permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        )


@LIVE_DATABASE
def test_database_validator_proves_dedicated_issuer_least_privilege(owner_engine: Engine) -> None:
    status = database.validate_database(owner_engine)

    assert status['auth_issuer_ready'] is True
    assert status['auth_issuer_direct_table_privilege_count'] == 0
    assert status['auth_issuer_direct_sequence_privilege_count'] == 0
    assert status['auth_issuer_membership_count'] == 0
    assert status['auth_issuer_can_create_cafeteria_schema'] is False
    assert status['auth_issuer_can_create_public_schema'] is False
    assert status['auth_issuer_connection_limit'] == -1
    assert status['auth_issuer_valid_until_infinity'] is True
    assert status['auth_issuer_role_config_valid'] is True
    assert status['ready'] is True


@LIVE_DATABASE
def test_entra_role_changes_are_audited_by_verified_target_without_pii(
    owner_engine: Engine,
) -> None:
    issuer_engine = create_engine(
        _role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    claims = {
        'tid': '00000000-0000-0000-0000-000000000911',
        'oid': '00000000-0000-0000-0000-000000000922',
        'sub': 'entra-audit-subject',
        'name': 'Audit Target',
        'email': 'audit-target@example.invalid',
        'preferred_username': 'audit-target@example.invalid',
    }
    try:
        user_id = database.upsert_entra_user(issuer_engine, claims, ['Cafeteria.Editor'])
        database.upsert_entra_user(
            issuer_engine,
            claims,
            ['Cafeteria.Admin', 'Cafeteria.Publisher'],
        )
    finally:
        issuer_engine.dispose()
    with owner_engine.connect() as connection:
        event = connection.execute(
            text(
                '''
                SELECT actor_user_id, details
                FROM cafeteria.audit_events
                WHERE action='auth.entra_roles_changed'
                  AND (details->>'target_user_id')::bigint=:user_id
                ORDER BY id DESC LIMIT 1
                '''
            ),
            {'user_id': user_id},
        ).mappings().one()

    assert event.actor_user_id == user_id
    assert event.details['old_roles'] == ['Cafeteria.Editor']
    assert event.details['new_roles'] == ['Cafeteria.Admin', 'Cafeteria.Publisher']
    assert event.details['authz_version'] > 0
    serialized = str(event.details).casefold()
    assert 'audit-target@example.invalid' not in serialized
    assert 'entra-audit-subject' not in serialized
