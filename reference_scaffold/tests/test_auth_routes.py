from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from cafeteria import create_app
from cafeteria import db as database
from cafeteria.auth import issuer as auth_issuer
from cafeteria.auth import routes as auth_routes
from cafeteria.auth.service import login_rate_key, trusted_client_address

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
REDIS_URL = os.getenv('TEST_REDIS_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
ACTOR_IDENTIFIER = 'routes.admin@example.invalid'
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason='TEST_DATABASE_URL und TEST_REDIS_URL für isolierte Auth-Tests fehlen.',
)


def _role_database_url(role: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role,
        password=password,
    ).render_as_string(hide_password=False)


class FakePipeline:
    def __init__(self, store: dict[str, int]) -> None:
        self.store = store
        self.key = ''

    def incr(self, key: str) -> FakePipeline:
        self.key = key
        return self

    def expire(self, key: str, seconds: int, *, nx: bool = False) -> FakePipeline:
        assert key == self.key
        assert seconds > 0
        assert nx is True
        return self

    def execute(self) -> list[int | bool]:
        self.store[self.key] = self.store.get(self.key, 0) + 1
        return [self.store[self.key], True]


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def pipeline(self, *, transaction: bool) -> FakePipeline:
        assert transaction is True
        return FakePipeline(self.store)

    def delete(self, key: str) -> int:
        return int(self.store.pop(key, None) is not None)


class BrokenRedis:
    def pipeline(self, *, transaction: bool) -> FakePipeline:
        raise RedisError('test redis unavailable')


class FakeMsalClient:
    def __init__(self, claims: dict[str, Any]) -> None:
        self.claims = claims

    def acquire_token_by_auth_code_flow(
        self,
        flow: dict[str, Any],
        query: Any,
    ) -> dict[str, Any]:
        assert flow == {'state': 'test-state'}
        return {'id_token_claims': self.claims}


@pytest.fixture
def auth_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Any, Engine, Engine]]:
    assert DATABASE_URL is not None
    owner_engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    with owner_engine.begin() as connection:
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
    app_url = _role_database_url('cafeteria_app', APP_PASSWORD)
    monkeypatch.setenv('DATABASE_URL', app_url)
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD', ISSUER_PASSWORD)
    assert REDIS_URL is not None
    redis_client = Redis.from_url(REDIS_URL)
    redis_client.flushdb()
    monkeypatch.setenv('SESSION_REDIS_URL', REDIS_URL)
    monkeypatch.setenv('LOCAL_AUTH_ENABLED', 'true')
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')
    monkeypatch.setenv('FLASK_SECRET_KEY', 'test-only-auth-secret')
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'false')
    monkeypatch.setenv('SEED_DEMO', 'false')
    monkeypatch.setenv('DEMO_TODAY', '')
    monkeypatch.setenv('ENTRA_ENABLED', 'true')
    application = create_app()
    application.config.update(TESTING=True)
    issuer_engine = application.extensions['cafeteria_auth_issuer_db']
    database.upsert_entra_user(
        issuer_engine,
        {
            'tid': '00000000-0000-0000-0000-000000000611',
            'oid': '00000000-0000-0000-0000-000000000622',
            'sub': 'routes-admin-actor',
            'name': 'Routes Admin',
            'preferred_username': ACTOR_IDENTIFIER,
        },
        ['Cafeteria.Admin'],
    )
    try:
        yield application, owner_engine, issuer_engine
    finally:
        application.extensions['cafeteria_db'].dispose()
        issuer_engine.dispose()
        with owner_engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
        owner_engine.dispose()
        redis_client.flushdb()
        redis_client.close()


def _provision(issuer_engine: Engine, username: str = 'local.editor') -> int:
    return auth_issuer.provision_local_user(
        issuer_engine,
        actor_identifier=ACTOR_IDENTIFIER,
        username=username,
        display_name='Lokale Redaktion',
        password='Correct-Horse-2026!Battery',
        roles=['Cafeteria.Editor'],
    )


def _csrf_payload(client: Any, **values: str) -> dict[str, str]:
    assert client.get('/auth/local').status_code == 200
    with client.session_transaction() as flask_session:
        token = flask_session['_csrf_token']
    return {'csrf_token': token, **values}


