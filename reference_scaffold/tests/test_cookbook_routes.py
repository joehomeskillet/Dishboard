"""Cookbook form parser, private-harness routes and PostgreSQL invariants."""
from __future__ import annotations

import os
from html.parser import HTMLParser
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest

from cafeteria.admin.cookbook_forms import (
    UNKNOWN_RECIPE, list_arguments, parse_cookbook_header, parse_cookbook_recipes,
    parse_status_action, recipe_label, signed_labels,
)
from cafeteria.admin.recipe_forms import FormError

PG = pytest.mark.skipif(
    not os.environ.get('TEST_DATABASE_URL'),
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


def header(name='Sammlung', description=''):
    data = MultiDict()
    data.add('name', name)
    data.add('description', description)
    return data


def recipes(*pairs):
    data = MultiDict()
    for public_id, position in pairs:
        data.add('recipe_public_ids', public_id)
        data.add('recipe_positions', position)
    return data


def test_header_keeps_multiline_original_and_rejects_markup():
    data = header(description='\nErste\r\nZweite')
    original = list(data.items(multi=True))
    assert parse_cookbook_header(data) == {'name': 'Sammlung', 'description': 'Erste\nZweite'}
    assert list(data.items(multi=True)) == original
    data['name'] = '<script>'
    with pytest.raises(FormError) as error:
        parse_cookbook_header(data)
    assert error.value.field == 'name'


@pytest.mark.parametrize('change', ['duplicate', 'unknown', 'missing'])
def test_header_rejects_ambiguous_fields(change):
    data = header()
    if change == 'duplicate':
        data.add('name', 'Anderer Name')
    elif change == 'unknown':
        data['server_role'] = 'Admin'
    else:
        del data['description']
    with pytest.raises(FormError):
        parse_cookbook_header(data)


def test_recipes_order_by_position_skips_empty_and_rejects_duplicates():
    first, second = str(uuid4()), str(uuid4())
    data = recipes((second, '20'), ('', '5'), (first, '10'))
    original = list(data.items(multi=True))
    assert parse_cookbook_recipes(data) == [str(UUID(first)), str(UUID(second))]
    assert list(data.items(multi=True)) == original
    data = recipes((first, '1'), (second, '1'))
    with pytest.raises(FormError) as error:
        parse_cookbook_recipes(data)
    assert error.value.field == 'recipe_positions'
    data = recipes((first, '1'), (first, '2'))
    with pytest.raises(FormError) as error:
        parse_cookbook_recipes(data)
    assert error.value.field == 'recipe_public_ids'


@pytest.mark.parametrize('change', ['mismatch', 'zero', 'unknown', 'sixtyfive'])
def test_recipes_reject_unusable_native_order(change):
    first, second = str(uuid4()), str(uuid4())
    if change == 'mismatch':
        data = recipes((first, '1'))
        data.add('recipe_public_ids', second)
    elif change == 'zero':
        data = recipes((first, '0'))
    elif change == 'unknown':
        data = recipes((first, '1'))
        data['row_action'] = 'up'
    else:
        data = recipes(*((str(uuid4()), str(index + 1)) for index in range(65)))
    with pytest.raises(FormError):
        parse_cookbook_recipes(data)


def test_status_action_and_unknown_display_labels():
    data = MultiDict([('status_action', 'cookbook.archive')])
    assert parse_status_action(data) == 'cookbook.archive'
    data['status_action'] = 'cookbook.delete'
    with pytest.raises(FormError) as error:
        parse_status_action(data)
    assert error.value.field == 'status_action'
    active = SimpleNamespace(public_id='a', active=True, payload={'title': 'Suppe'})
    archived = SimpleNamespace(public_id='b', active=False, payload={'title': 'Brot'})
    missing = SimpleNamespace(public_id='c', active=True, payload={})
    assert recipe_label(None) == UNKNOWN_RECIPE
    assert recipe_label(active) == 'Suppe'
    assert recipe_label(archived) == 'Brot (archiviert)'
    assert recipe_label(missing) == UNKNOWN_RECIPE
    many = [SimpleNamespace(public_id=str(index), active=True, payload={'title': 'R' + str(index)})
            for index in range(300)]
    labels = signed_labels(['b'], [archived, *many])
    assert list(labels)[0] == 'b' and len(labels) == 256 and 'b' in labels


def test_list_arguments_paging_search_and_rejects():
    app = Flask('cookbook-list-args')
    with app.test_request_context('/admin/kochbuecher?page=2&archived=1&q=Suppe'):
        assert list_arguments() == (2, True, 'Suppe')
    with app.test_request_context('/admin/kochbuecher'):
        assert list_arguments() == (1, False, '')
    with app.test_request_context('/admin/kochbuecher?page=0'):
        with pytest.raises(BadRequest):
            list_arguments()
    with app.test_request_context('/admin/kochbuecher?q=' + 'x' * 201):
        with pytest.raises(BadRequest):
            list_arguments()
    with app.test_request_context('/admin/kochbuecher?kind=foods'):
        with pytest.raises(BadRequest):
            list_arguments()


class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = {}
        self.current = None
        self.select = None
        self.selected = None
        self.area = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'form':
            self.current = MultiDict()
            self.forms[data.get('action', '')] = self.current
        if self.current is None:
            return
        if tag == 'input' and data.get('name') and data.get('type') != 'checkbox':
            self.current.add(data['name'], data.get('value', ''))
        if tag == 'select' and data.get('name'):
            self.select = data['name']
            self.selected = None
        if tag == 'option' and self.select:
            value = data.get('value', '')
            if 'selected' in data or self.selected is None:
                self.selected = value
        if tag == 'textarea' and data.get('name'):
            self.area = data['name']
            self.current.add(self.area, '')

    def handle_data(self, data):
        if self.area and self.current is not None:
            self.current[self.area] += data

    def handle_endtag(self, tag):
        if tag == 'select' and self.select and self.current is not None:
            self.current.add(self.select, self.selected or '')
            self.select = None
            self.selected = None
        if tag == 'textarea':
            self.area = None
        if tag == 'form':
            self.current = None


if os.environ.get('TEST_DATABASE_URL'):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from cafeteria import recipe_store as store
    from cafeteria import roles
    from cafeteria.admin import cookbook_routes as cookbooks
    from test_master_data_routes import b3, pg16, installed_pg16, seeded_pg16, app_engine  # noqa: F401
    from test_master_data_db import signed_in
    from test_recipe_store_db import payload, snapshot, target


    def attach(app):
        cookbooks.register_on(app, url_prefix='/admin', endpoint_prefix='admin.')


    @pytest.fixture
    def harness(b3):  # noqa: F811
        app, owner, client, actor = b3
        attach(app)
        with signed_in(app.extensions['cafeteria_db'], actor):
            yield app, owner, client, actor


    def fields(client, path, action=None):
        response = client.get(path)
        assert response.status_code == 200, response.text
        found = Forms(response.text).forms
        return response, found[path if action is None else action]


    def audits(owner, public_id):
        with owner.connect() as current:
            return current.execute(text(
                'SELECT details FROM cafeteria.audit_events '
                'WHERE entity_public_id=CAST(:id AS uuid) ORDER BY id'
            ), {'id': public_id}).scalars().all()


    @PG
    def test_private_harness_create_order_cas_archive_and_audit(harness):
        app, owner, client, actor = harness
        engine = app.extensions['cafeteria_db']
        location = store.get_location(engine)
        first = store.create_recipe(engine, actor, payload(title='Alpha'), expected_location_id=location)
        second = store.create_recipe(engine, actor, payload(title='Beta'), expected_location_id=location)
        before = snapshot(owner)
        listed = client.get('/admin/kochbuecher')
        assert listed.status_code == 200 and listed.headers['Cache-Control'] == 'no-store'
        assert snapshot(owner) == before
        created = fields(client, '/admin/kochbuecher/neu')[1]
        created['name'] = 'Sammlung'
        created['description'] = '\nOriginaltext'
        response = client.post('/admin/kochbuecher/neu', data=created)
        assert response.status_code == 303, response.text
        path = urlsplit(response.headers['Location']).path
        book_id = path.rsplit('/', 1)[1]
        page, header_form = fields(client, path)
        assert 'Originaltext' in page.text and 'Kochbuch' in page.text and 'Rezepte zuordnen' in page.text
        assert app.view_functions['admin.recipe_edit'].__module__ == 'cafeteria.admin.recipe_routes'
        assign = Forms(page.text).forms[path + '/rezepte']
        assign.setlist('recipe_public_ids', [second.public_id, first.public_id, '', '', ''])
        assign.setlist('recipe_positions', ['20', '10', '21', '22', '23'])
        events = audits(owner, book_id)
        saved = client.post(path + '/rezepte', data=assign)
        assert saved.status_code == 303, saved.text
        stored = store.get_cookbook(engine, book_id)
        assert stored.recipe_public_ids == (first.public_id, second.public_id)
        assert len(audits(owner, book_id)) == len(events) + 1
        noop = fields(client, path)[0]
        for recipe, title in ((first, 'Alpha'), (second, 'Beta')):
            recipe_path = '/admin/rezepte/' + recipe.public_id
            assert f'href="{recipe_path}"' in noop.text
            linked = client.get(recipe_path)
            assert linked.status_code == 200 and f'value="{title}"' in linked.text
        assign = Forms(noop.text).forms[path + '/rezepte']
        before_noop = snapshot(owner)
        assert client.post(path + '/rezepte', data=assign).status_code == 303
        assert snapshot(owner) == before_noop
        stale = Forms(client.get(path).text).forms[path]
        stale['name'] = 'Zwischenzeitlich'
        assert client.post(path, data=stale).status_code == 303
        stale['name'] = 'Mein ursprünglicher Entwurf'
        stale['description'] = '\nNicht speichern'
        conflict = client.post(path, data=stale)
        assert conflict.status_code == 409 and stale['_form_context'] in conflict.text
        assert 'Mein ursprünglicher Entwurf' in conflict.text and '\n\nNicht speichern' in conflict.text
        archived_recipe = store.set_recipe_active(
            engine, actor, target(second), active=False, expected_location_id=location,
        )
        editor = client.get(path)
        assert archived_recipe.public_id in editor.text and 'Beta (archiviert)' in editor.text
        keep = Forms(editor.text).forms[path + '/rezepte']
        assert client.post(path + '/rezepte', data=keep).status_code == 303
        other = store.create_recipe(engine, actor, payload(title='Gamma'), expected_location_id=location)
        store.set_recipe_active(engine, actor, target(other), active=False, expected_location_id=location)
        forbidden = Forms(client.get(path).text).forms[path + '/rezepte']
        ids = list(forbidden.getlist('recipe_public_ids'))
        positions = list(forbidden.getlist('recipe_positions'))
        ids[2] = other.public_id
        forbidden.setlist('recipe_public_ids', ids)
        forbidden.setlist('recipe_positions', positions)
        denied = client.post(path + '/rezepte', data=forbidden)
        assert denied.status_code in (400, 409)
        assert other.public_id not in store.get_cookbook(engine, book_id).recipe_public_ids
        confirm = client.get(path + '/status')
        assert confirm.status_code == 200 and 'Archivieren' in confirm.text
        cancel = snapshot(owner)
        assert client.get(path).status_code == 200
        assert snapshot(owner) == cancel
        status_form = Forms(confirm.text).forms[path + '/status']
        archived = client.post(path + '/status', data=status_form)
        assert archived.status_code == 303
        after_archive = snapshot(owner)
        assert client.post(path + '/status', data=status_form).status_code == 409
        assert snapshot(owner) == after_archive
        frozen = client.get(path)
        assert frozen.status_code == 200 and 'Zuordnung speichern' not in frozen.text
        assert client.post(path, data=header_form).status_code in (400, 409)
        reactivate = Forms(client.get(path + '/status').text).forms[path + '/status']
        assert client.post(path + '/status', data=reactivate).status_code == 303
        assert store.get_cookbook(engine, book_id).active is True
        after_reactivation = snapshot(owner)
        assert client.post(path + '/status', data=reactivate).status_code == 409
        assert snapshot(owner) == after_reactivation


    @PG
    def test_search_is_not_limited_to_the_first_unfiltered_page(harness):
        app, owner, client, actor = harness
        engine = app.extensions['cafeteria_db']
        location = store.get_location(engine)
        for index in range(51):
            store.create_cookbook(
                engine, actor, name=f'Alpha {index:02d}' if index < 50 else 'ZebraUnique',
                expected_location_id=location,
            )
        missed = client.get('/admin/kochbuecher?q=ZebraUnique')
        assert missed.status_code == 200 and 'ZebraUnique' in missed.text
        page_two = client.get('/admin/kochbuecher?page=2')
        assert page_two.status_code == 200 and 'ZebraUnique' in page_two.text


    @pytest.mark.parametrize('bad', ['csrf', 'token', 'actor', 'scope'])
    @PG
    def test_original_actor_location_and_cas_failures_never_write(harness, bad):
        _, owner, client, actor = harness
        _, data = fields(client, '/admin/kochbuecher/neu')
        data['name'] = 'Unverändert'
        if bad == 'csrf':
            data['_csrf'] = 'wrong'
        elif bad == 'token':
            data['_form_context'] += 'tampered'
        elif bad == 'actor':
            with owner.begin() as current:
                current.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
        else:
            with owner.begin() as current:
                current.execute(text('UPDATE cafeteria.locations SET active=false'))
                current.execute(text(
                    "INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Anderes Haus',true)"
                ))
        before = snapshot(owner)
        posted = client.post('/admin/kochbuecher/neu', data=data)
        assert posted.status_code == (401 if bad == 'actor' else 409 if bad == 'scope' else 400)
        assert snapshot(owner) == before
        if bad == 'scope':
            assert data['_form_context'] in posted.text and 'Unverändert' in posted.text


    @PG
    def test_outage_covers_auth_without_template_database_recursion(harness, monkeypatch):
        app, _, client, _ = harness

        def offline(*args, **kwargs):
            raise OperationalError('hidden', {}, Exception('secret detail'))

        monkeypatch.setattr(roles, 'load_user_authorization', offline)

        @app.context_processor
        def no_recursion():
            raise AssertionError('DB context called')

        response = client.get('/admin/kochbuecher')
        assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
        assert 'secret detail' not in response.text and 'tabler.min.css' in response.text


    @pytest.mark.parametrize('suffix', ['', '/status'])
    @pytest.mark.parametrize('during', ['parent', 'choices'])
    def test_get_location_change_never_signs_mixed_scope(harness, monkeypatch, suffix, during):
        app, owner, client, actor = harness
        engine = app.extensions['cafeteria_db']
        book = store.create_cookbook(engine, actor, name='Original', expected_location_id=store.get_location(engine))
        reader = store.get_cookbook if during == 'parent' else store.list_recipes
        def changed(*args, **kwargs):
            result = reader(*args, **kwargs)
            with owner.begin() as connection:
                connection.execute(text('UPDATE cafeteria.locations SET active=false'))
                connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Andere Küche',true)"))
            return result
        monkeypatch.setattr(store, 'get_cookbook' if during == 'parent' else 'list_recipes', changed)
        monkeypatch.setattr(cookbooks, 'sign_context', lambda **kwargs: pytest.fail('mixed scope must not sign'))
        if during == 'parent':
            monkeypatch.setattr(store, 'list_recipes', lambda *args, **kwargs: pytest.fail('foreign choices must not load'))
        response = client.get('/admin/kochbuecher/' + book.public_id + suffix)
        assert response.status_code == 409 and response.headers['Cache-Control'] == 'no-store'
        assert 'name="_form_context"' not in response.text


    @pytest.mark.parametrize('mode', ['scope', 'stale', 'invalid'])
    def test_assignment_recovery_preserves_original_order_context_and_names(harness, monkeypatch, mode):
        app, owner, client, actor = harness
        engine = app.extensions['cafeteria_db']
        location = store.get_location(engine)
        items = [store.create_recipe(engine, actor, payload(title=name), expected_location_id=location)
                 for name in ('Alpha', 'Beta')]
        book = store.create_cookbook(engine, actor, name='Original', expected_location_id=location)
        path = '/admin/kochbuecher/' + book.public_id
        _, data = fields(client, path, path + '/rezepte')
        data.setlist('recipe_public_ids', [row.public_id for row in reversed(items)])
        data.setlist('recipe_positions', ['2', '1'])
        if mode == 'scope':
            with owner.begin() as connection:
                connection.execute(text('UPDATE cafeteria.locations SET active=false'))
                connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Andere Küche',true)"))
        elif mode == 'stale':
            store.update_cookbook(engine, actor, target(book), name='Other tab', expected_location_id=location)
        else:
            data.setlist('recipe_positions', ['1', '1'])
        before = snapshot(owner)
        for name in ('get_cookbook', 'list_recipes'):
            monkeypatch.setattr(store, name, lambda *args, **kwargs: pytest.fail('POST must not enrich'))
        monkeypatch.setattr(cookbooks, 'sign_context', lambda **kwargs: pytest.fail('POST must not sign'))
        response = client.post(path + '/rezepte', data=data)
        assert response.status_code == (400 if mode == 'invalid' else 409)
        assert snapshot(owner) == before
        assert dict(Forms(response.text).forms[''].lists()) == dict(data.lists())
        assert 'Alpha' in response.text and 'Beta' in response.text
        if mode == 'scope':
            assert 'href="/admin/kochbuecher"' in response.text and f'href="{path}"' not in response.text


    @pytest.mark.parametrize('reader', ['get_location', 'get_cookbook', 'list_recipes'])
    def test_editor_reader_outage_stays_database_free(harness, monkeypatch, reader):
        app, _, client, actor = harness
        engine = app.extensions['cafeteria_db']
        book = store.create_cookbook(engine, actor, name='Original', expected_location_id=store.get_location(engine))
        def offline(*args, **kwargs):
            raise OperationalError('private', {}, Exception('private database detail'))
        monkeypatch.setattr(store, reader, offline)
        @app.context_processor
        def forbidden():
            pytest.fail('503 must not invoke context processors')
        response = client.get('/admin/kochbuecher/' + book.public_id)
        assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
        assert 'private database detail' not in response.text


    def test_read_only_role_cannot_receive_creation_or_status_context(harness, monkeypatch):
        app, owner, client, actor = harness
        engine = app.extensions['cafeteria_db']
        book = store.create_cookbook(engine, actor, name='Original', expected_location_id=store.get_location(engine))
        path = '/admin/kochbuecher/' + book.public_id
        data = fields(client, path)[1]
        before = snapshot(owner)
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
        assert client.get('/admin/kochbuecher/neu').status_code == 403
        assert client.get(path + '/status').status_code == 403
        assert client.post(path, data=data).status_code == 403
        readonly = client.get(path)
        assert readonly.status_code == 200 and 'name="_form_context"' not in readonly.text
        assert snapshot(owner) == before
