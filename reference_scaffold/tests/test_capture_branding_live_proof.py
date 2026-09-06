"""Offline verifier regressions: real local HTTP/Chrome, no app DB or live login."""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qsl

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import capture_branding_live_proof as tool  # noqa: E402

STATIC = ROOT / 'reference_scaffold/cafeteria/static'
CSS = '''[hidden]{display:none!important} body{font:18px var(--sh-font)} h1{font-family:var(--sh-font-display)}
.food-symbol{height:1.5em;width:1.5em;object-fit:contain}.food-symbol--country{width:2em}
.small .food-symbol{height:1.2em;width:1.2em}.food-legend *{font-size:18px}
.patient-week-day{height:500px}.patient-week-option,.cafe-week-slot,.hero-food{width:300px;height:200px}
.patient-week-option.tall,.cafe-week-slot.tall{height:240px}
:root{--sh-primary:#8c1c4b;--sh-secondary:#35666f;--sh-panel:#ffffff;--sh-ink:#383027;
--sh-font:"Fira Sans",sans-serif;--sh-font-display:"Carlito",sans-serif}'''


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as engine:
        with engine.chromium.launch(executable_path='/opt/google/chrome/chrome', args=['--no-sandbox']) as instance:
            yield instance


@pytest.fixture
def fixture_page(browser):
    state = {'body': '', 'requests': []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            state['requests'].append(('GET', self.path))
            content, mime = b'', 'text/html'
            if self.path.startswith('/static/vendor/food-symbols/'):
                content = (STATIC / self.path.removeprefix('/static/')).read_bytes()
                mime = 'image/svg+xml'
            elif self.path == '/static/fixture.css':
                content, mime = CSS.encode(), 'text/css'
            elif self.path == '/static/rotate.js':
                content = b'setTimeout(()=>{const p=document.querySelectorAll("[data-signage-page]");p[0].hidden=true;p[1].hidden=false},500)'
                mime = 'application/javascript'
            else:
                content = ('<link rel="stylesheet" href="/static/fixture.css">' + state['body']).encode()
            self.send_response(200)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'")
            self.end_headers()
            self.wfile.write(content)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with browser.new_page() as page:
        def load(body):
            state['body'] = body
            response = page.goto(f'http://127.0.0.1:{server.server_port}/fixture')
            assert response.status == 200
            assert "script-src 'self'" in response.headers['content-security-policy']
            return page
        yield load
    server.shutdown()
    thread.join()
    server.server_close()


def declaration(text='Enthält: Milch', *, kind='amber', asset='allergens/milk.svg'):
    image = f'<img class="food-symbol{" food-symbol--country" if kind == "" else ""}" src="/static/vendor/food-symbols/{asset}">' if asset else ''
    return f'<span class="label {kind}">{image}<span>{text}</span></span>'


def menu(entries='', warning='', *, classes='patient-week-option'):
    if not entries and not warning:
        warning = tool.WARNINGS[0]
    return f'<article class="{classes}"><h3>Menü</h3><div data-menu-metadata>{entries}<p>{warning}</p></div></article>'


def legend(entries='', warning='', *, classes=''):
    note = f'<p>{warning}</p>' if warning else ''
    return f'<section class="food-legend {classes}"><h2>Legende</h2>{entries}{note}</section>'


@pytest.mark.parametrize('fault', ['missing', 'foreign', 'presence', 'small', 'duplicate', 'warning', 'hidden_page', None])
def test_legends_match_visible_declarations_and_loaded_symbol_size(fixture_page, tmp_path, fault):
    contains = declaration()
    may = declaration('Kann enthalten: Milch')
    origin = declaration('Kartoffel: CH', kind='', asset='flags/ch.svg')
    country = declaration('Schweiz', kind='', asset='flags/ch.svg')
    plant = declaration('Vegetarisch', kind='green', asset='')
    warnings = 'Allergenprüfung offen'
    entries = contains + may + country + plant
    if fault == 'foreign':
        entries += declaration('Enthält: Fisch', asset='allergens/fish.svg')
    if fault == 'presence':
        entries = entries.replace('Kann enthalten:', 'Enthält:')
    if fault == 'duplicate':
        entries += contains
    body = menu(contains + may + origin + plant, warnings)
    body += legend(entries, '' if fault == 'warning' else warnings, classes='small' if fault == 'small' else '') if fault != 'missing' else ''
    hidden = declaration('Enthält: Fisch', asset='allergens/fish.svg')
    body += '<section hidden>' + menu(hidden) + legend(hidden) + '</section>'
    if fault == 'hidden_page':
        body = body.replace(country + plant, country + plant + hidden, 1)
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    proof.legends(fixture_page(body), 'page', signage=True)
    assert proof.outcome() == (('browser_passed', 0) if fault is None else ('failed', 1)), proof.data['failures']


@pytest.mark.parametrize('warning', tool.WARNINGS)
def test_unknown_allergens_and_text_fallback_are_not_dropped(fixture_page, tmp_path, warning):
    fallback = declaration('Allergenangabe ungeklärt: Unbekannt', asset='')
    unknown_origin = declaration('Zutat: ZZ', kind='', asset='')
    body = menu(fallback + unknown_origin, warning) + legend(fallback + declaration('ZZ', kind='', asset=''), warning)
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    proof.legends(fixture_page(body), 'page')
    assert proof.outcome() == ('browser_passed', 0), proof.data['failures']


@pytest.mark.parametrize('count', [0, 1, 2, 3])
def test_missing_or_wrong_card_counts_are_fatal(fixture_page, tmp_path, count):
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    proof.menu_evidence(fixture_page(menu(classes='hero-food') * count), tool.SIGNAGE[0], 'page')
    assert proof.outcome() == (('browser_passed', 0) if count == 2 else ('failed', 1)), proof.data['failures']


@pytest.mark.parametrize('path,classes,count', [(tool.SIGNAGE[1], 'cafe-week-slot', 10),
                                               (tool.SIGNAGE[3], 'patient-week-option', 12)])
def test_equal_day_containers_do_not_hide_unequal_menu_cards(fixture_page, tmp_path, path, classes, count):
    body = '<div class="patient-week-day">' + menu(classes=classes) * (count - 1) + menu(classes=classes + ' tall') + '</div>'
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    proof.menu_evidence(fixture_page(body), path, 'page')
    assert 'page.equal_unclipped_cards' in proof.data['failures']


def test_sunday_closed_state_is_incomplete_not_broken_or_passed(fixture_page, tmp_path):
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    page = fixture_page('<h2>Cafeteria geschlossen</h2>')
    proof.menu_evidence(page, tool.PUBLIC[0], 'sunday')
    proof.legends(page, 'sunday')
    assert proof.outcome() == ('incomplete', 2)
    assert proof.data['checks']['sunday.menu_count']
    assert proof.data['unavailable'] == ['sunday.closed_services_limit_full_menu_proof']


@pytest.mark.parametrize('pages', [0, 1])
def test_absent_patient_page_is_fatal_without_waiting(fixture_page, tmp_path, pages):
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    proof.patient_rotation(fixture_page('<section data-signage-page></section>' * pages), 'week')
    assert proof.outcome() == ('failed', 1)


def test_rotation_checks_all_28_real_menu_cards_and_page_specific_legends(fixture_page, tmp_path):
    first, second = declaration(), declaration('Enthält: Fisch', asset='allergens/fish.svg')
    body = '<section data-signage-page>' + menu(first) * 12 + legend(first) + '</section>'
    body += '<section data-signage-page hidden>' + menu(second) * 16 + legend(second) + '</section>'
    body += '<script src="/static/rotate.js"></script>'
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    page = fixture_page(body)
    proof.menu_evidence(page, tool.SIGNAGE[3], 'week')
    proof.legends(page, 'week', signage=True)
    proof.patient_rotation(page, 'week')
    assert proof.outcome() == ('browser_passed', 0), proof.data['failures']
    assert proof.data['observations']['week.visible_card_count'] == 12
    assert proof.data['observations']['week-page2.visible_card_count'] == 16
    assert (tmp_path / 'week-page2.png').is_file()


@pytest.mark.parametrize('fault', [None, 'primary', 'font_body'])
def test_applied_brand_tokens_are_checked_not_only_stylesheet_urls(fixture_page, tmp_path, fault):
    values = dict(primary='#8c1c4b', accent='#35666f', surface='#ffffff', text='#383027',
                  font_body='fira', font_heading='carlito')
    if fault:
        values[fault] = '#35666f' if fault == 'primary' else 'carlito'
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    proof.brand_values(fixture_page('<h1>Marke</h1>'), 'page', values)
    assert proof.outcome() == (('browser_passed', 0) if fault is None else ('failed', 1))


def test_active_revision_is_read_separately_from_newest_draft(tmp_path, monkeypatch):
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    proof.active_css, proof.active_logo = '/branding/revisions/1.css', '/static/img/suedhang-logo.png'
    page = MagicMock()
    visits = []
    active = dict(primary='#8c1c4b', accent='#35666f', surface='#ffffff', text='#383027',
                  font_body='fira', font_heading='carlito', **{'logo-select': ''})
    draft = dict(active, primary='#35666f', **{'logo-select': 'a' * 64})

    def capture(_page, path, _name):
        visits.append(path)

    def locator(selector, **kwargs):
        node = MagicMock()
        node.count.return_value = 1
        node.filter.return_value.count.return_value = 1
        node.filter.return_value.get_attribute.return_value = tool.EDITOR + '?revision=1'
        node.content_frame.locator.return_value.inner_text.return_value = 'Frisch zubereitet'
        node.content_frame.locator.return_value.evaluate.return_value = True
        if selector.startswith('#brand-'):
            node.input_value.side_effect = lambda: (active if visits[-1].endswith('?revision=1') else draft)[selector[7:]]
        return node

    page.locator.side_effect = locator
    monkeypatch.setattr(proof, 'capture', capture)
    checked_values = []
    monkeypatch.setattr(proof, 'brand_values', lambda _page, _name, values: checked_values.append(dict(values)))
    proof.editor(page, 390)
    assert visits == [tool.EDITOR, tool.EDITOR + '?revision=1']
    assert checked_values[0]['primary'] == active['primary']
    assert proof.data['checks']['admin-390.active_logo_identity']
    assert proof.outcome() == ('browser_passed', 0)


@pytest.mark.parametrize('method,path,allowed', [('GET', '/branding/revisions/1.css', True),
                                               ('GET', '/admin/design/marke?revision=1', True),
                                               ('POST', '/admin/design/marke', False),
                                               ('DELETE', '/branding/logo.png', False)])
def test_guard_retains_read_only_request_scope(tmp_path, method, path, allowed):
    proof = tool.BrandingProof('https://fixture.invalid', tmp_path)
    route = MagicMock()
    route.request.method, route.request.url = method, 'https://fixture.invalid' + path
    proof.guard(route)
    assert route.continue_.called is allowed
    assert route.abort.called is not allowed


@pytest.mark.parametrize('condition,exit_code', [('missing', 2), ('failed', 1), ('exception', 1)])
def test_cli_fails_honestly_and_never_serializes_exception_secrets(tmp_path, monkeypatch, capsys, condition, exit_code):
    target = tmp_path / 'artifacts'
    monkeypatch.setattr(sys, 'argv', ['proof', '--base-url', 'https://dishboard.joelduss.xyz', '--outdir', str(target)])
    monkeypatch.setattr(tool, 'sync_playwright', MagicMock())
    monkeypatch.setattr(tool.BrandingProof, 'configure', lambda *_: MagicMock())
    monkeypatch.setattr(tool.BrandingProof, 'login', lambda *_: None)
    monkeypatch.setattr(tool.BrandingProof, 'capture', lambda *_a, **_kw: None)
    monkeypatch.setattr(tool.BrandingProof, 'patient_rotation', lambda *_: None)

    def editor(proof, *_):
        if condition == 'exception':
            raise RuntimeError('synthetic-secret-never-report')
        proof.assets.update(('public.css', 'preview.css'))
        if condition == 'missing':
            proof.data['unavailable'].append('missing_published_data')
        else:
            proof.check('wrong_menu_count', False)
    monkeypatch.setattr(tool.BrandingProof, 'editor', editor)
    assert tool.main() == exit_code
    report = target / 'proof.json'
    data = json.loads(report.read_text())
    assert data['status'] == ('incomplete' if exit_code == 2 else 'failed')
    assert 'synthetic-secret' not in report.read_text() + capsys.readouterr().out
    assert report.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('origin', [
    'https://fixture.invalid', 'http://dishboard.joelduss.xyz',
    'https://dishboard.joelduss.xyz/', 'https://dishboard.joelduss.xyz:443',
])
def test_cli_rejects_other_origins_before_credentials_or_browser(tmp_path, monkeypatch, origin):
    target = tmp_path / 'artifacts'
    monkeypatch.setattr(sys, 'argv', ['proof', '--base-url', origin, '--outdir', str(target)])
    password = MagicMock(side_effect=AssertionError('credential access forbidden'))
    playwright = MagicMock(side_effect=AssertionError('browser and network access forbidden'))
    monkeypatch.setattr(tool, '_password', password)
    monkeypatch.setattr(tool, 'sync_playwright', playwright)
    with pytest.raises(SystemExit) as error:
        tool.main()
    assert error.value.code == 2
    password.assert_not_called()
    playwright.assert_not_called()
    assert not target.exists()


@pytest.mark.parametrize('arguments', [[], ['--base-url', 'https://dishboard.joelduss.xyz']])
def test_cli_uses_fixed_origin_and_real_chrome(tmp_path, monkeypatch, arguments):
    target = tmp_path / 'artifacts'
    monkeypatch.setattr(sys, 'argv', ['proof', *arguments, '--outdir', str(target)])
    playwright = MagicMock()
    launch = playwright.return_value.__enter__.return_value.chromium.launch
    launch.side_effect = RuntimeError('offline stop before browser creation')
    password = MagicMock(side_effect=AssertionError('credential access forbidden'))
    monkeypatch.setattr(tool, 'sync_playwright', playwright)
    monkeypatch.setattr(tool, '_password', password)
    assert tool.main() == 1
    launch.assert_called_once_with(executable_path='/opt/google/chrome/chrome',
                                   args=['--no-sandbox', '--disable-dev-shm-usage'])
    password.assert_not_called()
    data = json.loads((target / 'proof.json').read_text())
    assert data['base_url'] == 'https://dishboard.joelduss.xyz'
    assert data['failures'] == ['login.RuntimeError']


def test_real_local_login_preserves_form_pairs_and_session_state(browser, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, 'USER', 'fixture-user')
    monkeypatch.setattr(tool, '_password', lambda: 'fixture-value')
    requests, posted = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append(('GET', self.path))
            body = '''<meta charset="utf-8"><link rel="icon" href="/static/fixture-icon.svg">
              <form method="post" action="/auth/local">
                <input type="hidden" name="csrf_token" value="fixture-csrf">
                <input name="username"><input type="password" name="password">
                <input type="hidden" name="note" value="Grüsse + &amp; Leerzeichen">
                <input type="hidden" name="note" value="zweiter Wert">
                <input type="hidden" name="empty" value="">
                <input disabled name="ignored" value="unused">
              </form>'''
            if self.path.startswith('/static/'):
                body = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml' if self.path.startswith('/static/')
                             else 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body.encode())

        def do_POST(self):
            requests.append(('POST', self.path))
            posted.append({
                'pairs': parse_qsl(self.rfile.read(int(self.headers['Content-Length'])).decode(),
                                   keep_blank_values=True),
                'content_type': self.headers['Content-Type'],
                'origin': self.headers['Origin'], 'referer': self.headers['Referer'],
            })
            self.send_response(302)
            self.send_header('Location', '/admin/cafeteria')
            self.send_header('Set-Cookie', 'fixture_login=present; Path=/; HttpOnly; SameSite=Lax')
            self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    proof = tool.BrandingProof(base, tmp_path)
    try:
        with browser.new_context(service_workers='block') as context:
            proof.login(context, proof.configure(context))
            state = context.storage_state()
        assert any(cookie['name'] == 'fixture_login' and cookie['value'] == 'present'
                   and cookie['httpOnly'] for cookie in state['cookies'])
        assert proof.data['checks']['login.only_official_post']
        assert not proof.blocked
        assert posted == [{'pairs': [('csrf_token', 'fixture-csrf'), ('username', 'fixture-user'),
                                    ('password', 'fixture-value'), ('note', 'Grüsse + & Leerzeichen'),
                                    ('note', 'zweiter Wert'), ('empty', '')],
                           'content_type': 'application/x-www-form-urlencoded',
                           'origin': base, 'referer': base + '/auth/local'}]
        assert ('GET', '/admin/cafeteria') not in requests  # Redirects remain disabled.
        assert '/auth/local' in tool.AUX
        with browser.new_context(service_workers='block') as public:
            response = proof.configure(public).goto(base + '/auth/local', wait_until='networkidle')
            assert response.status == 200
        assert [request for request in requests if request[0] == 'POST'] == [('POST', '/auth/local')]
        assert requests.count(('GET', '/auth/local')) == 2
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
