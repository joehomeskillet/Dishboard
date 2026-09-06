from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import TypedDict

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page
from pypdf import PdfReader

from test_public_mobile_ui import http_app as http_app, public_server as public_server
from test_rendered_ui import app as app, browser as browser


class _Evidence(TypedDict):
    screen: list[dict[str, float | bool]]
    print: list[dict[str, float | bool]]
    print_pages: list[str]


def _geometry(page: Page) -> list[dict[str, float | bool]]:
    return page.locator('.week-menu').evaluate_all('''elements => elements.map(element => {
        const box = element.getBoundingClientRect();
        const day = element.closest('.week-day').getBoundingClientRect();
        return {x: box.x, y: box.y, width: box.width, height: box.height,
            clipped: element.scrollWidth > element.clientWidth + 1 ||
                element.scrollHeight > element.clientHeight + 1 ||
                box.bottom > day.bottom + 1 || box.right > day.right + 1};
    })''')


@pytest.mark.parametrize('profile,path,count', [
    ('patient', '/druck/patienten/woche', 28),
    ('staff_guest', '/druck/cafeteria/woche', 10),
])
@pytest.mark.parametrize('long_content', [False, True], ids=['short', 'long'])
def test_html_print_week_cards_keep_complete_content_and_shared_size(
    http_app: Flask, public_server: str, browser: Browser, profile: str,
    path: str, count: int, long_content: bool, tmp_path: Path,
) -> None:
    snapshot = http_app.config['TEST_SNAPSHOTS'][profile]
    options = [option for day in snapshot['days'] for meal in day['services']
               for option in meal['options']]
    for index, option in enumerate(options):
        option['title'] = f'Menü {index + 1}: Reis mit Gemüse'
        option['components'] = ['Reis', 'Gemüse']
        option['description'] = ''
        option['note'] = ''
        option['origins'] = [{'country_code': 'CH', 'text': 'Schweiz'}]
        option['labels'] = []
        option['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
        option['allergen_review_status'] = 'not_checked'
    options[-1]['title'] = 'Griessbrei mit Zwetschgenkompott'
    if long_content:
        options[-1]['components'].append('Frisch zubereitet mit saisonalem Gemüse. ' * 5)
        options[-1]['description'] = 'Vollständige Beschreibung bleibt sichtbar. ' * 5
        options[-1]['note'] = 'Rezeptur und Produktdeklaration vor der Ausgabe prüfen. ' * 6
        options[-1]['allergens'].extend([
            {'code': 'SOY', 'name': 'Soja', 'presence': 'may_contain'},
            {'code': 'CELERY', 'name': 'Sellerie', 'presence': 'unknown'},
        ])

    evidence: dict[int, _Evidence] = {}
    failures: list[str] = []
    with browser.new_context(java_script_enabled=False) as context:
        page = context.new_page()
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('requestfailed', lambda request: failures.append(request.url))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
        page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
        for width, height in [(390, 844), (820, 1180), (1440, 1100)]:
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto(f'{public_server}{path}', wait_until='networkidle')
            assert response is not None and response.status == 200
            assert "script-src 'self'" in response.headers['content-security-policy']
            assert "style-src 'self'" in response.headers['content-security-policy']
            assert 'set-cookie' not in response.headers
            page.evaluate('document.fonts.ready')
            cards = page.locator('.week-menu')
            assert cards.count() == count
            assert cards.locator(':scope > strong').all_text_contents() == [option['title'] for option in options]
            for card, option in zip(cards.all(), options, strict=True):
                content = card.inner_text()
                for text in [*option['components'], option['description'], option['note']]:
                    assert text.strip() in content
            legend = page.locator('.food-legend')
            assert legend.count() == 1
            for text in ['Schweiz', 'Enthält: Milch', 'Allergenprüfung offen'] + (
                ['Kann enthalten: Soja', 'Allergenangabe ungeklärt: Sellerie'] if long_content else []
            ):
                assert text in cards.last.inner_text()
                assert text in legend.inner_text()
            assert cards.locator('[data-menu-metadata]').evaluate_all('''elements => elements.every(element => {
                const box = element.getBoundingClientRect();
                const card = element.closest('.week-menu').getBoundingClientRect();
                return box.left >= card.left && box.right <= card.right + 1 && box.bottom <= card.bottom + 1;
            })''')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert page.locator('script, [style], [onclick]').count() == 0
            screen = _geometry(page)
            page.screenshot(path=str(tmp_path / f'{width}-screen.png'))
            cards.last.screenshot(path=str(tmp_path / f'{width}-last-card.png'))
            legend.screenshot(path=str(tmp_path / f'{width}-legend.png'))

            # Keep a durable print baseline: the screen-only fix must not change these pages.
            page.emulate_media(media='print')
            print_geometry = _geometry(page)
            pdf = page.pdf(path=str(tmp_path / f'{width}-print.pdf'), prefer_css_page_size=True)
            print_pages = []
            for sheet in PdfReader(BytesIO(pdf)).pages:
                contents = sheet.get_contents()
                assert contents is not None
                print_pages.append(hashlib.sha256(contents.get_data()).hexdigest())
            evidence[width] = {'screen': screen, 'print': print_geometry, 'print_pages': print_pages}
            page.emulate_media(media='screen')
        (tmp_path / 'geometry.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')

    assert not failures
    for width, sample in evidence.items():
        sizes = sample['screen']
        assert not any(size['clipped'] for size in sizes), (width, sizes)
        for axis in ('width', 'height'):
            values = [size[axis] for size in sizes]
            assert max(values) - min(values) <= 1, (path, width, axis, values)
