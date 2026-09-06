from __future__ import annotations

from threading import Thread

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from werkzeug.serving import make_server

from cafeteria.display_settings import set_admin_density
from test_admin_local_users_routes import _create, admin_account
from test_auth_routes import auth_app
from test_rendered_ui import browser

__all__ = ['admin_account', 'auth_app', 'browser']


@pytest.fixture
def live_accounts(admin_account):
    app, client, owner, issuer = admin_account
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', client, owner, issuer
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _context(browser, origin, client, width=1440):
    context = browser.new_context(viewport={'width': width, 'height': 1050})
    cookie_name = client.application.config['SESSION_COOKIE_NAME']
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    context.add_cookies([{'name': cookie_name, 'value': cookie.value, 'url': origin}])
    return context


def _layout(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('main input:not([type=hidden])').evaluate_all(
        'els=>els.every(el=>el.labels && el.labels.length>0)')
    assert page.locator('[id]').evaluate_all('els=>new Set(els.map(el=>el.id)).size===els.length')
    assert page.locator('[aria-describedby]').evaluate_all(
        'els=>els.every(el=>el.getAttribute("aria-describedby").split(/\\s+/).every(id=>document.getElementById(id)))')
    targets = page.locator('main .btn:visible,main .form-control:visible,main .form-select:visible,main .form-check:visible')
    assert targets.count() > 0
    assert targets.evaluate_all('els=>els.every(el=>el.getBoundingClientRect().height>=47.5)'), targets.evaluate_all(
        'els=>els.map(el=>({tag:el.tagName,text:el.textContent,height:el.getBoundingClientRect().height}))')


def test_local_user_pages_fit_both_densities_and_all_viewports(live_accounts, browser, tmp_path):
    origin, client, owner, issuer = live_accounts
    target = _create(issuer, 'managed.' + 'a' * 56)
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.users SET display_name=:name WHERE public_id=:id'),
                           {'id': target.public_id, 'name': 'Sehr langer Anzeigename für die Küchenadministration ' * 2})
    with client.session_transaction() as state:
        actor, version = state['user']['id'], state['authz_version']
    with _context(browser, origin, client) as context:
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        for density in ('compact', 'comfortable'):
            set_admin_density(owner, actor, version, density)
            for width in (390, 820, 1440):
                page.set_viewport_size({'width': width, 'height': 1050})
                for name, path in (
                    ('list', '/admin/benutzer'), ('detail', f'/admin/benutzer/{target.public_id}'),
                    ('create', '/admin/benutzer/neu'), ('events', '/admin/benutzer/protokoll'),
                    ('empty', '/admin/benutzer?status=disabled'),
                ):
                    response = page.goto(origin + path, wait_until='networkidle')
                    assert response.status == 200 and response.headers['cache-control'] == 'no-store'
                    assert "style-src 'self'" in response.headers['content-security-policy']
                    _layout(page)
                    page.screenshot(path=str(tmp_path / f'iam-{name}-{density}-{width}.png'), full_page=True)
                page.goto(origin + '/admin/benutzer/neu', wait_until='networkidle')
                page.get_by_label('Benutzername', exact=True).fill('browser.invalid')
                page.get_by_label('Anzeigename', exact=True).fill('Fehlerzustand mit langem Namen ' * 5)
                page.get_by_label('Neues Passwort', exact=True).fill('Valide!Wolken77Kette')
                page.get_by_label('Neues Passwort bestätigen', exact=True).fill('Frische!Sterne92Tanne')
                with page.expect_navigation() as navigation:
                    page.get_by_role('button', name='Lokales Konto anlegen').click()
                assert navigation.value.status == 400
                expect(page.get_by_role('alert')).to_be_visible()
                assert page.locator('input[type=password]').evaluate_all('els=>els.every(el=>el.value==="")')
                _layout(page)
                page.screenshot(path=str(tmp_path / f'iam-error-{density}-{width}.png'), full_page=True)
                page.get_by_label('Benutzername', exact=True).focus()
                page.keyboard.press('Tab')
                expect(page.get_by_label('Anzeigename', exact=True)).to_be_focused()
                assert page.get_by_label('Anzeigename', exact=True).evaluate(
                    'el=>el.matches(":focus-visible") && (getComputedStyle(el).outlineStyle!=="none" || getComputedStyle(el).boxShadow!=="none")')
                page.screenshot(path=str(tmp_path / f'iam-focus-{density}-{width}.png'), full_page=True)
        assert all('400' in error and 'Failed to load resource' in error for error in errors), errors


