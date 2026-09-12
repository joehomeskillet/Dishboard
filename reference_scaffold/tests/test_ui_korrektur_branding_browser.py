"""UX-02 browser contract for branding draft, preview and activation hierarchy."""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Browser, Page, expect

from cafeteria.admin import branding_routes  # noqa: F401 - blueprint registration
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_branding_store import _png

BRAND_PATH = "/admin/design/marke"
EVIDENCE = Path(__file__).resolve().parents[2] / ".claude/evidence/ui-korrektur-0912/branding"
VIEWPORTS = (
    (1366, 768, "1366x768"),
    (1920, 1080, "1920x1080"),
    (768, 1024, "768x1024"),
    (390, 844, "390x844"),
    (720, 450, "zoom-200"),
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


def test_branding_editor_viewports_default_saved_and_error_states(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    with _context(browser, live_server, client) as context:
        page = context.new_page()
        page.goto(BRAND_PATH)
        _screenshot_matrix(page, "empty")

        page.locator("#brand-name").fill("Gespeicherter Stand")
        page.get_by_role("button", name="Entwurf speichern & Vorschau", exact=True).click()
        expect(page).to_have_url(re.compile(r"revision=2$"))
        _screenshot_matrix(page, "saved")

        page.locator("#brand-primary").fill("#zzzzzz")
        page.locator('form[data-brand-action="save"]').evaluate("form => { form.noValidate = true; }")
        page.get_by_role("button", name="Entwurf speichern & Vorschau", exact=True).click()
        expect(page.locator(".alert-danger")).to_be_visible()
        expect(page.locator("#brand-primary")).to_have_value("#zzzzzz")
        _screenshot_matrix(page, "error")
