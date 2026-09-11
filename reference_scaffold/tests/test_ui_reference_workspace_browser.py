"""Browser evidence for MP-UI-REF-WORKSPACE week reference grids."""
from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine, text

from cafeteria import roles
from cafeteria.display_settings import DEFAULT_ADMIN_DISPLAY, set_admin_display
from cafeteria.workflow_partial_store import persist_week_header
from test_admin_ux_browser import live_server, page_context  # noqa: F401
from datetime import date

from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login, _overview_csrf, _scope, _session_actor_id
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080))
FAMILIES = ('cafeteria', 'patienten')
PROFILE_BY_FAMILY = {'cafeteria': 'staff_guest', 'patienten': 'patient'}
SLOT_COUNT = {'cafeteria': 10, 'patienten': 28}


def _goto(page: Page, family: str) -> None:
    response = page.goto(f'/admin/{family}?week={DAY}')
    assert response is not None and response.status == 200
    page.evaluate('document.fonts.ready')


def _assert_no_overflow(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('[style], [onclick], script:not([src])').count() == 0


def _card_dimensions(page: Page) -> list[dict[str, float]]:
    return page.locator('.menu-slot').evaluate_all('''elements => elements.map(element => {
        const box = element.getBoundingClientRect();
        return {height: box.height, width: box.width};
    })''')


def _dense_values(profile: str) -> dict:
    values = deepcopy(_staff_values() if profile == 'staff_guest' else _patient_values())
    for day in values['days']:
        for service in day['services']:
            for option in service['options']:
                option.setdefault('title', 'Gericht')
                option.setdefault('components', ['Gemüse'])
                if profile == 'staff_guest':
                    option.setdefault('internal_rappen', 950)
                    option.setdefault('external_rappen', 1450)
    return values


def _longtext_values(profile: str) -> dict:
    values = _dense_values(profile)
    last = values['days'][-1]['services'][-1]['options'][-1]
    last['title'] = 'Langtext-Menükarte mit vollständig sichtbarem Titel'
    last['components'] = ['Reis', 'Zucchetti', 'Frisch zubereitet mit saisonalem Gemüse. ' * 5]
    last['note'] = 'Vollständiger langer Rezepturhinweis bleibt sichtbar. ' * 8
    last['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    last['allergen_review_status'] = 'not_checked'
    return values


@pytest.mark.parametrize('family', FAMILIES)
def test_workspace_page_header_and_layout_variant(page_context: Page, family: str) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 1440, 'height': 900})
    _goto(page, family)
    expect(page.locator('main')).to_have_attribute('data-layout', 'workspace')
    title = 'Cafeteria-Plan bearbeiten' if family == 'cafeteria' else 'Patientenplan bearbeiten'
    expect(page.get_by_role('heading', level=1, name=title)).to_be_visible()
    expect(page.locator('.page-breadcrumb')).to_contain_text('Wochenpläne')
    expect(page.locator('.page-header-subtitle')).to_contain_text('KW 36')
    expect(page.locator('.page-header-subtitle')).to_contain_text('Menükarten')
    expect(page.get_by_role('link', name='Wochenangaben prüfen').first).to_be_visible()
    expect(page.locator('.admin-week-review-link')).to_be_visible()
    expect(page.locator('.status-pill')).to_have_attribute('data-status', 'empty')
    expect(page.locator('.status-pill .badge[data-status]')).to_be_visible()


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize(('width', 'height'), VIEWPORTS)
@pytest.mark.parametrize('state', ('empty', 'ready'))
def test_workspace_states_without_document_overflow(
    page_context: Page, admin_app: Flask, family: str, width: int, height: int, state: str,  # noqa: F811
    tmp_path: Path,
) -> None:
    profile = PROFILE_BY_FAMILY[family]
    if state == 'ready':
        _save_reviewed(admin_app.extensions['cafeteria_db'], profile, _dense_values(profile))
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    _goto(page, family)
    expect(page.locator('main')).to_have_attribute('data-status', state)
    assert page.locator('.menu-slot').count() == SLOT_COUNT[family]
    _assert_no_overflow(page)
    page.screenshot(path=str(tmp_path / f'{family}-{state}-{width}x{height}.png'), full_page=True)


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 900)))
def test_workspace_dense_week_cards_share_geometry(
    page_context: Page, admin_app: Flask, family: str, width: int, height: int,  # noqa: F811
) -> None:
    profile = PROFILE_BY_FAMILY[family]
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, _dense_values(profile))
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    _goto(page, family)
    dimensions = _card_dimensions(page)
    assert len(dimensions) == SLOT_COUNT[family]
    for axis in ('height', 'width'):
        sizes = [item[axis] for item in dimensions]
        assert max(sizes) - min(sizes) <= 1, (family, width, axis, sizes)
    _assert_no_overflow(page)


