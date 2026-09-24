from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from datetime import timedelta
from urllib.parse import parse_qs

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader
from playwright.sync_api import Page, expect, sync_playwright

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_db import _patient_values, _save, _save_reviewed, _staff_values
from test_admin_workflow_routes import DAY, DATABASE_URL, WEEK, _login, _scope
from test_course_week_html import _recipe
from cafeteria.course_store import persist_service_courses
from cafeteria.menu_images import CATALOG

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

VIEWPORTS = ((360, 800), (768, 1024), (820, 1180), (1024, 768), (1199, 800), (1200, 800), (1280, 800))


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_wp21_density_keyboard_and_nojs(admin_app, admin_engine, live_server, tmp_path, family, profile):  # noqa: F811
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    if family == 'cafeteria':
        photo = next(row for row in json.loads(CATALOG.read_text()) if row['status'] == 'ready')
        for day in values['days']:
            day['services'][0]['options'][0].update(title=photo['title'], components=photo['components'])
    _save(admin_engine, profile, values)
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    if family == 'cafeteria':
        engine = admin_app.extensions['cafeteria_db']
        scope = _scope(admin_engine, user_id, profile)
        soup = _recipe(engine, user_id, scope.location_id, 'Gemüsesuppe')
        dessert = _recipe(engine, user_id, scope.location_id, 'Fruchtsalat')
        for day in values['days']:
            persist_service_courses(engine, scope, WEEK, day['date'], 'LUNCH',
                                    soup={'state': 'planned', 'recipe_public_id': soup['public_id']},
                                    dessert={'state': 'planned', 'recipe_public_id': dessert['public_id']})
    cookie = client.get_cookie('session')
    measurements = []
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=True) as own_browser:
            for javascript in (True, False):
                with own_browser.new_context(base_url=live_server, java_script_enabled=javascript,
                                             reduced_motion='reduce') as context:
                    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
                    page = context.new_page()
                    for width, height in ((360, 800), (768, 1024), (1024, 768), (1440, 900)):
                        page.set_viewport_size({'width': width, 'height': height})
                        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
                        page.evaluate('document.fonts.ready')
                        metrics = page.evaluate('''() => {
                            const days = [...document.querySelectorAll('.admin-day-card, .patient-admin-day')];
                            const boxes = days.map(e => e.getBoundingClientRect());
                            const meals = [...days[0].querySelectorAll('.patient-admin-meal')];
                            const image = days[0].querySelector('[data-menu-image] img');
                            const mealGaps = meals.map(meal => {
                                const parts = [...meal.querySelectorAll('.admin-week-meal-head, .menu-slot, .admin-week-service, .admin-week-course')]
                                    .map(e => e.getBoundingClientRect()).sort((a, b) => a.top - b.top);
                                let end = meal.getBoundingClientRect().top, gap = 0;
                                for (const part of parts) {
                                    gap = Math.max(gap, part.top - end);
                                    end = Math.max(end, part.bottom);
                                }
                                return Math.max(gap, meal.getBoundingClientRect().bottom - end);
                            });
                            return {width: innerWidth, documentWidth: document.documentElement.scrollWidth,
                                dayHeight: boxes[0].height, firstDayTop: boxes[0].top,
                                visibleDays: boxes.filter(r => r.top >= 0 && r.bottom <= innerHeight).length,
                                mealOffset: meals.length ? Math.abs(meals[0].getBoundingClientRect().top -
                                    meals[1].getBoundingClientRect().top) : 0,
                                imageWidth: image ? image.getBoundingClientRect().width : 0,
                                imageHeight: image ? image.getBoundingClientRect().height : 0,
                                mealGap: Math.max(0, ...mealGaps),
                                cardParts: [...days[0].querySelector('.menu-slot .card-body').children].map(e =>
                                    ({tag: e.tagName, cls: e.className, height: e.getBoundingClientRect().height,
                                      top: e.getBoundingClientRect().top})),
                                dayParts: [...days[0].querySelectorAll('.card-header, .card-body, .admin-week-meal-head, .admin-week-service, .admin-week-course, .admin-week-course-editor')].filter(e => !e.closest('form')).map(e =>
                                    ({cls: e.className, height: e.getBoundingClientRect().height, top: e.getBoundingClientRect().top}))};
                        }''')
                        metrics.update(family=family, javascript=javascript)
                        measurements.append(metrics)
                        page.screenshot(path=str(tmp_path / f'{family}-{width}-{javascript}.png'), full_page=True)
                        page.screenshot(path=str(tmp_path / f'{family}-{width}-{javascript}-viewport.png'))
                        assert metrics['documentWidth'] <= width + 1, metrics
                        expect(page.locator('.admin-statusbar')).to_be_visible()
                        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
                        if family == 'cafeteria':
                            expect(page.locator('.admin-day-card').first).to_contain_text('Suppe: Gemüsesuppe')
                            expect(page.locator('.admin-day-card').first).to_contain_text('Dessert: Fruchtsalat')
                            expect(page.locator('.admin-day-card').first).to_contain_text('Allergenangaben fehlen')
                        service = page.locator('.admin-week-service > summary').first
                        service.focus()
                        page.keyboard.press('Enter')
                        expect(page.locator('.admin-week-service[open]').first).to_be_visible()
                        page.keyboard.press('Tab')
                        expect(page.locator('.admin-week-service select').first).to_be_focused()
                        assert page.locator(':focus').evaluate('e => parseFloat(getComputedStyle(e).outlineWidth)') >= 2
    (tmp_path / 'measurements.json').write_text(json.dumps(measurements, indent=2))
    print('WP21_METRICS=' + json.dumps(measurements))
    desktop = [row for row in measurements if row['width'] == 1440]
    for row in desktop:
        assert row['dayHeight'] <= (260 if family == 'cafeteria' else 300), row
        assert row['mealOffset'] <= 8, row
        assert row['mealGap'] <= 160, row
        assert max(row['imageWidth'], row['imageHeight']) <= 96, row
        if family == 'cafeteria':
            assert row['visibleDays'] >= 2, row


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


