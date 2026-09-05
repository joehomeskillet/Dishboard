from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask, request
from werkzeug.datastructures import MultiDict

from cafeteria import roles
from cafeteria.admin import rendering, workflow_routes as routes
from cafeteria.component_catalog_store import AdminScope, ComponentNotFoundError, StaleComponentError
from cafeteria.workflow_partial_store import PartialWorkflowConflictError
from test_admin_workflow_routes import DAY, ROOT, _menu_form, _register


@pytest.fixture
def form_client(monkeypatch):
    app = Flask(__name__, template_folder=str(ROOT / 'reference_scaffold/cafeteria/templates'))
    app.config.update(TESTING=True, SECRET_KEY='form-contract-test')
    app.extensions['cafeteria_db'] = object()
    _register(app)
    monkeypatch.setattr(roles, 'load_user_authorization', lambda *_: SimpleNamespace(
        authz_version=3, roles=['Cafeteria.Editor'],
    ))
    monkeypatch.setattr(routes, '_scope', lambda profile: AdminScope(7, 5, profile))
    state = {'writes': [], 'renders': [], 'overview': []}

    def write(*args):
        state['writes'].append(args)
        return 1

    for name in ('persist_menu_item', 'persist_week_header', 'persist_service_state', 'update_component'):
        monkeypatch.setattr(routes, name, write)
    monkeypatch.setattr(routes, 'create_component', write)
    monkeypatch.setattr(routes, 'find_components', lambda *_: [])
    monkeypatch.setattr(routes, 'get_component', lambda *_args, **_kwargs: {
        'public_id': 'component-id', 'profile_scope': 'patient', 'active': True,
        'name': 'Gespeichert', 'category': 'side', 'origin_country_code': 'CH',
        'row_version': 9, 'usage_count': 0,
        'labels': [{'code': 'VEGAN', 'name': 'Vegan'}],
        'allergens': [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}],
    })
    monkeypatch.setattr(routes, '_master_choices', lambda: (
        [{'code': 'GLUTEN', 'name': 'Gluten'}, {'code': 'MILK', 'name': 'Milch'}],
        [{'code': 'VEGAN', 'name': 'Vegan'}, {'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
    ))
    original_render = rendering.render_template

    def render(template, **values):
        state['renders'].append(values)
        return original_render(template, **values)

    monkeypatch.setattr(rendering, 'render_template', render)

    def menu_editor(*_args, **values):
        state['renders'].append(values)
        return 'menu-editor', values['status']

    monkeypatch.setattr(routes, '_render_menu_page', menu_editor)

    def overview(profile):
        state['overview'].append((profile, request.args.get('week')))
        return '<main id="main-content">Wochenübersicht</main>'

    monkeypatch.setattr(routes, '_week_overview', overview)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user={'id': 7, 'name': 'Test Editor'}, authz_version=3, _csrf_token='form-test-csrf')

    def token(family, purpose='overview'):
        profile = routes.FAMILIES[family]
        with app.app_context():
            digest = routes._csrf_digest(AdminScope(7, 5, profile), profile, purpose, 'form-test-csrf')
        return f'form-test-csrf.{purpose}.{digest}'

    return client, token, state


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('kind', ['header', 'service'])
def test_header_and_service_prg_reaches_selected_week_overview(form_client, family, kind):
    client, token, state = form_client
    fields = {'_csrf': token(family), 'week': DAY, 'row_version': '4'}
    if kind == 'header':
        fields.update(title='Gespeicherte Woche', shared_note='Vollständiger Hinweis')
    else:
        fields.update(day=DAY, meal='LUNCH', service_state='closed', notice='Keine Ausgabe')
    result = client.post(f'/admin/{family}/{kind}', data=fields, follow_redirects=True)
    assert [response.status_code for response in result.history] == [303]
    assert result.history[0].location == f'/admin/{family}?week={DAY}'
    assert result.status_code == 200 and 'Wochenübersicht' in result.text
    assert result.headers['Cache-Control'] == 'no-store'
    assert state['overview'] == [(routes.FAMILIES[family], DAY)]
    assert len(state['writes']) == 1 and state['writes'][0][-1] == 4
    with client.session_transaction() as session:
        assert session['_flashes'][-1][1].endswith('gespeichert.')


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
def test_menu_save_return_keeps_payload_csrf_and_selected_week(form_client, family):
    client, token, state = form_client
    fields = _menu_form(_csrf=token(family), row_version='4')
    if family == 'cafeteria':
        fields.update(internal_chf='9.50', external_chf='14.50')
    result = client.post(f'/admin/{family}/menu?return_to=week', data=fields)
    assert result.status_code == 303 and result.location == f'/admin/{family}?week={DAY}'
    assert state['writes'][0][-1] == 4
    assert state['writes'][0][1] == AdminScope(7, 5, routes.FAMILIES[family])
    default = client.post(f'/admin/{family}/menu', data=fields)
    assert default.status_code == 303 and default.location.startswith(f'/admin/{family}/menu?week={DAY}&')


@pytest.mark.parametrize('query', ['return_to=', 'return_to=other', 'return_to=https://example.invalid',
                                  'return_to=week&return_to=week', 'return_to=week&week=2026-08-31',
                                  'return_to=week&profile=patient'])
def test_menu_return_query_rejects_unrecognized_or_duplicate_targets_without_write(form_client, query):
    client, token, state = form_client
    result = client.post('/admin/patienten/menu?' + query, data=_menu_form(_csrf=token('patienten')))
    assert result.status_code == 400 and not state['writes']


@pytest.mark.parametrize('conflict', [False, True])
def test_menu_return_error_stays_in_editor_with_entered_values(form_client, monkeypatch, conflict):
    client, token, state = form_client
    fields = _menu_form(_csrf=token('patienten'), title='' if not conflict else 'Mein Entwurf', note='Behalten')
    if conflict:
        def stale(*_):
            raise PartialWorkflowConflictError('Veraltet')
        monkeypatch.setattr(routes, 'persist_menu_item', stale)
    result = client.post('/admin/patienten/menu?return_to=week', data=fields)
    assert result.status_code == (409 if conflict else 400)
    assert 'Location' not in result.headers and not state['overview']
    assert state['renders'][-1]['form_values']['title'] == fields['title']
    assert state['renders'][-1]['form_values']['note'] == 'Behalten'
    assert not state['writes']


def _component_fields(token, updating=False):
    return MultiDict([
        ('_csrf', token), ('name', '  Eingegebener Name  '), ('category', 'side'),
        ('origin_country_code', 'CH'), ('row_version' if updating else 'target_scope', '4' if updating else 'current'),
        ('label_code', 'VEGAN'), ('label_code', 'VEGETARIAN'),
        ('allergen_code', 'GLUTEN'), ('allergen_code', 'MILK'),
        ('allergen_presence', 'contains'), ('allergen_presence', 'may_contain'),
    ])


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('updating', [False, True])
@pytest.mark.parametrize(('field', 'invalid'), [('name', '   '), ('category', 'invalid'), ('origin_country_code', 'CHE')])
def test_component_validation_rerenders_field_errors_and_multivalue_form(form_client, family, updating, field, invalid):
    client, token, state = form_client
    fields = _component_fields(token(family, 'component' if updating else 'component-create'), updating)
    fields[field] = invalid
    path = f'/admin/{family}/komponenten' + ('/component-id' if updating else '')
    result = client.post(path, data=fields)
    assert result.status_code == 400 and result.headers['Cache-Control'] == 'no-store'
    assert 'aria-invalid="true"' in result.text
    captured = state['renders'][-1]
    assert field in captured['form_errors']
    assert isinstance(captured['form_values'], MultiDict)
    assert list(captured['form_values'].items(multi=True)) == list(fields.items(multi=True))
    assert captured['form_values'].getlist('allergen_presence') == ['contains', 'may_contain']
    if updating:
        assert captured['component']['row_version'] == '4'
    assert not state['writes']


def test_component_invalid_edit_does_not_disclose_foreign_component(form_client, monkeypatch):
    client, token, state = form_client
    def missing(*_args, **_kwargs):
        raise ComponentNotFoundError('Komponente nicht gefunden.')
    monkeypatch.setattr(routes, 'get_component', missing)
    fields = _component_fields(token('patienten', 'component'), True)
    fields['name'] = ' '
    assert client.post('/admin/patienten/komponenten/foreign-id', data=fields).status_code == 404
    assert not state['writes'] and not state['renders']


def test_component_stale_edit_and_invalid_csrf_keep_existing_rejection(form_client, monkeypatch):
    client, token, state = form_client
    def stale(*_args, **_kwargs):
        raise StaleComponentError('Veraltet')
    monkeypatch.setattr(routes, 'update_component', stale)
    fields = _component_fields(token('patienten', 'component'), True)
    assert client.post('/admin/patienten/komponenten/component-id', data=fields).status_code == 409
    fields['_csrf'] = 'invalid'
    assert client.post('/admin/patienten/komponenten/component-id', data=fields).status_code == 400
    assert not state['writes'] and not state['renders']


def test_component_get_keeps_saved_metadata_when_no_form_was_submitted(form_client):
    client, _, state = form_client
    result = client.get('/admin/patienten/komponenten/component-id')
    assert result.status_code == 200
    assert state['renders'][-1]['form_values'] == {}
    assert 'value="VEGAN" checked' in result.text and 'value="MILK" checked' in result.text
