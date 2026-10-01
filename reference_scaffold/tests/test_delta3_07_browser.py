"""DELTA-3-07: one empty-day target and static native event fields."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import live_server, page_context
from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_delta_renderer_browser import VISIBILITY, source_revision
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']


@pytest.mark.parametrize('width,height,touch', [(1440, 900, False), (1440, 900, True), (390, 844, False), (390, 844, True)])
@pytest.mark.parametrize('javascript', [True, False])
def test_calendar_day_and_static_event_form(
    browser, live_server, page_context, tmp_path, width, height, touch, javascript,
):
    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=touch, java_script_enabled=javascript, reduced_motion='reduce',
        storage_state=page_context.context.storage_state(),
    ) as context:
        calendar = context.new_page()
        assert calendar.goto('/admin/kuechenkalender?year=2026&month=9&profiles=both').status == 200
        calendar.screenshot(path=str(tmp_path / f'calendar-{width}-{touch}-js{javascript}.png'))
        page = context.new_page()
        assert page.goto('/admin/kuechenkalender/anlass?date=2026-09-01').status == 200
        page.screenshot(path=str(tmp_path / f'event-{width}-{touch}-js{javascript}.png'))
        expect(calendar.locator('.kitchen-cal-plan')).to_have_count(0)
        days = calendar.locator('.kitchen-cal-day:visible' if width == 1440 else '.kitchen-cal-list-day:visible')
        assert days.count() > 0
        for day in days.all():
            expect(day.locator('a')).to_have_count(1)
        target = days.first.locator('a')
        target.focus()
        expect(target).to_be_focused()
        assert '/admin/cafeteria?week=' in target.get_attribute('href')
        form = page.locator('#kitchen-event-form')
        expect(form.locator('details, summary')).to_have_count(0)
        for name in ('starts_at', 'ends_at', 'note'):
            expect(form.locator(f'[name="{name}"]')).to_be_visible()
        form.locator('[name="title"]').fill('Anlass mit null Gästen')
        form.locator('[name="guest_count"]').fill('0')
        form.locator('[name="starts_at"]').fill('11:30')
        form.locator('[name="ends_at"]').fill('13:00')
        form.locator('[name="note"]').fill('Optionale Notiz bleibt')
        expected = form.evaluate('el => Object.fromEntries(new FormData(el))')
        assert set(expected) == {'_csrf', 'event_date', 'profile_scope', 'title', 'guest_count', 'starts_at', 'ends_at', 'note'}
        save = form.locator('[data-semantic="actions.save"]')
        mode = save.evaluate(VISIBILITY)
        assert mode['icons'] == 1 and not mode['text'], mode
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            save.click()
        assert saved.value.status == 303
        assert parse_qs(saved.value.request.post_data, keep_blank_values=True) == {k: [v] for k, v in expected.items()}
        page.wait_for_load_state()
        expect(page.locator('.kitchen-cal-event:visible').first).to_have_text('Anlass mit null Gästen')
        page.locator('.kitchen-cal-event:visible').first.click()
        expect(page.locator('[name="guest_count"]')).to_have_value('0')
        expect(page.locator('[name="note"]')).to_have_value('Optionale Notiz bleibt')
        assert page.locator('[name="row_version"]').input_value()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


@pytest.mark.parametrize('width,height,touch', [(1440, 900, False), (1440, 900, True), (390, 844, False), (390, 844, True)])
@pytest.mark.parametrize('javascript', [True, False])
def test_full_day_dialog_contains_all_entries(
    browser, live_server, page_context, admin_engine, tmp_path, width, height, touch, javascript,
):
    _save_reviewed(admin_engine, 'staff_guest', _staff_values())
    _save_reviewed(admin_engine, 'patient', _patient_values())
    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=touch, java_script_enabled=javascript, reduced_motion='reduce',
        storage_state=page_context.context.storage_state(),
    ) as context:
        page = context.new_page()
        assert page.goto('/admin/kuechenkalender/anlass?date=2026-09-02').status == 200
        page.locator('[name="title"]').fill('Anlass im vollständigen Tageskontext')
        with page.expect_response(lambda response: response.request.method == 'POST') as created:
            page.locator('#kitchen-event-form [data-semantic="actions.save"]').click()
        assert created.value.status == 303
        assert page.goto('/admin/kuechenkalender?year=2026&month=9&profiles=both').status == 200
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(tmp_path / 'calendar.png'))
        expect(page.locator('main details')).to_have_count(0)
        variant = 'grid' if width == 1440 else 'list'
        dialog = page.locator(f'#calendar-day-{variant}-2026-09-02')
        trigger = page.locator(f'[data-read-detail="calendar-day-{variant}-2026-09-02"]')
        expect(trigger).to_have_accessible_name('Einträge am 02.09.2026 anzeigen')
        mode = trigger.evaluate(VISIBILITY)
        assert mode['icons'] == 1 and not mode['text'], mode
        assert page.evaluate('''() => {
            const ids=[...document.querySelectorAll('[id]')].map(el=>el.id);
            return new Set(ids).size === ids.length;
        }''')
        geometry = '''() => ({scroll: scrollY, boxes:
            [...document.querySelectorAll('.page-wrapper, .kitchen-cal-toolbar, .kitchen-cal-day, .kitchen-cal-list-day')]
            .filter(el=>el.getClientRects().length).map(el=>{
                const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height};
            })})'''
        trigger.scroll_into_view_if_needed()
        trigger.focus()
        before = page.evaluate(geometry)
        trigger.press('Enter')
        expect(dialog).to_be_visible()
        expect(dialog.locator('.kitchen-cal-dish')).to_have_count(6)
        expect(dialog.locator('.kitchen-cal-area')).to_have_count(2)
        expect(dialog.locator('.kitchen-cal-event')).to_have_text('Anlass im vollständigen Tageskontext')
        expect(dialog.locator('form, details, summary')).to_have_count(0)
        expect(dialog.locator('[data-read-detail-close]')).to_have_count(1)
        if javascript:
            expect(dialog.locator('h2')).to_be_focused()
        during = page.evaluate(geometry)
        page.screenshot(path=str(tmp_path / 'day-dialog.png'))
        dialog.locator('[data-read-detail-close]').click()
        expect(dialog).to_be_hidden()
        expect(trigger).to_be_focused()
        after = page.evaluate(geometry)
        (tmp_path / 'geometry.json').write_text(json.dumps({
            'revision': source_revision(), 'javascript': javascript,
            'before': before, 'during': during, 'after': after,
        }, indent=2))
        trigger.click()
        entry = dialog.locator('.kitchen-cal-dish').nth(3)
        assert parse_qs(urlsplit(entry.evaluate('(a) => a.href')).query) == {
            'week': ['2026-08-31'], 'day': ['2026-09-02'], 'meal': ['LUNCH'], 'option': ['VEGGIE'],
        }
        with page.expect_navigation() as followed:
            entry.click()
        assert followed.value.status == 200
        expect(page.locator('form[data-menu-editor]')).to_be_visible()
        for actual in (during, after):
            assert abs(actual['scroll'] - before['scroll']) <= 1
            for expected, found in zip(before['boxes'], actual['boxes'], strict=True):
                assert all(abs(found[key] - expected[key]) <= 1 for key in expected), (expected, found)
