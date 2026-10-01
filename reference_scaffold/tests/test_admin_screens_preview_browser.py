"""Real same-origin screen previews under the application's production CSP."""
from __future__ import annotations

import re
import hashlib
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect
from sqlalchemy import Engine
from werkzeug.serving import make_server

import cafeteria
from cafeteria.public import routes as public_routes
from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_rendered_ui import browser, cafeteria_snapshot, patient_snapshot  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/card-visuals-0913'
TARGETS = {
    '/cafeteria/heute/', '/cafeteria/wochenangebot/',
    '/patienten/heute/', '/patienten/wochenplan/',
    '/cafeteria/wochenangebot/ohne-bilder/', '/patienten/wochenplan/ohne-bilder/',
    '/signage/cafeteria/tag', '/signage/cafeteria/woche',
    '/signage/patienten/tag', '/signage/patienten/woche',
}


def _capture_card_visuals(page, name: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    sources = {name: hashlib.sha256((root / 'reference_scaffold/cafeteria/templates/admin' / name).read_bytes()).hexdigest()
               for name in ('screens.html', '_week_menu_card.html', 'cafeteria.html')}
    folder = EVIDENCE / hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()[:12]
    folder.mkdir(parents=True, exist_ok=True)
    page.evaluate('document.fonts.ready')
    page.screenshot(path=str(folder / f'{name}.png'), full_page=True)
    (folder / f'{name}.json').write_text(json.dumps({
        'sources': sources, 'viewport': page.viewport_size, 'path': urlsplit(page.url).path,
        'browser': page.context.browser.version,
        'geometry': page.evaluate('''() => ({innerWidth, innerHeight, devicePixelRatio,
            pageWidth: document.documentElement.scrollWidth,
            pageHeight: document.documentElement.scrollHeight,
            cards: [...document.querySelectorAll('.menu-slot')].map(el => ({
                width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height})),
            previews: [...document.querySelectorAll('.screen-preview-signage')].map(el => ({
                width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height})),
            photos: [...document.querySelectorAll('[data-menu-image] img')].map(el => ({
                width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height,
                complete: el.complete, naturalWidth: el.naturalWidth}))})'''),
    }, indent=2))
    if page.locator('.admin-day-card').count():
        page.locator('.admin-day-card').first.screenshot(path=str(folder / f'{name}-first-day.png'))
    return folder


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844), (320, 844)])
@pytest.mark.parametrize('javascript', [True, False])
def test_screen_read_pages_are_visible_and_native(
    screen_app, screen_server, database_engine, browser, width, height, javascript, tmp_path,  # noqa: F811
) -> None:
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(screen_app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(base_url=screen_server, viewport={'width': width, 'height': height},
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': screen_server}])
        page = context.new_page()
        assert page.goto('/admin/screens').status == 200
        page.screenshot(path=str(tmp_path / f'screens-{width}-{javascript}-closed.png'), full_page=True)
        expect(page.locator('main details')).to_have_count(0)
        expect(page.locator('main details, main iframe')).to_have_count(0)
        targets = page.locator('.screen-card a[href^="/signage/"]').evaluate_all(
            'links => links.map(link => link.getAttribute("href"))')
        assert len(targets) == 4
        for target in targets:
            link = page.locator(f'.screen-card a[href="{target}"]')
            link.focus()
            expect(link).to_be_focused()
            with page.expect_navigation() as navigation:
                link.press('Enter')
            assert navigation.value.status == 200 and navigation.value.request.method == 'GET'
            expect(page.locator('main')).to_be_visible()
            assert page.locator('main').inner_text().strip()
            page.screenshot(path=str(tmp_path / f'screen-{target.rsplit("/", 2)[-2]}-{target.rsplit("/", 1)[-1]}-{width}-js{javascript}.png'))
            page.goto('/admin/screens')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        link = page.get_by_role('link', name='Mitarbeitende und externe Gäste Bildschirm Tagesplan öffnen', exact=True)
        # Alt: icon-only, empty text, 36px. Neu: visible destination, still a 36px semantic control.
        expect(link).to_contain_text('Tagesplan')
        classes = link.get_attribute('class') or ''
        minimum = 36 if 'ui-sem-control' in classes else 48
        assert link.bounding_box()['height'] >= minimum
        link.focus()
        expect(link).to_be_focused()
        page.keyboard.press('Enter')
        expect(page).to_have_url(screen_server + '/signage/cafeteria/tag')
        expect(page.locator('main')).to_be_visible()


@pytest.fixture
def screen_app(database_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Flask:  # noqa: F811
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    application = cafeteria.create_app()
    application.config.update(
        TESTING=True, SECRET_KEY='screen-preview-test', LAST_GOOD_DIR=str(tmp_path),
        DEMO_TODAY='2026-09-02', FRAME_ANCESTORS="'self'",
    )
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    snapshots = {'staff_guest': cafeteria_snapshot(), 'patient': patient_snapshot()}
    monkeypatch.setattr(public_routes, 'active_snapshot', lambda _db, profile, *a, **kw: snapshots[profile])
    return application


@pytest.fixture
def screen_server(screen_app: Flask) -> Iterator[str]:
    server = make_server('127.0.0.1', 0, screen_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('width,height', [(320, 844), (390, 844), (768, 1024), (1024, 768), (1440, 900)])
def test_real_screen_links_open_all_targets_with_source_security_headers(
    screen_app: Flask, screen_server: str, database_engine: Engine, browser: Browser,  # noqa: F811
    width: int, height: int, tmp_path: Path,
) -> None:
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(screen_app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    with browser.new_context(base_url=screen_server, viewport={'width': width, 'height': height}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': screen_server}])
        page = context.new_page()
        failures: list[str] = []
        loaded: set[str] = set()
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)

        def record_response(response) -> None:
            path = urlsplit(response.url).path
            if path in TARGETS:
                assert response.status == 200, (path, response.status)
                assert response.headers['x-frame-options'] == 'SAMEORIGIN'
                assert "frame-ancestors 'self'" in response.headers['content-security-policy']
                assert not urlsplit(response.url).query
                loaded.add(path)

        page.on('response', record_response)
        response = page.goto('/admin/screens')
        assert response is not None and response.status == 200
        assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
        page.screenshot(path=str(tmp_path / f'screens-initial-{width}.png'), full_page=True)
        expect(page.locator('main details')).to_have_count(0)
        expect(page.locator('.screen-card')).to_have_count(4)
        expect(page.locator('main iframe, .screen-browser-frame')).to_have_count(0)
        screen_links = page.locator('.screens-grid a')
        all_targets = set(screen_links.evaluate_all('links => links.map(link => new URL(link.href).pathname)'))
        assert all_targets == TARGETS | {
            '/admin/screens/cafeteria/wochenvorlage',
            '/admin/screens/patienten/wochenvorlage',
        }
        for target in sorted(TARGETS):
            page.goto('/admin/screens')
            link = page.locator(f'.screen-card a[href="{target}"]')
            link.focus()
            expect(link).to_be_focused()
            with page.expect_navigation() as navigation:
                link.press('Enter')
            assert navigation.value.request.method == 'GET'
            expect(page.locator('main')).to_be_visible()
            expect(page.locator('body')).to_contain_text('Menü')
            snapshot = patient_snapshot() if '/patienten/' in target else cafeteria_snapshot()
            menu = next(day for day in snapshot['days'] if day['date'] == '2026-09-02')
            expect(page.locator('body')).to_contain_text(menu['services'][0]['options'][0]['title'])
            if target.endswith('/ohne-bilder/') or target.startswith('/signage/'):
                expect(page.locator('.menu-photo, .card-img-top')).to_have_count(0)
            elif target in ('/cafeteria/wochenangebot/', '/patienten/wochenplan/'):
                assert page.locator('.menu-photo img').count() > 0
            if '/patienten/' in target:
                assert not re.search(r'preis|chf|rappen|kosten|price', page.content(), re.IGNORECASE)
            assert page.evaluate('innerWidth') == width
            assert page.locator('main').bounding_box()['width'] <= width + 1
            page.keyboard.press('Tab')
            assert page.evaluate('document.activeElement.tagName') != 'IFRAME'
        page.goto('/admin/screens')
        assert loaded == TARGETS
        dimensions = page.locator('.screen-card').evaluate_all(
            'cards => cards.map(card => ({top: card.offsetTop, width: card.offsetWidth, height: card.offsetHeight}))',
        )
        assert max(item['width'] for item in dimensions) - min(item['width'] for item in dimensions) <= 1
        if width >= 768:
            for top in {item['top'] for item in dimensions}:
                row = [item for item in dimensions if item['top'] == top]
                assert max(item['height'] for item in row) - min(item['height'] for item in row) <= 1, row
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('main style, main [style]').count() == 0
        assert not failures
        page.get_by_role('heading', level=1).click()
        expect(page.locator('main details')).to_have_count(0)
        if (width, height) in ((390, 844), (1440, 900)):
            page.screenshot(path=str(tmp_path / f'admin-screens-{width}x{height}.png'), full_page=True)
        page.screenshot(path=str(tmp_path / f'screens-preview-{width}.png'), full_page=True)


def test_full_views_remain_available_without_javascript(
    screen_app: Flask, screen_server: str, database_engine: Engine, browser: Browser,  # noqa: F811
) -> None:
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(screen_app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    with browser.new_context(base_url=screen_server, java_script_enabled=False) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': screen_server}])
        page = context.new_page()
        page.goto('/admin/screens')
        expect(page.locator('.screen-card [data-semantic="actions.more"]')).to_have_count(0)
        expect(page.locator('main details')).to_have_count(0)
        for card in page.locator('.screen-card').all():
            expect(card.locator('.admin-row-actions a').first).to_be_visible()
            expect(card.locator('details, iframe')).to_have_count(0)
            for link in card.locator('a').all():
                link.focus()
                expect(link).to_be_focused()
        screen_links = page.locator('.screens-grid a')
        for link in screen_links.all():
            expect(link).to_be_visible()
        assert set(screen_links.evaluate_all('links => links.map(link => new URL(link.href).pathname)')) == TARGETS | {
            '/admin/screens/cafeteria/wochenvorlage', '/admin/screens/patienten/wochenvorlage',
        }
        page.get_by_role('link', name='Patientinnen und Patienten Web Wochenplan mit Bildern · Vorgabe öffnen', exact=True).click()
        expect(page).to_have_url(f'{screen_server}/patienten/wochenplan/')
        expect(page.locator('main')).to_contain_text('Patientinnen und Patienten · Wochenübersicht')
        page.goto('/admin/screens')
        expect(page.locator('.screen-card[aria-labelledby="patient-public-title"] .admin-row-actions')).to_be_visible()
        page.get_by_role('link', name='Patientinnen und Patienten Web Wochenplan ohne Bilder öffnen', exact=True).click()
        expect(page).to_have_url(f'{screen_server}/patienten/wochenplan/ohne-bilder/')
        expect(page.locator('.menu-photo, .card-img-top')).to_have_count(0)


def test_unpublished_screen_links_show_each_source_message(
    screen_app: Flask, screen_server: str, database_engine: Engine, browser: Browser,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(public_routes, 'active_snapshot', lambda *args, **kwargs: None)
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(screen_app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    with browser.new_context(base_url=screen_server) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': screen_server}])
        page = context.new_page()
        statuses: dict[str, int] = {}

        def record_status(response) -> None:
            path = urlsplit(response.url).path
            if path in TARGETS:
                statuses[path] = response.status

        page.on('response', record_status)
        page.goto('/admin/screens')
        for target in sorted(TARGETS):
            page.goto('/admin/screens')
            page.locator(f'.screen-card a[href="{target}"]').click()
            expect(page.locator('body')).to_contain_text(re.compile(r'nicht verfügbar|nicht angezeigt'))
        assert statuses == dict.fromkeys(TARGETS, 404)
