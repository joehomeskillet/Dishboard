from __future__ import annotations

import secrets
from io import BytesIO
from typing import Any

import pytest
from flask import Blueprint, Flask
from werkzeug.datastructures import MultiDict

from cafeteria.auth import routes
from cafeteria.auth.service import AuthorizationState


TENANT = '00000000-0000-0000-0000-000000000951'
ISSUER = f'https://login.microsoftonline.com/{TENANT}/v2.0'


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
def app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    application = Flask(__name__)
    admin = Blueprint('admin', __name__)

    @admin.get('/admin/cafeteria')
    def cafeteria() -> str:
        return ''

    application.config.update(
        TESTING=True,
        SECRET_KEY=secrets.token_bytes(32),
        ENTRA_ENABLED=True,
        ENTRA_TENANT_ID=TENANT,
        ENTRA_CLIENT_ID='test-client-id',
    )
    application.extensions['cafeteria_auth_issuer_db'] = object()
    application.extensions['cafeteria_db'] = object()
    application.register_blueprint(admin)
    application.register_blueprint(routes.bp)
    identity = AuthorizationState(
        user_id=1,
        display_name='Entra Test',
        auth_provider='entra',
        authz_version=1,
        roles=('Cafeteria.Editor',),
    )
    monkeypatch.setattr(routes, 'upsert_entra_user', lambda *_: identity.user_id)
    monkeypatch.setattr(routes, 'load_user_authorization', lambda *_: identity)
    monkeypatch.setattr(routes, 'record_access_event', lambda *_args, **_kwargs: None)
    return application


def _login(client: Any, monkeypatch: pytest.MonkeyPatch, *, provider_sid: str | None) -> None:
    claims = {
        'tid': TENANT,
        'oid': '00000000-0000-0000-0000-000000000952',
        'roles': ['Cafeteria.Editor'],
    }
    if provider_sid is not None:
        claims['sid'] = provider_sid
    monkeypatch.setattr(routes, '_client', lambda: FakeMsalClient(claims))
    with client.session_transaction() as current:
        current['auth_flow'] = {'state': 'test-state'}
    assert client.get('/auth/callback').status_code == 302


@pytest.mark.parametrize('method', ('get', 'post'))
def test_frontchannel_logout_matches_issuer_and_saved_provider_sid(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    client = app.test_client()
    _login(client, monkeypatch, provider_sid='provider-session-id')
    with client.session_transaction() as current:
        assert current['user']['sid'] == 'provider-session-id'

    mismatch = client.get(
        '/auth/frontchannel-logout',
        query_string={'iss': ISSUER, 'sid': 'different-session-id'},
    )

    assert mismatch.status_code == 200
    assert mismatch.headers['Cache-Control'] == 'no-store'
    with client.session_transaction() as current:
        assert current['user']['sid'] == 'provider-session-id'

    parameters = {'iss': ISSUER, 'sid': 'provider-session-id'}
    kwargs = {'query_string': parameters} if method == 'get' else {'data': parameters}
    match = getattr(client, method)('/auth/frontchannel-logout', **kwargs)

    assert match.status_code == 200
    assert match.get_data() == b''
    assert match.headers['Cache-Control'] == 'no-store'
    with client.session_transaction() as current:
        assert 'user' not in current


@pytest.mark.parametrize(
    ('method', 'query_string', 'data', 'expected_status'),
    (
        ('get', None, None, 400),
        ('post', None, None, 400),
        ('get', {'iss': ISSUER}, None, 400),
        ('post', None, {'sid': 'provider-session-id'}, 400),
        (
            'get',
            MultiDict((('iss', ISSUER), ('iss', ISSUER), ('sid', 'provider-session-id'))),
            None,
            400,
        ),
        (
            'post',
            None,
            MultiDict(
                (('iss', ISSUER), ('sid', 'provider-session-id'), ('sid', 'provider-session-id')),
            ),
            400,
        ),
        ('get', {'iss': ISSUER, 'sid': 'provider-session-id', 'extra': 'value'}, None, 400),
        (
            'post',
            None,
            {
                'iss': ISSUER,
                'sid': 'provider-session-id',
                'extra': (BytesIO(b'untrusted'), 'extra.txt'),
            },
            400,
        ),
        (
            'post',
            {'sid': 'provider-session-id'},
            {'iss': ISSUER, 'sid': 'provider-session-id'},
            400,
        ),
        ('get', {'iss': 'https://issuer.invalid', 'sid': 'provider-session-id'}, None, 200),
        ('post', None, {'iss': ISSUER, 'sid': 'different-session-id'}, 200),
    ),
)
def test_frontchannel_logout_ignores_invalid_or_mismatched_requests(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    query_string: Any,
    data: Any,
    expected_status: int,
) -> None:
    client = app.test_client()
    _login(client, monkeypatch, provider_sid='provider-session-id')

    response = getattr(client, method)(
        '/auth/frontchannel-logout',
        query_string=query_string,
        data=data,
    )

    assert response.status_code == expected_status
    assert response.get_data() == b''
    assert response.headers['Cache-Control'] == 'no-store'
    with client.session_transaction() as current:
        assert current['user']['sid'] == 'provider-session-id'


def test_frontchannel_logout_default_denies_when_id_token_has_no_sid(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = app.test_client()
    _login(client, monkeypatch, provider_sid=None)

    response = client.post(
        '/auth/frontchannel-logout',
        data={'iss': ISSUER, 'sid': 'untrusted-session-id'},
    )

    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    with client.session_transaction() as current:
        assert current['user']['provider'] == 'entra'
        assert 'sid' not in current['user']
    assert 'Entra ID token has no sid claim; front-channel logout will default-deny.' in caplog.text


def test_frontchannel_logout_never_revokes_local_session(app: Flask) -> None:
    client = app.test_client()
    with client.session_transaction() as current:
        current['user'] = {'id': 2, 'name': 'Local Test', 'provider': 'local'}
        current['authz_version'] = 1

    response = client.get(
        '/auth/frontchannel-logout',
        query_string={'iss': ISSUER, 'sid': 'provider-session-id'},
    )

    assert response.status_code == 200
    assert response.get_data() == b''
    assert response.headers['Cache-Control'] == 'no-store'
    with client.session_transaction() as current:
        assert current['user']['provider'] == 'local'
