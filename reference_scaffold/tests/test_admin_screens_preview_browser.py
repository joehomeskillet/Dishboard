"""Real same-origin screen previews under the application's production CSP."""
from __future__ import annotations

import re
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
TARGETS = {
    '/cafeteria/heute/', '/cafeteria/wochenangebot/',
    '/patienten/heute/', '/patienten/wochenplan/',
    '/cafeteria/wochenangebot/ohne-bilder/', '/patienten/wochenplan/ohne-bilder/',
    '/signage/cafeteria/tag', '/signage/cafeteria/woche',
    '/signage/patienten/tag', '/signage/patienten/woche',
}


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


@pytest.mark.parametrize('width', [390, 820, 1440])
def test_real_screen_previews_switch_all_targets_without_frame_blocks(
    screen_app: Flask, screen_server: str, database_engine: Engine, browser: Browser,  # noqa: F811
    width: int, tmp_path: Path,
) -> None:
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie(screen_app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    with browser.new_context(base_url=screen_server, viewport={'width': width, 'height': 1100}) as context:
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
        expect(page.locator('.screen-card')).to_have_count(4)
        expect(page.locator('iframe')).to_have_count(10)
        assert set(page.locator('main a').evaluate_all('links => links.map(link => new URL(link.href).pathname)')) == TARGETS
        for card in page.locator('.screen-card').all():
            is_web = 'Web' in card.locator('h2').inner_text()
            periods = ('Tagesplan', 'Wochenplan', 'Wochenplan ohne Bilder') if is_web else (
                'Tagesplan', 'Wochenplan ohne Bilder',
            )
            expect(card.get_by_role('tab')).to_have_count(len(periods))
            for period in periods:
                tab = card.get_by_role('tab', name=period, exact=True)
                tab.click()
                expect(tab).to_have_attribute('aria-selected', 'true')
                panel = card.locator('.tab-pane.active')
                frame_element = panel.locator('iframe')
                expect(frame_element).to_be_visible()
                handle = frame_element.element_handle()
                assert handle is not None
                frame = handle.content_frame()
                assert frame is not None
                expect(frame.locator('main')).to_be_visible()
                expect(frame.locator('body')).to_contain_text('Menü')
                snapshot = patient_snapshot() if '/patienten/' in frame.url else cafeteria_snapshot()
                menu = next(day for day in snapshot['days'] if day['date'] == '2026-09-02')
                expect(frame.locator('body')).to_contain_text(menu['services'][0]['options'][0]['title'])
                if period == 'Wochenplan ohne Bilder':
                    expect(frame.locator('.menu-photo, .card-img-top')).to_have_count(0)
                elif period == 'Wochenplan' and is_web:
                    assert frame.locator('.menu-photo img').count() > 0
                if '/patienten/' in frame.url:
                    assert not re.search(r'preis|chf|rappen|kosten|price', frame.content(), re.IGNORECASE)
                viewport_width = frame.evaluate('innerWidth')
                assert viewport_width == (1920 if '/signage/' in frame.url else 390 if width < 768 else 1440)
                assert frame_element.get_attribute('loading') == 'lazy'
                assert frame_element.get_attribute('tabindex') == '-1'
                assert frame_element.evaluate('el => el.parentElement.inert')
                viewport_box = panel.locator('.screen-preview').bounding_box()
                frame_box = frame_element.bounding_box()
                assert viewport_box is not None and frame_box is not None
                assert frame_box['width'] <= viewport_box['width'] + 1
                assert frame_box['height'] <= viewport_box['height'] + 1
                tab.focus()
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.tagName') != 'IFRAME'
        assert loaded == TARGETS
        dimensions = page.locator('.screen-card').evaluate_all(
            'cards => cards.map(card => ({width: card.offsetWidth, height: card.offsetHeight}))',
        )
        for axis in ('width', 'height'):
            assert max(item[axis] for item in dimensions) - min(item[axis] for item in dimensions) <= 1
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('main style, main [style]').count() == 0
        assert not failures
        page.get_by_role('heading', level=1).click()
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
        for link in page.locator('main a').all():
            expect(link).to_be_visible()
        assert set(page.locator('main a').evaluate_all('links => links.map(link => new URL(link.href).pathname)')) == TARGETS
        page.get_by_role('link', name='Patienten Web Wochenplan öffnen', exact=True).click()
        expect(page).to_have_url(f'{screen_server}/patienten/wochenplan/')
        expect(page.locator('main')).to_contain_text('Patienten-Speiseplan')
        page.goto('/admin/screens')
        page.get_by_role('link', name='Patienten Web Wochenplan ohne Bilder öffnen', exact=True).click()
        expect(page).to_have_url(f'{screen_server}/patienten/wochenplan/ohne-bilder/')
        expect(page.locator('.menu-photo, .card-img-top')).to_have_count(0)


def test_unpublished_screens_show_the_source_message_in_each_preview(
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
        for card in page.locator('.screen-card').all():
            for tab in card.get_by_role('tab').all():
                tab.click()
                frame = card.locator('.tab-pane.active iframe').content_frame
                expect(frame.locator('body')).to_contain_text(re.compile(r'nicht verfügbar|nicht angezeigt'))
        assert statuses == dict.fromkeys(TARGETS, 404)
