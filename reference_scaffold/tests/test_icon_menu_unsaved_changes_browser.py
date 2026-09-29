"""D8 / UI-18: real unsaved-change dialogs, native saves and return context."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_ux_browser import live_server
from test_admin_workflow_routes import DAY, WEEK, _login, _payload, _scope
from test_menu_template_binding_db import stored_state
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server']

TITLE = 'D8 Kräuterteller'
PROFILES = [('cafeteria', 'staff_guest'), ('patienten', 'patient')]
NAVIGATIONS = ['cancel', 'week-link', 'history-back']


@pytest.fixture(params=[(*profile, js) for profile in PROFILES for js in (True, False)],
                ids=['cafeteria-js', 'cafeteria-nojs', 'patienten-js', 'patienten-nojs'])
def menu_session(request, browser, live_server, admin_app, admin_engine, tmp_path):
    family, profile, javascript = request.param
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, actor, profile)
    payload = {**_payload(staff=family == 'cafeteria'), 'title': TITLE}
    assert persist_menu_item(admin_engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 0) == 1
    cookie = client.get_cookie('session')
    assert cookie is not None
    collection = f'/admin/{family}/menues?{urlencode({"q": TITLE})}'
    evidence = {'case': request.node.name, 'family': family, 'javascript': javascript, 'dialogs': [], 'writes': [],
                'documents': [], 'collection': collection}
    with browser.new_context(base_url=live_server, java_script_enabled=javascript,
                             viewport={'width': 1440, 'height': 900}, has_touch=False,
                             locale='de-CH', reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        response = page.goto(collection, wait_until='networkidle')
        assert response is not None and response.status == 200
        expect(page.locator('[name="q"]')).to_have_value(TITLE)
        expect(page.locator('.profile-tabs [aria-current="true"]')).to_have_attribute(
            'href', collection)
        page.locator(f'a[href*="/admin/{family}/menu?"]:visible').first.click()
        page.wait_for_load_state('networkidle')
        expect(page.get_by_label('Menüname', exact=True)).to_have_value(TITLE)
        assert page.evaluate("matchMedia('(pointer: fine)').matches")
        evidence['editor'] = page.url

        def observe_request(event):
            if event.method not in ('GET', 'HEAD', 'OPTIONS'):
                evidence['writes'].append({'method': event.method, 'url': event.url})
            if event.is_navigation_request() and event.frame == page.main_frame:
                evidence['documents'].append({'method': event.method, 'url': event.url})

        page.on('request', observe_request)
        try:
            yield page, family, javascript, evidence
        finally:
            evidence['final_url'] = page.url
            (tmp_path / 'd8-evidence.json').write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')


def _navigate(page, navigation):
    if navigation == 'history-back':
        # Real session-history traversal; no synthetic beforeunload dispatch.
        page.evaluate('history.back()')
    elif navigation == 'cancel':
        page.get_by_role('link', name='Abbrechen', exact=True).click()
    else:
        page.get_by_role('link', name='Wochenplan', exact=True).last.click()


def _expect_destination(page, family, navigation, evidence):
    target = evidence['collection'] if navigation == 'history-back' else f'/admin/{family}?week={DAY}'
    expect(page).to_have_url(urljoin(evidence['editor'], target))
    page.wait_for_load_state('networkidle')


@pytest.mark.parametrize('navigation', NAVIGATIONS)
def test_unsaved_navigation_stay_or_leave_without_mutation(
    menu_session, admin_engine, tmp_path, navigation,
):
    page, family, javascript, evidence = menu_session
    before = stored_state(admin_engine)
    title = page.get_by_label('Menüname', exact=True)
    note = page.get_by_label('Hinweis (auf dem Speiseplan sichtbar)', exact=True)
    title.fill('D8 ungespeicherter Titel')
    output_texts = page.locator('#sec-output-texts')
    if output_texts.get_attribute('open') is None:
        output_texts.locator('summary').click()
    note.fill('D8 ungespeicherter Hinweis')
    leave = False

    def answer(dialog):
        evidence['dialogs'].append({'type': dialog.type, 'decision': 'leave' if leave else 'stay'})
        dialog.accept() if leave else dialog.dismiss()

    page.on('dialog', answer)
    if javascript:
        with page.expect_event('dialog', timeout=5000):
            _navigate(page, navigation)
        assert evidence['dialogs'] == [{'type': 'beforeunload', 'decision': 'stay'}]
        expect(page).to_have_url(evidence['editor'])
        expect(title).to_have_value('D8 ungespeicherter Titel')
        expect(note).to_have_value('D8 ungespeicherter Hinweis')
        assert evidence['documents'] == []
        assert evidence['writes'] == []
        assert stored_state(admin_engine) == before
        page.screenshot(path=str(tmp_path / 'unsaved-stay.png'), full_page=True)
        leave = True
        with page.expect_event('dialog', timeout=5000):
            _navigate(page, navigation)
        assert evidence['dialogs'] == [
            {'type': 'beforeunload', 'decision': 'stay'},
            {'type': 'beforeunload', 'decision': 'leave'},
        ]
    else:
        # Native NoJS control: navigation discards the draft without a guard.
        _navigate(page, navigation)
    _expect_destination(page, family, navigation, evidence)
    if not javascript:
        assert evidence['dialogs'] == []
    assert evidence['writes'] == []
    assert stored_state(admin_engine) == before
    evidence['database_unchanged_after_navigation'] = True
    response = page.goto(evidence['editor'], wait_until='networkidle')
    assert response is not None and response.status == 200
    expect(title).to_have_value(TITLE)
    expect(note).to_have_value('')
    assert stored_state(admin_engine) == before


@pytest.mark.parametrize('navigation', ['cancel', 'week-link'])
def test_successful_save_clears_navigation_guard(menu_session, admin_engine, navigation):
    page, family, _, evidence = menu_session

    def unexpected_dialog(dialog):
        evidence['dialogs'].append(dialog.type)
        dialog.dismiss()

    page.on('dialog', unexpected_dialog)
    page.get_by_label('Menüname', exact=True).fill('D8 erfolgreich gespeichert')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        page.get_by_role('button', name='Menü speichern', exact=True).click()
    assert saved.value.status == 303
    page.wait_for_load_state('networkidle')
    expect(page.get_by_label('Menüname', exact=True)).to_have_value('D8 erfolgreich gespeichert')
    expect(page.locator('form[data-menu-editor] [name="row_version"]')).to_have_value('2')
    with admin_engine.connect() as connection:
        assert tuple(connection.execute(text(
            'SELECT title, row_version FROM cafeteria.menu_items'
        )).one()) == ('D8 erfolgreich gespeichert', 2)
    assert evidence['dialogs'] == []
    assert evidence['writes'] == [{'method': 'POST', 'url': evidence['editor'].split('?')[0]}]
    after_save = stored_state(admin_engine)
    _navigate(page, navigation)
    _expect_destination(page, family, navigation, evidence)
    assert evidence['dialogs'] == []
    assert len(evidence['writes']) == 1
    assert stored_state(admin_engine) == after_save
    evidence['saved_navigation_without_dialog_or_extra_mutation'] = True


@pytest.mark.parametrize('navigation', NAVIGATIONS)
def test_collection_return_context_expected_current_behavior(
    menu_session, admin_engine, navigation,
):
    """Characterize D8 delta: links lose q; browser Back preserves q and profile."""
    page, family, _, evidence = menu_session
    before = stored_state(admin_engine)
    _navigate(page, navigation)
    _expect_destination(page, family, navigation, evidence)
    returned = urlsplit(page.url)
    if navigation == 'history-back':
        assert returned.path == f'/admin/{family}/menues'
        assert parse_qs(returned.query) == {'q': [TITLE]}
        expect(page.locator('[name="q"]')).to_have_value(TITLE)
        expect(page.locator('.profile-tabs [aria-current="true"]')).to_have_attribute(
            'href', evidence['collection'])
        evidence['filter_return'] = 'q and profile retained by browser history'
    else:
        # Expected current behavior, NOT acceptance of filter-context preservation.
        assert returned.path == f'/admin/{family}'
        assert parse_qs(returned.query) == {'week': [DAY]}
        evidence['filter_return'] = 'DELTA: links return to week; q/collection context lost'
    assert evidence['writes'] == []
    assert stored_state(admin_engine) == before
