"""Real factory, runtime DB role and native form contracts for B3."""
from __future__ import annotations

from html.parser import HTMLParser
from html import unescape
import re

import pytest
from flask import render_template
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict

import cafeteria
from cafeteria import roles
from test_master_data_db import (  # noqa: F401
    app_engine, installed_pg16, make_actor, pg16, seeded_pg16, seed_storage, STORAGE_PUBLIC_ID,
)


class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = {}
        self.current = None
        self.select = None
        self.area = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'form':
            self.current = MultiDict()
            self.forms[data.get('action', '')] = self.current
        if self.current is None:
            return
        if tag == 'input' and data.get('name') and (data.get('type') != 'checkbox' or 'checked' in data):
            self.current.add(data['name'], data.get('value', ''))
        if tag == 'select':
            self.select = data['name']
        if tag == 'option' and self.select:
            if self.select not in self.current or 'selected' in data:
                self.current[self.select] = data.get('value', '')
        if tag == 'textarea' and data.get('name'):
            self.area = data['name']
            self.current[self.area] = ''

    def handle_data(self, data):
        if self.area and self.current is not None:
            self.current[self.area] += data

    def handle_endtag(self, tag):
        if tag == 'select':
            self.select = None
        if tag == 'textarea':
            self.area = None
        if tag == 'form':
            self.current = None


@pytest.fixture
def b3(seeded_pg16, app_engine, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda app: None)
    app = cafeteria.create_app()
    app.config.update(TESTING=True, SECRET_KEY='b3-isolated-fixture', LAST_GOOD_DIR=str(tmp_path))
    app.extensions['cafeteria_db'] = app_engine
    app.extensions['cafeteria_auth_issuer_db'] = app_engine
    actor = make_actor(seeded_pg16)
    seed_storage(seeded_pg16)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': actor.user_id, 'name': 'Küche Test'}
        session['authz_version'] = actor.authz_version
        session['_csrf_token'] = 'b3-test-csrf'
    return app, seeded_pg16, client, actor


def fields(client, path, purpose=None):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return Forms(response.text).forms[path + '/' + purpose if purpose else path]


def create(client, kind='zutaten', **values):
    path = '/admin/grundlagen/' + kind + '/neu'
    data = fields(client, path)
    if kind == 'zutaten':
        data['storage_location_public_ids'] = STORAGE_PUBLIC_ID
    for key, value in values.items():
        data[key] = value
    response = client.post(path, data=data)
    assert response.status_code == 303, response.text
    return response.location


def save(client, path, purpose, **values):
    data = fields(client, path, purpose)
    for key, value in values.items():
        data[key] = value
    return client.post(path + '/' + purpose, data=data)


def snapshot(owner):
    with owner.connect() as connection:
        return {table: connection.execute(text(
            f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
        )).all() for table in ('foods', 'food_tags', 'food_labels', 'food_allergens',
                              'storage_locations', 'food_storage_locations', 'audit_events')}


def test_real_factory_sidebar_and_full_atomic_food_flow(b3):
    app, owner, client, _ = b3
    assert sum(rule.endpoint == 'admin.master_data_list' for rule in app.url_map.iter_rules()) == 1
    for path in ('/admin/grundlagen', '/admin/vorlagen', '/admin/screens'):
        response = client.get(path)
        assert response.status_code == 200 and '/admin/grundlagen' in response.text
    category = create(client, 'kategorien', name='Gemüse', code='VEG', sort_order='1')
    tag = create(client, 'tags', name='Regional', code='LOCAL')
    food = create(client, name='Karotte', category_public_id=category.rsplit('/', 1)[1])
    assert save(client, food, 'tags', tag_public_ids=tag.rsplit('/', 1)[1]).status_code == 303
    before = snapshot(owner)
    assert save(client, food, 'metadaten', allergen_MILK='contains', labels='VEGETARIAN').status_code == 303
    assert len(snapshot(owner)['audit_events']) == len(before['audit_events']) + 1
    assert save(client, food, 'allergenpruefung', checked='true').status_code == 303
    before = snapshot(owner)
    same = fields(client, food, 'allergenpruefung')
    same['checked'] = 'true'
    response = client.post(food + '/allergenpruefung', data=same)
    assert response.status_code == 409 and snapshot(owner) == before
    assert save(client, food, 'stammdaten', name='Karotte').status_code == 303
    assert snapshot(owner) == before
    assert save(client, food, 'archivieren').status_code == 303
    assert 'Karotte' not in client.get('/admin/grundlagen').text
    assert 'Karotte' in client.get('/admin/grundlagen?archived=1').text
    assert save(client, food, 'reaktivieren').status_code == 303
    assert 'Manuell erfasst' in client.get(food).text


