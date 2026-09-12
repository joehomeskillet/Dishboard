"""Browser verification for MP-UI-OUTPUT-HUBS routes and matrix states."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from wsgiref.simple_server import make_server

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

from cafeteria.branding_config import contrast
from cafeteria.menu_images import CATALOG
from cafeteria.public import routes as public_routes
from cafeteria.screen_templates import key
from cafeteria.workflow import publish_draft
from test_admin_workflow_db import (
    WEEK_START,
    _actor_id,
    _patient_values,
    _save_reviewed,
    _staff_values,
)
from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_screen_template_routes import screen_app as screen_app  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL fehlt.")

VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080)]


@pytest.fixture
def published_hub_app(screen_app, database_engine):  # noqa: F811
    image = next(
        item for item in json.loads(CATALOG.read_text()) if item["status"] == "ready"
    )
    snapshots = {}
    for profile, values in [
        ("staff_guest", _staff_values()),
        ("patient", _patient_values()),
    ]:
        option = values["days"][0]["services"][0]["options"][0]
        option.update(title=image["title"], components=image["components"])
        version = _save_reviewed(database_engine, profile, values)
        snapshots[profile] = publish_draft(
            database_engine,
            profile,
            WEEK_START,
            expected_row_version=version,
            actor_id=_actor_id(database_engine),
            issuer_engine=database_engine,
        )
    screen_app.config["S1_PUBLISHED_SNAPSHOTS"] = snapshots
    return screen_app


def _hub_server(app):
    http = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}"
    finally:
        http.shutdown()
        thread.join(timeout=5)
        http.server_close()


@pytest.fixture
def hub_server(published_hub_app):
    yield from _hub_server(published_hub_app)


@pytest.fixture
def empty_hub_app(screen_app, monkeypatch):
    monkeypatch.setattr(public_routes, "active_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(public_routes, "published_snapshot", lambda profile: None)
    return screen_app


@pytest.fixture
def empty_hub_server(empty_hub_app):
    yield from _hub_server(empty_hub_app)


def _admin_page(
    app, db_engine, pw_browser, base_url, javascript=True, viewport=(1440, 900)
):
    client, _ = _login(app, db_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"])
    assert cookie is not None
    context = pw_browser.new_context(
        base_url=base_url,
        viewport={"width": viewport[0], "height": viewport[1]},
        java_script_enabled=javascript,
        reduced_motion="reduce",
    )
    context.add_cookies(
        [{"name": cookie.key, "value": cookie.value, "url": base_url}]
    )
    return context, context.new_page()


def _check_contrast(page: Page) -> None:
    styles = page.evaluate("""() => {
        const hex = color => '#' + (color.match(/[\\d.]+/g) || [0,0,0]).slice(0, 3)
            .map(n => Math.round(Number(n)).toString(16).padStart(2, '0')).join('');
        return [...document.querySelectorAll('main .btn-primary, main .form-label, main .card-title')].map(e => {
            const s = getComputedStyle(e);
            let parent = e;
            while (parent.parentElement && ['transparent', 'rgba(0, 0, 0, 0)'].includes(getComputedStyle(parent).backgroundColor)) {
                parent = parent.parentElement;
            }
            return {
                id: e.id || e.className,
                color: hex(s.color),
                background: hex(getComputedStyle(parent).backgroundColor)
            };
        });
    }""")
    for item in styles:
        ratio = contrast(item["color"], item["background"])
        assert ratio >= 4.5, f"Contrast {ratio} too low for {item}"


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_output_hubs_viewports_and_layouts(
    published_hub_app,
    hub_server,
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    width,
    height,
    tmp_path: Path,  # noqa: F811
) -> None:
    context, page = _admin_page(
        published_hub_app,
        database_engine,
        browser,
        hub_server,
        viewport=(width, height),
    )
    try:
        res_screens = page.goto("/admin/screens")
        assert res_screens is not None and res_screens.status == 200
        expect(page.locator("h1")).to_have_text("Screens")
        expect(page.locator("main")).to_have_attribute("data-layout", "standard")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        _check_contrast(page)
        page.screenshot(
            path=str(tmp_path / f"screens-{width}x{height}.png"), full_page=True
        )

        # 2. /admin/vorlagen
        res_vorlagen = page.goto("/admin/vorlagen")
        assert res_vorlagen is not None and res_vorlagen.status == 200
        expect(page.locator("h1")).to_have_text("Vorlagen")
        expect(page.locator("main")).to_have_attribute("data-layout", "standard")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        _check_contrast(page)
        page.screenshot(
            path=str(tmp_path / f"vorlagen-{width}x{height}.png"), full_page=True
        )

        # 3. /admin/screens/cafeteria/wochenvorlage
        res_assign = page.goto("/admin/screens/cafeteria/wochenvorlage")
        assert res_assign is not None and res_assign.status == 200
        expect(page.locator("h1")).to_have_text("Wochenvorlage zuordnen")
        expect(page.locator("main")).to_have_attribute("data-layout", "standard")
        expect(page.locator(".breadcrumb")).to_contain_text("Screens")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        cards = page.locator(".screen-choice-card").evaluate_all(
            "els => els.map(el => {const b=el.getBoundingClientRect(); return [b.width, b.height]})"
        )
        assert len(cards) == 2
        assert (
            abs(cards[0][0] - cards[1][0]) <= 1 and abs(cards[0][1] - cards[1][1]) <= 1
        )
        _check_contrast(page)
        page.screenshot(
            path=str(tmp_path / f"assignment-{width}x{height}.png"), full_page=True
        )
    finally:
        context.close()


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_output_hubs_keyboard_and_zoom_200(
    published_hub_app,
    hub_server,
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    javascript,
    tmp_path: Path,  # noqa: F811
) -> None:
    client, _ = _login(published_hub_app, database_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie(published_hub_app.config["SESSION_COOKIE_NAME"])
    assert cookie is not None

    with browser.new_context(
        base_url=hub_server,
        viewport={"width": 1440, "height": 900},
        java_script_enabled=javascript,
        reduced_motion="reduce",
    ) as context:
        context.add_cookies(
            [{"name": cookie.key, "value": cookie.value, "url": hub_server}]
        )
        page = context.new_page()

        # Keyboard checks on assignment page
        page.goto("/admin/screens/cafeteria/wochenvorlage")
        for control in page.locator("main :is(.btn, .screen-choice-control)").all():
            box = control.bounding_box()
            assert box is not None and box["height"] >= 48

        for control in page.locator("main :is(.btn, .form-check-input)").all():
            control.focus()
            expect(control).to_be_focused()
            has_focus_style = control.evaluate(
                "el => { const s = getComputedStyle(el); return s.boxShadow !== 'none' || "
                "(s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0); }"
            )
            assert has_focus_style

        # Zoom 200% check: half CSS viewport and DPR 2
        with browser.new_context(
            base_url=hub_server,
            viewport={"width": 720, "height": 450},
            device_scale_factor=2,
            java_script_enabled=javascript,
            reduced_motion="reduce",
        ) as zoom_ctx:
            zoom_ctx.add_cookies(
                [{"name": cookie.key, "value": cookie.value, "url": hub_server}]
            )
            zoom_page = zoom_ctx.new_page()

            for route, name in [
                ("/admin/screens", "screens"),
                ("/admin/vorlagen", "vorlagen"),
                ("/admin/screens/cafeteria/wochenvorlage", "assign"),
            ]:
                zoom_page.goto(route)
                assert zoom_page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth + 1"
                )
                zoom_page.screenshot(
                    path=str(tmp_path / f"zoom-200-{name}-js-{javascript}.png"),
                    full_page=True,
                )


def test_output_hubs_matrix_error_and_conflict_states(
    published_hub_app,
    hub_server,
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    tmp_path: Path,  # noqa: F811
) -> None:
    client, _ = _login(published_hub_app, database_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie(published_hub_app.config["SESSION_COOKIE_NAME"])
    assert cookie is not None

    with browser.new_context(
        base_url=hub_server,
        viewport={"width": 1440, "height": 900},
        java_script_enabled=True,
    ) as context:
        context.add_cookies(
            [{"name": cookie.key, "value": cookie.value, "url": hub_server}]
        )
        page = context.new_page()

        # State: invalid query parameters -> 400
        assert page.goto("/admin/screens?bad=1").status == 400
        assert page.goto("/admin/vorlagen?week=invalid").status == 400
        assert page.goto("/admin/screens/cafeteria/wochenvorlage?bad=1").status == 400

        # State: access_denied_401 (unauthenticated)
        unauth_ctx = browser.new_context(base_url=hub_server)
        unauth_page = unauth_ctx.new_page()
        for path in (
            "/admin/screens",
            "/admin/vorlagen",
            "/admin/screens/cafeteria/wochenvorlage",
        ):
            assert unauth_page.goto(path).status == 401
        unauth_ctx.close()

        # State: conflict_409 on assignment using stale session
        stale = context.new_page()
        route = "/admin/screens/cafeteria/wochenvorlage"
        page.goto(route)
        stale.goto(route)
        token = stale.locator('[name="_form_context"]').input_value()

        page.get_by_role(
            "radio", name="Wochenplan ohne Bilder auswählen", exact=True
        ).check()
        with page.expect_response(lambda r: r.request.method == "POST") as res:
            page.get_by_role("button", name="Auswahl aktivieren", exact=True).click()
        assert res.value.status == 303

        stale.get_by_role(
            "radio", name="Wochenplan ohne Bilder auswählen", exact=True
        ).check()
        with stale.expect_response(lambda r: r.request.method == "POST") as res:
            stale.get_by_role("button", name="Auswahl aktivieren", exact=True).click()
        assert res.value.status == 409
        expect(stale.locator('[name="_form_context"]')).to_have_value(token)
        expect(stale.locator('[name="version"]')).to_have_value("0")
        expect(stale.get_by_role("alert")).to_be_focused()
        assert stale.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        stale.screenshot(path=str(tmp_path / "conflict-409.png"), full_page=True)
        stale.close()

        # State: access_denied_403 (editor has no write capability)
        editor_client, _ = _login(
            published_hub_app, database_engine, ["Cafeteria.Editor"]
        )
        editor_cookie = editor_client.get_cookie(
            published_hub_app.config["SESSION_COOKIE_NAME"]
        )
        context.clear_cookies()
        context.add_cookies(
            [
                {
                    "name": editor_cookie.key,
                    "value": editor_cookie.value,
                    "url": hub_server,
                }
            ]
        )
        page.goto("/admin/screens/cafeteria/wochenvorlage")
        expect(page.locator(".alert-info")).to_contain_text(
            "Zum Aktivieren ist eine Admin-Berechtigung erforderlich"
        )

        # State: unavailable_503
        with database_engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE cafeteria.settings SET setting_value = CAST('{\"schema_version\": 999}' AS jsonb) "
                    "WHERE setting_key = :k"
                ),
                {"k": key("staff_guest")},
            )
        res_503 = page.goto("/admin/screens/cafeteria/wochenvorlage")
        assert res_503.status == 503
        expect(page.locator("h1")).to_have_text(
            "Screen-Vorlagen vorübergehend nicht verfügbar"
        )
        expect(page.get_by_role("alert")).to_be_visible()
        page.screenshot(path=str(tmp_path / "unavailable-503.png"), full_page=True)


@pytest.mark.parametrize(
    "route,title,empty_text,focus_role",
    [
        ("/admin/screens", "Screens", "Speiseplan nicht verfügbar", "iframe"),
        ("/admin/vorlagen", "Vorlagen", "veröffentlichten Plan", "tab"),
        (
            "/admin/screens/cafeteria/wochenvorlage",
            "Wochenvorlage zuordnen",
            "Ohne Veröffentlichung erscheint ein Hinweis",
            "radio",
        ),
    ],
)
def test_output_hubs_matrix_empty_states(
    empty_hub_app,
    empty_hub_server,
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    tmp_path,
    route,
    title,
    empty_text,
    focus_role,
) -> None:
    context, page = _admin_page(empty_hub_app, database_engine, browser, empty_hub_server)
    try:
        assert page.goto(route).status == 200
        expect(page.locator("h1")).to_have_text(title)
        if focus_role == "iframe":
            frame = page.frame_locator(".screen-preview iframe").first
            expect(frame.locator("body")).to_be_attached()
            expect(frame.get_by_text(empty_text, exact=False)).to_be_visible()
            focus_target = page.locator(".screen-card .nav-link").first
        elif focus_role == "tab":
            page.locator(".tab-pane.active .output-more-actions > summary").click()
            expect(page.get_by_text(empty_text, exact=False).first).to_be_visible()
            focus_target = page.locator(".output-area-tabs .nav-link").first
        else:
            expect(page.get_by_text(empty_text, exact=False)).to_be_visible()
            focus_target = page.get_by_role(focus_role).first
        focus_target.focus()
        expect(focus_target).to_be_focused()
        page.screenshot(path=str(tmp_path / f"empty-{route.strip('/').replace('/', '-')}.png"), full_page=True)
    finally:
        context.close()
