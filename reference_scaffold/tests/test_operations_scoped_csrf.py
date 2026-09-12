"""Operations tokens bind every form to its actor, location, profile and action."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from werkzeug.datastructures import MultiDict

from cafeteria import db as database
from test_admin_operations_routes import PATH, _get, _load
from test_admin_workflow_routes import DAY, app, client, database_engine  # noqa: F401

FORMS = ('name-staff_guest', 'name-patient', 'weekend-form', 'exception-load',
         'exception-load-patient', 'exception-save')


def _operation_form(client, form_id):  # noqa: F811
    if form_id == 'exception-save':
        return _load(client, profile='patient')
    form = _get(client, form_id)
    if form_id.startswith('exception-load'):
        form.update(date=DAY, meal='LUNCH')
    return form


def _snapshot(engine):
    with engine.connect() as connection:
        return tuple(connection.execute(text(
            f'SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), \'[]\'::jsonb) '
            f'FROM cafeteria.{table} t'
        )).scalar_one() for table in ('settings', 'menu_services', 'menu_weeks', 'audit_events'))


@pytest.mark.parametrize('form_id', FORMS)
def test_operations_reject_raw_cross_action_and_malformed_forms(client, database_engine, form_id):  # noqa: F811
    form = _operation_form(client, form_id)
    other = _get(client, 'schedule-patient')['_csrf']
    before = _snapshot(database_engine)
    for invalid in (
        {**form, '_csrf': form['_csrf'].split('.')[0]},
        {**form, '_csrf': other},
        {**form, 'actor_id': '1'},
        MultiDict([*form.items(), ('_csrf', form['_csrf'])]),
        MultiDict([*form.items(), ('action', form['action'])]),
    ):
        response = client.post(PATH, data=invalid)
        assert response.status_code == 400
        assert response.headers['Cache-Control'] == 'no-store'
        assert _snapshot(database_engine) == before
    assert client.post(PATH + '?profile=patient', data=form).status_code == 400
    assert _snapshot(database_engine) == before


@pytest.mark.parametrize('form_id', FORMS)
def test_operations_reject_location_replay_before_any_write(client, database_engine, form_id):  # noqa: F811
    form = _operation_form(client, form_id)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code,name,timezone,active) "
                                "VALUES ('OTHER','Anderer Standort','UTC',true)"))
    before = _snapshot(database_engine)
    assert client.post(PATH, data=form).status_code == 409
    assert _snapshot(database_engine) == before


@pytest.mark.parametrize('form_id', FORMS)
def test_operations_reject_actor_replay_even_with_same_raw_token(client, app, database_engine, form_id):  # noqa: F811
    form = _operation_form(client, form_id)
    actor = database.upsert_entra_user(database_engine, {
        'tid': '00000000-0000-0000-0000-000000000001',
        'oid': '00000000-0000-0000-0000-000000000003',
        'sub': 'second-operations-admin', 'name': 'Andere Küche',
        'preferred_username': 'other@example.invalid',
    }, ['Cafeteria.Admin'])
    with database_engine.connect() as connection:
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                                     {'id': actor}).scalar_one()
    other = app.test_client()
    with other.session_transaction() as session:
        session['user'] = {'id': actor, 'name': 'Andere Küche'}
        session['authz_version'] = version
        session['_csrf_token'] = form['_csrf'].split('.')[0]
    before = _snapshot(database_engine)
    assert other.post(PATH, data=form).status_code == 409
    assert _snapshot(database_engine) == before


def test_operations_reject_cross_profile_and_load_to_save_replay(client, database_engine):  # noqa: F811
    name = _get(client, 'name-patient')
    staff_name = _get(client, 'name-staff_guest')
    load = _operation_form(client, 'exception-load-patient')
    staff_load = _operation_form(client, 'exception-load')
    save = _load(client, profile='patient')
    staff_save = _load(client)
    before = _snapshot(database_engine)
    for form, token, status in (
        (name, staff_name['_csrf'], 409), (staff_name, name['_csrf'], 409),
        (load, staff_load['_csrf'], 409), (staff_load, load['_csrf'], 409),
        (save, staff_save['_csrf'], 409), (staff_save, save['_csrf'], 409),
        (save, load['_csrf'], 400), (load, save['_csrf'], 400),
    ):
        assert client.post(PATH, data={**form, '_csrf': token}).status_code == status
        assert _snapshot(database_engine) == before


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_native_exception_form_keeps_profile_after_validation_error(client, database_engine, profile):  # noqa: F811
    form_id = 'exception-load' if profile == 'staff_guest' else 'exception-load-patient'
    form = _operation_form(client, form_id)
    before = _snapshot(database_engine)
    response = client.post(PATH, data={**form, 'date': 'bad-date'})
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert body.count('id="date-error"') == 1
    assert f'id="{form_id}-date"' in body
    assert _snapshot(database_engine) == before
    saved = _load(client, profile=profile)
    assert client.post(PATH, data={**saved, 'service_start': '11:30', 'service_end': '13:30'}).status_code == 303
