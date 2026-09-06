from __future__ import annotations

import re
import sys
from copy import deepcopy
from collections.abc import Iterator
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
from flask import Flask, request
from playwright.sync_api import Browser, Page, expect
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

pytest_plugins = ('test_rendered_ui',)

from demo_snapshots import cafeteria_snapshot  # noqa: E402
from cafeteria import create_app  # noqa: E402
from cafeteria.admin import display_routes  # noqa: E402, F401 - register before the shared app fixture

SIGNAGE_ROUTES = (
    '/signage/cafeteria/tag',
    '/signage/cafeteria/woche',
    '/signage/patienten/tag',
    '/signage/patienten/woche',
)

SIGNAGE_JS_PATH = ROOT / 'reference_scaffold' / 'cafeteria' / 'static' / 'signage.js'
REFRESH_PATTERN = re.compile(r'<meta\s+http-equiv="refresh"', re.I)
SCRIPT_PATTERN = re.compile(
    r'<script[^>]+src="[^"]*signage\.js"[^>]*defer[^>]*>\s*</script>',
    re.I,
)
QUERY_BUILD_PATTERN = re.compile(
    r'location\.(pathname|href)\s*\+|fetch\([^)]*\?|new\s+URL\([^)]*\?|\?\s*date=',
)


def _profile_for_path(path: str) -> str:
    return 'patient' if 'patienten' in path else 'staff_guest'


@pytest.fixture
def live_signage(app: Flask, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, Flask]]:
    # Run the real app factory and CSP; only snapshot storage and cadence are test doubles.
    monkeypatch.setattr('cafeteria.Config', lambda: SimpleNamespace(**app.config))
    monkeypatch.setattr('cafeteria.init_app_database', lambda real: real.extensions.update(app.extensions))
    real = create_app()

    @real.after_request
    def polling_interval(response):
        if request.path.startswith('/signage/'):
            response.set_data(response.get_data().replace(
                b'data-signage-interval="60000"', b'data-signage-interval="100"',
            ))
        return response

    server = make_server('127.0.0.1', 0, real, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', real
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture
def signage_page(browser: Browser) -> Iterator[Page]:
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce')
    try:
        yield page
    finally:
        page.close()


@pytest.mark.parametrize('path', SIGNAGE_ROUTES)
def test_signage_routes_use_engine_shell_without_meta_refresh(app: Flask, path: str) -> None:
    client = app.test_client()
    response = client.get(path)
    html = response.get_data(as_text=True)
    profile = _profile_for_path(path)
    revision = app.config['TEST_SNAPSHOTS'][profile]['revision_id']

    assert response.status_code == 200
    assert REFRESH_PATTERN.search(html) is None
    assert len(SCRIPT_PATTERN.findall(html)) == 1
    assert f'data-signage-revision="{revision}"' in html
    assert response.headers['X-Snapshot-Revision'] == revision

    head = client.head(path)
    assert head.status_code == 200
    assert head.headers['X-Snapshot-Revision'] == revision

    bad = client.get(f'{path}?date=2026-09-03')
    assert bad.status_code == 400


def test_signage_js_avoids_reload_eval_and_query_strings() -> None:
    source = SIGNAGE_JS_PATH.read_text(encoding='utf-8')
    assert 'eval(' not in source
    assert 'location.reload(' not in source
    assert QUERY_BUILD_PATTERN.search(source) is None


def test_signage_polling_swaps_content_without_navigation(
    live_signage: tuple[str, Flask],
    signage_page: Page,
) -> None:
    base_url, app = live_signage
    page = signage_page
    path = '/signage/cafeteria/tag'
    revision_b = 'CAF-2026-KW36-R2'
    marker_a = 'Kalbsbratwurst mit Zwiebelsauce'
    marker_b = 'Polling-Ziel-Gericht'
    navigations: list[str] = []
    requests: list[tuple[str, str]] = []
    errors: list[str] = []
    page.on('framenavigated', lambda frame: navigations.append(frame.url))
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda req: requests.append((req.method, req.url)) if '/signage/' in req.url else None)
    response = page.goto(f'{base_url}{path}')
    assert response and "script-src 'self'" in response.headers['content-security-policy']
    expect(page.locator('[data-signage-root]')).to_contain_text(marker_a)
    updated = app.config['TEST_SNAPSHOTS']['staff_guest']
    updated['revision_id'] = revision_b
    updated['days'][2]['services'][0]['options'][0]['title'] = marker_b
    expect(page.locator('html')).to_have_attribute('data-signage-revision', revision_b)
    expect(page.locator('[data-signage-root]')).to_contain_text(marker_b)
    expect(page.locator('[data-signage-root]')).not_to_contain_text(marker_a)
    assert navigations == [f'{base_url}{path}']
    assert len(requests) >= 2
    assert set(requests) == {('GET', f'{base_url}{path}')}
    assert errors == []


