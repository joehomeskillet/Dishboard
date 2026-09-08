from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict

from cafeteria.auth import local_users as users
from cafeteria.admin.local_user_routes import _time
from cafeteria.template_filters import datetime_short
from test_auth_routes import ACTOR_IDENTIFIER, auth_app

__all__ = ['auth_app']


@pytest.mark.parametrize('instant,expected', [
    ('2026-09-08T12:34:56.123456+00:00', '08.09.2026 14:34'),
    ('2026-01-08T12:34:56+00:00', '08.01.2026 13:34'),
    ('2026-09-08T14:34:56+02:00', '08.09.2026 14:34'),
    ('2026-09-08T23:30:00Z', '09.09.2026 01:30'),
    ('2026-03-29T00:59:00+00:00', '29.03.2026 01:59'),
    ('2026-03-29T01:00:00+00:00', '29.03.2026 03:00'),
    ('2026-10-25T00:30:00+00:00', '25.10.2026 02:30'),
    ('2026-10-25T01:30:00+00:00', '25.10.2026 02:30'),
])
def test_shared_swiss_time_preserves_account_datetime_output(instant, expected):
    assert _time is datetime_short
    assert _time(datetime.fromisoformat(instant)) == expected
    assert datetime_short(instant) == expected


@pytest.mark.parametrize('value', [None, '', 'unbekannt', '2026-02-30T12:00:00Z', '2026-09-08T12:00:00'])
def test_shared_swiss_time_does_not_guess_missing_or_unknown_strings(value):
    assert datetime_short(value) == 'Noch nicht erfasst'


@pytest.fixture
def admin_account(auth_app) -> Iterator[tuple]:
    app, owner, issuer = auth_app
    with owner.connect() as connection:
        actor = connection.execute(text('SELECT id,authz_version,display_name FROM cafeteria.users '
            'WHERE preferred_username=:name'), {'name': ACTOR_IDENTIFIER}).one()
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': actor.id, 'name': actor.display_name}
        session['authz_version'] = actor.authz_version
        session['_csrf_token'] = 'isolated-account-csrf'
    yield app, client, owner, issuer


def _create(issuer, username='managed.editor', roles=('Cafeteria.Editor',)):
    actor = users.load_local_command_context(issuer, actor_identifier=ACTOR_IDENTIFIER).actor
    return users.create_local_user(issuer, actor=actor, username=username, display_name='Lokales Testkonto',
                                  password='Valide!Wolken77Kette', roles=roles)


def _form(**values):
    return {'_csrf': 'isolated-account-csrf', 'return_page': '1', 'return_status': 'all', **values}


def test_local_account_pages_are_real_tabler_and_private(admin_account):
    _, client, _, issuer = admin_account
    account = _create(issuer)
    for path in ('/admin/benutzer', '/admin/benutzer/neu', '/admin/benutzer/protokoll',
                 f'/admin/benutzer/{account.public_id}'):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        assert b'vendor/tabler/tabler.min.css' in response.data
        assert b'Benutzer &amp; Zugriff' in response.data
        assert b'password_hash' not in response.data


def test_create_posts_only_requested_identity_and_redirects(admin_account):
    _, client, owner, _ = admin_account
    response = client.post('/admin/benutzer', data=_form(username='web.created', display_name='Webkonto',
        password='Valide!Wolken77Kette', password_confirm='Valide!Wolken77Kette', roles='Cafeteria.Editor'))
    assert response.status_code == 303
    assert response.headers['Location'].startswith('/admin/benutzer/')
    with owner.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.local_credentials WHERE username='web.created'")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action='auth.local_user_provisioned'")).scalar_one() == 1


def _state(owner, target):
    with owner.connect() as connection:
        return connection.execute(text('SELECT u.id,u.authz_version,u.disabled_at,c.password_hash '
            'FROM cafeteria.users u JOIN cafeteria.local_credentials c ON c.user_id=u.id '
            'WHERE u.public_id=:id'), {'id': target}).one()


def test_all_actions_keep_versions_and_return_filters(admin_account):
    _, client, owner, issuer = admin_account
    target = _create(issuer)
    before = _state(owner, target.public_id)
    for action, values in [('rollen', {'roles': 'Cafeteria.Publisher'}),
                           ('passwort', {'password': 'Frische!Sterne92Tanne', 'password_confirm': 'Frische!Sterne92Tanne'}),
                           ('deaktivieren', {}), ('aktivieren', {})]:
        response = client.post(f'/admin/benutzer/{target.public_id}/{action}', data=_form(
            target_version=str(before.authz_version), confirm='yes', return_page='2', return_status='disabled', **values))
        assert response.status_code == 303
        assert 'page=2' in response.headers['Location'] and 'status=disabled' in response.headers['Location']
        after = _state(owner, target.public_id)
        assert after.authz_version > before.authz_version
        assert (after.password_hash != before.password_hash) == (action == 'passwort')
        assert (after.disabled_at is not None) == (action == 'deaktivieren')
        before = after
    events = client.get(f'/admin/benutzer/protokoll?target={target.public_id}')
    assert b'Lokales Passwort' in events.data and b'Lokales Konto reaktiviert.' in events.data
    assert before.password_hash.encode() not in events.data


