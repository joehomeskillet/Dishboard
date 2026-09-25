"""Kitchen calendar compact month browser checks."""
from __future__ import annotations

import re
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit
from wsgiref.simple_server import make_server

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values  # noqa: E402
from test_admin_workflow_routes import DATABASE_URL, _login  # noqa: E402
from test_rendered_ui import admin_app, admin_engine  # noqa: E402,F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

CALENDAR_URL = '/admin/kuechenkalender?jump=2026-09'
FULL_DAY = 2
EMPTY_DAY = 7
EXPECTED_DISHES_FULL_DAY = 6
MOBILE_DOC_HEIGHT_BEFORE = 4812
VIEWPORTS = ((360, 800), (768, 1024), (1024, 900), (1440, 900))


@pytest.fixture(scope='module')
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser_instance = playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        try:
            yield browser_instance
        finally:
            browser_instance.close()


@pytest.fixture
def live_server(admin_app: Flask) -> str:  # noqa: F811
    server = make_server('127.0.0.1', 0, admin_app)
    host, port = server.server_address
    url = f'http://{host}:{port}'
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield url
    server.shutdown()
    server.server_close()
    thread.join(timeout=1)


def _seed_calendar_month(application: Flask) -> None:
    engine = application.extensions['cafeteria_db']
    _save_reviewed(engine, 'staff_guest', _staff_values())
    _save_reviewed(engine, 'patient', _patient_values())


def _session_cookies(client) -> list[dict[str, str]]:
    cookie = client.get_cookie('session')
    if not cookie:
        return []
    return [{
        'name': 'session',
        'value': cookie.value,
        'domain': '127.0.0.1',
        'path': '/',
        'httpOnly': True,
    }]


def _open_calendar(
    browser: Browser,
    live_server: str,
    application: Flask,
    engine,
    *,
    width: int,
    height: int,
    javascript: bool = True,
) -> tuple[Page, object]:
    _seed_calendar_month(application)
    client, _ = _login(application, engine, ['Cafeteria.Admin'])
    context = browser.new_context(
        base_url=live_server,
        viewport={'width': width, 'height': height},
        java_script_enabled=javascript,
    )
    cookies = _session_cookies(client)
    if cookies:
        context.add_cookies(cookies)
    page = context.new_page()
    page.emulate_media(reduced_motion='reduce')
    response = page.goto(CALENDAR_URL)
    assert response is not None and response.status == 200
    page.evaluate('document.fonts.ready')
    return page, context


def _full_day_cell(page: Page):
    return page.locator('.kitchen-cal-grid td.kitchen-cal-day:not(.kitchen-cal-day-muted)').filter(
        has=page.locator('.kitchen-cal-day-num', has_text=str(FULL_DAY)),
    ).first


def _empty_day_cell(page: Page):
    return page.locator('.kitchen-cal-grid td.kitchen-cal-day:not(.kitchen-cal-day-muted)').filter(
        has=page.locator('.kitchen-cal-day-num', has_text=str(EMPTY_DAY)),
    ).first


def _empty_week_row(page: Page):
    return page.locator('.kitchen-cal-table tbody tr').filter(
        has=page.locator('.kitchen-cal-day-num', has_text=str(EMPTY_DAY)),
    ).first


def _empty_list_day(page: Page):
    return page.locator('.kitchen-cal-list-day').filter(
        has=page.locator('.kitchen-cal-list-head a', has_text=re.compile(rf'{EMPTY_DAY}\. September')),
    ).first


def _boxes_overlap(left: dict[str, float], right: dict[str, float]) -> bool:
    left_right = left['x'] + left['width']
    left_bottom = left['y'] + left['height']
    right_right = right['x'] + right['width']
    right_bottom = right['y'] + right['height']
    return not (
        left_right <= right['x']
        or right_right <= left['x']
        or left_bottom <= right['y']
        or right_bottom <= left['y']
    )