@pytest.mark.parametrize('family', FAMILIES)
def test_workspace_longtext_remains_readable(page_context: Page, admin_app: Flask, family: str) -> None:  # noqa: F811
    profile = PROFILE_BY_FAMILY[family]
    values = _longtext_values(profile)
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, values)
    page = page_context
    page.set_viewport_size({'width': 390, 'height': 844})
    _goto(page, family)
    card = page.locator('.menu-slot').last
    assert values['days'][-1]['services'][-1]['options'][-1]['note'].strip() in card.inner_text()
    expect(card.locator('h3')).to_contain_text('Langtext-Menükarte')
    _assert_no_overflow(page)


@pytest.mark.parametrize('family', FAMILIES)
def test_workspace_publish_dialog_escape_returns_focus(page_context: Page, admin_app: Flask, family: str) -> None:  # noqa: F811
    profile = PROFILE_BY_FAMILY[family]
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, _dense_values(profile))
    page = page_context
    page.set_viewport_size({'width': 1440, 'height': 900})
    _goto(page, family)
    trigger = page.locator('[data-bs-target="#week-publish-modal"]')
    expect(trigger).to_be_enabled()
    trigger.click()
    modal = page.get_by_role('dialog')
    expect(modal).to_be_visible()
    page.keyboard.press('Escape')
    expect(modal).to_be_hidden()
    expect(trigger).to_be_focused()


@pytest.mark.parametrize('family', FAMILIES)
def test_workspace_publish_dialog_nojs_form_fields(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine, family: str,  # noqa: F811
) -> None:
    profile = PROFILE_BY_FAMILY[family]
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, _dense_values(profile))
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = browser.new_context(base_url=live_server, java_script_enabled=False)
    try:
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
        page = context.new_page()
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        form = page.locator(f'form[action="/admin/{family}/publish"]')
        assert form.locator('input[name]').evaluate_all('fields => fields.map(field => field.name)') == [
            '_csrf', 'week', 'row_version',
        ]
        _assert_no_overflow(page)
    finally:
        context.close()


@pytest.mark.parametrize('family', FAMILIES)
def test_workspace_header_conflict_nojs_returns_409(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine, family: str,  # noqa: F811
) -> None:
    profile = PROFILE_BY_FAMILY[family]
    _save_reviewed(admin_app.extensions['cafeteria_db'], profile, _dense_values(profile))
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, _session_actor_id(client), profile)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = browser.new_context(base_url=live_server, java_script_enabled=False)
    try:
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
        page = context.new_page()
        page.goto(f'/admin/{family}?week={DAY}')
        header = page.locator(f'form[action="/admin/{family}/header"]')
        stale_version = header.locator('[name="row_version"]').input_value()
        persist_week_header(
            admin_engine, scope, date.fromisoformat(DAY),
            {'title': 'Konkurrierende Version', 'shared_note': ''}, int(stale_version),
        )
        header.locator('[name="title"]').fill('Ungespeicherte Eingabe')
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            header.get_by_role('button', name='Wochenangaben speichern').click()
        assert saved.value.status == 409
    finally:
        context.close()


def test_workspace_read_only_post_is_403(admin_app: Flask, admin_engine: Engine, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'draft.read'})
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Editor'])
    assert client.get(f'/admin/cafeteria?week={DAY}').status_code == 200
    response = client.post('/admin/cafeteria/header', data={
        '_csrf': _overview_csrf(client),
        'week': DAY,
        'row_version': '0',
        'title': 'Nicht erlaubt',
        'shared_note': '',
    })
    assert response.status_code == 403


@pytest.mark.parametrize('family', FAMILIES)
def test_workspace_editor_navigation_from_slot(page_context: Page, family: str) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 1024, 'height': 768})
    _goto(page, family)
    link = page.locator('.menu-slot .btn').first
    target = urlsplit(link.get_attribute('href') or '')
    assert target.path == f'/admin/{family}/menu'
    assert parse_qs(target.query)['week'] == [DAY]
    response = page.goto(link.get_attribute('href') or '')
    assert response is not None and response.status == 200
    expect(page.locator('form[data-menu-editor]')).to_be_visible()


@pytest.mark.parametrize('family', FAMILIES)
def test_workspace_respects_menu_images_setting(
    page_context: Page, admin_engine: Engine, family: str,  # noqa: F811
) -> None:
    with admin_engine.connect() as connection:
        user_id = connection.execute(text("SELECT id FROM cafeteria.users WHERE display_name='Küche'")).scalar_one()
        authz_version = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': user_id},
        ).scalar_one()
    set_admin_display(
        admin_engine, int(user_id), int(authz_version),
        {**DEFAULT_ADMIN_DISPLAY, 'admin_menu_images': 'hide'},
    )
    profile = PROFILE_BY_FAMILY[family]
    _save_reviewed(admin_engine, profile, _dense_values(profile))
    page = page_context
    page.set_viewport_size({'width': 1440, 'height': 900})
    _goto(page, family)
    expect(page.locator('main')).to_have_attribute('data-menu-images', 'hide')
    if family == 'patienten':
        assert re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I) is None
