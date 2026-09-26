from __future__ import annotations

import re
import json
from datetime import timedelta

import pytest
from playwright.sync_api import expect, sync_playwright

from cafeteria.workflow_partial_store import persist_week_header
from cafeteria.ui import register_ui
from test_admin_workflow_routes import WEEK, _login, _scope

from test_admin_ux_browser import (
    admin_app as admin_app, admin_engine as admin_engine,
    live_server as live_server, page_context as page_context,
)


@pytest.fixture(autouse=True)
def semantic_ui(admin_app):
    register_ui(admin_app)


@pytest.fixture
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        try:
            yield instance
        finally:
            instance.close()


def test_week_creation_and_tablet_layout(page_context):
    page = page_context
    page.goto('/admin/patienten')
    page.locator('#sidebar-menu').get_by_role('link', name='Wochenübersicht', exact=True).click()
    expect(page.get_by_role('heading', name='Wochenübersicht', exact=True)).to_be_visible()
    for width, height in [(768, 1024), (800, 1280), (1024, 768), (1280, 800), (390, 844)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.reload()
        toggle = page.locator('[data-bs-target="#sidebar-menu"]')
        if width < 992:
            expect(toggle).to_be_visible()
            toggle.click()
            expect(page.locator('#sidebar-menu')).to_have_class(re.compile(r'\bshow\b'))
            expect(page.get_by_role('navigation', name='Backend')).to_be_visible()
            page.evaluate("""() => {
              const menu = document.getElementById('sidebar-menu');
              const offcanvas = window.tabler?.Offcanvas?.getInstance(menu);
              if (offcanvas) offcanvas.hide();
            }""")
            expect(page.get_by_role('navigation', name='Backend')).to_be_hidden()
        assert not page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
        expect(page.locator('#new-week-date')).to_be_hidden()
        create = page.get_by_role('link', name='Neue Woche anlegen', exact=True)
        expect(create).to_have_text('')
        # Before enhancement this is also a valid no-JS link to the visible form.
        assert create.get_attribute('aria-expanded') is None
        create.focus()
        page.keyboard.press('Enter')
        expect(page.locator('#new-week-date')).to_be_visible()
        expect(create).to_have_attribute('aria-expanded', 'true')
        for selector in ['input[type="date"]', 'input[name="title"]', 'textarea', 'button[type="submit"]']:
            for control in page.locator(selector).all():
                if control.is_visible():
                    minimum = control.evaluate("e => e.matches('.ui-sem-control') ? (matchMedia('(pointer: coarse)').matches ? 44 : 36) : 48")
                    assert control.bounding_box()['height'] >= minimum
    expect(page.locator('#new-week-date')).to_be_visible()
    page.get_by_label('Wochenbeginn (Montag)').fill('2027-01-04')
    page.get_by_label('Wochentitel', exact=True).fill('Tabletwoche')
    page.get_by_role('button', name='Anlegen', exact=True).click()
    assert '/admin/patienten?week=2027-01-04' in page.url
    page.goto('/admin/patienten/wochen')
    expect(page.get_by_text('Tabletwoche', exact=True)).to_be_visible()


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [True, False])
def test_empty_week_creation_and_error_retention(admin_app, admin_engine, live_server, browser, family, profile, javascript):
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _scope(admin_engine, actor, profile)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = browser.new_context(base_url=live_server, java_script_enabled=javascript)
    try:
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        page.goto(f'/admin/{family}/wochen')
        empty_create = page.locator('[data-empty-kind="none"]').get_by_role('link', name='Anlegen', exact=True)
        expect(empty_create).to_have_text('')
        empty_create.click()
        expect(page.locator('#new-week-date')).to_be_visible()
        if javascript:
            expect(empty_create).to_have_attribute('aria-expanded', 'true')
        page.get_by_label('Wochenbeginn (Montag)').fill('2026-09-01')
        page.get_by_label('Wochentitel', exact=True).fill('Eingabe behalten')
        with page.expect_response(lambda r: r.request.method == 'POST') as posted:
            page.get_by_role('button', name='Anlegen', exact=True).click()
        assert posted.value.status == 400
        expect(page.locator('#new-week-error')).to_be_visible()
        expect(page.locator('#new-week-date')).to_be_visible()
        expect(page.locator('#new-week-date')).to_have_value('2026-09-01')
        expect(page.locator('#new-week-name')).to_have_value('Eingabe behalten')
    finally:
        context.close()


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [True, False])
def test_management_density_keyboard_and_native_actions(
    admin_app, admin_engine, live_server, tmp_path, family, profile, javascript,
):
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, actor, profile)
    for offset in range(4):
        persist_week_header(admin_engine, scope, WEEK + timedelta(weeks=offset),
                            {'title': f'Herbstwoche {offset + 1}', 'shared_note': ''}, 0)
    cookie = client.get_cookie('session')
    assert cookie is not None
    metrics = []
    with sync_playwright() as playwright:
        browser_instance = playwright.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        context = browser_instance.new_context(base_url=live_server, java_script_enabled=javascript)
        try:
            context.add_cookies([{'name': 'session', 'value': cookie.value,
                                 'domain': '127.0.0.1', 'path': '/', 'httpOnly': True}])
            page = context.new_page()
            page.emulate_media(reduced_motion='reduce')
            for width, height in [(360, 844), (768, 1024), (1024, 768), (1440, 900)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.goto(f'/admin/{family}/wochen')
                page.evaluate('document.fonts.ready')
                rows = page.locator('tr[data-week-id]')
                expect(rows).to_have_count(4)
                measurement = page.evaluate('''() => ({
                    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                    rowHeights: [...document.querySelectorAll('tr[data-week-id]')]
                        .map(e => e.getBoundingClientRect().height),
                    primaryCount: document.querySelectorAll('main .btn-primary').length,
                    tableWidth: document.querySelector('table').getBoundingClientRect().width,
                    firstRowY: document.querySelector('tr[data-week-id]').getBoundingClientRect().y,
                })''')
                metrics.append(measurement)
                (tmp_path / 'metrics.json').write_text(json.dumps(metrics), encoding='utf-8')
                page.screenshot(path=str(tmp_path / f'{family}-{javascript}-{width}.png'), full_page=True)
                assert measurement['scrollWidth'] <= width
                assert measurement['primaryCount'] == 1
                if width == 1440:
                    assert max(measurement['rowHeights']) <= 64, measurement
                summary = page.locator('.page-header-subtitle')
                expect(summary).to_be_visible()
                expect(summary).to_have_text('4 gespeicherte Wochen')
                expect(summary).not_to_contain_text('zu prüfen')
                expect(page.locator('dl.admin-statusbar')).to_have_count(0)
                expect(page.locator('.week-filter .active')).to_have_attribute('aria-current', 'true')
                expect(page.locator('.week-filter .active')).to_have_attribute('href', f'/admin/{family}/wochen')
                first = rows.first
                week_link = first.get_by_role('link', name='21.09.2026 – 27.09.2026', exact=True)
                expect(week_link).to_be_visible()
                expect(week_link).to_have_attribute('href', f'/admin/{family}?week={WEEK + timedelta(weeks=3)}')
                preview = first.get_by_role('link', name='Vorschau für Woche ab 21.09.2026', exact=True)
                expect(preview).to_be_visible()
                expect(preview).to_have_text('')
                expect(preview.locator('use')).to_have_attribute('href', re.compile(r'#tabler-eye$'))
                expect(first.locator('.admin-table-status .admin-label')).to_have_class(re.compile(r'admin-status--neutral'))
                expect(page.locator('.week-filter')).to_have_class(re.compile(r'admin-filter-bar'))
                copy = first.get_by_role('link', name='Woche ab 21.09.2026 kopieren', exact=True)
                expect(copy).to_be_hidden()
                more = first.locator('summary')
                more.focus()
                page.keyboard.press('Shift+Tab')
                page.keyboard.press('Tab')
                expect(more).to_be_focused()
                assert more.evaluate('e => getComputedStyle(e).outlineStyle') == 'solid'
                assert more.evaluate('e => parseFloat(getComputedStyle(e).outlineWidth)') >= 2
                page.keyboard.press('Enter')
                expect(copy).to_be_visible()
                preview = first.locator('a[href*="/preview?"]')
                expect(preview).to_be_visible()
                # The shared menu focuses its first action with JS; native details need Tab.
                if not javascript:
                    page.keyboard.press('Tab')
                expect(copy).to_be_focused()
                bad_targets = page.locator('main :is(.btn, summary):visible').evaluate_all('''es => es.flatMap(e => {
                    const r = e.getBoundingClientRect();
                    const min = e.matches('.ui-sem-control') ? (matchMedia('(pointer: coarse)').matches ? 44 : 36) : 48;
                    return r.height >= min && r.width >= min && r.left >= 0 && r.right <= innerWidth
                        ? [] : [{text: e.textContent, width: r.width, height: r.height, right: r.right}];
                })''')
                assert not bad_targets, bad_targets
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                expect(page.locator('main .btn-primary')).to_have_count(1)
                expect(page.locator('main .btn-primary')).to_be_visible()
                if not javascript:
                    expect(page.locator('#new-week-date')).to_be_visible()
                    expect(page.locator('#new-week-title')).to_have_attribute('href', '#new-week-date')
                    assert page.locator('#new-week-title').get_attribute('aria-expanded') is None
                if width < 768:
                    stacked = page.evaluate('''() => {
                        const table = document.querySelector('.week-table.admin-table--stack');
                        return Boolean(table) && getComputedStyle(table.querySelector('tbody')).display === 'block';
                    }''')
                    assert stacked, (family, javascript, width)
                # Redundant instruction is gone; the real actions retain keyboard access.
                preview.focus()
                expect(preview).to_be_focused()
                preview.click()
                assert '/preview?week=' in page.url
                page.goto(f'/admin/{family}/wochen')
                rows.first.locator('summary').click()
                rows.first.get_by_role('link', name='Woche ab 21.09.2026 kopieren', exact=True).click()
                expect(page.locator('main')).to_have_attribute('data-source-week', str(WEEK + timedelta(weeks=3)))
                expect(page.locator('main')).to_have_attribute('data-target-week', str(WEEK + timedelta(weeks=4)))
                page.goto(f'/admin/{family}/wochen')
                rows.first.get_by_role('link', name='21.09.2026 – 27.09.2026', exact=True).click()
                assert page.url.endswith(f'/admin/{family}?week={WEEK + timedelta(weeks=3)}')
            (tmp_path / 'metrics.json').write_text(json.dumps(metrics), encoding='utf-8')
            print(f'WP24_METRICS {family} js={javascript} {tmp_path}: {json.dumps(metrics)}')
        finally:
            context.close()
            browser_instance.close()