def test_local_login_succeeds_without_session_roles(auth_app: tuple[Any, Engine, Engine]) -> None:
    application, _, issuer_engine = auth_app
    user_id = _provision(issuer_engine)
    client = application.test_client()

    response = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='local.editor',
            password='Correct-Horse-2026!Battery',
        ),
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/cafeteria')
    with client.session_transaction() as flask_session:
        assert flask_session['user']['id'] == user_id
        assert flask_session['authz_version'] > 0
        assert 'roles' not in flask_session


def test_entra_login_redirects_to_local_login_when_entra_is_disabled(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, _ = auth_app
    application.config.update(ENTRA_ENABLED=False, LOCAL_AUTH_ENABLED=True)
    client = application.test_client()

    response = client.get('/auth/login')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/local')
    assert client.get('/auth/callback').status_code == 404
    assert client.get('/auth/frontchannel-logout').status_code == 404


def test_entra_login_fails_closed_when_all_login_providers_are_disabled(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, _ = auth_app
    application.config.update(ENTRA_ENABLED=False, LOCAL_AUTH_ENABLED=False)

    response = application.test_client().get('/auth/login')

    assert response.status_code == 503


def test_local_login_is_default_off_and_get_renders_dedicated_template(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, _ = auth_app
    client = application.test_client()

    enabled = client.get('/auth/local')
    assert enabled.status_code == 200
    assert '<form' in enabled.get_data(as_text=True)
    assert 'name="username"' in enabled.get_data(as_text=True)
    assert 'name="password"' in enabled.get_data(as_text=True)
    assert 'name="csrf_token"' in enabled.get_data(as_text=True)

    application.config['LOCAL_AUTH_ENABLED'] = False
    assert client.get('/auth/local').status_code == 404
    assert client.post('/auth/local', data={}).status_code == 404


def test_local_login_failures_are_generic_and_disabled_users_cannot_login(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, owner_engine, issuer_engine = auth_app
    user_id = _provision(issuer_engine)
    client = application.test_client()

    wrong = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='local.editor',
            password='wrong-password-value',
        ),
    )
    missing = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='unknown.user',
            password='wrong-password-value',
        ),
    )
    with owner_engine.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'),
            {'id': user_id},
        )
    disabled = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='local.editor',
            password='Correct-Horse-2026!Battery',
        ),
    )

    assert wrong.status_code == missing.status_code == disabled.status_code == 401
    assert wrong.get_data(as_text=True) == missing.get_data(as_text=True) == disabled.get_data(as_text=True)
    assert client.post('/auth/signup', data={}).status_code == 404


def test_local_login_fails_closed_when_redis_is_unavailable(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, issuer_engine = auth_app
    _provision(issuer_engine)
    application.extensions['cafeteria_rate_redis'] = BrokenRedis()
    client = application.test_client()

    response = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='local.editor',
            password='Correct-Horse-2026!Battery',
        ),
    )

    assert response.status_code == 503
    with client.session_transaction() as flask_session:
        assert 'user' not in flask_session


def test_real_redis_rate_limit_isolated_by_username_and_socket_ip(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, _ = auth_app
    client = application.test_client()
    for spoofed_ip in ('203.0.113.1', '203.0.113.2', '203.0.113.3', '203.0.113.4', '203.0.113.5'):
        response = client.post(
            '/auth/local',
            data=_csrf_payload(
                client,
                username='unknown.user',
                password='wrong-password-value',
            ),
            environ_base={'REMOTE_ADDR': '198.51.100.10'},
            headers={'X-Forwarded-For': spoofed_ip},
        )
        assert response.status_code == 401
    limited = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='unknown.user',
            password='wrong-password-value',
        ),
        environ_base={'REMOTE_ADDR': '198.51.100.10'},
        headers={'X-Forwarded-For': '203.0.113.99'},
    )
    assert limited.status_code == 429

    other_ip = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='unknown.user',
            password='wrong-password-value',
        ),
        environ_base={'REMOTE_ADDR': '198.51.100.11'},
    )
    other_user = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='another.user',
            password='wrong-password-value',
        ),
        environ_base={'REMOTE_ADDR': '198.51.100.10'},
    )
    assert other_ip.status_code == 401
    assert other_user.status_code == 401


