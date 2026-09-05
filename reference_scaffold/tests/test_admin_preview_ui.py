from __future__ import annotations

import re
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect
from sqlalchemy import Engine, text

from cafeteria.template_filters import date_long
from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('family,profile,label', [
    ('cafeteria', 'staff_guest', 'Cafeteria-Speiseplan'),
    ('patienten', 'patient', 'Patienten-Speiseplan'),
])
@pytest.mark.parametrize('viewport', [(390, 844), (1440, 1100)])
def test_preview_preserves_saved_week_and_uses_readable_responsive_grid(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, label: str, viewport: tuple[int, int], tmp_path: Path,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    closed = values['days'][-1]['services'][-1]
    closed.update(service_state='closed', notice='Feiertag – Küche geschlossen')
    _save(admin_app.extensions['cafeteria_db'], profile, values)
    options = [
        option for day in values['days'] for service in day['services']
        if service['service_state'] == 'open'
        for option in service['options']
    ]
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = browser.new_context(
        base_url=live_server, java_script_enabled=False,
        viewport={'width': viewport[0], 'height': viewport[1]},
    )
    try:
        context.add_cookies([{
            'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True,
        }])
        page = context.new_page()
        for state, translated in (
            ('ready', 'Bereit'), ('published', 'Publiziert'),
            ('archived', 'Archiviert'), ('draft', 'Entwurf'),
        ):
            with admin_engine.begin() as connection:
                connection.execute(
                    text('UPDATE cafeteria.menu_weeks SET workflow_state=:state'), {'state': state},
                )
            response = page.goto(f'/admin/{family}/preview?week={DAY}')
            assert response is not None and response.status == 200
            assert response.headers['cache-control'] == 'no-store'
            assert page.locator('[data-preview]').get_attribute('data-workflow-state') == state
            expect(page.locator('.preview-saved')).to_have_text(
                f'Zuletzt gespeicherter Stand · {translated}'
            )
            assert page.locator('.preview-option h5').all_text_contents() == [
                option['title'] for option in options
            ]

        expect(page.locator('.preview-banner[role="status"]')).to_have_text('PREVIEW')
        expect(page.get_by_role('heading', level=1)).to_have_text(f'Vorschau · {label}')
        expect(page.locator('.preview-context')).to_have_text(
            'KW 36 / 2026 · Woche ab 31. August 2026'
        )
        expect(page.get_by_role('heading', level=2)).to_have_text(values['title'])
        expect(page.locator('.shared-note')).to_have_text(values['shared_note'])
        assert page.locator('[data-preview]').get_attribute('data-preview') == 'last-saved'
        assert page.locator('[data-preview]').get_attribute('data-profile') == profile
        assert page.locator('[data-preview]').get_attribute('data-week') == DAY
        assert page.locator('.preview-day > h3').all_text_contents() == [
            date_long(day['date']) for day in values['days']
        ]
        assert page.locator('.preview-service > h4').all_text_contents() == [
            'Mittagessen' if service['meal_code'] == 'LUNCH' else 'Abendessen'
            for day in values['days'] for service in day['services']
        ]
        assert page.locator('.preview-option li').all_text_contents() == [
            component for option in options for component in option['components']
        ]
        expect(page.locator('.service-notice')).to_have_text('Feiertag – Küche geschlossen')
        if profile == 'staff_guest':
            assert page.locator('.prices').all_inner_texts() == [
                f"Mitarbeitende: {option['internal_rappen'] / 100:.2f} | "
                f"Externe: {option['external_rappen'] / 100:.2f}" for option in options
            ]
        else:
            assert not re.search(r'preis|chf|rappen|kosten|price', page.content(), re.IGNORECASE)

        assert page.locator('script, style, [style], [onclick], form, button').count() == 0
        assert page.locator('.skip-link').get_attribute('href') == '#main-content'
        assert page.locator('main#main-content.admin-preview').count() == 1
        assert page.locator('meta[name="viewport"]').get_attribute('content') == (
            'width=device-width,initial-scale=1'
        )
        assert page.evaluate(
            'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
        )
        cards = page.locator('.preview-day').evaluate_all(
            'els => els.map(el => { const r = el.getBoundingClientRect(); '
            'return {left: r.left, right: r.right, top: r.top, bottom: r.bottom}; })'
        )
        assert all(card['left'] >= 16 and card['right'] <= viewport[0] - 16 for card in cards)
        if viewport[0] < 800:
            assert all(abs(card['left'] - cards[0]['left']) < 1 for card in cards)
            assert all(cards[i + 1]['top'] > cards[i]['bottom'] for i in range(len(cards) - 1))
        else:
            assert abs(cards[0]['top'] - cards[2]['top']) < 1
            assert cards[0]['right'] < cards[1]['left'] < cards[2]['left']
            assert cards[3]['top'] > cards[0]['bottom']
        assert page.locator('.preview-option h5').first.evaluate(
            'el => parseFloat(getComputedStyle(el).fontSize) >= 16'
        )
        page.screenshot(path=str(tmp_path / f'{family}-preview-{viewport[0]}.png'),
                        full_page=True, caret='initial')
    finally:
        context.close()
