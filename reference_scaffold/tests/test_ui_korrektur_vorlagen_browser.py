"""Browser contracts for simplified print-template overview and editor."""
# ruff: noqa: F811

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _login
from test_print_template_browser import browser, editor_server, _context as recipe_context  # noqa: F401
from test_print_template_routes import database_engine, editor_app  # noqa: F401
from test_recipe_template_editor_browser import recipe_server  # noqa: F401
from test_recipe_template_editor_routes import (  # noqa: F401
    BASE, recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine, example,
    path as recipe_path,
    state as recipe_state,
)
from test_ui_korrektur_cookbooks_browser import _native_viewport_capture


VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080), (2560, 1440), (320, 844)]
EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / ".claude/evidence/density-print-0913/after"
)


def _context(
    app,
    database_engine,
    browser: Browser,
    server: str,
    viewport: tuple[int, int],
    *,
    javascript: bool = True,
) -> BrowserContext:
    client, _ = _login(app, database_engine, ["Cafeteria.Admin"])
    cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"])
    assert cookie is not None
    context = browser.new_context(
        base_url=server,
        viewport={"width": viewport[0], "height": viewport[1]},
        java_script_enabled=javascript,
        reduced_motion="reduce",
        locale="de-CH", timezone_id="Europe/Zurich",
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


def _capture(page: Page, name: str, *, native=False) -> dict:
    page.evaluate("document.fonts.ready")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    screenshot = EVIDENCE / name
    proof = _native_viewport_capture(page, screenshot) if native else None
    if not native:
        page.screenshot(path=str(screenshot), full_page=True, caret="hide")
    screenshot.chmod(0o600)
    metrics = page.evaluate('''() => {
        const rect = selector => {
            const node = document.querySelector(selector);
            if (!node) return null;
            const {x, y, width, height} = node.getBoundingClientRect();
            return {x, y, width, height};
        };
        return {width: innerWidth, height: innerHeight, documentHeight: document.documentElement.scrollHeight,
            overflow: document.documentElement.scrollWidth > innerWidth + 1,
            main: rect('main'), properties: rect('[data-template-properties]'),
            name: rect('#template-name'), preview: rect('iframe'),
            openDetails: document.querySelectorAll('main details[open]').length};
    }''')
    if proof:
        metrics['native'] = proof
    screenshot.with_suffix('.json').write_text(json.dumps(metrics, indent=2))
    return metrics


def _assert_controls(page):
    _assert_no_horizontal_scroll(page)
    for control in page.locator('main :is(.btn, .form-control, .form-select, summary)').all():
        if not control.is_visible():
            continue
        box = control.bounding_box()
        assert box is not None and box['height'] >= 48
        if 'btn-icon' in (control.get_attribute('class') or '').split():
            assert box['width'] >= 48 and control.get_attribute('aria-label')
            assert any(control.get_attribute(name) for name in ('title', 'data-bs-original-title', 'data-bs-title'))
            control.focus()
            expect(control).to_be_focused()
    assert page.locator('main svg use').evaluate_all('''nodes => nodes.every(node =>
        node.getAttribute('href').startsWith('/static/vendor/tabler-icons/tabler-icons.svg#tabler-'))''')


@contextmanager
def _native_zoom(browser, server, client, tmp_path):
    cookie = client.get_cookie(client.application.config['SESSION_COOKIE_NAME'])
    with TemporaryDirectory(prefix='print-density-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True, base_url=server,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server}])
            yield page


def _assert_native_zoom(page):
    cdp = page.context.new_cdp_session(page)
    assert cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom'] == 2
    cdp.detach()
    assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
    assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'


def test_recipe_editor_density_matrix(recipe_editor, recipe_server, browser):
    recipe, revision, _ = example(recipe_editor)
    with recipe_context(browser, recipe_server, recipe_editor[2], 1440) as context:
        page = context.new_page()
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            for state, route in (('empty-selection', BASE), ('selected', recipe_path(recipe, revision.public_id))):
                assert page.goto(route).status == 200
                _assert_controls(page)
                for area in ('appearance', 'texts', 'activation', 'versions', 'more-actions'):
                    expect(page.locator(f'details[data-template-{area}]')).not_to_have_attribute('open', '')
                if state == 'selected':
                    expect(page.locator('[data-recipe-selection]')).not_to_have_attribute('open', '')
                    normal = page.get_by_role('link', name='PDF mit aktiver Vorlage öffnen', exact=True)
                    expect(normal).to_be_visible()
                    assert urlsplit(normal.get_attribute('href')).path == f'/admin/rezepte/{recipe}/revisionen/{revision.public_id}/druck.pdf'
                metrics = _capture(page, f'recipe-editor-{state}-{width}x{height}.png')
                assert metrics['properties']['height'] <= 560
                if state == 'selected' and width == 1440:
                    assert metrics['name']['y'] < 650 and metrics['documentHeight'] < 2200
                    assert normal.bounding_box()['y'] < 280
                if state == 'selected' and width == 390:
                    assert metrics['name']['y'] + metrics['name']['height'] <= height
                    assert metrics['documentHeight'] < 3000


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
    tmp_path,
) -> None:  # noqa: F811
    with _context(
        editor_app, database_engine, browser, editor_server, (1366, 768)
    ) as context:
        page = context.new_page()
        page.goto(f"/admin/vorlagen/patienten?week={DAY}")
        expect(page.get_by_text("noch keine gespeicherten Menüs", exact=False)).to_be_visible()
        _assert_no_horizontal_scroll(page)
        _capture(page, "vorlagen-editor-leer-1366x768.png")

    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    with _native_zoom(browser, editor_server, client, tmp_path) as page:
        for state, route in (('overview', f'/admin/vorlagen?week={DAY}'),
                             ('patient-editor', f'/admin/vorlagen/patienten?week={DAY}')):
            assert page.goto(route).status == 200
            _assert_native_zoom(page)
            _assert_controls(page)
            _capture(page, f'{state}-native-200.png', native=True)


def test_recipe_editor_native_200(recipe_editor, recipe_server, browser, tmp_path):
    recipe, revision, _ = example(recipe_editor)
    with _native_zoom(browser, recipe_server, recipe_editor[2], tmp_path) as page:
        assert page.goto(recipe_path(recipe, revision.public_id)).status == 200
        _assert_native_zoom(page)
        _assert_controls(page)
        _capture(page, 'recipe-editor-native-200-top.png', native=True)
        save = page.get_by_role('button', name='Entwurf speichern', exact=True)
        save.scroll_into_view_if_needed()
        save.focus()
        expect(save).to_be_focused()
        _assert_native_zoom(page)
        _capture(page, 'recipe-editor-native-200-save.png', native=True)


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_closed_recipe_details_keep_inputs_and_active_print(recipe_editor, recipe_server, browser, javascript):
    _, owner, client, _ = recipe_editor
    recipe, revision, _ = example(recipe_editor)
    route = recipe_path(recipe, revision.public_id)
    before = recipe_state(owner)
    with recipe_context(browser, recipe_server, client, 390, javascript=javascript) as context:
        page = context.new_page()
        page.goto(route)
        posts = []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        for area in ('appearance', 'texts'):
            summary = page.locator(f'[data-template-{area}] > summary')
            summary.focus()
            page.keyboard.press('Enter')
            expect(page.locator(f'[data-template-{area}]')).to_have_attribute('open', '')
        page.get_by_label('Druckschrift', exact=True).select_option('fira')
        page.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Mein gespeicherter Entwurf')
        form = page.locator('[data-template-properties]')
        form_data = form.evaluate('form => [...new FormData(form)]')
        for area in ('appearance', 'texts'):
            page.locator(f'[data-template-{area}] > summary').click()
        assert form.evaluate('form => [...new FormData(form)]') == form_data
        assert posts == [] and recipe_state(owner) == before
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            page.get_by_role('button', name='Entwurf speichern', exact=True).click()
        assert saved.value.status == 303
        sent = parse_qs(posts[0].post_data)
        assert sent['version'] == ['0'] and sent['revision'] == ['1']
        assert sent['font'] == ['fira'] and sent['header_text'] == ['Mein gespeicherter Entwurf']
        expect(page.locator('[data-template-status-scope]')).to_contain_text('Version 1 · Angezeigt: Version 2')
        expect(page.locator('[data-template-texts] > summary')).to_contain_text('Zusatztext vorhanden')
        normal = page.get_by_role('link', name='PDF mit aktiver Vorlage öffnen', exact=True)
        preview = page.get_by_role('link', name='Vorschau als PDF öffnen', exact=True)
        # As in the native PDF consumer, use the authenticated factory client:
        # APIRequestContext does not send Secure cookies on HTTP loopback.
        normal_pdf = client.get(normal.get_attribute('href'))
        preview_pdf = client.get(preview.get_attribute('href'))
        assert normal_pdf.status_code == preview_pdf.status_code == 200
        assert normal_pdf.headers['x-print-template-revision'] == 'standard:1'
        assert preview_pdf.headers['x-print-template-revision'] == 'standard:2'
        assert normal_pdf.data != preview_pdf.data
        page.locator('[data-template-versions] > summary').click()
        _assert_controls(page)
        _capture(page, f'recipe-editor-saved-details-{javascript}-390x1100.png')


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_field_error_opens_details_and_remains_marked_when_closed(
    editor_app, editor_server, database_engine, browser, javascript,
):
    with _context(editor_app, database_engine, browser, editor_server, (390, 844), javascript=javascript) as context:
        page = context.new_page()
        page.goto(f'/admin/vorlagen/patienten?week={DAY}')
        page.locator('[data-template-texts] > summary').click()
        page.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('CHF 10')
        page.locator('[data-template-texts] > summary').click()
        with page.expect_response(lambda response: response.request.method == 'POST') as response:
            page.get_by_role('button', name='Vorlage speichern', exact=True).click()
        assert response.value.status == 400
        expect(page.locator('[data-template-texts]')).to_have_attribute('open', '')
        expect(page.locator('#template-header_text')).to_have_value('CHF 10')
        expect(page.locator('#template-header_text')).to_have_attribute('aria-invalid', 'true')
        assert page.locator('[data-template-properties] input[name=version]').input_value() == '0'
        if javascript:
            expect(page.locator('.error-region')).to_be_focused()
        page.locator('[data-template-texts] > summary').click()
        expect(page.locator('[data-template-texts] > summary [data-admin-details-error]')).to_be_visible()
        _assert_controls(page)
        _capture(page, f'patient-editor-field-error-{javascript}-390x844.png')


@pytest.mark.parametrize('unavailable', [False, True], ids=['invalid-query', 'unavailable'])
def test_standalone_error_pages_keep_native_return_link(recipe_editor, recipe_server, browser, monkeypatch, unavailable):
    if unavailable:
        from cafeteria.admin import recipe_print_template_routes as routes
        from cafeteria.print_templates import PrintTemplateStateError

        def fail_document(*args):
            raise PrintTemplateStateError('Vorlagen nicht verfügbar')

        monkeypatch.setattr(routes, '_document', fail_document)
    with recipe_context(browser, recipe_server, recipe_editor[2], 1440, javascript=False) as context:
        page = context.new_page()
        for width, height in ((1440, 900), (390, 844)):
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto(BASE if unavailable else BASE + '?revision=0')
            assert response.status == (503 if unavailable else 400)
            expect(page.get_by_role('alert')).to_be_visible()
            link = page.get_by_role('link')
            expect(link).to_have_count(1)
            assert link.get_attribute('href') == ('/admin/vorlagen' if unavailable else BASE)
            link.focus()
            expect(link).to_be_focused()
            _assert_controls(page)
            _capture(page, f'recipe-template-error-{unavailable}-{width}x{height}.png')


def test_native_validation_reveals_closed_copy_form(recipe_editor, recipe_server, browser):
    with recipe_context(browser, recipe_server, recipe_editor[2], 390) as context:
        page = context.new_page()
        page.goto(BASE)
        posts = []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        details = page.locator('[data-template-more-actions]')
        expect(details).not_to_have_attribute('open', '')
        field = page.get_by_label('Name der Kopie', exact=True)
        # Exercise browser constraint validation while its required field is hidden.
        field.evaluate('field => { field.value = ""; field.form.requestSubmit(); }')
        expect(details).to_have_attribute('open', '')
        expect(field).to_be_focused()
        expect(field).to_have_attribute('data-admin-native-invalid', '')
        assert posts == []
        details.locator(':scope > summary').click()
        expect(details.locator('[data-admin-details-error]')).to_be_visible()
        _capture(page, 'recipe-editor-native-invalid-390x1100.png')
