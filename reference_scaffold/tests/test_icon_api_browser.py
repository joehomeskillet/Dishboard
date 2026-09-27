"""API key actions share accessible icon controls without changing native forms."""
from __future__ import annotations

from threading import Thread

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from test_admin_api_page import _create_form, admin_client, app, database_engine
from test_rendered_ui import browser

__all__ = ['admin_client', 'app', 'database_engine', 'browser']


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
def test_api_icon_actions_keyboard_and_confirmation(admin_client, browser, tmp_path, width, javascript):
    payload = _create_form()
    payload['label'] = 'Vorschau Küche'
    assert admin_client.post('/admin/api/keys', data=payload, follow_redirects=True).status_code == 200
    application = admin_client.application
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with browser.new_context(
            java_script_enabled=javascript, reduced_motion='reduce', has_touch=width == 390,
            viewport={'width': width, 'height': 844 if width == 390 else 900},
        ) as context:
            name = application.config['SESSION_COOKIE_NAME']
            cookie = admin_client.get_cookie(name)
            assert cookie is not None
            context.add_cookies([{'name': name, 'value': cookie.value, 'url': origin}])
            page = context.new_page()
            page.goto(origin + '/admin/api', wait_until='networkidle')
            expect(page.locator('[data-new-key]')).to_have_count(0)
            row = page.locator('[data-key-state="active"]')
            revoke = row.locator('form[action$="/revoke"]')
            trigger = revoke.locator('summary')
            more = row.locator('.ui-sem-actions > summary')
            expect(trigger).to_have_accessible_name('Schlüssel Vorschau Küche widerrufen')
            expect(more).to_have_accessible_name('Weitere Aktionen für Vorschau Küche')
            for control in (trigger, more):
                expect(control).to_have_text('')
                assert control.get_attribute('title') is None
                assert control.get_attribute('data-ui-tooltip') == control.get_attribute('aria-label')
                expect(control.locator('svg')).to_have_attribute('aria-hidden', 'true')
                box = control.bounding_box()
                assert box and box['width'] >= (44 if width == 390 else 36)
                assert box['height'] >= (44 if width == 390 else 36)
            assert revoke.get_attribute('method') == 'post'
            assert revoke.evaluate('e => [...new FormData(e)]') == [['_csrf', 'workflow-csrf']]
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            expect(page.locator('#api-key-create-title')).to_contain_text('API-Schlüssel')
            expect(page.locator('[data-api-technical] > summary')).to_contain_text('Weitere Optionen')
            page.screenshot(path=str(tmp_path / f'api-{width}-js-{javascript}-closed.png'), full_page=True)
            more.focus()
            expect(more).to_be_focused()
            if javascript:
                expect(page.get_by_role('tooltip')).to_contain_text('Weitere Aktionen für Vorschau Küche')
                more.press('Escape')
                expect(page.get_by_role('tooltip')).not_to_be_visible()
            more.press('Enter')
            details = row.locator('.admin-api-key-details > summary')
            expect(details).to_have_text('Details')
            expect(details).to_have_accessible_name('Details zu Vorschau Küche')
            details.press('Enter')
            expect(row.locator('[data-label="Präfix"]')).to_be_visible()
            details.press('Enter')
            more.press('Enter')
            trigger.press('Enter')
            expect(revoke.locator('.ui-sem-consequence')).to_contain_text('Anwendungen verlieren damit den Vorschauzugriff.')
            confirm = revoke.get_by_role('button', name='Schlüssel Vorschau Küche widerrufen', exact=True)
            expect(confirm).to_have_text('Widerrufen')
            expect(confirm).to_have_attribute('type', 'submit')
            if javascript:
                expect(page.get_by_role('tooltip')).to_have_count(1)
                expect(page.get_by_role('tooltip')).to_contain_text('Schlüssel Vorschau Küche widerrufen')
            page.screenshot(path=str(tmp_path / f'api-{width}-js-{javascript}-confirmation.png'), full_page=True)
            # A disclosure and closing it cannot revoke a key or submit its form.
            trigger.press('Enter')
            expect(confirm).not_to_be_visible()
            page.reload(wait_until='networkidle')
            expect(page.locator('[data-key-state="active"]')).to_have_count(1)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
