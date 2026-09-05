from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader
from playwright.sync_api import Page, expect
from sqlalchemy import Engine, text

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import DAY, _login, _scope
from cafeteria.component_assignment_store import replace_component_links
from cafeteria.component_catalog_store import create_component, update_component
from cafeteria.workflow_review import get_component_review_token, review_component, review_open

ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = '77422d91cf1eedbf29404db3fdeb941c9b0d4056'
VIEWPORTS = ((390, 844), (1440, 1100))


def _capture(page: Page, phase: str, family: str, state: str, width: int) -> None:
    proof_path = os.environ.get('WEEK_OVERVIEW_PROOF_DIR')
    if proof_path and state in ('empty', 'ready', 'sticky'):
        folder = Path(proof_path)
        folder.mkdir(parents=True, exist_ok=True)
        assert page.locator('[style], [onclick], script:not([src])').count() == 0
        page.screenshot(
            path=str(folder / f'{phase}-{family}-{state}-{width}.png'),
            full_page=state != 'sticky', caret='initial',
        )


def _capture_original(page: Page, app: Flask, family: str, state: str, width: int) -> None:
    if not os.environ.get('WEEK_OVERVIEW_PROOF_DIR') or state not in ('empty', 'ready'):
        return
    template = f'admin/{family}.html'
    original = subprocess.run(
        ['rtk', 'git', '-C', str(ROOT), 'cat-file', 'blob',
         f'{BASE_REVISION}:reference_scaffold/cafeteria/templates/{template}'],
        check=True, capture_output=True, text=True,
    ).stdout
    loader = app.jinja_env.loader
    assert loader is not None
    app.jinja_env.loader = ChoiceLoader([DictLoader({template: original}), loader])
    app.jinja_env.cache.clear()
    try:
        page.goto(f'/admin/{family}?week={DAY}')
        _capture(page, 'before', family, state, width)
    finally:
        app.jinja_env.loader = loader
        app.jinja_env.cache.clear()


def _assert_layout(page: Page, height: int) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('[style], [onclick], script:not([src])').count() == 0
    controls = page.locator('.admin-week-controls')
    box = controls.bounding_box()
    assert box is not None and box['y'] >= 0 and box['y'] + box['height'] <= height
    bad_targets = page.locator('main a, main button, main input:not([type="hidden"]), main select').evaluate_all('''elements => elements.flatMap(element => {
        const target = element.type === 'checkbox' ? element.closest('label') : element;
        if (!target.getClientRects().length || getComputedStyle(target).visibility === 'hidden') return [];
        const box = target.getBoundingClientRect();
        return box.width < 44 || box.height < 44 || box.x < 0 || box.right > innerWidth + 1
            ? [element.outerHTML] : [];
    })''')
    assert not bad_targets


