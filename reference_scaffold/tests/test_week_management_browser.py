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
        page.locator('#new-week-title').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#new-week-date')).to_be_visible()
        for selector in ['input[type="date"]', 'input[name="title"]', 'textarea', 'button[type="submit"]']:
            for control in page.locator(selector).all():
                if control.is_visible():
                    assert control.bounding_box()['height'] >= 48
    expect(page.locator('#new-week-date')).to_be_visible()
    page.get_by_label('Wochenbeginn (Montag)').fill('2027-01-04')
    page.get_by_label('Wochentitel', exact=True).fill('Tabletwoche')
    page.get_by_role('button', name='Woche anlegen').click()
    assert '/admin/patienten?week=2027-01-04' in page.url
    page.goto('/admin/patienten/wochen')
    expect(page.get_by_text('Tabletwoche', exact=True)).to_be_visible()


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
                statusbar = page.locator('dl.admin-statusbar')
                expect(statusbar).to_be_visible()
                expect(statusbar.locator('.admin-statusbar-item').filter(
                    has=page.get_by_text('Gespeicherte Wochen', exact=True)
                ).locator('dd')).to_have_text('4')
                expect(statusbar.locator('.admin-statusbar-item').filter(
                    has=page.get_by_text('Noch zu prüfen', exact=True)
                ).locator('dd')).to_have_text('0')
                expect(page.locator('.week-filter .active')).to_have_attribute('aria-current', 'true')
                expect(page.locator('.week-filter .active')).to_have_attribute('href', f'/admin/{family}/wochen')
                first = rows.first
                expect(first.get_by_role('link', name='Öffnen', exact=True)).to_be_visible()
                expect(first.get_by_role('link', name='Kopieren vorbereiten', exact=True)).to_be_hidden()
                more = first.locator('summary')
                more.focus()
                page.keyboard.press('Shift+Tab')
                page.keyboard.press('Tab')
                expect(more).to_be_focused()
                assert more.evaluate('e => getComputedStyle(e).outlineStyle') == 'solid'
                assert more.evaluate('e => parseFloat(getComputedStyle(e).outlineWidth)') >= 2
                page.keyboard.press('Enter')
                expect(first.get_by_role('link', name='Kopieren vorbereiten', exact=True)).to_be_visible()
                preview = first.locator('a[href*="/preview?"]')
                expect(preview).to_be_visible()
                page.keyboard.press('Tab')
                expect(preview).to_be_focused()
                bad_targets = page.locator('main :is(.btn, summary):visible').evaluate_all('''es => es.flatMap(e => {
                    const r = e.getBoundingClientRect();
                    return r.height >= 48 && r.width >= 48 && r.left >= 0 && r.right <= innerWidth
                        ? [] : [{text: e.textContent, width: r.width, height: r.height, right: r.right}];
                })''')
                assert not bad_targets, bad_targets
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                expect(page.locator('main .btn-primary')).to_have_count(1)
                expect(page.locator('main .btn-primary')).to_be_visible()
                if width < 768:
                    stacked = page.evaluate('''() => {
                        const table = document.querySelector('.week-table.admin-table--stack');
                        return Boolean(table) && getComputedStyle(table.querySelector('tbody')).display === 'block';
                    }''')
                    assert stacked, (family, javascript, width)
                hint = page.locator('details.admin-hint').first
                summary = hint.locator('summary')
                expect(summary).to_be_visible()
                summary.focus()
                expect(summary).to_be_focused()
                if hint.get_attribute('open') is None:
                    page.keyboard.press('Enter')
                expect(hint).to_have_attribute('open', '')
                page.keyboard.press('Enter')
                preview.click()
                assert '/preview?week=' in page.url
                page.goto(f'/admin/{family}/wochen')
                rows.first.locator('summary').click()
                rows.first.get_by_role('link', name='Kopieren vorbereiten', exact=True).click()
                expect(page.locator('main')).to_have_attribute('data-source-week', str(WEEK + timedelta(weeks=3)))
                expect(page.locator('main')).to_have_attribute('data-target-week', str(WEEK + timedelta(weeks=4)))
                page.goto(f'/admin/{family}/wochen')
                rows.first.get_by_role('link', name='Öffnen', exact=True).click()
                assert page.url.endswith(f'/admin/{family}?week={WEEK + timedelta(weeks=3)}')
            (tmp_path / 'metrics.json').write_text(json.dumps(metrics), encoding='utf-8')
            print(f'WP24_METRICS {family} js={javascript} {tmp_path}: {json.dumps(metrics)}')
        finally:
            context.close()
            browser_instance.close()