def _dish_counts(cell) -> dict[str, int]:
    return cell.evaluate('''(element) => {
        const dishes = [...element.querySelectorAll('.kitchen-cal-dish')];
        const visible = dishes.filter((node) => !node.closest('details')).length;
        const overflow = dishes.filter((node) => node.closest('details')).length;
        return { visible, overflow, total: dishes.length };
    }''')


def test_compact_full_day_cell_and_week_rows(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine, tmp_path: Path,  # noqa: F811
) -> None:
    page, context = _open_calendar(browser, live_server, admin_app, admin_engine, width=1440, height=900)
    try:
        cell = _full_day_cell(page)
        box = cell.bounding_box()
        assert box is not None, 'fully planned day cell missing'
        assert box['height'] <= 220, f'cell height {box["height"]:.1f}px exceeds 220px'

        metrics = page.evaluate('''() => {
            const rows = [...document.querySelectorAll('.kitchen-cal-table tbody tr')];
            const tops = rows.map((row) => row.getBoundingClientRect().top);
            const within = tops.filter((top) => top < 900).length;
            return { rowCount: rows.length, within900: within, tops };
        }''')
        assert metrics['within900'] >= 4, metrics

        counts = _dish_counts(cell)
        assert counts['visible'] <= 3, counts
        assert counts['total'] == EXPECTED_DISHES_FULL_DAY, counts
        assert counts['visible'] + counts['overflow'] == EXPECTED_DISHES_FULL_DAY, counts

        empty_row = _empty_week_row(page)
        row_box = empty_row.bounding_box()
        assert row_box is not None, 'empty week row missing'
        assert row_box['height'] <= 72, f'empty week row height {row_box["height"]:.1f}px exceeds 72px'

        empty_cell = _empty_day_cell(page)
        head = empty_cell.locator('.kitchen-cal-day-head')
        plan = empty_cell.locator('.kitchen-cal-plan')
        assert plan.count() == 1
        head_box = head.bounding_box()
        plan_box = plan.bounding_box()
        assert head_box is not None and plan_box is not None
        assert not _boxes_overlap(head_box, plan_box), {
            'head': head_box,
            'plan': plan_box,
        }
        head.focus()
        page.keyboard.press('Tab')
        assert plan.evaluate('element => element === document.activeElement') is True

        page.screenshot(path=str(tmp_path / 'kitchen-calendar-1440x900.png'), full_page=True)
    finally:
        context.close()


def test_overflow_details_keyboard_accessible(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine,  # noqa: F811
) -> None:
    page, context = _open_calendar(browser, live_server, admin_app, admin_engine, width=1440, height=900)
    try:
        cell = _full_day_cell(page)
        details = cell.locator('details.kitchen-cal-more')
        assert details.count() == 1
        summary = details.locator('summary')
        summary.focus()
        page.keyboard.press('Enter')
        assert details.evaluate('element => element.open') is True
        overflow_link = details.locator('.kitchen-cal-dish').first
        overflow_link.focus()
        assert overflow_link.evaluate('element => element === document.activeElement') is True
    finally:
        context.close()


