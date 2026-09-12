"""UI-Korrektur 2026-09-12: Patientenplan and Cafeteria-Plan (U01–U03, U05)."""
from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from flask import Flask
from playwright.sync_api import Page, expect
from sqlalchemy import Engine, text

from cafeteria.workflow import publish_draft
from cafeteria.workflow_partial_store import persist_service_state
from test_admin_ux_browser import live_server, page_context  # noqa: F401
from test_admin_workflow_db import WEEK_START, _actor_id, _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, WEEK, _login, _scope
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'ui-korrektur-0912' / 'week'
FAMILIES = ('cafeteria', 'patienten')
PROFILE_BY_FAMILY = {'cafeteria': 'staff_guest', 'patienten': 'patient'}
SLOT_COUNT = {'cafeteria': 10, 'patienten': 28}
VIEWPORTS = ((1366, 768), (1920, 1080), (768, 1024), (390, 844), (720, 450))
LONG_NOTE = 'Vollständiger langer Rezepturhinweis bleibt sichtbar und darf nicht gekürzt werden. ' * 4


def _goto(page: Page, family: str) -> None:
    response = page.goto(f'/admin/{family}?week={DAY}')
    assert response is not None and response.status == 200
    page.evaluate('document.fonts.ready')


def _open_week_forms(page: Page) -> None:
    page.locator('details.admin-week-settings').evaluate('el => { el.open = true }')
    page.locator('details.admin-week-service').first.evaluate('el => { el.open = true }')


def _open_more_actions(page: Page) -> None:
    page.locator('details.admin-week-more').evaluate('el => { el.open = true }')


def _assert_no_overflow(page: Page) -> None:
    metrics = page.evaluate('''() => ({
        viewport: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        statusWidth: document.querySelector('.admin-week-status')?.scrollWidth || 0,
        statusVisibleWidth: document.querySelector('.admin-week-status')?.clientWidth || 0,
    })''')
    assert metrics['documentWidth'] <= metrics['viewport'] + 1, metrics


def _assert_page_container_width(page: Page, width: int) -> None:
    if width < 1024:
        return
    layout = page.evaluate('''() => {
        const main = document.querySelector('main.admin-main');
        const container = document.querySelector('.page-body > .container-xl');
        const maxWidth = getComputedStyle(container).maxWidth;
        const containerWidth = container.getBoundingClientRect().width;
        const cap = maxWidth === 'none' ? null : parseFloat(maxWidth);
        return {
            maxWidth,
            ratio: containerWidth / main.clientWidth,
            containerWidth,
            cap,
            mainWidth: main.clientWidth,
        };
    }''')
    if layout['maxWidth'] == 'none':
        assert layout['ratio'] >= 0.9, layout
    else:
        frame_width = min(layout['cap'], layout['mainWidth'])
        assert layout['containerWidth'] >= frame_width - 2, layout


def _shot(page: Page, family: str, state: str, width: int, height: int) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(EVIDENCE / f'{family}-{state}-{width}x{height}.png'),
        full_page=True,
    )


def _tab_to(page: Page, target, *, max_steps: int = 40) -> None:
    for _ in range(max_steps):
        page.keyboard.press('Tab')
        if target.evaluate('element => element === document.activeElement'):
            return
    pytest.fail(f'Tab did not reach {target}')


