"""EH-1b: exercise the real handlers, login links and failure frames together."""
# ruff: noqa: F811 -- shared fixtures imported for pytest injection.
import json
import re
import threading
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from wsgiref.simple_server import make_server

import pytest
from flask import abort, request
from playwright.sync_api import expect
from redis.exceptions import RedisError

from cafeteria.auth import routes
from test_auth_routes import auth_app, _csrf_payload, _provision  # noqa: F401
from test_bf_session_rights_browser import _business_snapshot
from test_rendered_ui import browser  # noqa: F401


EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/state/EH-1b-evidence/screenshots'


@pytest.fixture
def integrated_server(auth_app):
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    app.config['ENTRA_ENABLED'] = False

    @app.get('/eh-integration/failure/<int:status>')
    def failure(status):
        abort(status)

    @app.context_processor
    def forbid_failure_context():
        if request.path.startswith('/eh-integration/failure/'):
            raise AssertionError('Failure rendering must bypass context processors')
        return {}

    server = make_server('127.0.0.1', 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', app, owner
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('width,javascript', [(1440, True), (390, False)])
def test_real_login_denial_interruption_and_outage_frames(integrated_server, browser, width, javascript):
    origin, app, owner = integrated_server
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    proof = []
    with browser.new_context(base_url=origin, java_script_enabled=javascript,
                             viewport={'width': width, 'height': 900 if width == 1440 else 844}) as context:
        page = context.new_page()
        response = page.goto('/admin/patienten?week=2026-09-28')
        assert response.status == 200 and urlsplit(page.url).path == '/auth/local'
        redirects = []
        previous = response.request.redirected_from
        while previous:
            redirects.append(previous.response().status)
            previous = previous.redirected_from
        assert redirects == [302, 302]
        assert parse_qs(urlsplit(page.url).query).keys() == {'return_token'}
        expect(page.get_by_role('heading', level=1)).to_have_text('Anmeldung erforderlich')
        expect(page.locator('[data-eh-frame="auth"]')).to_be_visible()
        page.screenshot(path=str(EVIDENCE / f'login-{width}.png'), full_page=True)
        proof.append({'case': 'login', 'status': 200, 'redirects': redirects})
        page.get_by_label('Benutzername', exact=True).fill('local.editor')
        page.get_by_label('Passwort', exact=True).fill('Correct-Horse-2026!Battery')
        with page.expect_response(lambda r: r.request.method == 'POST') as login:
            page.get_by_role('button', name='Anmelden', exact=True).click()
        assert login.value.status == 303
        expect(page).to_have_url(origin + '/admin/patienten?week=2026-09-28')

        response = page.goto('/admin/api')
        assert response.status == 403 and 'location' not in response.headers
        expect(page.locator('[data-eh-frame="admin"][data-error-code="AUTH_FORBIDDEN"]')).to_be_visible()
        expect(page.get_by_role('heading', level=1)).to_have_text('Kein Zugriff')
        expect(page.locator('.dishboard-admin')).to_have_count(1)
        page.screenshot(path=str(EVIDENCE / f'forbidden-{width}.png'), full_page=True)
        proof.append({'case': 'forbidden', 'status': 403, 'frame': 'admin'})

        assert page.goto('/admin/patienten?week=2026-09-28').status == 200
        page.locator('details.admin-week-settings > summary').click()
        page.locator('input[name="title"]').fill('EH1B-PRIVATE-UNSAVED')
        form = page.locator('form').filter(has=page.locator('input[name="title"]'))
        before = _business_snapshot(owner)
        context.clear_cookies()
        posts = []
        page.on('request', lambda req: posts.append(req.url) if req.method == 'POST' else None)
        with page.expect_response(lambda r: r.request.method == 'POST') as denied:
            form.locator('button[type="submit"]').click()
        page.wait_for_load_state()
        assert denied.value.status == 401 and 'location' not in denied.value.headers
        expect(page.locator('[data-eh-frame="auth"][data-error-code="AUTH_REQUIRED"]')).to_be_visible()
        expect(page.locator('.eh-mutation')).to_contain_text('vor der Ausführung abgelehnt')
        assert 'EH1B-PRIVATE-UNSAVED' not in page.content()
        assert 'Eingaben werden nicht über die Anmeldung hinweg gesichert.' in page.locator('main').inner_text()
        assert _business_snapshot(owner) == before
        assert len(posts) == 1
        page.screenshot(path=str(EVIDENCE / f'post-interruption-{width}.png'), full_page=True)
        proof.append({'case': 'post-interruption', 'status': 401, 'frame': 'auth', 'posts': len(posts)})

        for status in (500, 503):
            response = page.goto(f'/eh-integration/failure/{status}')
            assert response.status == status
            assert response.headers['cache-control'] == 'no-store'
            assert "default-src 'self'" in response.headers['content-security-policy']
            expect(page.locator('[data-eh-frame="minimal"]')).to_be_visible()
            expect(page.locator('.eh-reference')).to_contain_text(response.headers['x-request-id'])
            assert page.locator('form, .dishboard-admin').count() == 0
            assert page.locator('html').get_attribute('lang') == app.config['UI_LOCALE']
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.screenshot(path=str(EVIDENCE / f'minimal-{status}-{width}.png'), full_page=True)
            proof.append({'case': f'outage-{status}', 'status': status, 'frame': 'minimal'})
    (EVIDENCE / f'http-{width}.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')


def test_rendered_organization_link_preserves_bound_return_flow(auth_app, monkeypatch):
    app, _, _ = auth_app
    app.config.update(ENTRA_ENABLED=True, ENTRA_CLIENT_ID='eh-client',
                      ENTRA_TENANT_ID='eh-tenant', ENTRA_CLIENT_SECRET='test-only')

    class Provider:
        def initiate_auth_code_flow(self, **_kwargs):
            return {'state': 'eh-link-state', 'auth_uri': 'https://login.microsoftonline.com/test'}

    monkeypatch.setattr(routes, '_client', Provider)
    client = app.test_client()
    redirect = client.get('/admin/patienten?week=2026-09-28')
    token = parse_qs(urlsplit(redirect.location).query)['return_token'][0]
    page = client.get(redirect.location, follow_redirects=True)
    link = unescape(re.search(r'<a href="([^"]+)" class="auth-org-link', page.text)[1])
    assert parse_qs(urlsplit(link).query) == {'method': ['entra'], 'return_token': [token]}
    started = client.get(link)
    assert started.status_code == 302 and started.location == 'https://login.microsoftonline.com/test'


@pytest.mark.parametrize('stage', ['open_session', 'save_session'])
def test_session_outage_uses_branded_isolated_renderer(auth_app, monkeypatch, stage):
    app, _, _ = auth_app
    app.config['UI_LOCALE'] = 'en'

    def unavailable(*_args, **_kwargs):
        raise RedisError('PRIVATE-SESSION-FAILURE')

    monkeypatch.setattr(app.session_interface.delegate, stage, unavailable)
    response = app.test_client().get('/auth/local')
    assert response.status_code == 503 and 'Location' not in response.headers
    assert 'data-eh-frame="minimal"' in response.text
    assert '<html lang="en">' in response.text
    assert '/static/errors.css' in response.text and '/static/img/suedhang-logo.png' in response.text
    assert response.headers['X-Request-ID'] in response.text
    assert 'PRIVATE-SESSION-FAILURE' not in response.text
