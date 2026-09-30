"""EH navigation targets are checked, flow bound and never contain form data."""
# ruff: noqa: F811 -- shared fixture imported for pytest injection.
from urllib.parse import parse_qs, urlsplit

import secrets

import pytest
from sqlalchemy import text
from requests.exceptions import ConnectionError
from werkzeug.exceptions import ServiceUnavailable

from cafeteria.auth import routes as auth_routes

from test_auth_routes import auth_app, _csrf_payload, _provision  # noqa: F401


def _token(response):
    return parse_qs(urlsplit(response.location).query)['return_token'][0]


def test_eh_t02_t05_t06_local_tabs_keep_separate_checked_targets(auth_app):
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    app.config['ENTRA_ENABLED'] = False
    client = app.test_client()
    targets = ['/admin/patienten?week=2026-09-28', '/admin/cafeteria?week=2026-10-05']
    tokens = [_token(client.get(target)) for target in targets]
    assert tokens[0] != tokens[1]
    for token, target in zip(tokens, targets):
        payload = _csrf_payload(client, username='local.editor', password='Correct-Horse-2026!Battery')
        old_csrf = payload['csrf_token']
        with client.session_transaction() as sess:
            sess['private_old_value'] = 'must disappear'
        response = client.post('/auth/local', data=payload | {'return_token': token})
        assert response.status_code == 303 and response.location == target
        with client.session_transaction() as sess:
            assert 'private_old_value' not in sess
            assert sess.get('_csrf_token') != old_csrf


def test_eh_t03_t04_target_allowlist_rejects_ambiguous_or_sensitive_urls(auth_app):
    from cafeteria.errors import safe_return_target
    app, _, _ = auth_app
    rejected = [
        'https://evil.invalid', '//evil.invalid', '/\\evil.invalid', '/%2f%2fevil.invalid',
        '/%252f%252fevil.invalid', '/admin/patienten%0d%0aLocation:evil',
        '/auth/logout', '/auth/callback', '/admin/patienten/publish', '/missing',
        '/admin/patienten?week=2026-09-28&week=2026-10-05',
        '/admin/patienten?password=secret', '/admin/patienten?q=patient-name',
        '/admin/patienten?week=2026-09-29', '/admin/patienten#private',
    ]
    with app.test_request_context():
        for target in rejected:
            assert safe_return_target(target) is None, target
        assert safe_return_target('/admin/patienten?week=2026-09-28') == '/admin/patienten?week=2026-09-28'


def test_eh_t03_return_token_is_browser_bound_and_single_use(auth_app):
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    first, second = app.test_client(), app.test_client()
    token = _token(first.get('/admin/patienten?week=2026-09-28'))
    for client, expected in ((second, '/admin/cafeteria'), (first, '/admin/patienten?week=2026-09-28'),
                             (first, '/admin/cafeteria')):
        response = client.post('/auth/local', data=_csrf_payload(
            client, username='local.editor', password='Correct-Horse-2026!Battery') | {'return_token': token})
        assert response.status_code == 303 and response.location == expected


def test_eh_t05_t10_entra_flows_keep_msal_state_and_reject_callback_replay(auth_app, monkeypatch):
    app, _, _ = auth_app
    tenant = '00000000-0000-0000-0000-000000000411'
    app.config.update(ENTRA_TENANT_ID=tenant, ENTRA_CLIENT_ID='eh-client', ENTRA_CLIENT_SECRET='test-only')
    class Provider:
        def initiate_auth_code_flow(self, *, scopes, redirect_uri):
            state = secrets.token_hex(16)
            return {'state': state, 'auth_uri': 'https://login.microsoftonline.com/test?state=' + state}

        def acquire_token_by_auth_code_flow(self, flow, query):
            assert flow['state'] == query['state']
            return {'id_token_claims': {'tid': tenant, 'oid': '00000000-0000-0000-0000-000000000422',
                'sub': 'eh-entra', 'name': 'EH Entra', 'aud': 'eh-client', 'roles': ['Cafeteria.Editor']}}
    monkeypatch.setattr(auth_routes, '_client', Provider)
    client = app.test_client()
    targets = ['/admin/patienten?week=2026-09-28', '/admin/cafeteria?week=2026-10-05']
    states = []
    for target in targets:
        token = _token(client.get(target))
        response = client.get('/auth/login', query_string={'method': 'entra', 'return_token': token})
        assert response.status_code == 302
        states.append(parse_qs(urlsplit(response.location).query)['state'][0])
    assert states[0] != states[1]
    invalid = client.get('/auth/callback?state=wrong&code=secret-provider-code')
    assert invalid.status_code == 400 and 'Location' not in invalid.headers
    assert 'secret-provider-code' not in invalid.text
    for state, target in zip(states, targets):
        response = client.get('/auth/callback', query_string={'state': state, 'code': 'test-code'})
        assert response.status_code == 303 and response.location == target
        replay = client.get('/auth/callback', query_string={'state': state, 'code': 'test-code'})
        assert replay.status_code == 400 and 'Location' not in replay.headers