def test_forwarded_client_ip_is_used_only_for_trusted_loopback_proxy() -> None:
    peers = ('127.0.0.1', '::1')
    trusted_environ = {
        'REMOTE_ADDR': '127.0.0.1',
        'HTTP_X_FORWARDED_FOR': '203.0.113.20',
    }
    direct_environ = {
        'REMOTE_ADDR': '198.51.100.10',
        'HTTP_X_FORWARDED_FOR': '203.0.113.20',
    }

    assert trusted_client_address(trusted_environ, '127.0.0.1', peers) == '203.0.113.20'
    assert trusted_client_address(direct_environ, '198.51.100.10', peers) == '198.51.100.10'


def test_fifth_failed_login_locks_and_audits_local_user(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, owner_engine, issuer_engine = auth_app
    user_id = _provision(issuer_engine)
    client = application.test_client()

    for _ in range(5):
        response = client.post(
            '/auth/local',
            data=_csrf_payload(
                client,
                username='local.editor',
                password='Wrong-2026!Password',
            ),
        )
        assert response.status_code == 401

    with owner_engine.connect() as connection:
        row = connection.execute(
            text(
                '''
                SELECT c.failed_login_count,
                       c.locked_until > clock_timestamp() AS locked,
                       (SELECT count(*) FROM cafeteria.audit_events a
                        WHERE a.action='auth.local_login_locked'
                          AND (a.details->>'user_id')::bigint=:user_id) AS audit_count
                FROM cafeteria.local_credentials c
                WHERE c.user_id=:user_id
                '''
            ),
            {'user_id': user_id},
        ).one()
    assert row.failed_login_count == 5
    assert row.locked is True
    assert row.audit_count == 1


def test_role_revocation_invalidates_live_session(auth_app: tuple[Any, Engine, Engine]) -> None:
    application, owner_engine, issuer_engine = auth_app
    user_id = _provision(issuer_engine)
    client = application.test_client()
    login = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='local.editor',
            password='Correct-Horse-2026!Battery',
        ),
    )
    assert login.status_code == 302

    with owner_engine.begin() as connection:
        connection.execute(
            text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'),
            {'id': user_id},
        )
    protected = client.get('/admin/cafeteria')

    assert protected.status_code == 401
    with client.session_transaction() as flask_session:
        assert 'user' not in flask_session
        assert 'authz_version' not in flask_session


