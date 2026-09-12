"""Browser contract for simplified areas and opening-hours settings."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Browser, expect

from cafeteria.admin import operations_routes  # noqa: F401 - blueprint registration
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_ui_brand_ops_browser import _assert_page_container_width, _create_context

OPS_PATH = '/admin/bereiche-zeiten'
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'ui-korrektur-0912' / 'ops'
VIEWPORTS = (
    (1366, 768, '1366x768'),
    (1920, 1080, '1920x1080'),
    (768, 1024, '768x1024'),
    (390, 844, '390x844'),
    (683, 384, '1366x768-zoom200'),
)
SCHEDULE_SLOTS = {
    'staff_guest': tuple((day, 'LUNCH') for day in range(1, 8)),
    'patient': tuple((day, meal) for day in range(1, 8) for meal in ('LUNCH', 'DINNER')),
}


def _shot(page, state: str, viewport: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.evaluate('window.scrollTo(0, 0)')
    page.screenshot(path=str(EVIDENCE / f'bereiche-zeiten-{state}-{viewport}.png'), full_page=True)


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


def _submit_and_capture(page, button_name: str) -> tuple[set[str], dict[str, list[str]]]:
    with page.expect_request(
        lambda request: request.method == 'POST' and urlparse(request.url).path == OPS_PATH,
    ) as request_info:
        page.get_by_role('button', name=button_name, exact=True).click()
    request = request_info.value
    assert urlparse(request.url).path == OPS_PATH
    assert request.method == 'POST'
    payload = parse_qs(request.post_data or '', keep_blank_values=True)
    return set(payload), payload


@pytest.mark.parametrize('width,height,viewport', VIEWPORTS)
def test_operations_puts_area_overview_before_collapsed_editors(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
    width: int, height: int, viewport: str,
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
        _assert_no_document_overflow(page)
        _shot(page, 'regulaer', viewport)


def test_operations_empty_exception_state_is_explicit(
    browser: Browser, live_server: str, admin_app, admin_engine,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1366, 'height': 768})
        page.goto(OPS_PATH)
        page.locator('#saved-exceptions > summary').click()
        expect(page.locator('#saved-exceptions')).to_have_attribute('open', '')
        expect(page.locator('#saved-exceptions')).to_contain_text('Keine gespeicherten Ausnahmen')
        _assert_no_document_overflow(page)
        _shot(page, 'leer', '1366x768')


@pytest.mark.parametrize('javascript', [False, True])
def test_operations_error_opens_affected_editor_and_preserves_input(
    browser: Browser, live_server: str, admin_app, admin_engine, javascript: bool,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _create_context(browser, live_server, client, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': 1366, 'height': 768})
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
            _shot(page, 'fehler', '1366x768')
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
        page.locator('#profile').select_option('patient')
        fields, payload = _submit_and_capture(page, 'Ausgabe laden')
        assert fields == {'_csrf', 'action', 'profile', 'date', 'meal'}
        assert payload['action'] == ['load_exception']

        fields, payload = _submit_and_capture(page, 'Ausnahme speichern')
        assert fields == {
            '_csrf', 'action', 'profile', 'date', 'meal', 'row_version', 'loaded',
            'service_state', 'service_start', 'service_end', 'notice',
        }
        assert payload['action'] == ['save_exception']
