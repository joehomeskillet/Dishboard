from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page

from test_public_mobile_ui import http_app as http_app, public_server as public_server
from test_rendered_ui import app as app, browser as browser

PUBLIC_ROUTES = (
    ('/cafeteria/heute/', 'staff_guest', 2),
    ('/cafeteria/wochenangebot/', 'staff_guest', 10),
    ('/patienten/heute/', 'patient', 4),
    ('/patienten/wochenplan/', 'patient', 28),
)


def _assert_symbol_sizes(page: Page) -> None:
    assert page.locator('link[href$="/food-symbols.css"]').count() == 1
    symbols = page.locator('.food-symbol').evaluate_all('''elements => elements.map(element => {
        const box = element.getBoundingClientRect();
        const font = parseFloat(getComputedStyle(element).fontSize);
        return {width: box.width, height: box.height, font,
            country: element.classList.contains('food-symbol--country'),
            loaded: element.complete && element.naturalWidth > 0};
    })''')
    assert symbols and any(symbol['country'] for symbol in symbols)
    assert any(not symbol['country'] for symbol in symbols)
    for symbol in symbols:
        assert symbol['loaded']
        assert abs(symbol['height'] - 1.5 * symbol['font']) <= 1, symbol
        assert abs(symbol['width'] - (2 if symbol['country'] else 1.5) * symbol['font']) <= 1, symbol


@pytest.mark.parametrize('path,profile,count', PUBLIC_ROUTES)
def test_public_menu_cards_share_size_with_long_weekend_content(
    http_app: Flask, public_server: str, browser: Browser, path: str, profile: str,
    count: int, tmp_path: Path,
) -> None:
    snapshot = http_app.config['TEST_SNAPSHOTS'][profile]
    days = [day for day in snapshot['days'] if day['services']]
    http_app.config['DEMO_TODAY'] = days[-1]['date']
    selected = days[-1:] if count <= 4 else days
    options = [option for day in selected for meal in day['services'] for option in meal['options']]
    photo_option = snapshot['days'][2]['services'][0]['options'][0]
    options[0]['title'] = photo_option['title']
    options[0]['components'] = list(photo_option['components'])
    options[-1]['title'] = 'Saisonales Gemüse aus der Küche'
    options[-1]['components'] = ['Reis', 'Zucchetti', 'Frisch zubereitet mit saisonalem Gemüse. ' * 5]
    options[-1]['description'] = 'Vollständige Beschreibung bleibt sichtbar. ' * 5
    options[-1]['note'] = 'Ungeprüfter Rezepturhinweis: Rezeptur und Produktdeklaration prüfen. ' * 6
    options[-1]['origins'] = [{'country_code': 'CH', 'text': 'Schweiz'}]
    options[-1]['allergens'] = [
        {'code': 'MILK', 'name': 'Milch', 'presence': 'contains'},
        {'code': 'SOY', 'name': 'Soja', 'presence': 'may_contain'},
        {'code': 'CELERY', 'name': 'Sellerie', 'presence': 'unknown'},
    ]
    with browser.new_context(java_script_enabled=False) as context:
        page = context.new_page()
        for width, height in [(390, 844), (820, 1180), (1440, 1100)]:
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto(f'{public_server}{path}', wait_until='networkidle')
            assert response is not None and response.status == 200
            assert 'set-cookie' not in response.headers
            page.evaluate('document.fonts.ready')
            cards = page.locator('.card:has(> .card-status-top)')
            assert cards.count() == count
            assert cards.locator('.card-title').all_text_contents() == [option['title'] for option in options]
            for field in ('description', 'note'):
                assert options[-1][field].strip() in cards.last.inner_text()
            for text in ('Enthält: Milch', 'Kann enthalten: Soja', 'Allergenangabe ungeklärt: Sellerie', 'Schweiz'):
                assert text in cards.last.inner_text()
            sizes = cards.evaluate_all('''elements => elements.map(element => {
                const box = element.getBoundingClientRect();
                return {width: box.width, height: box.height,
                    clipped: element.scrollWidth > element.clientWidth + 1 ||
                        element.scrollHeight > element.clientHeight + 1};
            })''')
            for axis in ('width', 'height'):
                values = [size[axis] for size in sizes]
                assert max(values) - min(values) <= 1, (path, width, axis, values)
            assert not any(size['clipped'] for size in sizes)
            assert cards.locator('[data-menu-metadata]').evaluate_all('''elements => elements.every(element => {
                const box = element.getBoundingClientRect();
                const card = element.closest('.card').getBoundingClientRect();
                return box.left >= card.left && box.right <= card.right && box.bottom <= card.bottom &&
                    getComputedStyle(element).overflowY !== 'hidden';
            })''')
            assert cards.locator('.menu-photo img').count() > 0
            assert cards.last.locator('.menu-photo').count() == 0
            assert 'Frisch aus unserer Küche' in cards.last.inner_text()
            _assert_symbol_sizes(page)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert page.locator('script, [style], [onclick]').count() == 0
            if profile == 'patient':
                assert re.search(r'preis|chf|rappen|kosten|price|intern|extern|money|currency', page.content(), re.I) is None
            for link in page.locator('a:visible').all():
                box = link.bounding_box()
                assert box is not None and box['height'] >= 48
            cards.last.screenshot(path=str(tmp_path / f'{path.strip("/").replace("/", "-")}-{width}.png'))


@pytest.mark.parametrize('path,profile', [
    ('/signage/cafeteria/tag', 'staff_guest'), ('/signage/cafeteria/woche', 'staff_guest'),
    ('/signage/patienten/tag', 'patient'), ('/signage/patienten/woche', 'patient'),
])
def test_signage_shell_loads_shared_food_symbol_styles(
    http_app: Flask, public_server: str, browser: Browser, path: str, profile: str,
) -> None:
    for day in http_app.config['TEST_SNAPSHOTS'][profile]['days']:
        for meal in day['services']:
            for option in meal['options']:
                option['origins'] = [{'country_code': 'CH', 'text': 'Schweiz'}]
                option['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    with browser.new_context(java_script_enabled=False, viewport={'width': 1920, 'height': 1080}) as context:
        page = context.new_page()
        response = page.goto(f'{public_server}{path}', wait_until='networkidle')
        assert response is not None and response.status == 200
        assert page.locator('link[href$="/food-symbols.css"]').count() == 1
        # PS2 already consumes shared symbols; PS3/PS4 own their remaining template wiring.
        if path == '/signage/cafeteria/tag':
            _assert_symbol_sizes(page)
