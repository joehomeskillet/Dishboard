"""BF-19/T11/T31: real sessions, rights, failed writes and safe recovery."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by parameter name.
import json
import threading
from urllib.parse import urlsplit
from wsgiref.simple_server import make_server

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from local_user_test_support import provision_local_fixture
from test_auth_routes import ACTOR_IDENTIFIER, _csrf_payload, auth_app  # noqa: F401
from test_recipe_routes import create, fields
from test_recipe_store_db import snapshot
from test_rendered_ui import browser  # noqa: F401


@pytest.fixture
def recovery_server(auth_app):  # noqa: F811
    app, owner, issuer = auth_app
    app.config.update(ENTRA_ENABLED=False)
    actor = provision_local_fixture(
        issuer, owner, actor_identifier=ACTOR_IDENTIFIER, username='bf.recovery',
        display_name='Recovery Test', password='Correct-Horse-2026!Battery',
        roles=['Cafeteria.Admin'],
    )
    client = app.test_client()
    assert client.post('/auth/local', data=_csrf_payload(
        client, username='bf.recovery', password='Correct-Horse-2026!Battery',
    )).status_code == 303
    server = make_server('127.0.0.1', 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', app, owner, client, actor
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _context(browser, origin, client, javascript, width=390):
    context = browser.new_context(
        base_url=origin, java_script_enabled=javascript,
        viewport={'width': width, 'height': 900 if width == 1440 else 844},
        reduced_motion='reduce',
    )
    cookie_name = client.application.config['SESSION_COOKIE_NAME']
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    context.add_cookies([{'name': cookie_name, 'value': cookie.value, 'url': origin}])
    return context


def _business_snapshot(owner):
    result = snapshot(owner)
    tables = ('menu_weeks', 'menu_services', 'menu_items', 'menu_item_prices',
              'menu_item_components', 'menu_item_labels', 'menu_item_allergens',
              'publication_revisions')
    with owner.connect() as connection:
        for table in tables:
            result[table] = connection.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
            )).all()
    return result


def _safe_error(page, response, status):
    assert response.status == status
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert "default-src 'self'" in response.headers['content-security-policy']
    expect(page.get_by_role('heading', level=1)).to_have_text({
        401: 'Anmeldung erforderlich', 403: 'Kein Zugriff',
        404: 'Nicht mehr verfügbar',
    }[status])
    # EH-22: a newly navigated error page does not announce the whole page as a live alert.
    if status == 404:
        expect(page.get_by_role('alert')).to_be_visible()
        expect(page.get_by_role('alert')).to_be_focused()
    assert page.locator('form, input, textarea, [data-account-row]').count() == 0
    assert 'Keine Einträge' not in page.locator('main').inner_text()
    for link in page.locator('main a').all():
        target = urlsplit(link.get_attribute('href'))
        assert not target.scheme and not target.netloc and not target.query and not target.fragment
        assert target.path in ('/auth/login', '/cafeteria/heute/')
    page.keyboard.press('Tab')
    expect(page.locator('main a').first).to_be_focused()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def _assert_only_login_added(owner, before, actor):
    after = _business_snapshot(owner)
    added = set(after['audit_events']) - set(before['audit_events'])
    assert len(added) == 1
    event = json.loads(next(iter(added))[0])
    assert event['action'] == 'auth.login.accepted'
    assert event['entity_type'] == 'authentication'
    assert event['actor_user_id'] == actor
    assert event['entity_public_id'] is None and event['profile_code'] is None
    after['audit_events'] = [row for row in after['audit_events'] if row not in added]
    assert after == before


@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('width', [390, 1440])
def test_expired_session_before_save_never_replays(
    recovery_server, browser, javascript, family, width, tmp_path,
):
    origin, _app, owner, client, actor = recovery_server
    with _context(browser, origin, client, javascript, width) as context:
        page = context.new_page()
        path = f'/admin/{family}?week=2026-08-31'
        assert page.goto(path).status == 200
        page.locator('details.admin-week-settings > summary').click()
        page.locator('input[name="title"]').fill('BF private unsaved title')
        form = page.locator('form').filter(has=page.locator('input[name="title"]'))
        token = form.locator('input[name="_csrf"]').input_value()
        before = _business_snapshot(owner)
        context.clear_cookies()
        with page.expect_response(lambda response: response.request.method == 'POST') as denied:
            form.locator('button[type="submit"]').click()
        page.wait_for_load_state()
        _safe_error(page, denied.value, 401)
        assert 'BF private unsaved title' not in page.content()
        assert token not in page.content()
        assert _business_snapshot(owner) == before
        page.screenshot(path=str(tmp_path / f'expired-{family}-{width}-js{javascript}.png'))
        posts = []
        page.on('request', lambda request: posts.append(request.url)
                if request.method == 'POST' else None)
        page.get_by_role('link', name='Anmelden', exact=True).click()
        expect(page).to_have_url(origin + '/auth/local')
        page.get_by_label('Benutzername', exact=True).fill('bf.recovery')
        page.get_by_label('Passwort', exact=True).fill('Correct-Horse-2026!Battery')
        page.get_by_role('button', name='Anmelden', exact=True).click()
        expect(page).to_have_url(origin + '/admin/cafeteria')
        page.reload()
        assert posts == [origin + '/auth/local']
        _assert_only_login_added(owner, before, actor)


@pytest.mark.parametrize('javascript', [False, True])
def test_revoked_rights_require_reauthentication_then_show_forbidden(
    recovery_server, browser, javascript, tmp_path,
):
    origin, _app, owner, client, actor = recovery_server
    with _context(browser, origin, client, javascript) as context:
        page = context.new_page()
        assert page.goto('/admin/benutzer').status == 200
        with owner.begin() as connection:
            connection.execute(text(
                "UPDATE cafeteria.user_role_cache SET role_code='Cafeteria.Editor' WHERE user_id=:id"
            ), {'id': actor})
        before = _business_snapshot(owner)
        response = page.reload()
        assert response.status == 200
        assert urlsplit(page.url).path == '/auth/local'
        assert 'return_token=' in page.url
        page.get_by_label('Benutzername', exact=True).fill('bf.recovery')
        page.get_by_label('Passwort', exact=True).fill('Correct-Horse-2026!Battery')
        page.get_by_role('button', name='Anmelden', exact=True).click()
        expect(page).to_have_url(origin + '/admin/cafeteria')
        _safe_error(page, page.goto('/admin/benutzer'), 403)
        page.screenshot(path=str(tmp_path / f'forbidden-js{javascript}.png'))
        page.get_by_role('link', name='Zur Übersicht', exact=True).click()
        assert urlsplit(page.url).path == '/cafeteria/heute/'
        _assert_only_login_added(owner, before, actor)


@pytest.mark.parametrize('javascript', [False, True])
def test_open_recipe_archived_is_explained_without_mutation(
    recovery_server, browser, javascript, tmp_path,
):
    origin, _app, owner, client, _actor = recovery_server
    path = create(client, 'BF available recipe')
    with _context(browser, origin, client, javascript) as context:
        page = context.new_page()
        assert page.goto(path).status == 200
        page.get_by_label('Titel', exact=True).fill('BF pending recipe title')
        assert client.post(path + '/status', data=fields(client, path + '/status')).status_code == 303
        before = _business_snapshot(owner)
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            page.locator('button[form="recipe-editor"][data-semantic="actions.save"]').click()
        page.wait_for_load_state()
        assert rejected.value.status == 409
        expect(page.get_by_role('alert')).to_contain_text('Zwischenzeitlich geändert')
        expect(page.get_by_label('Titel', exact=True)).to_have_value('BF pending recipe title')
        expect(page.get_by_role('link', name='Aktuellen Stand bewusst neu laden')).to_be_visible()
        page.screenshot(path=str(tmp_path / f'archived-js{javascript}.png'))
        assert _business_snapshot(owner) == before


@pytest.mark.parametrize('javascript', [False, True])
def test_open_recipe_becomes_inaccessible_after_location_change(
    recovery_server, browser, javascript, tmp_path,
):
    origin, _app, owner, client, _actor = recovery_server
    path = create(client, 'BF original location recipe')
    with _context(browser, origin, client, javascript) as context:
        page = context.new_page()
        assert page.goto(path).status == 200
        # Recipe history cannot be deleted; use a real loss of read access instead.
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            connection.execute(text(
                "INSERT INTO cafeteria.locations(code,name,active) VALUES('BF_OTHER','Anderer Standort',true)"
            ))
        before = _business_snapshot(owner)
        response = page.reload()
        assert response.status == 404
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert "default-src 'self'" in response.headers['content-security-policy']
        # EH-14 preserves deliberately rendered domain errors and their recovery context.
        expect(page.get_by_role('heading', level=1)).to_have_text('Rezepte')
        expect(page.get_by_role('alert')).to_have_text('Der Datensatz wurde nicht gefunden.')
        expect(page.get_by_role('alert')).to_be_focused()
        assert page.locator('form, input, textarea').count() == 0
        recovery = page.get_by_role('link', name='Aktuellen Stand bewusst neu laden')
        expect(recovery).to_have_attribute('href', '/admin/rezepte')
        page.keyboard.press('Tab')
        expect(recovery).to_be_focused()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert 'BF original location recipe' not in page.content()
        page.screenshot(path=str(tmp_path / f'inaccessible-js{javascript}.png'))
        assert _business_snapshot(owner) == before


def test_recovery_ignores_untrusted_destinations_and_does_not_capture_other_surfaces(recovery_server):
    _origin, app, owner, _client, _actor = recovery_server
    client = app.test_client()
    before = _business_snapshot(owner)
    for target in ('https://evil.invalid', '//evil.invalid', '/admin/cafeteria/publish'):
        response = client.post('/admin/cafeteria/header', query_string={'next': target, 'token': 'private-token'},
                               data={'title': 'private-form', '_csrf': 'private-csrf'})
        assert response.status_code == 401
        assert 'href="/auth/login"' in response.text
        assert all(value not in response.text for value in (target, 'private-token', 'private-form', 'private-csrf'))
    missing = client.get('/admin/missing-record')
    assert missing.status_code == 404 and 'RESOURCE_NOT_FOUND' in missing.text
    # An unauthenticated request must not parse rejected form bodies while rendering.
    app.config['MAX_FORM_MEMORY_SIZE'] = 100
    oversized = client.post('/admin/cafeteria/header', data={'title': 'x' * 101})
    assert oversized.status_code == 401 and 'AUTH_REQUIRED' in oversized.text
    for path in ('/missing-public', '/api/v1/missing-record'):
        response = client.get(path)
        assert response.status_code == 404 and 'Erneut anmelden' not in response.text
    assert _business_snapshot(owner) == before