def test_entra_callback_purges_empty_roles_before_denial(
    auth_app: tuple[Any, Engine, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, owner_engine, issuer_engine = auth_app
    claims = {
        'tid': '00000000-0000-0000-0000-000000000411',
        'oid': '00000000-0000-0000-0000-000000000422',
        'sub': 'entra-empty-role-subject',
        'name': 'Entra ohne Rolle',
        'roles': [],
    }
    application.config['ENTRA_TENANT_ID'] = claims['tid']
    user_id = database.upsert_entra_user(
        issuer_engine,
        claims,
        ['Cafeteria.Editor'],
    )
    with owner_engine.connect() as connection:
        before_version = int(
            connection.execute(
                text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                {'id': user_id},
            ).scalar_one()
        )
    monkeypatch.setattr(auth_routes, '_client', lambda: FakeMsalClient(claims))
    client = application.test_client()
    with client.session_transaction() as flask_session:
        flask_session['auth_flow'] = {'state': 'test-state'}

    response = client.get('/auth/callback')

    with owner_engine.connect() as connection:
        row = connection.execute(
            text(
                '''
                SELECT authz_version,
                       (SELECT count(*) FROM cafeteria.user_role_cache r
                        WHERE r.user_id=u.id) AS role_count
                FROM cafeteria.users u WHERE id=:id
                '''
            ),
            {'id': user_id},
        ).mappings().one()
    assert response.status_code == 403
    assert row.role_count == 0
    assert row.authz_version > before_version
    with client.session_transaction() as flask_session:
        assert 'user' not in flask_session


@pytest.mark.parametrize(
    'supplied_roles',
    (
        ['Cafeteria.Editor', 'Unexpected.Role'],
        ['Cafeteria.Editor', 'Cafeteria.Editor'],
    ),
)
def test_entra_callback_rejects_invalid_roles_without_identity_mutation(
    auth_app: tuple[Any, Engine, Engine],
    monkeypatch: pytest.MonkeyPatch,
    supplied_roles: list[str],
) -> None:
    application, owner_engine, issuer_engine = auth_app
    original_claims = {
        'tid': '00000000-0000-0000-0000-000000000711',
        'oid': '00000000-0000-0000-0000-000000000722',
        'sub': 'entra-invalid-role-subject',
        'name': 'Unveränderte Identität',
        'preferred_username': 'unchanged@example.invalid',
    }
    application.config['ENTRA_TENANT_ID'] = original_claims['tid']
    user_id = database.upsert_entra_user(
        issuer_engine,
        original_claims,
        ['Cafeteria.Editor'],
    )
    with owner_engine.connect() as connection:
        before = connection.execute(
            text(
                '''
                SELECT display_name, preferred_username, last_seen_roles,
                       last_login_at, authz_version,
                       (SELECT array_agg(role_code ORDER BY role_code)
                          FROM cafeteria.user_role_cache r WHERE r.user_id=u.id) AS roles
                FROM cafeteria.users u WHERE id=:id
                '''
            ),
            {'id': user_id},
        ).one()
    invalid_claims = original_claims | {
        'name': 'Darf nicht gespeichert werden',
        'preferred_username': 'mutated@example.invalid',
        'roles': supplied_roles,
    }
    monkeypatch.setattr(auth_routes, '_client', lambda: FakeMsalClient(invalid_claims))
    client = application.test_client()
    with client.session_transaction() as flask_session:
        flask_session['auth_flow'] = {'state': 'test-state'}

    response = client.get('/auth/callback')

    with owner_engine.connect() as connection:
        after = connection.execute(
            text(
                '''
                SELECT display_name, preferred_username, last_seen_roles,
                       last_login_at, authz_version,
                       (SELECT array_agg(role_code ORDER BY role_code)
                          FROM cafeteria.user_role_cache r WHERE r.user_id=u.id) AS roles
                FROM cafeteria.users u WHERE id=:id
                '''
            ),
            {'id': user_id},
        ).one()
    assert response.status_code == 403
    assert after == before
    with client.session_transaction() as flask_session:
        assert 'user' not in flask_session


def test_entra_callback_accepts_exact_unique_application_roles(
    auth_app: tuple[Any, Engine, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, owner_engine, _ = auth_app
    claims = {
        'tid': '00000000-0000-0000-0000-000000000811',
        'oid': '00000000-0000-0000-0000-000000000822',
        'sub': 'entra-valid-role-subject',
        'name': 'Gültige Entra Identität',
        'roles': ['Cafeteria.Publisher', 'Cafeteria.Editor'],
    }
    application.config['ENTRA_TENANT_ID'] = claims['tid']
    monkeypatch.setattr(auth_routes, '_client', lambda: FakeMsalClient(claims))
    client = application.test_client()
    with client.session_transaction() as flask_session:
        flask_session['auth_flow'] = {'state': 'test-state'}

    response = client.get('/auth/callback')

    with owner_engine.connect() as connection:
        roles = connection.execute(
            text(
                '''
                SELECT array_agg(r.role_code ORDER BY r.role_code)
                FROM cafeteria.users u
                JOIN cafeteria.user_role_cache r ON r.user_id=u.id
                WHERE u.entra_tenant_id=CAST(:tid AS uuid)
                  AND u.entra_object_id=CAST(:oid AS uuid)
                '''
            ),
            {'tid': claims['tid'], 'oid': claims['oid']},
        ).scalar_one()
    assert response.status_code == 302
    assert roles == ['Cafeteria.Editor', 'Cafeteria.Publisher']
    with client.session_transaction() as flask_session:
        assert flask_session['user']['provider'] == 'entra'
        assert 'roles' not in flask_session


def test_entra_callback_never_reactivates_disabled_user(
    auth_app: tuple[Any, Engine, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, owner_engine, issuer_engine = auth_app
    claims = {
        'tid': '00000000-0000-0000-0000-000000000511',
        'oid': '00000000-0000-0000-0000-000000000522',
        'sub': 'entra-disabled-subject',
        'name': 'Entra deaktiviert',
        'roles': ['Cafeteria.Editor'],
    }
    application.config['ENTRA_TENANT_ID'] = claims['tid']
    user_id = database.upsert_entra_user(issuer_engine, claims, ['Cafeteria.Editor'])
    with owner_engine.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'),
            {'id': user_id},
        )
    monkeypatch.setattr(auth_routes, '_client', lambda: FakeMsalClient(claims))
    client = application.test_client()
    with client.session_transaction() as flask_session:
        flask_session['auth_flow'] = {'state': 'test-state'}

    response = client.get('/auth/callback')

    with owner_engine.connect() as connection:
        disabled_at = connection.execute(
            text('SELECT disabled_at FROM cafeteria.users WHERE id=:id'),
            {'id': user_id},
        ).scalar_one()
    assert response.status_code == 403
    assert disabled_at is not None
    with client.session_transaction() as flask_session:
        assert 'user' not in flask_session


def test_local_login_requires_csrf_before_rate_limit_or_auth(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, issuer_engine = auth_app
    _provision(issuer_engine)
    client = application.test_client()
    valid = _csrf_payload(
        client,
        username='local.editor',
        password='Correct-Horse-2026!Battery',
    )
    with client.session_transaction() as flask_session:
        flask_session['sentinel'] = 'preserved-before-validation'
    redis_client = application.extensions['cafeteria_rate_redis']
    rate_key = login_rate_key('local.editor', '127.0.0.1')

    missing = client.post(
        '/auth/local',
        data={'username': 'local.editor', 'password': 'Correct-Horse-2026!Battery'},
    )
    assert missing.status_code == 400
    assert redis_client.exists(rate_key) == 0
    with client.session_transaction() as flask_session:
        assert flask_session['sentinel'] == 'preserved-before-validation'

    wrong = client.post(
        '/auth/local',
        data={
            'csrf_token': '0' * 64,
            'username': 'local.editor',
            'password': 'Correct-Horse-2026!Battery',
        },
    )
    assert wrong.status_code == 400
    assert redis_client.exists(rate_key) == 0
    with client.session_transaction() as flask_session:
        assert flask_session['sentinel'] == 'preserved-before-validation'

    accepted = client.post('/auth/local', data=valid)
    assert accepted.status_code == 302
    with client.session_transaction() as flask_session:
        assert flask_session['user']['id'] > 0
        assert 'sentinel' not in flask_session


def test_csrf_tokens_are_patient_safe_fixed_hex(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, _ = auth_app
    client = application.test_client()
    forbidden = ('chf', 'intern', 'extern', '0.00', 'price', 'preis')

    for _ in range(128):
        with client.session_transaction() as flask_session:
            flask_session.pop('_csrf_token', None)
        response = client.get('/auth/local')
        assert response.status_code == 200
        body = response.get_data(as_text=True).casefold()
        with client.session_transaction() as flask_session:
            token = flask_session['_csrf_token']
        assert re.fullmatch(r'[0-9a-f]{64}', token)
        assert token in body
        assert all(marker not in token.casefold() for marker in forbidden)
        for path in ('/patienten/heute/', '/patienten/wochenplan/'):
            patient_body = client.get(path).get_data(as_text=True).casefold()
            assert all(marker not in patient_body for marker in forbidden)


def test_secure_cookie_flags_are_emitted(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, _ = auth_app
    application.config['SESSION_COOKIE_SECURE'] = True

    response = application.test_client().get('/auth/local')
    cookie = response.headers.get('Set-Cookie', '')

    assert 'Secure' in cookie
    assert 'HttpOnly' in cookie
    assert 'SameSite=Lax' in cookie


def test_real_redis_connection_failure_blocks_local_login(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, issuer_engine = auth_app
    _provision(issuer_engine)
    application.extensions['cafeteria_rate_redis'] = Redis(
        host='127.0.0.1',
        port=1,
        socket_connect_timeout=0.05,
        socket_timeout=0.05,
    )
    client = application.test_client()

    response = client.post(
        '/auth/local',
        data=_csrf_payload(
            client,
            username='local.editor',
            password='Correct-Horse-2026!Battery',
        ),
    )

    assert response.status_code == 503
    with client.session_transaction() as flask_session:
        assert 'user' not in flask_session
