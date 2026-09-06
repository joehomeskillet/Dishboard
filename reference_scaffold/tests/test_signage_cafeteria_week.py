from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect

from test_rendered_ui import _set_unbroken_signage_boundaries
from test_rendered_ui import app as app, browser as browser
from test_signage_engine import live_signage as live_signage


def _layout_metrics(page: Page) -> dict:
    return page.evaluate('''() => {
        const selectors = '.cafe-week-board, .cafe-week-day, .cafe-week-menus, .cafe-week-slot, '
            + '.cafe-week-slot .slot-body, .cafe-week-slot h3, .cafe-week-slot p, '
            + '.cafe-week-slot [data-menu-metadata], .cafe-week-slot .label, '
            + '.cafe-week-slot footer, .cafe-week-closed';
        return {
            viewport: document.documentElement.scrollWidth <= innerWidth + 1 &&
                document.documentElement.scrollHeight <= innerHeight + 1,
            clipped: [...document.querySelectorAll(selectors)].flatMap(element => {
                const box = element.getBoundingClientRect();
                const body = element.closest('.slot-body');
                const bounds = body && body.getBoundingClientRect();
                const outside = bounds && element !== body && box.bottom > bounds.bottom + 1;
                if (element.scrollHeight <= element.clientHeight + 1 &&
                    element.scrollWidth <= element.clientWidth + 1 && !outside) return [];
                return [{element: element.className, width: [element.scrollWidth, element.clientWidth],
                    height: [element.scrollHeight, element.clientHeight], outside,
                    content: element.textContent.trim().slice(0, 90)}];
            }),
        };
    }''')


@pytest.mark.parametrize('width,height', [(1920, 1080), (3840, 2160)])
@pytest.mark.parametrize('scenario', ['published', 'unbroken', 'closed', 'recipe_note'])
def test_cafeteria_week_has_five_equal_complete_day_cards(
    live_signage: tuple[str, Flask], browser: Browser, tmp_path: Path,
    width: int, height: int, scenario: str,
) -> None:
    base_url, application = live_signage
    snapshot = application.config['TEST_SNAPSHOTS']['staff_guest']
    if scenario == 'unbroken':
        _set_unbroken_signage_boundaries(snapshot, title_length=37, component_length=49)
    if scenario == 'closed':
        meal = snapshot['days'][2]['services'][0]
        meal.update(service_state='closed', notice='Betriebsfeiertag: Am Mittwoch bleibt die Cafeteria geschlossen.')
    if scenario == 'recipe_note':
        option = snapshot['days'][4]['services'][0]['options'][-1]
        option['title'] = 'Gemüsegeschnetzeltes'
        option['components'] = ['Reis', 'Zucchetti']
        option['description'] = 'Mit hausgemachter Sauce serviert.'
        option['note'] = (
            'Ungeprüfter Rezepturhinweis: Bei Sauce Milch, bei Bindung Weizen und bei Bouillon Sellerie prüfen; '
            'falls Fleischersatz verwendet wird, dessen Soja- und Weizenbestandteile prüfen. '
            'Rezeptur und Produktdeklaration prüfen.'
        )
    options = [option for day in snapshot['days'] for meal in day['services']
               if meal.get('service_state', 'open') == 'open' for option in meal['options']]
    page = browser.new_page(viewport={'width': width, 'height': height}, reduced_motion='reduce')
    try:
        response = page.goto(f'{base_url}/signage/cafeteria/woche')
        assert response is not None and response.status == 200
        assert "style-src 'self'" in response.headers['content-security-policy']
        assert "script-src 'self'" in response.headers['content-security-policy']
        assert 'set-cookie' not in response.headers
        page.evaluate('document.fonts.ready')
        days = page.locator('.cafe-week-board.row.g-3 > .col > .cafe-week-day.card')
        expect(days).to_have_count(5)
        boxes = [card.bounding_box() for card in days.all()]
        assert all(box is not None for box in boxes)
        for axis in ('width', 'height'):
            values = [box[axis] for box in boxes if box is not None]
            assert max(values) - min(values) <= 1
        titles = page.locator('.cafe-week-slot h3')
        assert titles.all_text_contents() == [option['title'] for option in options]
        assert all(size >= (36 if width == 1920 else 72) for size in titles.evaluate_all(
            'elements => elements.map(element => parseFloat(getComputedStyle(element).fontSize))',
        ))
        for card, option in zip(page.locator('.cafe-week-slot').all(), options, strict=True):
            metadata = card.locator('[data-menu-metadata]')
            expect(metadata).to_be_visible()
            for component in option['components']:
                assert component in card.inner_text()
            if option.get('description'):
                assert option['description'] in card.inner_text()
            if option.get('note'):
                assert option['note'] in metadata.inner_text()
            for allergen in option.get('allergens', []):
                assert allergen['name'] in metadata.inner_text()
            expect(card.locator('footer')).to_contain_text('Mitarbeitende CHF')
            expect(card.locator('footer')).to_contain_text('Externe CHF')
        expect(page.locator('h1')).to_have_count(1)
        expect(page.locator('a,nav,form,button,input,select,textarea,[style],[onclick]')).to_have_count(0)
        assert page.locator('.food-symbol').count() > 0
        page.wait_for_function(
            "[...document.querySelectorAll('.food-symbol')].every(image => image.complete && image.naturalWidth > 0)",
        )
        if scenario == 'closed':
            expect(page.locator('.cafe-week-closed')).to_contain_text('Betriebsfeiertag: Am Mittwoch')
            expect(page.locator('.cafe-week-closed')).to_contain_text('Kein Mittagsservice')
        metrics = _layout_metrics(page)
        (tmp_path / f'cafeteria-week-{scenario}-{width}.json').write_text(json.dumps(metrics, indent=2))
        page.screenshot(path=str(tmp_path / f'cafeteria-week-{scenario}-{width}.png'))
        assert metrics == {'viewport': True, 'clipped': []}
    finally:
        page.close()


def test_week_retains_distinct_notes_and_allergen_presence(app: Flask) -> None:
    option = app.config['TEST_SNAPSHOTS']['staff_guest']['days'][0]['services'][0]['options'][0]
    option['description'] = 'Mit hausgemachter Sauce serviert.'
    option['note'] = 'Rezeptur und Produktdeklaration prüfen.'
    option['allergens'] = [
        {'code': 'MILK', 'name': 'Milch', 'presence': 'contains'},
        {'code': 'SOY', 'name': 'Soja', 'presence': 'may_contain'},
        {'code': 'CELERY', 'name': 'Sellerie', 'presence': 'unknown'},
    ]
    html = app.test_client().get('/signage/cafeteria/woche').get_data(as_text=True)
    for text in (option['description'], option['note']):
        assert html.count(text) == 1
    for text in ('Enthält: Milch', 'Kann enthalten: Soja', 'Allergenangabe ungeklärt: Sellerie'):
        assert text in html
