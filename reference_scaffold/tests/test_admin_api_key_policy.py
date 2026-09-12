from __future__ import annotations

import re
from datetime import date, timedelta
from threading import Thread

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from werkzeug.datastructures import MultiDict
from werkzeug.serving import make_server

from test_admin_api_page import (
    ROOT, _create_form, admin_client, app, database_engine,
)
from test_api_key_policy import _counts
from test_api_keys_db import _create_user
from test_rendered_ui import browser

__all__ = ['admin_client', 'app', 'database_engine', 'browser']


def test_create_rejects_extra_duplicate_query_and_bad_policy_without_mutation(admin_client, database_engine):
    before = _counts(database_engine)
    for extra in ({'unknown': '1'}, {'channels': ''}, {'expires_at': ''},
                  {'expires_at': (date.today() + timedelta(days=91)).isoformat()}):
        response = admin_client.post('/admin/api/keys', data=_create_form() | extra)
        assert response.status_code == 400
    for name in ('_csrf', 'label', 'scopes', 'expires_at', 'channels'):
        values = MultiDict(_create_form())
        values.add(name, values[name])
        assert admin_client.post('/admin/api/keys', data=values).status_code == 400
    for field in ('_csrf', 'label', 'expires_at', 'channels', 'scopes'):
        data = _create_form()
        data.pop(field)
        assert admin_client.post('/admin/api/keys', data=data).status_code == 400
    assert admin_client.post('/admin/api/keys?x=1', data=_create_form()).status_code == 400
    assert _counts(database_engine) == before


def test_create_and_revoke_recheck_role_csrf_and_payload_shape(app, database_engine, admin_client):
    editor_id = _create_user(database_engine, suffix='909', roles=['Cafeteria.Editor'])
    with database_engine.connect() as connection:
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                                     {'id': editor_id}).scalar_one()
    editor_client = app.test_client()
    with editor_client.session_transaction() as session:
        session['user'] = {'id': editor_id, 'name': 'Editor'}
        session['authz_version'] = version
        session['_csrf_token'] = 'workflow-csrf'
    before = _counts(database_engine)
    assert editor_client.post('/admin/api/keys', data=_create_form()).status_code == 403
    assert app.test_client().post('/admin/api/keys', data=_create_form()).status_code == 401
    assert _counts(database_engine) == before
    assert admin_client.post('/admin/api/keys', data=_create_form()).status_code == 303
    with database_engine.connect() as connection:
        public_id = connection.execute(text('SELECT public_id::text FROM cafeteria.api_keys')).scalar_one()
    path = f'/admin/api/keys/{public_id}/revoke'
    before = _counts(database_engine)
    for client, data, status in ((editor_client, {'_csrf': 'workflow-csrf'}, 403),
                                 (admin_client, {'_csrf': 'invalid'}, 400),
                                 (admin_client, {'_csrf': 'workflow-csrf', 'extra': '1'}, 400),
                                 (admin_client, MultiDict([('_csrf', 'workflow-csrf')] * 2), 400)):
        assert client.post(path, data=data).status_code == status
    assert admin_client.post(path + '?x=1', data={'_csrf': 'workflow-csrf'}).status_code == 400
    assert _counts(database_engine) == before
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT revoked_at FROM cafeteria.api_keys')).scalar_one() is None


def test_validation_preserves_selection_and_legacy_expiry_is_visible(admin_client, database_engine):
    data = MultiDict(_create_form() | {'label': 'Retained', 'expires_at': ''})
    data.add('channels', 'patienten')
    response = admin_client.post('/admin/api/keys', data=data)
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert 'value="Retained"' in body
    for element_id in ('api-key-channel-cafeteria', 'api-key-channel-patienten'):
        element = re.search(r'<input[^>]+id="' + element_id + r'"[^>]*>', body)
        assert element and 'checked' in element.group(0)
    assert admin_client.post('/admin/api/keys', data=_create_form()).status_code == 303
    with database_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.api_keys SET expires_at=NULL, channels=ARRAY['cafeteria','patienten']::text[]"))
    body = admin_client.get('/admin/api').get_data(as_text=True)
    assert 'Bestandsschlüssel ohne Ablaufdatum' in body
    assert 'Cafeteria, Patienten' in body


@pytest.mark.parametrize('width', [390, 1440])
def test_no_js_creation_channels_and_revoke_flow(admin_client, browser, width):
    application = admin_client.application
    application.static_folder = str(ROOT / 'reference_scaffold/cafeteria/static')
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with browser.new_context(java_script_enabled=False, reduced_motion='reduce',
                                 viewport={'width': width, 'height': 900}) as context:
            name = application.config['SESSION_COOKIE_NAME']
            cookie = admin_client.get_cookie(name)
            assert cookie is not None
            context.add_cookies([{'name': name, 'value': cookie.value, 'url': origin}])
            page = context.new_page()
            page.goto(origin + '/admin/api')
            expect(page.get_by_role('heading', name='Technische Versionen')).to_be_visible()
            expect(page.locator('[data-api-status]')).not_to_contain_text('Schema-Version')
            expect(page.locator('#api-key-channel-cafeteria')).not_to_be_checked()
            expect(page.locator('#api-key-channel-patienten')).not_to_be_checked()
            expect(page.locator('#api-key-expires')).to_have_attribute('required', '')
            page.locator('summary#api-key-create-title').click()
            page.get_by_label('Bezeichnung', exact=True).fill('Browser policy')
            page.locator('#api-key-scope-preview').check()
            page.locator('#api-key-channel-patienten').check()
            page.get_by_role('button', name='Schlüssel erstellen').click()
            expect(page.locator('[data-new-key]')).to_be_visible()
            row = page.locator('[data-api-keys] tbody tr')
            expect(row.locator('[data-label="Scopes / Kanäle"]')).to_contain_text('Patienten')
            expect(row.locator('[data-label="Scopes / Kanäle"]')).not_to_contain_text('Cafeteria')
            row.get_by_role('button', name='Widerrufen').click()
            expect(page.locator('[data-key-state="revoked"]')).to_be_visible()
            expect(page.locator('[data-new-key]')).to_have_count(0)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