@pytest.mark.parametrize('field,value', [
    ('_csrf', 'wrong'), ('username', 'web.invalid'), ('password', 'second-copy'),
    ('return_page', '2'), ('actor_id', '1'), ('authz_version', '1'),
])
def test_unknown_and_repeated_scalar_fields_cannot_create(admin_account, field, value):
    _, client, owner, _ = admin_account
    form = MultiDict(_form(username='web.invalid', display_name='Test', password='Valide!Wolken77Kette',
                           password_confirm='Valide!Wolken77Kette', roles='Cafeteria.Editor'))
    form.add(field, value)
    response = client.post('/admin/benutzer', data=form)
    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.local_credentials')).scalar_one() == 0


@pytest.mark.parametrize('values', [
    {'username': 'UPPER'}, {'display_name': ' '}, {'roles': ['Cafeteria.Admin', 'Cafeteria.Admin']},
    {'roles': 'Cafeteria.Unknown'}, {'roles': []}, {'password_confirm': 'mismatch'},
])
def test_create_errors_preserve_identity_but_never_passwords(admin_account, values):
    _, client, _, _ = admin_account
    form = _form(username='web.invalid', display_name='Testkonto', password='Valide!Wolken77Kette',
                 password_confirm='Valide!Wolken77Kette', roles='Cafeteria.Publisher')
    form.update(values)
    response = client.post('/admin/benutzer', data=form)
    assert response.status_code == 400
    assert b'Valide!Wolken77Kette' not in response.data
    assert b'autocomplete="new-password"' in response.data
    assert b'role="alert"' in response.data
    assert b'value="Testkonto"' in response.data or values.get('display_name') == ' '


def test_stale_target_conflict_displays_current_version_without_retry(admin_account):
    _, client, owner, issuer = admin_account
    target = _create(issuer)
    assert client.get(f'/admin/benutzer/{target.public_id}').status_code == 200
    context = users.load_local_command_context(issuer, actor_identifier=ACTOR_IDENTIFIER,
                                               target_username='managed.editor')
    newer = users.reset_local_password(issuer, actor=context.actor, target=context.target,
                                      password='Frische!Sterne92Tanne')
    response = client.post(f'/admin/benutzer/{target.public_id}/rollen', data=_form(
        target_version=str(target.authz_version), confirm='yes', roles='Cafeteria.Admin'))
    assert response.status_code == 409
    assert b'zwischenzeitlich' in response.data
    assert f'name="target_version" value="{newer.authz_version}"'.encode() in response.data
    assert _state(owner, target.public_id).authz_version == newer.authz_version


def test_original_actor_version_is_not_refreshed_after_target_read(admin_account, monkeypatch):
    from cafeteria.admin import local_user_routes as routes
    _, client, owner, issuer = admin_account
    target = _create(issuer)
    original = routes._account

    def revoke_after_read(public_id):
        result = original(public_id)
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 '
                'WHERE preferred_username=:name'), {'name': ACTOR_IDENTIFIER})
        return result

    monkeypatch.setattr(routes, '_account', revoke_after_read)
    response = client.post(f'/admin/benutzer/{target.public_id}/deaktivieren', data=_form(
        target_version=str(target.authz_version), confirm='yes'))
    assert response.status_code == 401
    assert _state(owner, target.public_id).disabled_at is None
    with client.session_transaction() as session:
        assert 'user' not in session


def test_last_local_admin_and_self_change_have_explicit_results(admin_account):
    app, client, owner, issuer = admin_account
    first = _create(issuer, 'first.admin', ('Cafeteria.Admin',))
    denied = client.post(f'/admin/benutzer/{first.public_id}/deaktivieren', data=_form(
        target_version=str(first.authz_version), confirm='yes'))
    assert denied.status_code == 409 and b'weiterer ungesperrter lokaler Admin' in denied.data
    _create(issuer, 'second.admin', ('Cafeteria.Admin',))
    own = app.test_client()
    state = _state(owner, first.public_id)
    with own.session_transaction() as session:
        session['user'] = {'id': state.id, 'name': 'Lokaler Admin'}
        session['authz_version'], session['_csrf_token'] = state.authz_version, 'isolated-account-csrf'
    response = own.post(f'/admin/benutzer/{first.public_id}/rollen', data=_form(
        target_version=str(state.authz_version), confirm='yes', roles='Cafeteria.Editor'))
    assert response.status_code == 303 and response.headers['Location'] == '/auth/local'
    with own.session_transaction() as session:
        assert 'user' not in session
    assert own.get('/admin/benutzer').status_code == 401


