from __future__ import annotations

# ruff: noqa: F811

import os
import re
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from flask import Flask
from playwright.sync_api import Page, expect
from sqlalchemy import Engine, text

from cafeteria import roles
from cafeteria.admin import week_review_routes  # noqa: F401
from cafeteria.workflow_partial_store import persist_service_state, persist_week_header
from cafeteria.workflow_review_context import get_week_review
from test_admin_workflow_db import WEEK_START, _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, _login, _scope
from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
CONFIRM = 'Wochenkopf und alle Servicehinweise als geprüft bestätigen'


def _values(profile: str, *, closed: bool = False) -> dict:
    values = _patient_values() if profile == 'patient' else _staff_values()
    values['title'] = 'Gespeicherter Wochenkopf <script> mit vollständiger Prüfung'
    values['shared_note'] = 'Wochenhinweis: ' + 'Bitte alle Angaben sorgfältig lesen. ' * 8 + 'WOCHEN-ENDE'
    for index, service in enumerate(service for day in values['days'] for service in day['services']):
        sentinel = chr(ord('A') + index)
        service['notice'] = f'SERVICE-{sentinel}: ' + 'Vollständiger gespeicherter Hinweis. ' * 6 + f' ENDE-{sentinel}'
        if closed or index % 3 == 0:
            service['service_state'] = 'closed'
    return values


def _url(family: str) -> str:
    return f'/admin/{family}/wochen/pruefung?week={WEEK_START}'


def _audit_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(text(
            "SELECT count(*) FROM cafeteria.audit_events WHERE action='workflow.week_context_reviewed'"
        )).scalar_one()


def _capture(page: Page, name: str) -> None:
    if directory := os.environ.get('WEEK_REVIEW_PROOF_DIR'):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(path / f'{name}.png'), full_page=True)


def _assert_layout(page: Page) -> None:
    assert page.locator('main').count() == 1
    assert page.locator('link[href$="/app.css"], script:not([src]), [style]').count() == 0
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('main dd').evaluate_all('''elements => elements.every(el => {
        const box = el.getBoundingClientRect();
        const range = document.createRange(); range.selectNodeContents(el);
        return [...range.getClientRects()].every(rect =>
            rect.left >= box.left - 1 && rect.right <= box.right + 1 &&
            rect.top >= box.top - 1 && rect.bottom <= box.bottom + 1);
    })''')


