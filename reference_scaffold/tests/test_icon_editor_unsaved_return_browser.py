"""V3-5 / UI-18: real dirty-leave, saved navigation and list-context evidence."""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria import component_catalog_store, recipe_store
from cafeteria.admin import cookbook_routes
from test_admin_ux_browser import live_server
from test_admin_workflow_routes import _login, _scope
from test_master_data_browser import master_server
from test_master_data_db import signed_in
from test_master_data_routes import (
    app_engine, b3, create as create_food, installed_pg16, pg16, seeded_pg16,
    snapshot as food_snapshot,
)
from test_recipe_routes import create as create_recipe
from test_recipe_store_db import snapshot as recipe_snapshot
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = [
    'admin_app', 'admin_engine', 'app_engine', 'b3', 'browser', 'installed_pg16',
    'live_server', 'master_server', 'pg16', 'seeded_pg16',
]

TITLE = 'V3-5 Kräuter'
CASES = [
    ('recipe', None, 1440), ('recipe', None, 390), ('ingredient', None, 1440),
    ('cookbook', None, 1440), ('component', 'cafeteria', 1440),
    ('component', 'patienten', 1440),
]


def _database_state(owner):
    state = recipe_snapshot(owner) | food_snapshot(owner)
    with owner.connect() as connection:
        for table in ('menu_components', 'component_labels', 'component_allergens'):
            state[table] = connection.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY 1'
            )).all()
    return state


@pytest.fixture(params=[(*case, js) for case in CASES for js in (True, False)], ids=[
    f'{kind}-{family or "shared"}-{width}-{"js" if js else "nojs"}'
    for kind, family, width in CASES for js in (True, False)
])
def editor_session(request, browser, tmp_path):
    kind, family, width, javascript = request.param
    if kind == 'component':
        app = request.getfixturevalue('admin_app')
        owner = request.getfixturevalue('admin_engine')
        client, actor = _login(app, owner, ['Cafeteria.Admin'])
        profile = 'staff_guest' if family == 'cafeteria' else 'patient'
        row = component_catalog_store.create_component(
            owner, _scope(owner, actor, profile), 'side', TITLE, 'CH', 'current', [], [],
        )
        list_path = f'/admin/{family}/komponenten'
        editor_path = f'{list_path}/{row["public_id"]}'
        base = request.getfixturevalue('live_server')
        filter_values = {'q': TITLE, 'status': 'all', 'category': 'side'}
        return_query = {}
        form_selector = '#component-form'
    else:
        app, owner, client, actor = request.getfixturevalue('b3')
        if kind == 'recipe':
            editor_path = create_recipe(client, TITLE)
            list_path, form_selector = '/admin/rezepte', '#recipe-editor'
        elif kind == 'ingredient':
            editor_path = create_food(client, name=TITLE)
            list_path, form_selector = '/admin/grundlagen', '#food-core-form'
        else:
            cookbook_routes.register_on(app, url_prefix='/admin', endpoint_prefix='admin.')
            engine = app.extensions['cafeteria_db']
            with signed_in(engine, actor):
                row = recipe_store.create_cookbook(
                    engine, actor, name=TITLE, description='Gespeicherte Beschreibung',
                    expected_location_id=recipe_store.get_location(engine),
                )
            list_path = '/admin/kochbuecher'
            editor_path = f'{list_path}/{row.public_id}'
            form_selector = f'form[action="{editor_path}"]'
        base, _ = request.getfixturevalue('master_server')
        filter_values = {'q': TITLE, 'archived': '1'}
        return_query = {'kind': ['foods']} if kind == 'ingredient' else {}
        if kind == 'ingredient':
            filter_values['kind'] = 'foods'
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    collection = list_path + '?' + urlencode(filter_values)
    evidence = {
        'case': request.node.name, 'kind': kind, 'family': family, 'javascript': javascript,
        'width': width, 'dialogs': [], 'writes': [], 'documents': [], 'requests': [],
        'collection': collection, 'list_path': list_path, 'return_query': return_query,
        'filter_values': filter_values,
    }
    with browser.new_context(
        base_url=base, java_script_enabled=javascript, has_touch=width == 390,
        viewport={'width': width, 'height': 844 if width == 390 else 900},
        locale='de-CH', reduced_motion='reduce', service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        response = page.goto(collection, wait_until='networkidle')
        assert response is not None and response.status == 200
        expect(page.locator('[name="q"]')).to_have_value(TITLE)
        page.locator(f'a[data-semantic="actions.edit"][href="{editor_path}"]').click()
        page.wait_for_load_state('networkidle')
        expect(page).to_have_url(base + editor_path)
        field = page.locator(form_selector).locator('[name="title"], [name="name"]')
        expect(field).to_have_value(TITLE)
        pointer = 'coarse' if width == 390 else 'fine'
        assert page.evaluate(f"matchMedia('(pointer: {pointer})').matches")
        if family:
            expect(page.locator('main')).to_have_attribute('data-profile-scope', profile)
        evidence['editor'] = page.url
        evidence['form'] = form_selector

        def observe_request(event):
            entry = {'method': event.method, 'path': urlsplit(event.url).path}
            evidence['requests'].append(entry)
            if event.method not in ('GET', 'HEAD', 'OPTIONS'):
                evidence['writes'].append(entry)
            if event.is_navigation_request() and event.frame == page.main_frame:
                evidence['documents'].append(entry)

        page.on('request', observe_request)
        try:
            yield page, owner, evidence
        finally:
            evidence['final_url'] = page.url
            (tmp_path / 'v3-5-evidence.json').write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8',
            )


def _return_control(page, evidence):
    semantic = 'actions.cancel' if evidence['kind'] in ('component', 'cookbook') else 'actions.back'
    return page.locator(f'main a[data-semantic="{semantic}"]')


