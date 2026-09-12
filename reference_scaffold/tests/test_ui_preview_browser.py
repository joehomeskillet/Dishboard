"""Browser suite for standalone, script-free admin.preview (MP-UI-PREVIEW)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, BrowserContext, Page, expect
from sqlalchemy import Engine, text

from cafeteria import roles
from cafeteria.branding_config import contrast
from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080))
FAMILIES = (
    ('cafeteria', 'staff_guest', 'Mitarbeitende und externe Gäste'),
    ('patienten', 'patient', 'Patientinnen und Patienten'),
)
SCRIPT_FREE = 'script, style, [style], [onclick], form, button'
STATUS_LABELS = (
    ('ready', 'Nicht veröffentlicht · Bereit'),
    ('published', 'Veröffentlicht'),
    ('archived', 'Nicht veröffentlicht · Archiviert'),
    ('draft', 'Nicht veröffentlicht · Entwurf'),
)


def _hex(color: str) -> str:
    match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', color)
    if match:
        red, green, blue = (int(value) for value in match.groups())
        return f'#{red:02x}{green:02x}{blue:02x}'
    return color


def _cookie_page(
    browser: Browser, live_server: str, cookie_value: str, *,  # noqa: F811
    width: int, height: int, java_script_enabled: bool,
) -> tuple[BrowserContext, Page]:
    context = browser.new_context(
        base_url=live_server,
        java_script_enabled=java_script_enabled,
        viewport={'width': width, 'height': height},
    )
    context.add_cookies([{
        'name': 'session', 'value': cookie_value, 'url': live_server, 'httpOnly': True,
    }])
    return context, context.new_page()


def _setup(app: Flask, profile: str) -> dict:
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    closed = values['days'][-1]['services'][-1]
    closed.update(service_state='closed', notice='Feiertag – Küche geschlossen')
    _save(app.extensions['cafeteria_db'], profile, values)
    return values


def _assert_script_free(page: Page) -> None:
    assert page.locator(SCRIPT_FREE).count() == 0


def _assert_no_overflow(page: Page) -> None:
    assert page.evaluate(
        'document.documentElement.scrollWidth <= document.documentElement.clientWidth',
    )


@pytest.mark.parametrize('family,profile,label', FAMILIES)
def test_preview_standalone_script_free_saved_states(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, label: str, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _setup(admin_app, profile)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900,
        java_script_enabled=False,
    )
    try:
        for state, translated in STATUS_LABELS:
            with admin_engine.begin() as connection:
                connection.execute(
                    text('UPDATE cafeteria.menu_weeks SET workflow_state=:state'),
                    {'state': state},
                )
            response = page.goto(f'/admin/{family}/preview?week={DAY}')
            assert response is not None and response.status == 200
            expect(page.locator('.preview-saved')).to_have_text(
                f'Veröffentlichungsstand dieser Woche: {translated}',
            )
            assert page.locator('[data-preview]').get_attribute('data-workflow-state') == state
        expect(page.get_by_role('heading', level=1)).to_have_text(f'Vorschau · {label}')
        expect(page.locator('.preview-banner[role="status"]')).to_have_text('PREVIEW')
        expect(page.locator('.preview-context')).to_have_text(
            'KW 36 / 2026 · Woche ab 31. August 2026',
        )
        expect(page.locator('.preview-notice')).to_contain_text('gespeicherten Stand')
        expect(page.get_by_role('link', name='Zurück zum Wochenplan')).to_have_attribute(
            'href', f'/admin/{family}?week={DAY}',
        )
        expect(page.get_by_role('link', name='Wochenplan als PDF öffnen')).to_have_attribute(
            'href', f'/admin/{family}/preview/print?week={DAY}',
        )
        current = page.locator('.preview-profiles a[aria-current="page"]')
        expect(current).to_have_text(label)
        expect(page.locator('.preview-profiles a')).to_have_count(2)
        expect(page.locator('main#main-content.admin-preview')).to_have_count(1)
        assert page.locator('.skip-link').get_attribute('href') == '#main-content'
        assert page.locator('nav.admin-sidebar, .navbar-vertical, .admin-main').count() == 0
        _assert_script_free(page)
        expect(page.locator('.service-notice')).to_have_text('Feiertag – Küche geschlossen')
        if values.get('title'):
            expect(page.get_by_role('heading', level=2, name=values['title'])).to_have_text(
                values['title'],
            )
        assert 'Allergen' in page.locator('main').inner_text()
        _assert_no_overflow(page)
        page.screenshot(path=str(tmp_path / f'preview-default-{family}-1440.png'), full_page=True)
    finally:
        context.close()


@pytest.mark.parametrize('family,profile,label', FAMILIES)
@pytest.mark.parametrize(
    'width,height,java_script_enabled',
    [
        (1440, 900, False), (1366, 768, False), (1024, 768, False), (768, 1024, False),
        (390, 844, False), (1920, 1080, False),
        (1440, 900, True), (390, 844, True),
    ],
)
def test_preview_viewports_no_overflow(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, label: str, width: int, height: int,
    java_script_enabled: bool, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _setup(admin_app, profile)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=width, height=height,
        java_script_enabled=java_script_enabled,
    )
    try:
        response = page.goto(f'/admin/{family}/preview?week={DAY}')
        assert response is not None and response.status == 200
        if java_script_enabled:
            page.evaluate('document.fonts.ready')
        expect(page.get_by_role('heading', level=1)).to_have_text(f'Vorschau · {label}')
        _assert_script_free(page)
        _assert_no_overflow(page)
        links = page.locator('.preview-links a, .preview-profiles a')
        assert links.count() >= 3
        for index in range(links.count()):
            box = links.nth(index).bounding_box()
            assert box is not None and box['height'] >= 44
        suffix = 'js' if java_script_enabled else 'nojs'
        page.screenshot(
            path=str(tmp_path / f'preview-{family}-{width}x{height}-{suffix}.png'),
            full_page=True,
        )
    finally:
        context.close()


def test_preview_keyboard_focus_and_zoom(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _setup(admin_app, 'staff_guest')
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900,
        java_script_enabled=True,
    )
    try:
        page.goto(f'/admin/cafeteria/preview?week={DAY}')
        page.evaluate('document.fonts.ready')
        _assert_script_free(page)
        page.keyboard.press('Tab')
        expect(page.locator('.skip-link')).to_be_focused()
        page.get_by_role('link', name='Zurück zum Wochenplan').focus()
        focused = page.evaluate(
            '''() => {
                const el = document.activeElement;
                const style = getComputedStyle(el);
                return {tag: el.tagName, outline: style.outlineStyle, width: parseFloat(style.outlineWidth)};
            }''',
        )
        assert focused['tag'] == 'A'
        assert focused['outline'] != 'none' or focused['width'] >= 2
        page.screenshot(path=str(tmp_path / 'preview-keyboard-1440.png'), full_page=True)
        page.evaluate("document.documentElement.style.zoom = '2'")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 8')
        page.screenshot(path=str(tmp_path / 'preview-zoom200-1440.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.goto(f'/admin/cafeteria/preview?week={DAY}')
        page.evaluate("document.documentElement.style.zoom = '2'")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 8')
        page.screenshot(path=str(tmp_path / 'preview-zoom200-390.png'), full_page=True)
    finally:
        context.close()


def test_preview_contrast_empty_invalid_and_authz(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _setup(admin_app, 'staff_guest')
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900,
        java_script_enabled=False,
    )
    try:
        page.goto(f'/admin/cafeteria/preview?week={DAY}')
        for selector in ('h1', '.preview-saved', '.preview-day > h3', '.preview-option h5'):
            locator = page.locator(selector).first
            color = locator.evaluate('el => getComputedStyle(el).color')
            background = locator.evaluate(
                '''el => {
                    let node = el;
                    while (node) {
                        const bg = getComputedStyle(node).backgroundColor;
                        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
                        node = node.parentElement;
                    }
                    return 'rgb(255, 255, 255)';
                }''',
            )
            assert contrast(_hex(color), _hex(background)) >= 4.5, (selector, color, background)
        empty_values = _staff_values('Leere Woche')
        for day in empty_values['days']:
            for service in day['services']:
                service.update(service_state='closed', notice='Noch keine Menüs gespeichert')
        _save(admin_app.extensions['cafeteria_db'], 'staff_guest', empty_values)
        empty = page.goto(f'/admin/cafeteria/preview?week={DAY}')
        assert empty is not None and empty.status == 200
        assert page.locator('.preview-option').count() == 0
        expect(page.locator('.service-notice').first).to_have_text('Noch keine Menüs gespeichert')
        _assert_script_free(page)
        page.screenshot(path=str(tmp_path / 'preview-empty-1440.png'), full_page=True)
        assert page.goto('/admin/cafeteria/preview?week=invalid-date').status == 400
        assert page.goto('/admin/cafeteria/preview?week=2026-08-30').status == 400
        assert page.goto('/admin/cafeteria/preview?week=2099-01-05').status == 404
    finally:
        context.close()

    with browser.new_context(base_url=live_server, viewport={'width': 1440, 'height': 900}) as anon:
        denied = anon.new_page().goto(f'/admin/cafeteria/preview?week={DAY}')
        assert denied is not None and denied.status == 401

    monkeypatch.setattr(roles, 'capabilities', lambda: set())
    forbidden_ctx, forbidden_page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900,
        java_script_enabled=False,
    )
    try:
        forbidden = forbidden_page.goto(f'/admin/cafeteria/preview?week={DAY}')
        assert forbidden is not None and forbidden.status == 403
    finally:
        forbidden_ctx.close()
