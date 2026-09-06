from __future__ import annotations

from datetime import datetime

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect

from test_rendered_ui import app as app
from test_rendered_ui import browser as browser
from test_signage_engine import live_signage as live_signage

MENUS = '.hero-food, .cafe-week-slot, .patient-signage-option, .patient-week-option'


@pytest.mark.parametrize('failure', ('network', 'server'))
@pytest.mark.parametrize('surface', ('cafeteria/tag', 'cafeteria/woche', 'patienten/tag', 'patienten/woche'))
def test_buffer_expires_after_five_minutes_and_same_revision_recovers(
    live_signage: tuple[str, Flask], browser: Browser, failure: str, surface: str,
) -> None:
    base_url, _ = live_signage
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce')
    url = f'{base_url}/signage/{surface}'
    try:
        page.clock.install(time=datetime.fromisoformat('2026-09-02T10:00:00+00:00'))
        response = page.goto(url)
        assert response and response.status == 200
        assert "script-src 'self'" in response.headers['content-security-policy']
        count = page.locator(MENUS).count()
        assert count > 0
        revision = page.locator('html').get_attribute('data-signage-revision')
        assert revision and revision not in page.locator('body').inner_text()
        rendered_titles = page.locator('[data-signage-root] h3').all_text_contents()
        assert rendered_titles
        if failure == 'network':
            page.route(url, lambda route: route.abort('failed'))
        else:
            page.route(url, lambda route: route.fulfill(status=503, body='Unavailable'))
        page.clock.fast_forward(298000)
        expect(page.locator(MENUS)).to_have_count(count)
        expect(page.locator('[data-signage-status]')).to_have_attribute('data-offline', 'true')
        page.clock.fast_forward(2100)
        expect(page.locator(MENUS)).to_have_count(0)
        expect(page.locator('[data-signage-root]')).to_contain_text('Speiseplan nicht verfügbar')
        assert all(title not in page.locator('[data-signage-root]').inner_text() for title in rendered_titles)
        clock = page.locator('[data-signage-clock]').inner_text()
        page.clock.fast_forward(61000)
        expect(page.locator(MENUS)).to_have_count(0)
        expect(page.locator('[data-signage-clock]')).not_to_have_text(clock)

        page.unroute(url)
        page.clock.fast_forward(1000)
        expect(page.locator(MENUS)).to_have_count(count)
        expect(page.locator('html')).to_have_attribute('data-signage-revision', revision)
        assert revision not in page.locator('body').inner_text()
        expect(page.locator('[data-signage-status]')).not_to_have_attribute('data-offline', 'true')
        if surface == 'patienten/woche':
            visible = '[data-signage-page]:not([hidden]) .patient-board-page-label'
            expect(page.locator(visible)).to_contain_text('Seite 1')
            page.clock.fast_forward(30100)
            expect(page.locator(visible)).to_contain_text('Seite 2')
    finally:
        page.close()


@pytest.mark.parametrize('failure', ('network', 'server'))
@pytest.mark.parametrize('instant', ('2026-09-02T21:59:58+00:00', '2026-01-02T22:59:58+00:00'))
def test_buffer_expires_at_zurich_midnight_in_summer_and_winter(
    live_signage: tuple[str, Flask], browser: Browser, failure: str, instant: str,
) -> None:
    base_url, _ = live_signage
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce')
    url = f'{base_url}/signage/patienten/woche'
    try:
        page.clock.install(time=datetime.fromisoformat(instant))
        response = page.goto(url)
        assert response and response.status == 200
        expect(page.locator(MENUS)).to_have_count(28)
        if failure == 'network':
            page.route(url, lambda route: route.abort('failed'))
        else:
            page.route(url, lambda route: route.fulfill(status=503, body='Unavailable'))
        page.clock.fast_forward(1000)
        expect(page.locator(MENUS)).to_have_count(28)
        page.clock.fast_forward(1100)
        expect(page.locator(MENUS)).to_have_count(0)
        expect(page.locator('[data-signage-root]')).to_contain_text('Speiseplan nicht verfügbar')
        page.clock.fast_forward(61000)
        expect(page.locator('[data-signage-page]')).to_have_count(0)
    finally:
        page.close()


def test_midnight_expiry_cancels_a_snapshot_fade_in_progress(
    live_signage: tuple[str, Flask], browser: Browser,
) -> None:
    base_url, application = live_signage
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion='no-preference')
    try:
        page.clock.install(time=datetime.fromisoformat('2026-09-02T21:59:50+00:00'))
        page.goto(f'{base_url}/signage/patienten/woche')
        page.clock.pause_at(datetime.fromisoformat('2026-09-02T21:59:59.700+00:00'))
        application.config['TEST_SNAPSHOTS']['patient']['revision_id'] = 'PAT-2026-KW36-R2'
        page.clock.run_for(100)
        expect(page.locator('[data-signage-frame]')).to_have_class('signage-shell patient-week-shell patient-board-shell is-updating')
        page.context.set_offline(True)
        page.clock.run_for(600)
        expect(page.locator(MENUS)).to_have_count(0)
        expect(page.locator('[data-signage-root]')).to_contain_text('Speiseplan nicht verfügbar')
        assert not page.locator('[data-signage-frame]').evaluate('node => node.classList.contains("is-updating")')
    finally:
        page.close()
