"""Browser evidence for simplified screen and display administration."""
from __future__ import annotations

import base64
import json
import struct
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

EVIDENCE = Path(__file__).resolve().parents[2] / ".claude/evidence/card-visuals-0913/screens-consumer"
VIEWPORTS = [
    (1366, 768), (1920, 1080), (768, 1024), (390, 844),
    (1440, 900), (1024, 768), (2560, 1440), (320, 844),
]


def _assert_no_horizontal_scroll(page: Page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def _screenshot(page: Page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.evaluate("document.fonts.ready")
    page.screenshot(path=str(EVIDENCE / name), full_page=True)
    (EVIDENCE / name).with_suffix('.json').write_text(json.dumps({
        'path': urlsplit(page.url).path,
        'viewport': page.viewport_size,
        'geometry': page.evaluate('''() => ({
            innerWidth, innerHeight, pageHeight: document.documentElement.scrollHeight,
            firstActionY: document.querySelector('main .btn')?.getBoundingClientRect().y,
            firstSettingY: document.querySelector('main select')?.getBoundingClientRect().y
        })'''),
    }, indent=2))


def _assert_rendered_icons_and_targets(page: Page) -> None:
    icons = page.locator('main svg.icon:visible')
    assert icons.count() > 0
    assert icons.evaluate_all('''icons => icons.every(icon => {
        const box = icon.getBBox();
        return box.width > 0 && box.height > 0;
    })''')
    for target in page.locator('main .btn:visible, main summary:visible').all():
        box = target.bounding_box()
        assert box is not None and box['height'] >= 44 and box['width'] >= 44


@pytest.mark.parametrize(
    "width,height,javascript",
    [(width, height, True) for width, height in VIEWPORTS]
    + [(1440, 900, False), (390, 844, False)],
)
def test_lists_and_settings_come_first_at_required_viewports(
    published_hub_app,  # noqa: F811
    hub_server,  # noqa: F811
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    width: int,
    height: int,
    javascript: bool,
) -> None:
    context, page = _admin_page(
        published_hub_app,
        database_engine,
        browser,
        hub_server,
        viewport=(width, height),
        javascript=javascript,
    )
    try:
        assert page.goto("/admin/screens").status == 200
        expect(page.get_by_role("heading", level=1)).to_have_text("Bildschirme")
        expect(page.locator('nav[aria-label="Bereich"]')).to_have_count(0)
        expect(page.locator('.admin-statusbar-item')).to_have_count(2)
        expect(page.locator('main .btn-primary')).to_have_count(0)
        first_screen = page.locator(".screen-card").first.bounding_box()
        assert first_screen is not None and first_screen["y"] < height
        expect(page.get_by_text("Vorlage für Web-Wochenplan:", exact=False)).to_have_count(2)
        body = page.locator("main").inner_text().lower()
        assert "verbunden" not in body and "zuletzt gesehen" not in body
        expect(page.locator('.screen-preview-details[open]')).to_have_count(0)
        expect(page.locator('.screen-preview-details .screen-preview-signage')).to_have_count(4)
        first_action = page.locator('.screen-card .btn').first.bounding_box()
        assert first_action is not None and first_action['y'] < height
        assert first_action['y'] < page.locator('.screen-preview-details > summary').first.bounding_box()['y']
        expect(page.locator('.screen-status .badge')).to_have_text(['Vorgabe', 'Vorgabe'])
        _assert_no_horizontal_scroll(page)
        _assert_rendered_icons_and_targets(page)
        _screenshot(page, f"bildschirme-regulaer-{width}x{height}-{javascript}.png")

        assert page.goto("/admin/screens/cafeteria/wochenvorlage").status == 200
        expect(page.locator('.admin-statusbar')).to_contain_text('Vorgabe')
        expect(page.locator('.admin-statusbar')).to_contain_text('Wochenplan mit Bildern')
        expect(page.locator('#screen-assignment-version')).not_to_have_attribute('open', '')
        assignment = page.locator("#screen-assignment-details")
        expect(assignment).not_to_have_attribute("open", "")
        assert assignment.locator(":scope > summary").bounding_box()["y"] < height
        _assert_no_horizontal_scroll(page)
        _assert_rendered_icons_and_targets(page)
        _screenshot(page, f"vorlage-zuweisen-geschlossen-{width}x{height}-{javascript}.png")
        assignment.locator(':scope > summary').click()
        _assert_no_horizontal_scroll(page)
        _assert_rendered_icons_and_targets(page)
        for preview in assignment.locator('a[data-admin-icon-action]').all():
            tooltip_attribute = 'data-bs-original-title' if javascript else 'title'
            assert preview.get_attribute(tooltip_attribute) == preview.get_attribute('aria-label')
            assert preview.inner_text() == ''
        _screenshot(page, f"vorlage-zuweisen-offen-{width}x{height}-{javascript}.png")

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
        _assert_rendered_icons_and_targets(page)
        _screenshot(page, f"darstellung-regulaer-{width}x{height}-{javascript}.png")
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
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        summary = page.locator('#screen-assignment-details > summary')
        summary.click()
        summary.click()
        expect(page.locator(f'input[name="template_id"][value="{template_id}"]')).to_be_checked()
        assert posts == []
        with page.expect_request(
            lambda request: request.method == "POST"
        ) as submitted, page.expect_response(
            lambda response: response.request.method == "POST"
        ) as response:
            page.get_by_role("button", name="Speichern", exact=True).click()
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
        expect(page.locator('.admin-statusbar-item--success')).to_contain_text('Aktiv')
        page.locator('#screen-assignment-version > summary').click()
        expect(page.get_by_text('Zuordnung 1', exact=False)).to_be_visible()

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
            current.get_by_role("button", name="Speichern", exact=True).click()
        assert saved.value.status == 303
        with stale.expect_response(lambda response: response.request.method == "POST") as conflict:
            stale.get_by_role("button", name="Speichern", exact=True).click()
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


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_empty_and_unavailable_states_have_scoped_messages_and_evidence(
    empty_hub_app,  # noqa: F811
    empty_hub_server,  # noqa: F811
    database_engine,  # noqa: F811
    browser,  # noqa: F811
    javascript: bool,
    width: int,
    height: int,
) -> None:
    empty_context, empty = _admin_page(
        empty_hub_app,
        database_engine,
        browser,
        empty_hub_server,
        viewport=(width, height),
        javascript=javascript,
    )
    try:
        empty.goto("/admin/screens")
        empty.locator('.screen-preview-details > summary').first.click()
        expect(empty.frame_locator(".screen-preview iframe").first.get_by_text(
            "Speiseplan nicht verfügbar", exact=False
        )).to_be_visible()
        _assert_no_horizontal_scroll(empty)
        _screenshot(empty, f"bildschirme-leer-{width}x{height}-{javascript}.png")
    finally:
        empty_context.close()

    context, unavailable = _admin_page(
        empty_hub_app,
        database_engine,
        browser,
        empty_hub_server,
        viewport=(width, height),
        javascript=javascript,
    )
    unavailable.goto('/admin/screens/cafeteria/wochenvorlage')
    unavailable.locator('#screen-assignment-details > summary').click()
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
    try:
        with unavailable.expect_response(lambda response: response.request.method == 'POST') as failed:
            unavailable.get_by_role('button', name='Speichern', exact=True).click()
        assert failed.value.status == 503
        expect(unavailable.get_by_text('Der Abschluss der Zuweisung konnte nicht bestätigt werden.', exact=False)).to_be_visible()
        _assert_no_horizontal_scroll(unavailable)
        _screenshot(unavailable, f"vorlage-nicht-verfuegbar-post-{width}x{height}-{javascript}.png")
        response = unavailable.goto("/admin/screens/cafeteria/wochenvorlage")
        assert response.status == 503
        expect(unavailable.get_by_role("heading", level=1)).to_have_text(
            "Bildschirmvorlagen vorübergehend nicht verfügbar"
        )
        expect(unavailable.get_by_text("Die gespeicherte Bildschirmvorlage ist zurzeit nicht erreichbar.", exact=True)).to_be_visible()
        expect(unavailable.get_by_text('Es wurde keine neue Vorlage zugewiesen.', exact=False)).to_have_count(0)
        expect(unavailable.get_by_role('link', name='Aktualisieren')).to_have_attribute('href', '/admin/screens/cafeteria/wochenvorlage')
        _assert_no_horizontal_scroll(unavailable)
        _assert_rendered_icons_and_targets(unavailable)
        _screenshot(unavailable, f"vorlage-nicht-verfuegbar-{width}x{height}-{javascript}.png")
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
    tmp_path: Path,
) -> None:
    client, _ = _login(published_hub_app, database_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie(published_hub_app.config["SESSION_COOKIE_NAME"])
    assert cookie is not None
    with browser.browser_type.launch_persistent_context(
        str(tmp_path / 'density-screen-zoom'),
        channel='chromium', headless=True, no_viewport=True,
        locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
        args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
    ) as context:
        context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": hub_server}])
        page = context.pages[0]
        page.goto('chrome://settings/appearance')
        page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
        assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
        cdp = context.new_cdp_session(page)
        proof = {}
        for path, name in (
            ("/admin/screens", "bildschirme"),
            ("/admin/cafeteria?week=2026-08-31", "cafeteria"),
            ("/admin/screens/cafeteria/wochenvorlage", "vorlage-zuweisen"),
            ("/admin/design/darstellung", "darstellung"),
        ):
            assert page.goto(hub_server + path).status == 200
            metrics = cdp.send('Page.getLayoutMetrics')
            assert metrics['cssVisualViewport']['zoom'] == 2
            assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
            assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
            proof[name] = metrics
            if name == 'vorlage-zuweisen':
                page.locator('#screen-assignment-details > summary').click()
            if name == 'cafeteria':
                photo = page.locator('[data-menu-image] img').first
                expect(photo).to_be_visible()
                photo.scroll_into_view_if_needed()
                assert photo.evaluate('el => el.complete && el.naturalWidth > 0')
            if name == 'bildschirme':
                page.locator('.screen-preview-details').nth(1).locator(':scope > summary').click()
                preview = page.locator('.tab-pane.active .screen-preview-signage').first
                box = preview.bounding_box()
                assert box['width'] >= 220 and abs(box['width'] / box['height'] - 16 / 9) < .01
                preview.scroll_into_view_if_needed()
            _assert_no_horizontal_scroll(page)
            _assert_rendered_icons_and_targets(page)
            # Playwright full_page clips real browser zoom; capture the native viewport.
            page.evaluate('document.fonts.ready')
            capture = cdp.send('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
            png = base64.b64decode(capture['data'])
            pixels = struct.unpack('>II', png[16:24])
            assert pixels[0] == 1440 and pixels[1] >= 800
            proof[name]['capture_kind'] = 'native CDP viewport, not full page'
            proof[name]['capture_pixels'] = pixels
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            (EVIDENCE / f'{name}-zoom-200.png').write_bytes(png)
        cdp.detach()
        (EVIDENCE / 'zoom-probe.json').write_text(json.dumps(proof, indent=2))


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_native_disclosure_and_assignment_preview_are_keyboard_reachable(
    published_hub_app, hub_server, database_engine, browser, javascript,  # noqa: F811
) -> None:
    context, page = _admin_page(
        published_hub_app, database_engine, browser, hub_server, javascript=javascript,
        viewport=(390, 844),
    )
    try:
        page.goto('/admin/screens')
        page.keyboard.press('Tab')
        expect(page.locator('.skip-link')).to_be_focused()
        summary = page.locator('.screen-preview-details > summary').first
        summary.focus()
        page.keyboard.press('Enter')
        expect(page.locator('.screen-preview-details').first).to_have_attribute('open', '')
        expect(summary).to_be_focused()
        assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        _screenshot(page, f'bildschirme-tastatur-{javascript}.png')
        page.goto('/admin/screens/cafeteria/wochenvorlage')
        page.locator('#screen-assignment-details > summary').focus()
        page.keyboard.press('Enter')
        selected = page.locator('input[name=template_id]:checked')
        selected.focus()
        page.keyboard.press('Tab')
        preview = page.get_by_role('link', name='Wochenplan mit Bildern prüfen', exact=True)
        expect(preview).to_be_focused()
        assert preview.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        _assert_rendered_icons_and_targets(page)
        _screenshot(page, f'vorlage-zuweisen-tastatur-{javascript}.png')
    finally:
        context.close()
