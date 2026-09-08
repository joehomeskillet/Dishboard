"""Authentication outcomes on real PostgreSQL and server-side Redis sessions."""
from unittest.mock import Mock

import pytest
from redis.exceptions import RedisError
from requests.exceptions import ConnectionError as ProviderConnectionError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from cafeteria.auth import routes
from test_auth_routes import auth_app, _csrf_payload, _provision, FakeMsalClient  # noqa: F401

SENTINEL = 'access-history-secret-sentinel-2026'


def events(owner):
    with owner.connect() as connection:
        return connection.execute(text('''SELECT public_id,action,actor_user_id,details
            FROM cafeteria.audit_events WHERE entity_type='authentication' ORDER BY id''')).all()


def audit_outage(owner):
    with owner.begin() as connection:
        connection.execute(text('''REVOKE EXECUTE ON FUNCTION
            cafeteria.record_auth_access_v25(uuid,text,text,text,bigint,bigint)
            FROM cafeteria_auth_issuer'''))


@pytest.mark.parametrize('case,status,reason', [
    ('valid', 302, None), ('wrong', 401, 'credentials'), ('unknown', 401, 'credentials'),
    ('disabled', 401, 'credentials'), ('no_roles', 401, 'credentials'),
    ('locked', 401, 'credentials'), ('throttled', 429, 'throttled'),
    ('rate_unavailable', 503, 'unavailable'), ('clear_unavailable', 503, 'unavailable'),
    ('db_unavailable', 503, 'unavailable'), ('audit_outage', 503, None),
])
def test_local_outcomes_keep_unverified_actor_null(auth_app, monkeypatch, caplog, case, status, reason):  # noqa: F811
    app, owner, issuer = auth_app
    actor = _provision(issuer, owner)
    client = app.test_client()
    data = _csrf_payload(client, username='local.editor', password='Correct-Horse-2026!Battery')
    if case == 'wrong':
        data['password'] = SENTINEL
    if case == 'unknown':
        data['username'] = SENTINEL
    if case in ('disabled', 'no_roles', 'locked'):
        with owner.begin() as connection:
            if case == 'disabled':
                connection.execute(text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'), {'id': actor})
            elif case == 'no_roles':
                connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor})
            else:
                connection.execute(text("UPDATE cafeteria.local_credentials SET failed_login_count=5,locked_until=clock_timestamp()+interval '1 hour' WHERE user_id=:id"), {'id': actor})
    if case == 'throttled':
        app.extensions['cafeteria_rate_redis'].set(routes.login_rate_key('local.editor', '127.0.0.1'), 5, ex=300)
    if case in ('rate_unavailable', 'clear_unavailable'):
        name = 'consume_login_attempt' if case == 'rate_unavailable' else 'clear_login_attempts'
        monkeypatch.setattr(routes, name, Mock(side_effect=routes.RateLimitUnavailable(SENTINEL)))
    if case == 'db_unavailable':
        monkeypatch.setattr(routes, 'authenticate_local_user', Mock(side_effect=SQLAlchemyError(SENTINEL)))
    if case == 'audit_outage':
        audit_outage(owner)
    response = client.post('/auth/local', data=data)
    assert response.status_code == status
    recorded = events(owner)
    if case == 'audit_outage':
        assert recorded == []
        assert 'Authentication decision audit unavailable.' in caplog.text
        with owner.connect() as connection:
            verified = connection.execute(text('''SELECT last_login_at,failed_login_count,locked_until
                FROM cafeteria.users JOIN cafeteria.local_credentials ON user_id=users.id WHERE users.id=:id'''), {'id': actor}).one()
        assert verified.last_login_at is not None and verified.failed_login_count == 0 and verified.locked_until is None
    else:
        assert len(recorded) == 1
        event = recorded[0]
        assert event.actor_user_id == (actor if case == 'valid' else None)
        assert event.action == ('auth.login.accepted' if case == 'valid' else
                                'auth.login.unavailable' if reason == 'unavailable' else 'auth.login.rejected')
        assert set(event.details) == {'provider', 'reason', 'authz_version'}
        assert event.details['provider'] == 'local' and event.details['reason'] == reason
        assert (event.details['authz_version'] is not None) == (case == 'valid')
    assert SENTINEL not in repr(recorded) and SENTINEL not in caplog.text
    with client.session_transaction() as session:
        assert ('user' in session) == (case == 'valid')
    if case == 'locked':
        with owner.connect() as connection:
            row = connection.execute(text('''SELECT failed_login_count,locked_until>clock_timestamp() AS locked,
                last_login_at FROM cafeteria.local_credentials JOIN cafeteria.users ON users.id=user_id WHERE user_id=:id'''), {'id': actor}).one()
        assert row.failed_login_count == 6 and row.locked and row.last_login_at is None


