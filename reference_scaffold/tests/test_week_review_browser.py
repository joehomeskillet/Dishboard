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
CONFIRM = 'Wochenkopf und alle Ausgabehinweise als geprüft bestätigen'


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
@pytest.mark.parametrize('width', [360, 768, 1024, 1280, 1440])
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
    expect(page.get_by_role('heading', name='Wochenangaben prüfen', exact=True)).to_be_visible()
    expect(
        page.locator('main .alert-warning').filter(has_text='Für den gespeicherten Wochenkopf')
    ).to_contain_text('Noch zu prüfen')
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
    expect(confirm.locator('use')).to_have_attribute('href', re.compile(r'#tabler-check$'))
    expect(page.locator('main .btn-primary:visible')).to_have_count(1)
    expect(page.locator('.admin-list-row')).to_have_count(len(services))
    expect(page.get_by_role('list', name='Ausgabeangaben').get_by_role('listitem')).to_have_count(len(services))
    closed = sum(1 for index, _service in enumerate(services) if index % 3 == 0)
    expect(page.locator('.admin-list-status .admin-label')).to_have_count(closed)
    expect(page.locator('.admin-list-row').filter(has_text='Geöffnet')).to_have_count(0)
    expect(page.locator('#week-service-normal')).to_contain_text('geöffnet, kein Ausgabehinweis')
    box = confirm.bounding_box()
    minimum = page.evaluate("matchMedia('(pointer: coarse)').matches ? 44 : 36")
    assert box is not None and box['width'] >= minimum and box['height'] >= minimum
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
                              {'service_state': service['state'], 'notice': 'Geänderter Servicehinweis',
                               'service_start': service.get('start', ''), 'service_end': service.get('end', '')},
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


