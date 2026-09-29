"""D20 / UI-18: validated list return, dirty-leave and saved navigation."""
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
        filter_values['page'] = '1'
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
        page.locator(f'a[data-semantic="actions.edit"][href^="{editor_path}"]').click()
        page.wait_for_load_state('networkidle')
        assert urlsplit(page.url).path == editor_path
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


def _expect_list(page, evidence, navigation, *, retained=True):
    expected_query = evidence['return_query']
    if retained:
        expected_query = {key: [value] for key, value in evidence['filter_values'].items()}
    destination = urljoin(evidence['editor'], evidence['list_path'])
    expect(page).to_have_url(re.compile(re.escape(destination) + r'(?:\?.*)?$'))
    page.wait_for_load_state('networkidle')
    assert parse_qs(urlsplit(page.url).query) == expected_query
    expect(page.locator('[name="q"]')).to_have_value(evidence['filter_values']['q'] if retained else '')
    if evidence['kind'] == 'component':
        expect(page.locator('[name="status"]')).to_have_value('all' if retained else 'active')
        expect(page.locator('#f-cat')).to_have_value('side' if retained else '')
    else:
        expect(page.locator('[name="archived"]')).to_be_checked(checked=retained)
    evidence['filter_return'] = f'retained by {navigation}' if retained else 'default after save'


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
    _expect_list(page, evidence, 'list-control', retained=False)
    assert evidence['dialogs'] == []
    assert evidence['writes'] == [{'method': 'POST', 'path': post_path}]
    assert _database_state(owner) == after
    evidence['saved_navigation_without_guard'] = True


@pytest.mark.parametrize('navigation', ['list-control', 'history-back'])
def test_list_return_characterizes_current_filter_context(editor_session, navigation):
    """History and explicit list controls both retain the permitted list context."""
    page, owner, evidence = editor_session
    before = _database_state(owner)
    destination = urlsplit(_return_control(page, evidence).get_attribute('href'))
    assert destination.path == evidence['list_path']
    assert parse_qs(destination.query) == {key: [value] for key, value in evidence['filter_values'].items()}
    _navigate(page, evidence, navigation)
    _expect_list(page, evidence, navigation)
    assert evidence['writes'] == []
    assert _database_state(owner) == before


def test_invalid_return_context_falls_back_without_writes(editor_session):
    page, owner, evidence = editor_session
    before = _database_state(owner)
    marker = {'recipe': 'recipes', 'ingredient': 'foods', 'cookbook': 'cookbooks', 'component': 'components'}[evidence['kind']]
    valid = {'from': marker, **evidence['filter_values']}
    variants = [
        ('missing-source', [(k, v) for k, v in valid.items() if k != 'from']),
        ('wrong-source', list({**valid, 'from': '//example.invalid'}.items())),
        ('long-search', list({**valid, 'q': 'x' * 201}.items())),
        ('nul-search', list({**valid, 'q': 'x\x00y'}.items())),
        ('free-target', [*valid.items(), ('next', 'https://example.invalid/')]),
    ]
    variants.extend((f'duplicate-{key}', [*valid.items(), (key, value)]) for key, value in valid.items())
    if evidence['kind'] == 'component':
        variants.extend((key, list({**valid, key: value}.items())) for key, value in (
            ('category', 'invalid'), ('status', 'invalid'), ('page', '2'),
        ))
    else:
        variants.extend((f'page-{value}', list({**valid, 'page': value}.items())) for value in (
            '0', '-1', '1.5', '01', '１', '1000000', '9' * 100,
        ))
        variants.append(('archive', list({**valid, 'archived': 'yes'}.items())))
        if evidence['kind'] == 'ingredient':
            variants.append(('kind', list({**valid, 'kind': 'units'}.items())))
    editor = urlsplit(evidence['editor']).path
    evidence['invalid_contexts'] = []
    for label, args in variants:
        response = page.goto(editor + '?' + urlencode(args), wait_until='networkidle')
        assert response is not None and response.status == 200, label
        destination = urlsplit(_return_control(page, evidence).get_attribute('href'))
        assert destination.path == evidence['list_path'], label
        assert parse_qs(destination.query) == evidence['return_query'], label
        _navigate(page, evidence, 'list-control')
        _expect_list(page, evidence, 'list-control', retained=False)
        evidence['invalid_contexts'].append(label)
    assert evidence['writes'] == []
    assert _database_state(owner) == before

def test_valid_return_context_preserves_page_and_escaped_search(editor_session):
    page, owner, evidence = editor_session
    before = _database_state(owner)
    marker = {'recipe': 'recipes', 'ingredient': 'foods', 'cookbook': 'cookbooks', 'component': 'components'}[evidence['kind']]
    evidence['filter_values']['q'] = 'Kräuter & "<Zitrone>" / ? #'
    if evidence['kind'] != 'component':
        evidence['filter_values']['page'] = '2'
    args = {'from': marker, **evidence['filter_values']}
    response = page.goto(urlsplit(evidence['editor']).path + '?' + urlencode(args), wait_until='networkidle')
    assert response is not None and response.status == 200
    _navigate(page, evidence, 'list-control')
    _expect_list(page, evidence, 'list-control')
    assert evidence['writes'] == []
    assert _database_state(owner) == before

    evidence['filter_values']['q'] = 'x' * 200
    if evidence['kind'] != 'component':
        evidence['filter_values']['page'] = '999999' if evidence['kind'] == 'cookbook' else '100000'
    args = {'from': marker, **evidence['filter_values']}
    response = page.goto(urlsplit(evidence['editor']).path + '?' + urlencode(args), wait_until='networkidle')
    assert response is not None and response.status == 200
    _navigate(page, evidence, 'list-control')
    _expect_list(page, evidence, 'list-control')
    assert evidence['writes'] == []
    assert _database_state(owner) == before


@pytest.mark.parametrize('editor_session', [
    ('ingredient', None, 1440, True), ('ingredient', None, 1440, False),
], indirect=True, ids=['ingredient-js', 'ingredient-nojs'])
def test_ingredient_recipe_search_keeps_its_validation_with_return_context(editor_session):
    page, owner, evidence = editor_session
    before = _database_state(owner)
    editor = urlsplit(evidence['editor']).path
    valid = {'from': 'foods', **evidence['filter_values'], 'recipe_q': 'Suchtest', 'recipe_page': '2'}
    response = page.goto(editor + '?' + urlencode(valid), wait_until='networkidle')
    assert response is not None and response.status == 200
    destination = urlsplit(_return_control(page, evidence).get_attribute('href'))
    assert parse_qs(destination.query) == {key: [value] for key, value in evidence['filter_values'].items()}
    for args in (
        list({**valid, 'recipe_page': '0'}.items()),
        list({**valid, 'recipe_q': 'x' * 201}.items()),
        [*valid.items(), ('recipe_page', '3')],
        [*valid.items(), ('recipe_q', 'duplicate')],
    ):
        response = page.goto(editor + '?' + urlencode(args), wait_until='networkidle')
        assert response is not None and response.status == 400
    assert evidence['writes'] == []
    assert _database_state(owner) == before