@pytest.mark.parametrize('family,profile,values', [
    ('cafeteria', 'staff_guest', _staff_values), ('patienten', 'patient', _patient_values),
])
def test_wp21_nojs_publish_keeps_exact_payload(admin_app, admin_engine, live_server, browser, family, profile, values):  # noqa: F811
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, values())
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    # This module's existing sync_playwright fixture is already active in the full suite.
    with browser.new_context(base_url=live_server, java_script_enabled=False,
                             viewport={'width': 360, 'height': 800}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        page.goto(f'/admin/{family}?week={DAY}')
        form = page.locator('#week-publish-form')
        before = dict(form.locator('input[name]').evaluate_all('els => els.map(e => [e.name, e.value])'))
        summary = page.locator('.admin-week-nojs-publish > summary')
        summary.focus()
        page.keyboard.press('Enter')
        page.keyboard.press('Tab')
        expect(page.locator('.admin-week-nojs-publish button')).to_be_focused()
        with page.expect_response(lambda response: response.request.method == 'POST') as published:
            page.keyboard.press('Enter')
        assert published.value.status == 303
        assert parse_qs(published.value.request.post_data, keep_blank_values=True) == {
            key: [value] for key, value in before.items()
        }
        assert set(before) == {'_csrf', 'week', 'row_version'}
        expect(page.locator('main')).to_have_attribute('data-status', 'live')


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
    page.locator('details.admin-week-settings, details.admin-week-service').evaluate_all(
        'els => els.forEach(el => { el.open = true })',
    )
    toggle = page.get_by_role('button', name='Menü', exact=True)
    nav = page.get_by_role('navigation', name='Backend')
    if width < 992:  # K2-A: sidebar breakpoint moved from 1200 to 992 (navbar-expand-lg)
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
    assert review_links.count() == 1
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
    page.locator('details.admin-week-settings > summary').click()
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
        header.get_by_role('button', name='Speichern').click()
    assert saved.value.status == 303
    payload = parse_qs(saved.value.request.post_data, keep_blank_values=True)
    assert set(payload) == {'_csrf', 'week', 'row_version', 'title', 'shared_note'}
    assert payload['week'] == [DAY]
    # The existing POST redirects to a legacy header fragment; inspect persisted overview data.
    page.goto(f'/admin/{family}?week={DAY}')
    page.locator('details.admin-week-settings > summary').click()
    expect(header.locator('[name="title"]')).to_have_value('Gespeicherte Wochenangaben')
    expect(header.locator('[name="shared_note"]')).to_have_value('Saisonales Angebot')

    page.locator('details.admin-week-service').first.evaluate('el => { el.open = true }')
    service = page.locator(f'form[action="/admin/{family}/service"]').first
    service.locator('[name="service_state"]').select_option('open')
    service.locator('[name="notice"]').fill('Geänderte Ausgabezeit')
    service.locator('[name="service_start"]').fill('11:45')
    service.locator('[name="service_end"]').fill('13:45')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved_service:
        service.get_by_role('button', name='Speichern').click()
    assert saved_service.value.status == 303
    payload = parse_qs(saved_service.value.request.post_data, keep_blank_values=True)
    assert set(payload) == {
        '_csrf', 'week', 'row_version', 'day', 'meal', 'service_state', 'notice',
        'service_start', 'service_end',
    }
    assert payload['week'] == payload['day'] == [DAY]
    assert payload['meal'] == ['LUNCH']
    assert payload['service_start'] == ['11:45']
    assert payload['service_end'] == ['13:45']
    page.goto(f'/admin/{family}?week={DAY}')
    page.locator('details.admin-week-service').first.evaluate('el => { el.open = true }')
    expect(service.locator('[name="service_state"]')).to_have_value('open')
    expect(service.locator('[name="notice"]')).to_have_value('Geänderte Ausgabezeit')
    expect(service.locator('[name="service_start"]')).to_have_value('11:45')
    expect(service.locator('[name="service_end"]')).to_have_value('13:45')


def test_p4_density_and_native_form_contract(page_context, admin_app, admin_engine, tmp_path, caplog):  # noqa: F811
    """Compare owned templates to the assigned release candidate, without checkout."""
    _save_reviewed(admin_engine, 'staff_guest', _staff_values())
    _save_reviewed(admin_engine, 'patient', _patient_values())
    root = Path(__file__).resolve().parents[2]
    names = ('_course_editor', '_course_line', '_course_recipe_search', '_service_courses',
             '_week_controls', '_week_menu_card', '_week_service', '_week_settings',
             'cafeteria', 'copy', 'kuechenkalender', 'week_management', 'week_review')
    sources = {}
    for name in names:
        path = f'admin/{name}.html'
        sources[path] = subprocess.run(
            ['git', 'cat-file', 'blob',
             f'2932189c7276edbe984b5bf880b3293e84230493:reference_scaffold/cafeteria/templates/{path}'],
            cwd=root, check=True, capture_output=True, text=True,
        ).stdout
    routes = {'cafeteria': f'/admin/cafeteria?week={DAY}',
              'patienten': f'/admin/patienten?week={DAY}',
              'management': '/admin/cafeteria/wochen',
              'review': f'/admin/cafeteria/wochen/pruefung?week={DAY}',
              'copy': f'/admin/cafeteria/copy?week={WEEK + timedelta(weeks=1)}',
              'calendar': f'/admin/kuechenkalender?year={WEEK.year}&month={WEEK.month}'}
    loader = admin_app.jinja_env.loader
    measurements = {}
    page = page_context
    try:
        for phase in ('before', 'after'):
            admin_app.jinja_env.loader = ChoiceLoader([DictLoader(sources), loader]) if phase == 'before' else loader
            admin_app.jinja_env.cache.clear()
            for name, route in routes.items():
                for width in (360, 1440):
                    page.set_viewport_size({'width': width, 'height': 900})
                    response = page.goto(route)
                    assert response is not None and response.status == 200, caplog.text
                    page.evaluate('document.fonts.ready')
                    metrics = page.evaluate('''() => ({
                        height: document.documentElement.scrollHeight,
                        width: document.documentElement.scrollWidth,
                        rows: [...document.querySelectorAll('.admin-day-card, .patient-admin-day, tr[data-week-id]')]
                            .map(e => e.getBoundingClientRect().height),
                        fields: [...document.querySelectorAll('main input, main select, main textarea, main button')]
                            .map(e => ({tag: e.tagName, type: e.type, name: e.name,
                                value: e.name === '_csrf' ? Boolean(e.value) : e.value,
                                form: e.form?.id, action: e.form?.getAttribute('action'),
                                disabled: e.disabled})),
                    })''')
                    measurements[f'{phase}-{name}-{width}'] = metrics
                    page.screenshot(path=str(tmp_path / f'p4-{phase}-{name}-{width}.png'), full_page=True)
    finally:
        admin_app.jinja_env.loader = loader
        admin_app.jinja_env.cache.clear()
    (tmp_path / 'p4-density-contract.json').write_text(json.dumps(measurements, indent=2))
    for name in routes:
        for width in (360, 1440):
            before, after = (measurements[f'{phase}-{name}-{width}'] for phase in ('before', 'after'))
            assert after['fields'] == before['fields'], (name, width)
            assert after['width'] <= width, (name, width, after)
            if width == 1440:
                assert after['height'] <= before['height'] + 1, (name, before['height'], after['height'])
                assert len(after['rows']) == len(before['rows'])
                assert all(a <= b + 1 for a, b in zip(after['rows'], before['rows'])), (name, before['rows'], after['rows'])
