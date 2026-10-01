"""UI-DELTA: static publication fallback and exclusive confirmation actions."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import live_server, page_context
from cafeteria.course_store import persist_service_courses
from test_admin_workflow_db import _actor_id, _patient_values, _save, _save_reviewed, _staff_values
from test_admin_workflow_routes import DAY, WEEK, _scope
from test_course_week_html import _recipe
from test_delta_renderer_browser import VISIBILITY, source_revision
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
def test_confirmation_modes_and_native_fallback(
    browser, live_server, page_context, admin_engine, tmp_path, family, profile,
    width, height, touch,
):
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    _save_reviewed(admin_engine, profile, values)
    for js in (True, False):
        with browser.new_context(
            base_url=live_server, viewport={'width': width, 'height': height},
            has_touch=touch, java_script_enabled=js, reduced_motion='reduce',
            storage_state=page_context.context.storage_state(),
        ) as context:
            page = context.new_page()
            assert page.goto(f'/admin/{family}?week={DAY}').status == 200
            page.evaluate('document.fonts.ready')
            if js:
                trigger = page.locator('[data-bs-target="#week-publish-modal"]')
                trigger.click()
                area = page.locator('#week-publish-modal')
                expect(area).to_be_visible()
                expect(area.locator('[data-bs-dismiss="modal"]')).to_have_count(1)
                controls = area.locator('.modal-footer button')
            else:
                area = page.locator('.admin-week-nojs-publish')
                expect(area).to_be_visible()
                expect(area.locator('details, summary')).to_have_count(0)
                controls = area.locator('button')
                expect(controls).to_have_attribute('form', 'week-publish-form')
            for control in controls.all():
                visible = control.evaluate(VISIBILITY)
                assert visible['icons'] == 0, visible
                assert visible['text'], visible
                assert visible['text'] in control.get_attribute('aria-label')
            page.screenshot(path=str(tmp_path / f'{family}-{width}-{touch}-js{js}.png'))
            if js:
                area.get_by_role('button', name='Abbrechen', exact=True).click()
                expect(area).to_be_hidden()
                expect(trigger).to_be_focused()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def test_empty_week_has_one_first_slot_action(page_context):
    page = page_context
    assert page.goto('/admin/cafeteria?week=2026-09-07').status == 200
    first = page.locator('.menu-slot').first.locator('a[data-semantic="actions.add"]')
    expect(first).to_be_visible()
    href = first.get_attribute('href')
    expect(page.locator(f'a[href="{href}"]')).to_have_count(1)
    first.click()
    expect(page.locator('form[data-menu-editor]')).to_be_visible()


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height,touch', [(1440, 900, False), (1440, 900, True), (390, 844, False), (390, 844, True)])
@pytest.mark.parametrize('javascript', [True, False])
def test_affected_entries_dialog_and_background_targets(
    browser, live_server, page_context, admin_engine, tmp_path,
    family, profile, width, height, touch, javascript,
):
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    for day in values['days']:
        for service in day['services']:
            service['service_start'] = service['service_end'] = ''
            for option in service['options']:
                option['allergens'] = []
                option['allergen_review_status'] = 'not_checked'
    _save(admin_engine, profile, values)
    actor = _actor_id(admin_engine)
    scope = _scope(admin_engine, actor, profile)
    recipe = _recipe(admin_engine, actor, scope.location_id, 'Synthetische Suppe - ohne Angaben')
    persist_service_courses(
        admin_engine, scope, WEEK, DAY, 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': recipe['public_id']},
        dessert={'state': 'not_offered'}, exceptions=[],
    )
    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=touch, java_script_enabled=javascript, reduced_motion='reduce',
        storage_state=page_context.context.storage_state(),
    ) as context:
        page = context.new_page()
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(tmp_path / 'week.png'))
        expect(page.locator('main details')).to_have_count(0)
        trigger = page.locator('[data-read-detail="week-check-entries"]')
        expect(trigger).to_have_count(1)
        mode = trigger.evaluate(VISIBILITY)
        assert mode['icons'] == 1 and not mode['text'], mode
        expect(page.locator('.admin-week-checkline')).to_contain_text('1 Gang prüfen')
        expect(page.locator('.admin-week-checkline')).to_contain_text('nicht allergenfrei')
        geometry = '''() => ({scroll: scrollY,
            scrollbar: innerWidth-document.documentElement.clientWidth,
            boxes: ['.page-wrapper', '#week-check-summary', '.admin-week-controls',
                    '.admin-week-settings', '.admin-day-card'].map(s => {
                const r = document.querySelector(s).getBoundingClientRect();
                return {x:r.x, y:r.y, width:r.width, height:r.height};
            })})'''
        trigger.scroll_into_view_if_needed()
        trigger.focus()
        before = page.evaluate(geometry)
        trigger.press('Enter')
        dialog = page.locator('#week-check-entries')
        expect(dialog).to_be_visible()
        if not javascript:
            assert dialog.evaluate('el => el.matches(":target")')
        expect(dialog.locator('details, summary, form')).to_have_count(0)
        expect(dialog.locator('[data-read-detail-close]')).to_have_count(1)
        expect(dialog.locator('#course-issues')).to_contain_text('Allergenangaben fehlen')
        expect(dialog.locator('#course-issues')).to_contain_text('Nährwertangaben fehlen')
        if javascript:
            expect(dialog.locator('h2')).to_be_focused()
        during = page.evaluate(geometry)
        page.screenshot(path=str(tmp_path / 'checks-dialog.png'))
        close = dialog.locator('[data-read-detail-close]')
        mode = close.evaluate(VISIBILITY)
        assert mode['text'] and mode['icons'] == 0, mode
        close.click()
        expect(dialog).to_be_hidden()
        expect(trigger).to_be_focused()
        expect(trigger).to_be_in_viewport()
        after = page.evaluate(geometry)
        if not javascript:
            assert not dialog.evaluate('el => el.matches(":target")')
            if trigger.evaluate('el => el.getBoundingClientRect().top + scrollY > innerHeight'):
                assert after['scroll'] > 0
        (tmp_path / 'geometry.json').write_text(json.dumps({
            'revision': source_revision(), 'viewport': [width, height],
            'javascript': javascript, 'before': before, 'during': during, 'after': after,
        }, indent=2))
        for selector in ('a[href^="#week-slot-"]', 'a[href^="#service-"]', '#course-issues a'):
            trigger.click()
            link = dialog.locator(selector).last
            target = page.locator(link.get_attribute('href'))
            link.click()
            expect(dialog).to_be_hidden()
            expect(target).to_be_in_viewport()
            if javascript:
                expect(target).to_be_focused()
        expect(page.locator('main')).to_have_attribute('data-status', 'review_open')
        expect(page.locator('#week-publish-form [type="submit"]')).to_be_disabled()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        for phase, actual in (('during', during), ('after', after)):
            # No-JS close returns to its anchor (orchestrator decision 19:55).
            anchor_return = not javascript and phase == 'after'
            if not anchor_return:
                assert abs(actual['scroll'] - before['scroll']) <= 1
            scroll_adjustment = actual['scroll'] - before['scroll'] if anchor_return else 0
            for expected, found in zip(before['boxes'], actual['boxes'], strict=True):
                assert all(
                    abs(found[key] + (scroll_adjustment if key == 'y' else 0) - expected[key]) <= 1
                    for key in expected
                ), (expected, found)
