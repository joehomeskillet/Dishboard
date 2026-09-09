"""Real POST contracts for immutable bindings and original signed write context."""
# ruff: noqa: F401, F811
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict

from cafeteria.admin import workflow_routes
from cafeteria.workflow_partial_store import persist_week_header
from cafeteria.workflow_store import load_draft_connection
from test_admin_workflow_routes import (
    database_engine, app, client, _scope, _hidden, _menu_form, _session_actor_id, _counts, DAY, WEEK,
)
from test_admin_csv_import import _preview, _token, _example


def recipe(database_engine, client):
    actor = _session_actor_id(client)
    scope = _scope(database_engine, actor)
    with database_engine.begin() as connection:
        head = connection.execute(text('''INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,
            title,servings,servings_unit_id,source_kind) SELECT :location,:actor,:actor,'Suppe',4,id,'manual'
            FROM cafeteria.measurement_units WHERE code='PORTION' RETURNING id'''),
            {'location': scope.location_id, 'actor': actor}).scalar_one()
        revision = str(connection.execute(text('''INSERT INTO cafeteria.recipe_revisions(location_id,
            recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
            VALUES(:location,:head,1,'{}',encode(pg_catalog.sha256(convert_to('{}','UTF8')),'hex'),:actor)
            RETURNING public_id'''), {'location': scope.location_id, 'head': head, 'actor': actor}).scalar_one())
    return scope, revision


def menu_token(client):
    response = client.get(f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    assert response.status_code == 200
    return _hidden(response.get_data(as_text=True), '_csrf', form_action='/admin/patienten/menu')


def form(token, revision, **changes):
    return MultiDict(_menu_form(_csrf=token, component_public_id='', component_text='Suppe',
                               recipe_revision_public_id=revision, **changes))


def test_post_roundtrip_legacy_loss_refusal_explicit_detach_and_no_price_leak(client, database_engine):
    _, revision = recipe(database_engine, client)
    token = menu_token(client)
    first = client.post('/admin/patienten/menu', data=form(token, revision))
    assert first.status_code == 303 and first.headers['Cache-Control'] == 'no-store'
    with database_engine.connect() as connection:
        option = load_draft_connection(connection, 'patient', WEEK)['days'][0]['services'][0]['options'][0]
        identity = connection.execute(text('SELECT id,row_version FROM cafeteria.menu_items')).one()
    assert option['assignments'][0]['recipe_revision_public_id'] == revision
    assert identity.row_version == 1
    legacy = form(token, revision, row_version='1')
    legacy.pop('recipe_revision_public_id')
    denied = client.post('/admin/patienten/menu', data=legacy)
    assert denied.status_code == 409 and denied.headers['Cache-Control'] == 'no-store'
    with database_engine.connect() as connection:
        same = load_draft_connection(connection, 'patient', WEEK)['days'][0]['services'][0]['options'][0]
    assert same == option
    assert client.post('/admin/patienten/menu', data=form(token, '', row_version='1')).status_code == 303
    with database_engine.connect() as connection:
        detached = load_draft_connection(connection, 'patient', WEEK)['days'][0]['services'][0]['options'][0]
        updated = connection.execute(text('SELECT id,row_version FROM cafeteria.menu_items')).one()
    assert detached['assignments'][0]['recipe_revision_public_id'] is None
    assert updated == (identity.id, 2)
    page = client.get(f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    assert page.status_code == 200
    assert not any(word in page.get_data(as_text=True) for word in ('internal_rappen', 'external_rappen'))


@pytest.mark.parametrize('invalid', ['short', 'long', 'malformed', 'noncanonical'])
def test_three_parallel_arrays_are_exact_not_truncated(client, database_engine, invalid):
    _, revision = recipe(database_engine, client)
    data = form(menu_token(client), revision)
    if invalid == 'short':
        data.add('component_public_id', '')
        data.add('component_text', 'Zweite Zeile')
    elif invalid == 'long':
        data.add('recipe_revision_public_id', revision)
    else:
        data['recipe_revision_public_id'] = 'not-a-uuid' if invalid == 'malformed' else revision.upper()
    before = _counts(database_engine)
    response = client.post('/admin/patienten/menu', data=data)
    assert response.status_code == 400 and response.headers['Cache-Control'] == 'no-store'
    assert _counts(database_engine) == before


@pytest.mark.parametrize('endpoint', ['menu', 'week_context'])
def test_old_get_token_rejected_after_reauthorization_even_with_current_session(client, database_engine, endpoint):
    scope, revision = recipe(database_engine, client)
    if endpoint == 'menu':
        path, data = '/admin/patienten/menu', form(menu_token(client), revision)
    else:
        persist_week_header(database_engine, scope, WEEK, {'title': 'Woche', 'shared_note': ''}, 0)
        path = '/admin/patienten/wochen/pruefung'
        page = client.get(path + f'?week={DAY}')
        assert page.status_code == 200
        body = page.get_data(as_text=True)
        data = {'_csrf': _hidden(body, '_csrf', form_action=path), 'week': DAY,
                'context_version': _hidden(body, 'context_version', form_action=path)}
    before = _counts(database_engine)
    with database_engine.begin() as connection:
        authz = connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 '
            'WHERE id=:actor RETURNING authz_version'), {'actor': scope.actor_id}).scalar_one()
    with client.session_transaction() as session:
        session['authz_version'] = authz
    response = client.post(path, data=data)
    assert response.status_code == 409 and response.headers['Cache-Control'] == 'no-store'
    assert _counts(database_engine) == before