def _a06_values(profile: str) -> dict:
    values = deepcopy(_staff_values() if profile == 'staff_guest' else _patient_values())
    options = [option for day in values['days'] for service in day['services'] for option in service['options']]
    milk = {'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}
    for option in options[1:]:
        option['allergens'] = [milk]
        option['allergen_review_status'] = 'checked'
    options[0]['allergens'] = []
    options[0]['allergen_review_status'] = 'checked'
    return values


def _publish_ready(engine: Engine, profile: str, values: dict) -> None:
    version = _save_reviewed(engine, profile, values)
    publish_draft(
        engine, profile, WEEK_START,
        expected_row_version=version,
        actor_id=_actor_id(engine),
        issuer_engine=engine,
    )


@pytest.mark.parametrize('family', FAMILIES)
def test_a01_single_area_nav_and_single_week_review_link(page_context: Page, family: str) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, family)
    expect(page.locator('.admin-area-tabs')).to_have_count(1)
    expect(page.locator('.profile-tabs')).to_have_count(0)
    expect(page.get_by_role('link', name='Wochenangaben prüfen')).to_have_count(1)
    expect(page.locator('.admin-week-review-link')).to_have_count(1)


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize(('width', 'height'), ((1366, 768), (1920, 1080)))
def test_a02_first_menu_slot_fits_viewport_without_scroll(
    page_context: Page, admin_app: Flask, family: str, width: int, height: int,  # noqa: F811
) -> None:
    profile = PROFILE_BY_FAMILY[family]
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    _goto(page, family)
    page.evaluate('scrollTo(0, 0)')
    slot = page.locator('.menu-slot').first
    expect(slot).to_be_visible()
    box = slot.bounding_box()
    assert box is not None
    assert box['y'] >= 0
    assert box['y'] + box['height'] <= height + 1, (family, width, height, box)
    _shot(page, family, 'regular', width, height)


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize(('width', 'height', 'expected_px'), ((1366, 768, 34), (390, 844, 28)))
def test_week_h1_uses_design_system_title_size(
    page_context: Page, family: str, width: int, height: int, expected_px: int,  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    _goto(page, family)
    size = page.locator('h1.page-title').evaluate(
        'element => parseFloat(getComputedStyle(element).fontSize)'
    )
    assert size == pytest.approx(expected_px)


@pytest.mark.parametrize('family', FAMILIES)
def test_a03_full_week_grid_and_patient_prices_absent(
    page_context: Page, family: str,  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, family)
    assert page.locator('.menu-slot').count() == SLOT_COUNT[family]
    if family == 'patienten':
        assert page.locator('article.patient-admin-day').count() == 7
        assert page.locator('.patient-admin-meal').count() == 14
        assert re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I) is None
    else:
        days = page.locator('article.admin-day-card')
        assert days.count() in (5, 7)
        assert page.locator('.menu-slot[data-meal="LUNCH"]').count() == SLOT_COUNT[family]


@pytest.mark.parametrize('family', FAMILIES)
def test_a04_week_and_service_details_closed_then_same_payloads(
    page_context: Page, family: str,  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, family)
    settings = page.locator('details.admin-week-settings')
    assert settings.get_attribute('open') is None
    assert page.locator('details.admin-week-service').first.get_attribute('open') is None
    _open_week_forms(page)
    header = page.locator(f'form[action="/admin/{family}/header"]')
    header.locator('[name="title"]').fill('Wochenangebot September')
    header.locator('[name="shared_note"]').fill('Frisch zubereitet')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        header.get_by_role('button', name='Wochenangaben speichern', exact=True).click()
    assert saved.value.status == 303
    payload = parse_qs(saved.value.request.post_data or '', keep_blank_values=True)
    assert set(payload) == {'_csrf', 'week', 'row_version', 'title', 'shared_note'}
    assert payload['week'] == [DAY] and payload['row_version'] == ['0']
    _goto(page, family)
    _open_week_forms(page)
    service = page.locator(f'form[action="/admin/{family}/service"]').first
    service.locator('[name="service_state"]').select_option('holiday')
    service.locator('[name="notice"]').fill('Heute keine Ausgabe')
    service.locator('[name="service_start"]').fill('11:30')
    service.locator('[name="service_end"]').fill('13:30')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved_service:
        service.get_by_role('button', name='Ausgabeangaben speichern', exact=True).click(force=True)
    assert saved_service.value.status == 303
    payload = parse_qs(saved_service.value.request.post_data or '', keep_blank_values=True)
    assert set(payload) == {
        '_csrf', 'week', 'day', 'meal', 'row_version', 'service_state', 'notice',
        'service_start', 'service_end',
    }
    assert payload['service_start'] == ['11:30'] and payload['service_end'] == ['13:30']
    assert payload['day'] == [DAY] and payload['meal'] == ['LUNCH'] and payload['row_version'] == ['0']


@pytest.mark.parametrize(('family', 'profile'), (('cafeteria', 'staff_guest'), ('patienten', 'patient')))
def test_a05_empty_times_are_not_standard_hours(
    page_context: Page, admin_app: Flask, admin_engine: Engine, family: str, profile: str,  # noqa: F811
) -> None:
    _, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    persist_service_state(
        admin_app.extensions['cafeteria_db'], _scope(admin_engine, user_id, profile),
        WEEK, DAY, 'LUNCH',
        {'service_state': 'open', 'notice': '', 'service_start': '', 'service_end': ''},
        0,
    )
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, family)
    meal = page.locator('.patient-admin-meal, .admin-day-card').first
    expect(meal).to_contain_text('Zeiten nicht eingetragen')
    expect(meal).not_to_contain_text('Standardzeiten')


