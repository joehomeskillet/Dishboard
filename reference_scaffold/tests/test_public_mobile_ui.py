from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page
from werkzeug.serving import make_server

import cafeteria
from cafeteria.admin import display_routes, menu_collection_routes, week_management_routes  # noqa: F401

from test_rendered_ui import app as app
from test_rendered_ui import browser as browser

ROUTES = [
    '/cafeteria/heute/',
    '/cafeteria/wochenangebot/',
    '/patienten/heute/',
    '/patienten/wochenplan/',
]


@pytest.fixture
def http_app(app: Flask, monkeypatch: pytest.MonkeyPatch) -> Flask:
    # Keep the real factory, routes, filters and CSP; only storage uses demo snapshots.
    monkeypatch.setattr(cafeteria, 'Config', lambda: SimpleNamespace(**app.config))
    monkeypatch.setattr(
        cafeteria, 'init_app_database',
        lambda application: application.extensions.update(cafeteria_db=object()),
    )
    return cafeteria.create_app()


@pytest.fixture
def public_server(http_app: Flask) -> Iterator[str]:
    server = make_server('127.0.0.1', 0, http_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _assert_layout(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), page.evaluate(
        """() => [...document.querySelectorAll('body *')]
            .filter(element => element.getBoundingClientRect().right > innerWidth + 1)
            .slice(0, 8).map(element => [element.tagName, element.className, element.scrollWidth])"""
    )
    assert page.evaluate("""() => [...document.querySelectorAll('.card, .page-title, .card-title')]
        .every(element => element.scrollWidth <= element.clientWidth + 1)""")
    assert page.locator('h1').count() == 1
    assert page.locator('main#main-content').count() == 1
    assert page.locator('script, [style], [onclick]').count() == 0
    for link in page.locator('a').all():
        if link.is_visible():
            box = link.bounding_box()
            assert box is not None and box['height'] >= 48, link.inner_text()
    assert page.locator('body').evaluate(
        "element => parseFloat(getComputedStyle(element).fontSize) >= 16"
    )


@pytest.mark.parametrize('path', ROUTES)
@pytest.mark.parametrize('width,height', [(390, 844), (1440, 1100)])
def test_public_mobile_ui_requirements(
    http_app: Flask, public_server: str, browser: Browser,
    path: str, width: int, height: int, tmp_path: Path,
) -> None:
    page = browser.new_page(viewport={'width': width, 'height': height})
    failures: list[str] = []
    page.on('requestfailed', lambda request: failures.append(request.url))
    page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
    page.on('pageerror', lambda error: failures.append(str(error)))
    page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
    try:
        response = page.goto(f'{public_server}{path}', wait_until='networkidle')
        assert response is not None and response.status == 200
        assert 'set-cookie' not in response.headers
        assert "style-src 'self'" in response.headers['content-security-policy']
        assert "script-src 'self'" in response.headers['content-security-policy']
        profile = 'patient' if 'patienten' in path else 'staff_guest'
        snapshot = http_app.config['TEST_SNAPSHOTS'][profile]
        assert response.headers['x-snapshot-revision'] == snapshot['revision_id']
        assert snapshot['revision_id'][:8] not in page.locator('body').inner_text()
        if profile == 'patient':
            assert re.search(r'preis|chf|rappen|kosten|price|intern|extern|money|currency', page.content(), re.I) is None
        else:
            assert 'CHF' in page.locator('body').inner_text()
        _assert_layout(page)
        stylesheets = page.evaluate('Array.from(document.styleSheets, sheet => sheet.href)')
        for filename in ('tokens.css', 'vendor/tabler/tabler.min.css', 'menu-images.css', 'public.css'):
            assert f'{public_server}/static/{filename}' in stylesheets
        assert all(not href.endswith('/app.css') for href in stylesheets)
        assert page.locator('.card-img-top .menu-photo img').count() > 0
        assert page.locator('.site-logo-img').evaluate('image => image.complete && image.naturalWidth > 0')
        assert page.locator('.card-status-top').first.evaluate("""element => {
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            context.fillStyle = getComputedStyle(element).backgroundColor;
            context.fillRect(0, 0, 1, 1);
            return [...context.getImageData(0, 0, 1, 1).data];
        }""") == [140, 28, 75, 255]
        page.screenshot(path=str(tmp_path / f'{path.strip("/").replace("/", "-")}-{width}.png'))
        if 'woche' in path:
            days = [day for day in snapshot['days'] if day['services']]
            nav_links = page.locator('.nav-pills.week-nav .nav-link')
            assert nav_links.count() == len(days)
            assert page.locator('.week-nav .active[aria-current="date"]').count() == 1
            assert page.locator('[role="tablist"]').count() == 0
            for index, day in enumerate(days):
                assert nav_links.nth(index).get_attribute('href') == f'#tag-{day["date"]}'
                assert day['weekday'] in nav_links.nth(index).get_attribute('aria-label')
                assert nav_links.nth(index).evaluate("""element => {
                    const [day, date] = [...element.children].map(child => child.getBoundingClientRect());
                    return day.bottom <= date.top && date.right <= element.getBoundingClientRect().right;
                }""")
            nav_links.last.click()
            assert page.url.endswith(f'#tag-{days[-1]["date"]}')
        page.keyboard.press('Control+Home')
        page.locator('.site-logo').focus()
        page.keyboard.press('Shift+Tab')
        page.keyboard.press('Shift+Tab')
        assert page.locator('a[href="#main-content"]').is_visible()
        assert page.locator('a[href="#main-content"]').evaluate(
            "element => getComputedStyle(element).outlineStyle !== 'none'"
        )
        page.keyboard.press('Enter')
        assert page.locator('main').evaluate('element => document.activeElement === element')
        assert failures == []
    finally:
        page.close()


@pytest.mark.parametrize('path', ROUTES)
def test_public_long_content_and_missing_photos_remain_readable(
    http_app: Flask, public_server: str, browser: Browser, path: str,
) -> None:
    profile = 'patient' if 'patienten' in path else 'staff_guest'
    for day in http_app.config['TEST_SNAPSHOTS'][profile]['days']:
        for meal in day['services']:
            for option in meal['options']:
                option['title'] = 'W' * 120
                option['components'] = ['W' * 360]
                option['description'] = 'W' * 360
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    try:
        page.goto(f'{public_server}{path}', wait_until='networkidle')
        _assert_layout(page)
        assert page.locator('.menu-photo').count() == 0
        assert 'Frisch aus unserer Küche' in page.locator('body').inner_text()
        assert 'W' * 120 in page.locator('body').inner_text()
        assert 'W' * 360 in page.locator('body').inner_text()
    finally:
        page.close()


@pytest.mark.parametrize('path', ['/cafeteria/wochenangebot/', '/patienten/wochenplan/'])
def test_week_navigation_marks_first_day_when_today_is_outside_snapshot(
    http_app: Flask, public_server: str, browser: Browser, path: str,
) -> None:
    http_app.config['DEMO_TODAY'] = '2026-09-07'
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    try:
        page.goto(f'{public_server}{path}', wait_until='networkidle')
        assert page.locator('.week-nav .active').count() == 1
        assert page.locator('.week-nav .active').get_attribute('aria-current') == 'location'
        assert page.locator('[aria-current="date"]').count() == 0
    finally:
        page.close()
