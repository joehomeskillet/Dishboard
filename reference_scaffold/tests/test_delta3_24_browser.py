"""UI-DELTA: native login/recovery actions show text only, including fallback."""
from __future__ import annotations

from pathlib import Path
from threading import Thread

import pytest
from flask import render_template, request
from playwright.sync_api import expect
from werkzeug.exceptions import BadRequest, ServiceUnavailable
from werkzeug.serving import make_server

from cafeteria.errors import _minimal, error_view
from test_delta_renderer_browser import VISIBILITY
from test_eh_pages_browser import _error, browser, build_family_app  # noqa: F401
from test_auth_routes import auth_app  # noqa: F401

EVIDENCE = Path('/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18/.claude/state/'
                'claude-session-2026-09-29/audit/DELTA/DELTA-3-24')


@pytest.fixture(scope='module')
def delta_site():
    app = build_family_app()

    @app.get('/delta/post')
    def post_form():
        payload = _error('INTERNAL_ERROR', frame='auth', status=500, request_id='EH-DELTA', recovery=[{
            'semantic': 'actions.reload', 'label_key': 'actions.reload.label',
            'href': '/delta/recovery', 'method': 'post', 'primary': True,
        }])
        return render_template('errors/page.html', error=payload)

    @app.post('/delta/recovery')
    def recovery():
        assert request.form.to_dict() == {'_csrf': 'test-csrf'}
        return 'Native recovery received', 200

    @app.get('/delta/fallback')
    def fallback():
        return _minimal(error_view(BadRequest(description=request.args.get('detail', '')))), 400

    server = make_server('127.0.0.1', 0, app, threaded=False)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('width,coarse', [(1440, False), (1440, True), (390, False), (390, True)])
@pytest.mark.parametrize('javascript', [True, False])
def test_login_and_all_error_frames_use_native_text_actions(
    delta_site, browser, width, coarse, javascript,  # noqa: F811
):
    routes = [('/eh/login?notice=auth.required&methods=both', '.auth-submit'),
              ('/eh/admin?session_user=1', '.eh-action'),
              ('/eh/session', '.eh-action'), ('/eh/minimal', '.eh-action'),
              ('/eh/legacy', '.eh-action'), ('/delta/post', '.eh-action')]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with browser.new_context(base_url=delta_site, viewport={'width': width, 'height': 900},
                             has_touch=coarse, java_script_enabled=javascript) as context:
        page = context.new_page()
        posts, errors, visible = [], [], []
        page.on('request', lambda r: posts.append(r) if r.method == 'POST' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        for index, (route, selector) in enumerate(routes):
            assert page.goto(route).status == 200
            page.evaluate('document.fonts.ready')
            controls = page.locator(selector)
            values = [control.evaluate(VISIBILITY) for control in controls.all()]
            phase = 'before' if any(v['icons'] for v in values) else 'after'
            page.screenshot(path=str(EVIDENCE / (
                f'{phase}-{index}-{width}-{"coarse" if coarse else "fine"}-js{javascript}.png')))
            assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
            visible.extend(values)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            for control in controls.all():
                control.focus()
                expect(control).to_be_focused()
                assert control.evaluate('e => e.getBoundingClientRect().height') >= 44
            for primary in page.locator('.eh-action-primary, .auth-submit').all():
                colors = primary.evaluate('''e => {
                    const probe = document.createElement('div');
                    probe.style.backgroundColor = 'var(--sh-magenta)';
                    document.body.appendChild(probe);
                    const expected = getComputedStyle(probe).backgroundColor;
                    probe.remove();
                    const style = getComputedStyle(e);
                    return {actual: style.backgroundColor, expected,
                            focused: e.matches(':focus'), hovered: e.matches(':hover'),
                            transition: style.transition};
                }''')
                assert colors['actual'] == colors['expected'], colors
        assert not posts and not errors
        assert all(v['text'] and not v['icons'] for v in visible), visible
        page.goto('/eh/login?return_token=opaque-token')
        form = page.locator('.auth-form')
        assert form.get_attribute('method') == 'post'
        assert form.get_attribute('action') == '/auth/local_login'
        assert form.evaluate('f => [...new FormData(f)]') == [
            ['csrf_token', 'test-csrf'], ['return_token', 'opaque-token'],
            ['username', ''], ['password', '']]
        page.locator('#username').focus()
        page.keyboard.press('Tab')
        expect(page.locator('#password')).to_be_focused()
        page.keyboard.press('Tab')
        expect(page.locator('.auth-submit')).to_be_focused()
        page.goto('/eh/session')
        page.locator('.eh-action').focus()
        with page.expect_navigation():
            page.keyboard.press('Enter')
        expect(page).to_have_url(delta_site + '/eh/login')
        page.goto('/delta/post')
        action = page.locator('.eh-action')
        action.focus()
        with page.expect_navigation():
            page.keyboard.press('Enter')
        expect(page.locator('body')).to_have_text('Native recovery received')
        assert len(posts) == 1 and posts[0].post_data == '_csrf=test-csrf'


@pytest.mark.parametrize('detail', ['', '   ', 'Wert A&B - 0 <script>'])
def test_optional_fallback_detail_has_no_empty_wrapper(delta_site, browser, detail):  # noqa: F811
    from urllib.parse import urlencode
    with browser.new_context(base_url=delta_site, java_script_enabled=False) as context:
        page = context.new_page()
        assert page.goto('/delta/fallback?' + urlencode({'detail': detail})).status == 400
        paragraphs = page.locator('main p').all_text_contents()
        assert all(value.strip() for value in paragraphs), paragraphs
        assert len(paragraphs) == (3 if detail.strip() else 2)
        if detail.strip():
            assert paragraphs[1] == detail
        expect(page.locator('script')).to_have_count(0)
        expect(page.locator('main a')).to_have_text(['Zur Übersicht'])


def test_public_outage_cannot_duplicate_overview_recovery(auth_app):  # noqa: F811
    """R-69 is unreachable: safe_return_target allows only enumerated admin reads."""
    app, _, _ = auth_app
    with app.test_request_context('/cafeteria/heute/'):
        view = error_view(ServiceUnavailable())
        assert [(a['semantic'], a['href'], a['method']) for a in view.recovery] == [
            ('navigation.overview', '/cafeteria/heute/', 'get')]
    with app.test_request_context('/admin/cafeteria?week=2026-09-28'):
        view = error_view(ServiceUnavailable())
        assert [(a['semantic'], a['href'], a['method']) for a in view.recovery] == [
            ('actions.reload', '/admin/cafeteria?week=2026-09-28', 'get'),
            ('navigation.overview', '/cafeteria/heute/', 'get')]
