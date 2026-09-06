from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect

from test_rendered_ui import _set_unbroken_signage_boundaries
from test_rendered_ui import app as app
from test_rendered_ui import browser as browser
from test_signage_engine import live_signage as live_signage


def test_distinct_menu_description_is_retained_once(app: Flask) -> None:
    option = app.config['TEST_SNAPSHOTS']['staff_guest']['days'][2]['services'][0]['options'][0]
    description = 'Mit hausgemachter Sauce serviert.'
    option['description'] = description
    response = app.test_client().get('/signage/cafeteria/tag')
    assert response.status_code == 200
    assert response.get_data(as_text=True).count(description) == 1


def _assert_visible_contents(page: Page) -> None:
    metrics = page.evaluate(
        """() => {
          const selectors = '.hero-food, .hero-food .content, .hero-food h3, '
            + '.hero-food p, .hero-food footer, .hero-food .signage-price, '
            + '.hero-food .signage-tags, .hero-food-closed';
          return {
            viewport: document.documentElement.scrollWidth <= innerWidth + 1
              && document.documentElement.scrollHeight <= innerHeight + 1,
            clipped: [...document.querySelectorAll(selectors)].filter(node =>
              node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1
            ).map(node => ({element: node.className, width: [node.scrollWidth, node.clientWidth],
              height: [node.scrollHeight, node.clientHeight], lineHeight: getComputedStyle(node).lineHeight})),
          };
        }""",
    )
    assert metrics == {'viewport': True, 'clipped': []}


@pytest.mark.parametrize(('width', 'height'), ((1920, 1080), (3840, 2160)))
@pytest.mark.parametrize('scenario', ('photos', 'fallback', 'boundary'))
def test_hero_food_two_cards_remain_visible(
    live_signage: tuple[str, Flask], browser: Browser, tmp_path: Path,
    width: int, height: int, scenario: str,
) -> None:
    base_url, application = live_signage
    snapshot = application.config['TEST_SNAPSHOTS']['staff_guest']
    if scenario == 'boundary':
        _set_unbroken_signage_boundaries(snapshot, title_length=46, component_length=70)
    elif scenario == 'fallback':
        for option in snapshot['days'][2]['services'][0]['options']:
            option.pop('menu_image', None)
            option['title'] = f"Tagesgericht {option['type_name']}"

    page = browser.new_page(viewport={'width': width, 'height': height}, reduced_motion='reduce')
    try:
        response = page.goto(f'{base_url}/signage/cafeteria/tag')
        assert response and response.status == 200
        assert "script-src 'self'" in response.headers['content-security-policy']
        page.evaluate('document.fonts.ready')
        cards = page.locator('.hero-food-grid.row.g-4 > .col-6 > .hero-food.card')
        expect(cards).to_have_count(2)
        expect(page.locator('h1')).to_have_count(1)
        for card in cards.all():
            expect(card).to_be_visible()
            expect(card.locator('.card-title')).to_be_visible()
            expect(card.locator('[data-menu-metadata]')).to_be_visible()
            expect(card.locator('footer')).to_contain_text('Mitarbeitende CHF')
            expect(card.locator('footer')).to_contain_text('Externe CHF')
            assert card.locator('.card-title').evaluate(
                'node => parseFloat(getComputedStyle(node).fontSize)',
            ) >= (46 if width == 1920 else 92)
        if scenario == 'photos':
            expect(page.locator('.hero-food .menu-photo img')).to_have_count(2)
            page.wait_for_function(
                "[...document.querySelectorAll('.hero-food .menu-photo img')]"
                '.every(image => image.complete && image.naturalWidth > 0)',
            )
        else:
            expect(page.locator('[data-menu-image-fallback]')).to_have_count(2)
            expect(page.locator('.hero-food .menu-photo')).to_have_count(0)
        expect(page.locator('a,nav,form,button,input,select,textarea,[style],[onclick],[onload]')).to_have_count(0)
        page.screenshot(path=str(tmp_path / f'cafeteria-day-{scenario}-{width}x{height}.png'))
        _assert_visible_contents(page)
    finally:
        page.close()


@pytest.mark.parametrize('closure', ('weekend', 'service'))
@pytest.mark.parametrize(('width', 'height'), ((1920, 1080), (3840, 2160)))
def test_hero_food_closed_screen_keeps_the_shared_shell(
    live_signage: tuple[str, Flask], browser: Browser, tmp_path: Path,
    closure: str, width: int, height: int,
) -> None:
    base_url, application = live_signage
    if closure == 'weekend':
        application.config['DEMO_TODAY'] = '2026-09-05'
        expected = 'Am Wochenende bleibt die Cafeteria geschlossen.'
    else:
        lunch = application.config['TEST_SNAPSHOTS']['staff_guest']['days'][2]['services'][0]
        lunch['service_state'] = 'closed'
        lunch['notice'] = 'Heute bleibt die Cafeteria wegen eines Feiertags geschlossen.'
        expected = lunch['notice']
    page = browser.new_page(viewport={'width': width, 'height': height}, reduced_motion='reduce')
    try:
        response = page.goto(f'{base_url}/signage/cafeteria/tag')
        assert response and response.status == 200
        page.evaluate('document.fonts.ready')
        expect(page.locator('.hero-food-closed.card')).to_be_visible()
        expect(page.locator('[data-signage-root]')).to_contain_text('Cafeteria geschlossen')
        expect(page.locator('[data-signage-root]')).to_contain_text(expected)
        expect(page.locator('[data-signage-clock]')).not_to_be_empty()
        expect(page.locator('[data-signage-footer]')).to_be_visible()
        expect(page.locator('h1')).to_have_count(1)
        expect(page.locator('a,nav,form,button,[style],[onclick]')).to_have_count(0)
        _assert_visible_contents(page)
        page.screenshot(path=str(tmp_path / f'cafeteria-closed-{closure}-{width}x{height}.png'))
    finally:
        page.close()
