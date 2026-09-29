"""Real paused week-review POSTs retain an accessible icon-only busy state."""
from __future__ import annotations

import json
from base64 import b64decode
from threading import Event
from time import monotonic
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.workflow_partial_store import persist_week_header
from cafeteria.workflow_review_context import get_week_review
from test_admin_workflow_db import WEEK_START, _save
from test_admin_workflow_routes import DATABASE_URL, _login, _scope
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_week_review_browser import CONFIRM, _audit_count, _url, _values

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('width,height,family,profile', [
    (390, 844, 'patienten', 'patient'), (1440, 900, 'cafeteria', 'staff_guest'),
])
@pytest.mark.parametrize('stale', [False, True], ids=['success', 'stale409'])
def test_real_week_review_loading_preserves_native_post(
    admin_app, admin_engine, browser, live_server, tmp_path, monkeypatch,  # noqa: F811
    width, height, family, profile, stale,
):
    values = _values(profile)
    version = _save(admin_engine, profile, values)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    scope = _scope(admin_engine, actor, profile)
    original = get_week_review(admin_engine, scope, WEEK_START)
    assert original['receipt'] is None and _audit_count(admin_engine) == 0
    observations = {}
    phases = []

    def phase(name):
        phases.append({'phase': name, 'time': monotonic()})
        (tmp_path / 'phases.json').write_text(json.dumps(phases, indent=2) + '\n')

    with browser.new_context(
        base_url=live_server, java_script_enabled=True, has_touch=width == 390,
        viewport={'width': width, 'height': height}, reduced_motion='reduce',
        service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        assert page.goto(_url(family)).status == 200
        page.evaluate('document.fonts.ready')
        confirm = page.get_by_role('button', name=CONFIRM, exact=True)
        form = page.locator('#week-review-form')
        expect(confirm).to_have_attribute('type', 'submit')
        expect(confirm).to_have_attribute('form', 'week-review-form')
        assert confirm.evaluate('button => button.form === document.querySelector("#week-review-form") && !button.closest("form")')
        expect(confirm).to_have_accessible_name(CONFIRM)
        expect(confirm).to_have_attribute('data-ui-tooltip', CONFIRM)
        expect(confirm).to_have_text('')
        expect(confirm.locator('svg[aria-hidden="true"] > use')).to_have_attribute(
            'href', '/static/vendor/tabler-icons/tabler-icons.svg#tabler-check')
        expect(form).to_have_attribute('method', 'post')
        path = _url(family).split('?')[0]
        expect(form).to_have_attribute('action', path)
        expected_fields = form.evaluate('form => [...new FormData(form)]')
        assert {key for key, _ in expected_fields} == {'_csrf', 'week', 'context_version'}
        assert dict(expected_fields)['_csrf']
        assert dict(expected_fields)['week'] == str(WEEK_START)
        assert dict(expected_fields)['context_version'] == original['token']
        assert get_week_review(admin_engine, scope, WEEK_START) == original

        cdp = context.new_cdp_session(page)

        def capture(stage):
            phase(stage + ':pointer-before')
            pointer = page.evaluate('''() => ({fine: matchMedia('(pointer: fine)').matches,
                coarse: matchMedia('(pointer: coarse)').matches,
                anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                touch: navigator.maxTouchPoints})''')
            assert pointer == {'fine': width == 1440, 'coarse': width == 390,
                               'anyCoarse': width == 390, 'touch': int(width == 390)}
            phase(stage + ':position')
            page.mouse.move(0, 0)
            page.evaluate('() => scrollTo(0, 0)')
            screenshot = tmp_path / f'{family}-{width}-{stage}.png'
            phase(stage + ':screenshot-before')
            page.screenshot(path=str(screenshot), full_page=False, timeout=5000)
            phase(stage + ':screenshot-after')
            assert page.evaluate('''() => ({fine: matchMedia('(pointer: fine)').matches,
                coarse: matchMedia('(pointer: coarse)').matches,
                anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                touch: navigator.maxTouchPoints})''') == pointer
            observations[stage] = {'pointer': pointer}

        read_state = '''button => {
                const box = button.getBoundingClientRect(), svg = button.querySelector('svg'),
                    icon = svg.getBoundingClientRect(), glyph = svg.querySelector('use').getBBox(),
                    spinner = getComputedStyle(button, '::after'),
                    left = parseFloat(spinner.left), top = parseFloat(spinner.top),
                    width = parseFloat(spinner.width), height = parseFloat(spinner.height),
                    x = box.x + button.clientLeft + left, y = box.y + button.clientTop + top;
                return {name: button.getAttribute('aria-label'), text: button.innerText,
                    disabled: button.disabled, busy: button.getAttribute('aria-busy'),
                    loading: button.classList.contains('admin-btn-loading'),
                    x: box.x, y: box.y, width: box.width, height: box.height,
                    iconWidth: icon.width, iconHeight: icon.height,
                    glyphWidth: glyph.width, glyphHeight: glyph.height,
                    spinner: {content: spinner.content, width: spinner.width, height: spinner.height,
                        left: spinner.left, top: spinner.top, position: spinner.position,
                        boxSizing: spinner.boxSizing, transform: spinner.transform},
                    spinnerBox: [x, y, x + width, y, x + width, y + height, x, y + height]
                        .every(Number.isFinite) ? [x, y, x + width, y, x + width, y + height, x, y + height] : null};
        }'''

        def control_state():
            return page.evaluate(
                f'() => ({read_state})(document.querySelector(\'button[form="week-review-form"]\'))')

        capture('before')
        before = control_state()
        size = 44 if width == 390 else 36
        assert before['width'] == before['height'] == size
        assert before['iconWidth'] == before['iconHeight'] == 20
        assert not before['disabled'] and before['busy'] is None and not before['loading']
        snapshots = []

        def receive_snapshot(source, snapshot):
            assert source['page'] == page
            snapshot['received_at'] = monotonic()
            snapshots.append(snapshot)

        page.expose_binding('recordWeekReviewState', receive_snapshot)
        # Observe actual events only: no submit, FormData construction, timers or DOM writes.
        page.evaluate(f'''() => {{
            const form = document.querySelector('#week-review-form'),
                button = document.querySelector('button[form="week-review-form"]'),
                readControl = ({read_state});
            const snapshot = phase => window.recordWeekReviewState({{
                phase, browserTime: performance.now(), control: readControl(button),
                fields: [...form.elements].filter(el => el.name && !el.disabled)
                    .map(el => [el.name, el.value]),
                pointer: {{fine: matchMedia('(pointer: fine)').matches,
                    coarse: matchMedia('(pointer: coarse)').matches,
                    anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                    touch: navigator.maxTouchPoints}}
            }});
            document.addEventListener('submit', event => {{
                if (event.target === form) snapshot('submit');
            }});
            window.addEventListener('beforeunload', () => snapshot('beforeunload'));
            new MutationObserver(() => snapshot('mutation')).observe(button, {{
                attributes: true, attributeFilter: ['disabled', 'aria-busy', 'class']
            }});
        }}''')
        if stale:
            persist_week_header(admin_engine, scope, WEEK_START,
                                {'title': 'Neuer gespeicherter Wochenkopf', 'shared_note': values['shared_note']}, version)
        server_before_post = get_week_review(admin_engine, scope, WEEK_START)
        assert server_before_post['receipt'] is None
        assert (server_before_post['token'] != original['token']) == stale
        pending, release, expired = Event(), Event(), Event()
        held_posts, posts = [], []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        original_wsgi = admin_app.wsgi_app

        def hold_post(environ, start_response):
            if environ['REQUEST_METHOD'] == 'POST' and environ['PATH_INFO'] == path:
                held_posts.append(environ['PATH_INFO'])
                pending.set()
                if not release.wait(15):
                    expired.set()
                    raise TimeoutError('Week-review test barrier was not released within 15s')
            return original_wsgi(environ, start_response)

        monkeypatch.setattr(admin_app, 'wsgi_app', hold_post)
        try:
            phase('request:click-before')
            with page.expect_request(lambda request: request.method == 'POST' and request.url == live_server + path):
                confirm.click(no_wait_after=True)
            phase('request:observed')
            # Pump request callbacks while the server thread waits before the real handler.
            deadline = monotonic() + 3
            while not pending.is_set() and monotonic() < deadline:
                page.wait_for_timeout(10)
            assert pending.is_set() and len(held_posts) == len(posts) == 1
            phase('barrier:held')
            assert parse_qs(posts[0].post_data, keep_blank_values=True) == {
                key: [value] for key, value in expected_fields}
            # Allow the real deferred loader to publish a mutation while the POST is held.
            deadline = monotonic() + 3
            while (not snapshots or not snapshots[-1]['control']['loading']) and monotonic() < deadline:
                page.wait_for_timeout(10)
            assert snapshots and any(item['phase'] == 'beforeunload' for item in snapshots)
            assert all(item['fields'] == expected_fields for item in snapshots)
            observed = snapshots[-1]
            busy = observed['control']
            assert observed['pointer'] == observations['before']['pointer']
            phase('busy:screenshot-before')
            (tmp_path / f'{family}-{width}-busy.png').write_bytes(b64decode(
                cdp.send('Page.captureScreenshot', {
                    'format': 'png', 'captureBeyondViewport': False,
                })['data']))
            phase('busy:screenshot-after')
            assert get_week_review(admin_engine, scope, WEEK_START) == server_before_post
            assert _audit_count(admin_engine) == 0
            if busy['disabled']:
                box = busy
                page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                assert len(posts) == 1
            spinner_box = busy['spinnerBox']
            assert not expired.is_set() and not release.is_set()
            observations['before']['control'] = before
            observations['busy'] = {
                'control': busy, 'spinner_box': spinner_box, 'posts': len(posts),
                'measurement_boundary': observed['phase'], 'received_at': observed['received_at'],
                'snapshots': [{key: value for key, value in item.items() if key != 'fields'}
                              for item in snapshots], 'fields_match_native_post': True,
            }
            with page.expect_navigation(wait_until='domcontentloaded'), page.expect_response(
                lambda response: response.request.method == 'POST' and response.url == live_server + path
            ) as result:
                phase('barrier:release')
                release.set()
            phase('response:observed')
        finally:
            release.set()
            phase('barrier:finally-released')
            cdp.detach()
        assert not expired.is_set() and len(held_posts) == 1
        assert result.value.status == (409 if stale else 303)
        assert len(posts) == 1
        current = get_week_review(admin_engine, scope, WEEK_START)
        assert current['context'] == server_before_post['context']
        expect(page.locator('.admin-btn-loading, [aria-busy="true"]')).to_have_count(0)
        if stale:
            expect(page.locator('body')).to_contain_text('Wochenkopf oder Servicehinweise wurden geändert. Bitte erneut prüfen.')
            assert current['receipt'] is None and _audit_count(admin_engine) == 0
            capture('after409')
            assert page.goto(_url(family)).status == 200
            expect(confirm).to_be_enabled()
            assert control_state()['busy'] is None and not control_state()['loading']
            expect(form.locator('[name="context_version"]')).to_have_value(current['token'])
            expect(page.get_by_text('Neuer gespeicherter Wochenkopf', exact=True)).to_be_visible()
        else:
            assert result.value.headers['location'] == _url(family)
            assert current['receipt'] is not None and _audit_count(admin_engine) == 1
            expect(page.get_by_role('status')).to_contain_text('Dieser Stand wurde von ' + current['receipt']['actor_name'])
            expect(confirm).to_have_count(0)
            with admin_engine.connect() as connection:
                assert connection.execute(text(
                    "SELECT details->>'reviewed_token' FROM cafeteria.audit_events "
                    "WHERE action='workflow.week_context_reviewed'"
                )).scalar_one() == original['token']
        capture('after')
        with admin_engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.publication_revisions')).scalar_one() == 0
            assert connection.execute(text(
                "SELECT count(*) FROM cafeteria.audit_events WHERE action='workflow.menu_reviewed'"
            )).scalar_one() == 0
        (tmp_path / 'loading-observations.json').write_text(json.dumps(observations, indent=2) + '\n')
        assert busy['name'] == CONFIRM and busy['text'] == ''
        assert busy['width'] == busy['height'] == size
        assert busy['iconWidth'] == busy['iconHeight'] == 20
        assert busy['glyphWidth'] > 0 and busy['glyphHeight'] > 0
        assert busy['disabled'] and busy['busy'] == 'true' and busy['loading'], busy
        assert busy['spinner']['content'] == '""' and spinner_box is not None
        assert busy['spinner']['position'] == 'absolute'
        assert busy['spinner']['boxSizing'] == 'border-box' and busy['spinner']['transform'] == 'none'
        assert busy['x'] <= min(spinner_box[::2]) < max(spinner_box[::2]) <= busy['x'] + busy['width']
        assert busy['y'] <= min(spinner_box[1::2]) < max(spinner_box[1::2]) <= busy['y'] + busy['height']