@pytest.mark.parametrize(('family', 'profile'), (('cafeteria', 'staff_guest'), ('patienten', 'patient')))
def test_a06_live_checked_and_missing_allergens_are_separate(
    page_context: Page, admin_app: Flask, family: str, profile: str,  # noqa: F811
) -> None:
    engine = admin_app.extensions['cafeteria_db']
    values = _a06_values(profile)
    _publish_ready(engine, profile, values)
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, family)
    expect(page.locator('main')).to_have_attribute('data-status', 'live')
    status = page.get_by_role('status')
    status_copy = status.locator('.admin-week-status-copy')
    expect(status_copy).to_have_text('Gespeicherter Stand veröffentlicht')
    expect(status_copy).to_have_attribute(
        'aria-label', 'Veröffentlicht · entspricht dem gespeicherten Stand'
    )
    filled = SLOT_COUNT[family]
    expect(status).to_contain_text(f'{filled} Menükarten geprüft')
    expect(status).to_contain_text('Wochenkopf und Ausgabehinweise geprüft')
    expect(status).to_contain_text('1 ohne Allergenangaben')
    expect(status).not_to_contain_text('Keine offenen Prüfungen')
    text_line_tops = status.evaluate('''root => {
        const tops = [];
        for (const item of root.querySelectorAll(':scope > span:not(.status-pill)')) {
            const range = document.createRange();
            range.selectNodeContents(item);
            for (const rect of range.getClientRects()) {
                if (rect.width > 0 && rect.height > 0) tops.push(Math.round(rect.top));
            }
        }
        return [...new Set(tops)];
    }''')
    assert len(text_line_tops) == 1, text_line_tops
    _assert_no_overflow(page)
    card = page.locator('.menu-slot').first
    expect(card.locator('.slot-badge')).to_have_text('Geprüft')
    expect(card).to_contain_text('Allergenangaben nicht erfasst')
    _shot(page, family, 'a06', 1366, 768)

    values['title'] = f"{values['title']} geändert"
    _save_reviewed(engine, profile, values)
    _goto(page, family)
    expect(page.locator('main')).to_have_attribute('data-status', 'changed')
    changed_status = page.get_by_role('status')
    expect(changed_status.locator('.admin-week-status-copy')).to_have_text(
        'Veröffentlicht · Änderungen offen'
    )
    expect(changed_status).to_contain_text('Wochenkopf und Ausgabehinweise geprüft')


@pytest.mark.parametrize(('family', 'profile'), (('cafeteria', 'staff_guest'), ('patienten', 'patient')))
def test_a07_long_note_collapses_and_keeps_allergen_warning_visible(
    page_context: Page, admin_app: Flask, family: str, profile: str,  # noqa: F811
) -> None:
    values = deepcopy(_staff_values() if profile == 'staff_guest' else _patient_values())
    first = values['days'][0]['services'][0]['options'][0]
    first['note'] = LONG_NOTE
    first['allergens'] = []
    first['title'] = first.get('title') or 'Gericht'
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, values)
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, family)
    card = page.locator('.menu-slot').first
    details = card.locator('details.admin-week-note')
    expect(details).to_have_count(1)
    expect(details.locator('summary')).to_have_text('Hinweis anzeigen')
    expect(card.locator('[data-menu-metadata] > p')).to_contain_text('Allergenangaben nicht erfasst')
    order = card.evaluate('''(root, family) => {
        const nodes = [...root.querySelectorAll('*')];
        const index = selector => nodes.indexOf(root.querySelector(selector));
        const result = [
            index('.dish-type'), index('h3'), index('.admin-week-components'),
            index('[data-menu-metadata] > p'), index('[data-menu-metadata] .labels'),
            index('.admin-week-review-line'),
        ];
        if (family === 'cafeteria') {
            result.push(nodes.findIndex(node =>
                node.tagName === 'P' && node.textContent.includes('Mitarbeitende CHF')
            ));
        }
        result.push(index('a[href*="/menu"]'), index('details.admin-week-note'));
        return result;
    }''', family)
    assert all(position >= 0 for position in order), order
    assert order == sorted(order), order
    assert LONG_NOTE.strip() not in (card.inner_text() or '')
    details.locator('summary').click()
    assert LONG_NOTE.strip() in card.inner_text()
    warning = card.locator('[data-menu-metadata] > p').filter(has_text='Allergenangaben nicht erfasst')
    expect(warning).to_be_visible()
    assert warning.evaluate('el => el.closest("details")') is None