def test_browser_complete_lifecycle_and_session_revocation(live_accounts, browser, tmp_path):
    origin, client, _, _ = live_accounts
    with _context(browser, origin, client, 390) as admin, browser.new_context(
        viewport={'width': 390, 'height': 1050}) as target_context:
        page, target_page = admin.new_page(), target_context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin + '/admin/benutzer/neu', wait_until='networkidle')
        page.get_by_label('Benutzername', exact=True).fill('browser.lifecycle')
        page.get_by_label('Anzeigename', exact=True).fill('Browser Lebenszyklus')
        page.get_by_label('Neues Passwort', exact=True).fill('Valide!Wolken77Kette')
        page.get_by_label('Neues Passwort bestätigen', exact=True).fill('Valide!Wolken77Kette')
        page.get_by_role('button', name='Lokales Konto anlegen').click()
        expect(page.get_by_role('heading', name='Browser Lebenszyklus')).to_be_visible()
        detail_url = page.url
        page.get_by_label('Editor · Menüs bearbeiten', exact=True).uncheck()
        page.get_by_label('Publisher · Menüs veröffentlichen', exact=True).check()
        page.get_by_label('Rollenänderung für browser.lifecycle bestätigen', exact=True).check()
        page.get_by_role('button', name='Rollen speichern').click()
        expect(page.get_by_label('Publisher · Menüs veröffentlichen', exact=True)).to_be_checked()
        page.get_by_label('Neues Passwort', exact=True).fill('Frische!Sterne92Tanne')
        page.get_by_label('Neues Passwort bestätigen', exact=True).fill('Frische!Sterne92Tanne')
        page.get_by_label('Neues Passwort für browser.lifecycle setzen und bestehende Anmeldungen widerrufen', exact=True).check()
        page.get_by_role('button', name='Passwort zurücksetzen', exact=True).click()
        expect(page.locator('input[type=password]').first).to_have_value('')

        def login_target():
            target_page.goto(origin + '/auth/local', wait_until='networkidle')
            target_page.locator('input[name=username]').fill('browser.lifecycle')
            target_page.locator('input[name=password]').fill('Frische!Sterne92Tanne')
            target_page.get_by_role('button', name='Anmelden', exact=True).click()
            expect(target_page).to_have_url(origin + '/admin/cafeteria')

        login_target()
        page.get_by_label('Konto browser.lifecycle ausdrücklich deaktivieren', exact=True).check()
        page.get_by_role('button', name='Konto deaktivieren', exact=True).click()
        expect(page.get_by_role('button', name='Konto reaktivieren', exact=True)).to_be_visible()
        assert target_page.goto(origin + '/admin/cafeteria', wait_until='networkidle').status == 401
        page.screenshot(path=str(tmp_path / 'iam-disabled-390.png'), full_page=True)
        page.get_by_label('Konto browser.lifecycle ausdrücklich reaktivieren', exact=True).check()
        page.get_by_role('button', name='Konto reaktivieren', exact=True).click()
        expect(page.get_by_role('button', name='Konto deaktivieren', exact=True)).to_be_visible()
        login_target()
        page.goto(detail_url, wait_until='networkidle')
        page.get_by_role('link', name='Kontoereignisse', exact=True).click()
        expect(page.get_by_text('Lokales Konto reaktiviert.', exact=True)).to_be_visible()
        page.screenshot(path=str(tmp_path / 'iam-lifecycle-events-390.png'), full_page=True)
        assert errors == []


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('density', ['compact', 'comfortable'])
def test_conflict_and_database_failure_remain_readable(live_accounts, browser, monkeypatch, tmp_path, width, density):
    from sqlalchemy.exc import OperationalError

    from cafeteria.auth import local_users as users
    from test_auth_routes import ACTOR_IDENTIFIER

    origin, client, owner, issuer = live_accounts
    target = _create(issuer)
    with client.session_transaction() as state:
        actor, version = state['user']['id'], state['authz_version']
    set_admin_density(owner, actor, version, density)
    with _context(browser, origin, client, width) as context:
        page = context.new_page()
        failures = []
        page.on('requestfailed', lambda request: failures.append(request.failure))
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.goto(origin + f'/admin/benutzer/{target.public_id}', wait_until='networkidle')
        command = users.load_local_command_context(issuer, actor_identifier=ACTOR_IDENTIFIER,
                                                  target_username='managed.editor')
        newer = users.replace_local_roles(issuer, actor=command.actor, target=command.target,
                                          roles=('Cafeteria.Publisher',))
        page.get_by_label('Editor · Menüs bearbeiten', exact=True).uncheck()
        page.get_by_label('Admin · Benutzer und Einstellungen verwalten', exact=True).check()
        page.get_by_label('Rollenänderung für managed.editor bestätigen', exact=True).check()
        with page.expect_navigation() as navigation:
            page.get_by_role('button', name='Rollen speichern').click()
        assert navigation.value.status == 409
        expect(page.get_by_role('alert')).to_contain_text('zwischenzeitlich')
        expect(page.get_by_label('Publisher · Menüs veröffentlichen', exact=True)).to_be_checked()
        expect(page.get_by_label('Rollenänderung für managed.editor bestätigen', exact=True)).not_to_be_checked()
        assert page.locator('input[name=target_version]').evaluate_all(
            'els=>els.map(el=>el.value)') == [str(newer.authz_version)] * 3
        _layout(page)
        page.screenshot(path=str(tmp_path / f'iam-conflict-{density}-{width}.png'), full_page=True)

        def unavailable(*_args, **_kwargs):
            raise OperationalError('DO-NOT-EXPOSE', {}, None)

        monkeypatch.setattr('cafeteria.roles.load_user_authorization', unavailable)
        response = page.goto(origin + '/admin/benutzer', wait_until='networkidle')
        assert response.status == 503 and response.headers['cache-control'] == 'no-store'
        assert "style-src 'self'" in response.headers['content-security-policy']
        expect(page.get_by_role('heading', name='Benutzerverwaltung nicht verfügbar')).to_be_visible()
        assert 'DO-NOT-EXPOSE' not in page.content()
        _layout(page)
        page.screenshot(path=str(tmp_path / f'iam-unavailable-{density}-{width}.png'), full_page=True)
        assert failures == []
