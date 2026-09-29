"""Real delayed recipe-editor save and native error return keep the icon-only submitter honest.

The recipe editor posts natively from an external header submitter. A held server POST measures
what a user actually gets: submitter state, duplicate activation and the number of POSTs the
server receives. Missing product behaviour is reported as a red assertion, never defined away.
"""
from __future__ import annotations

import json
from base64 import b64decode
from threading import Event
from time import monotonic
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect

from test_master_data_browser import master_server  # noqa: F401
from test_recipe_density_browser import reference
from test_recipe_routes import (  # noqa: F401
    app_engine, b3, fields, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import snapshot
from test_rendered_ui import browser  # noqa: F401

SAVE = 'Speichern'
SUBMITTER = 'button[form="recipe-editor"]'
NEW_TITLE = 'Gemüsesuppe · verzögert gespeichert'
BLANK_TITLE = '   '
STATE = '''() => {
    const button = document.querySelector('button[form="recipe-editor"]'), box = button.getBoundingClientRect();
    return {name: button.getAttribute('aria-label'), text: button.innerText, disabled: button.disabled,
        ariaDisabled: button.getAttribute('aria-disabled'), busy: button.getAttribute('aria-busy'),
        loading: button.classList.contains('admin-btn-loading'), svg: !!button.querySelector('svg'),
        focused: document.activeElement === button,
        x: box.x, y: box.y, width: box.width, height: box.height};
}'''
CONTRACT = '''() => {
    const form = document.querySelector('#recipe-editor'), button = document.querySelector('button[form="recipe-editor"]');
    return {method: form.getAttribute('method'), action: form.getAttribute('action'),
        names: [...form.elements].filter(el => el.name && !el.disabled).map(el => el.name),
        hidden: Object.fromEntries([...form.querySelectorAll('input[type=hidden]')].map(el => [el.name, el.value])),
        submitter: {form: button.getAttribute('form'), type: button.getAttribute('type'),
            name: button.getAttribute('name'), value: button.getAttribute('value'),
            inside: !!button.closest('form'), owner: button.form === form}};
}'''
FIELDS = '() => [...new FormData(document.querySelector("#recipe-editor"))]'


def normalized(items):
    return [(key, value.replace('\r\n', '\n')) for key, value in items]


def submit_by_keyboard(page):
    # no_wait_after: keyboard.press would block until the held navigation commits.
    page.locator(SUBMITTER).press('Enter', no_wait_after=True)


def cdp_enter(cdp):
    cdp.send('Input.dispatchKeyEvent', {
        'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13, 'text': '\r'})
    cdp.send('Input.dispatchKeyEvent', {
        'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})


def screenshot(cdp, path):
    path.write_bytes(b64decode(cdp.send('Page.captureScreenshot', {
        'format': 'png', 'captureBeyondViewport': False})['data']))


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_recipe_editor_native_loading_and_error_return(
    b3, master_server, browser, monkeypatch, tmp_path, width, height, javascript,  # noqa: F811
):
    app, owner, client, _ = b3
    path = reference(client)
    base, cookie = master_server
    original = fields(client, path)
    failures, observations = [], {'javascript': javascript, 'width': width}
    held_posts, statuses = [], []
    pending, release, expired, hold = Event(), Event(), Event(), Event()
    original_wsgi = app.wsgi_app

    def hold_post(environ, start_response):
        if environ['REQUEST_METHOD'] != 'POST' or environ['PATH_INFO'] != path:
            return original_wsgi(environ, start_response)
        held_posts.append(monotonic())

        def record(status, headers, exc_info=None):
            statuses.append(int(status[:3]))
            return start_response(status, headers, exc_info)
        if hold.is_set():
            pending.set()
            if not release.wait(15):
                expired.set()
                raise TimeoutError('Recipe-editor test barrier was not released within 15s')
        return original_wsgi(environ, record)

    def check(condition, message):
        if not condition:
            failures.append(message)

    with browser.new_context(
        base_url=base, java_script_enabled=javascript, has_touch=width == 390,
        viewport={'width': width, 'height': height}, reduced_motion='reduce', service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        requests = []
        page.on('request', lambda request: requests.append(request) if request.method == 'POST' else None)
        assert page.goto(path).status == 200
        page.evaluate('document.fonts.ready')
        submitter = page.locator(SUBMITTER)
        form = page.locator('#recipe-editor')
        expect(submitter).to_have_accessible_name(SAVE)
        expect(submitter).to_have_text('')
        expect(submitter).to_have_attribute('type', 'submit')
        expect(form).to_have_attribute('method', 'post')
        expect(form).to_have_attribute('action', path)
        assert submitter.evaluate('b => b.form === document.querySelector("#recipe-editor") && !b.closest("form")')
        contract_before = page.evaluate(CONTRACT)
        assert contract_before['hidden']['_csrf'] and contract_before['hidden']['_form_context']
        assert contract_before['hidden']['row_version'] == original['row_version']
        idle = page.evaluate(STATE)
        assert not idle['disabled'] and idle['busy'] is None and not idle['loading'] and idle['svg']
        observations['idle'] = idle
        before_db = snapshot(owner)

        # Phase 1: valid save with the real POST held at the server.
        page.locator('[name="title"]').fill(NEW_TITLE)
        expected_fields = normalized(page.evaluate(FIELDS))
        assert dict(expected_fields)['title'] == NEW_TITLE
        cdp = context.new_cdp_session(page)
        busy = None
        ticks = []
        # Console events need no evaluate round trip, which cannot be answered while the POST is held.
        page.on('console', lambda message: ticks.append(json.loads(message.text[5:]))
                if message.text.startswith('TICK:') else None)
        page.evaluate("""() => {
            const read = %s;
            setInterval(() => console.log('TICK:' + JSON.stringify(read())), 100);
        }""" % STATE.strip())
        monkeypatch.setattr(app, 'wsgi_app', hold_post)
        hold.set()
        try:
            with page.expect_request(lambda r: r.method == 'POST' and r.url == base + path):
                submit_by_keyboard(page)
            deadline = monotonic() + 3
            while not pending.is_set() and monotonic() < deadline:
                page.wait_for_timeout(10)
            assert pending.is_set() and len(held_posts) == 1
            assert normalized((key, value[0]) for key, value in parse_qs(
                requests[0].post_data, keep_blank_values=True).items()) == expected_fields
            page.wait_for_timeout(500)
            assert ticks or not javascript, 'no state ticks arrived while the POST was held'
            busy = ticks[-1] if javascript else None
            observations['busy'] = busy
            screenshot(cdp, tmp_path / f'save-busy-{width}-js{javascript}.png')
            assert snapshot(owner) == before_db  # server is still holding: nothing saved yet
            if javascript:  # without JS nothing can block a second native submit; that is no product claim
                # Second activation attempt: Enter again, focus still sits on the submitter.
                cdp_enter(cdp)
                page.wait_for_timeout(1000)
            observations['posts_at_server_while_held'] = len(held_posts)
            observations['posts_from_browser_while_held'] = len(requests)
            observations['busy_after_second_attempt'] = ticks[-1] if javascript else None
            with page.expect_navigation(wait_until='domcontentloaded'):
                release.set()
        finally:
            release.set()
            hold.clear()
        assert not expired.is_set()
        page.wait_for_timeout(500)
        observations['server_statuses'] = list(statuses)
        expect(page.locator('.admin-btn-loading, [aria-busy="true"]')).to_have_count(0)
        # After a duplicate submit the browser may land on the 409 page; reload for the form contract.
        observations['landing_is_editor'] = page.locator('#recipe-editor').count() == 1
        assert page.goto(path).status == 200
        saved = fields(client, path)
        observations['saved_row_version'] = saved['row_version']
        assert saved['title'] == NEW_TITLE and int(saved['row_version']) == int(original['row_version']) + 1
        expect(page.locator('[name="title"]')).to_have_value(NEW_TITLE)
        contract_after = page.evaluate(CONTRACT)
        assert (contract_after['method'], contract_after['action'], contract_after['names'],
                contract_after['submitter']) == (contract_before['method'], contract_before['action'],
                                                 contract_before['names'], contract_before['submitter'])
        assert contract_after['hidden']['_csrf'] and contract_after['hidden']['_form_context']
        assert int(contract_after['hidden']['row_version']) == int(original['row_version']) + 1

        check(statuses.count(303) == 1 and len(held_posts) == 1,
              f'save reached the server {len(held_posts)}x with statuses {statuses}, expected exactly one 303')
        if javascript:
            check(busy['disabled'] or busy['ariaDisabled'] == 'true',
                  f'submitter stayed operable during the held POST: {busy}')
            check(busy['busy'] == 'true' and busy['loading'], f'no calm progress state on the submitter: {busy}')
            check(busy['name'] == SAVE and busy['text'] == '' and busy['svg'],
                  f'submitter lost its accessible name or icon during the held POST: {busy}')
        check(observations['posts_at_server_while_held'] == 1,
              f'duplicate activation reached the server {observations["posts_at_server_while_held"]}x while held')

        # Phase 2: native error return; no client-side validation may hide the server response.
        assert page.goto(path).status == 200
        page.locator('[name="title"]').fill(BLANK_TITLE)
        error_fields = normalized(page.evaluate(FIELDS))
        stored = snapshot(owner)
        posts_before = len(requests)
        with page.expect_response(lambda r: r.request.method == 'POST' and r.url == base + path) as result:
            submit_by_keyboard(page)
        response = result.value
        page.wait_for_load_state('domcontentloaded')
        observations['error_status'] = response.status
        assert response.status == 400 and len(requests) == posts_before + 1
        assert snapshot(owner) == stored
        expect(page.get_by_role('alert')).to_be_visible()
        expect(page.get_by_role('alert')).not_to_be_empty()
        kept = page.evaluate('() => [...document.querySelectorAll("input[type=hidden]")].map(el => [el.name, el.value])')
        assert normalized(kept) == error_fields, 'submitted values must be preserved on the error page'
        expect(page.locator('.admin-btn-loading, [aria-busy="true"], button:disabled')).to_have_count(0)
        reload = page.get_by_role('link', name='Aktuellen Stand bewusst neu laden')
        expect(reload).to_be_visible()
        assert reload.get_attribute('aria-disabled') is None
        screenshot(cdp, tmp_path / f'error-return-{width}-js{javascript}.png')
        cdp.detach()
        # Back to the editor: the submitter must be usable again (pageshow/reload restores it).
        page.go_back(wait_until='domcontentloaded')
        expect(submitter).to_be_enabled()
        back = page.evaluate(STATE)
        observations['after_back'] = back
        assert back['busy'] is None and not back['loading'] and back['name'] == SAVE

    (tmp_path / 'recipe-loading-observations.json').write_text(json.dumps(observations, indent=2) + '\n')
    assert not failures, {'failures': failures, 'measured': observations}
