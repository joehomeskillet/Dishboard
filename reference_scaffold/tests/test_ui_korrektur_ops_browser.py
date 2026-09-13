"""Browser contract for compact areas and opening-hours settings (M15/M19)."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Browser, expect

from cafeteria.admin import operations_routes  # noqa: F401 - blueprint registration
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_ui_brand_ops_browser import (
    _assert_no_overflow_and_min_targets,
    _assert_page_container_width,
    _create_context,
)

OPS_PATH = '/admin/bereiche-zeiten'
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'density-settings-0913' / 'after'
DENSITY_VIEWPORTS = (
    (1440, 900),
    (390, 844),
    (1024, 768),
    (768, 1024),
    (1920, 1080),
    (2560, 1440),
    (320, 844),
)
SCHEDULE_SLOTS = {
    'staff_guest': tuple((day, 'LUNCH') for day in range(1, 8)),
    'patient': tuple((day, meal) for day in range(1, 8) for meal in ('LUNCH', 'DINNER')),
}


def _shot(page, state: str, viewport: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.evaluate('window.scrollTo(0, 0)')
    page.evaluate('document.fonts.ready')
    _assert_no_document_overflow(page)
    destination = EVIDENCE / f'bereiche-zeiten-{state}-{viewport}.png'
    page.screenshot(path=str(destination), full_page=True)
    destination.with_suffix('.json').write_text(json.dumps({
        'route': page.url,
        'viewport': page.viewport_size,
        'geometry': page.evaluate('({innerWidth,innerHeight,outerWidth,outerHeight,devicePixelRatio})'),
    }, indent=2))


def _assert_no_document_overflow(page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')


def _expected_schedule_fields(profile: str) -> set[str]:
    fields = {'_csrf', 'action', 'profile', 'revision'}
    fields.update(
        f'slot_{day}_{meal}_{part}'
        for day, meal in SCHEDULE_SLOTS[profile]
        for part in ('state', 'start', 'end', 'notice')
    )
    return fields


def _submit_and_capture(page, button_name: str, *, form_id: str | None = None) -> tuple[set[str], dict[str, list[str]]]:
    with page.expect_request(
        lambda request: request.method == 'POST' and urlparse(request.url).path == OPS_PATH,
    ) as request_info:
        target = page.locator(f'#{form_id}') if form_id else page
        target.get_by_role('button', name=button_name, exact=True).click()
    request = request_info.value
    assert urlparse(request.url).path == OPS_PATH
    assert request.method == 'POST'
    payload = parse_qs(request.post_data or '', keep_blank_values=True)
    return set(payload), payload


@pytest.mark.parametrize('width,height', DENSITY_VIEWPORTS)
def test_operations_puts_area_overview_before_collapsed_editors(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
    width: int, height: int,
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(OPS_PATH)
        assert response is not None and response.status == 200

        expect(page.locator('.admin-area-tabs')).to_have_count(1)
        expect(page.locator('#operations-overview')).to_be_visible()
        expect(page.locator('#operations-overview tbody tr')).to_have_count(2)
        expect(page.locator('#operations-overview')).to_contain_text(
            'Wochenendbetrieb für neue Ausgaben',
        )
        expect(page.locator('#operations-overview')).to_contain_text(
            'Wochenvorgaben für neue Ausgaben',
        )
        first_row = page.locator('#operations-overview tbody tr').first
        expect(first_row).to_be_visible()
        box = first_row.bounding_box()
        assert box is not None and box['y'] < height

        details = page.locator('main details.operations-editor')
        assert details.count() >= 6
        assert page.locator('main details.operations-editor[open]').count() == 0
        assert page.locator('main form').evaluate_all(
            "forms => forms.every(form => form.closest('details.operations-editor'))",
        )
        assert page.locator('main form').evaluate_all(
            "forms => forms.every(form => form.querySelectorAll('button[type=submit]').length === 1)",
        )
        overview_box = page.locator('#operations-overview').bounding_box()
        first_editor_box = details.first.bounding_box()
        assert overview_box is not None and first_editor_box is not None
        assert overview_box['y'] < first_editor_box['y']

        _assert_page_container_width(page, width)
        _assert_no_overflow_and_min_targets(page)
        _shot(page, 'regulaer', f'{width}x{height}')


def test_operations_saved_summary_shows_missing_times_not_recorded(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(OPS_PATH)
        overview = page.locator('#operations-overview')
        expect(overview).to_contain_text('Zeiten nicht eingetragen')
        expect(overview).to_contain_text('Offene Ausgaben ohne Zeit: Zeiten nicht eingetragen.')
        expect(overview).not_to_contain_text('Standardzeiten')

        rows = overview.locator('tbody tr')
        expect(rows).to_have_count(2)

        staff_row = rows.first
        monday_staff = staff_row.locator('li').filter(has_text='Montag · Mittag')
        expect(monday_staff).to_contain_text('Offen · Zeiten nicht eingetragen')
        saturday_staff = staff_row.locator('li').filter(has_text='Samstag · Mittag')
        expect(saturday_staff).to_contain_text('Geschlossen')
        expect(saturday_staff).not_to_contain_text('Zeiten nicht eingetragen')

        patient_row = rows.nth(1)
        monday_patient = patient_row.locator('li').filter(has_text='Montag · Mittag')
        expect(monday_patient).to_contain_text('Offen · Zeiten nicht eingetragen')
        saturday_patient = patient_row.locator('li').filter(has_text='Samstag · Mittag')
        expect(saturday_patient).to_contain_text('Offen · Zeiten nicht eingetragen')


def test_operations_empty_exception_state_is_explicit(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(OPS_PATH)
        page.locator('#saved-exceptions > summary').click()
        expect(page.locator('#saved-exceptions')).to_have_attribute('open', '')
        expect(page.locator('#saved-exceptions')).to_contain_text('Keine gespeicherten Ausnahmen')
        _assert_no_document_overflow(page)
        _shot(page, 'leer', '1440x900')


@pytest.mark.parametrize('javascript', [False, True])
def test_operations_error_opens_affected_editor_and_preserves_input(
    browser: Browser, live_server: str, admin_app, admin_engine, javascript: bool,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(OPS_PATH)
        page.locator('#schedule-editor-staff_guest > summary').click()
        page.locator('#staff_guest-slot_6_LUNCH_state').select_option('open')
        page.locator('#staff_guest-slot_6_LUNCH_start').fill('14:00')
        page.locator('#staff_guest-slot_6_LUNCH_end').fill('13:00')
        page.get_by_role('button', name='Wochenvorgaben speichern', exact=True).click()

        expect(page.locator('#schedule-editor-staff_guest')).to_have_attribute('open', '')
        expect(page.locator('#staff_guest-slot_6_LUNCH_start')).to_have_value('14:00')
        expect(page.locator('#staff_guest-slot_6_LUNCH_end')).to_have_attribute(
            'aria-invalid', 'true',
        )
        if javascript:
            expect(page.locator('.error-region')).to_be_focused()
            _shot(page, 'fehler', '1440x900')
        else:
            expect(page.locator('#staff_guest-slot_6_LUNCH_end')).to_be_focused()


@pytest.mark.parametrize('javascript', [False, True])
def test_operations_requests_keep_original_form_contracts(
    browser: Browser, live_server: str, admin_app, admin_engine, javascript: bool,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client, javascript=javascript) as context:
        page = context.new_page()
        page.goto(OPS_PATH)

        page.locator('#area-name-editor-staff_guest > summary').click()
        fields, payload = _submit_and_capture(page, 'Anzeigename speichern')
        assert fields == {'_csrf', 'action', 'expected_staff_guest', 'name_staff_guest'}
        assert payload['action'] == ['save_name_staff_guest']

        page.locator('#weekend-editor > summary').click()
        page.locator('#allows_weekend').check()
        fields, payload = _submit_and_capture(page, 'Wochenendbetrieb speichern')
        assert fields == {'_csrf', 'action', 'expected_allows_weekend', 'allows_weekend'}
        assert payload['action'] == ['save_weekend']

        for profile in ('staff_guest', 'patient'):
            page.locator(f'#schedule-editor-{profile} > summary').click()
            fields, payload = _submit_and_capture(page, 'Wochenvorgaben speichern')
            assert fields == _expected_schedule_fields(profile)
            assert payload['action'] == ['save_schedule']
            assert payload['profile'] == [profile]

        page.locator('#exception-editor > summary').click()
        fields, payload = _submit_and_capture(page, 'Ausgabe laden', form_id='exception-load-patient')
        assert fields == {'_csrf', 'action', 'profile', 'date', 'meal'}
        assert payload['action'] == ['load_exception']

        fields, payload = _submit_and_capture(page, 'Ausnahme speichern')
        assert fields == {
            '_csrf', 'action', 'profile', 'date', 'meal', 'row_version', 'loaded',
            'service_state', 'service_start', 'service_end', 'notice',
        }
        assert payload['action'] == ['save_exception']


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
@pytest.mark.parametrize('width', [390, 1440])
def test_profile_bound_exception_forms_work_without_javascript(
    browser, live_server, admin_app, admin_engine, profile, width, tmp_path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client, javascript=False) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': 900})
        page.goto(OPS_PATH)
        page.locator('#exception-editor > summary').click()
        assert page.locator('[id]').evaluate_all(
            'nodes => new Set(nodes.map(node => node.id)).size === nodes.length',
        )
        form_id = 'exception-load' if profile == 'staff_guest' else 'exception-load-patient'
        form = page.locator(f'#{form_id}')
        expect(form.get_by_role('heading')).to_be_visible()
        form.locator('[name=date]').fill('2026-08-31')
        form.locator('[name=meal]').select_option('LUNCH')
        _assert_no_document_overflow(page)
        page.screenshot(path=str(tmp_path / f'operations-scoped-{profile}-{width}.png'), full_page=True)
        fields, payload = _submit_and_capture(page, 'Ausgabe laden', form_id=form_id)
        assert fields == {'_csrf', 'action', 'profile', 'date', 'meal'}
        assert payload['profile'] == [profile]
        expect(page.locator('#exception-save [name=profile]')).to_have_value(profile)
        page.locator('#service_start').fill('11:30')
        page.locator('#service_end').fill('13:30')
        page.get_by_role('button', name='Ausnahme speichern', exact=True).click()
        page.locator('#saved-exceptions > summary').click()
        expect(page.locator('#saved-exceptions')).to_contain_text('11:30–13:30')


def test_operations_keyboard_focus_reaches_native_controls(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(OPS_PATH)

        page.keyboard.press('Tab')
        expect(page.locator('.skip-link')).to_be_focused()

        page.locator('#weekend-editor > summary').click()
        page.locator('#allows_weekend').focus()
        expect(page.locator('#allows_weekend')).to_be_focused()
        outline = page.locator('#allows_weekend').evaluate('el => getComputedStyle(el).outlineColor')
        assert outline != 'rgba(0, 0, 0, 0)'


def test_operations_density_reflow_and_zoom_probe(
    browser: Browser, live_server: str, admin_app, admin_engine, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.goto(OPS_PATH)
        for width, height in DENSITY_VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            _assert_no_document_overflow(page)
            _assert_no_overflow_and_min_targets(page)
            expect(page.locator('#operations-overview')).to_be_visible()

    profile_dir = tmp_path / 'density-zoom-profile'
    profile_dir.mkdir(parents=True, exist_ok=True)
    with browser.browser_type.launch_persistent_context(
        str(profile_dir),
        channel='chromium',
        headless=True,
        no_viewport=True,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        reduced_motion='reduce',
        args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
    ) as zoom_context:
        zoom_page = zoom_context.pages[0]
        zoom_page.goto('chrome://settings/appearance')
        zoom_page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
        assert zoom_page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
        cookie = client.get_cookie('session')
        assert cookie is not None
        zoom_context.add_cookies([{
            'name': 'session', 'value': cookie.value, 'url': live_server,
        }])
        zoom_page.goto(live_server + OPS_PATH)
        cdp = zoom_context.new_cdp_session(zoom_page)
        metrics = cdp.send('Page.getLayoutMetrics')
        assert metrics['cssVisualViewport']['zoom'] == 2
        assert zoom_page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
        assert zoom_page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
        _assert_no_document_overflow(zoom_page)
        _assert_no_overflow_and_min_targets(zoom_page)
        _shot(zoom_page, 'regulaer', 'zoom-probe-1440x900')
        cdp.detach()

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'zoom-probe.txt').write_text('chrome-settings-cdp-zoom-2\n', encoding='utf-8')
    (EVIDENCE / 'zoom-probe.json').write_text(json.dumps({
        'zoom': 2,
        'metrics': metrics,
        'geometry': {'innerWidth': 720, 'outerWidth': 1440, 'devicePixelRatio': 2},
    }, indent=2), encoding='utf-8')
