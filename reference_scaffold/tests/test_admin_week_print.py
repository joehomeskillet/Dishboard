from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser
from sqlalchemy import Engine, text

from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_print_requires_auth_and_exact_saved_week(
    admin_app: Flask, admin_engine: Engine, family: str, profile: str,  # noqa: F811
) -> None:
    path = f'/admin/{family}/preview/print?week={DAY}'
    assert admin_app.test_client().get(path).status_code == 401
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Editor'])
    assert client.get(path).status_code == 404
    values = _staff_values('Nur gespeicherte Druckwoche') if profile == 'staff_guest' else _patient_values('Nur gespeicherte Druckwoche')
    _save(admin_app.extensions['cafeteria_db'], profile, values)
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    body = response.get_data(as_text=True)
    assert 'Nur gespeicherte Druckwoche' in body
    assert f'data-profile="{profile}"' in body
    assert '31. August 2026 bis 04. September 2026' in body if profile == 'staff_guest' else '31. August 2026 bis 06. September 2026' in body
    assert client.get(f'/admin/{family}/preview/print?week=2026-09-07').status_code == 404
    preview = client.get(f'/admin/{family}/preview?week={DAY}').get_data(as_text=True)
    assert path in preview
    for suffix in ('&profile=patient', '&profile_scope=common', '&week=2026-09-07'):
        assert client.get(path + suffix).status_code == 400
    assert client.get(f'/admin/{family}/preview/print?week=2026-09-01').status_code == 400
    with admin_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
    assert client.get(path).status_code == 503


def test_print_metadata_closed_slots_and_patient_isolation(
    admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _patient_values()
    option = values['days'][0]['services'][0]['options'][0]
    option.update(
        title='<b>Kartoffelgratin</b>', description='Mit frischen Kräutern', note='Hinweis zur Zubereitung',
        allergens=[{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}, {'code': 'EGGS', 'name': 'Eier', 'presence': 'may_contain'}],
        labels=[{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}], origins=[{'ingredient': 'Kartoffeln', 'country_code': 'CH', 'text': 'Kartoffeln: CH'}],
        allergen_review_status='not_checked',
    )
    values['days'][-1]['services'][-1].update(service_state='closed', notice='Küche geschlossen')
    _save(admin_app.extensions['cafeteria_db'], 'patient', values)
    response = client.get(f'/admin/patienten/preview/print?week={DAY}')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '&lt;b&gt;Kartoffelgratin&lt;/b&gt;' in body
    assert 'Mit frischen Kräutern' in body and 'Hinweis zur Zubereitung' in body
    assert 'Kartoffeln: CH' in body and 'Enthält: Milch' in body and 'Kann enthalten: Eier' in body
    assert 'Allergenprüfung offen' in body and 'Allergenangaben nicht erfasst' in body
    assert body.count('Küche geschlossen') == 1
    assert body.count('week-print-patient') == 2
    assert re.search(r'\b(?:preise?|chf|rappen|kosten|prices?|cafeteria)\b', body, re.I) is None


@pytest.mark.parametrize('family,profile,dense', [
    ('cafeteria', 'staff_guest', False), ('patienten', 'patient', False), ('cafeteria', 'staff_guest', True),
])
def test_print_browser_and_pdf(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, dense: bool, tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    for day in values['days']:
        for service in day['services']:
            for option in service['options']:
                if profile == 'staff_guest':
                    option.update(internal_rappen=1100, external_rappen=1660)
                if dense:
                    option.update(
                        title='Gebratene Gemüse-Kichererbsenbällchen mit Zitronen-Kräuter-Dressing',
                        description='Frisch zubereitet mit saisonalen Zutaten. ' * 4,
                        note='Druck-Endmarke-' + day['date'] + '-' + option['type_code'],
                        components=['Basmatireis mit gerösteten Kürbiskernen', 'Broccoli und bunte Rüebli', 'Kräuter-Joghurt-Dip'],
                        allergens=[{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}, {'code': 'NUTS', 'name': 'Schalenfrüchte', 'presence': 'may_contain'}],
                        allergen_review_status='not_checked',
                    )
    _save(admin_app.extensions['cafeteria_db'], profile, values)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = browser.new_context(base_url=live_server, viewport={'width': 1440, 'height': 1100})
    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
    try:
        page = context.new_page()
        response = page.goto(f'/admin/{family}/preview/print?week={DAY}')
        assert response is not None and response.status == 200
        page.evaluate('document.fonts.ready')
        assert page.locator('img').evaluate_all('els => els.every(el => el.complete && el.naturalWidth > 0)')
        assert page.locator('[onclick], [style]').count() == 0
        page.evaluate('window.print = () => { window.didPrint = true; }')
        page.locator('#week-print-button').click()
        page.wait_for_function('window.didPrint === true')
        page.emulate_media(media='print')
        geometry = page.locator('.week-print-sheet').first.bounding_box()
        assert geometry is not None and abs(geometry['width'] - 210 / 25.4 * 96) < 1
        assert page.locator('td').evaluate_all('els => els.every(el => el.scrollWidth <= el.clientWidth + 1 && el.scrollHeight <= el.clientHeight + 1)')
        if profile == 'staff_guest':
            assert '11.00 CHF' in page.locator('.week-print-cost-footer').inner_text()
            assert '16.60 CHF' in page.locator('.week-print-cost-footer').inner_text()
            assert page.locator('.week-print-cost').count() == 0
        else:
            assert page.locator('.week-print-sheet').count() == 2
        artifact = f'{family}-{"dense" if dense else "normal"}'
        page.pdf(path=str(tmp_path / f'{artifact}.pdf'), prefer_css_page_size=True, print_background=True)
        page.screenshot(path=str(tmp_path / f'{artifact}.png'), full_page=True)
        assert (tmp_path / f'{artifact}.pdf').read_bytes().startswith(b'%PDF-')
        page.emulate_media(media='screen')
        for width, height in [(390, 844), (768, 1024), (800, 1280), (1024, 768), (1280, 800)]:
            page.set_viewport_size({'width': width, 'height': height})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert page.locator('.week-print-tools a, .week-print-tools button').evaluate_all(
                'els => els.every(el => el.getBoundingClientRect().height >= 44)'
            )
    finally:
        context.close()
