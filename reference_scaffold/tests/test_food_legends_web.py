from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect

from test_rendered_ui import app as app
from test_rendered_ui import browser as browser
from test_signage_engine import live_signage as live_signage


@pytest.mark.parametrize('profile,path,weekly', [
    ('staff_guest', '/cafeteria/heute/', False),
    ('staff_guest', '/cafeteria/wochenangebot/', True),
    ('patient', '/patienten/heute/', False),
    ('patient', '/patienten/wochenplan/', True),
])
@pytest.mark.parametrize('width', [390, 1440])
def test_web_legends_follow_rendered_options_over_real_http(
    live_signage: tuple[str, Flask], browser: Browser, tmp_path: Path,
    profile: str, path: str, weekly: bool, width: int,
) -> None:
    url, application = live_signage
    snapshot = application.config['TEST_SNAPSHOTS'][profile]
    application.config['DEMO_TODAY'] = snapshot['days'][0]['date']
    for day in snapshot['days']:
        for service in day['services']:
            for option in service['options']:
                option.update(allergens=[], origins=[], labels=[], allergen_review_status='checked')
    visible = snapshot['days'][0]['services'][0]['options']
    for option, presence in zip(visible, ('contains', 'may_contain'), strict=True):
        option.update(
            allergens=[{'code': 'MILK', 'name': 'Milch', 'presence': presence}],
            origins=[{'ingredient': 'Kartoffel', 'country_code': 'CH', 'text': 'Kartoffel: CH'}],
            labels=[{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
            allergen_review_status='not_checked',
        )
    closed = snapshot['days'][1]['services'][0]
    closed.update(service_state='closed', notice='Heute geschlossen')
    closed['options'][0]['allergens'] = [{'code': 'FISH', 'name': 'Fisch', 'presence': 'contains'}]
    later = snapshot['days'][2]['services'][0]['options']
    later[0]['allergens'] = [{'code': 'NUTS', 'name': 'Schalenfrüchte', 'presence': 'contains'}]
    later[1].update(title='', allergens=[{'code': 'SESAME', 'name': 'Sesam', 'presence': 'contains'}])
    original = deepcopy(snapshot)
    page = browser.new_page(viewport={'width': width, 'height': 1100})
    try:
        response = page.goto(url + path, wait_until='load')
        assert response and response.status == 200
        assert "script-src 'self'" in response.headers['content-security-policy']
        legend = page.locator('.food-legend')
        expect(legend).to_have_count(1)
        text = legend.inner_text()
        assert text.count('Enthält: Milch') == text.count('Kann enthalten: Milch') == 1
        assert text.count('Schweiz') == text.count('Vegetarisch') == 1
        assert 'Fisch' not in text and 'Sesam' not in text
        assert ('Schalenfrüchte' in text) == weekly
        assert 'Allergenprüfung offen' in text
        assert ('Allergenangaben nicht erfasst' in text) == (weekly or profile == 'patient')
        assert legend.locator('img').evaluate_all('nodes => nodes.every(n => n.complete && n.naturalWidth > 0)')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert legend.evaluate('node => node.scrollWidth <= node.clientWidth + 1')
        page.screenshot(path=str(tmp_path / f'legend-{profile}-{weekly}-{width}.png'), full_page=True)
    finally:
        page.close()
    assert snapshot == original


@pytest.mark.parametrize('path', ['/cafeteria/heute/', '/patienten/heute/'])
def test_closed_days_do_not_publish_a_legend(app: Flask, path: str) -> None:
    profile = 'patient' if 'patienten' in path else 'staff_guest'
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    app.config['DEMO_TODAY'] = snapshot['days'][0]['date']
    for service in snapshot['days'][0]['services']:
        service.update(service_state='closed', notice='Heute geschlossen')
        service['options'][0]['allergens'] = [{'code': 'FISH', 'name': 'Fisch', 'presence': 'contains'}]
    response = app.test_client().get(path)
    assert response.status_code == 200
    assert 'food-legend' not in response.get_data(as_text=True)