@pytest.mark.parametrize('kind,values', [
    ('tags', {'name': 'Regional', 'code': 'LOCAL'}),
    ('kategorien', {'name': 'Gemüse', 'code': 'VEG', 'sort_order': '3'}),
    ('einheiten', {'display_name': 'Dose', 'code': 'DOS', 'dimension': 'count', 'base_factor': '2'}),
])
def test_vocabulary_and_unit_edit_archive_restore_and_immutable_fields(b3, kind, values):
    _, _, client, _ = b3
    path = create(client, kind, **values)
    assert save(client, path, 'name', **{'display_name' if kind == 'einheiten' else 'name': 'Neuer Name'}).status_code == 303
    data = fields(client, path, 'name')
    data['code'] = 'OVERRIDE'
    assert client.post(path + '/name', data=data).status_code == 400
    assert save(client, path, 'archivieren').status_code == 303
    assert save(client, path, 'reaktivieren').status_code == 303
    assert 'Neuer Name' in client.get(path).text


def test_original_cas_actor_and_form_scope_never_rebase(b3):
    _, owner, client, actor = b3
    path = create(client, name='Karotte')
    stale = fields(client, path, 'stammdaten')
    old_token = stale['_form_context']
    assert save(client, path, 'stammdaten', name='Erste Sitzung').status_code == 303
    stale['name'] = 'Zweite Sitzung'
    before = snapshot(owner)
    conflict = client.post(path + '/stammdaten', data=stale)
    assert conflict.status_code == 409 and 'Zweite Sitzung' in conflict.text
    returned = Forms(conflict.text).forms[path + '/stammdaten']
    assert returned['_form_context'] == old_token and returned['row_version'] == stale['row_version']
    assert snapshot(owner) == before
    forged = MultiDict(stale)
    forged['row_version'] = str(int(stale['row_version']) + 1)
    assert client.post(path + '/stammdaten', data=forged).status_code == 400
    assert client.post(path + '/archivieren', data=stale).status_code == 400
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:id'), {'id': actor.user_id})
    assert client.post(path + '/stammdaten', data=stale).status_code == 401
    assert snapshot(owner) == before
    # A fresh session must not silently upgrade the original signed form actor.
    with client.session_transaction() as session:
        session['user'] = {'id': actor.user_id}
        session['authz_version'] = actor.authz_version + 1
        session['_csrf_token'] = 'b3-test-csrf'
    assert client.post(path + '/stammdaten', data=stale).status_code == 401
    assert snapshot(owner) == before


@pytest.mark.parametrize('query', ['kind=storage_location', 'page=0', 'page=1&page=2', 'archived=true', 'profile=patient', 'kind=tags&q=x'])
def test_strict_queries(b3, query):
    assert b3[2].get('/admin/grundlagen?' + query).status_code == 400


def test_read_role_forbidden_writes_csrf_unknown_fields_and_missing_object(b3, monkeypatch):
    app, owner, client, _ = b3
    path = create(client, name='Karotte')
    data = fields(client, path, 'stammdaten')
    before = snapshot(owner)
    for key in ('actor_id', 'location_id', 'source_kind', 'profile'):
        invalid = MultiDict(data)
        invalid[key] = 'override'
        assert client.post(path + '/stammdaten', data=invalid).status_code == 400
    duplicate = MultiDict(data)
    duplicate.add('name', 'Doppelt')
    assert client.post(path + '/stammdaten', data=duplicate).status_code == 400
    invalid = MultiDict(data)
    invalid['_csrf'] = 'wrong'
    assert client.post(path + '/stammdaten', data=invalid).status_code == 400
    assert client.get('/admin/grundlagen/zutaten/not-a-uuid').status_code == 404
    assert snapshot(owner) == before
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    response = client.get(path)
    assert response.status_code == 200 and 'Stammdaten speichern' not in response.text
    assert client.post(path + '/stammdaten', data=data).status_code == 403
    assert app.test_client().get('/admin/grundlagen').status_code == 401


