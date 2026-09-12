"""Browser contracts for simplified print-template overview and editor."""
# ruff: noqa: F811

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _login
from test_print_template_browser import browser, editor_server  # noqa: F401
from test_print_template_routes import database_engine, editor_app  # noqa: F401


VIEWPORTS = [(1366, 768), (1920, 1080), (768, 1024), (390, 844)]
EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / ".claude/evidence/ui-korrektur-0912/vorlagen"
)


def _context(
    app,
    database_engine,
    browser: Browser,
    server: str,
    viewport: tuple[int, int],
    *,
    javascript: bool = True,
    device_scale_factor: int = 1,
) -> BrowserContext:
    client, _ = _login(app, database_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"])
    assert cookie is not None
    context = browser.new_context(
        base_url=server,
        viewport={"width": viewport[0], "height": viewport[1]},
        java_script_enabled=javascript,
        reduced_motion="reduce",
        device_scale_factor=device_scale_factor,
    )
    context.add_cookies(
        [{"name": cookie.key, "value": cookie.value, "url": server}]
    )
    return context


def _assert_no_horizontal_scroll(page: Page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def _save_week_data(database_engine) -> None:
    _save(database_engine, "staff_guest", _staff_values())
    _save(database_engine, "patient", _patient_values())


def _capture(page: Page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    screenshot = EVIDENCE / name
    page.screenshot(path=str(screenshot), full_page=True, caret="hide")
    screenshot.chmod(0o600)


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_overview_puts_templates_first_at_all_viewports(
    editor_app,
    editor_server,
    database_engine,
    browser: Browser,
    width: int,
    height: int,
) -> None:  # noqa: F811
    _save_week_data(database_engine)
    with _context(
        editor_app, database_engine, browser, editor_server, (width, height)
    ) as context:
        page = context.new_page()
        response = page.goto(f"/admin/vorlagen?week={DAY}")
        assert response is not None and response.status == 200
        expect(page.locator("h1")).to_have_text("Vorlagen")
        expect(page.locator("main")).to_have_attribute("data-layout", "standard")
        expect(page.locator('[aria-label="Bereich"]:visible')).to_have_count(1)
        first_template = page.locator("#output-cafeteria [data-current-template]")
        expect(first_template).to_be_visible()
        if width >= 1366:
            box = first_template.bounding_box()
            assert box is not None and box["y"] < height
        _assert_no_horizontal_scroll(page)
        _capture(page, f"vorlagen-regulaer-{width}x{height}.png")


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_overview_has_one_area_navigation_with_and_without_javascript(
    editor_app,
    editor_server,
    database_engine,
    browser: Browser,
    javascript: bool,
) -> None:  # noqa: F811
    _save_week_data(database_engine)
    with _context(
        editor_app,
        database_engine,
        browser,
        editor_server,
        (1366, 768),
        javascript=javascript,
    ) as context:
        page = context.new_page()
        page.goto(f"/admin/vorlagen?week={DAY}")
        expect(page.locator('[aria-label="Bereich"]:visible')).to_have_count(1)
        expect(page.locator("#output-cafeteria")).to_be_visible()
        page.locator("#output-patienten-tab").click()
        expect(page.locator("#output-patienten")).to_be_visible()
        _assert_no_horizontal_scroll(page)


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_editor_prioritises_form_and_one_primary_save_action(
    editor_app,
    editor_server,
    database_engine,
    browser: Browser,
    width: int,
    height: int,
) -> None:  # noqa: F811
    _save(database_engine, "patient", _patient_values())
    with _context(
        editor_app, database_engine, browser, editor_server, (width, height)
    ) as context:
        page = context.new_page()
        page.goto(f"/admin/vorlagen/patienten?week={DAY}")
        expect(page.get_by_role("button", name="Vorlage speichern", exact=True)).to_be_visible()
        expect(page.locator("main .btn-primary:visible")).to_have_count(1)
        expect(page.locator("[data-template-status-scope]")).to_contain_text(
            "Patienten-Wochenpläne"
        )
        expect(page.locator("details[data-template-activation] summary")).to_have_text(
            "Aktivieren"
        )
        expect(page.locator("details[data-template-versions] summary")).to_have_text(
            "Versionen"
        )
        expect(page.locator("details[data-template-more-actions] summary")).to_have_text(
            "Weitere Aktionen"
        )
        form = page.locator("form[data-template-properties]")
        expect(form).to_be_visible()
        expect(page.locator("details[data-template-appearance]")).not_to_have_attribute(
            "open", ""
        )
        expect(page.locator("details[data-template-texts]")).not_to_have_attribute(
            "open", ""
        )
        expect(page.locator("details[data-template-week-layout]")).not_to_have_attribute(
            "open", ""
        )
        if width >= 1366:
            box = form.bounding_box()
            assert box is not None and box["y"] < height
        _assert_no_horizontal_scroll(page)
        _capture(page, f"vorlagen-editor-regulaer-{width}x{height}.png")


def _assert_editor_target(request, family: str) -> dict[str, list[str]]:
    target = urlsplit(request.url)
    assert target.path == f"/admin/vorlagen/{family}"
    assert parse_qs(target.query) == {"week": [DAY], "template": ["standard"]}
    assert request.post_data is not None
    return parse_qs(request.post_data)


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_save_activate_and_load_version_keep_native_requests(
    editor_app,
    editor_server,
    database_engine,
    browser: Browser,
    javascript: bool,
) -> None:  # noqa: F811
    _save(database_engine, "patient", _patient_values())
    with _context(
        editor_app,
        database_engine,
        browser,
        editor_server,
        (1366, 768),
        javascript=javascript,
    ) as context:
        page = context.new_page()
        page.goto(f"/admin/vorlagen/patienten?week={DAY}")
        page.get_by_label("Vorlagenname", exact=True).fill("Ruhiger Wochenplan")
        with page.expect_request(lambda request: request.method == "POST") as sent:
            page.get_by_role("button", name="Vorlage speichern", exact=True).click()
        save = _assert_editor_target(sent.value, "patienten")
        assert save["action"] == ["save"]
        assert save["version"] == ["0"]
        assert save["revision"] == ["1"]
        assert save["name"] == ["Ruhiger Wochenplan"]

        expect(page.locator("[data-template-current-version]")).to_contain_text(
            "Version 2"
        )
        page.locator("details[data-template-activation] summary").click()
        with page.expect_request(lambda request: request.method == "POST") as sent:
            page.get_by_role("button", name="Diese Version aktivieren", exact=True).click()
        activate = _assert_editor_target(sent.value, "patienten")
        assert set(activate) == {"_csrf", "action", "version", "revision"}
        assert activate["action"] == ["activate"]
        assert activate["revision"] == ["2"]

        page.locator("details[data-template-versions] summary").click()
        with page.expect_request(lambda request: request.method == "POST") as sent:
            page.get_by_role(
                "button", name="Version 1 als neuen Entwurf laden", exact=True
            ).click()
        restore = _assert_editor_target(sent.value, "patienten")
        assert set(restore) == {"_csrf", "action", "version", "revision"}
        assert restore["action"] == ["restore"]
        assert restore["revision"] == ["1"]
        expect(page.locator("[data-template-current-version]")).to_contain_text(
            "Version 3"
        )
        _assert_no_horizontal_scroll(page)


def test_conflict_preserves_input_and_focuses_error_region(
    editor_app,
    editor_server,
    database_engine,
    browser: Browser,
) -> None:  # noqa: F811
    _save(database_engine, "patient", _patient_values())
    with _context(
        editor_app, database_engine, browser, editor_server, (1366, 768)
    ) as first, _context(
        editor_app,
        database_engine,
        browser,
        editor_server,
        (390, 844),
        javascript=False,
    ) as stale:
        current_page = first.new_page()
        stale_page = stale.new_page()
        route = f"/admin/vorlagen/patienten?week={DAY}"
        current_page.goto(route)
        stale_page.goto(route)
        current_page.get_by_label("Vorlagenname", exact=True).fill("Erste Sitzung")
        current_page.get_by_role("button", name="Vorlage speichern", exact=True).click()
        stale_page.get_by_label("Vorlagenname", exact=True).fill("Zweite Sitzung")
        with stale_page.expect_response(
            lambda response: response.request.method == "POST"
        ) as response:
            stale_page.get_by_role("button", name="Vorlage speichern", exact=True).click()
        assert response.value.status == 409
        expect(stale_page.get_by_label("Vorlagenname", exact=True)).to_have_value(
            "Zweite Sitzung"
        )
        expect(stale_page.locator(".error-region")).to_be_focused()
        _assert_no_horizontal_scroll(stale_page)
        _capture(stale_page, "vorlagen-editor-konflikt-390x844.png")


def test_empty_preview_and_zoom_200_remain_readable(
    editor_app,
    editor_server,
    database_engine,
    browser: Browser,
) -> None:  # noqa: F811
    with _context(
        editor_app, database_engine, browser, editor_server, (1366, 768)
    ) as context:
        page = context.new_page()
        page.goto(f"/admin/vorlagen/patienten?week={DAY}")
        expect(page.get_by_text("noch keine gespeicherten Menüs", exact=False)).to_be_visible()
        _assert_no_horizontal_scroll(page)
        _capture(page, "vorlagen-editor-leer-1366x768.png")

    with _context(
        editor_app,
        database_engine,
        browser,
        editor_server,
        (720, 450),
        device_scale_factor=2,
    ) as zoom_context:
        zoom_page = zoom_context.new_page()
        zoom_page.goto(f"/admin/vorlagen?week={DAY}")
        _assert_no_horizontal_scroll(zoom_page)
        _capture(zoom_page, "vorlagen-zoom-200-720x450.png")
