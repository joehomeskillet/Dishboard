"""Real browser evidence for the M365-styled /auth/local page (Dishboard CSS)."""
from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

import pytest
from PIL import Image
from playwright.sync_api import expect
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from werkzeug.serving import make_server

from cafeteria import create_app
from cafeteria import db as database
from local_user_test_support import provision_local_fixture
from test_rendered_ui import browser  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
REDIS_URL = os.getenv('TEST_REDIS_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
ACTOR_IDENTIFIER = 'login-m365.admin@example.invalid'
LOCAL_USERNAME = 'kueche.m365'
LOCAL_PASSWORD = 'Correct-Horse-2026!Battery'
EVIDENCE = ROOT / '.claude' / 'evidence' / 'auth-login-m365-0914'
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason='TEST_DATABASE_URL und TEST_REDIS_URL für isolierte Auth-Tests fehlen.',
)

_LAYOUT_JS = """
() => {
  const card = document.querySelector('.auth-card');
  const submit = document.querySelector('.auth-submit');
  const cardRect = card.getBoundingClientRect();
  const submitRect = submit.getBoundingClientRect();
  return {
    viewportOverflow: document.documentElement.scrollWidth > innerWidth + 1,
    clippedElements: [...document.querySelectorAll('.auth-shell, .auth-card')]
      .filter(el => el.scrollWidth > el.clientWidth + 1)
      .map(el => el.className),
    cardCentered: Math.abs((cardRect.left + cardRect.right) / 2 - innerWidth / 2) <= 2,
    buttonHeight: submitRect.height,
  };
}
"""


