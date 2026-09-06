from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect
from sqlalchemy import Engine

from test_admin_ux_browser import live_server as live_server
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import _login
from test_rendered_ui import admin_app as admin_app
from test_rendered_ui import admin_engine as admin_engine
from test_rendered_ui import browser as browser


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_admin_legends_explain_only_the_rendered_cards(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,
    family: str, profile: str, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    for option, presence in zip(values['days'][-1]['services'][0]['options'], ('contains', 'may_contain'), strict=True):
        option['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': presence}]
        option['origins'] = [{'ingredient': 'Kartoffel', 'country_code': 'CH', 'text': 'Kartoffel: CH'}]
    closed = values['days'][1]['services'][0]
    closed.update(service_state='closed', notice='Heute geschlossen')
    closed['options'][0]['allergens'] = [{'code': 'FISH', 'name': 'Fisch', 'presence': 'contains'}]
    empty_service = values['days'][2]['services'][0]
    empty_service.update(service_state='closed', notice='Heute geschlossen')
    empty = empty_service['options'][0]
    empty.update(title='', allergens=[{'code': 'SESAME', 'name': 'Sesam', 'presence': 'contains'}])
    _save(admin_engine, profile, values)
    cookie = client.get_cookie('session')
    assert cookie is not None
    week = values['days'][0]['date']
    with browser.new_context(base_url=live_server) as context:
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
        page = context.new_page()
        for width in (390, 1440):
            page.set_viewport_size({'width': width, 'height': 1100})
            for suffix in ('', '/preview', '/menues'):
                path = f'/admin/{family}{suffix}' + (f'?week={week}' if suffix != '/menues' else '')
                response = page.goto(path, wait_until='load')
                assert response and response.status == 200
                legend = page.locator('.food-legend:visible')
                expect(legend).to_have_count(1)
                assert legend.inner_text().count('Enthält: Milch') == 1
                assert legend.inner_text().count('Kann enthalten: Milch') == 1
                assert legend.inner_text().count('Schweiz') == 1
                assert 'Fisch' not in legend.inner_text()
                assert 'Sesam' not in legend.inner_text()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                assert legend.locator('img').evaluate_all('nodes => nodes.every(n => n.complete && n.naturalWidth > 0)')
                page.screenshot(path=str(tmp_path / f'{family}-{suffix.replace("/", "") or "week"}-{width}.png'), full_page=True)
                if suffix == '/menues':
                    page.get_by_role('tab', name='Liste', exact=True).click()
                    expect(page.locator('.food-legend:visible')).to_have_count(0)
                    page.get_by_role('tab', name='Karten', exact=True).click()
                    expect(page.locator('.food-legend:visible')).to_have_count(1)
