"""Real runtime-role HTTP, immutable PDF and template CAS contracts."""
from io import BytesIO
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from pypdf import PdfReader
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict

from cafeteria import recipe_store as recipes
from cafeteria.admin import recipe_print_template_routes as routes
from cafeteria.print_template_config import default_config
from cafeteria.print_templates import read_templates
from test_master_data_routes import b3, pg16, installed_pg16, seeded_pg16, app_engine  # noqa: F401
from test_master_data_db import make_actor, signed_in
from test_recipe_print_input_db import freeze_image
from test_recipe_store_db import mutable, payload, snapshot, target

BASE = '/admin/vorlagen/rezepte'


@pytest.fixture
def recipe_editor(b3):  # noqa: F811
    app, owner, _, _ = b3
    app.config['FRAME_ANCESTORS'] = "'self'"
    actor = make_actor(owner, 'Cafeteria.Admin')
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': actor.user_id, 'name': 'Vorlagenprüfung'}
        session['authz_version'] = actor.authz_version
        session['_csrf_token'] = 'recipe-template-csrf'
    return app, owner, client, actor


def example(fixture):
    app, _, _, actor = fixture
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        return freeze_image(engine, actor)


def path(recipe, recipe_revision, *, pdf=False, **values):
    return BASE + ('/vorschau.pdf' if pdf else '') + '?' + urlencode({
        'recipe': recipe, 'recipe_revision': recipe_revision, **values})


def fields(action='save', version=0, revision=1, **extra):
    values = {'_csrf': 'recipe-template-csrf', 'action': action, 'version': str(version), 'revision': str(revision)}
    if action == 'save':
        values.update(name='Rezeptdruck', **default_config())
    return {**values, **extra}


def state(owner):
    values = snapshot(owner)
    with owner.connect() as connection:
        values['settings'] = connection.execute(text('SELECT to_jsonb(s)::text FROM cafeteria.settings s ORDER BY to_jsonb(s)::text')).all()
    return values


def test_catalog_and_empty_editor_allow_drafts_without_recipe_or_settings_initialization(recipe_editor):
    app, owner, client, _ = recipe_editor
    before = state(owner)
    response = client.get(BASE)
    assert response.status_code == 200 and 'Keine Rezepte' in response.text
    assert '48 pt' in response.text and '54 pt' in response.text and '64 pt' in response.text
    assert '11 pt' in response.text and '12 pt' in response.text
    for forbidden in ('name="week"', 'name="layout_', 'Wochenlayout', '21 pt', '<iframe'):
        assert forbidden not in response.text
    assert 'Rezeptvorlageneditor öffnen' in client.get('/admin/vorlagen').text
    assert state(owner) == before
    assert client.post(BASE, data=fields()).status_code == 303
    assert client.post(BASE, data=fields('copy', 1, 2, name='Ohne Beispiel')).status_code == 303
    response = client.post(BASE, data=fields('activate', 2, 2))
    assert response.status_code == 400 and 'festgeschriebene Revision' in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    with app.extensions['cafeteria_db'].connect() as connection:
        assert read_templates(connection, 'recipe')['active_revision'] == 1


