from __future__ import annotations

import datetime as dt
import json

import pytest
from flask import Flask
from playwright.sync_api import Page, expect
from sqlalchemy import Engine, text

from cafeteria.workflow_partial_store import persist_menu_item, persist_service_state
from test_admin_ux_browser import live_server, page_context  # noqa: F401
from test_admin_workflow_routes import DATABASE_URL, DAY, WEEK, _login, _payload, _scope
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('viewport', [(390, 844), (1440, 1100)])
def test_overview_header_submits_native_form_and_reloads_saved_values(
    page_context: Page, admin_engine: Engine, family: str, viewport: tuple[int, int],  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
    page.goto(f'/admin/{family}?week={DAY}')
    page.locator('details.admin-week-settings > summary').click()
    form = page.locator(f'form[action="/admin/{family}/header"]')
    assert form.locator('[name="row_version"]').input_value() == '0'
    form.locator('[name="title"]').fill('Wochenangebot September')
    form.locator('[name="shared_note"]').fill('Hinweis für alle Tage')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        form.get_by_role('button', name='Speichern', exact=True).click()
    assert saved.value.status == 303
    page.wait_for_url(f'**/admin/{family}?week={DAY}')
    assert form.locator('[name="row_version"]').input_value() == '1'
    assert form.locator('[name="title"]').input_value() == 'Wochenangebot September'
    assert form.locator('[name="shared_note"]').input_value() == 'Hinweis für alle Tage'
    with admin_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 0


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('viewport', [(390, 844), (1440, 1100)])
def test_overview_service_uses_own_version_and_preserves_notice_without_items(
    page_context: Page, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, viewport: tuple[int, int],
) -> None:
    _, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, user_id, profile)
    engine = admin_app.extensions['cafeteria_db']
    persist_service_state(engine, scope, WEEK, DAY, 'LUNCH', {
        'service_state': 'open', 'notice': 'Ausgabe ab 11:30 Uhr',
        'service_start': '11:30', 'service_end': '13:00',
    }, 0)
    payload = _payload(staff=profile == 'staff_guest')
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 0)
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 1)
    empty_day = (WEEK + dt.timedelta(days=1)).isoformat()
    persist_service_state(engine, scope, WEEK, empty_day, 'LUNCH', {
        'service_state': 'holiday', 'notice': 'Feiertag: keine Ausgabe',
        'service_start': '', 'service_end': '',
    }, 0)

    page = page_context
    page.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
    page.goto(f'/admin/{family}?week={DAY}')
    page.locator('details.admin-week-service').evaluate_all(
        'els => els.forEach(el => { el.open = true })',
    )
    for day, state, notice in (
        (DAY, 'open', 'Ausgabe ab 11:30 Uhr'),
        (empty_day, 'holiday', 'Feiertag: keine Ausgabe'),
    ):
        form = page.locator(f'form[action="/admin/{family}/service"]').filter(
            has=page.locator(f'input[name="day"][value="{day}"]'),
        ).filter(has=page.locator('input[name="meal"][value="LUNCH"]'))
        assert form.locator('[name="row_version"]').input_value() == '1'
        assert form.locator('[name="service_state"]').input_value() == state
        assert form.locator('[name="notice"]').input_value() == notice
        assert form.locator('[name="service_start"]').input_value() == ('11:30' if day == DAY else '')
        assert form.locator('[name="service_end"]').input_value() == ('13:00' if day == DAY else '')
        if day == DAY:
            assert page.locator(
                f'.menu-slot[data-day="{DAY}"][data-meal="LUNCH"][data-option="MENU_1"]',
            ).get_attribute('data-row-version') == '2'
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            form.get_by_role('button', name='Speichern', exact=True).click()
        assert saved.value.status == 303
        page.wait_for_url(f'**/admin/{family}?week={DAY}')
        page.locator('details.admin-week-service').evaluate_all(
            'els => els.forEach(el => { el.open = true })',
        )
        assert form.locator('[name="row_version"]').input_value() == '2'
        assert form.locator('[name="service_state"]').input_value() == state
        assert form.locator('[name="notice"]').input_value() == notice
        assert form.locator('[name="service_start"]').input_value() == ('11:30' if day == DAY else '')
        assert form.locator('[name="service_end"]').input_value() == ('13:00' if day == DAY else '')
    with admin_engine.connect() as connection:
        assert connection.execute(text('SELECT row_version FROM cafeteria.menu_items')).scalar_one() == 2
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.menu_services s JOIN cafeteria.menu_items i '
            'ON i.service_id=s.id WHERE s.service_date=:day',
        ), {'day': empty_day}).scalar_one() == 0


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('viewport', [(390, 844), (1440, 1100)])
def test_copy_link_on_empty_week_submits_exact_native_form(
    page_context: Page, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, viewport: tuple[int, int],
) -> None:
    _, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    persist_menu_item(
        admin_app.extensions['cafeteria_db'], _scope(admin_engine, user_id, profile),
        WEEK, DAY, 'LUNCH', 'MENU_1', _payload(staff=profile == 'staff_guest'), 0,
    )
    target = (WEEK + dt.timedelta(days=7)).isoformat()
    page = page_context
    page.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
    page.goto(f'/admin/{family}?week={target}')
    expect(page.locator('[data-semantic="actions.more"]')).to_have_count(0)
    page.get_by_role('link', name='Vorwoche kopieren', exact=True).click()
    form = page.locator(f'form[action="/admin/{family}/copy"]')
    fields = form.evaluate('form => Object.fromEntries(new FormData(form))')
    assert set(fields) == {'_csrf', 'source_week', 'target_week', 'target_row_version'}
    assert fields['source_week'] == DAY
    assert fields['target_week'] == target
    assert fields['target_row_version'] == '0'
    copy = page.get_by_role('button', name='Vorwoche kopieren', exact=True)
    assert copy.get_attribute('form') == form.get_attribute('id') == 'week-copy-form'
    assert copy.evaluate('button => button.form.action') == form.evaluate('form => form.action')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        copy.click()
    assert saved.value.status == 303
    page.wait_for_url(f'**/admin/{family}?week={target}')
    assert page.locator(
        f'.menu-slot[data-day="{target}"][data-meal="LUNCH"][data-option="MENU_1"] h3',
    ).inner_text() == 'Kartoffelgratin'
    with admin_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 2


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [True, False])
def test_menu_direct_origin_action_preserves_native_form(
    page_context, browser, live_server, tmp_path, family, width, javascript,  # noqa: F811
):
    with browser.new_context(
        base_url=live_server, storage_state=page_context.context.storage_state(),
        viewport={'width': width, 'height': 844 if width == 390 else 900},
        has_touch=width == 390, java_script_enabled=javascript, reduced_motion='reduce',
    ) as context:
        page = context.new_page()
        posts, errors = [], []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        route = f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
        assert page.goto(route).status == 200
        page.get_by_label('Menüname', exact=True).fill('Direkte Herkunftsaktion')
        if family == 'cafeteria':
            page.get_by_label('Mitarbeitende CHF', exact=True).fill('9.50')
            page.get_by_label('Preis für externe Gäste CHF', exact=True).fill('14.50')
        field = page.locator('[name="origin_ingredient"]').first
        field.fill('Tomate')
        page.locator('[name="origin_country_code"]').first.select_option('CH')
        form = page.locator('form[data-menu-editor]')
        before = form.evaluate('f => Object.fromEntries(new FormData(f))')
        assert before['_csrf']
        expect(page.locator('[data-semantic="actions.more"]')).to_have_count(0)
        remove = page.locator('#origins-list [data-remove-row]').first
        expect(remove).to_be_visible()
        expect(remove).to_have_text('')
        expect(remove).to_have_accessible_name('Herkunft löschen')
        expect(remove).to_have_attribute('type', 'button')
        remove.scroll_into_view_if_needed()
        box = remove.bounding_box()
        size = 44 if width == 390 else 36
        assert (box['width'], box['height']) == (size, size)
        assert page.evaluate("matchMedia('(any-pointer: coarse)').matches") is (width == 390)
        page.screenshot(path=str(tmp_path / f'{family}-origin-{width}-js{javascript}.png'), full_page=False)
        (tmp_path / 'capture.json').write_text(json.dumps({
            'route': route, 'viewport': page.viewport_size, 'role': 'Cafeteria.Admin',
            'javascript': javascript, 'coarse': width == 390,
        }, indent=2))
        if javascript:
            page.get_by_role('button', name='Herkunft hinzufügen', exact=True).press('Enter')
            page.locator('[name="origin_ingredient"]').last.fill('Kartoffel')
            page.locator('[name="origin_country_code"]').last.select_option('CH')
        remove.press('Enter')
        expect(field).to_have_value('Kartoffel' if javascript else 'Tomate')
        assert not posts and not errors
        assert form.locator('[name="_csrf"]').input_value() == before['_csrf']
        expect(page.get_by_label('Menüname', exact=True)).to_have_value('Direkte Herkunftsaktion')
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            form.locator('[data-sticky]').get_by_role('button', name='Menü speichern', exact=True).click()
        assert saved.value.status == 303 and len(posts) == 1
        assert not errors
