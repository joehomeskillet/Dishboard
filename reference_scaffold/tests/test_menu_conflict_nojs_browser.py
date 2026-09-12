"""A native no-JS conflict form must not silently adopt the concurrent version."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect
from sqlalchemy import Engine, text

from test_admin_ux_browser import _submit_menu, live_server  # noqa: F401
from test_admin_workflow_routes import DATABASE_URL, DAY, _hidden, _login, _menu_form
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


def _stored_state(engine: Engine) -> dict[str, tuple[str, ...]]:
    with engine.connect() as connection:
        return {table: tuple(connection.execute(text(
            f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY id'
        )).scalars()) for table in ('menu_items', 'menu_weeks', 'audit_events')}


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_conflict_form_resubmit_without_javascript_keeps_original_cas(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    action = f'/admin/{family}/menu'
    editor = f'{action}?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
    initial = client.get(editor)
    assert initial.status_code == 200
    csrf = _hidden(initial.get_data(as_text=True), '_csrf', form_action=action)
    prices = {'internal_chf': '9.50', 'external_chf': '14.50'} if family == 'cafeteria' else {}
    # Native forms retain visible optional rows; seed valid rows instead of JS-stripped blanks.
    metadata = {'component_public_id': '', 'component_text': 'Gemüse',
                'origin_ingredient': 'Gemüse', 'origin_country_code': 'CH'}
    assert client.post(action, data=_menu_form(
        _csrf=csrf, title='Ursprünglicher Titel', **prices, **metadata,
    )).status_code == 303
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = browser.new_context(base_url=live_server, java_script_enabled=False)
    try:
        context.add_cookies([{
            'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True,
        }])
        page = context.new_page()
        opened = page.goto(editor)
        assert opened is not None and opened.status == 200
        form = page.locator('form[data-menu-editor]')
        version = form.locator('[name="row_version"]')
        expect(version).to_have_value('1')
        expect(page.get_by_label('Menüname', exact=True)).to_have_value('Ursprünglicher Titel')
        original_csrf = form.locator('[name="_csrf"]').input_value()

        # Editor B saves after A has opened the original form, through the real route.
        assert client.post(action, data=_menu_form(
            _csrf=csrf, row_version='1', title='Zwischenzeitlich von B gespeichert', **prices, **metadata,
        )).status_code == 303
        before = _stored_state(admin_engine)
        item = json.loads(before['menu_items'][0])
        assert (item['row_version'], item['title']) == (2, 'Zwischenzeitlich von B gespeichert')
        navigations: list[tuple[str, str]] = []
        page.on('request', lambda request: navigations.append((request.method, urlsplit(request.url).path))
                if request.is_navigation_request() else None)
        page.get_by_label('Menüname', exact=True).fill('Ungespeicherter Titel von A')
        first = _submit_menu(page, 409)
        assert first['row_version'] == ['1'] and first['_csrf'] == [original_csrf]
        expect(page.locator('.error-region[role="alert"]')).to_be_visible()
        expect(page.get_by_label('Menüname', exact=True)).to_have_value('Ungespeicherter Titel von A')
        assert _stored_state(admin_engine) == before
        returned_version = version.input_value()

        # Click the returned form unchanged: no GET, reload, JS, or hidden-field repair.
        second = _submit_menu(page, 409)
        assert returned_version == '1'
        assert second['row_version'] == ['1']
        assert second['title'] == ['Ungespeicherter Titel von A']
        expect(version).to_have_value('1')
        assert navigations == [('POST', action), ('POST', action)]
        assert _stored_state(admin_engine) == before

        fresh = page.goto(editor)
        assert fresh is not None and fresh.status == 200
        expect(version).to_have_value('2')
        expect(page.get_by_label('Menüname', exact=True)).to_have_value('Zwischenzeitlich von B gespeichert')
        assert _stored_state(admin_engine) == before
    finally:
        context.close()