@pytest.mark.parametrize(('family', 'profile'), [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width', [360, 768, 1024, 1280])
def test_real_week_review_saved_content_and_explicit_confirmation(
    page_context: Page, admin_app: Flask, admin_engine: Engine, family: str, profile: str, width: int,
) -> None:
    page = page_context
    page.set_viewport_size({'width': width, 'height': 1024})
    values = _values(profile)
    _save(admin_engine, profile, values)
    response = page.goto(_url(family))
    assert response is not None and response.status == 200
    assert response.headers['cache-control'] == 'no-store'
    expect(page.get_by_role('heading', name='Wochenkopf und Servicehinweise prüfen')).to_be_visible()
    for value in [values['title'], values['shared_note']]:
        expect(page.get_by_text(value, exact=True)).to_be_visible()
    services = [service for day in values['days'] for service in day['services']]
    assert page.locator('main h3').count() == len(services)
    for service in services:
        expect(page.get_by_text(service['notice'], exact=True)).to_be_visible()
    assert page.locator('main script').count() == 0
    if profile == 'patient':
        assert not re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I)
    _assert_layout(page)
    confirm = page.get_by_role('button', name=CONFIRM)
    box = confirm.bounding_box()
    assert box is not None and box['width'] >= 48 and box['height'] >= 48
    confirm.focus()
    expect(confirm).to_be_focused()
    assert confirm.evaluate("el => getComputedStyle(el).outlineStyle !== 'none'")
    assert _audit_count(admin_engine) == 0
    _capture(page, f'{family}-{width}-open')
    with page.expect_response(lambda result: result.request.method == 'POST') as saved:
        page.keyboard.press('Enter')
    assert saved.value.status == 303
    assert saved.value.headers['location'] == _url(family)
    fields = parse_qs(saved.value.request.post_data or '')
    assert set(fields) == {'_csrf', 'week', 'context_version'}
    assert fields['_csrf'] and fields['week'] == [str(WEEK_START)]
    page.wait_for_url('**' + _url(family))
    expect(page.get_by_role('status')).to_contain_text('Dieser Stand wurde von Küche')
    expect(confirm).to_have_count(0)
    assert _audit_count(admin_engine) == 1
    with admin_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.publication_revisions')).scalar_one() == 0
        receipt = connection.execute(text(
            "SELECT profile_code, details->>'reviewed_token' FROM cafeteria.audit_events "
            "WHERE action='workflow.week_context_reviewed'"
        )).one()
        assert tuple(receipt) == (profile, fields['context_version'][0])
    _assert_layout(page)
    _capture(page, f'{family}-{width}-receipt')


@pytest.mark.parametrize(('family', 'profile'), [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('changed_field', ['header', 'service'])
def test_changed_saved_context_refuses_old_browser_token(
    page_context: Page, admin_engine: Engine, family: str, profile: str, changed_field: str,
) -> None:
    page = page_context
    values = _values(profile)
    version = _save(admin_engine, profile, values)
    page.goto(_url(family))
    form = page.locator('form:has(input[name="context_version"])')
    fields = form.evaluate('form => Object.fromEntries(new FormData(form))')
    path = _url(family).split('?')[0]
    assert page.context.request.post(path, form={**fields, '_csrf': ''}).status == 400
    with admin_engine.connect() as connection:
        actor = connection.execute(text("SELECT id FROM cafeteria.users WHERE display_name='Küche'")).scalar_one()
    scope = _scope(admin_engine, actor, profile)
    if changed_field == 'header':
        persist_week_header(admin_engine, scope, WEEK_START,
                            {'title': 'Geänderter Wochenkopf', 'shared_note': values['shared_note']}, version)
    else:
        service = get_week_review(admin_engine, scope, WEEK_START)['context']['services'][0]
        persist_service_state(admin_engine, scope, WEEK_START, service['date'], service['meal'],
                              {'service_state': service['state'], 'notice': 'Geänderter Servicehinweis'},
                              service['row_version'])
    with page.expect_response(lambda result: result.request.method == 'POST') as saved:
        page.get_by_role('button', name=CONFIRM).click()
    assert saved.value.status == 409
    assert _audit_count(admin_engine) == 0
    assert get_week_review(admin_engine, scope, WEEK_START)['receipt'] is None


@pytest.mark.parametrize(('family', 'profile'), [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_closed_week_without_menus_can_be_reviewed_and_read_only_has_no_action(
    page_context: Page, admin_app: Flask, admin_engine: Engine,
    family: str, profile: str, monkeypatch: pytest.MonkeyPatch, live_server: str,
) -> None:
    page = page_context
    page.set_viewport_size({'width': 360, 'height': 1024})
    _save(admin_engine, profile, _values(profile, closed=True))
    with admin_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 0
    # No shipped role is read-only: exercise the existing draft.read capability boundary.
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'draft.read'})
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Editor'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    page.context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
    page.goto(_url(family))
    expect(page.get_by_role('status')).to_contain_text('Bearbeitungsrechte')
    expect(page.get_by_role('button', name=CONFIRM)).to_have_count(0)
    assert page.locator('input[name="context_version"]').count() == 0
    assert _audit_count(admin_engine) == 0
    _assert_layout(page)
    _capture(page, f'{family}-360-read-only-closed')
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    page.context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': page.url}])
    page.goto(_url(family))
    with page.expect_response(lambda result: result.request.method == 'POST') as saved:
        page.get_by_role('button', name=CONFIRM).click()
    assert saved.value.status == 303
    expect(page.get_by_role('status')).to_contain_text('Dieser Stand wurde von Küche')
    assert _audit_count(admin_engine) == 1
