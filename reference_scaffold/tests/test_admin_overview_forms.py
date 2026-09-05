from __future__ import annotations

import datetime as dt

import pytest
from flask import Flask
from playwright.sync_api import Page
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
    form = page.locator(f'form[action="/admin/{family}/header"]')
    assert form.locator('[name="row_version"]').input_value() == '0'
    form.locator('[name="title"]').fill('Wochenangebot September')
    form.locator('[name="shared_note"]').fill('Hinweis für alle Tage')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        form.get_by_role('button', name='Wochenangaben speichern', exact=True).click()
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
    }, 0)
    payload = _payload(staff=profile == 'staff_guest')
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 0)
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 1)
    empty_day = (WEEK + dt.timedelta(days=1)).isoformat()
    persist_service_state(engine, scope, WEEK, empty_day, 'LUNCH', {
        'service_state': 'holiday', 'notice': 'Feiertag: keine Ausgabe',
    }, 0)

    page = page_context
    page.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
    page.goto(f'/admin/{family}?week={DAY}')
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
        if day == DAY:
            assert page.locator(
                f'.menu-slot[data-day="{DAY}"][data-meal="LUNCH"][data-option="MENU_1"]',
            ).get_attribute('data-row-version') == '2'
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            form.get_by_role('button', name='Service speichern', exact=True).click()
        assert saved.value.status == 303
        page.wait_for_url(f'**/admin/{family}?week={DAY}')
        assert form.locator('[name="row_version"]').input_value() == '2'
        assert form.locator('[name="service_state"]').input_value() == state
        assert form.locator('[name="notice"]').input_value() == notice
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
    page.get_by_role('link', name='Vorwoche kopieren', exact=True).click()
    form = page.locator(f'form[action="/admin/{family}/copy"]')
    fields = form.evaluate('form => Object.fromEntries(new FormData(form))')
    assert set(fields) == {'_csrf', 'source_week', 'target_week', 'target_row_version'}
    assert fields['source_week'] == DAY
    assert fields['target_week'] == target
    assert fields['target_row_version'] == '0'
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        form.get_by_role('button', name='Vorwoche kopieren', exact=True).click()
    assert saved.value.status == 303
    page.wait_for_url(f'**/admin/{family}?week={target}')
    assert page.locator(
        f'.menu-slot[data-day="{target}"][data-meal="LUNCH"][data-option="MENU_1"] h3',
    ).inner_text() == 'Kartoffelgratin'
    with admin_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 2
