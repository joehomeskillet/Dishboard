"""Repeated missing-data markers stay precise while the week owns the warning summary."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

from cafeteria.course_store import persist_service_courses
from test_admin_ux_browser import live_server, page_context
from test_admin_workflow_db import _actor_id, _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, WEEK, _scope
from test_course_week_html import _recipe
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']


@pytest.mark.parametrize('family,profile,slots,services', [
    ('cafeteria', 'staff_guest', 10, 5), ('patienten', 'patient', 28, 14),
])
@pytest.mark.parametrize('state', ['missing', 'mixed', 'complete'])
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_week_warning_summary_and_precise_compact_records(
    page_context, admin_engine, tmp_path, family, profile, slots, services, state, width, height,
):
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    index = 0
    for day_index, day in enumerate(values['days']):
        for service_index, service in enumerate(day['services']):
            missing_time = state == 'missing' or (state == 'mixed' and day_index == service_index == 0)
            service['service_start'] = '' if missing_time else '11:30' if service['meal_code'] == 'LUNCH' else '17:30'
            service['service_end'] = '' if missing_time else '13:30' if service['meal_code'] == 'LUNCH' else '19:30'
            for option in service['options']:
                missing_allergens = state == 'missing' or (state == 'mixed' and index == 0)
                option['allergens'] = [] if missing_allergens else [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
                option['allergen_review_status'] = 'not_checked'
                index += 1
    _save(admin_engine, profile, values)
    actor = _actor_id(admin_engine)
    scope = _scope(admin_engine, actor, profile)
    meals = ('LUNCH',) if family == 'cafeteria' else ('LUNCH', 'DINNER')
    if state != 'complete':
        soup = _recipe(admin_engine, actor, scope.location_id, 'Synthetische Gemüsesuppe')
        dessert = _recipe(admin_engine, actor, scope.location_id, 'Synthetisches Apfelkompott')
    for meal in meals:
        persist_service_courses(
            admin_engine, scope, WEEK, DAY, meal,
            soup={'state': 'not_offered'} if state == 'complete' else {'state': 'planned', 'recipe_public_id': soup['public_id']},
            dessert={'state': 'planned', 'recipe_public_id': dessert['public_id']} if state == 'missing' else {'state': 'not_offered'},
            exceptions=[],
        )
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    response = page.goto(f'/admin/{family}?week={DAY}', wait_until='networkidle')
    assert response is not None and response.status == 200
    page.evaluate('document.fonts.ready')
    summary = page.locator('#week-check-summary')
    missing_count = slots if state == 'missing' else 1 if state == 'mixed' else 0
    missing_times = services if state == 'missing' else 1 if state == 'mixed' else 0
    review_count = slots - missing_count
    course_count = len(meals) * (2 if state == 'missing' else 1 if state == 'mixed' else 0)
    expected = [f'{slots} Menüs mit offener Kartenprüfung.']
    if missing_count:
        expected.append(f'{missing_count} {"Menü" if missing_count == 1 else "Menüs"}: Allergenangaben nicht erfasst (nicht allergenfrei).')
    if review_count:
        expected.append(f'{review_count} {"Menü" if review_count == 1 else "Menüs"}: Allergenprüfung offen.')
    if missing_times:
        expected.append(f'{missing_times} {"Mahlzeit" if missing_times == 1 else "Mahlzeiten"}: Zeiten nicht eingetragen.')
    if course_count:
        expected.append(f'{course_count} {"Gang" if course_count == 1 else "Gänge"} prüfen. {course_count} ohne Allergenangaben (nicht allergenfrei).')
    expect(summary.locator('[role="status"]')).to_have_text(' '.join(expected))
    expect(page.get_by_role('link', name='Wochenangaben prüfen', exact=True)).to_have_attribute(
        'href', f'/admin/{family}/wochen/pruefung?week={DAY}',
    )
    expect(page.locator('.menu-slot')).to_have_count(slots)
    expect(page.locator('.admin-week-meal-head')).to_have_count(services)
    expect(page.locator('#week-publish-form [type="submit"]')).to_be_disabled()
    # Complete data remains unreviewed after saving; opening this view never lifts the lock.
    expect(page.locator('main')).to_have_attribute('data-status', 'review_open')
    form_contracts = page.locator('.admin-week-service-form, #week-publish-form').evaluate_all('''forms => forms.map(form => ({
        action: new URL(form.action).pathname, method: form.method, fields: [...new FormData(form)]
    }))''')
    assert all(form['method'] == 'post' for form in form_contracts)
    assert all(dict(form['fields'])['_csrf'] for form in form_contracts)
    assert all(dict(form['fields'])['week'] == DAY for form in form_contracts)
    assert all('row_version' in dict(form['fields']) for form in form_contracts)
    for form in form_contracts:
        fields = dict(form['fields'])
        if form['action'].endswith('/service'):
            assert form['action'] == f'/admin/{family}/service'
            assert set(fields) == {'_csrf', 'week', 'day', 'meal', 'row_version', 'service_state', 'notice', 'service_start', 'service_end'}
        else:
            assert form['action'] == f'/admin/{family}/publish'
            assert set(fields) == {'_csrf', 'week', 'row_version'}
    summary.locator('summary').press('Enter')
    missing_links = summary.locator('a').filter(has_text='Allergenangaben nicht erfasst')
    expect(missing_links).to_have_count(missing_count)
    for link in missing_links.all():
        expect(page.locator(link.get_attribute('href'))).to_contain_text('Allergenangaben nicht erfasst')
    summary.locator('summary').press('Enter')
    if course_count:
        course_issues = page.locator('#course-issues')
        course_issues.locator('summary').press('Enter')
        expect(course_issues.locator('li')).to_have_count(course_count)
        expect(course_issues).to_contain_text('Allergenangaben fehlen')
        expect(course_issues).to_contain_text('Nährwertangaben fehlen')
        course_issues.locator('summary').press('Enter')
    warnings = page.locator('[data-menu-metadata] > p').filter(has_text='Allergen')
    expect(warnings).to_have_count(missing_count + review_count)
    # Screenshot precedes presentation assertions so a baseline run preserves before evidence.
    page.keyboard.press('Escape')
    page.locator('h1').click()
    page.screenshot(path=str(tmp_path / f'{family}-{state}-{width}.png'), full_page=True)
    metrics = warnings.evaluate_all('''nodes => nodes.map(node => ({
        text: node.textContent.trim(), height: node.getBoundingClientRect().height,
        fontSize: getComputedStyle(node).fontSize, background: getComputedStyle(node).backgroundColor,
        badges: node.querySelectorAll('.admin-status, .badge').length
    }))''')
    (tmp_path / 'record-warning-metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert all(metric['badges'] == 0 for metric in metrics)
    assert all(metric['fontSize'] == '13px' for metric in metrics)
    expect(page.locator('.admin-week-meal-head .admin-status--warning')).to_have_count(0)
    expect(page.locator('.admin-week-course-line [data-allergen-state="missing"]')).to_have_count(course_count)
    expect(page.locator('.admin-week-course-line .admin-status--warning')).to_have_count(0)
    if missing_count:
        expect(warnings.first).to_contain_text('nicht allergenfrei')
        assert warnings.first.evaluate('node => node.closest("details")') is None
    if state == 'complete':
        expect(summary).not_to_contain_text('Allergenangaben nicht erfasst')
        expect(summary).not_to_contain_text('Zeiten nicht eingetragen')
