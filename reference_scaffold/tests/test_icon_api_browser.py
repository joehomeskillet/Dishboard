"""API key actions share accessible icon controls without changing native forms."""
from __future__ import annotations

import json
from threading import Thread
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from test_admin_api_page import _create_form, admin_client, app, database_engine
from test_rendered_ui import browser

__all__ = ['admin_client', 'app', 'database_engine', 'browser']


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
def test_api_icon_actions_keyboard_and_confirmation(
    admin_client, browser, tmp_path, width, javascript, locale, monkeypatch,
):
    application = admin_client.application
    monkeypatch.setitem(application.config, 'UI_LOCALE', locale)
    key_label = 'Vorschau Küche' if locale == 'de' else 'Preview <Kitchen> & "A"'
    revoke_name = f'Schlüssel {key_label} widerrufen' if locale == 'de' else f'Revoke key {key_label}'
    confirmation = 'Schlüssel wirklich widerrufen?' if locale == 'de' else 'Really revoke this key?'
    consequence = ('Anwendungen verlieren damit den Vorschauzugriff.' if locale == 'de'
                   else 'Applications will lose preview access.')
    payload = _create_form()
    payload['label'] = key_label
    assert admin_client.post('/admin/api/keys', data=payload, follow_redirects=True).status_code == 200
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
            posts, errors, measurements = [], [], []
            page.on('request', lambda req: posts.append(req) if req.method == 'POST' else None)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(origin + '/admin/api', wait_until='networkidle')
            expect(page.locator('html')).to_have_attribute('lang', locale)
            expect(page.locator('[data-new-key]')).to_have_count(0)
            row = page.locator('[data-key-state="active"]')
            key_id = row.get_attribute('data-key-id')
            expect(row.locator('.admin-list-primary')).to_have_text(key_label)
            expect(row.locator('.admin-list-primary > *')).to_have_count(0)
            revoke = row.locator('form[action$="/revoke"]')
            trigger = revoke.get_by_role('button', name=revoke_name, exact=True)
            expect(row.locator('[data-semantic="actions.more"]')).to_have_count(0)
            expect(row.locator('.admin-api-key-details > summary')).to_have_count(0)
            expect(row.locator('[data-api-key-prefix]')).to_be_visible()

            def capture(stage):
                row.scroll_into_view_if_needed()
                page.evaluate('document.fonts.ready')
                for moment in ('before', 'after'):
                    if moment == 'after':
                        page.screenshot(path=str(tmp_path / f'api-{width}-{locale}-js-{javascript}-{stage}.png'), full_page=False)
                    state = page.evaluate('''() => ({coarse: matchMedia('(pointer: coarse)').matches,
                        anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                        fine: matchMedia('(pointer: fine)').matches, maxTouchPoints: navigator.maxTouchPoints,
                        width: innerWidth, scrollWidth: document.documentElement.scrollWidth})''')
                    state['controls'] = [control.evaluate('''el => ({width: el.getBoundingClientRect().width,
                        height: el.getBoundingClientRect().height})''') for control in (trigger,)]
                    measurements.append({'stage': stage, 'moment': moment, 'state': state})
                    (tmp_path / 'api-measurements.json').write_text(json.dumps(measurements, indent=2))
                    coarse = width == 390
                    assert (state['coarse'], state['anyCoarse'], state['fine']) == (coarse, coarse, not coarse), state
                    assert state['maxTouchPoints'] == (1 if coarse else 0), state
                    assert state['width'] == width and state['scrollWidth'] <= width + 1, state
                    size = 44 if coarse else 36
                    assert all(c['width'] >= size and c['height'] == size for c in state['controls']), state

            capture('static')
            expect(trigger).to_have_accessible_name(revoke_name)
            for control in (trigger,):
                expect(control).to_have_text('Widerrufen' if locale == 'de' else 'Revoke')
                assert control.get_attribute('title') is None
                assert control.get_attribute('data-ui-tooltip') == control.get_attribute('aria-label')
                expect(control.locator('svg')).to_have_count(0)
                box = control.bounding_box()
                assert box and box['width'] >= (44 if width == 390 else 36)
                assert box['height'] >= (44 if width == 390 else 36)
            assert revoke.get_attribute('method') == 'post'
            expect(revoke).to_have_attribute('data-confirm', confirmation)
            assert revoke.evaluate('e => [...new FormData(e)]') == [['_csrf', 'workflow-csrf']]
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            expect(page.locator('#api-key-create-title')).to_contain_text('API-Schlüssel' if locale == 'de' else 'API key')
            expect(page.locator('#api-technical > summary')).to_have_count(0)
            expect(page.locator('[data-api-help]')).to_be_visible()
            page.mouse.move(0, 0)
            page.keyboard.press('Tab')
            trigger.focus()
            expect(trigger).to_be_focused()
            assert trigger.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
            if javascript:
                tooltip = page.get_by_role('tooltip', name=revoke_name, exact=True)
                expect(tooltip).to_be_visible()
                trigger.press('Escape')
                expect(tooltip).not_to_be_visible()
            expect(row.locator('.admin-api-key-details dl')).to_be_visible()
            expect(row.locator('[data-api-key-prefix]')).to_be_visible()
            expect(row.locator('.ui-sem-actions')).to_have_count(0)
            expect(revoke.locator('.ui-sem-consequence')).to_have_text(f'{confirmation} {consequence}')
            confirm = revoke.get_by_role('button', name=revoke_name, exact=True)
            expect(confirm).to_have_text('Widerrufen' if locale == 'de' else 'Revoke')
            expect(confirm).to_have_attribute('type', 'submit')
            capture('confirmation')
            # Reading static metadata and focusing a control cannot revoke a key.
            expect(confirm).to_be_visible()
            assert not posts and not errors
            page.reload(wait_until='networkidle')
            expect(page.locator('[data-key-state="active"]')).to_have_count(1)
            if javascript:
                dialogs = []

                def dismiss(dialog):
                    dialogs.append(dialog.message)
                    dialog.dismiss()

                page.once('dialog', dismiss)
                confirm.press('Enter')
                assert dialogs == [confirmation]
                assert not posts
                expect(page.locator('[data-key-state="active"]')).to_have_count(1)
                page.once('dialog', lambda dialog: dialog.accept())
            with page.expect_response(lambda response: response.request.method == 'POST') as submitted:
                confirm.press('Enter')
            assert submitted.value.status == 303
            assert submitted.value.url == f'{origin}/admin/api/keys/{key_id}/revoke'
            assert parse_qs(submitted.value.request.post_data) == {'_csrf': ['workflow-csrf']}
            expect(page.locator(f'[data-key-id="{key_id}"][data-key-state="revoked"]')).to_be_visible()
            expect(page.locator('form[action$="/revoke"]')).to_have_count(0)
            assert len(posts) == 1 and not errors
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