@pytest.mark.parametrize(('family', 'profile'), [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('width', [1440, 390])
def test_week_review_status_without_redundant_header(
    admin_app, admin_engine, live_server, browser, family, profile, javascript, width, tmp_path,
):
    import json

    values = _values(profile)
    _save(admin_engine, profile, values)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    scope = _scope(admin_engine, actor, profile)
    original = get_week_review(admin_engine, scope, WEEK_START)
    assert original['receipt'] is None and _audit_count(admin_engine) == 0
    observations = {}
    status_cards = []
    with browser.new_context(base_url=live_server, java_script_enabled=javascript, has_touch=width == 390,
                             viewport={'width': width, 'height': 844 if width == 390 else 900},
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        response = page.goto(_url(family))
        assert response is not None and response.status == 200
        expect(page.get_by_role('heading', name='Wochenangaben prüfen', exact=True)).to_be_visible()
        warn = page.locator('main .alert-warning').filter(has_text='Für den gespeicherten Wochenkopf')
        expect(warn).to_have_count(1)
        expect(warn).to_contain_text('Noch zu prüfen')
        expect(warn).to_contain_text('liegt keine gültige Prüfung vor')
        expect(warn).to_contain_text('Nach Änderungen ist eine erneute Prüfung erforderlich.')
        confirm = page.get_by_role('button', name=CONFIRM, exact=True)
        expect(confirm).to_have_attribute('form', 'week-review-form')
        expect(confirm).to_have_attribute('type', 'submit')
        expect(confirm).to_have_attribute('data-ui-tooltip', CONFIRM)
        expect(confirm.locator('use')).to_have_attribute('href', re.compile(r'#tabler-check$'))
        form = page.locator('#week-review-form')
        expect(form).to_have_attribute('method', 'post')
        expect(form).to_have_attribute('action', _url(family).split('?')[0])
        expected_fields = form.evaluate('form => Object.fromEntries(new FormData(form))')
        assert set(expected_fields) == {'_csrf', 'week', 'context_version'}
        assert expected_fields['_csrf'] and expected_fields['week'] == str(WEEK_START)
        assert expected_fields['context_version'] == original['token']

        for stage in ('unreviewed', 'reviewed'):
            current = get_week_review(admin_engine, scope, WEEK_START)
            assert current['context'] == original['context']
            intro = page.locator('[data-week-review-intro]')
            expect(intro).to_contain_text('Die Menüs werden einzeln geprüft.')
            expect(intro).to_contain_text('Eine Bestätigung veröffentlicht noch keinen Wochenplan.')
            expect(page.get_by_text(values['title'], exact=True)).to_be_visible()
            expect(page.get_by_text(values['shared_note'], exact=True)).to_be_visible()
            assert page.locator('main script').count() == 0
            expect(page.get_by_role('list', name='Ausgabeangaben').get_by_role('listitem')).to_have_count(
                len(original['context']['services']))
            for service in original['context']['services']:
                expect(page.get_by_text(service['notice'], exact=True)).to_be_visible()
            back = page.get_by_role('link', name='Zur Wochenübersicht', exact=True)
            expect(back).to_have_attribute('href', f'/admin/{family}?week={WEEK_START}')
            expect(back).to_be_visible()
            status_cards.append(page.locator('.admin-statusbar').count())
            _assert_layout(page)
            pointer = page.evaluate('''() => ({coarse: matchMedia('(pointer: coarse)').matches,
                anyCoarse: matchMedia('(any-pointer: coarse)').matches, touch: navigator.maxTouchPoints,
                width: innerWidth})''')
            assert pointer['coarse'] == pointer['anyCoarse'] == (width == 390)
            assert (pointer['touch'] > 0) == (width == 390) and pointer['width'] == width
            page.evaluate('window.scrollTo(0, 0)')
            page.screenshot(path=str(tmp_path / f'{family}-{javascript}-{width}-{stage}.png'), full_page=False)
            assert page.evaluate('''() => ({coarse: matchMedia('(pointer: coarse)').matches,
                anyCoarse: matchMedia('(any-pointer: coarse)').matches, touch: navigator.maxTouchPoints,
                width: innerWidth})''') == pointer
            observations[stage] = {'pointer': pointer, 'header_status_cards': status_cards[-1]}
            if stage == 'unreviewed':
                observations[stage]['confirm'] = {'text': confirm.inner_text(),
                    'aria': confirm.get_attribute('aria-label'), 'tooltip': confirm.get_attribute('data-ui-tooltip'),
                    'class': confirm.get_attribute('class'), 'box': confirm.bounding_box()}
                page.keyboard.press('Tab')
                confirm.focus()
                expect(confirm).to_be_focused()
                with page.expect_navigation(wait_until='domcontentloaded'), page.expect_response(
                    lambda result: result.request.method == 'POST' and
                    result.url == live_server + _url(family).split('?')[0]
                ) as saved:
                    page.keyboard.press('Enter')
                assert saved.value.status == 303 and saved.value.headers['location'] == _url(family)
                assert parse_qs(saved.value.request.post_data or '') == {
                    key: [value] for key, value in expected_fields.items()}
                assert _audit_count(admin_engine) == 1
                receipt = get_week_review(admin_engine, scope, WEEK_START)['receipt']
                assert receipt is not None
                status = page.locator('main [role="status"]').filter(has_text='Dieser Stand wurde von')
                expect(status).to_have_count(1)
                expect(status).to_contain_text('Geprüft')
                expect(status).to_contain_text('Wochenkopf und Ausgabeangaben für diesen gespeicherten Stand.')
                expect(status).to_contain_text('Dieser Stand wurde von ' + receipt['actor_name'])
                expect(status).to_contain_text(admin_app.jinja_env.filters['datetime_short'](receipt['occurred_at']))
                expect(confirm).to_have_count(0)
                expect(form).to_have_count(0)
                expect(warn).to_have_count(0)
        (tmp_path / 'review-status-observations.json').write_text(json.dumps(observations, indent=2))
        with admin_engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.publication_revisions')).scalar_one() == 0
            assert connection.execute(text(
                "SELECT count(*) FROM cafeteria.audit_events WHERE action='workflow.menu_reviewed'"
            )).scalar_one() == 0
        assert {'header_status_cards': status_cards, 'confirm_text': observations['unreviewed']['confirm']['text']} == {
            'header_status_cards': [0, 0], 'confirm_text': ''}, observations