@pytest.mark.parametrize('failure', ('network', 503))
def test_signage_polling_keeps_content_when_offline(
    live_signage: tuple[str, Flask],
    signage_page: Page,
    failure: str | int,
) -> None:
    base_url, app = live_signage
    page = signage_page
    path = '/signage/cafeteria/tag'
    marker_a = 'Kalbsbratwurst mit Zwiebelsauce'
    page.goto(f'{base_url}{path}')
    page.route(f'{base_url}{path}', lambda route: route.abort() if failure == 'network' else route.fulfill(status=503))
    expect(page.locator('[data-signage-status]')).to_contain_text('offline')
    expect(page.locator('[data-signage-root]')).to_contain_text(marker_a)
    page.unroute(f'{base_url}{path}')
    app.config['TEST_SNAPSHOTS']['staff_guest']['revision_id'] = 'CAF-RECOVERED'
    expect(page.locator('html')).to_have_attribute('data-signage-revision', 'CAF-RECOVERED')
    expect(page.locator('[data-signage-status]')).not_to_contain_text('offline')
    # Verify new status nodes remain live after the DOM swap.
    page.route(f'{base_url}{path}', lambda route: route.abort())
    expect(page.locator('[data-signage-status]')).to_contain_text('offline')


@pytest.mark.parametrize('path', SIGNAGE_ROUTES)
@pytest.mark.parametrize('initially_missing', (False, True))
def test_signage_withdrawal_and_initial_404_recover(
    live_signage: tuple[str, Flask], signage_page: Page, path: str, initially_missing: bool,
) -> None:
    base_url, app = live_signage
    page = signage_page
    profile = _profile_for_path(path)
    snapshot = deepcopy(app.config['TEST_SNAPSHOTS'][profile])
    if initially_missing:
        app.config['TEST_SNAPSHOTS'][profile] = None
    response = page.goto(f'{base_url}{path}')
    assert response and response.status == (404 if initially_missing else 200)
    app.config['TEST_SNAPSHOTS'][profile] = None
    expect(page.locator('[data-signage-root]')).to_contain_text('nicht verfügbar')
    expect(page.locator('html')).to_have_attribute('data-signage-revision', '')
    app.config['TEST_SNAPSHOTS'][profile] = snapshot
    expect(page.locator('html')).to_have_attribute('data-signage-revision', snapshot['revision_id'])
    expect(page.locator('[data-signage-root]')).not_to_contain_text('nicht verfügbar')
    assert 'offline' not in page.locator('[data-signage-status]').inner_text()


@pytest.mark.parametrize('status', (200, 410, 403))
def test_signage_missing_revision_and_client_errors_remove_old_content(
    live_signage: tuple[str, Flask], signage_page: Page, status: int,
) -> None:
    base_url, app = live_signage
    page = signage_page
    url = f'{base_url}/signage/cafeteria/tag'
    page.goto(url)
    # An upstream client error can have a plain response rather than the app shell.
    page.route(url, lambda route: route.fulfill(status=status, body='Unavailable', content_type='text/html'))
    expect(page.locator('[data-signage-root]')).to_contain_text('nicht verfügbar')
    expect(page.locator('html')).to_have_attribute('data-signage-revision', '')
    expect(page.locator('[data-signage-root]')).not_to_contain_text('Kalbsbratwurst')
    page.unroute(url)
    expect(page.locator('html')).to_have_attribute('data-signage-revision', cafeteria_snapshot()['revision_id'])


def test_signage_server_date_change_updates_unchanged_revision(
    live_signage: tuple[str, Flask], signage_page: Page,
) -> None:
    base_url, app = live_signage
    page = signage_page
    page.goto(f'{base_url}/signage/cafeteria/tag')
    revision = page.locator('html').get_attribute('data-signage-revision')
    app.config['DEMO_TODAY'] = '2026-09-03'
    expect(page.locator('html')).to_have_attribute('data-signage-date', '2026-09-03')
    expect(page.locator('html')).to_have_attribute('data-signage-revision', revision)
    expect(page.locator('[data-signage-root]')).not_to_contain_text('Kalbsbratwurst')
    expect(page.locator('.signage-weekday')).to_have_text('Donnerstag')


def test_signage_clock_uses_zurich_timezone(live_signage: tuple[str, Flask], signage_page: Page) -> None:
    base_url, _ = live_signage
    page = signage_page
    page.clock.install(time='2026-09-02T22:05:00Z')  # 3 September 00:05 in Zurich.
    page.goto(f'{base_url}/signage/cafeteria/tag')
    expect(page.locator('[data-signage-clock]')).to_have_text('00:05')
