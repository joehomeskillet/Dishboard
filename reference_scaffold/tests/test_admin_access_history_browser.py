from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from test_access_history_reads import _seed_history
from test_admin_access_history_routes import PATH
from test_admin_local_users_browser import _layout, live_accounts
from test_admin_local_users_routes import admin_account
from test_auth_routes import auth_app
from test_print_template_browser import browser

__all__ = ['live_accounts', 'admin_account', 'auth_app', 'browser']


@pytest.mark.parametrize('width,javascript', [(390, False), (1440, True)])
def test_native_history_filters_pagination_keyboard_and_outage(
    live_accounts, browser, tmp_path, monkeypatch, width, javascript,
):
    origin, client, owner, _ = live_accounts
    cookie_name = client.application.config['SESSION_COOKIE_NAME']
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    with browser.new_context(viewport={'width': width, 'height': 1050},
                             java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie_name, 'value': cookie.value, 'url': origin}])
        page = context.new_page()
        errors, requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('requestfailed', lambda request: requests.append(request.failure))
        response = page.goto(origin + PATH, wait_until='networkidle')
        assert response.status == 200 and response.headers['cache-control'] == 'no-store'
        assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
        expect(page.get_by_text('Keine Zugriffsereignisse in dieser Auswahl', exact=True)).to_be_visible()
        _layout(page)
        page.screenshot(path=str(tmp_path / f'access-empty-{width}.png'), full_page=True)

        _seed_history(owner, 56)
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.users SET display_name=:name '
                "WHERE auth_provider='local'"), {'name': 'Küchenverantwortung Südhang ' * 4})
        page.goto(origin + '/admin/benutzer', wait_until='networkidle')
        page.get_by_role('link', name='Zugriffsverlauf', exact=True).click()
        expect(page.get_by_role('heading', name='Zugriffsverlauf', exact=True)).to_be_visible()
        expect(page.locator('tbody tr')).to_have_count(50)
        _layout(page)
        page.get_by_label('Zugang', exact=True).focus()
        page.keyboard.press('Tab')
        expect(page.get_by_label('Ereignis', exact=True)).to_be_focused()
        assert page.get_by_label('Ereignis', exact=True).evaluate(
            'el=>el.matches(":focus-visible") && (getComputedStyle(el).outlineStyle!=="none" || getComputedStyle(el).boxShadow!=="none")')
        page.screenshot(path=str(tmp_path / f'access-history-{width}.png'))
        page.screenshot(path=str(tmp_path / f'access-history-full-{width}.png'), full_page=True)

        page.get_by_label('Zugang', exact=True).select_option('entra')
        page.get_by_label('Ereignis', exact=True).select_option('auth.login.accepted')
        page.get_by_role('button', name='Filtern', exact=True).click()
        expect(page.locator('tbody tr')).to_have_count(9)
        assert parse_qs(urlsplit(page.url).query) == {'provider': ['entra'], 'action': ['auth.login.accepted']}
        assert page.locator('tbody td[data-label="Zugang"]').all_text_contents() == ['Microsoft Entra'] * 9
        assert page.locator('tbody td[data-label="Ereignis"]').all_text_contents() == ['Anmeldung akzeptiert'] * 9
        _layout(page)
        page.screenshot(path=str(tmp_path / f'access-filtered-{width}.png'), full_page=True)
        page.get_by_role('link', name='Zurücksetzen', exact=True).click()
        navigation = page.get_by_role('navigation', name='Zugriffsereignisseiten', exact=True)
        navigation.get_by_role('link', name='Weiter', exact=True).click()
        expect(page.locator('tbody tr')).to_have_count(6)
        expect(page.get_by_text('Seite 2', exact=True)).to_be_visible()
        _layout(page)
        page.screenshot(path=str(tmp_path / f'access-second-page-{width}.png'), full_page=True)
        page.get_by_role('link', name='Kontoereignisse', exact=True).click()
        expect(page.get_by_role('heading', name='Kontoereignisse', exact=True, level=1)).to_be_visible()
        page.get_by_role('link', name='Zugriffsverlauf', exact=True).click()
        expect(page.get_by_role('heading', name='Zugriffsverlauf', exact=True)).to_be_visible()
        assert not errors and not requests

        def unavailable(*_args, **_kwargs):
            raise OperationalError('PRIVATE-SENTINEL', {}, None)

        monkeypatch.setattr('cafeteria.admin.access_history_routes.list_access_history', unavailable)
        response = page.goto(origin + PATH, wait_until='networkidle')
        assert response.status == 503 and response.headers['cache-control'] == 'no-store'
        expect(page.get_by_role('heading', name='Benutzerverwaltung nicht verfügbar')).to_be_visible()
        assert 'PRIVATE-SENTINEL' not in page.content()
        _layout(page)
        page.screenshot(path=str(tmp_path / f'access-unavailable-{width}.png'), full_page=True)
        assert not requests
        assert all('503' in error and 'Failed to load resource' in error for error in errors), errors
        (tmp_path / f'access-metrics-{width}.json').write_text(json.dumps({
            'width': width, 'javascript': javascript, 'rows': 50, 'filtered_rows': 9,
            'second_page_rows': 6, 'keyboard_focus': True, 'horizontal_overflow': False,
            'unexpected_browser_errors': [], 'cache_control': 'no-store', 'outage_status': 503,
        }, indent=2))