def test_eh_t07_t08_failed_local_login_is_generic_and_does_not_echo_password(auth_app):
    app, owner, issuer = auth_app
    user_id = _provision(issuer, owner)
    client = app.test_client()
    for username in ('missing', 'local.editor'):
        response = client.post('/auth/local', data=_csrf_payload(
            client, username=username, password='PRIVATE-UNSAVED-PASSWORD'))
        assert response.status_code == 401 and 'Location' not in response.headers
        assert 'Anmeldung fehlgeschlagen.' in response.text
        assert 'PRIVATE-UNSAVED-PASSWORD' not in response.text
    with owner.begin() as conn:
        conn.execute(text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'), {'id': user_id})
    response = client.post('/auth/local', data=_csrf_payload(
        client, username='local.editor', password='Correct-Horse-2026!Battery'))
    assert response.status_code == 401 and 'Anmeldung fehlgeschlagen.' in response.text
    assert 'gesperrt' not in response.text and 'deaktiviert' not in response.text


def test_eh_t09_t11_provider_and_configuration_outage_never_exposes_details(auth_app, monkeypatch):
    app, _, _ = auth_app
    app.config.update(LOCAL_AUTH_ENABLED=False, ENTRA_ENABLED=True,
                      ENTRA_CLIENT_ID='', ENTRA_CLIENT_SECRET='', ENTRA_TENANT_ID='')
    response = app.test_client().get('/auth/login')
    assert response.status_code == 503
    assert 'Anmeldung' in response.text and 'verfügbar' in response.text
    assert 'Konfiguration' not in response.text and 'Secret' not in response.text
    app.config.update(ENTRA_CLIENT_ID='eh-client', ENTRA_CLIENT_SECRET='test-only', ENTRA_TENANT_ID='eh-tenant')
    def unavailable():
        raise ConnectionError('PRIVATE-PROVIDER-ERROR')
    monkeypatch.setattr(auth_routes, '_client', unavailable)
    response = app.test_client().get('/auth/login')
    assert response.status_code == 503 and 'PRIVATE-PROVIDER-ERROR' not in response.text


def test_eh_t14_revoked_authorization_precedes_csrf_and_prevents_business_write(auth_app):
    app, owner, issuer = auth_app
    user_id = _provision(issuer, owner)
    client = app.test_client()
    client.post('/auth/local', data=_csrf_payload(
        client, username='local.editor', password='Correct-Horse-2026!Battery'))
    with owner.begin() as conn:
        conn.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': user_id})
        before = conn.execute(text('SELECT to_jsonb(w)::text FROM cafeteria.menu_weeks w ORDER BY id')).all()
    response = client.post('/admin/patienten/header', data={'_csrf': 'bad', 'title': 'DO NOT WRITE'})
    assert response.status_code == 401 and 'AUTH_SESSION_INVALID' in response.text
    assert 'Location' not in response.headers and 'DO NOT WRITE' not in response.text
    with owner.connect() as conn:
        assert conn.execute(text('SELECT to_jsonb(w)::text FROM cafeteria.menu_weeks w ORDER BY id')).all() == before


def test_eh_t06_t07_valid_session_login_entry_uses_checked_target_without_new_login(auth_app):
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    client = app.test_client()
    token = _token(client.get('/admin/patienten?week=2026-09-28'))
    client.post('/auth/local', data=_csrf_payload(
        client, username='local.editor', password='Correct-Horse-2026!Battery') | {'return_token': token})
    with client.session_transaction() as sess:
        before = sess['user']
    response = client.get('/auth/login')
    assert response.status_code == 303 and response.location == '/admin/cafeteria'
    with client.session_transaction() as sess:
        assert sess['user'] == before


def test_eh_t03_flow_storage_is_bounded_expiring_and_excludes_client_form_values(auth_app, monkeypatch):
    from cafeteria import errors
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    client = app.test_client()
    tokens = []
    for _ in range(12):
        response = client.get('/admin/patienten?week=2026-09-28')
        assert response.status_code == 302
        tokens.extend(parse_qs(urlsplit(response.location).query).get('return_token', []))
    assert len(tokens) == 12
    with client.session_transaction() as sess:
        owner_id = sess['_eh_navigation']
        assert all('/admin/' not in str(value) for value in sess.values())
    store = app.extensions['cafeteria_rate_redis']
    keys = set(store.scan_iter(match=f'dishboard:login-navigation:{owner_id}:*'))
    assert len(keys) == 12
    assert all(0 < store.ttl(key) <= 600 for key in keys)
    clock = errors.time()
    monkeypatch.setattr(errors, 'time', lambda: clock + 601)
    response = client.post('/auth/local', data=_csrf_payload(
        client, username='local.editor', password='Correct-Horse-2026!Battery') | {'return_token': tokens[0]})
    assert response.status_code == 303 and response.location == '/admin/cafeteria'


def test_eh_t03_flow_binding_cannot_resurrect_consumed_context(auth_app, monkeypatch):
    from flask import session
    from cafeteria import errors
    app, _, _ = auth_app
    with app.test_request_context():
        token = errors.issue_return_token('/admin/patienten')
        context = errors.login_context(token)
        store = app.extensions['cafeteria_rate_redis']
        owner_id = session['_eh_navigation']
        key = f'dishboard:login-navigation:{owner_id}:{token}'
        # Model expiry/consumption after validation but before attaching the provider flow.
        store.delete(key)
        monkeypatch.setattr(errors, 'login_context', lambda token: context)
        with pytest.raises(ServiceUnavailable):
            errors.bind_entra_flow(token, {'state': 'test-state'})
        assert store.exists(key) == 0
        assert list(store.scan_iter(match='dishboard:login-navigation:state:*')) == []


def test_nine_navigation_flows_keep_login_and_separate_tabs(auth_app, monkeypatch):
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    app.config.update(ENTRA_ENABLED=True, ENTRA_CLIENT_ID='eh-client', ENTRA_CLIENT_SECRET='test-only',
                      ENTRA_TENANT_ID='00000000-0000-0000-0000-000000000411')

    class Provider:
        def initiate_auth_code_flow(self, *, scopes, redirect_uri):
            return {'state': 'flow-nine', 'auth_uri': 'https://login.microsoftonline.com/test?state=flow-nine'}

    monkeypatch.setattr(auth_routes, '_client', Provider)
    first = app.test_client()
    tokens = [_token(first.get('/admin/patienten?week=2026-09-28')) for _ in range(9)]
    assert len(set(tokens)) == 9
    started = first.get('/auth/login', query_string={'method': 'entra', 'return_token': tokens[-1]})
    assert started.status_code == 302
    assert started.location.startswith('https://login.microsoftonline.com/')
    second = app.test_client()
    other = _token(second.get('/admin/cafeteria?week=2026-10-05'))
    pairs = (
        (first, tokens[0], '/admin/patienten?week=2026-09-28'),
        (second, other, '/admin/cafeteria?week=2026-10-05'),
    )
    for client, token, target in pairs:
        response = client.post('/auth/local', data=_csrf_payload(
            client, username='local.editor', password='Correct-Horse-2026!Battery') | {'return_token': token})
        assert response.status_code == 303 and response.location == target


def test_return_store_rejection_does_not_block_entra_login(auth_app, monkeypatch):
    app, _, _ = auth_app
    app.config.update(LOCAL_AUTH_ENABLED=False, ENTRA_ENABLED=True, ENTRA_CLIENT_ID='eh-client',
                      ENTRA_CLIENT_SECRET='test-only', ENTRA_TENANT_ID='00000000-0000-0000-0000-000000000411')

    class Provider:
        def initiate_auth_code_flow(self, *, scopes, redirect_uri):
            return {'state': 'capacity-state', 'auth_uri': 'https://login.microsoftonline.com/test?state=capacity-state'}

    def reject_bind(token, flow):
        raise ServiceUnavailable()

    monkeypatch.setattr(auth_routes, '_client', Provider)
    monkeypatch.setattr(auth_routes, 'login_context', lambda *_args, **_kwargs: {
        'target': '/admin/cafeteria', 'notice': 'auth.required', 'expires': 10**12})
    monkeypatch.setattr(auth_routes, 'bind_entra_flow', reject_bind)
    response = app.test_client().get('/auth/login')
    assert response.status_code == 302
    assert response.location.startswith('https://login.microsoftonline.com/')
    assert 'SERVICE_UNAVAILABLE' not in response.get_data(as_text=True)
    assert 'momentan nicht' not in response.get_data(as_text=True)
