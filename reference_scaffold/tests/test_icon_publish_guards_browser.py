from __future__ import annotations

from hashlib import sha256
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, WEEK, _login, _payload, _scope
from review_support import write_expectations
from cafeteria.db import active_snapshot
from cafeteria.workflow import load_draft
from cafeteria.workflow_partial_store import persist_menu_item
from cafeteria.workflow_review_context import get_week_review

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


def _database_snapshot(engine):
    # Compare complete rows, including versions, review receipts and withdrawal fields.
    tables = (
        'menu_weeks', 'menu_services', 'menu_items', 'menu_item_components',
        'menu_item_allergens', 'menu_item_labels', 'menu_item_prices',
        'origin_declarations', 'menu_components', 'component_allergens',
        'component_labels', 'menu_service_courses', 'menu_item_course_exceptions',
        'publication_revisions', 'publication_lifecycle_events', 'audit_events',
    )
    with engine.connect() as connection:
        return {
            table: sha256(connection.execute(text(
                "SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), "
                f"'[]'::jsonb)::text FROM cafeteria.{table} t"
            )).scalar_one().encode()).hexdigest()
            for table in tables
        }


def _native_publish(page, family):
    form = page.locator('#week-publish-form')
    expect(form).to_have_attribute('method', 'post')
    expect(form).to_have_attribute('action', f'/admin/{family}/publish')
    fields = {
        field.get_attribute('name'): [field.input_value()]
        for field in form.locator('input[name]').all()
    }
    with page.expect_navigation(wait_until='domcontentloaded'), page.expect_response(
        lambda response: response.request.method == 'POST'
        and response.url.endswith(f'/admin/{family}/publish')
    ) as response:
        # Native form submission bypasses disabled controls, including with site JS off.
        form.evaluate('form => HTMLFormElement.prototype.submit.call(form)')
    assert response.value.request.is_navigation_request()
    assert parse_qs(response.value.request.post_data, keep_blank_values=True) == fields
    return response.value


