"""UX-02 browser contract for branding draft, preview and activation hierarchy."""
from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import Browser, Page, expect
from sqlalchemy import text

from cafeteria.admin import branding_routes  # noqa: F401 - blueprint registration
from cafeteria.branding import SETTING_KEY
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_branding_store import _png

BRAND_PATH = "/admin/design/marke"
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / ".claude" / "evidence" / "density-branding-0913"
VIEWPORTS = (
    (1440, 900, "1440x900"),
    (390, 844, "390x844"),
    (1024, 768, "1024x768"),
    (768, 1024, "768x1024"),
    (1920, 1080, "1920x1080"),
)


def _context(playwright_browser: Browser, server_url: str, client, *, javascript: bool = True):
    cookie = client.get_cookie("session")
    assert cookie is not None
    context = playwright_browser.new_context(
        base_url=server_url,
        java_script_enabled=javascript,
        reduced_motion="reduce",
    )
    context.add_cookies(
        [{"name": "session", "value": cookie.value, "domain": "127.0.0.1", "path": "/"}]
    )
    return context


def _assert_viewport(page: Page, state: str) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    expect(page.locator("main.admin-main")).to_have_attribute("data-layout", "standard")
    expect(page.locator("main .btn-primary:visible")).to_have_count(1)
    for locator in page.locator("main :is(.btn, .form-select, .form-control):visible").all():
        box = locator.bounding_box()
        assert box is not None and box["height"] >= 44, (state, locator.get_attribute("id"), box)


