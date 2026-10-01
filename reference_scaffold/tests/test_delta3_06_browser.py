"""DELTA-3-06: stable navigation, static creation and text-only confirmation."""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import live_server, page_context
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, WEEK
from test_delta_renderer_browser import VISIBILITY
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width,height,touch', [(1440, 900, False), (1440, 900, True), (390, 844, False), (390, 844, True)])
def test_static_creation_preview_and_copy(
    browser, live_server, page_context, admin_engine, tmp_path, family, profile,
    width, height, touch,
):
    _save(admin_engine, profile, _staff_values() if family == 'cafeteria' else _patient_values())
    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=touch, reduced_motion='reduce',
        storage_state=page_context.context.storage_state(),
    ) as context:
        pages = {}
        for name, route in {
            'management': f'/admin/{family}/wochen',
            'review': f'/admin/{family}/wochen/pruefung?week={DAY}',
            'preview': f'/admin/{family}/preview?week={DAY}',
            'copy': f'/admin/{family}/copy?week={WEEK + timedelta(days=7)}',
        }.items():
            page = context.new_page()
            assert page.goto(route).status == 200
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(tmp_path / f'{name}-{family}-{width}-{touch}.png'))
            pages[name] = page
        page = pages['management']
        form = page.locator('#new-week-form form')
        expect(form.locator('details, summary')).to_have_count(0)
        expect(form.locator('[name="shared_note"]')).to_be_visible()
        expect(page.locator('[data-bs-target="#new-week-form"]')).to_have_count(0)
        expect(page.locator('a[href="#new-week-date"]')).to_have_count(1)
        nav = page.locator('.week-filter')
        assert nav.bounding_box()['y'] < form.bounding_box()['y']
        expect(page.locator('.week-list-summary')).to_be_visible()
        assert nav.bounding_box()['y'] < page.locator('.week-list-summary').bounding_box()['y']
        page.locator('#new-week-date').fill('2026-09-01')
        page.locator('#new-week-name').fill('Eingabe bleibt')
        page.locator('#new-week-note').fill('Optionaler Hinweis bleibt')
        expected = form.evaluate('el => Object.fromEntries(new FormData(el))')
        with page.expect_response(lambda response: response.request.method == 'POST') as failed:
            form.locator('button[type="submit"]').click()
        assert failed.value.status == 400
        assert parse_qs(failed.value.request.post_data, keep_blank_values=True) == {k: [v] for k, v in expected.items()}
        expect(page.locator('#new-week-error')).to_be_visible()
        expect(page.locator('#new-week-note')).to_have_value('Optionaler Hinweis bleibt')
        preview = pages['preview']
        assert preview.locator('.preview-profiles').bounding_box()['y'] < preview.locator('.admin-statusbar').bounding_box()['y']
        mode = preview.locator('[data-semantic="actions.back"]').evaluate(VISIBILITY)
        assert mode['icons'] == 1 and not mode['text'], mode
        copy = pages['copy']
        for action in copy.locator('main [data-semantic]:is(a,button)').all():
            mode = action.evaluate(VISIBILITY)
            assert mode['text'] and mode['icons'] == 0, mode
        for page in pages.values():
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_review_and_preview_partial_times(page_context, admin_engine, family, profile):
    values = _staff_values() if family == 'cafeteria' else _patient_values()
    for day, (start, end) in zip(values['days'], [('', ''), ('11:30', ''), ('', '13:00'), ('11:30', '13:00')]):
        day['services'][0].update(service_start=start, service_end=end)
    _save(admin_engine, profile, values)
    page = page_context
    assert page.goto(f'/admin/{family}/preview?week={DAY}').status == 200
    for index, expected in enumerate(['', 'ab 11:30', 'bis 13:00', '11:30–13:00']):
        times = page.locator('.preview-day').nth(index).locator('.preview-service').first.locator('.service-time')
        if expected:
            expect(times).to_have_text(expected)
        else:
            expect(times).to_have_count(0)
    assert page.goto(f'/admin/{family}/wochen/pruefung?week={DAY}').status == 200
    rows = page.locator('[aria-label="Ausgabeangaben"] [role="listitem"]')
    stride = 1 if family == 'cafeteria' else 2
    for index, expected in enumerate(['', 'ab 11:30', 'bis 13:00', '11:30–13:00']):
        row = rows.nth(index * stride)
        expect(row.locator('.admin-list-status, .admin-list-secondary')).to_have_count(0)
        meta = row.locator('.admin-list-meta')
        if expected:
            expect(meta).to_have_text(expected)
        else:
            expect(meta).to_have_count(0)
