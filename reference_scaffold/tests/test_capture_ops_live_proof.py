"""DB-free operator regressions: transport boundaries, private output and real DOM."""
from __future__ import annotations

import json
import stat
import sys
from datetime import date
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock

import pytest
from flask import Flask, redirect, request, send_from_directory
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
from werkzeug.serving import make_server

from cafeteria.operations_settings import default_schedule
from test_rendered_ui import browser  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import capture_ops_live_proof as tool  # noqa: E402

BASE = 'https://dishboard.example.invalid'


@pytest.mark.parametrize('fault', [None, '404', '204', '304', 'redirect', 'csp'])
@pytest.mark.parametrize(('asset', 'as_script', 'allowed'), [
    ('/static/menu-images.css', False, True),
    ('/branding/revisions/1.css', False, True),
    ('/branding/revisions/1.css', True, False),
    ('/branding/revisions/01.css', False, False),
    ('/branding/revisions/0.css', False, False),
    ('/branding/revisions/1.css?preview=1', False, False),
    ('/branding/revisions/1.css#fragment', False, False),
    ('/branding/other/1.css', False, False),
])
def test_capture_uses_real_browser_asset_responses(
        browser, tmp_path, monkeypatch, fault, asset, as_script, allowed):  # noqa: F811
    app = Flask(__name__, static_folder=None)
    styles = ['/static/tokens.css', '/static/vendor/tabler/tabler.min.css',
              '/static/admin-tabler.css', '/static/menu-images.css']
    if asset.startswith('/branding/') and not as_script:
        styles.append(asset)
    scripts = ['/static/vendor/tabler/tabler.min.js', '/static/admin.js']
    if as_script:
        scripts.append(asset)
    shell = ('<body class="dishboard-admin">'
             + ''.join(f'<link rel="stylesheet" href="{path}">' for path in styles)
             + ''.join(f'<script src="{path}"></script>' for path in scripts)
             + '<aside class="navbar navbar-vertical navbar-expand-xl">'
             '<button class="navbar-toggler" aria-label="Menü"></button>'
             '<nav aria-label="Backend"><a href="/admin/bereiche-zeiten" '
             'aria-current="page">Bereiche &amp; Zeiten</a></nav></aside></body>')
    ops_started = False
    api_gets = []

    @app.route('/auth/local', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            return redirect('/admin')
        return ('<form method="post"><input name="username">'
                '<input name="password" type="password"><button>Anmelden</button></form>')

    @app.route('/admin')
    @app.route(tool.OPS_PATH)
    def admin():
        nonlocal ops_started
        ops_started = request.path == tool.OPS_PATH
        policy = "script-src 'self'; style-src " + ("'none'" if ops_started and fault == 'csp' else "'self'")
        return shell, 200, {'Content-Security-Policy': policy}

    @app.route('/static/<path:filename>')
    @app.route('/branding/revisions/<path:filename>')
    def static_asset(filename):
        # Reproduce the transport distinction: API GETs fail, actual browser GETs work.
        if 'Chrome/' not in request.headers.get('User-Agent', ''):
            api_gets.append(request.path)
            return '', 503
        if ops_started and request.path == asset:
            if fault in {'404', '204', '304'}:
                return '', int(fault)
            if fault == 'redirect':
                return redirect('/static/tokens.css')
        if request.path.startswith('/branding/'):
            return 'body { --branding-proof: 1; }', 200, {'Content-Type': 'text/css'}
        return send_from_directory(ROOT / 'reference_scaffold/cafeteria/static', filename)

    observed = []
    original_audit = tool.audit_tabler

    def audit(page, base, statuses):
        observed.append(dict(statuses))
        return original_audit(page, base, statuses)

    monkeypatch.setattr(tool, 'audit_tabler', audit)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        proof = tool.Proof()
        tool.capture_viewport(browser, base, tmp_path, 'desktop', 'synthetic-password', proof)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert len(observed) == 1
    assert all(type(value) is bool for value in observed[0].values())
    assert observed[0][base + asset] is (fault is None and allowed)
    assert observed[0][base + scripts[0]] is True
    assert proof.checks['desktop.local_assets_http_200'] is (fault is None and allowed)
    assert 'desktop.capture_failed' not in proof.failures
    assert len(proof.pages) == 1
    assert api_gets == []  # The shared auditor received complete browser evidence.


@pytest.mark.parametrize(('method', 'path', 'allowed'), [
    ('GET', '/admin/bereiche-zeiten', True), ('HEAD', '/static/tokens.css', True),
    ('POST', '/auth/local', True), ('POST', '/admin/bereiche-zeiten', False),
    ('PUT', '/admin/bereiche-zeiten', False), ('PATCH', '/admin/bereiche-zeiten', False),
    ('DELETE', '/admin/bereiche-zeiten', False), ('POST', '/admin/import-preview', False),
    ('POST', '/auth/local?next=/admin', False),
])
def test_guard_allows_only_reads_and_exact_single_login(method, path, allowed):
    proof = tool.Proof()
    guard = tool.ReadGuard(BASE, proof, 'mobile')
    route = MagicMock()
    route.request.method, route.request.url = method, BASE + path
    guard(route)
    assert route.continue_.called is allowed
    assert route.abort.called is not allowed
    if method == 'POST' and allowed:
        route.reset_mock()
        guard(route)
        route.abort.assert_called_once()
        route.continue_.assert_not_called()
    assert BASE not in json.dumps(proof.failures)


@pytest.mark.parametrize('method', ['GET', 'HEAD', 'POST'])
def test_guard_blocks_other_origins_without_recording_request_data(method):
    proof = tool.Proof()
    route = MagicMock()
    route.request.method = method
    route.request.url = 'https://other.example.invalid/auth/local?token=sensitive-test-marker'
    tool.ReadGuard(BASE, proof, 'desktop')(route)
    route.abort.assert_called_once()
    route.continue_.assert_not_called()
    assert proof.failures == ['desktop.request_blocked']


@pytest.mark.parametrize('fault', [None, 'http_error', 'lost_auth', 'exception', 'overflow', 'csp', 'asset'])
def test_capture_sanitizes_failures_and_never_screenshots_error_bodies(tmp_path, monkeypatch, fault):
    browser_mock = MagicMock()
    context = browser_mock.new_context.return_value.__enter__.return_value
    page = context.new_page.return_value
    response = MagicMock(status=200)
    response.header_value.return_value = "script-src 'self'" if fault != 'csp' else "script-src 'unsafe-inline'"

    def goto(url, **kwargs):
        page.url = url
        if url.endswith(tool.OPS_PATH):
            if fault == 'exception':
                raise RuntimeError('sensitive-test-marker token cookie body header')
            if fault == 'http_error':
                return MagicMock(status=503)
            if fault == 'lost_auth':
                page.url = BASE + '/auth/local'
        return response

    page.goto.side_effect = goto
    page.get_by_role.return_value.click.side_effect = lambda: setattr(page, 'url', BASE + '/admin/cafeteria')
    page.locator.return_value.count.return_value = 0
    page.evaluate.side_effect = lambda script: ({
        'overflow_px': 10 if fault == 'overflow' else 0,
        'inline_scripts': 0, 'inline_handlers': 0, 'inline_styles': 0,
    } if script == tool.LAYOUT_AUDIT else {'names': True, 'weekend_switch': True})
    page.screenshot.return_value = b'synthetic screenshot bytes'
    monkeypatch.setattr(tool, 'audit_tabler', lambda *_: {'local_assets_http_200': fault != 'asset'})
    proof = tool.Proof()
    tool.capture_viewport(browser_mock, BASE, tmp_path, 'mobile', 'synthetic-password', proof)
    assert 'sensitive-test-marker' not in json.dumps(tool.asdict(proof))
    page.content.assert_not_called()
    page.get_by_role.return_value.click.assert_called_once()  # Only login.
    context.route.assert_called_once()
    context.route_web_socket.assert_called_once()
    assert browser_mock.new_context.call_args.kwargs['service_workers'] == 'block'
    if fault in {'http_error', 'lost_auth', 'exception'}:
        page.screenshot.assert_not_called()
        assert not list(tmp_path.iterdir()) and not proof.pages and proof.failures
    else:
        assert len(proof.pages) == 1
        assert stat.S_IMODE((tmp_path / proof.pages[0]['screenshot']).stat().st_mode) == 0o600
        assert bool(proof.failures) is (fault is not None)


def test_main_writes_private_sanitized_failure_and_never_reuses_directory(tmp_path, monkeypatch, capsys):
    outdir = tmp_path / 'private-proof'
    monkeypatch.setattr(sys, 'argv', ['capture_ops_live_proof', '--outdir', str(outdir), '--base-url', BASE])
    monkeypatch.setenv('DEBUG', 'pw:api')
    monkeypatch.setenv('PWDEBUG', '1')

    def password():
        assert 'DEBUG' not in tool.os.environ and 'PWDEBUG' not in tool.os.environ
        raise RuntimeError('sensitive-test-marker password cookie token')

    monkeypatch.setattr(tool, '_password', password)
    assert tool.main() == 1
    evidence = outdir / 'proof.json'
    assert stat.S_IMODE(outdir.stat().st_mode) == 0o700
    assert stat.S_IMODE(evidence.stat().st_mode) == 0o600
    raw = evidence.read_text()
    assert 'sensitive-test-marker' not in raw + capsys.readouterr().out
    assert json.loads(raw)['failures'] == ['runner.failed', 'both_viewports_captured']
    assert tool.main() == 1
    assert evidence.read_text() == raw


@pytest.mark.parametrize('base', ['https://user:password@example.invalid', 'https://example.invalid/path',
                                 'https://example.invalid?token=secret', 'file:///tmp/local'])
def test_invalid_origins_fail_before_credentials_or_browser(tmp_path, monkeypatch, capsys, base):
    monkeypatch.setattr(sys, 'argv', ['capture_ops_live_proof', '--outdir', str(tmp_path / 'proof'), '--base-url', base])
    password = MagicMock()
    monkeypatch.setattr(tool, '_password', password)
    assert tool.main() == 1
    password.assert_not_called()
    assert base not in capsys.readouterr().out


@pytest.mark.parametrize('width', [390, 1440])
def test_ops_dom_audit_on_actual_operations_template_without_network(browser, width):  # noqa: F811
    # Only the shell/macros are replaced; OPS forms are the real production template.
    env = Environment(loader=ChoiceLoader([
        DictLoader({
            'admin/base_tabler.html': '{% block content %}{% endblock %}',
            'admin/_macros.html': '{% macro icon(name) %}{% endmacro %}'
                                 '{% macro page_header(a,b) %}{% endmacro %}'
                                 '{% macro flash_region(a) %}{% endmacro %}',
        }), FileSystemLoader(ROOT / 'reference_scaffold/cafeteria/templates'),
    ]), autoescape=True)
    html = env.get_template('admin/operations.html').render(
        url_for=lambda *_args, **_kwargs: tool.OPS_PATH, get_flashed_messages=lambda: [],
        errors={}, values={}, preview=False, exceptions=[], timezone='Europe/Zurich',
        today=date(2026, 9, 7), csrf='synthetic', schedule_csrf={'patient': 'synthetic', 'staff_guest': 'synthetic'},
        area_names={'patient': 'Stationen', 'staff_guest': 'Restaurant'},
        schedules={profile: default_schedule(profile) for profile in ('patient', 'staff_guest')},
        day_names=('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'),
        meal_labels={'LUNCH': 'Mittag', 'DINNER': 'Abend'}, state_labels={'open': 'Offen', 'closed': 'Geschlossen'},
    )
    with browser.new_context(viewport={'width': width, 'height': 844}) as context:
        page = context.new_page()
        page.set_content(f'<a href="{tool.OPS_PATH}" aria-current="page">Bereiche & Zeiten</a>' + html)
        assert all(page.evaluate(tool.OPS_AUDIT).values())
        page.locator('#patient-slot_7_DINNER_end').evaluate("element => element.type = 'text'")
        audit = page.evaluate(tool.OPS_AUDIT)
        assert audit['patient_native_times'] is False
        assert audit['staff_guest_native_times'] is True
        page.locator('#weekend-form').evaluate('element => element.remove()')
        assert page.evaluate(tool.OPS_AUDIT)['weekend_switch'] is False