def test_real_preview_same_snapshot_lifecycle_and_historical_image(recipe_editor):
    app, owner, client, actor = recipe_editor
    recipe, revision, digest = example(recipe_editor)
    selected = path(recipe, revision.public_id, **{'yield': '8'})
    assert client.post(selected, data=fields(header_text='Unveränderlicher Rezeptdruck')).status_code == 303
    engine = app.extensions['cafeteria_db']
    seen = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        seen.append((connection, statement))
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        preview = client.get(path(recipe, revision.public_id, pdf=True, revision=2, **{'yield': '8'}))
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert preview.status_code == 200 and preview.mimetype == 'application/pdf'
    assert preview.headers['Cache-Control'] == 'no-store'
    assert preview.headers['X-Recipe-Revision'] == revision.public_id
    assert preview.headers['X-Print-Template-Revision'] == 'standard:2'
    pdf = PdfReader(BytesIO(preview.data))
    assert any(list(page.images) for page in pdf.pages)
    assert all(word in '\n'.join(page.extract_text() for page in pdf.pages)
               for word in ('Unveränderlicher Rezeptdruck', 'Karotte', 'Gewünscht: 8'))
    reads = [(connection, sql) for connection, sql in seen if any(name in sql for name in
             ('setting_value', 'recipe_revisions', 'recipe_assets'))]
    assert reads and len({id(connection) for connection, _ in reads}) == 1
    assert any(sql == 'SET TRANSACTION READ ONLY' for _, sql in seen)
    before = state(owner)
    with signed_in(engine, actor):
        current = recipes.get_recipe(engine, recipe)
        changed = mutable(current.payload)
        changed.update(title='Neuer Rezeptentwurf', images=[])
        changed['steps'][0]['image_sha256'] = None
        recipes.update_recipe(engine, actor, target(current), changed, expected_location_id=recipes.get_location(engine))
    assert client.get(path(recipe, revision.public_id, pdf=True, revision=2, **{'yield': '8'})).data == preview.data
    assert client.post(selected, data=fields('activate', 1, 2)).status_code == 303
    assert client.post(selected, data=fields('restore', 2, 1)).status_code == 303
    with engine.connect() as connection:
        assert read_templates(connection, 'recipe')['active_revision'] == 2
    copied = client.post(selected, data=fields('copy', 3, 3, name='Kopie'))
    copy_id = copied.location.split('template=')[1].split('&')[0]
    assert client.post(path(recipe, revision.public_id, template=copy_id), data=fields('archive', 4, 1)).status_code == 303
    archived = client.get(path(recipe, revision.public_id, template=copy_id))
    assert archived.status_code == 200 and 'Diese Vorlage ist archiviert' in archived.text
    assert client.post(path(recipe, revision.public_id, template=copy_id), data=fields('reactivate', 5, 1)).status_code == 303
    assert state(owner)['recipe_revisions'] == before['recipe_revisions']
    assert digest in str(state(owner)['recipe_assets'])


@pytest.mark.parametrize('query', ['week=2026-09-07', 'layout=custom', 'recipe=bad', 'revision=0', 'page=0',
                                 'archived=true', 'yield=0', 'yield=', 'yield=1&yield=2',
                                 'template=standard&template=standard', 'recipe_revision=' + str(uuid4())])
def test_strict_queries_are_no_store_and_readonly(recipe_editor, query):
    _, owner, client, _ = recipe_editor
    before = state(owner)
    response = client.get(BASE + '?' + query)
    assert response.status_code == 400 and response.headers['Cache-Control'] == 'no-store'
    assert state(owner) == before


def test_foreign_unknown_and_unrenderable_selection_never_activate(recipe_editor, monkeypatch):
    app, owner, client, actor = recipe_editor
    recipe, revision, _ = example(recipe_editor)
    with signed_in(app.extensions['cafeteria_db'], actor):
        other = recipes.create_recipe(app.extensions['cafeteria_db'], actor, payload(title='Anderes Rezept'),
                                       expected_location_id=recipes.get_location(app.extensions['cafeteria_db']))
    assert client.get(path(other.public_id, revision.public_id, pdf=True)).status_code == 404
    assert client.get(path(recipe, str(uuid4()), pdf=True)).status_code == 404
    assert client.post(BASE, data=fields()).status_code == 303
    before = state(owner)
    def cannot_render(*args, **kwargs):
        raise routes.RecipePdfError('Dieses Rezeptbild passt nicht vollständig auf die Seite.')
    monkeypatch.setattr(routes, 'render_recipe_pdf', cannot_render)
    preview = client.get(path(recipe, revision.public_id, pdf=True))
    assert preview.status_code == 422 and 'Rezeptbild' in preview.text
    # The store imports the actual renderer module rather than this route alias.
    monkeypatch.setattr('cafeteria.admin.recipe_pdf.render_recipe_pdf', cannot_render)
    rejected = client.post(path(recipe, revision.public_id), data=fields('activate', 1, 2))
    assert rejected.status_code == 422 and 'Rezeptbild' in rejected.text
    assert state(owner) == before


