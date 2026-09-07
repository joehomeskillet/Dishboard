"""Registered screen routes with real PostgreSQL and original signed forms."""
import json
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from time import monotonic

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool
from werkzeug.datastructures import MultiDict

from cafeteria import screen_templates as store
from cafeteria.admin import screen_template_routes as routes
from cafeteria.public import routes as public
from test_admin_screens_preview_browser import screen_app as _screen_app
from test_admin_workflow_routes import APP_PASSWORD, _hidden, _login, database_engine  # noqa: F401
from test_screen_template_store import state


@pytest.fixture
def screen_app(database_engine, monkeypatch, tmp_path):  # noqa: F811
    # Use the real app factory/registration/CSP, but remove the older snapshot double.
    application = _screen_app.__wrapped__(database_engine, monkeypatch, tmp_path)
    from cafeteria.db import active_snapshot
    monkeypatch.setattr(public, 'active_snapshot', active_snapshot)
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD), poolclass=NullPool)
    application.extensions['cafeteria_db'] = runtime
    yield application
    runtime.dispose()


def form(client, family='patienten'):
    response = client.get(f'/admin/screens/{family}/wochenvorlage')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    values = {key: _hidden(html, key) for key in ('_csrf', '_form_context', 'version', 'renderer_revision', 'action')}
    values['template_id'] = 'patient-week-text' if family == 'patienten' else 'cafeteria-week-text'
    return values


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('role', ['Cafeteria.Admin', 'Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_read_has_no_writes_and_preview_without_publication_is_honest404(screen_app, database_engine, family, role):  # noqa: F811
    client, _ = _login(screen_app, database_engine, [role])
    before = state(database_engine)
    values = form(client, family)
    for mode in ('photo', 'text'):
        response = client.get(f'/admin/vorlagen/screens/{family}/{"patient" if family == "patienten" else family}-week-{mode}')
        assert response.status_code == 404 and response.headers['Cache-Control'] == 'no-store'
    assert state(database_engine) == before
    if role != 'Cafeteria.Admin':
        assert client.post(f'/admin/screens/{family}/wochenvorlage', data=values).status_code == 403
        assert state(database_engine) == before


@pytest.mark.parametrize('kind', ['extra', 'duplicate', 'version', 'signature', 'revision', 'action', 'csrf', 'unicode_csrf'])
def test_bad_form_is400_preserves_original_values_and_does_not_write(screen_app, database_engine, kind):  # noqa: F811
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    values = form(client)
    if kind == 'duplicate':
        data = MultiDict(list(values.items()) + [('template_id', 'patient-week-photo')])
    else:
        field = {'extra': 'unexpected', 'version': 'version', 'signature': '_form_context',
                 'revision': 'renderer_revision', 'action': 'action', 'csrf': '_csrf', 'unicode_csrf': '_csrf'}[kind]
        data = values | {field: 'ungültig' if kind == 'unicode_csrf' else '<invalid>'}
    before = state(database_engine)
    response = client.post('/admin/screens/patienten/wochenvorlage', data=data)
    assert response.status_code == 400 and response.headers['Cache-Control'] == 'no-store'
    html = response.get_data(as_text=True)
    assert unescape(_hidden(html, '_form_context')) == data['_form_context']
    assert unescape(_hidden(html, 'version')) == data['version']
    assert 'value="patient-week-text" checked' in html
    assert '<invalid>' not in html
    assert state(database_engine) == before


def test_signed_scope_cannot_be_reused_for_other_profile(screen_app, database_engine):  # noqa: F811
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    values = form(client) | {'template_id': 'cafeteria-week-text'}
    before = state(database_engine)
    response = client.post('/admin/screens/cafeteria/wochenvorlage', data=values)
    assert response.status_code == 400
    assert _hidden(response.get_data(as_text=True), '_form_context') == values['_form_context']
    assert state(database_engine) == before


def test_same_state_conflict_rolls_back_first_insert_and_keeps_signed_cas(screen_app, database_engine):  # noqa: F811
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    values = form(client) | {'template_id': 'patient-week-photo'}
    before = state(database_engine)
    response = client.post('/admin/screens/patienten/wochenvorlage', data=values)
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert _hidden(html, '_form_context') == values['_form_context']
    assert _hidden(html, 'version') == '0'
    assert state(database_engine) == before


@pytest.mark.parametrize('selected,status', [('unknown', 404), ('cafeteria-week-text', 400)])
def test_unknown_or_incompatible_template_is_rejected(screen_app, database_engine, selected, status):  # noqa: F811
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    values = form(client) | {'template_id': selected}
    before = state(database_engine)
    assert client.post('/admin/screens/patienten/wochenvorlage', data=values).status_code == status
    assert state(database_engine) == before


@pytest.mark.parametrize('rotate_csrf', [False, True])
def test_changed_original_actor_is401(screen_app, database_engine, rotate_csrf):  # noqa: F811
    client, actor = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    values = form(client)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:actor'), {'actor': actor})
    with client.session_transaction() as session:
        session['authz_version'] += 1
        if rotate_csrf:
            session['_csrf_token'] = 'renewed-session-csrf'
    before = state(database_engine)
    assert client.post('/admin/screens/patienten/wochenvorlage', data=values).status_code == 401
    assert state(database_engine) == before


@pytest.mark.parametrize('path', ['/admin/screens', '/admin/vorlagen', '/admin/screens/patienten/wochenvorlage'])
def test_failed_database_does_not_render_db_context_again(screen_app, database_engine, monkeypatch, path):  # noqa: F811
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise OperationalError('private statement', {}, Exception('private error'))
    monkeypatch.setattr(routes.store, 'read_assignment', fail)
    monkeypatch.setattr('cafeteria.admin.output_routes.read_assignment', fail)
    screen_app.context_processor(lambda: pytest.fail('DB-dependent context rendered after failure'))
    response = client.get(path)
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert len(calls) == 1
    assert b'private' not in response.data


@pytest.mark.parametrize('path', ['/patienten/wochenplan/', '/admin/screens/patienten/wochenvorlage'])
def test_corrupt_assignment_is503_not_default(screen_app, database_engine, path):  # noqa: F811
    client, _ = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    with database_engine.begin() as connection:
        connection.execute(text('INSERT INTO cafeteria.settings(setting_key,setting_value) VALUES (:key,CAST(:value AS jsonb))'),
                           {'key': store.key('patient'), 'value': json.dumps({'schema_version': 99})})
    before = state(database_engine)
    response = client.get(path)
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert state(database_engine) == before
    assert client.get('/patienten/wochenplan/ohne-bilder/').status_code == 404


def test_real_writer_lock_timeout_is503_without_db_render_or_mutation(screen_app, database_engine):  # noqa: F811
    probe = {'armed': False}
    screen_app.context_processor(lambda: pytest.fail('DB context must not render after writer timeout') if probe['armed'] else {})
    client, actor = _login(screen_app, database_engine, ['Cafeteria.Admin'])
    values = form(client)
    before = state(database_engine)
    probe['armed'] = True
    with database_engine.begin() as blocker:
        blocker.execute(text('SELECT id FROM cafeteria.users WHERE id=:actor FOR UPDATE'), {'actor': actor})
        with ThreadPoolExecutor(max_workers=1) as worker:
            started = monotonic()
            future = worker.submit(client.post, '/admin/screens/patienten/wochenvorlage', data=values)
            response = future.result(timeout=12)
            assert 4 <= monotonic() - started < 10
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert b'lock timeout' not in response.data and b'SELECT' not in response.data
    assert state(database_engine) == before