@pytest.mark.parametrize(('width', 'height'), VIEWPORTS)
@pytest.mark.parametrize(('family', 'profile', 'slots'), (
    ('cafeteria', 'staff_guest', 10), ('patienten', 'patient', 28),
))
@pytest.mark.parametrize('state', ('empty', 'incomplete', 'review_open', 'ready'))
def test_week_status_and_native_actions_are_visible_and_remain_available(
    page_context: Page, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    width: int, height: int, family: str, profile: str, slots: int, state: str,
) -> None:
    if state != 'empty':
        values = _staff_values() if profile == 'staff_guest' else _patient_values()
        _save_reviewed(admin_app.extensions['cafeteria_db'], profile, values)
        with admin_engine.begin() as connection:
            if state == 'incomplete':
                connection.execute(text(
                    'DELETE FROM cafeteria.menu_items WHERE id=(SELECT min(id) FROM cafeteria.menu_items)'
                ))
            elif state == 'review_open':
                connection.execute(text(
                    "UPDATE cafeteria.menu_items SET allergen_review_status='not_checked' "
                    'WHERE id=(SELECT min(id) FROM cafeteria.menu_items)'
                ))
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    _capture_original(page, admin_app, family, state, width)
    page.goto(f'/admin/{family}?week={DAY}')
    expect(page.locator('main')).to_have_attribute('data-status', state)
    expect(page.locator('.status-pill')).to_have_attribute('data-status', state)
    expect(page.locator('.weekbar')).to_contain_text('KW 36')
    expect(page.get_by_role('status')).to_contain_text(
        '1 Menükarte mit offener Prüfung' if state == 'review_open' else 'Keine offenen Prüfungen'
    )
    assert page.locator('.menu-slot').count() == slots
    assert 'Arbeitsstand' not in page.locator('main').inner_text()
    form = page.locator(f'form[action="/admin/{family}/publish"]')
    assert form.count() == 1
    assert page.locator('.admin-actions').count() == 1
    assert form.locator('input').evaluate_all('fields => fields.map(field => field.name)') == [
        '_csrf', 'week', 'row_version',
    ]
    expect(form.locator('[name="week"]')).to_have_value(DAY)
    publish = form.locator('button[type="submit"]')
    publish_trigger = page.locator('[data-bs-target="#week-publish-modal"]')
    expect(publish).to_have_text('Publizieren')
    if state == 'ready':
        expect(publish).to_be_enabled()
        expect(publish_trigger).to_be_enabled()
    else:
        expect(publish).to_be_disabled()
        expect(publish_trigger).to_be_disabled()
        expect(page.locator('#week-publish-guidance')).to_contain_text({
            'empty': 'Zuerst Gerichte erfassen',
            'incomplete': 'Zuerst die Woche vervollständigen',
            'review_open': 'Zuerst offene Prüfungen abschliessen',
        }[state])
    _assert_layout(page, height)
    _capture(page, 'after', family, state, width)
    if family == 'patienten':
        assert re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I) is None
        if state == 'empty':
            expect(page.locator('.patient-admin-day > .card-header span').first).to_have_text('0 von 4 Menükarten erfasst')
    page.locator('.menu-slot').last.scroll_into_view_if_needed()
    if width < 1200:
        controls = page.locator('.admin-week-controls')
        assert controls.evaluate('element => getComputedStyle(element).position') == 'static'
        expect(controls).not_to_be_in_viewport()
        controls.scroll_into_view_if_needed()
    _assert_layout(page, height)
    if state == 'ready':
        _capture(page, 'after', family, 'sticky', width)
        requests: list[str] = []
        page.on('request', lambda request: requests.append(request.method))
        publish_trigger.click()
        modal = page.get_by_role('dialog')
        expect(modal).to_be_visible()
        expect(modal).to_contain_text('Woche publizieren')
        expect(publish).to_be_visible()
        assert modal.locator('button').evaluate_all('''buttons => buttons.every(button => {
            const box = button.getBoundingClientRect();
            return box.width >= 44 && box.height >= 44 && box.left >= 0 && box.right <= innerWidth + 1;
        })''')
        modal.get_by_role('button', name='Abbrechen', exact=True).click()
        expect(modal).not_to_be_visible()
        assert 'POST' not in requests
        expect(page.locator('main')).to_have_attribute('data-status', 'ready')
        copy = page.get_by_role('link', name='Vorwoche kopieren', exact=True)
        publish_trigger.focus()
        page.keyboard.press('Tab')
        expect(page.locator('a[href*="/preview"]')).to_be_focused()
        page.keyboard.press('Tab')
        expect(copy).to_be_focused()
        assert copy.evaluate('element => getComputedStyle(element).outlineStyle !== "none"')
        title = page.locator('input[name="title"]')
        for _ in range(8):
            page.keyboard.press('Tab')
            if title.evaluate('element => element === document.activeElement'):
                break
        expect(title).to_be_focused()
        title.fill('Angepasste Woche')
        focused_box = title.bounding_box()
        actions_box = page.locator('.admin-week-controls').bounding_box()
        assert focused_box is not None and actions_box is not None
        assert focused_box['y'] >= actions_box['y'] + actions_box['height']
        expect(publish).to_be_disabled()
        expect(publish).to_have_text('Zuerst speichern')
        expect(page.locator('a[href*="/preview"]')).to_have_attribute('aria-disabled', 'true')


