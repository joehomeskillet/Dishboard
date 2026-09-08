"""Invalid OAuth callbacks preserve existing Redis sessions without granting access."""
from unittest.mock import Mock

import pytest

from cafeteria.auth import routes
from test_access_event_routes import SENTINEL, audit_outage, events
from test_auth_routes import FakeMsalClient, _csrf_payload, _provision, auth_app  # noqa: F401


@pytest.mark.parametrize('flow', ['missing', 'state'])
@pytest.mark.parametrize('outage', [False, True])
@pytest.mark.parametrize('authenticated', [False, True])
def test_invalid_callback_keeps_only_existing_authorized_session(
    auth_app, monkeypatch, caplog, flow, outage, authenticated,  # noqa: F811
):
    app, owner, issuer = auth_app
    client = app.test_client()
    if authenticated:
        actor = _provision(issuer, owner)
        assert client.post('/auth/local', data=_csrf_payload(
            client, username='local.editor', password='Correct-Horse-2026!Battery',
        )).status_code == 302
    else:
        actor = None
    provider = Mock()
    provider.acquire_token_by_auth_code_flow.side_effect = ValueError(SENTINEL)
    monkeypatch.setattr(routes, '_client', lambda: provider)
    with client.session_transaction() as current:
        if flow == 'state':
            current['auth_flow'] = {'state': 'test-state'}
        before = {key: value for key, value in current.items() if key != 'auth_flow'}
        sid = current.sid
    cookie_name = app.config['SESSION_COOKIE_NAME']
    original_cookie = client.get_cookie(cookie_name)
    before_events = events(owner)
    if outage:
        audit_outage(owner)

    response = client.get('/auth/callback', query_string={
        'state': SENTINEL, 'code': SENTINEL, 'error_description': SENTINEL,
        'clear_session': 'false',
    }, headers={'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Dest': 'document'})
    assert response.status_code == (503 if outage else 400)
    if flow == 'missing':
        provider.acquire_token_by_auth_code_flow.assert_not_called()
    else:
        provider.acquire_token_by_auth_code_flow.assert_called_once()
    assert SENTINEL not in response.get_data(as_text=True) and SENTINEL not in caplog.text
    with client.session_transaction() as current:
        assert 'auth_flow' not in current
        assert ('user' in current) == authenticated
        if authenticated:
            assert dict(current) == before
            assert current.sid == sid and current['user']['id'] == actor
        else:
            assert 'authz_version' not in current
    current_cookie = client.get_cookie(cookie_name)
    redis_key = app.session_interface.key_prefix + sid
    if authenticated:
        assert original_cookie is not None and current_cookie is not None
        assert current_cookie.value == original_cookie.value
        assert app.session_interface.client.exists(redis_key)
        replay = app.test_client(use_cookies=False).get('/admin/cafeteria', headers={
            'Cookie': f'{cookie_name}={original_cookie.value}',
        })
        assert replay.status_code == 200
    else:
        assert current_cookie is None
        assert not app.session_interface.client.exists(redis_key)
        assert client.get('/admin/cafeteria').status_code == 401

    recorded = events(owner)
    assert recorded[:len(before_events)] == before_events
    if outage:
        assert recorded == before_events
        assert 'Authentication decision audit unavailable.' in caplog.text
    else:
        assert len(recorded) == len(before_events) + 1
        rejected = recorded[-1]
        assert rejected.action == 'auth.login.rejected' and rejected.actor_user_id is None
        assert rejected.details == {'provider': 'entra', 'reason': 'flow', 'authz_version': None}
    assert SENTINEL not in repr(recorded)


@pytest.mark.parametrize('case,status', [('local_wrong', 401), ('role', 403), ('accepted_outage', 503)])
def test_other_login_failures_still_revoke_existing_session(auth_app, monkeypatch, case, status):  # noqa: F811
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    client = app.test_client()
    assert client.post('/auth/local', data=_csrf_payload(
        client, username='local.editor', password='Correct-Horse-2026!Battery',
    )).status_code == 302
    with client.session_transaction() as current:
        sid = current.sid
    cookie_name = app.config['SESSION_COOKIE_NAME']
    original_cookie = client.get_cookie(cookie_name)
    assert original_cookie is not None
    if case == 'role':
        app.config.update(ENTRA_TENANT_ID='00000000-0000-0000-0000-000000000411')
        provider = FakeMsalClient({
            'tid': app.config['ENTRA_TENANT_ID'],
            'oid': '00000000-0000-0000-0000-000000000422',
            'roles': [SENTINEL],
        })
        monkeypatch.setattr(routes, '_client', lambda: provider)
        with client.session_transaction() as current:
            current['auth_flow'] = {'state': 'test-state'}
        response = client.get('/auth/callback?clear_session=false')
    else:
        data = _csrf_payload(client, username='local.editor',
                             password=SENTINEL if case == 'local_wrong' else 'Correct-Horse-2026!Battery')
        data['clear_session'] = 'false'
        if case == 'accepted_outage':
            audit_outage(owner)
        response = client.post('/auth/local', data=data)
    assert response.status_code == status
    if case == 'role':
        assert not app.session_interface.client.exists(app.session_interface.key_prefix + sid)
    replay = app.test_client(use_cookies=False).get('/admin/cafeteria', headers={
        'Cookie': f'{cookie_name}={original_cookie.value}',
    })
    assert replay.status_code == 401
    with client.session_transaction() as current:
        assert 'user' not in current
        assert 'authz_version' not in current