def _screenshot_matrix(page: Page, state: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for width, height, label in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        _assert_viewport(page, state)
        page.screenshot(
            path=str(EVIDENCE / f"branding-editor-{state}-{label}.png"),
            full_page=True,
        )
        (EVIDENCE / f"branding-editor-{state}-{label}.json").write_text(
            json.dumps(
                {
                    "route": page.url,
                    "viewport": {"width": width, "height": height},
                    "state": state,
                    "label": label,
                    "geometry": page.evaluate(
                        "({innerWidth, innerHeight, outerWidth, outerHeight, devicePixelRatio})"
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def test_branding_editor_separates_saved_draft_from_publication(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    with _context(browser, live_server, client) as context:
        page = context.new_page()
        page.goto(BRAND_PATH)

        expect(page.get_by_role("link", name="Erscheinungsbild", exact=True)).to_have_count(1)
        expect(page.get_by_role("heading", name="Entwurf bearbeiten", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Entwurf speichern & Vorschau", exact=True)).to_have_class(
            re.compile(r"\bbtn-primary\b")
        )
        expect(page.get_by_role("heading", name="Veröffentlichte Version", exact=True)).to_be_visible()
        publication = page.locator(".brand-publication-card")
        expect(publication.get_by_text("Aktive Version", exact=True)).to_be_visible()
        expect(publication.get_by_text("Ausgewählter gespeicherter Stand", exact=True)).to_be_visible()
        expect(publication.get_by_text("Zuletzt geändert", exact=True)).to_be_visible()

        activate = page.get_by_role("button", name="Version 1 aktivieren", exact=True)
        expect(activate).not_to_have_class(re.compile(r"\bbtn-primary\b"))
        expect(activate).to_be_disabled()
        expect(page.locator('form[data-brand-action="activate"]')).to_have_attribute(
            "data-confirm", re.compile(r"Version 1")
        )
        expect(page.locator("details.brand-history-card summary")).to_contain_text("Weitere Aktionen")
        expect(page.frame_locator("iframe").get_by_role("button")).to_have_count(0)


def test_branding_forms_keep_exact_targets_and_fields_without_javascript(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    with _context(browser, live_server, client, javascript=False) as context:
        page = context.new_page()
        page.goto(BRAND_PATH)

        expected_fields = {
            "save": [
                "_csrf",
                "version",
                "name",
                "logo_sha256",
                "logo",
                "primary",
                "accent",
                "surface",
                "text",
                "font_body",
                "font_heading",
                "action",
            ],
            "activate": ["_csrf", "version", "revision", "action"],
            "restore": ["_csrf", "version", "revision", "action"],
            "reset": ["_csrf", "version", "action"],
        }
        for purpose, fields in expected_fields.items():
            form = page.locator(f'form[data-brand-action="{purpose}"]')
            expect(form).to_have_attribute("method", "post")
            expect(form).to_have_attribute("action", BRAND_PATH)
            assert form.locator("[name]").evaluate_all("els => els.map(el => el.name)") == fields

        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / "branding-editor-nojs-1440x900.png"), full_page=True)

        page.locator("#brand-name").fill("Klarer Entwurf")
        page.locator("#brand-upload").set_input_files(
            {"name": "Logo.png", "mimeType": "image/png", "buffer": _png((100, 100))}
        )
        page.get_by_role("button", name="Entwurf speichern & Vorschau", exact=True).click()
        expect(page).to_have_url(re.compile(r"/admin/design/marke\?revision=2$"))

        page.get_by_role("button", name="Version 2 aktivieren", exact=True).click()
        expect(page.locator(".brand-status-list > div").first.locator("dd span")).to_have_text(
            "Klarer Entwurf · Version 2"
        )

        page.locator("details.brand-history-card summary").click()
        page.get_by_role("button", name="Version 2 als neuen Entwurf übernehmen", exact=True).click()
        expect(page).to_have_url(re.compile(r"/admin/design/marke\?revision=3$"))

        page.locator("details.brand-history-card summary").click()
        page.get_by_role("button", name="Südhang Standard als Entwurf", exact=True).click()
        expect(page).to_have_url(re.compile(r"/admin/design/marke\?revision=4$"))

        with admin_engine.connect() as connection:
            before = connection.execute(
                text("SELECT setting_value FROM cafeteria.settings WHERE setting_key=:key"),
                {"key": SETTING_KEY},
            ).scalar_one()
        assert before["active_revision"] == 2
        assert [revision["id"] for revision in before["revisions"]] == [1, 2, 3, 4]

        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#brand-name").fill("Sichere Eingaben bleiben erhalten")
        page.locator("#brand-primary").fill("#8c1c4b")
        page.locator("#brand-font_body").select_option("carlito")
        form = page.locator('form[data-brand-action="save"]')
        safe_fields = {
            name: form.locator(f'[name="{name}"]').input_value()
            for name in ("version", "name", "logo_sha256", "primary", "accent", "surface", "text", "font_body", "font_heading")
        }
        page.locator("#brand-upload").set_input_files(
            {"name": "Beschaedigt.png", "mimeType": "image/png", "buffer": b"invalid-png"}
        )
        with page.expect_response(
            lambda response: response.request.method == "POST" and response.url.endswith(BRAND_PATH)
        ) as rejected:
            page.get_by_role("button", name="Entwurf speichern & Vorschau", exact=True).click()
        assert rejected.value.status == 400
        expect(page.get_by_role("alert")).to_have_text(
            "Das Logo konnte nicht als sicheres Bild gelesen werden."
        )
        for name, value in safe_fields.items():
            expect(form.locator(f'[name="{name}"]')).to_have_value(value)
        expect(page.locator("#brand-upload")).to_have_value("")
        with admin_engine.connect() as connection:
            after = connection.execute(
                text("SELECT setting_value FROM cafeteria.settings WHERE setting_key=:key"),
                {"key": SETTING_KEY},
            ).scalar_one()
        assert after == before


def test_branding_editor_viewports_default_saved_and_error_states(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    with _context(browser, live_server, client) as context:
        page = context.new_page()
        page.goto(BRAND_PATH)
        _screenshot_matrix(page, "regular")
        _screenshot_matrix(page, "empty")

        # Save draft (revision 2) -> creates a selected draft distinct from active version 1
        page.locator("#brand-name").fill("Gespeicherter Stand")
        page.get_by_role("button", name="Entwurf speichern & Vorschau", exact=True).click()
        expect(page).to_have_url(re.compile(r"revision=2$"))
        _screenshot_matrix(page, "saved")
        _screenshot_matrix(page, "selected-vs-active")

        # Readonly state on active version
        page.goto(f"{BRAND_PATH}?revision=1")
        expect(page.get_by_role("button", name="Version 1 aktivieren", exact=True)).to_be_disabled()
        _screenshot_matrix(page, "readonly")

        # Return to revision 2 and trigger validation error (400)
        page.goto(f"{BRAND_PATH}?revision=2")
        page.locator("#brand-primary").fill("#zzzzzz")
        page.locator('form[data-brand-action="save"]').evaluate("form => { form.noValidate = true; }")
        page.get_by_role("button", name="Entwurf speichern & Vorschau", exact=True).click()
        expect(page.locator(".alert-danger")).to_be_visible()
        expect(page.locator("#brand-primary")).to_have_value("#zzzzzz")
        _screenshot_matrix(page, "error")

        # CAS conflict state (409)
        page.goto(BRAND_PATH)
        page.locator('form[data-brand-action="save"] input[name="version"]').evaluate("el => { el.value = '9999'; }")
        page.locator('form[data-brand-action="save"]').evaluate("form => { form.noValidate = true; }")
        with page.expect_response(
            lambda response: response.request.method == "POST" and response.url.endswith(BRAND_PATH)
        ) as conflict_response:
            page.get_by_role("button", name="Entwurf speichern & Vorschau", exact=True).click()
        assert conflict_response.value.status == 409
        expect(page.locator(".alert-danger")).to_be_visible()
        _screenshot_matrix(page, "cas-conflict")


def test_branding_editor_keyboard_navigation(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    with _context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(BRAND_PATH)

        # Keyboard focus sequence
        name_input = page.locator("#brand-name")
        name_input.focus()
        expect(name_input).to_be_focused()
        outline = name_input.evaluate("el => getComputedStyle(el).outlineColor || getComputedStyle(el).boxShadow")
        assert outline != "none" and outline != "rgba(0, 0, 0, 0)"

        page.keyboard.press("Tab")
        expect(page.locator("#brand-logo-select")).to_be_focused()

        page.keyboard.press("Tab")
        expect(page.locator("#brand-upload")).to_be_focused()

        page.keyboard.press("Tab")
        expect(page.locator("#brand-primary")).to_be_focused()

        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / "branding-editor-keyboard-focus.png"), full_page=True)


def test_branding_editor_native_cdp_zoom_200(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    profile_dir = tmp_path / "density-branding-zoom-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    with browser.browser_type.launch_persistent_context(
        str(profile_dir),
        channel="chromium",
        headless=True,
        no_viewport=True,
        locale="de-CH",
        timezone_id="Europe/Zurich",
        reduced_motion="reduce",
        args=["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,900"],
    ) as zoom_context:
        zoom_page = zoom_context.pages[0]
        zoom_page.goto("chrome://settings/appearance")
        zoom_page.evaluate("new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))")
        assert zoom_page.evaluate("new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))") == 2
        cookie = client.get_cookie("session")
        assert cookie is not None
        zoom_context.add_cookies([{
            "name": "session", "value": cookie.value, "url": live_server,
        }])
        zoom_page.goto(live_server + BRAND_PATH)
        cdp = zoom_context.new_cdp_session(zoom_page)
        metrics = cdp.send("Page.getLayoutMetrics")
        assert metrics["cssVisualViewport"]["zoom"] == 2
        assert zoom_page.evaluate("[innerWidth, outerWidth, devicePixelRatio]") == [720, 1440, 2]
        assert zoom_page.evaluate("getComputedStyle(document.documentElement).zoom") == "1"
        assert zoom_page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        _assert_viewport(zoom_page, "zoom-200")

        EVIDENCE.mkdir(parents=True, exist_ok=True)
        zoom_page.screenshot(path=str(EVIDENCE / "branding-editor-zoom200-cdp.png"), full_page=True)
        (EVIDENCE / "zoom-probe.txt").write_text("chrome-settings-cdp-zoom-2\n", encoding="utf-8")
        (EVIDENCE / "zoom-probe.json").write_text(
            json.dumps({
                "zoom": 2,
                "metrics": metrics,
                "geometry": {"innerWidth": 720, "outerWidth": 1440, "devicePixelRatio": 2},
            }, indent=2),
            encoding="utf-8",
        )
        cdp.detach()

