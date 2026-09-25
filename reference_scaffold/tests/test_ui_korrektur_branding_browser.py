"""UX-02 browser contract for branding draft, preview and activation hierarchy."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright
from sqlalchemy import text

from cafeteria.admin import branding_routes  # noqa: F401 - blueprint registration
from cafeteria.branding import SETTING_KEY
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_branding_store import _png
from test_recipe_freeze_v2_browser import native_full_page_capture

BRAND_PATH = "/admin/design/marke"
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / ".claude" / "evidence" / "branding-reviewfix-0913" / "after"
VIEWPORTS = (
    (1440, 900, "1440x900"),
    (360, 844, "360x844"),
    (390, 844, "390x844"),
    (1024, 768, "1024x768"),
    (768, 1024, "768x1024"),
    (1920, 1080, "1920x1080"),
    (2560, 1440, "2560x1440"),
    (320, 844, "320x844"),
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


def _assert_icons_painted(page: Page) -> None:
    icons = page.locator(".brand-settings-grid svg use")
    assert icons.count() >= 3
    for icon_use in icons.all():
        box = icon_use.evaluate("el => ({width: el.getBBox().width, height: el.getBBox().height})")
        assert box["width"] > 0 and box["height"] > 0, (
            "unpainted icon", icon_use.get_attribute("href"), box
        )


def _assert_hex_values_fit(page: Page) -> list[dict]:
    measurements = page.locator(".brand-color-field input[name]").evaluate_all("""fields => {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        return fields.map(field => {
            const style = getComputedStyle(field);
            context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
            const spacing = parseFloat(style.letterSpacing) || 0;
            return {name: field.name, value: field.value,
                textWidth: context.measureText(field.value).width + spacing * field.value.length,
                innerWidth: field.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)};
        });
    }""")
    assert len(measurements) == 4
    for field in measurements:
        assert len(field["value"]) == 7
        assert field["textWidth"] <= field["innerWidth"], ("clipped hex value", field)
    return measurements


def _assert_viewport(page: Page, state: str) -> None:
    page.evaluate("document.fonts.ready")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    _assert_icons_painted(page)
    _assert_hex_values_fit(page)
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
                    "hex_fields": _assert_hex_values_fit(page),
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
        expect(page.get_by_role("button", name="Speichern", exact=True)).to_have_class(
            re.compile(r"\bbtn-primary\b")
        )
        expect(page.locator("main .btn-primary")).to_have_count(1)
        statusbar = page.locator("dl.admin-statusbar")
        expect(statusbar).to_be_visible()
        expect(statusbar).to_contain_text("Südhang Standard")
        expect(statusbar).to_contain_text("Aktiv")
        expect(page.get_by_text("Ausgewählter gespeicherter Stand", exact=True)).to_have_count(0)

        activate = page.get_by_role("button", name="Version 1 aktivieren", exact=True)
        expect(activate).not_to_have_class(re.compile(r"\bbtn-primary\b"))
        expect(activate).to_be_disabled()
        expect(activate).to_have_attribute("data-semantic", "actions.activate")
        expect(activate).to_have_attribute("title", "Öffentliche Marke aktivieren")
        expect(activate.locator("span")).to_have_text("Aktivieren")
        expect(activate).not_to_contain_text("Bereit")
        expect(page.locator('form[data-brand-action="activate"]')).to_have_attribute(
            "data-confirm", re.compile(r"Version 1")
        )
        expect(page.locator("#brand-more summary")).to_contain_text("Weitere Optionen")
        expect(page.locator("#brand-more")).not_to_have_attribute("open", "")
        expect(page.frame_locator("iframe").get_by_role("button")).to_have_count(0)


def test_branding_forms_keep_exact_targets_and_fields_without_javascript(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    with _context(browser, live_server, client, javascript=False) as context:
        page = context.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(BRAND_PATH)
        _assert_viewport(page, "nojs-1440")

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
            names = form.locator("[name]").evaluate_all("els => els.map(el => el.name)")
            if purpose == "save":
                names.append(page.locator('button[form="brand-save"][name="action"]').get_attribute("name"))
            assert names == fields

        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / "branding-editor-nojs-1440x900.png"), full_page=True)

        page.locator("#brand-name").fill("Klarer Entwurf")
        page.locator("#brand-upload").set_input_files(
            {"name": "Logo.png", "mimeType": "image/png", "buffer": _png((100, 100))}
        )
        page.get_by_role("button", name="Speichern", exact=True).click()
        expect(page).to_have_url(re.compile(r"/admin/design/marke\?revision=2$"))

        page.get_by_role("button", name="Version 2 aktivieren", exact=True).click()
        expect(page.locator("dl.admin-statusbar")).to_contain_text("Klarer Entwurf")
        expect(page.locator("[role='status']")).to_contain_text("Klarer Entwurf")

        page.locator("#brand-more summary").click()
        restore = page.get_by_role("button", name="Version 2 als neuen Entwurf übernehmen", exact=True)
        expect(restore).to_have_attribute("data-semantic", "actions.apply")
        expect(restore.locator("span")).to_have_text("Übernehmen")
        expect(restore).to_have_attribute("title", "Erstellt einen neuen Entwurf")
        expect(page.locator('form[data-brand-action="restore"]').get_by_text(
            "Erstellt einen neuen Entwurf", exact=True,
        )).to_be_visible()
        restore.click()
        expect(page).to_have_url(re.compile(r"/admin/design/marke\?revision=3$"))

        page.locator("#brand-more summary").click()
        reset = page.get_by_role("button", name="Südhang Standard als Entwurf anlegen", exact=True)
        expect(reset).to_have_attribute("data-semantic", "actions.add")
        expect(reset).to_have_attribute("title", "Südhang Standard als neuen Entwurf anlegen")
        expect(reset.locator("span")).to_have_text("Entwurf anlegen")
        expect(reset).not_to_have_class(re.compile(r"\bbtn-primary\b"))
        expect(page.locator('form[data-brand-action="reset"] [data-semantic="view.reset"]')).to_have_count(0)
        reset.click()
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
            page.get_by_role("button", name="Speichern", exact=True).click()
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
        _assert_viewport(page, "nojs-390-error")


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
        page.get_by_role("button", name="Speichern", exact=True).click()
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
        page.get_by_role("button", name="Speichern", exact=True).click()
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
            page.get_by_role("button", name="Speichern", exact=True).click()
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
        upload_hint = page.locator('[aria-describedby="brand-upload-hint"]').filter(has=page.locator('svg'))
        expect(upload_hint).to_be_focused()
        expect(page.locator('#brand-upload-hint')).to_be_hidden()
        page.keyboard.press("Enter")
        expect(page.locator('#brand-upload-hint')).to_be_visible()
        page.keyboard.press("Enter")
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
        native_full_page_capture(zoom_page, EVIDENCE / "branding-editor-zoom200-cdp.png")
        (EVIDENCE / "zoom-probe.txt").write_text("chrome-settings-cdp-zoom-2\n", encoding="utf-8")
        (EVIDENCE / "zoom-probe.json").write_text(
            json.dumps({
                "zoom": 2,
                "metrics": metrics,
                "geometry": {"innerWidth": 720, "outerWidth": 1440, "devicePixelRatio": 2},
                "hex_fields": _assert_hex_values_fit(zoom_page),
            }, indent=2),
            encoding="utf-8",
        )
        cdp.detach()


def test_branding_locale_names_contain_visible_action_text(admin_app, admin_engine):  # noqa: F811
    """DE keeps the contextual name; EN and pseudo include the translated label."""
    from html import unescape

    from cafeteria.ui.i18n import pseudo

    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    translator = admin_app.extensions["ui_translator"]
    original = admin_app.config["UI_LOCALE"]
    translator.locales["xx"] = {
        key: pseudo(value) for key, value in translator.locales["de"].items()
    }
    german = {
        "actions.activate": "Version 1 aktivieren",
        "actions.apply": "Version 1 als neuen Entwurf übernehmen",
    }
    try:
        for locale in ("de", "en", "xx"):
            admin_app.config["UI_LOCALE"] = locale
            response = client.get(BRAND_PATH)
            assert response.status_code == 200, (locale, response.status_code)
            html = response.get_data(as_text=True)
            for key, german_name in german.items():
                match = re.search(
                    rf'<button(?P<attrs>[^>]*data-semantic="{key}"[^>]*)>(?P<body>.*?)</button>',
                    html,
                    re.S,
                )
                assert match, (locale, key)
                aria = unescape(re.search(r'aria-label="([^"]*)"', match.group("attrs")).group(1))
                visible = unescape(re.search(r"<span>([^<]*)</span>", match.group("body")).group(1))
                assert visible.lower() in aria.lower(), (locale, key, visible, aria)
                if locale == "de":
                    assert aria == german_name, (key, aria)
            assert "Erstellt einen neuen Entwurf" in html
            assert 'title="Erstellt einen neuen Entwurf"' in html
            assert 'visually-hidden">Erstellt einen neuen Entwurf' not in html
    finally:
        admin_app.config["UI_LOCALE"] = original


def test_branding_rendered_icons_reject_missing_symbols(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    with _context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(BRAND_PATH)
        summary = page.locator("#brand-more summary")
        summary.focus()
        page.keyboard.press("Enter")
        expect(page.locator("#brand-more")).to_have_attribute("open", "")
        reset = page.get_by_role("button", name="Südhang Standard als Entwurf anlegen", exact=True)
        expect(reset).to_be_visible()
        expect(reset.locator("span")).to_have_text("Entwurf anlegen")
        expect(reset).to_have_attribute("data-semantic", "actions.add")
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / "branding-editor-open-actions-1440x900.png"), full_page=True)
        _assert_icons_painted(page)
        icon_use = page.locator("#brand-edit-title use")
        original = icon_use.get_attribute("href")
        assert original is not None
        for missing in ("broadcast", "adjustments", "rotate", "not-a-real-icon"):
            icon_use.evaluate("(el, href) => el.setAttribute('href', href)", original.split("#")[0] + "#tabler-" + missing)
            with pytest.raises(AssertionError, match="unpainted icon"):
                _assert_icons_painted(page)
        icon_use.evaluate("(el, href) => el.setAttribute('href', href)", original)
        _assert_icons_painted(page)


def test_branding_hex_geometry_rejects_four_column_clipping(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    with _context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(BRAND_PATH)
        page.evaluate("document.fonts.ready")
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / "branding-editor-hex-fields-1440x900.png"), full_page=True)
        _assert_hex_values_fit(page)
        columns = page.locator("fieldset .row > div")
        columns.evaluate_all("els => els.forEach(el => el.classList.add('col-md-3'))")
        with pytest.raises(AssertionError, match="clipped hex value"):
            _assert_hex_values_fit(page)
        columns.evaluate_all("els => els.forEach(el => el.classList.remove('col-md-3'))")
        _assert_hex_values_fit(page)


def test_branding_frame_viewports_statusbar_and_no_overflow(
    live_server: str, admin_app, admin_engine,  # noqa: F811
):
    """Own Chromium start: 360/768/1024/1440, No-JS, keyboard, status bar, overflow."""
    client, _ = _login(admin_app, admin_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie("session")
    assert cookie is not None
    measurements = []

    def inspect() -> None:
        with sync_playwright() as playwright:
            instance = playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                for javascript in (False, True):
                    context = instance.new_context(
                        java_script_enabled=javascript,
                        locale="de-CH",
                        timezone_id="Europe/Zurich",
                        reduced_motion="reduce",
                        service_workers="block",
                    )
                    context.add_cookies([
                        {"name": "session", "value": cookie.value, "url": live_server},
                    ])
                    page = context.new_page()
                    try:
                        for width, height in ((360, 800), (768, 1024), (1024, 768), (1440, 900)):
                            page.set_viewport_size({"width": width, "height": height})
                            response = page.goto(live_server + BRAND_PATH, wait_until="load")
                            assert response is not None and response.status == 200
                            page.evaluate("document.fonts.ready")
                            metric = page.evaluate(
                                """() => {
                                    const iframe = document.querySelector('.brand-preview-frame');
                                    const row = document.querySelector('.brand-history-row');
                                    return {
                                        height: document.documentElement.scrollHeight,
                                        overflow: document.documentElement.scrollWidth > innerWidth + 1,
                                        primary: document.querySelectorAll('main .btn-primary').length,
                                        open: document.querySelectorAll('main details[open]').length,
                                        iframe: iframe ? iframe.getBoundingClientRect().height : 0,
                                        row: row ? row.getBoundingClientRect().height : 0,
                                    };
                                }"""
                            )
                            measurements.append(dict(width=width, javascript=javascript, **metric))
                            assert not metric["overflow"], metric
                            assert metric["primary"] == 1, metric
                            assert metric["open"] == 0, metric
                            if width == 1440:
                                assert metric["iframe"] <= 280, metric
                                page.locator("#brand-more summary").click()
                                row = page.locator(".brand-history-row").first.bounding_box()
                                assert row is not None and row["height"] <= 96, row
                                page.locator("#brand-more summary").click()
                            if width == 360:
                                assert metric["iframe"] <= 240, metric
                                assert page.evaluate(
                                    "document.documentElement.scrollWidth <= innerWidth + 1"
                                )
                            expect(page.locator("dl.admin-statusbar")).to_contain_text("Südhang Standard")
                            expect(page.locator("dl.admin-statusbar")).to_contain_text("Aktiv")
                            expect(page.locator("dl.admin-statusbar")).to_contain_text("Veröffentlicht")
                            save = page.get_by_role("button", name="Speichern", exact=True)
                            expect(save).to_have_count(1)
                            box = save.bounding_box()
                            assert box is not None and box["height"] >= 48, box
                        page.set_viewport_size({"width": 360, "height": 800})
                        page.goto(live_server + BRAND_PATH, wait_until="load")
                        name = page.locator("#brand-name")
                        name.focus()
                        expect(name).to_be_focused()
                        outline = name.evaluate(
                            "el => getComputedStyle(el).outlineColor || getComputedStyle(el).boxShadow"
                        )
                        assert outline != "none" and outline != "rgba(0, 0, 0, 0)"
                        page.keyboard.press("Tab")
                        expect(page.locator("#brand-logo-select")).to_be_focused()
                        form = page.locator('form[data-brand-action="save"]')
                        names = form.locator("[name]").evaluate_all("els => els.map(el => el.name)")
                        names.append(page.locator('button[form="brand-save"][name="action"]').get_attribute("name"))
                        assert names == [
                            "_csrf", "version", "name", "logo_sha256", "logo",
                            "primary", "accent", "surface", "text", "font_body",
                            "font_heading", "action",
                        ]
                        assert page.locator('button[form="brand-save"][name="action"]').get_attribute("value") == "save"
                        for purpose, fields in (
                            ("activate", ["_csrf", "version", "revision", "action"]),
                            ("restore", ["_csrf", "version", "revision", "action"]),
                            ("reset", ["_csrf", "version", "action"]),
                        ):
                            listed = page.locator(
                                f'form[data-brand-action="{purpose}"] [name]'
                            ).evaluate_all("els => els.map(el => el.name)")
                            assert listed == fields
                    finally:
                        context.close()
            finally:
                instance.close()

    with ThreadPoolExecutor(max_workers=1) as worker:
        worker.submit(inspect).result()
    print("WP15_MEASUREMENTS", json.dumps(measurements))