def test_cas_and_exact_form_validation_preserve_fields(recipe_editor):
    _, owner, client, _ = recipe_editor
    assert client.post(BASE, data=fields(header_text='Erster Stand')).status_code == 303
    conflict = client.post(BASE, data=fields(header_text='Mein ursprünglicher Text'))
    assert conflict.status_code == 409 and 'Mein ursprünglicher Text</textarea>' in conflict.text
    assert 'name="version" value="0"' in conflict.text
    before = state(owner)
    for extra in ({'layout_mode': 'custom'}, {'week': '2026-09-07'}, {'actor_id': '1'}, {'_csrf': 'bad'}):
        response = client.post(BASE, data=fields(version=1, revision=2, **extra))
        assert response.status_code == 400 and response.headers['Cache-Control'] == 'no-store'
    duplicate = MultiDict([*fields(version=1, revision=2).items(), ('name', 'Doppelt')])
    assert client.post(BASE, data=duplicate).status_code == 400
    assert state(owner) == before


@pytest.mark.parametrize('role', ['Cafeteria.Publisher', 'Cafeteria.Editor'])
def test_lower_current_role_cannot_use_editor_or_preview(recipe_editor, role):
    app, owner, _, _ = recipe_editor
    actor = make_actor(owner, role)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': actor.user_id, 'name': 'Lesende Person'}
        session['authz_version'] = actor.authz_version
    for method, url in (('get', BASE), ('post', BASE), ('get', BASE + '/vorschau.pdf')):
        result = getattr(client, method)(url)
        assert result.status_code == 403 and result.headers['Cache-Control'] == 'no-store'
    assert 'Rezeptvorlageneditor öffnen' not in client.get('/admin/vorlagen').text


def test_database_outage_never_reloads_context(recipe_editor, monkeypatch):
    _, _, client, _ = recipe_editor
    def unavailable(*args, **kwargs):
        raise OperationalError('private sql', {}, Exception('private details'))
    monkeypatch.setattr(routes, '_document', unavailable)
    monkeypatch.setattr(routes, '_template_context', lambda: pytest.fail('Must not load context after outage'))
    response = client.get(BASE)
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'private' not in response.text and 'vorübergehend nicht verfügbar' in response.text


def test_archived_recipe_and_revision_pagination_keep_explicit_historical_choice(recipe_editor):
    app, owner, client, actor = recipe_editor
    recipe, first, _ = example(recipe_editor)
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = recipes.get_location(engine)
        for number in range(50):
            current = recipes.get_recipe(engine, recipe)
            values = mutable(current.payload)
            values['description'] = f'Historischer Stand {number}'
            changed = recipes.update_recipe(engine, actor, target(current), values, expected_location_id=location)
            recipes.freeze_revision(engine, actor, target(changed), expected_location_id=location)
        current = recipes.get_recipe(engine, recipe)
        recipes.set_recipe_active(engine, actor, target(current), active=False, expected_location_id=location)
    before = state(owner)
    recent = client.get(BASE + '?' + urlencode({'recipe': recipe}))
    assert recent.status_code == 200 and 'Archiviert' in recent.text
    assert f'value="{first.public_id}"' not in recent.text
    old = client.get(BASE + '?' + urlencode({'recipe': recipe, 'revision_page': 2}))
    assert old.status_code == 200 and f'value="{first.public_id}"' in old.text
    # No implicit choice, including a directly selected archived recipe.
    assert '<iframe' not in recent.text and '<iframe' not in old.text
    selected = client.get(path(recipe, first.public_id, revision_page=2))
    assert selected.status_code == 200 and '<iframe' in selected.text
    assert client.get(path(recipe, first.public_id, pdf=True)).status_code == 200
    assert state(owner) == before


def test_no_file_upload_and_revoked_actor_never_mutate(recipe_editor):
    _, owner, client, actor = recipe_editor
    before = state(owner)
    uploaded = client.post(BASE, data={**fields(), 'file': (BytesIO(b'not a document'), 'extra.txt')})
    assert uploaded.status_code == 400 and uploaded.headers['Cache-Control'] == 'no-store'
    assert state(owner) == before
    with owner.begin() as connection:
        connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
    before = state(owner)
    denied = client.post(BASE, data=fields())
    assert denied.status_code == 401 and denied.headers['Cache-Control'] == 'no-store'
    assert state(owner) == before