@pytest.mark.parametrize(('width', 'height'), VIEWPORTS)
@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_week_fields_preserve_native_payloads_and_usable_widths(
    page_context: Page, family: str, width: int, height: int,  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(f'/admin/{family}?week={DAY}')
    header = page.locator(f'form[action="/admin/{family}/header"]')
    title = header.locator('[name="title"]')
    box = title.bounding_box()
    assert box is not None and box['width'] >= 300
    title.fill('Wochenangebot September')
    header.locator('[name="shared_note"]').fill('Frisch zubereitet')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        header.get_by_role('button', name='Wochenangaben speichern', exact=True).click()
    assert saved.value.status == 303
    payload = parse_qs(saved.value.request.post_data or '', keep_blank_values=True)
    assert set(payload) == {'_csrf', 'week', 'row_version', 'title', 'shared_note'}
    assert payload['week'] == [DAY] and payload['row_version'] == ['0']
    page.goto(f'/admin/{family}?week={DAY}')
    expect(title).to_have_value('Wochenangebot September')
    service = page.locator(f'form[action="/admin/{family}/service"]').first
    service.locator('[name="service_state"]').select_option('holiday')
    service.locator('[name="notice"]').fill('Heute keine Ausgabe')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        service.get_by_role('button', name='Service speichern', exact=True).click()
    assert saved.value.status == 303
    payload = parse_qs(saved.value.request.post_data or '', keep_blank_values=True)
    assert set(payload) == {'_csrf', 'week', 'day', 'meal', 'row_version', 'service_state', 'notice'}
    assert payload['day'] == [DAY] and payload['meal'] == ['LUNCH'] and payload['row_version'] == ['0']
    page.goto(f'/admin/{family}?week={DAY}')
    expect(service.locator('[name="row_version"]')).to_have_value('1')
    expect(service.locator('[name="notice"]')).to_have_value('Heute keine Ausgabe')
    if family == 'cafeteria' and width > 900:
        bounds = [service.locator(f'[name="{name}"]').bounding_box() for name in ('service_state', 'notice')]
        assert all(bound is not None and bound['width'] >= 140 for bound in bounds)
        assert abs(bounds[0]['y'] - bounds[1]['y']) < 1


@pytest.mark.parametrize(('family', 'profile'), (('cafeteria', 'staff_guest'), ('patienten', 'patient')))
def test_changed_catalog_never_reports_no_open_week_checks(
    page_context: Page, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str,
) -> None:
    engine = admin_app.extensions['cafeteria_db']
    _save_reviewed(engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    _, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, user_id, profile)
    component = create_component(engine, scope, 'side', 'Salat', 'CH', 'common', (), ())
    with admin_engine.connect() as connection:
        item = connection.execute(text('SELECT id, row_version FROM cafeteria.menu_items ORDER BY id LIMIT 1')).one()
    item_version = replace_component_links(
        engine, scope, item.id,
        [{'component_public_id': str(component['public_id']), 'component_text': None}],
        item.row_version,
    )
    review_component(
        engine, scope, item.id, get_component_review_token(engine, scope, item.id), item_version,
    )
    assert not review_open(engine, scope, item.id)
    update_component(engine, scope, str(component['public_id']), {
        'category': 'side', 'name': 'Gemischter Salat', 'origin_country_code': 'CH',
        'label_codes': [], 'allergens': [],
    }, component['row_version'])
    page = page_context
    page.goto(f'/admin/{family}?week={DAY}')
    expect(page.locator('main')).to_have_attribute('data-status', 'review_open')
    assert review_open(engine, scope, item.id)
    with admin_engine.connect() as connection:
        assert connection.execute(text(
            'SELECT allergen_review_status FROM cafeteria.menu_items WHERE id=:id'
        ), {'id': item.id}).scalar_one() == 'checked'
    assert page.locator('.slot-badge[data-review="open"]').count() == 1
    expect(page.get_by_role('status')).to_contain_text('1 Menükarte mit offener Prüfung')
    expect(page.get_by_role('status')).not_to_contain_text('Keine offenen Prüfungen')
    expect(page.get_by_role('button', name='Publizieren', exact=True)).to_be_disabled()
