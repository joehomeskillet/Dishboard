from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect

from test_rendered_ui import app as app
from test_rendered_ui import browser as browser
from test_signage_engine import live_signage as live_signage


def _assert_legend_fits(page: Page) -> None:
    legend = page.locator('.food-legend:visible')
    expect(legend).to_have_count(1)
    assert legend.evaluate('''node => {
        const box = node.getBoundingClientRect();
        return box.left >= 0 && box.top >= 0 && box.right <= innerWidth + 1 && box.bottom <= innerHeight + 1
          && node.scrollWidth <= node.clientWidth + 1 && node.scrollHeight <= node.clientHeight + 1;
    }''')
    assert legend.locator('h2, p, span').evaluate_all(
        'nodes => nodes.every(node => parseFloat(getComputedStyle(node).fontSize) >= 18)',
    )
    assert legend.locator('img').evaluate_all('nodes => nodes.every(n => n.complete && n.naturalWidth > 0)')
    symbols = legend.locator('.food-symbol').evaluate_all('''nodes => nodes.map(node => {
        const box = node.getBoundingClientRect();
        return {width: box.width, height: box.height,
            font: parseFloat(getComputedStyle(node).fontSize),
            country: node.classList.contains('food-symbol--country')};
    })''')
    assert symbols
    for symbol in symbols:
        assert abs(symbol['height'] - 1.5 * symbol['font']) <= 1, symbol
        assert abs(symbol['width'] - (2 if symbol['country'] else 1.5) * symbol['font']) <= 1, symbol


@pytest.mark.parametrize('width,height', [(1920, 1080), (3840, 2160)])
def test_patient_rotation_keeps_legends_with_their_page_and_recovers(
    live_signage: tuple[str, Flask], browser: Browser, tmp_path: Path, width: int, height: int,
) -> None:
    url, application = live_signage
    snapshot = application.config['TEST_SNAPSHOTS']['patient']
    for index, day in enumerate(snapshot['days']):
        for service in day['services']:
            for option in service['options']:
                code, name = ('MILK', 'Milch') if index < 3 else ('NUTS', 'Schalenfrüchte')
                option.update(
                    allergens=[{'code': code, 'name': name, 'presence': 'contains'}],
                    origins=[], labels=[], allergen_review_status='checked',
                )
    closed = snapshot['days'][1]['services'][0]
    closed.update(service_state='closed', notice='Heute geschlossen')
    closed['options'][0]['allergens'] = [{'code': 'FISH', 'name': 'Fisch', 'presence': 'contains'}]
    snapshot['days'][2]['services'][0]['options'][1].update(
        title='', allergens=[{'code': 'SESAME', 'name': 'Sesam', 'presence': 'contains'}],
    )
    page = browser.new_page(viewport={'width': width, 'height': height}, reduced_motion='reduce')
    try:
        page.clock.install()
        response = page.goto(url + '/signage/patienten/woche')
        assert response and response.status == 200
        assert "script-src 'self'" in response.headers['content-security-policy']
        for index, wanted, absent in [(1, 'Milch', 'Schalenfrüchte'), (2, 'Schalenfrüchte', 'Milch')]:
            if index == 2:
                page.clock.fast_forward(30100)
            legend = page.locator('.food-legend:visible')
            expect(legend).to_contain_text(f'Enthält: {wanted}')
            assert absent not in legend.inner_text()
            assert 'Fisch' not in legend.inner_text() and 'Sesam' not in legend.inner_text()
            assert 'Sesam' not in page.locator('body').inner_text()
            _assert_legend_fits(page)
            page.screenshot(path=str(tmp_path / f'patient-week-legend-{index}-{width}.png'))
        application.config['TEST_SNAPSHOTS']['patient'] = None
        page.clock.fast_forward(1000)
        expect(page.locator('.food-legend')).to_have_count(0)
        page.clock.fast_forward(31000)
        expect(page.locator('.food-legend')).to_have_count(0)
        application.config['TEST_SNAPSHOTS']['patient'] = snapshot
        page.clock.fast_forward(1000)
        expect(page.locator('.food-legend:visible')).to_contain_text('Enthält: Milch')
        page.clock.fast_forward(30100)
        expect(page.locator('.food-legend:visible')).to_contain_text('Enthält: Schalenfrüchte')
    finally:
        page.close()


@pytest.mark.parametrize('path', ['/signage/cafeteria/tag', '/signage/cafeteria/woche', '/signage/patienten/tag'])
@pytest.mark.parametrize('width,height', [(1920, 1080), (3840, 2160)])
def test_other_signage_legends_are_complete_and_fit(
    live_signage: tuple[str, Flask], browser: Browser, tmp_path: Path,
    path: str, width: int, height: int,
) -> None:
    url, _ = live_signage
    page = browser.new_page(viewport={'width': width, 'height': height})
    try:
        response = page.goto(url + path)
        assert response and response.status == 200
        _assert_legend_fits(page)
        assert 'Enthält:' in page.locator('.food-legend').inner_text()
        page.screenshot(path=str(tmp_path / f'{path.replace("/", "-")}-legend-{width}.png'))
    finally:
        page.close()
