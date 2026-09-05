from __future__ import annotations

import re
from urllib.parse import parse_qs

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_db import _patient_values, _save, _save_reviewed, _staff_values
from test_admin_workflow_routes import DAY, DATABASE_URL

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

VIEWPORTS = ((360, 800), (768, 1024), (820, 1180), (1024, 768), (1199, 800), (1200, 800), (1280, 800))


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_week_overviews_extend_tabler_base_and_load_assets(page_context: Page, family: str) -> None:  # noqa: F811
    page = page_context
    response = page.goto(f'/admin/{family}?week={DAY}')
    assert response is not None and response.status == 200
    assert page.locator('.page').count() == 1
    assert page.locator('aside.navbar-vertical.admin-sidebar').count() == 1
    assert page.locator('main#main-content.page-wrapper.admin-main').count() == 1
    assert page.locator('link[href$="vendor/tabler/tabler.min.css"]').count() == 1
    assert page.locator('link[href$="admin-week-tabler.css"]').count() == 1
    assert page.locator('link[href$="/app.css"]').count() == 0
    assert page.locator('script[src$="vendor/tabler/tabler.min.js"]').count() == 1
    if family == 'cafeteria':
        assert page.locator('article.admin-day-card').count() == 5
    else:
        assert page.locator('article.patient-admin-day.card').count() == 7
    assert page.locator('[style], script:not([src])').count() == 0


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_week_overview_sidebar_and_main_layout_at_desktop(page_context: Page, admin_engine, family: str) -> None:  # noqa: F811
    _save(admin_engine, 'staff_guest', _staff_values())
    _save(admin_engine, 'patient', _patient_values())
    page = page_context
    page.set_viewport_size({'width': 1280, 'height': 800})
    assert page.goto(f'/admin/{family}?week={DAY}').status == 200
    sidebar = page.locator('aside.admin-sidebar').bounding_box()
    main = page.locator('main.admin-main').bounding_box()
    assert sidebar is not None and main is not None
    assert main['y'] < 120
    assert main['x'] >= sidebar['x'] + sidebar['width'] - 1
    expect(page.get_by_role('navigation', name='Backend')).to_be_visible()
    expect(page.get_by_role('button', name='Menü', exact=True)).to_be_hidden()


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize(('width', 'height'), VIEWPORTS)
def test_week_overview_responsive_matrix_without_horizontal_overflow(
    page_context: Page, admin_engine, family: str, width: int, height: int,  # noqa: F811
    tmp_path,
) -> None:
    _save(admin_engine, 'staff_guest', _staff_values())
    _save(admin_engine, 'patient', _patient_values())
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(f'/admin/{family}?week={DAY}')
    toggle = page.get_by_role('button', name='Menü', exact=True)
    nav = page.get_by_role('navigation', name='Backend')
    if width < 1200:
        expect(toggle).to_be_visible()
        if toggle.get_attribute('aria-expanded') == 'true':
            toggle.click()
        expect(nav).to_be_hidden()
    else:
        expect(toggle).to_be_hidden()
        expect(nav).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width
    for control in page.locator(
        '.admin-week-controls .btn, .admin-overview-form .form-control, .admin-overview-form .btn, '
        '.admin-week-service .form-select, .admin-week-service .form-control, .menu-slot .btn',
    ).all():
        box = control.bounding_box()
        assert box is not None and box['height'] >= 48, control.evaluate('(el) => el.outerHTML')
    if width in (360, 1280):
        page.screenshot(path=str(tmp_path / f'{family}-week-overview-{width}.png'))
        page.locator('.admin-day-card, .patient-admin-day').first.screenshot(
            path=str(tmp_path / f'{family}-week-day-{width}.png'),
        )


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_week_review_link_points_to_saved_week(page_context: Page, family: str) -> None:  # noqa: F811
    page = page_context
    page.goto(f'/admin/{family}?week={DAY}')
    review_links = page.locator(f'a[href="/admin/{family}/wochen/pruefung?week={DAY}"]')
    assert review_links.count() >= 2
    expect(review_links.first).to_be_visible()


def test_cafeteria_day_cards_use_two_column_menu_layout(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 768, 'height': 1024})
    page.goto(f'/admin/cafeteria?week={DAY}')
    first_day = page.locator('article.admin-day-card').first
    slots = first_day.locator('.menu-slot')
    assert slots.count() == 2
    first_box = slots.nth(0).bounding_box()
    second_box = slots.nth(1).bounding_box()
    assert first_box is not None and second_box is not None
    assert abs(first_box['y'] - second_box['y']) < 2


def test_patient_overview_has_no_cost_vocabulary(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.goto(f'/admin/patienten?week={DAY}')
    assert re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I) is None


