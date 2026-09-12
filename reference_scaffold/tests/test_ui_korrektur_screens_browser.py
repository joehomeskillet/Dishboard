"""Browser evidence for simplified screen and display administration."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

from cafeteria.screen_templates import key
from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_screen_template_routes import screen_app as screen_app  # noqa: F401
from test_ui_output_hubs_browser import (  # noqa: F401
    _admin_page,
    empty_hub_app,
    empty_hub_server,
    hub_server,
    published_hub_app,
)

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL fehlt.")

EVIDENCE = Path(__file__).resolve().parents[2] / ".claude/evidence/ui-korrektur-0912/screens"
VIEWPORTS = [(1366, 768), (1920, 1080), (768, 1024), (390, 844)]


def _assert_no_horizontal_scroll(page: Page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def _screenshot(page: Page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / name), full_page=True)


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_lists_and_settings_come_first_at_required_viewports(
    published_hub_app,  # noqa: F811
    hub_server,  # noqa: F811
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    width: int,
    height: int,
) -> None:
    context, page = _admin_page(
        published_hub_app,
        database_engine,
        browser,
        hub_server,
        viewport=(width, height),
    )
    try:
        assert page.goto("/admin/screens").status == 200
        expect(page.get_by_role("heading", level=1)).to_have_text("Bildschirme")
        expect(page.locator('nav[aria-label="Bereich"]')).to_have_count(1)
        first_screen = page.locator(".screen-card").first.bounding_box()
        assert first_screen is not None and first_screen["y"] < height
        expect(page.get_by_text("Vorlage für Web-Wochenplan:", exact=False)).to_have_count(2)
        body = page.locator("main").inner_text().lower()
        assert "verbunden" not in body and "zuletzt gesehen" not in body
        _assert_no_horizontal_scroll(page)
        _screenshot(page, f"bildschirme-regulaer-{width}x{height}.png")

        assert page.goto("/admin/screens/cafeteria/wochenvorlage").status == 200
        expect(page.locator("#active-screen-template-title")).to_have_text("Aktive Vorlage")
        assignment = page.locator("#screen-assignment-details")
        expect(assignment).not_to_have_attribute("open", "")
        assert assignment.locator(":scope > summary").bounding_box()["y"] < height
        _assert_no_horizontal_scroll(page)
        _screenshot(page, f"vorlage-zuweisen-geschlossen-{width}x{height}.png")

        assert page.goto("/admin/design/darstellung").status == 200
        expect(page.locator("#display-settings-form .card-title")).to_have_text(
            "Anzeige einstellen"
        )
        first_setting = page.get_by_label("Abstände", exact=True).bounding_box()
        assert first_setting is not None and first_setting["y"] < height
        expect(page.locator("#display-settings-form .btn-primary")).to_have_count(1)
        expect(page.locator(".display-preview")).to_have_attribute("data-density", "compact")
        expect(page.locator(".display-preview")).to_have_attribute("data-font-size", "normal")
        expect(page.locator(".display-preview")).to_have_attribute("data-content-width", "contained")
        expect(page.locator(".display-preview")).to_have_attribute("data-menu-images", "show")
        _assert_no_horizontal_scroll(page)
        _screenshot(page, f"darstellung-regulaer-{width}x{height}.png")
    finally:
        context.close()


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_native_form_targets_and_payloads_stay_complete(
    published_hub_app,  # noqa: F811
    hub_server,  # noqa: F811
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    javascript: bool,
) -> None:
    context, page = _admin_page(
        published_hub_app,
        database_engine,
        browser,
        hub_server,
        javascript=javascript,
    )
    try:
        page.goto("/admin/screens/cafeteria/wochenvorlage")
        page.locator("#screen-assignment-details > summary").click()
        selected = page.locator('input[name="template_id"]:not(:checked)').first
        template_id = selected.get_attribute("value")
        selected.check()
        with page.expect_request(
            lambda request: request.method == "POST"
        ) as submitted, page.expect_response(
            lambda response: response.request.method == "POST"
        ) as response:
            page.get_by_role("button", name="Vorlage zuweisen", exact=True).click()
        assert response.value.status == 303
        request = submitted.value
        payload = parse_qs(request.post_data or "", keep_blank_values=True)
        assert urlsplit(request.url).path == "/admin/screens/cafeteria/wochenvorlage"
        assert set(payload) == {
            "_csrf",
            "_form_context",
            "version",
            "renderer_revision",
            "action",
            "template_id",
        }
        assert payload["template_id"] == [template_id]
        assert payload["renderer_revision"] == ["1"]
        assert payload["action"] == ["activate"]

        page.goto("/admin/design/darstellung")
        page.get_by_label("Abstände", exact=True).select_option("comfortable")
        page.get_by_label("Menübilder", exact=True).select_option("hide")
        with page.expect_request(
            lambda request: request.method == "POST"
        ) as submitted, page.expect_response(
            lambda response: response.request.method == "POST"
        ) as response:
            page.get_by_role("button", name="Vorschau aktualisieren", exact=True).click()
        assert response.value.status == 200
        request = submitted.value
        payload = parse_qs(request.post_data or "", keep_blank_values=True)
        assert urlsplit(request.url).path == "/admin/design/darstellung"
        assert set(payload) == {
            "_csrf",
            "action",
            "admin_density",
            "admin_font_size",
            "admin_content_width",
            "admin_menu_images",
        }
        assert payload["action"] == ["preview"]
        assert payload["admin_density"] == ["comfortable"]
        assert payload["admin_menu_images"] == ["hide"]
        expect(page.get_by_text("Vorschau der Auswahl", exact=False)).to_be_visible()
    finally:
        context.close()


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_assignment_conflict_opens_details_preserves_values_and_focuses_error(
    published_hub_app,  # noqa: F811
    hub_server,  # noqa: F811
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    javascript: bool,
) -> None:
    context, current = _admin_page(
        published_hub_app,
        database_engine,
        browser,
        hub_server,
        javascript=javascript,
        viewport=(1366, 768),
    )
    stale = context.new_page()
    try:
        route = "/admin/screens/cafeteria/wochenvorlage"
        current.goto(route)
        stale.goto(route)
        for page in (current, stale):
            page.locator("#screen-assignment-details > summary").click()
            page.locator('input[name="template_id"]:not(:checked)').first.check()
        assignment_form = stale.locator("#screen-assignment-details form")
        original = {
            name: assignment_form.locator(f'[name="{name}"]').input_value()
            for name in ("_csrf", "_form_context", "version", "renderer_revision", "action")
        }
        chosen = assignment_form.locator('input[name="template_id"]:checked').input_value()

        with current.expect_response(lambda response: response.request.method == "POST") as saved:
            current.get_by_role("button", name="Vorlage zuweisen", exact=True).click()
        assert saved.value.status == 303
        with stale.expect_response(lambda response: response.request.method == "POST") as conflict:
            stale.get_by_role("button", name="Vorlage zuweisen", exact=True).click()
        assert conflict.value.status == 409

        details = stale.locator("#screen-assignment-details")
        expect(details).to_have_attribute("open", "")
        error = stale.locator(".error-region")
        expect(error).to_be_focused()
        for name, value in original.items():
            expect(assignment_form.locator(f'[name="{name}"]')).to_have_value(value)
        expect(assignment_form.locator(f'input[name="template_id"][value="{chosen}"]')).to_be_checked()
        _assert_no_horizontal_scroll(stale)
        _screenshot(stale, f"vorlage-zuweisen-konflikt-{javascript}.png")
    finally:
        context.close()


def test_empty_and_unavailable_states_have_scoped_messages_and_evidence(
    empty_hub_app,  # noqa: F811
    empty_hub_server,  # noqa: F811
    database_engine,  # noqa: F811
    browser,  # noqa: F811
) -> None:
    empty_context, empty = _admin_page(
        empty_hub_app,
        database_engine,
        browser,
        empty_hub_server,
        viewport=(1366, 768),
    )
    try:
        empty.goto("/admin/screens")
        expect(empty.frame_locator(".screen-preview iframe").first.get_by_text(
            "Speiseplan nicht verfügbar", exact=False
        )).to_be_visible()
        _assert_no_horizontal_scroll(empty)
        _screenshot(empty, "bildschirme-leer-1366x768.png")
    finally:
        empty_context.close()

    setting_key = key("staff_guest")
    with database_engine.begin() as connection:
        original = connection.execute(
            text(
                "SELECT setting_value::text FROM cafeteria.settings "
                "WHERE location_id IS NULL AND profile_id IS NULL AND setting_key = :key"
            ),
            {"key": setting_key},
        ).scalar_one_or_none()
        connection.execute(
            text(
                "INSERT INTO cafeteria.settings (location_id, profile_id, setting_key, setting_value) "
                "VALUES (NULL, NULL, :key, CAST(:value AS jsonb)) "
                "ON CONFLICT (location_id, profile_id, setting_key) "
                "DO UPDATE SET setting_value = EXCLUDED.setting_value"
            ),
            {"key": setting_key, "value": '{"schema_version": 999}'},
        )
    context, unavailable = _admin_page(
        empty_hub_app,
        database_engine,
        browser,
        empty_hub_server,
        viewport=(1366, 768),
    )
    try:
        response = unavailable.goto("/admin/screens/cafeteria/wochenvorlage")
        assert response.status == 503
        expect(unavailable.get_by_role("heading", level=1)).to_have_text(
            "Bildschirmvorlagen vorübergehend nicht verfügbar"
        )
        expect(unavailable.get_by_text("Es wurde keine neue Vorlage zugewiesen.")).to_be_visible()
        _assert_no_horizontal_scroll(unavailable)
        _screenshot(unavailable, "vorlage-nicht-verfuegbar-1366x768.png")
    finally:
        context.close()
        with database_engine.begin() as connection:
            if original is None:
                connection.execute(
                    text(
                        "DELETE FROM cafeteria.settings WHERE location_id IS NULL "
                        "AND profile_id IS NULL AND setting_key = :key"
                    ),
                    {"key": setting_key},
                )
            else:
                connection.execute(
                    text(
                        "UPDATE cafeteria.settings SET setting_value = CAST(:value AS jsonb) "
                        "WHERE location_id IS NULL AND profile_id IS NULL AND setting_key = :key"
                    ),
                    {"key": setting_key, "value": original},
                )


def test_required_pages_have_no_overflow_at_200_percent_zoom(
    published_hub_app,  # noqa: F811
    hub_server,  # noqa: F811
    database_engine,  # noqa: F811
    browser,  # noqa: F811
) -> None:
    client, _ = _login(published_hub_app, database_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie(published_hub_app.config["SESSION_COOKIE_NAME"])
    assert cookie is not None
    with browser.new_context(
        base_url=hub_server,
        viewport={"width": 720, "height": 450},
        device_scale_factor=2,
        reduced_motion="reduce",
    ) as context:
        context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": hub_server}])
        page = context.new_page()
        for path, name in (
            ("/admin/screens", "bildschirme"),
            ("/admin/screens/cafeteria/wochenvorlage", "vorlage-zuweisen"),
            ("/admin/design/darstellung", "darstellung"),
        ):
            assert page.goto(path).status == 200
            _assert_no_horizontal_scroll(page)
            _screenshot(page, f"{name}-zoom-200.png")
