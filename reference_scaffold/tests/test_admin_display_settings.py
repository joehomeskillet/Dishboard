"""Global presentation settings use the existing settings table and admin authorization."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from werkzeug.datastructures import MultiDict

from cafeteria.admin import display_routes  # noqa: F401 - register settings with shared blueprint
from cafeteria.display_settings import get_admin_density, set_admin_density

from test_admin_workflow_routes import (  # noqa: F401
    APP_PASSWORD, _hidden, _login, app, client, database_engine,
)

PATH = '/admin/design/darstellung'


def test_default_and_global_save_preserve_other_settings(client, database_engine):  # noqa: F811
    response = client.get(PATH)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    html = response.get_data(as_text=True)
    assert 'data-density="compact"' in html
    csrf = _hidden(html, '_csrf', form_action=PATH)
    with client.session_transaction() as session:
        actor = session['user']['id']
    with database_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO cafeteria.settings(setting_key, setting_value)
            VALUES ('unrelated_setting', jsonb_build_object('keep', true))
        """))
    for value in ('comfortable', 'compact'):
        result = client.post(PATH, data={'_csrf': csrf, 'admin_density': value})
        assert result.status_code == 303 and result.location == PATH
        assert result.headers['Cache-Control'] == 'no-store'
        assert f'data-density="{value}"' in client.get('/admin/patienten').get_data(as_text=True)
        with database_engine.connect() as connection:
            row = connection.execute(text("""
                SELECT location_id, profile_id, setting_value, updated_by, updated_at
                FROM cafeteria.settings WHERE setting_key='admin_density'
            """)).mappings().one()
            assert row['location_id'] is None and row['profile_id'] is None
            assert row['setting_value'] == value and row['updated_by'] == actor
            assert row['updated_at'] is not None
            assert connection.execute(text("""
                SELECT setting_value FROM cafeteria.settings WHERE setting_key='unrelated_setting'
            """)).scalar_one() == {'keep': True}


@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_only_current_admin_can_read_or_change_settings(app, database_engine, role):  # noqa: F811
    user, _ = _login(app, database_engine, [role])
    assert user.get(PATH).status_code == 403
    assert user.post(PATH, data={'_csrf': 'workflow-csrf', 'admin_density': 'comfortable'}).status_code == 403
    html = user.get('/admin/cafeteria').get_data(as_text=True)
    assert 'data-density="compact"' in html
    assert f'href="{PATH}"' not in html
    with database_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.settings WHERE setting_key='admin_density'")).scalar_one() == 0


@pytest.mark.parametrize('value', ['', 'dense', 'COMPACT', ' compact ', 'comfortable<script>', 'true'])
def test_invalid_density_has_field_error_and_does_not_write(client, database_engine, value):  # noqa: F811
    response = client.post(PATH, data={'_csrf': 'workflow-csrf', 'admin_density': value})
    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'
    body = response.get_data(as_text=True)
    assert 'id="admin-density-error"' in body and 'aria-invalid="true"' in body
    with database_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.settings WHERE setting_key='admin_density'")).scalar_one() == 0


def test_csrf_duplicates_override_query_and_stale_session_are_rejected(client, app, database_engine):  # noqa: F811
    valid = {'_csrf': 'workflow-csrf', 'admin_density': 'comfortable'}
    for fields in (
        {**valid, '_csrf': 'wrong'}, {'admin_density': 'comfortable'},
        {**valid, 'location_id': '1'}, {**valid, 'actor_id': '1'},
        MultiDict([*valid.items(), ('admin_density', 'compact')]),
        MultiDict([*valid.items(), ('_csrf', 'workflow-csrf')]),
    ):
        assert client.post(PATH, data=fields).status_code == 400
    assert client.get(PATH + '?profile=patient').status_code == 400
    assert client.post(PATH + '?admin_density=compact', data=valid).status_code == 400
    _login(app, database_engine, ['Cafeteria.Editor'])
    assert client.post(PATH, data=valid).status_code == 401
    assert app.test_client().get(PATH).status_code == 401
    with database_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.settings WHERE setting_key='admin_density'")).scalar_one() == 0


def test_real_app_role_can_save_only_for_current_admin_and_all_users_see_it(app, database_engine):  # noqa: F811
    admin, actor = _login(app, database_engine, ['Cafeteria.Admin'])
    with admin.session_transaction() as session:
        version = session['authz_version']
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD), poolclass=NullPool)
    try:
        set_admin_density(runtime, actor, version, 'comfortable')
        assert get_admin_density(runtime) == 'comfortable'
        with pytest.raises(PermissionError):
            set_admin_density(runtime, actor, version + 1, 'compact')
        editor, _ = _login(app, database_engine, ['Cafeteria.Editor'])
        with editor.session_transaction() as session:
            editor_version = session['authz_version']
        with pytest.raises(PermissionError):
            set_admin_density(runtime, actor, editor_version, 'compact')
        for family in ('cafeteria', 'patienten'):
            response = editor.get(f'/admin/{family}')
            assert response.status_code == 200
            body = response.get_data(as_text=True)
            assert 'data-density="comfortable"' in body
            assert f'href="{PATH}"' not in body
        assert get_admin_density(runtime) == 'comfortable'
    finally:
        runtime.dispose()


def test_scoped_settings_and_malformed_values_cannot_override_global_default(client, database_engine):  # noqa: F811
    with database_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO cafeteria.settings(location_id, setting_key, setting_value)
            SELECT id, 'admin_density', to_jsonb('comfortable'::text) FROM cafeteria.locations
        """))
        connection.execute(text("""
            INSERT INTO cafeteria.settings(setting_key, setting_value)
            VALUES ('admin_density', jsonb_build_object('compact', 'invalid'))
        """))
    assert get_admin_density(database_engine) == 'compact'
    response = client.get(PATH)
    assert response.status_code == 200 and 'data-density="compact"' in response.get_data(as_text=True)
    assert client.post(PATH, data={'_csrf': 'workflow-csrf', 'admin_density': 'comfortable'}).status_code == 303
    assert get_admin_density(database_engine) == 'comfortable'
