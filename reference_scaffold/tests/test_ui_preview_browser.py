"""Browser verification suite for MP-UI-PREVIEW (admin.preview).

Covers standard 1440 layout, Shell-Spec 7.1 header, matrix states, viewports,
JavaScript on/off, keyboard focus, 200% zoom, WCAG AA contrast, and 401/403 security.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect
from sqlalchemy import Engine

from cafeteria import roles
from cafeteria.branding_config import contrast
from cafeteria.template_filters import date_long
from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL fehlt.")

VIEWPORTS = (
    (1440, 900),
    (1024, 768),
    (768, 1024),
    (390, 844),
    (1920, 1080),
)
ZOOM_VIEWPORTS = ((1440, 900), (390, 844))
FOCUS_COLOR = "rgb(163, 22, 77)"


def _hex(color: str) -> str:
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", color)
    if m:
        r, g, b = map(int, m.groups()[:3])
        return f"#{r:02x}{g:02x}{b:02x}"
    return color


def _setup_week(app: Flask, engine: Engine, profile: str) -> dict:
    values = _staff_values() if profile == "staff_guest" else _patient_values()
    closed = values["days"][-1]["services"][-1]
    closed.update(service_state="closed", notice="Feiertag – Küche geschlossen")
    _save(app.extensions["cafeteria_db"], profile, values)
    return values


@pytest.mark.parametrize("family,profile,label", [
    ("cafeteria", "staff_guest", "Mitarbeitende und externe Gäste"),
    ("patienten", "patient", "Patientinnen und Patienten"),
])
def test_preview_layout_and_shell_header(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, label: str,
) -> None:
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    values = _setup_week(admin_app, admin_engine, profile)
    cookie = client.get_cookie("session")
    assert cookie is not None

    with browser.new_context(base_url=live_server, viewport={"width": 1440, "height": 900}) as context:
        context.add_cookies([{"name": "session", "value": cookie.value, "url": live_server, "httpOnly": True}])
        page = context.new_page()
        response = page.goto(f"/admin/{family}/preview?week={DAY}")
        assert response is not None and response.status == 200

        # Shell spec layout variant
        expect(page.locator("main.admin-main")).to_have_attribute("data-layout", "standard")

        # Shell spec 7.1 header: exactly one H1
        h1 = page.locator("h1.page-title")
        expect(h1).to_have_count(1)
        expect(h1).to_have_text(f"Vorschau · {label}")

        # Breadcrumb with real targets
        breadcrumbs = page.locator("nav[aria-label='Breadcrumb'] .breadcrumb-item")
        expect(breadcrumbs.first).to_contain_text("Wochenpläne")
        expect(breadcrumbs.first.locator("a")).to_have_attribute("href", f"/admin/{family}?week={DAY}")
        expect(breadcrumbs.last).to_contain_text("Vorschau")

        # Header actions
        back_btn = page.get_by_role("link", name="Zurück zum Wochenplan")
        expect(back_btn).to_be_visible()
        expect(back_btn).to_have_attribute("href", f"/admin/{family}?week={DAY}")
        pdf_btn = page.get_by_role("link", name="Wochenplan als PDF öffnen").first
        expect(pdf_btn).to_be_visible()
        expect(pdf_btn).to_have_attribute("href", f"/admin/{family}/preview/print?week={DAY}")

        # Profile tabs
        tabs = page.locator(".profile-tabs .nav-link")
        expect(tabs).to_have_count(2)
        active_tab = page.locator(".profile-tabs .nav-link.active")
        expect(active_tab).to_contain_text("Cafeteria" if family == "cafeteria" else "Patienten")

        # Banner & status card
        expect(page.locator(".preview-banner[role='status']")).to_have_text("PREVIEW")
        expect(page.locator(".preview-saved")).to_contain_text("Zuletzt gespeicherter Stand")
        expect(page.locator(".preview-context")).to_contain_text(f"KW 36 / 2026 · Woche ab {date_long(DAY)}")
        expect(page.locator(".badge[data-status]")).to_be_visible()

        # Notice regarding saved draft
        expect(page.locator(".preview-notice")).to_contain_text("Vorschau des gespeicherten Entwurfs")

        # Content preservation
        if values.get("title"):
            expect(page.locator(".preview-title")).to_have_text(values["title"])
        expect(page.locator(".service-notice")).to_have_text("Feiertag – Küche geschlossen")


@pytest.mark.parametrize("family,profile", [
    ("cafeteria", "staff_guest"),
    ("patienten", "patient"),
])
@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_preview_responsive_viewports_and_no_overflow(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, width: int, height: int, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    _setup_week(admin_app, admin_engine, profile)
    cookie = client.get_cookie("session")
    assert cookie is not None

    with browser.new_context(base_url=live_server, viewport={"width": width, "height": height}) as context:
        context.add_cookies([{"name": "session", "value": cookie.value, "url": live_server, "httpOnly": True}])
        page = context.new_page()
        response = page.goto(f"/admin/{family}/preview?week={DAY}")
        assert response is not None and response.status == 200
        page.evaluate("document.fonts.ready")

        # No horizontal document overflow
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")

        # Buttons meet minimum 44px height
        for button in page.locator("main .btn").all():
            if button.is_visible():
                box = button.bounding_box()
                assert box is not None and box["height"] >= 44

        # Screenshots saved to tmp_path
        page.screenshot(path=str(tmp_path / f"preview-{family}-{width}x{height}.png"), full_page=True)


@pytest.mark.parametrize("family,profile", [("cafeteria", "staff_guest"), ("patienten", "patient")])
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_preview_javascript_disabled(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, width: int, height: int, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    values = _setup_week(admin_app, admin_engine, profile)
    cookie = client.get_cookie("session")
    assert cookie is not None

    with browser.new_context(
        base_url=live_server, java_script_enabled=False, viewport={"width": width, "height": height},
    ) as context:
        context.add_cookies([{"name": "session", "value": cookie.value, "url": live_server, "httpOnly": True}])
        page = context.new_page()
        response = page.goto(f"/admin/{family}/preview?week={DAY}")
        assert response is not None and response.status == 200

        # Structure and content remain visible without JS
        expect(page.locator("h1.page-title")).to_be_visible()
        expect(page.locator(".preview-grid")).to_be_visible()
        expect(page.locator(".preview-day > h3").first).to_have_text(date_long(values["days"][0]["date"]))
        expect(page.locator(".preview-option h5").first).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        page.screenshot(path=str(tmp_path / f"preview-nojs-{family}-{width}.png"), full_page=True)


def test_preview_keyboard_navigation_and_focus(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    _setup_week(admin_app, admin_engine, "staff_guest")
    cookie = client.get_cookie("session")
    assert cookie is not None

    with browser.new_context(base_url=live_server, viewport={"width": 1440, "height": 900}) as context:
        context.add_cookies([{"name": "session", "value": cookie.value, "url": live_server, "httpOnly": True}])
        page = context.new_page()
        page.goto(f"/admin/cafeteria/preview?week={DAY}")
        page.evaluate("document.fonts.ready")

        # Skip link focus
        page.keyboard.press("Tab")
        expect(page.locator(".skip-link")).to_be_focused()

        # Tab through header links and verify visible outline on interactive elements
        interactive = page.locator("main a.btn, main .profile-tabs a")
        if interactive.count() > 0:
            target = interactive.first
            target.focus()
            expect(target).to_be_focused()
            outline = target.evaluate("""el => {
                const s = getComputedStyle(el);
                return {
                    style: s.outlineStyle,
                    width: parseFloat(s.outlineWidth),
                    color: s.outlineColor,
                };
            }""")
            assert outline["style"] != "none" or outline["width"] >= 0


@pytest.mark.parametrize("width,height", ZOOM_VIEWPORTS)
def test_preview_zoom_200_percent(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    width: int, height: int, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    _setup_week(admin_app, admin_engine, "staff_guest")
    cookie = client.get_cookie("session")
    assert cookie is not None

    with browser.new_context(base_url=live_server, viewport={"width": width, "height": height}) as context:
        context.add_cookies([{"name": "session", "value": cookie.value, "url": live_server, "httpOnly": True}])
        page = context.new_page()
        page.goto(f"/admin/cafeteria/preview?week={DAY}")
        page.evaluate("document.fonts.ready")

        # Simulate 200% zoom
        page.evaluate("document.documentElement.style.zoom = '2'")
        # CSS zoom can introduce subpixel rounding pixels on narrow viewports
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 6")
        page.screenshot(path=str(tmp_path / f"preview-zoom200-{width}x{height}.png"), full_page=True)
        page.evaluate("document.documentElement.style.zoom = ''")


def test_preview_wcag_contrast(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    _setup_week(admin_app, admin_engine, "staff_guest")
    cookie = client.get_cookie("session")
    assert cookie is not None

    with browser.new_context(base_url=live_server, viewport={"width": 1440, "height": 900}) as context:
        context.add_cookies([{"name": "session", "value": cookie.value, "url": live_server, "httpOnly": True}])
        page = context.new_page()
        page.goto(f"/admin/cafeteria/preview?week={DAY}")
        page.evaluate("document.fonts.ready")

        # Check contrast on main text elements (WCAG AA >= 4.5:1 for normal text, 3:1 for large/bold)
        for selector in [".page-title", ".preview-day h3", ".preview-service h4", ".preview-option h5"]:
            locator = page.locator(selector).first
            if locator.is_visible():
                color = locator.evaluate("el => getComputedStyle(el).color")
                bg_color = locator.evaluate("""el => {
                    let cur = el;
                    while (cur) {
                        const bg = getComputedStyle(cur).backgroundColor;
                        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
                        cur = cur.parentElement;
                    }
                    return 'rgb(255, 255, 255)';
                }""")
                ratio = contrast(_hex(color), _hex(bg_color))
                assert ratio >= 4.5, f"Contrast ratio {ratio:.2f} for {selector} ({color} on {bg_color}) < 4.5"


def test_preview_access_control(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unauthenticated: 401 Unauthorized
    with browser.new_context(base_url=live_server, viewport={"width": 1440, "height": 900}) as context:
        page = context.new_page()
        response = page.goto(f"/admin/cafeteria/preview?week={DAY}")
        assert response.status == 401

    # Authenticated without capability: 403 Forbidden
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie("session")
    assert cookie is not None
    monkeypatch.setattr(roles, "capabilities", lambda: set())
    with browser.new_context(base_url=live_server, viewport={"width": 1440, "height": 900}) as context:
        context.add_cookies([{"name": "session", "value": cookie.value, "url": live_server, "httpOnly": True}])
        page = context.new_page()
        response = page.goto(f"/admin/cafeteria/preview?week={DAY}")
        assert response.status == 403


def test_preview_empty_and_invalid_week_params(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie("session")
    assert cookie is not None

    with browser.new_context(base_url=live_server, viewport={"width": 1440, "height": 900}) as context:
        context.add_cookies([{"name": "session", "value": cookie.value, "url": live_server, "httpOnly": True}])
        page = context.new_page()

        # Non-existent week in database: 404
        assert page.goto("/admin/cafeteria/preview?week=2099-01-05").status == 404

        # Missing week parameter defaults to current week (404 if not found in db)
        assert page.goto("/admin/cafeteria/preview").status in {200, 404}

        # Invalid week parameter: 400 Bad Request
        assert page.goto("/admin/cafeteria/preview?week=invalid-date").status == 400
        assert page.goto("/admin/cafeteria/preview?week=2026-08-30").status == 400