def test_publisher_and_unknown_provider_do_not_gain_account_access(admin_account):
    app, client, owner, issuer = admin_account
    target = _create(issuer)
    with owner.connect() as connection:
        foreign = connection.execute(text("SELECT public_id FROM cafeteria.users WHERE auth_provider='entra'")).scalar_one()
    for public_id in (foreign, uuid4()):
        assert client.get(f'/admin/benutzer/{public_id}').status_code == 404
        assert client.post(f'/admin/benutzer/{public_id}/deaktivieren', data=_form(
            target_version='1', confirm='yes')).status_code == 404
    with owner.begin() as connection:
        connection.execute(text("UPDATE cafeteria.user_role_cache SET role_code='Cafeteria.Publisher' "
            "WHERE user_id=(SELECT id FROM cafeteria.users WHERE preferred_username=:name)"), {'name': ACTOR_IDENTIFIER})
        actor = connection.execute(text('SELECT id,authz_version FROM cafeteria.users WHERE preferred_username=:name'),
                                   {'name': ACTOR_IDENTIFIER}).one()
    with client.session_transaction() as session:
        session['authz_version'] = actor.authz_version
    for path in ('/admin/benutzer', '/admin/benutzer/neu', '/admin/benutzer/protokoll', f'/admin/benutzer/{target.public_id}'):
        assert client.get(path).status_code == 403
        assert app.test_client().get(path).status_code == 401
    overview = client.get('/admin/cafeteria')
    assert overview.status_code == 200 and b'Benutzer &amp; Zugriff' not in overview.data


def test_missing_issuer_leaves_reads_and_blocks_mutation(admin_account):
    app, client, owner, _ = admin_account
    app.extensions['cafeteria_auth_issuer_db'] = None
    assert client.get('/admin/benutzer').status_code == 200
    response = client.post('/admin/benutzer', data=_form(username='web.created', display_name='Webkonto',
        password='Valide!Wolken77Kette', password_confirm='Valide!Wolken77Kette', roles='Cafeteria.Editor'))
    assert response.status_code == 503 and b'Valide!Wolken77Kette' not in response.data
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.local_credentials')).scalar_one() == 0


@pytest.mark.parametrize('failure_at', ['authorization', 'reader'])
def test_db_failure_before_or_inside_route_has_safe_independent_page(admin_account, monkeypatch, failure_at):
    app, client, _, _ = admin_account

    def unavailable(*_args, **_kwargs):
        raise OperationalError('DO-NOT-EXPOSE', {'password': 'DO-NOT-EXPOSE'}, None)

    monkeypatch.setattr('cafeteria.roles.load_user_authorization' if failure_at == 'authorization'
                        else 'cafeteria.auth.local_users.list_local_users', unavailable)
    # Rendering the normal admin frame would invoke this failed database consumer.
    monkeypatch.setattr('cafeteria.admin.display_routes.get_admin_display', unavailable)
    response = client.get('/admin/benutzer')
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert b'DO-NOT-EXPOSE' not in response.data and b'Benutzerverwaltung nicht verf' in response.data
    assert b'vendor/tabler/tabler.min.css' in response.data


@pytest.mark.parametrize('query', ['page=0', 'page=10001', 'page=1&page=2', 'status=unknown', 'next=https://example.invalid'])
def test_query_bounds_and_return_urls_are_closed(admin_account, query):
    _, client, _, _ = admin_account
    assert client.get('/admin/benutzer?' + query).status_code == 400


@pytest.mark.parametrize('action', ['passwort', 'deaktivieren'])
def test_password_and_status_self_actions_clear_session(admin_account, action):
    app, _, owner, issuer = admin_account
    own = _create(issuer, 'self.admin', ('Cafeteria.Admin',))
    _create(issuer, 'remaining.admin', ('Cafeteria.Admin',))
    state = _state(owner, own.public_id)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': state.id, 'name': 'Lokaler Admin'}
        session['authz_version'], session['_csrf_token'] = state.authz_version, 'isolated-account-csrf'
    values = {'password': 'Frische!Sterne92Tanne', 'password_confirm': 'Frische!Sterne92Tanne'} if action == 'passwort' else {}
    response = client.post(f'/admin/benutzer/{own.public_id}/{action}', data=_form(
        target_version=str(state.authz_version), confirm='yes', **values))
    assert response.status_code == 303 and response.headers['Location'] == '/auth/local'
    with client.session_transaction() as session:
        assert 'user' not in session
    assert _state(owner, own.public_id).authz_version > state.authz_version


@pytest.mark.parametrize('changed_field', ['_csrf', 'target_version', 'confirm', 'actor_id'])
def test_mutation_form_boundaries_preserve_target(admin_account, changed_field):
    _, client, owner, issuer = admin_account
    target = _create(issuer)
    before = _state(owner, target.public_id)
    values = MultiDict(_form(target_version=str(before.authz_version), confirm='yes'))
    if changed_field in ('target_version', 'actor_id'):
        values.add(changed_field, '1')
    else:
        values[changed_field] = 'invalid'
    response = client.post(f'/admin/benutzer/{target.public_id}/deaktivieren', data=values)
    assert response.status_code == 400
    assert _state(owner, target.public_id) == before