@pytest.mark.parametrize('count', [0, 2])
def test_direct_scope_configuration_failure_is_db_free_503(b3, count):
    _, owner, client, _ = b3
    food = create(client, name='Karotte')
    data = fields(client, food, 'stammdaten')
    with owner.begin() as connection:
        if count == 0:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        else:
            connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('SECOND','Zweiter',true)"))
    for path in ('/admin/grundlagen/zutaten/neu', food, '/admin/grundlagen'):
        response = client.get(path)
        assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
        assert 'Grundlagen nicht verfügbar' in response.text
    assert client.post(food + '/stammdaten', data=data).status_code == 503


def test_auth_database_failure_never_reenters_render_context(b3, monkeypatch):
    _, _, client, _ = b3
    def unavailable(*args, **kwargs):
        raise OperationalError('private detail', {}, RuntimeError('do not expose'))
    monkeypatch.setattr(roles, 'load_user_authorization', unavailable)
    response = client.get('/admin/grundlagen')
    assert response.status_code == 503 and 'private detail' not in response.text
    assert response.headers['Cache-Control'] == 'no-store'


def test_complete_choices_pagination_and_archived_references_stay_visible(b3):
    _, owner, client, _ = b3
    with owner.begin() as connection:
        connection.execute(text("INSERT INTO cafeteria.tags(location_id,code,name) SELECT l.id, 'T'||n, 'Tag '||lpad(n::text,3,'0') FROM cafeteria.locations l CROSS JOIN generate_series(1,505) n WHERE l.active"))
    page = client.get('/admin/grundlagen?kind=tags&page=10&archived=1')
    assert page.status_code == 200 and 'page=11' in page.text
    assert 'Tag 505' in client.get('/admin/grundlagen?kind=tags&page=11').text
    food = create(client, name='Karotte')
    assert 'Tag 505' in client.get(food).text
    with owner.connect() as connection:
        tag = str(connection.execute(text("SELECT public_id FROM cafeteria.tags WHERE code='T505'")).scalar_one())
    assert save(client, food, 'tags', tag_public_ids=tag).status_code == 303
    assert save(client, '/admin/grundlagen/tags/' + tag, 'archivieren').status_code == 303
    data = fields(client, food, 'tags')
    assert data.getlist('tag_public_ids') == [tag]
    before = snapshot(owner)
    assert client.post(food + '/tags', data=data).status_code == 400
    assert snapshot(owner) == before
    del data['tag_public_ids']
    assert client.post(food + '/tags', data=data).status_code == 303


def test_old_location_create_form_conflicts_but_units_are_global(b3):
    _, owner, client, _ = b3
    food_path = '/admin/grundlagen/zutaten/neu'
    food = fields(client, food_path)
    food['name'] = 'Alter Standort'
    unit_path = '/admin/grundlagen/einheiten/neu'
    unit = fields(client, unit_path)
    for key, value in {'display_name': 'Dose', 'code': 'DOS', 'dimension': 'count', 'base_factor': '2'}.items():
        unit[key] = value
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('NEW','Neuer Standort',true)"))
    before = snapshot(owner)
    assert client.post(food_path, data=food).status_code == 409
    assert snapshot(owner) == before
    assert client.post(unit_path, data=unit).status_code == 303


def test_current_canonical_unit_cannot_be_archived_and_read_gets_do_not_write(b3):
    _, owner, client, _ = b3
    with owner.connect() as connection:
        public_id = str(connection.execute(text("SELECT public_id FROM cafeteria.measurement_units WHERE code='G'")).scalar_one())
    path = '/admin/grundlagen/einheiten/' + public_id
    response = client.get(path)
    assert response.status_code == 200 and path + '/archivieren' not in Forms(response.text).forms
    before = snapshot(owner)
    for route in ('/admin/grundlagen', path, '/admin/grundlagen/zutaten/neu'):
        assert client.get(route).status_code == 200
    assert snapshot(owner) == before