@pytest.mark.parametrize('family,profile,values', [
    ('cafeteria', 'staff_guest', _staff_values), ('patienten', 'patient', _patient_values),
])
@pytest.mark.parametrize('width', [360, 1280])
def test_publish_modal_shows_summary_and_submits_exact_form(
    page_context: Page, admin_app: Flask, family: str, profile: str, values, width: int,  # noqa: F811
    tmp_path,
) -> None:  # noqa: F811
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, values())
    page = page_context
    page.set_default_timeout(3000)
    page.set_viewport_size({'width': width, 'height': 800})
    page.goto(f'/admin/{family}?week={DAY}')
    publish_form = page.locator(f'form[action="/admin/{family}/publish"]')
    assert publish_form.count() == 1
    assert publish_form.locator('input[name]').evaluate_all('fields => fields.map(field => field.name)') == [
        '_csrf', 'week', 'row_version',
    ]
    trigger = page.locator('[data-bs-target="#week-publish-modal"]')
    trigger.click()
    modal = page.locator('#week-publish-modal')
    expect(modal).to_have_class(re.compile(r'\bshow\b'))
    expect(modal).to_contain_text('Gespeicherte Woche')
    expect(modal).to_contain_text('Erfasste Menükarten')
    expect(modal).to_contain_text('Prüfstatus')
    modal.get_by_role('button', name='Abbrechen', exact=True).click()
    expect(modal).to_be_hidden()
    expect(page.locator('main')).to_have_attribute('data-status', 'ready')
    expect(trigger).to_be_focused()
    trigger.click()
    modal.locator('button[type="submit"]').click(trial=True)
    page.screenshot(path=str(tmp_path / f'{family}-publish-modal-{width}.png'), animations='disabled')
    with page.expect_response(lambda response: response.request.method == 'POST') as published:
        modal.locator('button[type="submit"]').click()
    assert published.value.status == 303
    payload = parse_qs(published.value.request.post_data)
    assert set(payload) == {'_csrf', 'week', 'row_version'}
    assert payload['week'] == [DAY]
    assert all(len(value) == 1 for value in payload.values())
    expect(page.locator('main')).to_have_attribute('data-status', 'live')


@pytest.mark.parametrize('family,profile,values', [
    ('cafeteria', 'staff_guest', _staff_values), ('patienten', 'patient', _patient_values),
])
def test_week_header_and_service_save_keep_dirty_guard_and_exact_payloads(
    page_context: Page, admin_app: Flask, family: str, profile: str, values,  # noqa: F811
) -> None:
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, values())
    page = page_context
    page.set_viewport_size({'width': 360, 'height': 800})
    page.goto(f'/admin/{family}?week={DAY}')
    header = page.locator(f'form[action="/admin/{family}/header"]')
    header.locator('[name="title"]').fill('Gespeicherte Wochenangaben')
    header.locator('[name="shared_note"]').fill('Saisonales Angebot')
    publish = page.locator('form[action$="/publish"] button[type="submit"]')
    expect(publish).to_be_disabled()
    preview = page.locator('a[href*="/preview"]').first
    expect(preview).to_have_attribute('aria-disabled', 'true')
    page.locator('[data-bs-target="#week-publish-modal"]').click()
    expect(page.locator('#week-publish-modal')).to_be_visible()
    expect(publish).to_be_disabled()
    page.get_by_role('button', name='Abbrechen', exact=True).click()
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        header.get_by_role('button', name='Wochenangaben speichern').click()
    assert saved.value.status == 303
    payload = parse_qs(saved.value.request.post_data, keep_blank_values=True)
    assert set(payload) == {'_csrf', 'week', 'row_version', 'title', 'shared_note'}
    assert payload['week'] == [DAY]
    # The existing POST redirects to a legacy header fragment; inspect persisted overview data.
    page.goto(f'/admin/{family}?week={DAY}')
    expect(header.locator('[name="title"]')).to_have_value('Gespeicherte Wochenangaben')
    expect(header.locator('[name="shared_note"]')).to_have_value('Saisonales Angebot')

    service = page.locator(f'form[action="/admin/{family}/service"]').first
    service.locator('[name="service_state"]').select_option('open')
    service.locator('[name="notice"]').fill('Geänderte Ausgabezeit')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved_service:
        service.get_by_role('button', name='Service speichern').click()
    assert saved_service.value.status == 303
    payload = parse_qs(saved_service.value.request.post_data, keep_blank_values=True)
    assert set(payload) == {'_csrf', 'week', 'row_version', 'day', 'meal', 'service_state', 'notice'}
    assert payload['week'] == payload['day'] == [DAY]
    assert payload['meal'] == ['LUNCH']
    page.goto(f'/admin/{family}?week={DAY}')
    expect(service.locator('[name="service_state"]')).to_have_value('open')
    expect(service.locator('[name="notice"]')).to_have_value('Geänderte Ausgabezeit')
