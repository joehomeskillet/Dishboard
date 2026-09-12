"""Original historical revision and bounded DB failure responses on real routes."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from cafeteria import roles
from cafeteria.admin import print_template_routes as routes
from test_admin_workflow_routes import APP_PASSWORD, DAY, _login, database_engine  # noqa: F401
from test_print_template_archive import COPY_ID, legacy_document, seed, snapshot
from test_print_template_archive_concurrency import wait_blocked
from test_print_template_routes import editor_app, fields  # noqa: F401


def test_historical_archive_conflict_keeps_submitted_revision(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    seed(database_engine, 'patient', legacy_document())
    # Native actions omit revision in the URL; historical selection is a form field.
    url = f'/admin/vorlagen/patienten?week={DAY}&template=standard'
    before = snapshot(database_engine)
    response = client.post(url, data=fields('archive', 3, 1))
    assert response.status_code == 409
    assert 'Vorlage · Version 1' in response.text
    assert 'PDF-Vorschau · Version 1' in response.text
    assert 'name="version" value="3"' in response.text
    assert 'name="revision" value="2"' not in response.text
    assert 'Aktuellen Stand neu laden' in response.text
    assert snapshot(database_engine) == before


@pytest.mark.parametrize('method,path', [
    ('GET', '/admin/vorlagen/patienten'), ('POST', '/admin/vorlagen/patienten'),
    ('GET', '/admin/vorlagen/patienten/vorschau.pdf'),
])
def test_auth_database_outage_returns_db_free_unavailable(editor_app, database_engine, monkeypatch, method, path):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    before = snapshot(database_engine)

    def unavailable(*args, **kwargs):
        raise OperationalError('private statement', {}, RuntimeError('private database detail'))

    def no_context():
        pytest.fail('Unavailable rendering must not run database-backed template context')

    monkeypatch.setattr(roles, 'load_user_authorization', unavailable)
    editor_app.context_processor(no_context)
    response = client.open(path + '?week=' + DAY, method=method, data=fields('archive'))
    assert response.status_code == 503
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'Druckvorlagen vorübergehend nicht verfügbar' in response.text
    assert 'private' not in response.text and '_csrf' not in response.text
    assert snapshot(database_engine) == before


def test_runtime_settings_lock_timeout_returns_503_without_reread(editor_app, database_engine, monkeypatch):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    seed(database_engine, 'patient', legacy_document())
    before = snapshot(database_engine)
    application = 'v2-route-lock-timeout'
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD),
                            poolclass=NullPool, connect_args={'application_name': application})
    monkeypatch.setitem(editor_app.extensions, 'cafeteria_db', runtime)

    def no_reread(*args, **kwargs):
        pytest.fail('Unavailable response must not re-read templates or refresh form state')

    monkeypatch.setattr(routes, '_render_editor', no_reread)
    monkeypatch.setattr(routes, '_document', no_reread)
    monkeypatch.setattr(routes, 'csrf_token', no_reread)
    try:
        with ThreadPoolExecutor(max_workers=1) as workers:
            with database_engine.begin() as blocker:
                blocker.execute(text("SELECT id FROM cafeteria.settings WHERE setting_key='print_templates.v1.patient' FOR UPDATE"))
                future = workers.submit(client.post,
                    f'/admin/vorlagen/patienten?week={DAY}&template={COPY_ID}', data=fields('archive', 3, 1))
                wait_blocked(database_engine, application)
                response = future.result(timeout=12)
                assert response.status_code == 503
                assert response.headers['Cache-Control'] == 'no-store'
                assert 'Druckvorlagen vorübergehend nicht verfügbar' in response.text
                assert 'lock_timeout' not in response.text and 'SELECT' not in response.text
                assert 'name="version"' not in response.text
        assert snapshot(database_engine) == before
    finally:
        runtime.dispose()
