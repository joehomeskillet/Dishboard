from __future__ import annotations

import os
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
from cafeteria.auth.service import trusted_client_address


ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
REDIS_URL = os.getenv('TEST_REDIS_URL')
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
        app_password='test-app-secret',
        backup_password='test-backup-secret',
        auth_issuer_password='test-auth-issuer-secret',
    )
    app_url = _role_database_url('cafeteria_app', 'test-app-secret')
    issuer_url = _role_database_url('cafeteria_auth_issuer', 'test-auth-issuer-secret')
    monkeypatch.setenv('DATABASE_URL', app_url)
    monkeypatch.setenv('AUTH_ISSUER_DATABASE_URL', issuer_url)
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
    application = create_app()
    application.config.update(TESTING=True)
    issuer_engine = application.extensions['cafeteria_auth_issuer_db']
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
        username=username,
        display_name='Lokale Redaktion',
        password='Correct-Horse-2026!Battery',
        roles=['Cafeteria.Editor'],
    )


def test_local_login_succeeds_without_session_roles(auth_app: tuple[Any, Engine, Engine]) -> None:
    application, _, issuer_engine = auth_app
    user_id = _provision(issuer_engine)
    client = application.test_client()

    response = client.post(
        '/auth/local',
        data={'username': 'local.editor', 'password': 'Correct-Horse-2026!Battery'},
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/cafeteria')
    with client.session_transaction() as flask_session:
        assert flask_session['user']['id'] == user_id
        assert flask_session['authz_version'] > 0
        assert 'roles' not in flask_session


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
        data={'username': 'local.editor', 'password': 'wrong-password-value'},
    )
    missing = client.post(
        '/auth/local',
        data={'username': 'unknown.user', 'password': 'wrong-password-value'},
    )
    with owner_engine.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'),
            {'id': user_id},
        )
    disabled = client.post(
        '/auth/local',
        data={'username': 'local.editor', 'password': 'Correct-Horse-2026!Battery'},
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
        data={'username': 'local.editor', 'password': 'Correct-Horse-2026!Battery'},
    )

    assert response.status_code == 503
    with client.session_transaction() as flask_session:
        assert 'user' not in flask_session


def test_real_redis_rate_limit_isolated_by_username_and_socket_ip(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, _, _ = auth_app
    client = application.test_client()
    data = {'username': 'unknown.user', 'password': 'wrong-password-value'}

    for spoofed_ip in ('203.0.113.1', '203.0.113.2', '203.0.113.3', '203.0.113.4', '203.0.113.5'):
        response = client.post(
            '/auth/local',
            data=data,
            environ_base={'REMOTE_ADDR': '198.51.100.10'},
            headers={'X-Forwarded-For': spoofed_ip},
        )
        assert response.status_code == 401
    limited = client.post(
        '/auth/local',
        data=data,
        environ_base={'REMOTE_ADDR': '198.51.100.10'},
        headers={'X-Forwarded-For': '203.0.113.99'},
    )
    assert limited.status_code == 429

    other_ip = client.post(
        '/auth/local',
        data=data,
        environ_base={'REMOTE_ADDR': '198.51.100.11'},
    )
    other_user = client.post(
        '/auth/local',
        data={'username': 'another.user', 'password': 'wrong-password-value'},
        environ_base={'REMOTE_ADDR': '198.51.100.10'},
    )
    assert other_ip.status_code == 401
    assert other_user.status_code == 401


def test_forwarded_client_ip_is_used_only_for_trusted_loopback_proxy() -> None:
    cidrs = ('127.0.0.0/8', '::1/128')
    trusted_environ = {
        'REMOTE_ADDR': '203.0.113.20',
        'werkzeug.proxy_fix.orig': {'REMOTE_ADDR': '127.0.0.1'},
    }
    direct_environ = {
        'REMOTE_ADDR': '203.0.113.20',
        'werkzeug.proxy_fix.orig': {'REMOTE_ADDR': '198.51.100.10'},
    }

    assert trusted_client_address(trusted_environ, '203.0.113.20', cidrs) == '203.0.113.20'
    assert trusted_client_address(direct_environ, '203.0.113.20', cidrs) == '198.51.100.10'


def test_fifth_failed_login_locks_and_audits_local_user(
    auth_app: tuple[Any, Engine, Engine],
) -> None:
    application, owner_engine, issuer_engine = auth_app
    user_id = _provision(issuer_engine)
    client = application.test_client()

    for _ in range(5):
        response = client.post(
            '/auth/local',
            data={'username': 'local.editor', 'password': 'Wrong-2026!Password'},
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
        data={'username': 'local.editor', 'password': 'Correct-Horse-2026!Battery'},
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