@pytest.fixture(params=[
    ('cafeteria', 'staff_guest', _staff_values),
    ('patienten', 'patient', _patient_values),
], ids=['cafeteria', 'patienten'])
def blocked_week(request, admin_app, admin_engine, live_server, browser, javascript):  # noqa: F811
    family, profile, values = request.param
    data = values()
    for day in data['days']:
        for service in day['services']:
            service.update(service_start='11:30', service_end='13:30')
            for option in service['options']:
                option['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    _save_reviewed(admin_engine, profile, data)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    scope = _scope(admin_engine, actor, profile)
    overview = f'/admin/{family}?week={DAY}'
    with browser.new_context(
        base_url=live_server, java_script_enabled=javascript,
        viewport={'width': 1440, 'height': 900}, reduced_motion='reduce',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        assert page.goto(overview).status == 200
        # Positive control proves the role, route, scoped CSRF and CAS really can publish.
        assert _native_publish(page, family).status == 303
        old_publication = active_snapshot(admin_engine, profile, DAY)
        assert old_publication is not None
        stale_version = page.locator('#week-publish-form [name="row_version"]').input_value()
        item_version = page.locator(f'#week-slot-{DAY}-LUNCH-MENU_1').get_attribute('data-row-version')
        persist_menu_item(
            admin_engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1',
            _payload(staff=profile == 'staff_guest'), int(item_version),
        )
        draft = load_draft(admin_engine, profile, WEEK, actor_id=actor,
                           **write_expectations(admin_engine, actor))
        pending = [item for day in draft['days'] for service in day['services']
                   for item in service['options'] if item['allergen_review_status'] != 'checked']
        assert len(pending) == 1 and pending[0]['allergens'] == []
        assert get_week_review(admin_engine, scope, WEEK)['receipt'] is not None
        assert page.goto(overview).status == 200
        form = page.locator('#week-publish-form')
        expect(form.locator('[name="week"]')).to_have_value(DAY)
        expect(form.locator('[name="row_version"]')).to_have_value(str(draft['row_version']))
        assert int(stale_version) < draft['row_version']
        assert active_snapshot(admin_engine, profile, DAY) == old_publication
        yield page, family, profile, stale_version, old_publication


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_blocked_publish_explains_guard_and_links_to_review(blocked_week, admin_engine, tmp_path):  # noqa: F811
    page, family, profile, _, old_publication = blocked_week
    before = _database_snapshot(admin_engine)
    posts = []
    page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
    for width, height in ((1440, 900), (390, 844)):
        page.set_viewport_size({'width': width, 'height': height})
        trigger = page.locator('[data-bs-target="#week-publish-modal"]')
        expect(trigger).to_be_visible()
        expect(trigger).to_be_disabled()
        expect(trigger).to_have_attribute('aria-describedby', 'week-publish-guidance')
        guidance = page.locator('#week-publish-guidance')
        expect(guidance).to_be_visible()
        expect(guidance).to_contain_text('Zuerst offene Prüfungen abschliessen')
        summary = page.locator('#week-check-summary')
        expect(summary).to_contain_text('1 Menü mit offener Kartenprüfung.')
        expect(summary).to_contain_text('Allergenangaben nicht erfasst (nicht allergenfrei).')
        for button in page.locator('button[data-semantic="actions.publish"]').all():
            expect(button).to_be_disabled()
        fallback = page.locator('.admin-week-nojs-publish')
        if fallback.count():
            expect(fallback.locator('summary')).to_have_count(0)
            expect(fallback).to_be_visible()
            expect(page.locator('button[form="week-publish-form"]')).to_be_disabled()
        guidance.scroll_into_view_if_needed()
        page.screenshot(path=str(tmp_path / f'{family}-blocked-{width}.png'))
        review = page.get_by_role('link', name='Wochenangaben prüfen', exact=True)
        expect(review).to_be_visible()
        expect(review).to_have_attribute('href', f'/admin/{family}/wochen/pruefung?week={DAY}')
        review.focus()
        expect(review).to_be_focused()
        review.press('Enter')
        page.wait_for_url(f'**/admin/{family}/wochen/pruefung?week={DAY}')
        expect(page.get_by_role('heading', name='Wochenangaben prüfen', exact=True)).to_be_visible()
        expect(page.locator('[data-week-review-intro]')).to_contain_text('Die Menüs werden einzeln geprüft.')
        assert _database_snapshot(admin_engine) == before
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        page.locator('#week-check-entries > summary').click()
        affected = page.locator('#week-check-entries a', has_text='Kartenprüfung offen')
        expect(affected).to_have_count(1)
        affected.focus()
        affected.press('Enter')
        slot = page.locator(f'#week-slot-{DAY}-LUNCH-MENU_1')
        slot.locator('[data-semantic="actions.edit"]').click()
        expect(page.locator(f'form[action="/admin/{family}/menu/review"]')).to_have_count(1)
        expect(page.locator('#review')).to_be_visible()
        expect(page.locator('[data-review-field="allergens"]')).to_contain_text('Allergenangaben nicht erfasst')
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
    assert posts == []
    assert _database_snapshot(admin_engine) == before
    assert active_snapshot(admin_engine, profile, DAY) == old_publication


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('case,status,message', [
    ('open-review', 400, 'Allergendeklaration ist nicht geprüft.'),
    ('missing-csrf', 400, 'CSRF-Prüfung fehlgeschlagen.'),
    ('wrong-csrf', 400, 'CSRF-Prüfung fehlgeschlagen.'),
    ('stale-cas', 409, 'Der Entwurf wurde zwischenzeitlich geändert.'),
])
def test_publish_guards_preserve_existing_publication(
    blocked_week, admin_engine, case, status, message,  # noqa: F811
):
    page, family, profile, stale_version, old_publication = blocked_week
    form = page.locator('#week-publish-form')
    assert form.locator('input[name]').count() == 3
    csrf = form.locator('[name="_csrf"]')
    assert csrf.input_value().startswith('v2.')
    if case == 'missing-csrf':
        csrf.evaluate('input => input.remove()')
    elif case == 'wrong-csrf':
        # Keep the scoped envelope intact; invalidate the session CSRF value itself.
        csrf.evaluate("input => { const parts = input.value.split('.'); "
                      "parts[1] = 'invalid-csrf'; input.value = parts.join('.'); }")
    elif case == 'stale-cas':
        form.locator('[name="row_version"]').evaluate('(input, value) => input.value = value', stale_version)
    before = _database_snapshot(admin_engine)
    response = _native_publish(page, family)
    assert response.status == status
    assert message in response.text()
    assert active_snapshot(admin_engine, profile, DAY) == old_publication
    assert _database_snapshot(admin_engine) == before