@pytest.mark.parametrize(('hint_length', 'collapsed'), ((139, False), (140, True)))
def test_a07_hint_collapses_at_140_character_boundary(
    page_context: Page, admin_app: Flask, hint_length: int, collapsed: bool,  # noqa: F811
) -> None:
    values = deepcopy(_staff_values())
    first = values['days'][0]['services'][0]['options'][0]
    first['description'] = ''
    first['note'] = 'x' * hint_length
    _save_reviewed(admin_app.extensions['cafeteria_db'], 'staff_guest', values)
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, 'cafeteria')
    card = page.locator('.menu-slot').first
    details = card.locator('details.admin-week-note')
    expect(details).to_have_count(1 if collapsed else 0)
    if collapsed:
        expect(details).to_contain_text('x' * hint_length)
    else:
        expect(card).to_contain_text('x' * hint_length)


def test_cafeteria_weekend_hint_sits_in_page_header_before_status(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    with admin_engine.begin() as connection:
        connection.execute(text(
            "UPDATE cafeteria.offer_profiles SET allows_weekend=true WHERE code='staff_guest'"
        ))
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, 'cafeteria')
    hint = page.locator('.admin-page-header .form-hint')
    expect(hint).to_have_text('Wochenendbetrieb: Samstag und Sonntag sind im Raster.')
    assert page.evaluate('''() => {
        const hint = document.querySelector('.admin-page-header .form-hint');
        const status = document.querySelector('.admin-week-controls');
        return Boolean(hint && status && (hint.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING));
    }''')


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize(('width', 'height'), VIEWPORTS)
def test_a11_a12_full_width_and_no_horizontal_scroll(
    page_context: Page, admin_app: Flask, family: str, width: int, height: int,  # noqa: F811
) -> None:
    profile = PROFILE_BY_FAMILY[family]
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    _goto(page, family)
    _assert_no_overflow(page)
    _assert_page_container_width(page, width)
    _shot(page, family, 'regular', width, height)


@pytest.mark.parametrize('family', FAMILIES)
def test_a12_empty_and_review_open_screenshots(
    page_context: Page, admin_app: Flask, family: str,  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, family)
    _shot(page, family, 'empty', 1366, 768)
    profile = PROFILE_BY_FAMILY[family]
    values = deepcopy(_staff_values() if profile == 'staff_guest' else _patient_values())
    values['days'][0]['services'][0]['options'][0]['allergen_review_status'] = 'not_checked'
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, values)
    _goto(page, family)
    expect(page.locator('main')).to_have_attribute('data-status', 'review_open')
    _shot(page, family, 'review_open', 1366, 768)


@pytest.mark.parametrize('family', FAMILIES)
def test_a13_tab_order_actions_then_first_card_not_covered_by_sticky(
    page_context: Page, admin_app: Flask, family: str,  # noqa: F811
) -> None:
    profile = PROFILE_BY_FAMILY[family]
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    page = page_context
    page.set_viewport_size({'width': 1366, 'height': 768})
    _goto(page, family)
    trigger = page.locator('[data-bs-target="#week-publish-modal"]')
    _tab_to(page, trigger)
    page.keyboard.press('Tab')
    expect(page.locator('a[href*="/preview"]')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('link', name='Wochenangaben prüfen')).to_be_focused()
    page.keyboard.press('Tab')
    more = page.locator('details.admin-week-more > summary')
    expect(more).to_be_focused()
    page.keyboard.press('Tab')
    settings = page.locator('details.admin-week-settings > summary')
    expect(settings).to_be_focused()
    page.keyboard.press('Tab')
    service = page.locator('details.admin-week-service > summary').first
    expect(service).to_be_focused()
    page.keyboard.press('Tab')
    first_edit = page.locator('.menu-slot a.btn').first
    expect(first_edit).to_be_focused()
    page.keyboard.press('Shift+Tab')
    expect(service).to_be_focused()
    page.keyboard.press('Tab')
    expect(first_edit).to_be_focused()
    focused_box = first_edit.bounding_box()
    actions_box = page.locator('.admin-week-controls').bounding_box()
    assert focused_box is not None and actions_box is not None
    position = page.locator('.admin-week-controls').evaluate('el => getComputedStyle(el).position')
    if position == 'sticky':
        assert focused_box['y'] >= actions_box['y'] + actions_box['height'] - 1
