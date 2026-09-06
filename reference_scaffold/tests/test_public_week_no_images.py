"""Image-free weekly links retain the complete published menu over real HTTP."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect

from cafeteria.public import routes as public_routes
from test_public_equal_cards_browser import _assert_symbol_sizes
from test_public_mobile_ui import http_app as http_app, public_server as public_server
from test_rendered_ui import PATIENT_FORBIDDEN, app as app, browser as browser

WEEKS = (
    ('staff_guest', '/cafeteria/wochenangebot/', 10),
    ('patient', '/patienten/wochenplan/', 28),
)


@pytest.mark.parametrize('profile,path,count', WEEKS)
def test_image_free_week_is_a_published_variant(app: Flask, profile: str, path: str, count: int) -> None:
    original = deepcopy(app.config['TEST_SNAPSHOTS'][profile])
    client = app.test_client()
    with_images = client.get(path)
    without_images = client.get(path + 'ohne-bilder/')
    assert with_images.status_code == without_images.status_code == 200
    assert with_images.headers['X-Snapshot-Revision'] == without_images.headers['X-Snapshot-Revision']
    assert with_images.headers['Cache-Control'] == without_images.headers['Cache-Control']
    body = without_images.get_data(as_text=True)
    assert body.count('class="card h-100"') == count
    assert 'class="menu-photo"' in with_images.get_data(as_text=True)
    assert 'menu-photo' not in body and 'card-img-top' not in body
    assert 'Frisch aus unserer Küche' not in body
    assert 'KI-generierter Serviervorschlag' not in body
    assert 'class="food-legend' in body
    if profile == 'patient':
        assert PATIENT_FORBIDDEN.search(body) is None
    else:
        assert 'CHF' in body
    assert app.config['TEST_SNAPSHOTS'][profile] == original


@pytest.mark.parametrize('profile,path,count', WEEKS)
@pytest.mark.parametrize('query', ['images=hide', 'date=2026-09-02', '&'])
def test_image_free_week_keeps_the_no_query_contract(
    app: Flask, profile: str, path: str, count: int, query: str,
) -> None:
    response = app.test_client().get(path + 'ohne-bilder/', query_string=query)
    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('profile,path,count', WEEKS)
def test_image_free_week_without_publication_is_not_cached(
    app: Flask, profile: str, path: str, count: int, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(public_routes, 'active_snapshot', lambda *args, **kwargs: None)
    response = app.test_client().get(path + 'ohne-bilder/')
    assert response.status_code == 404
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'card-img-top' not in response.get_data(as_text=True)


@pytest.mark.parametrize('profile,path,count', WEEKS)
def test_image_free_week_preserves_closed_service_and_date(
    app: Flask, profile: str, path: str, count: int,
) -> None:
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    meal = snapshot['days'][0]['services'][0]
    withdrawn_titles = [option['title'] for option in meal['options']]
    meal.update(service_state='closed', notice='Heute wegen Wartung geschlossen')
    app.config['DEMO_TODAY'] = snapshot['days'][-1]['date']
    response = app.test_client().get(path + 'ohne-bilder/')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Heute wegen Wartung geschlossen' in body
    assert body.count('class="card h-100"') == count - 2
    for title in withdrawn_titles:
        assert title not in body
    if profile == 'patient':
        assert 'aria-current="date"' in body


@pytest.mark.parametrize('profile,path,count', WEEKS)
@pytest.mark.parametrize('width,height', [(390, 844), (820, 1180), (1920, 1080)])
def test_real_image_free_weeks_keep_equal_complete_cards_and_symbols(
    http_app: Flask, public_server: str, browser: Browser, profile: str,
    path: str, count: int, width: int, height: int, tmp_path: Path,
) -> None:
    snapshot = http_app.config['TEST_SNAPSHOTS'][profile]
    options = [option for day in snapshot['days'] for meal in day['services'] for option in meal['options']]
    options[-1].update(
        title='Saisonales Gemüse aus unserer Küche',
        components=['Reis', 'Zucchetti', 'Frisch zubereitet mit saisonalem Gemüse. ' * 5],
        description='Vollständige Beschreibung bleibt sichtbar. ' * 5,
        note='Ungeprüfter Rezepturhinweis: Rezeptur und Produktdeklaration prüfen. ' * 6,
        origins=[{'country_code': 'CH', 'text': 'Schweiz'}],
        allergens=[
            {'code': 'MILK', 'name': 'Milch', 'presence': 'contains'},
            {'code': 'SOY', 'name': 'Soja', 'presence': 'may_contain'},
            {'code': 'CELERY', 'name': 'Sellerie', 'presence': 'unknown'},
        ],
    )
    original = deepcopy(snapshot)
    with browser.new_context(java_script_enabled=False, viewport={'width': width, 'height': height}) as context:
        page = context.new_page()
        failures: list[str] = []
        image_requests: list[str] = []
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
        page.on('requestfailed', lambda request: failures.append(request.url))
        page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
        page.goto(public_server + path, wait_until='networkidle')
        cards = page.locator('.card:has(> .card-status-top)')
        original_text = cards.locator('.card-body').all_text_contents()
        original_legend = page.locator('.food-legend').inner_text()
        original_logo = page.locator('.site-logo-img').get_attribute('src')
        image_count = cards.locator('.menu-photo img').count()
        assert image_count > 0
        page.on('request', lambda request: image_requests.append(request.url) if '/img/menus/' in request.url else None)
        response = page.goto(public_server + path + 'ohne-bilder/', wait_until='networkidle')
        assert response is not None and response.status == 200
        assert "script-src 'self'" in response.headers['content-security-policy']
        assert "style-src 'self'" in response.headers['content-security-policy']
        assert response.headers['x-snapshot-revision'] == snapshot['revision_id']
        assert 'set-cookie' not in response.headers
        page.evaluate('document.fonts.ready')
        expect(cards).to_have_count(count)
        assert cards.locator('.card-title').all_text_contents() == [option['title'] for option in options]
        assert cards.locator('.card-body').all_text_contents() == original_text
        assert page.locator('.food-legend').inner_text() == original_legend
        assert page.locator('.site-logo-img').get_attribute('src') == original_logo
        assert page.locator('.card-img-top, .menu-photo').count() == 0
        assert not image_requests
        for text in ('Enthält: Milch', 'Kann enthalten: Soja', 'Allergenangabe ungeklärt: Sellerie', 'Schweiz'):
            assert text in cards.last.inner_text()
        for field in ('description', 'note'):
            assert options[-1][field].strip() in cards.last.inner_text()
        sizes = cards.evaluate_all('''elements => elements.map(element => {
            const box = element.getBoundingClientRect();
            return {width: box.width, height: box.height,
                clipped: element.scrollWidth > element.clientWidth + 1 ||
                    element.scrollHeight > element.clientHeight + 1};
        })''')
        for axis in ('width', 'height'):
            assert max(size[axis] for size in sizes) - min(size[axis] for size in sizes) <= 1
        assert not any(size['clipped'] for size in sizes)
        assert cards.locator('[data-menu-metadata]').evaluate_all('''elements => elements.every(element => {
            const box = element.getBoundingClientRect();
            const card = element.closest('.card').getBoundingClientRect();
            return box.left >= card.left && box.right <= card.right && box.bottom <= card.bottom &&
                getComputedStyle(element).overflowY !== 'hidden';
        })''')
        _assert_symbol_sizes(page)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('script, [style], [onclick]').count() == 0
        if profile == 'patient':
            assert PATIENT_FORBIDDEN.search(page.content()) is None
        else:
            assert 'CHF' in page.locator('body').inner_text()
        for link in page.locator('a:visible').all():
            box = link.bounding_box()
            assert box is not None and box['height'] >= 48
        assert not failures
        page.screenshot(path=str(tmp_path / f'{profile}-without-images-{width}.png'), full_page=True)
        (tmp_path / f'{profile}-{width}.json').write_text(json.dumps({
            'path': path + 'ohne-bilder/', 'viewport': [width, height], 'cards': count,
            'original_images': image_count, 'variant_images': 0, 'menu_image_requests': image_requests,
            'card_sizes': sizes, 'browser_errors': failures,
        }, indent=2))
    assert snapshot == original
