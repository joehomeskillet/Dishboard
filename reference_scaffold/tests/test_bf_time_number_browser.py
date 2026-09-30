"""BF-E2 time and number contracts: T17 browser zones, T18 quantities and price."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria.workflow_partial_store import persist_week_header
from test_admin_ux_browser import live_server as live_server  # noqa: F401
from test_admin_workflow_routes import _login, _scope
from test_master_data_browser import master_server  # noqa: F401
from test_master_data_db import signed_in
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_rendered_ui import admin_app as admin_app, admin_engine as admin_engine, browser as browser  # noqa: F401
from test_recipe_store_db import payload as recipe_payload

BOUNDARY = '2026-12-28'
NEXT_WEEK = '2027-01-04'
ZONES = ('Pacific/Kiritimati', 'Pacific/Pago_Pago')


def _workflow_context(browser, live_server, admin_app, admin_engine, timezone_id: str):
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    context = browser.new_context(
        base_url=live_server, timezone_id=timezone_id, java_script_enabled=True,
        reduced_motion='reduce', viewport={'width': 1280, 'height': 900},
    )
    cookie = client.get_cookie('session')
    assert cookie is not None
    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
    return context, user_id


def test_t17_year_boundary_week_ignores_browser_timezone(browser, live_server, admin_app, admin_engine):  # noqa: F811
    """T17: UTC+14 and UTC-11 show the same Zurich week, range and write target."""
    _client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, user_id, 'staff_guest')
    persist_week_header(
        admin_engine, scope, date.fromisoformat(BOUNDARY),
        {'title': 'BFGrenze', 'shared_note': ''}, 0,
    )
    today_hrefs = []
    for zone in ZONES:
        context, _user = _workflow_context(browser, live_server, admin_app, admin_engine, zone)
        try:
            page = context.new_page()
            page.goto(f'/admin/cafeteria?week={BOUNDARY}', wait_until='load')
            expect(page.locator('main[data-week]')).to_have_attribute('data-week', BOUNDARY)
            expect(page.locator('body')).to_contain_text('28. Dezember 2026–1. Januar 2027 · KW 53')
            weeks = page.locator('input[name="week"]').evaluate_all('els => els.map(el => el.value)')
            assert weeks and set(weeks) == {BOUNDARY}
            page.goto(f'/admin/cafeteria?week={NEXT_WEEK}', wait_until='load')
            expect(page.locator('main[data-week]')).to_have_attribute('data-week', NEXT_WEEK)
            expect(page.locator('body')).to_contain_text('4.–8. Januar 2027 · KW 1')
            page.goto('/admin/cafeteria/wochen', wait_until='load')
            expect(page.locator('body')).to_contain_text('KW 53 / 2026')
            page.goto('/admin/kuechenkalender', wait_until='load')
            href = page.get_by_role('link', name='Heute', exact=True).get_attribute('href')
            assert href
            today_hrefs.append(parse_qs(urlsplit(href).query))
        finally:
            context.close()
    assert today_hrefs[0] == today_hrefs[1]


@pytest.mark.parametrize('javascript', [False, True])
def test_t18_recipe_quantity_keeps_six_places_and_rejects_comma(
    b3, master_server, browser, javascript,  # noqa: F811
):
    """T18 recipe: 1.234567 round-trips; a comma stays on the field and is explained."""
    from cafeteria import recipe_store as store
    app, _owner, _client, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        created = store.create_recipe(engine, actor, recipe_payload(title='BFMenge'), expected_location_id=location)
    base, cookie = master_server
    context = browser.new_context(
        viewport={'width': 1280, 'height': 900}, java_script_enabled=javascript, reduced_motion='reduce',
    )
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
    try:
        page = context.new_page()
        page.goto(base + f'/admin/rezepte/{created.public_id}', wait_until='load')
        page.locator('[id="ingredients.0.quantity"]').fill('1.234567')
        page.locator('.admin-compact-toolbar [data-semantic="actions.save"]').click()
        expect(page.locator('[id="ingredients.0.quantity"]')).to_be_visible()
        shown = page.locator('[id="ingredients.0.quantity"]').input_value()
        assert Decimal(shown) == Decimal('1.234567')
        with signed_in(engine, actor):
            stored = store.get_recipe(engine, created.public_id).payload['ingredients'][0]['quantity']
        assert Decimal(str(stored)) == Decimal('1.234567')
        page.locator('[id="ingredients.0.quantity"]').fill('2,5')
        page.locator('.admin-compact-toolbar [data-semantic="actions.save"]').click()
        expect(page.locator('#recipe-error')).to_contain_text('Dezimalzahl')
        invalid = page.locator('textarea[aria-invalid="true"]')
        expect(invalid).to_have_count(1)
        expect(page.locator('label', has_text='ingredients.0.quantity')).to_be_visible()
        assert invalid.input_value().strip() == '2,5'
    finally:
        context.close()
