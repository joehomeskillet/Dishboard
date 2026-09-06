from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect

from test_rendered_ui import _set_unbroken_signage_boundaries
from test_rendered_ui import app as app
from test_rendered_ui import browser as browser
from test_signage_engine import live_signage as live_signage

FORBIDDEN = re.compile(r'preis|chf|rappen|kosten|price|intern|extern|money|currency', re.I)


def _assert_full_surface(page: Page, menu_selector: str) -> None:
    metrics = page.evaluate(
        """selector => {
          const boxes = [...document.querySelectorAll(selector)];
          const nodes = [...document.querySelectorAll(selector + ', ' + selector + ' *')]
            .filter(node => !['IMG', 'SVG', 'PATH'].includes(node.tagName));
          return {
            viewport: document.documentElement.scrollWidth <= innerWidth + 1
              && document.documentElement.scrollHeight <= innerHeight + 1,
            unequal: boxes.filter(node => {
              const box = node.getBoundingClientRect(), first = boxes[0].getBoundingClientRect();
              return Math.abs(box.width - first.width) > 1 || Math.abs(box.height - first.height) > 1;
            }).length,
            clipped: nodes.filter(node => node.clientWidth && node.clientHeight &&
              (node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1)
            ).map(node => ({tag: node.tagName, class: node.className,
              width: [node.scrollWidth, node.clientWidth], height: [node.scrollHeight, node.clientHeight]})),
          };
        }""", menu_selector,
    )
    assert metrics == {'viewport': True, 'unequal': 0, 'clipped': []}


@pytest.mark.parametrize(('width', 'height'), ((1920, 1080), (3840, 2160)))
@pytest.mark.parametrize('surface', ('tag', 'woche'))
@pytest.mark.parametrize('scenario', ('normal', 'boundary'))
def test_patient_boards_are_complete_and_legible(
    live_signage: tuple[str, Flask], browser: Browser, tmp_path: Path,
    width: int, height: int, surface: str, scenario: str,
) -> None:
    base_url, application = live_signage
    if scenario == 'boundary':
        _set_unbroken_signage_boundaries(
            application.config['TEST_SNAPSHOTS']['patient'],
            title_length=42 if surface == 'tag' else 36,
            component_length=62 if surface == 'tag' else 48,
        )
    page = browser.new_page(viewport={'width': width, 'height': height}, reduced_motion='reduce')
    try:
        if surface == 'woche':
            page.clock.install()
        response = page.goto(f'{base_url}/signage/patienten/{surface}')
        assert response and response.status == 200
        assert "script-src 'self'" in response.headers['content-security-policy']
        page.evaluate('document.fonts.ready')
        page.wait_for_function('[...document.images].every(image => image.complete && image.naturalWidth > 0)')
        assert FORBIDDEN.search(response.text()) is None
        assert FORBIDDEN.search(page.content()) is None
        expect(page.locator('h1')).to_have_count(1)
        expect(page.locator('a,nav,form,button,[style],[onclick],[onload]')).to_have_count(0)
        selector = '.patient-signage-option' if surface == 'tag' else '.patient-week-option'
        expect(page.locator(selector)).to_have_count(4 if surface == 'tag' else 28)
        sizes = page.locator(f'{selector} h3, {selector} p, {selector} small, {selector} span').evaluate_all(
            'nodes => nodes.map(node => parseFloat(getComputedStyle(node).fontSize))',
        )
        assert min(sizes) >= 18
        symbols = page.locator(f'{selector} .food-symbol')
        assert symbols.count() > 0
        for symbol in page.locator(f'{selector} .food-symbol:visible').all():
            expect(symbol).to_be_visible()
            box = symbol.bounding_box()
            assert box and 18 <= box['height'] <= 50
            assert box['height'] <= box['width'] <= box['height'] * 1.5
        if surface == 'tag':
            assert page.locator(f'{selector} h3').first.evaluate(
                'node => parseFloat(getComputedStyle(node).fontSize)',
            ) >= (46 if width == 1920 else 92)
        expect(page.locator('[data-signage-clock]')).not_to_be_empty()
        if surface == 'tag':
            expect(page.locator('.patient-duo > .col-6')).to_have_count(2)
            expect(page.locator('.menu-photo img')).to_have_count(4 if scenario == 'normal' else 0)
            expect(page.locator('[data-menu-image-fallback]')).to_have_count(0 if scenario == 'normal' else 4)
            page.screenshot(path=str(tmp_path / f'patient-{surface}-{scenario}-{width}x{height}.png'))
            _assert_full_surface(page, selector)
        else:
            visible = '[data-signage-page]:not([hidden])'
            widths = []
            # Four pages: Mittag and Abend, each split Monday to Thursday and Friday to Sunday.
            for index, (meal, count) in enumerate(
                (('Mittag', 4), ('Mittag', 3), ('Abend', 4), ('Abend', 3)),
            ):
                if index:
                    page.clock.fast_forward(30100)
                label = page.locator(f'{visible} .patient-board-page-label')
                expect(label).to_contain_text(f'Seite {index + 1} von 4')
                expect(label).to_contain_text(meal)
                columns = page.locator(f'{visible} .patient-week-day')
                expect(columns).to_have_count(count)
                assert len({round(box.bounding_box()['x']) for box in columns.all()}) == count
                widths.append(columns.first.bounding_box()['width'])
                page.screenshot(path=str(tmp_path / f'patient-{surface}-{scenario}-{index + 1}-{width}x{height}.png'))
                _assert_full_surface(page, f'{visible} {selector}')
            assert max(widths) - min(widths) <= 1
    finally:
        page.close()


