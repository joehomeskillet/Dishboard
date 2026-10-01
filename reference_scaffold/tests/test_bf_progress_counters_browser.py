"""BF-E2 counters and editor-row identity: T16 and T22."""
from __future__ import annotations

from datetime import timedelta

import pytest
from playwright.sync_api import expect

from cafeteria.course_store import persist_service_courses
from cafeteria.workflow_partial_store import persist_menu_item, persist_service_state
from test_admin_ux_browser import live_server as live_server  # noqa: F401
from test_admin_workflow_routes import WEEK, _login, _scope
from test_master_data_browser import master_server  # noqa: F401
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_rendered_ui import admin_app as admin_app, admin_engine as admin_engine, browser as browser  # noqa: F401
from test_workflow_partial_store_db import _payload, _service_payload

TUESDAY = (WEEK + timedelta(days=1)).isoformat()


def _session(browser, live_server, admin_app, admin_engine, javascript: bool):
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    context = browser.new_context(
        base_url=live_server, java_script_enabled=javascript, reduced_motion='reduce',
        viewport={'width': 1280, 'height': 900},
    )
    cookie = client.get_cookie('session')
    assert cookie is not None
    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
    return context, user_id


def _closed_monday_and_open_tuesday(engine, user_id) -> None:
    scope = _scope(engine, user_id, 'staff_guest')
    persist_service_state(
        engine, scope, WEEK, WEEK.isoformat(), 'LUNCH',
        _service_payload(state='closed', notice='Betrieb zu'), 0,
    )
    persist_menu_item(engine, scope, WEEK, TUESDAY, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_service_courses(
        engine, scope, WEEK, TUESDAY, 'LUNCH',
        soup={'state': 'unplanned'}, dessert={'state': 'not_offered'}, exceptions=[],
    )


@pytest.mark.parametrize('javascript', [False, True])
def test_t16_optional_course_and_empty_card_stay_distinct(browser, live_server, admin_app, admin_engine, javascript):  # noqa: F811
    """T16 green part: optional courses are not check errors; the empty card stays visible."""
    context, user_id = _session(browser, live_server, admin_app, admin_engine, javascript)
    _closed_monday_and_open_tuesday(admin_engine, user_id)
    try:
        page = context.new_page()
        page.goto(f'/admin/cafeteria?week={WEEK.isoformat()}', wait_until='load')
        tuesday = page.locator('article.admin-day-card', has=page.get_by_role('heading', name='Dienstag', exact=True))
        expect(tuesday.locator('.admin-week-day-count')).to_have_text('1 von 2 Menükarten erfasst')
        expect(tuesday).to_contain_text('Noch kein Gericht')
        expect(tuesday).to_contain_text('Suppe noch nicht geplant')
        expect(tuesday).to_contain_text('Kein Dessert')
        expect(tuesday.locator('.admin-week-service-summary')).to_contain_text('Offen')
        summary = page.locator('#week-check-summary')
        summary_text = summary.text_content() if summary.count() else ''
        assert summary_text is not None
        assert 'Gang prüfen' not in summary_text and 'Gänge prüfen' not in summary_text
        page.goto('/admin/kuechenkalender?year=2026&month=8', wait_until='load')
        header = page.locator('body').inner_text()
        assert 'Tage geplant' in header or 'Keine Tage geplant' in header
    finally:
        context.close()


@pytest.mark.parametrize('javascript', [False, True])
def test_t22_moved_ingredient_keeps_identity_when_quantity_is_invalid(
    b3, master_server, browser, javascript,  # noqa: F811
):
    """T22: after insert and move, the decimal error, value and line id stay on that row."""
    from cafeteria import recipe_store as store
    from test_master_data_db import signed_in
    from test_recipe_store_db import payload
    app, _owner, _client, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        created = store.create_recipe(engine, actor, payload(title='BFZeile'), expected_location_id=location)
        line_id = store.get_recipe(engine, created.public_id).payload['ingredients'][0]['line_public_id']
    base, cookie = master_server
    context = browser.new_context(
        viewport={'width': 1280, 'height': 900}, java_script_enabled=javascript, reduced_motion='reduce',
    )
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
    try:
        page = context.new_page()
        page.goto(base + f'/admin/rezepte/{created.public_id}', wait_until='load')
        page.get_by_role('button', name='Zutat 1 davor einfügen', exact=True).click()
        page.locator('[id="ingredients.0.ingredient_text"]').fill('Karotte grob')
        page.locator('[id="ingredients.0.quantity"]').fill('3')
        page.locator('[id="ingredients.0.unit_code"]').select_option('G')
        page.locator('[id="ingredients.1.ingredient_text"]').fill('Karotte fein')
        page.locator('[id="ingredients.1.quantity"]').fill('1')
        page.locator('[id="ingredients.1.unit_code"]').select_option('G')
        page.get_by_role('button', name='Zutat 2 nach oben verschieben', exact=True).click()
        page.locator('[id="ingredients.0.quantity"]').fill('2,5')
        assert page.locator('[name="ingredients.0.line_public_id"]').input_value() == line_id
        page.locator('.admin-form-footer [form="recipe-editor"][data-semantic="actions.save"]').click()
        error = page.locator('#recipe-error')
        expect(error).to_contain_text('Dezimalzahl')
        invalid = page.locator('textarea[aria-invalid="true"]')
        expect(invalid).to_have_count(1)
        expect(invalid).to_be_focused()
        field_id = invalid.get_attribute('id')
        assert field_id
        expect(page.locator(f'label[for="{field_id}"]')).to_contain_text('ingredients.0.quantity')
        assert invalid.input_value().strip() == '2,5'
        other = page.locator('label', has_text='ingredients.1.quantity')
        other_id = other.get_attribute('for')
        assert other_id
        assert page.locator(f'#{other_id}').input_value().strip() == '3'
        expect(page.locator(f'#{other_id}')).not_to_have_attribute('aria-invalid', 'true')
        line_label = page.locator('label', has_text='ingredients.0.line_public_id')
        line_for = line_label.get_attribute('for')
        assert line_for and page.locator(f'#{line_for}').input_value().strip() == line_id
    finally:
        context.close()