def _navigate(page, evidence, navigation):
    if navigation == 'history-back':
        page.evaluate('history.back()')
    else:
        _return_control(page, evidence).click()


def _expect_list(page, evidence, navigation):
    expected_query = evidence['return_query']
    if navigation == 'history-back':
        expected_query = {key: [value] for key, value in evidence['filter_values'].items()}
    destination = urljoin(evidence['editor'], evidence['list_path'])
    expect(page).to_have_url(re.compile(re.escape(destination) + r'(?:\?.*)?$'))
    page.wait_for_load_state('networkidle')
    assert parse_qs(urlsplit(page.url).query) == expected_query
    expect(page.locator('[name="q"]')).to_have_value(TITLE if navigation == 'history-back' else '')
    if evidence['kind'] == 'component':
        expect(page.locator('[name="status"]')).to_have_value('all' if navigation == 'history-back' else 'active')
        expect(page.locator('#f-cat')).to_have_value('side' if navigation == 'history-back' else '')
    else:
        expect(page.locator('[name="archived"]')).to_be_checked(checked=navigation == 'history-back')
    evidence['filter_return'] = 'retained by history' if navigation == 'history-back' else 'lost by list control'


@pytest.mark.parametrize('navigation', ['list-control', 'history-back'])
def test_dirty_leave_stay_keeps_values_and_leave_never_saves(editor_session, tmp_path, navigation):
    page, owner, evidence = editor_session
    before = _database_state(owner)
    field = page.locator(evidence['form']).locator('[name="title"], [name="name"]')
    field.fill('V3-5 ungespeichert')
    leave = False

    def answer(dialog):
        evidence['dialogs'].append({'type': dialog.type, 'decision': 'leave' if leave else 'stay'})
        dialog.accept() if leave else dialog.dismiss()

    page.on('dialog', answer)
    if evidence['javascript']:
        requests_before = list(evidence['requests'])
        with page.expect_event('dialog', timeout=5000):
            _navigate(page, evidence, navigation)
        assert evidence['dialogs'] == [{'type': 'beforeunload', 'decision': 'stay'}]
        expect(page).to_have_url(evidence['editor'])
        expect(field).to_have_value('V3-5 ungespeichert')
        assert evidence['requests'] == requests_before
        assert evidence['documents'] == evidence['writes'] == []
        assert _database_state(owner) == before
        page.screenshot(path=str(tmp_path / 'dirty-stay.png'), full_page=True)
        leave = True
        with page.expect_event('dialog', timeout=5000):
            _navigate(page, evidence, navigation)
        assert evidence['dialogs'] == [
            {'type': 'beforeunload', 'decision': 'stay'},
            {'type': 'beforeunload', 'decision': 'leave'},
        ]
    else:
        # Native No-JS has no dirty guard; characterize without claiming protection.
        _navigate(page, evidence, navigation)
    _expect_list(page, evidence, navigation)
    if not evidence['javascript']:
        assert evidence['dialogs'] == []
    assert evidence['writes'] == []
    assert _database_state(owner) == before
    page.goto(evidence['editor'], wait_until='networkidle')
    expect(field).to_have_value(TITLE)
    assert _database_state(owner) == before
    evidence['database_unchanged'] = True


def test_successful_save_releases_guard_without_extra_write(editor_session):
    page, owner, evidence = editor_session
    before = _database_state(owner)

    def unexpected_dialog(dialog):
        evidence['dialogs'].append(dialog.type)
        dialog.dismiss()

    page.on('dialog', unexpected_dialog)
    form = page.locator(evidence['form'])
    field = form.locator('[name="title"], [name="name"]')
    field.fill('V3-5 gespeichert')
    post_path = form.get_attribute('action')
    save = page.locator('[form="recipe-editor"][data-semantic="actions.save"]') if evidence['kind'] == 'recipe' else form.locator('[data-semantic="actions.save"]')
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        save.click()
    assert saved.value.status == 303
    page.wait_for_load_state('networkidle')
    expect(field).to_have_value('V3-5 gespeichert')
    expect(form.locator('[name="row_version"]')).to_have_value('2')
    table, column = {
        'recipe': ('recipes', 'title'), 'ingredient': ('foods', 'name'),
        'cookbook': ('cookbooks', 'name'), 'component': ('menu_components', 'name'),
    }[evidence['kind']]
    with owner.connect() as connection:
        assert tuple(connection.execute(text(
            f'SELECT {column}, row_version FROM cafeteria.{table} WHERE public_id::text=:id'
        ), {'id': urlsplit(evidence['editor']).path.rsplit('/', 1)[1]}).one()) == ('V3-5 gespeichert', 2)
    after = _database_state(owner)
    assert after != before
    _navigate(page, evidence, 'list-control')
    _expect_list(page, evidence, 'list-control')
    assert evidence['dialogs'] == []
    assert evidence['writes'] == [{'method': 'POST', 'path': post_path}]
    assert _database_state(owner) == after
    evidence['saved_navigation_without_guard'] = True


@pytest.mark.parametrize('navigation', ['list-control', 'history-back'])
def test_list_return_characterizes_current_filter_context(editor_session, navigation):
    """History retains search/filters; explicit list controls currently discard them."""
    page, owner, evidence = editor_session
    before = _database_state(owner)
    destination = urlsplit(_return_control(page, evidence).get_attribute('href'))
    assert destination.path == evidence['list_path']
    assert parse_qs(destination.query) == evidence['return_query']
    _navigate(page, evidence, navigation)
    _expect_list(page, evidence, navigation)
    assert evidence['writes'] == []
    assert _database_state(owner) == before
