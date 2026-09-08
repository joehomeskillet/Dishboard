from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from test_access_history_reads import _seed_history
from test_admin_local_users_routes import _create, admin_account
from test_auth_routes import auth_app

__all__ = ['admin_account', 'auth_app']
PATH = '/admin/benutzer/zugriffsverlauf'


def test_empty_history_and_navigation_are_native_private_tabler(admin_account):
    app, client, owner, issuer = admin_account
    target = _create(issuer)
    with owner.begin() as connection:
        connection.execute(text("UPDATE cafeteria.users SET last_login_at=clock_timestamp()"))
    response = client.get(PATH)
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    assert b'vendor/tabler/tabler.min.css' in response.data
    assert b'Keine Zugriffsereignisse' in response.data
    assert 'Frühere Anmeldungen werden nicht ergänzt.' in response.text
    assert 'weder eine aktive Sitzung noch eine abgeschlossene Abmeldung' in response.text
    for path in ('/admin/benutzer', '/admin/benutzer/protokoll', f'/admin/benutzer/{target.public_id}'):
        assert f'href="{PATH}"' in client.get(path).text
    app.extensions['cafeteria_auth_issuer_db'] = None
    assert client.get(PATH).status_code == 200


def test_history_is_separate_filtered_escaped_and_preserves_queries(admin_account):
    _, client, owner, _ = admin_account
    _seed_history(owner, 120)
    with owner.begin() as connection:
        connection.execute(text("UPDATE cafeteria.users SET display_name='<script>DISPLAY-SENTINEL</script>' "
            "WHERE auth_provider='local'"))
    response = client.get(PATH + '?provider=local&action=all')
    assert response.status_code == 200
    assert '&lt;script&gt;DISPLAY-SENTINEL&lt;/script&gt;' in response.text
    assert '<script>DISPLAY-SENTINEL</script>' not in response.text
    assert 'page=2&amp;provider=local&amp;action=all' in response.text
    assert 'Nicht zugeordnet' in response.text
    assert 'Kontonamen entsprechen dem aktuellen Stand' in response.text
    filtered = client.get(PATH + '?provider=entra&action=auth.frontchannel.requested')
    assert 'Lokale Abmeldung angefordert' in filtered.text
    assert 'Anmeldung akzeptiert</div>' not in filtered.text
    assert 'password_hash' not in response.text and 'authz_version' not in response.text


def test_last_allowed_page_never_links_beyond_the_bound(admin_account, monkeypatch):
    from cafeteria.auth.access_history_reads import AccessHistoryPage

    _, client, _, _ = admin_account
    monkeypatch.setattr('cafeteria.admin.access_history_routes.list_access_history',
                        lambda *_args, **_kwargs: AccessHistoryPage((), True))
    response = client.get(PATH + '?page=10000')
    assert response.status_code == 200 and 'page=10001' not in response.text
    assert 'page=9999' in response.text


@pytest.mark.parametrize('query', [
    'page=0', 'page=10001', 'page=true', 'page=1&page=2', 'page=', 'page=１',
    'provider=', 'provider=LOCAL', 'provider=local&provider=entra',
    'action=auth.local_login_locked', 'action=', 'action=all&action=auth.login.accepted',
    'next=https://example.invalid', 'target=1', 'provider=' + 'x' * 1000,
])
def test_invalid_queries_return_private_400(admin_account, query):
    _, client, _, _ = admin_account
    response = client.get(PATH + '?' + query)
    assert response.status_code == 400 and response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_route_denies_non_admin_and_anonymous_with_no_store(admin_account, role):
    app, client, owner, _ = admin_account
    with client.session_transaction() as state:
        actor = state['user']['id']
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.user_role_cache SET role_code=:role WHERE user_id=:id'),
                           {'role': role, 'id': actor})
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                                     {'id': actor}).scalar_one()
    stale = client.get(PATH)
    assert stale.status_code == 401 and stale.headers['Cache-Control'] == 'no-store'
    with client.session_transaction() as state:
        state['user'], state['authz_version'] = {'id': actor}, version
    denied = client.get(PATH)
    assert denied.status_code == 403 and denied.headers['Cache-Control'] == 'no-store'
    anonymous = app.test_client().get(PATH)
    assert anonymous.status_code == 401 and anonymous.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('stage', ['authorization', 'history'])
def test_outage_uses_independent_safe_page_and_does_not_drop_session(admin_account, monkeypatch, stage):
    _, client, _, _ = admin_account
    with client.session_transaction() as state:
        before = dict(state)

    def unavailable(*_args, **_kwargs):
        raise OperationalError('PRIVATE-SENTINEL', {}, None)

    monkeypatch.setattr('cafeteria.roles.load_user_authorization' if stage == 'authorization'
        else 'cafeteria.admin.access_history_routes.list_access_history', unavailable)
    monkeypatch.setattr('cafeteria.admin.display_routes.get_admin_display', unavailable)
    response = client.get(PATH)
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert b'vendor/tabler/tabler.min.css' in response.data and b'PRIVATE-SENTINEL' not in response.data
    with client.session_transaction() as state:
        assert dict(state) == before