@pytest.mark.parametrize(('width', 'height'), ((1920, 1080), (3840, 2160)))
@pytest.mark.parametrize('state', ('closed', 'unavailable'))
def test_patient_notice_uses_real_shell(
    live_signage: tuple[str, Flask], browser: Browser, tmp_path: Path,
    width: int, height: int, state: str,
) -> None:
    base_url, application = live_signage
    if state == 'closed':
        meal = application.config['TEST_SNAPSHOTS']['patient']['days'][2]['services'][1]
        meal['service_state'] = 'closed'
        meal['notice'] = 'Heute wird das Abendessen auf der Station serviert.'
        expected = meal['notice']
    else:
        application.config['TEST_SNAPSHOTS']['patient'] = None
        expected = 'Speiseplan nicht verfügbar'
    page = browser.new_page(viewport={'width': width, 'height': height})
    try:
        response = page.goto(f'{base_url}/signage/patienten/tag')
        assert response and response.status == (200 if state == 'closed' else 404)
        page.evaluate('document.fonts.ready')
        assert FORBIDDEN.search(response.text()) is None
        assert FORBIDDEN.search(page.content()) is None
        expect(page.locator('[data-signage-root]')).to_contain_text(expected, use_inner_text=True)
        expect(page.locator('h1')).to_have_count(1)
        expect(page.locator('[data-signage-clock]')).not_to_be_empty()
        page.screenshot(path=str(tmp_path / f'patient-{state}-{width}x{height}.png'))
        _assert_full_surface(page, '.patient-unavailable' if state == 'unavailable' else '.patient-duo-closed')
    finally:
        page.close()


@pytest.mark.parametrize('reduced_motion', ('reduce', 'no-preference'))
@pytest.mark.parametrize('status', (404, 410))
def test_week_paging_preserves_updates_and_never_restores_withdrawn_content(
    live_signage: tuple[str, Flask], browser: Browser, reduced_motion: str, status: int,
) -> None:
    base_url, application = live_signage
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion=reduced_motion)
    path = f'{base_url}/signage/patienten/woche'
    visible = '[data-signage-page]:not([hidden])'
    try:
        page.clock.install()
        response = page.goto(path)
        assert response and response.status == 200
        expect(page.locator(f'{visible} .patient-board-page-label')).to_contain_text('Seite 1')
        page.clock.fast_forward(29000)
        expect(page.locator(f'{visible} .patient-board-page-label')).to_contain_text('Seite 1')
        page.clock.fast_forward(1400)
        expect(page.locator(f'{visible} .patient-board-page-label')).to_contain_text('Seite 2')

        snapshot = application.config['TEST_SNAPSHOTS']['patient']
        snapshot['revision_id'] = 'PAT-2026-KW36-R2'
        # Friday lunch sits on page 2, the page the board is showing right now.
        snapshot['days'][4]['services'][0]['options'][0]['title'] = 'Frisch zubereitetes Tagesgericht'
        page.clock.fast_forward(1000)
        expect(page.locator('html')).to_have_attribute('data-signage-revision', 'PAT-2026-KW36-R2')
        expect(page.locator(f'{visible} .patient-board-page-label')).to_contain_text('Seite 2')
        expect(page.locator(visible)).to_contain_text('Frisch zubereitetes Tagesgericht')
        application.config['DEMO_TODAY'] = '2026-09-03'
        page.clock.fast_forward(1000)
        expect(page.locator('html')).to_have_attribute('data-signage-date', '2026-09-03')
        expect(page.locator(f'{visible} .patient-board-page-label')).to_contain_text('Seite 2')

        # Withdrawal while a page transition may be pending must cancel the old callbacks.
        page.clock.fast_forward(30000)
        page.route(path, lambda route: route.fulfill(status=status, content_type='text/html', body='<h1>Pause</h1>'))
        page.clock.fast_forward(150)
        expect(page.locator('[data-signage-page]')).to_have_count(0)
        expect(page.locator('[data-signage-root]')).to_contain_text('Speiseplan nicht verfügbar')
        page.clock.fast_forward(61000)
        expect(page.locator('[data-signage-page]')).to_have_count(0)
        assert not page.locator('[data-signage-frame]').evaluate('node => node.classList.contains("is-updating")')

        page.unroute(path)
        page.clock.fast_forward(1000)
        expect(page.locator('[data-signage-page]')).to_have_count(4)
        expect(page.locator(f'{visible} .patient-board-page-label')).to_contain_text('Seite 1')
        page.clock.fast_forward(30400)
        expect(page.locator(f'{visible} .patient-board-page-label')).to_contain_text('Seite 2')
        assert FORBIDDEN.search(page.content()) is None
    finally:
        page.close()