def test_revoke_after_route_authorization_before_write_fails_without_mutation(client, database_engine, monkeypatch):
    scope, revision = recipe(database_engine, client)
    data = form(menu_token(client), revision)
    original = workflow_routes.persist_menu_item

    def revoke_then_write(*args, **kwargs):
        assert args[1] == scope
        with database_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor'),
                               {'actor': scope.actor_id})
        return original(*args, **kwargs)

    monkeypatch.setattr(workflow_routes, 'persist_menu_item', revoke_then_write)
    before = _counts(database_engine)
    response = client.post('/admin/patienten/menu', data=data)
    assert response.status_code == 403 and response.headers['Cache-Control'] == 'no-store'
    assert _counts(database_engine) == before


def test_csv_preview_carries_original_authz_and_rejects_refresh(client, database_engine):
    # Reuse the real CSV route with this module's authenticated session and CSRF value.
    with client.session_transaction() as session:
        session['_csrf_token'] = 'csv-import-csrf'
    preview = _preview(client, _example('menu_patient_example.csv'))
    assert preview.status_code == 200
    token = _token(preview)
    actor = _session_actor_id(client)
    with database_engine.begin() as connection:
        version = connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 '
            'WHERE id=:actor RETURNING authz_version'), {'actor': actor}).scalar_one()
    with client.session_transaction() as session:
        session['authz_version'] = version
    response = client.post('/admin/import', data={'_csrf': 'csv-import-csrf', 'import_token': token})
    assert response.status_code == 409 and response.headers['Cache-Control'] == 'no-store'
    assert _counts(database_engine) == (0, 0, 0)


def test_writer_outage_is_safe_503_without_partial_mutation(client, database_engine):
    _, revision = recipe(database_engine, client)
    data = form(menu_token(client), revision)

    def unavailable(_conn, _cursor, statement, _params, _ctx, _many):
        if 'begin_menu_binding_write_v26' in statement:
            raise OperationalError(statement, {}, Exception('isolated connection outage'))

    event.listen(database_engine, 'before_cursor_execute', unavailable)
    try:
        response = client.post('/admin/patienten/menu', data=data)
    finally:
        event.remove(database_engine, 'before_cursor_execute', unavailable)
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'isolated connection outage' not in response.get_data(as_text=True)
    assert _counts(database_engine) == (0, 0, 0)