@pytest.mark.parametrize('case,status,reason', [
    ('valid', 302, None), ('missing_flow', 400, 'flow'), ('state', 400, 'flow'),
    ('provider_error', 401, 'credentials'), ('network', 503, 'unavailable'),
    ('tenant', 403, 'flow'), ('audience', 403, 'flow'), ('claims_type', 403, 'flow'),
    ('roles_type', 403, 'role'), ('roles_unknown', 403, 'role'), ('roles_duplicate', 403, 'role'),
    ('roles_empty', 403, 'role'), ('audit_outage', 503, None),
])
def test_entra_decisions_have_bounded_details_and_generic_errors(auth_app, monkeypatch, caplog, case, status, reason):  # noqa: F811
    app, owner, _ = auth_app
    app.config.update(ENTRA_TENANT_ID='00000000-0000-0000-0000-000000000411', ENTRA_CLIENT_ID='access-test-client')
    claims = dict(tid=app.config['ENTRA_TENANT_ID'], oid='00000000-0000-0000-0000-000000000422',
                  sub=SENTINEL, name=SENTINEL, roles=['Cafeteria.Editor'])
    if case == 'tenant':
        claims['tid'] = SENTINEL
    if case == 'audience':
        claims['aud'] = SENTINEL
    if case == 'roles_type':
        claims['roles'] = SENTINEL
    if case == 'roles_unknown':
        claims['roles'] = [SENTINEL]
    if case == 'roles_duplicate':
        claims['roles'] = ['Cafeteria.Editor', 'Cafeteria.Editor']
    if case == 'roles_empty':
        claims['roles'] = []
    provider = FakeMsalClient(claims)
    if case == 'state':
        provider.acquire_token_by_auth_code_flow = Mock(side_effect=ValueError(SENTINEL))
    if case == 'network':
        provider.acquire_token_by_auth_code_flow = Mock(side_effect=ProviderConnectionError(SENTINEL))
    if case == 'provider_error':
        provider.acquire_token_by_auth_code_flow = Mock(return_value={'error': SENTINEL, 'error_description': SENTINEL})
    if case == 'claims_type':
        provider.acquire_token_by_auth_code_flow = Mock(return_value={'id_token_claims': [SENTINEL]})
    monkeypatch.setattr(routes, '_client', lambda: provider)
    client = app.test_client()
    with client.session_transaction() as session:
        if case != 'missing_flow':
            session['auth_flow'] = {'state': 'test-state'}
    if case == 'audit_outage':
        audit_outage(owner)
    response = client.get('/auth/callback?error_description=' + SENTINEL)
    assert response.status_code == status
    recorded = events(owner)
    if case == 'audit_outage':
        assert recorded == []
    else:
        assert len(recorded) == 1 and recorded[0].details['reason'] == reason
        assert recorded[0].details['provider'] == 'entra'
        assert (recorded[0].actor_user_id is not None) == (case == 'valid')
    assert SENTINEL not in repr(recorded) and SENTINEL not in caplog.text
    assert SENTINEL not in response.get_data(as_text=True)
    with client.session_transaction() as session:
        assert ('user' in session) == (case == 'valid')


def test_get_and_csrf_rejection_never_create_authentication_outcomes(auth_app):  # noqa: F811
    app, owner, _ = auth_app
    app.config['ENTRA_ENABLED'] = False
    client = app.test_client()
    assert client.get('/auth/login').status_code == 302
    assert client.get('/auth/local').status_code == 200
    assert client.post('/auth/local', data={'username': SENTINEL, 'password': SENTINEL}).status_code == 400
    assert client.post('/auth/logout', data={}).status_code == 400
    assert events(owner) == []


@pytest.mark.parametrize('frontchannel', [False, True])
@pytest.mark.parametrize('condition', ['normal', 'audit_outage', 'stale', 'disabled'])
def test_logout_rejects_real_old_cookie_even_if_audit_fails(auth_app, frontchannel, condition):  # noqa: F811
    app, owner, issuer = auth_app
    actor = _provision(issuer, owner)
    client = app.test_client()
    assert client.post('/auth/local', data=_csrf_payload(client, username='local.editor', password='Correct-Horse-2026!Battery')).status_code == 302
    client.get('/auth/local')
    with client.session_transaction() as session:
        csrf, sid = session['_csrf_token'], session.sid
    cookie_name = app.config['SESSION_COOKIE_NAME']
    cookie = client.get_cookie(cookie_name).value
    if condition == 'audit_outage':
        audit_outage(owner)
    if condition in ('stale', 'disabled'):
        with owner.begin() as connection:
            statement = ('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:id' if condition == 'stale'
                         else 'UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id')
            connection.execute(text(statement), {'id': actor})
    response = client.get('/auth/frontchannel-logout') if frontchannel else client.post('/auth/logout', data={'_csrf': csrf})
    assert response.status_code == (200 if frontchannel else 302)
    assert not app.session_interface.client.exists(app.session_interface.key_prefix + sid)
    replay = app.test_client(use_cookies=False).get('/admin/cafeteria', headers={'Cookie': f'{cookie_name}={cookie}'})
    assert replay.status_code == 401
    recorded = events(owner)
    assert len(recorded) == (1 if condition == 'audit_outage' else 2)
    if condition != 'audit_outage':
        assert recorded[-1].action == ('auth.frontchannel.requested' if frontchannel else 'auth.logout.requested')
        assert recorded[-1].actor_user_id == (actor if condition == 'normal' else None)
    if frontchannel:
        assert client.get('/auth/frontchannel-logout').status_code == 200
    else:
        client.get('/auth/local')
        with client.session_transaction() as session:
            csrf = session['_csrf_token']
        assert client.post('/auth/logout', data={'_csrf': csrf}).status_code == 302
    assert events(owner) == recorded


def test_failed_redis_revocation_is_not_reported_as_completed_logout(auth_app, monkeypatch):  # noqa: F811
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    client = app.test_client()
    assert client.post('/auth/local', data=_csrf_payload(client, username='local.editor', password='Correct-Horse-2026!Battery')).status_code == 302
    client.get('/auth/local')
    with client.session_transaction() as session:
        csrf = session['_csrf_token']
    with monkeypatch.context() as patch:
        patch.setattr(app.session_interface.client, 'delete', Mock(side_effect=RedisError('Revocation unavailable.')))
        with pytest.raises(RedisError):
            client.post('/auth/logout', data={'_csrf': csrf})
    assert events(owner)[-1].action == 'auth.logout.requested'