@pytest.mark.parametrize(('width', 'height'), VIEWPORTS)
def test_calendar_has_no_horizontal_overflow(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine, width: int, height: int, tmp_path: Path,  # noqa: F811
) -> None:
    page, context = _open_calendar(browser, live_server, admin_app, admin_engine, width=width, height=height)
    try:
        overflow = page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        assert overflow, page.evaluate('''() => ({
            scrollWidth: document.documentElement.scrollWidth,
            innerWidth: window.innerWidth,
        })''')
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('main .btn-primary')).to_be_visible()
        hint = page.locator('details.admin-hint').first
        summary = hint.locator('summary')
        expect(summary).to_be_visible()
        summary.focus()
        expect(summary).to_be_focused()
        if hint.get_attribute('open') is None:
            page.keyboard.press('Enter')
        expect(hint).to_have_attribute('open', '')
        page.keyboard.press('Enter')
        if width == 360:
            list_visible = page.evaluate('''() => {
                const list = document.querySelector('.kitchen-cal-list');
                const grid = document.querySelector('.kitchen-cal-grid');
                return Boolean(list) && getComputedStyle(list).display !== 'none'
                    && Boolean(grid) && getComputedStyle(grid).display === 'none';
            }''')
            assert list_visible
            empty_day = _empty_list_day(page)
            day_box = empty_day.bounding_box()
            assert day_box is not None, 'empty mobile list day missing'
            assert day_box['height'] <= 64, f'empty mobile day height {day_box["height"]:.1f}px exceeds 64px'

            doc_height = page.evaluate('document.documentElement.scrollHeight')
            max_height = MOBILE_DOC_HEIGHT_BEFORE * 0.65
            assert doc_height <= max_height, (
                f'mobile document height {doc_height}px not at least 35% smaller than '
                f'{MOBILE_DOC_HEIGHT_BEFORE}px (max {max_height:.0f}px)'
            )

            # Locator-Nachzug: .kitchen-cal-list-head > a → .kitchen-cal-list-head h2 > a.
            # Grund: h2 bleibt Zeilentitel mit Rolle Primär; Planen steht daneben.
            head = empty_day.locator('.kitchen-cal-list-head h2 > a').first
            plan = empty_day.locator('.kitchen-cal-plan')
            assert plan.count() == 1
            head_box = head.bounding_box()
            plan_box = plan.bounding_box()
            assert head_box is not None and plan_box is not None
            assert not _boxes_overlap(head_box, plan_box), {
                'head': head_box,
                'plan': plan_box,
            }
            head.focus()
            page.keyboard.press('Tab')
            assert plan.evaluate('element => element === document.activeElement') is True

            page.screenshot(path=str(tmp_path / 'kitchen-calendar-360x800.png'), full_page=True)
    finally:
        context.close()


def test_single_primary_and_active_filter(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine,  # noqa: F811
) -> None:
    page, context = _open_calendar(browser, live_server, admin_app, admin_engine, width=1440, height=900)
    try:
        assert page.locator('main .btn-primary').count() == 1
        active = page.locator('.kitchen-cal-filters .btn.active[aria-current="true"]')
        assert active.count() == 1
        assert 'Beide' in (active.inner_text() or '')
    finally:
        context.close()


def test_no_js_navigation_filter_and_details(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine,  # noqa: F811
) -> None:
    page, context = _open_calendar(
        browser, live_server, admin_app, admin_engine, width=1440, height=900, javascript=False,
    )
    try:
        cafeteria_link = page.locator('.kitchen-cal-filters a', has_text='Cafeteria')
        href = cafeteria_link.get_attribute('href')
        assert href
        response = page.goto(href)
        assert response is not None and response.status == 200
        assert 'profiles=cafeteria' in (page.url or '')

        page.goto(CALENDAR_URL)
        prev = page.locator('.kitchen-cal-month-nav a[aria-label="Vorheriger Monat"]')
        prev_href = prev.get_attribute('href')
        assert prev_href
        response = page.goto(prev_href)
        assert response is not None and response.status == 200
        assert urlsplit(response.url).path == '/admin/kuechenkalender'

        page.goto(CALENDAR_URL)
        cell = _full_day_cell(page)
        summary = cell.locator('details.kitchen-cal-more > summary')
        summary.focus()
        page.keyboard.press('Space')
        assert cell.locator('details.kitchen-cal-more[open]').count() == 1
    finally:
        context.close()


def test_statusbar_excludes_version_and_day_date(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine,  # noqa: F811
) -> None:
    page, context = _open_calendar(browser, live_server, admin_app, admin_engine, width=1440, height=900)
    try:
        status_text = page.locator('.admin-page-header').inner_text() or ''
        assert 'Version' not in status_text
        assert re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', status_text) is None
        assert 'von' in status_text
    finally:
        context.close()
