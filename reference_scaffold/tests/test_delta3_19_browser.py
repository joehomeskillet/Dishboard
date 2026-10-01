"""UI-DELTA account sections retain separate native security forms."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from test_admin_local_users_browser import live_accounts  # noqa: F401
from test_admin_local_users_routes import _create, admin_account  # noqa: F401
from test_auth_routes import auth_app  # noqa: F401
from test_delta_renderer_browser import VISIBILITY
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_account_delta_sections(live_accounts, browser, tmp_path, monkeypatch, width, height, touch):  # noqa: F811
    origin, client, owner, issuer = live_accounts
    target = _create(issuer, 'delta.account')
    route = f'/admin/benutzer/{target.public_id}'
    failures = []
    cookie_name = client.application.config['SESSION_COOKIE_NAME']
    cookie = client.get_cookie(cookie_name)
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch) as context:
        context.add_cookies([{'name': cookie_name, 'value': cookie.value, 'url': origin}])
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def visit(path, label, status=200):
            assert page.goto(origin + path).status == status
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if page.locator('main details, main summary').count():
                failures.append(label + ': content accordion')
            for control in page.locator('main a.ui-sem-control:visible, main button.ui-sem-control:visible').all():
                result = control.evaluate(VISIBILITY)
                assert not result['pseudos'], result
                assert (result['icons'] == 1 and not result['text']) or (
                    result['icons'] == 0 and bool(result['text'])
                ), result

        visit('/admin/benutzer/neu', 'create')
        expect(page.locator('#create-local-user form')).to_have_attribute('method', 'post')
        expect(page.locator('#create-local-user [name="_csrf"]')).to_have_count(1)
        visit(route, 'editor')
        if not page.locator('#account-actions-hint').is_visible():
            failures.append('D-100: hidden separate-save guidance')
        if page.get_by_text('Nicht vorübergehend gesperrt', exact=True).count() != 1:
            failures.append('R-81: repeated login state')
        for section, action in [('roles', 'rollen'), ('password', 'passwort'), ('state', 'deaktivieren')]:
            form = page.locator(f'#{section}-action form')
            expect(form).to_have_attribute('action', route + '/' + action)
            for name in ('_csrf', 'return_page', 'return_status', 'target_version', 'confirm'):
                expect(form.locator(f'[name="{name}"]')).to_have_count(1)
            expect(form.locator('[name="confirm"]')).to_have_attribute('required', '')
        with owner.begin() as connection:
            connection.execute(text("UPDATE cafeteria.local_credentials SET failed_login_count=5, locked_until=clock_timestamp()+interval '2 hours' "
                                    'WHERE user_id=(SELECT id FROM cafeteria.users WHERE public_id=:id)'),
                               {'id': target.public_id})
        visit(route, 'locked')
        expect(page.locator('.admin-statusbar')).to_contain_text('Gesperrt')
        if page.locator('#account-login-details').get_by_text('Lokale Anmeldung', exact=True).count():
            failures.append('R-81: repeated lock scope')
        client.application.extensions['cafeteria_auth_issuer_db'] = None
        visit(route, 'readonly')
        for submit in page.locator('main form[method="post"] button[type="submit"]').all():
            expect(submit).to_be_disabled()

        def unavailable(*_args, **_kwargs):
            raise OperationalError('SYNTHETIC-PRIVATE-ERROR', {}, None)

        monkeypatch.setattr('cafeteria.roles.load_user_authorization', unavailable)
        visit('/admin/benutzer', 'unavailable', 503)
        recovery = page.locator('[data-semantic="actions.retry"]')
        result = recovery.evaluate(VISIBILITY)
        assert result['text'] == 'Neu laden' and result['icons'] == 0 and not result['pseudos']
        assert 'SYNTHETIC-PRIVATE-ERROR' not in page.content()
        assert not errors, errors
    assert not failures, failures
