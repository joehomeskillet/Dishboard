"""UI-DELTA account list and history keep one route per purpose."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from test_admin_local_users_browser import live_accounts  # noqa: F401
from test_admin_local_users_routes import _create, admin_account  # noqa: F401
from test_auth_routes import auth_app  # noqa: F401
from test_delta_renderer_browser import VISIBILITY
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_accounts_and_history_delta(live_accounts, browser, tmp_path, width, height, touch):  # noqa: F811
    origin, client, owner, issuer = live_accounts
    cookie_name = client.application.config['SESSION_COOKIE_NAME']
    cookie = client.get_cookie(cookie_name)
    failures = []
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch) as context:
        context.add_cookies([{'name': cookie_name, 'value': cookie.value, 'url': origin}])
        page = context.new_page()
        methods = []
        page.on('request', lambda request: methods.append(request.method))

        def visit(route, label):
            assert page.goto(origin + route).status == 200
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if page.locator('main details, main summary').count():
                failures.append(label + ': content accordion')
            for control in page.locator('main a.ui-sem-control:visible, main button.ui-sem-control:visible, main .admin-segment-switch a').all():
                result = control.evaluate(VISIBILITY)
                assert not result['pseudos'], result
                assert (result['icons'] == 1 and not result['text']) or (
                    result['icons'] == 0 and bool(result['text'])
                ), result

        visit('/admin/benutzer', 'empty')
        if page.locator('main [data-semantic="actions.add"]').count() != 1:
            failures.append('R-39: duplicate create')
        target = _create(issuer, 'delta.list')
        visit('/admin/benutzer', 'filled')
        expect(page.locator('[data-account-row]')).to_have_count(1)
        visit('/admin/benutzer?status=active', 'active')
        expect(page.locator('[data-account-row] .admin-list-status')).to_have_count(0)
        with owner.begin() as connection:
            connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE source=\'local\' '
                                    'AND user_id=(SELECT id FROM cafeteria.users WHERE public_id=:id)'),
                               {'id': target.public_id})
        visit('/admin/benutzer', 'no-role')
        if not page.locator('[data-account-row]').get_by_text('Keine Rolle', exact=True).count():
            failures.append('P-15: missing access role must be explicit')
        visit('/admin/benutzer?status=disabled', 'filtered-empty')
        if page.locator('main [data-semantic="view.reset"]').count():
            failures.append('R-77: duplicate reset beside all-accounts segment')
        page.get_by_role('link', name='Alle lokalen Konten', exact=True).click()
        expect(page.locator('[data-account-row]')).to_have_count(1)
        visit('/admin/benutzer/protokoll', 'events')
        if not page.locator('#account-events-hint').is_visible():
            failures.append('D-100: hidden events guidance')
        visit('/admin/benutzer/zugriffsverlauf', 'history')
        if not page.get_by_text('Zeitangaben: Schweiz.', exact=False).is_visible():
            failures.append('D-65: hidden history scope')
        page.get_by_label('Zugang', exact=True).select_option('entra')
        page.get_by_role('button', name='Filter', exact=True).click()
        expect(page.get_by_label('Zugang', exact=True)).to_have_value('entra')
        page.get_by_role('link', name='Zurücksetzen', exact=True).click()
        expect(page.get_by_label('Zugang', exact=True)).to_have_value('all')
    assert set(methods) == {'GET'}
    assert not failures, failures
