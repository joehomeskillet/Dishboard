from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect
from sqlalchemy import Engine, text

from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_routes import DATABASE_URL, _login, _payload, _scope
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('family,profile,label', [
    ('cafeteria', 'staff_guest', 'Cafeteria'), ('patienten', 'patient', 'Patienten'),
])
@pytest.mark.parametrize('viewport', [(360, 844), (1280, 1100)])
def test_copy_confirmation_is_readable_and_submits_without_javascript(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, label: str, viewport: tuple[int, int],
) -> None:
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    source = dt.date(2026, 12, 28)
    target = source + dt.timedelta(days=7)
    persist_menu_item(
        admin_app.extensions['cafeteria_db'], _scope(admin_engine, user_id, profile),
        source, source.isoformat(), 'LUNCH', 'MENU_1', _payload(staff=profile == 'staff_guest'), 0,
    )
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
        copy_url = f'/admin/{family}/copy?week={target.isoformat()}'
        response = page.goto(copy_url)
        assert response is not None and response.status == 200
        assert page.locator('meta[name="viewport"]').get_attribute('content') == (
            'width=device-width,initial-scale=1'
        )
        expect(page.get_by_role('heading', name='Vorwoche kopieren', exact=True)).to_be_visible()
        expect(page.locator('.admin-copy-profile')).to_have_text(label)
        expect(page.locator('#copy-description')).to_have_text(
            'Woche vom 28.12.2026 in die leere Woche vom 04.01.2027 kopieren.'
        )
        expect(page.locator('.admin-copy-weeks')).to_contain_text('KW 53 / 2026')
        expect(page.locator('.admin-copy-target')).to_contain_text('KW 1 / 2027')
        assert page.locator('main').get_attribute('data-profile') == profile
        assert page.locator('main').get_attribute('data-source-week') == source.isoformat()
        assert page.locator('main').get_attribute('data-target-week') == target.isoformat()
        assert page.locator('script:not([src]), style, [style], [onclick], [onsubmit]').count() == 0
        assert page.locator('link[href$="/app.css"]').count() == 0
        assert page.locator('main').count() == 1
        assert page.locator('body').evaluate(
            "el => getComputedStyle(el).fontFamily.includes('Fira Sans')"
        )
        assert page.locator('.admin-copy-weeks').evaluate(
            "el => getComputedStyle(el).display === 'flex'"
        )
        assert page.evaluate(
            'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
        )
        if profile == 'patient':
            assert not re.search(r'preis|chf|rappen|kosten|price', page.content(), re.IGNORECASE)

        form = page.locator(f'form[action="/admin/{family}/copy"]')
        fields = form.evaluate('form => Object.fromEntries(new FormData(form))')
        assert set(fields) == {'_csrf', 'source_week', 'target_week', 'target_row_version'}
        assert fields['_csrf']
        assert fields['source_week'] == source.isoformat()
        assert fields['target_week'] == target.isoformat()
        assert fields['target_row_version'] == '0'
        assert form.locator('input[type="hidden"]').count() == 4
        primary = form.get_by_role('button', name='Vorwoche kopieren', exact=True)
        cancel = form.get_by_role('link', name='Zurück zur Wochenübersicht', exact=True)
        for action in (primary, cancel):
            box = action.bounding_box()
            assert box is not None and box['width'] >= 48 and box['height'] >= 48
        if proof_dir := os.environ.get('COPY_TABLER_PROOF_DIR'):
            directory = Path(proof_dir)
            directory.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(directory / f'copy-{family}-{viewport[0]}.png'), full_page=True)
        cancel.click()
        page.wait_for_url(f'**/admin/{family}?week={target.isoformat()}')
        with admin_engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 1

        page.goto(copy_url)
        page.keyboard.press('Tab')
        expect(page.locator('.skip-link')).to_be_focused()
        page.keyboard.press('Enter')
        page.keyboard.press('Tab')
        expect(primary).to_be_focused()
        assert primary.evaluate("el => getComputedStyle(el).outlineStyle !== 'none'")
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            page.keyboard.press('Enter')
        assert saved.value.status == 303
        page.wait_for_url(f'**/admin/{family}?week={target.isoformat()}')
        expect(page.locator(
            f'.menu-slot[data-day="{target.isoformat()}"][data-meal="LUNCH"]'
            '[data-option="MENU_1"] h3',
        )).to_have_text('Kartoffelgratin')
        with admin_engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 2
    finally:
        context.close()