@pytest.mark.parametrize('kind,purpose', [
    ('zutaten', 'neu'), ('kategorien', 'neu'), ('tags', 'neu'),
    ('zutaten', 'stammdaten'), ('kategorien', 'name'), ('tags', 'name'),
    ('zutaten', 'tags'), ('zutaten', 'metadaten'),
    ('zutaten', 'allergenpruefung'), ('zutaten', 'archivieren'),
])
def test_location_conflict_retains_complete_original_form_without_rebinding(b3, monkeypatch, kind, purpose):
    from cafeteria.admin import master_data_routes as routes

    _, owner, client, _ = b3
    initial = {'name': 'Original'} if kind == 'zutaten' else {'name': 'Original', 'code': 'ORIGINAL'}
    if kind == 'kategorien':
        initial['sort_order'] = '2'
    path = '/admin/grundlagen/' + kind + '/neu' if purpose == 'neu' else create(client, kind, **initial)
    data = fields(client, path, None if purpose == 'neu' else purpose)
    if 'name' in data:
        data['name'] = 'Mein unveröffentlichter Entwurf'
    if 'code' in data:
        data['code'] = 'ENTWURF'
    if 'sort_order' in data:
        data['sort_order'] = '3'
    if 'note' in data:
        data['note'] = '\nErste Zeile\nZweite Zeile mit Umlaut ä'
    if purpose == 'tags':
        tags = [create(client, 'tags', name=name, code=name.upper()).rsplit('/', 1)[1]
                for name in ('Regional', 'Saisonal')]
        data.setlist('tag_public_ids', tags)
    if purpose == 'metadaten':
        data.setlist('labels', ['VEGETARIAN', 'VEGAN', 'ALT<&'])
        data['allergen_MILK'] = 'may_contain'
        data['allergen_ALT'] = 'contains'
    action = path if purpose == 'neu' else path + '/' + purpose
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('NEW','Neuer Standort',true)"))

    def state():
        with owner.connect() as connection:
            vocabulary = {table: connection.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
            )).all() for table in ('food_categories', 'tags', 'measurement_units')}
        return snapshot(owner), vocabulary

    def forbidden(*args, **kwargs):
        pytest.fail('Location-conflict rendering must not read objects/choices or sign new contexts')

    before = state()
    with monkeypatch.context() as patch:
        patch.setattr(routes, 'get_row', forbidden)
        patch.setattr(routes, 'choices', forbidden)
        patch.setattr(routes.forms, 'form_token', forbidden)
        response = client.post(action, data=data)
        assert response.status_code == 409
        assert response.headers['Cache-Control'] == 'no-store'
        returned = Forms(response.text).forms[action]
        assert dict(returned.lists()) == dict(data.lists())
        visible = [unescape(value).removeprefix('\n') for value in re.findall(r'<textarea\b[^>]*>(.*?)</textarea>', response.text, re.S)]
        for key, value in data.items(multi=True):
            if key not in {'_csrf', '_form_context', 'row_version'}:
                assert any(value in shown for shown in visible), (key, value)
        if purpose == 'metadaten':
            assert 'Ursprünglicher Code: ALT&lt;&amp;' in response.text
            assert 'Allergen · ursprünglicher Code ALT' in response.text
        assert f'href="{path}"' in response.text
        assert 'Aktuellen Stand neu laden' in response.text
        assert client.post(action, data=returned).status_code == 409
    assert state() == before
    if purpose == 'neu':
        reloaded = fields(client, path)
        assert reloaded['_form_context'] != data['_form_context']
        assert reloaded['name'] == ''
    else:
        assert client.get(path).status_code == 404


def test_invalid_choices_remain_visible_with_original_form_and_legacy_navigation(b3):
    app, owner, client, _ = b3
    path = create(client, name='Karotte')
    before = snapshot(owner)
    data = fields(client, path, 'stammdaten')
    data['base_unit_code'] = 'UNKNOWN'
    response = client.post(path + '/stammdaten', data=data)
    assert response.status_code == 400
    returned = Forms(response.text).forms[path + '/stammdaten']
    assert returned['base_unit_code'] == 'UNKNOWN' and returned['_form_context'] == data['_form_context']
    data = fields(client, path, 'metadaten')
    data['labels'] = 'UNKNOWN'
    response = client.post(path + '/metadaten', data=data)
    assert response.status_code == 400
    assert Forms(response.text).forms[path + '/metadaten'].getlist('labels') == ['UNKNOWN']
    assert snapshot(owner) == before
    with app.test_request_context():
        html = render_template('admin/_workflow_sidebar.html', family='cafeteria',
                               workflow_nav='master_data', tabler_admin=False)
    assert 'href="/admin/grundlagen" class="active" aria-current="page"' in html