def _role_database_url(role: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(username=role, password=password).render_as_string(hide_password=False)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(rgb_a: tuple[int, int, int], rgb_b: tuple[int, int, int]) -> float:
    la, lb = _relative_luminance(rgb_a), _relative_luminance(rgb_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.fixture
def live_site(monkeypatch, browser):  # noqa: F811
    assert DATABASE_URL is not None and REDIS_URL is not None
    owner_engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    with owner_engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    redis_client = Redis.from_url(REDIS_URL)
    redis_client.flushdb()
    monkeypatch.setenv('DATABASE_URL', _role_database_url('cafeteria_app', APP_PASSWORD))
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD', ISSUER_PASSWORD)
    monkeypatch.setenv('SESSION_REDIS_URL', REDIS_URL)
    monkeypatch.setenv('LOCAL_AUTH_ENABLED', 'true')
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')
    monkeypatch.setenv('FLASK_SECRET_KEY', 'test-only-auth-m365-secret')
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'false')
    monkeypatch.setenv('SEED_DEMO', 'false')
    monkeypatch.setenv('DEMO_TODAY', '')
    monkeypatch.setenv('ENTRA_ENABLED', 'false')
    application = create_app()
    application.config.update(TESTING=True)
    issuer_engine = application.extensions['cafeteria_auth_issuer_db']
    database.upsert_entra_user(
        issuer_engine,
        {
            'tid': '00000000-0000-0000-0000-000000000911',
            'oid': '00000000-0000-0000-0000-000000000922',
            'sub': 'login-m365-actor',
            'name': 'Login M365 Admin',
            'preferred_username': ACTOR_IDENTIFIER,
        },
        ['Cafeteria.Admin'],
    )
    provision_local_fixture(
        issuer_engine, owner_engine,
        actor_identifier=ACTOR_IDENTIFIER,
        username=LOCAL_USERNAME,
        display_name='Küche M365',
        password=LOCAL_PASSWORD,
        roles=['Cafeteria.Editor'],
    )
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        yield origin
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        application.extensions['cafeteria_db'].dispose()
        issuer_engine.dispose()
        with owner_engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
        owner_engine.dispose()
        redis_client.flushdb()
        redis_client.close()


def test_auth_local_login_layout_contrast_and_tab_order(live_site, browser):  # noqa: F811
    """390x844 / 1440x900 / 1920x1080: no overflow, centered card, 48px button;
    footer link contrast on the teal background; keyboard order and focus."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with browser.new_context(base_url=live_site, locale='de-CH', timezone_id='Europe/Zurich',
                              reduced_motion='reduce') as context:
        page = context.new_page()
        for width, height in ((390, 844), (1440, 900), (1920, 1080)):
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto('/auth/local', wait_until='load')
            assert response is not None and response.status == 200
            assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
            page.evaluate('document.fonts.ready')
            metrics = page.evaluate(_LAYOUT_JS)
            assert metrics['viewportOverflow'] is False, metrics
            assert metrics['clippedElements'] == [], metrics
            assert metrics['cardCentered'] is True, metrics
            assert metrics['buttonHeight'] >= 48, metrics
            page.screenshot(path=str(EVIDENCE / f'auth-local-{width}x{height}.png'), full_page=True)

        # Footer link contrast against the teal page background (real pixels).
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto('/auth/local', wait_until='load')
        page.evaluate('document.fonts.ready')
        link = page.locator('.auth-page-links a').first
        color = link.evaluate("el => getComputedStyle(el).color")
        fg = tuple(int(value) for value in re.findall(r'\d+', color)[:3])
        rect = link.evaluate(
            "el => { const r = el.getBoundingClientRect(); "
            "return {left: r.left, top: r.top, height: r.height}; }",
        )
        sample = {'x': max(rect['left'] - 12, 0), 'y': rect['top'] + rect['height'] / 2 - 2,
                   'width': 4, 'height': 4}
        with Image.open(BytesIO(page.screenshot(clip=sample))) as crop:
            bg = crop.convert('RGB').resize((1, 1)).getpixel((0, 0))
        ratio = _contrast_ratio(fg, bg)
        assert ratio >= 4.5, (fg, bg, ratio)

        # Tab order: Benutzername -> Passwort -> Anmelden -> Seiten-Fusslinks.
        page.locator('#username').focus()
        assert page.evaluate('document.activeElement.id') == 'username'
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.id') == 'password'
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.className') == 'auth-submit'
        box_shadow = page.evaluate('getComputedStyle(document.activeElement).boxShadow')
        assert box_shadow not in ('none', ''), box_shadow
        page.keyboard.press('Tab')
        assert page.evaluate("document.activeElement.closest('.auth-page-links') !== null")


def test_auth_local_login_zoom_200_native(live_site, browser, tmp_path):  # noqa: F811
    """Real Chrome default zoom (chrome://settings + CDP), matching test_ui_preview_browser.py."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='auth-login-zoom-', dir=tmp_path) as profile_dir:
        with browser.browser_type.launch_persistent_context(
            profile_dir, channel='chromium', headless=True, no_viewport=True, base_url=live_site,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate(
                'new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))',
            ) == 2
            cdp = context.new_cdp_session(page)
            response = page.goto('/auth/local', wait_until='networkidle')
            assert response is not None and response.status == 200
            page.evaluate('document.fonts.ready')
            assert cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom'] == 2
            metrics = page.evaluate(_LAYOUT_JS)
            assert metrics['viewportOverflow'] is False, metrics
            assert metrics['clippedElements'] == [], metrics
            assert metrics['buttonHeight'] >= 48, metrics
            page.screenshot(path=str(EVIDENCE / 'auth-local-zoom200-1440.png'), full_page=True)


def test_auth_local_login_wrong_password_real_post_shows_alert(live_site, browser):  # noqa: F811
    """Real POST with a fixture account and the wrong password: alert, kept username, no JS/CSS."""
    with browser.new_context(base_url=live_site, locale='de-CH', timezone_id='Europe/Zurich',
                              reduced_motion='reduce') as context:
        page = context.new_page()
        response = page.goto('/auth/local', wait_until='load')
        assert response is not None and response.status == 200
        html = page.content()
        assert '<script' not in html
        assert ' style="' not in html
        assert 'name="csrf_token"' in html

        page.fill('#username', LOCAL_USERNAME)
        page.fill('#password', 'Definitely-Wrong-Password-2026!')
        with page.expect_navigation():
            page.click('.auth-submit')

        expect(page).to_have_url(re.compile(r'/auth/local$'))
        alert = page.locator('.auth-alert')
        expect(alert).to_be_visible()
        expect(alert).to_have_text(re.compile(r'Anmeldung fehlgeschlagen\.'))
        assert page.evaluate("document.activeElement.className") == 'auth-alert'
        assert page.locator('#username').input_value() == LOCAL_USERNAME
        assert page.locator('#password').input_value() == ''
        html_after = page.content()
        assert '<script' not in html_after
        assert ' style="' not in html_after
        assert 'name="csrf_token"' in html_after
