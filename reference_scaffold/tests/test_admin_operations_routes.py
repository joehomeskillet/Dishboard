"""Real operations forms: authorization, original versions and persisted readback."""
from __future__ import annotations

import re
from html import unescape

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool
from werkzeug.datastructures import MultiDict

from cafeteria import roles
from cafeteria.admin import operations_routes
from cafeteria.operations_settings import get_area_names, get_schedule
from test_admin_output_hubs import hub_app  # noqa: F401
from cafeteria.workflow_partial_store import persist_menu_item, persist_week_header
from cafeteria.workflow_review_context import get_week_review, review_week_context
from test_admin_workflow_routes import (  # noqa: F401
    APP_PASSWORD, DAY, WEEK, _login, _payload, _scope, _session_actor_id, app, client, database_engine,
)

PATH = '/admin/bereiche-zeiten'


def _form(body, form_id):
    match = re.search(rf'<form\b[^>]*\bid="{re.escape(form_id)}"[^>]*>(.*?)</form>', body, re.S)
    assert match, form_id
    result = {}
    for tag in re.findall(r'<input\b[^>]*>', match.group(1)):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        if attrs.get('type') == 'checkbox' and ' checked' not in tag:
            continue
        result[attrs['name']] = unescape(attrs.get('value', 'on'))
    for tag, options in re.findall(r'<select\b([^>]*)>(.*?)</select>', match.group(1), re.S):
        name = re.search(r'name="([^"]+)"', tag).group(1)
        choices = re.findall(r'<option\b([^>]*)>', options)
        choice = next((option for option in choices if ' selected' in option), choices[0])
        result[name] = unescape(re.search(r'value="([^"]*)"', choice).group(1))
    return result


def _get(client, form_id):  # noqa: F811
    response = client.get(PATH)
    assert response.status_code == 200, response.get_data(as_text=True)
    return _form(response.get_data(as_text=True), form_id)


def _load(client, **changes):  # noqa: F811
    form = {**_get(client, 'exception-load'), 'date': DAY, **changes}
    response = client.post(PATH, data=form)
    assert response.status_code == 200, response.get_data(as_text=True)
    return _form(response.get_data(as_text=True), 'exception-save')


def test_get_authorization_csrf_and_shape(client, app, database_engine):  # noqa: F811
    response = client.get(PATH)
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    assert 'Zeiten in Europe/Zurich' in response.get_data(as_text=True)
    assert 'aria-current="page"' in response.get_data(as_text=True)
    valid = _get(client, 'name-patient')
    for form in ({**valid, '_csrf': 'wrong'}, {**valid, 'actor_id': '1'},
                 MultiDict([*valid.items(), ('action', 'save_name_patient')])):
        assert client.post(PATH, data=form).status_code == 400
    assert client.get(PATH + '?profile=patient').status_code == 400
    assert app.test_client().get(PATH).status_code == 401
    for role in ['Cafeteria.Editor', 'Cafeteria.Publisher']:
        other, _ = _login(app, database_engine, [role])
        assert other.get(PATH).status_code == 403
        assert other.post(PATH, data=valid).status_code == 403
        assert f'href="{PATH}"' not in other.get('/admin/cafeteria').get_data(as_text=True)
    assert client.get(PATH).status_code == 401


@pytest.mark.parametrize('where', ['authorization', 'scope', 'context'])
def test_database_outage_covers_authorization_scope_and_context(client, monkeypatch, where):  # noqa: F811
    def down(*args, **kwargs):
        raise OperationalError('unavailable', {}, RuntimeError('offline'))
    if where == 'authorization':
        monkeypatch.setattr(roles, 'load_user_authorization', down)
    elif where == 'scope':
        monkeypatch.setattr(operations_routes, '_scope', down)
    else:
        monkeypatch.setattr(operations_routes, '_template_context', down)
    response = client.get(PATH)
    assert response.status_code == 503
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'vorübergehend' in response.get_data(as_text=True)


def test_names_are_independent_cas_forms_and_preserve_invalid_values(hub_app, database_engine):  # noqa: F811
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Admin'])  # noqa: F811
    first = _get(client, 'name-staff_guest')
    patient = _get(client, 'name-patient')
    assert 'name_patient' not in first and 'name_staff_guest' not in patient
    assert client.post(PATH, data={**first, 'name_staff_guest': 'Restaurant Süd'}).status_code == 303
    assert client.post(PATH, data={**first, 'name_staff_guest': 'Veraltet'}).status_code == 409
    for invalid in ('', 'Preisliste'):
        response = client.post(PATH, data={**patient, 'name_patient': invalid})
        assert response.status_code == 400
        assert 'id="name_patient-error"' in response.get_data(as_text=True)
        assert f'value="{invalid}"' in response.get_data(as_text=True)
    assert get_area_names(database_engine)['staff_guest'] == 'Restaurant Süd'
    assert get_area_names(database_engine)['patient'] == patient['name_patient']
    assert client.post(PATH, data={**patient, 'name_patient': 'Stationen'}).status_code == 303
    for path in ('/admin/screens', '/admin/vorlagen', '/admin/patienten/wochen'):
        response = client.get(path)
        assert response.status_code == 200
        assert 'Stationen' in response.get_data(as_text=True)


def test_weekend_switch_and_seven_schedule_rows_have_cas_and_precise_errors(client, database_engine):  # noqa: F811
    form = _get(client, 'schedule-staff_guest')
    assert all(f'slot_{day}_LUNCH_start' in form for day in range(1, 8))
    invalid = {**form, 'slot_6_LUNCH_start': '14:00', 'slot_6_LUNCH_end': '13:00'}
    response = client.post(PATH, data=invalid)
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert re.search(r'id="staff_guest-slot_6_LUNCH_end"[^>]*aria-invalid="true"[^>]*autofocus', body)
    assert _form(body, 'schedule-staff_guest')['slot_6_LUNCH_start'] == '14:00'
    valid = {**form, 'slot_6_LUNCH_state': 'open', 'slot_6_LUNCH_start': '11:30', 'slot_6_LUNCH_end': '13:30'}
    assert client.post(PATH, data=valid).status_code == 303
    assert client.post(PATH, data=valid).status_code == 409
    scope = _scope(database_engine, _session_actor_id(client), 'staff_guest')
    schedule = get_schedule(database_engine, scope.location_id, 'staff_guest')
    assert schedule.revision == 1 and schedule.slots[(6, 'LUNCH')].start == '11:30'
    switch = _get(client, 'weekend-form')
    assert client.post(PATH, data={**switch, 'allows_weekend': 'on'}).status_code == 303
    assert client.post(PATH, data=switch).status_code == 409
    assert get_schedule(database_engine, scope.location_id, 'staff_guest').allows_weekend
    off = _get(client, 'weekend-form')
    off.pop('allows_weekend')
    assert client.post(PATH, data=off).status_code == 303
    assert get_schedule(database_engine, scope.location_id, 'staff_guest').slots[(6, 'LUNCH')].start == '11:30'


def test_exception_preview_is_read_only_original_version_cannot_be_reloaded_or_retargeted(client, database_engine):  # noqa: F811
    form = _load(client, profile='patient')
    assert form['row_version'] == '0'
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one() == 0
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == 0
    form.update(service_start='11:30', service_end='13:30')
    assert client.post(PATH, data=form).status_code == 303
    assert client.post(PATH, data=form).status_code == 409
    loaded = _load(client, profile='patient')
    assert loaded['row_version'] == '1' and loaded['service_start'] == '11:30'
    assert client.post(PATH, data={**loaded, 'date': '2026-09-01'}).status_code == 409
    assert client.post(PATH, data={**loaded, 'row_version': '9'}).status_code == 409
    assert client.post(PATH, data={**loaded, 'service_end': '14:00'}).status_code == 303
    assert client.post(PATH, data={**loaded, 'service_end': '15:00'}).status_code == 409
    with database_engine.connect() as connection:
        row = connection.execute(text("SELECT row_version,to_char(service_end,'HH24:MI') FROM cafeteria.menu_services")).one()
    assert tuple(row) == (2, '14:00')


def test_exception_menu_preservation_weekend_guard_and_status_mismatch(client, database_engine):  # noqa: F811
    load = _get(client, 'exception-load')
    assert client.post(PATH, data={**load, 'date': '2026-09-05'}).status_code == 400
    patient = _load(client, profile='patient')
    assert client.post(PATH, data=patient).status_code == 303
    scope = _scope(database_engine, _session_actor_id(client))
    persist_menu_item(database_engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(), 0)
    close = _load(client, profile='patient')
    assert client.post(PATH, data={**close, 'service_state': 'closed', 'notice': 'Ferien'}).status_code == 409
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 1
    schedule = _get(client, 'schedule-patient')
    schedule.update(slot_1_LUNCH_state='closed', slot_1_LUNCH_notice='Normalerweise geschlossen')
    assert client.post(PATH, data=schedule).status_code == 303
    assert 'data-kind="open"' in client.get(PATH).get_data(as_text=True)
    closed = _load(client, profile='patient', date='2026-09-01')
    assert client.post(PATH, data={**closed, 'service_state': 'holiday', 'notice': 'Feiertag'}).status_code == 303
    timed = _load(client, profile='patient', date='2026-09-02')
    assert client.post(PATH, data={**timed, 'service_start': '12:00'}).status_code == 303
    body = client.get(PATH).get_data(as_text=True)
    assert all(f'data-kind="{kind}"' in body for kind in ('open', 'closure', 'time'))


def test_defaults_keep_original_week_version_menu_times_and_invalidate_review(client, database_engine):  # noqa: F811
    actor = _session_actor_id(client)
    scope = _scope(database_engine, actor, 'staff_guest')
    persist_week_header(database_engine, scope, WEEK, {'title': 'Testwoche', 'shared_note': 'Erhalten'}, 0)
    persist_menu_item(database_engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    schedule = _get(client, 'schedule-staff_guest')
    schedule.update(slot_1_LUNCH_start='11:30', slot_1_LUNCH_end='13:30', slot_6_LUNCH_state='open')
    assert client.post(PATH, data=schedule).status_code == 303
    switch = _get(client, 'weekend-form')
    assert client.post(PATH, data={**switch, 'allows_weekend': 'on'}).status_code == 303
    original = _form(client.get(f'/admin/cafeteria?week={DAY}').get_data(as_text=True), 'schedule-defaults')
    review = get_week_review(database_engine, scope, WEEK)
    review_week_context(database_engine, scope, WEEK, review['token'])
    assert get_week_review(database_engine, scope, WEEK)['receipt'] is not None
    result = client.post('/admin/cafeteria/wochenvorgaben', data=original)
    assert result.status_code == 303 and result.headers['Cache-Control'] == 'no-store'
    assert client.post('/admin/cafeteria/wochenvorgaben', data=original).status_code == 409
    assert get_week_review(database_engine, scope, WEEK)['receipt'] is None
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one() == 7
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 1
        assert connection.execute(text('SELECT title FROM cafeteria.menu_items')).scalar_one() == 'Kartoffelgratin'
        assert connection.execute(text("SELECT to_char(service_start,'HH24:MI') FROM cafeteria.menu_services WHERE service_date=:day"), {'day': WEEK}).scalar_one() == '11:30'
        assert connection.execute(text('SELECT shared_note FROM cafeteria.menu_weeks')).scalar_one() == 'Erhalten'
    assert 'Wochenvorgaben übernommen.' in client.get(f'/admin/cafeteria?week={DAY}').get_data(as_text=True)
    assert client.post('/admin/cafeteria/wochenvorgaben', data={**original, '_csrf': 'bad'}).status_code == 400


def test_weekend_editor_links_defaults_and_existing_services_survive_switch_off(client, database_engine):  # noqa: F811
    saturday = f'/admin/cafeteria/menu?week={DAY}&day=2026-09-05&meal=LUNCH&option=MENU_1'
    sunday = saturday.replace('2026-09-05', '2026-09-06')
    assert client.get(saturday).status_code == 404
    assert client.get(sunday).status_code == 404
    switch = _get(client, 'weekend-form')
    assert client.post(PATH, data={**switch, 'allows_weekend': 'on'}).status_code == 303
    for path in (saturday, sunday):
        assert client.get(path).status_code == 200
    body = client.get(f'/admin/cafeteria?week={DAY}').get_data(as_text=True)
    assert '14 Menükarten · 7 Tage' in body
    assert 'Vorgabe' in body
    exception = _load(client, date='2026-09-05')
    assert client.post(PATH, data={**exception, 'service_state': 'open'}).status_code == 303
    off = _get(client, 'weekend-form')
    off.pop('allows_weekend')
    assert client.post(PATH, data=off).status_code == 303
    assert client.get(saturday).status_code == 200
    assert client.get(sunday).status_code == 404
    for path in (saturday.replace('2026-09-05', '2026-09-07'),
                 saturday.replace('2026-09-05', '2026-08-30'),
                 saturday.replace('LUNCH', 'DINNER'), saturday.replace('MENU_1', 'INVALID')):
        assert client.get(path).status_code == 404


def test_operations_write_readback_through_actual_application_database_role(client, app, database_engine):  # noqa: F811
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD), poolclass=NullPool)
    app.extensions['cafeteria_db'] = runtime
    try:
        name = _get(client, 'name-patient')
        assert client.post(PATH, data={**name, 'name_patient': 'Stationen'}).status_code == 303
        switch = _get(client, 'weekend-form')
        assert client.post(PATH, data={**switch, 'allows_weekend': 'on'}).status_code == 303
        schedule = _get(client, 'schedule-patient')
        schedule.update(slot_7_DINNER_start='17:30', slot_7_DINNER_end='19:00')
        assert client.post(PATH, data=schedule).status_code == 303
        exception = _load(client, profile='patient', date='2026-09-06', meal='DINNER')
        assert exception['service_start'] == '17:30'
        assert client.post(PATH, data={**exception, 'service_end': '19:30'}).status_code == 303
        assert get_area_names(runtime)['patient'] == 'Stationen'
        assert _load(client, profile='patient', date='2026-09-06', meal='DINNER')['service_end'] == '19:30'
    finally:
        app.extensions['cafeteria_db'] = database_engine
        runtime.dispose()


@pytest.mark.parametrize(('profile', 'field', 'value'), [
    ('staff_guest', 'slot_6_LUNCH_notice', ''),
    ('staff_guest', 'slot_7_LUNCH_start', '25:10'),
    ('patient', 'slot_6_DINNER_notice', 'Preisliste'),
    ('patient', 'slot_7_DINNER_end', 'noon'),
])
def test_later_schedule_fields_have_exact_error_and_original_revision(client, database_engine, profile, field, value):  # noqa: F811
    form = _get(client, f'schedule-{profile}')
    response = client.post(PATH, data={**form, field: value})
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert re.search(rf'id="{profile}-{field}"[^>]*aria-invalid="true"[^>]*autofocus', body)
    shown = _form(body, f'schedule-{profile}')
    assert shown[field] == value and shown['revision'] == '0'
    with database_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.settings WHERE setting_key='operations_schedule'")).scalar_one() == 0


def test_loaded_exception_retains_original_location_expectation(client, database_engine):  # noqa: F811
    original = _load(client, profile='patient')
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code,name,timezone,active) VALUES ('OTHER','Anderer Standort','UTC',true)"))
    response = client.post(PATH, data=original)
    assert response.status_code == 409
    assert 'Zeiten in UTC' in response.get_data(as_text=True)
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one() == 0


def test_schedule_retains_original_location_at_equal_revision(client, database_engine):  # noqa: F811
    original = _get(client, 'schedule-patient')
    assert original['revision'] == '0'
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code,name,timezone,active) VALUES ('OTHER','Anderer Standort','UTC',true)"))
    current = _get(client, 'schedule-patient')
    assert current['revision'] == original['revision']
    response = client.post(PATH, data={**original, 'slot_1_LUNCH_start': '11:30'})
    assert response.status_code == 409
    assert response.headers['Cache-Control'] == 'no-store'
    with database_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.settings WHERE setting_key='operations_schedule'")).scalar_one() == 0
    assert client.post(PATH, data={**current, 'slot_1_LUNCH_start': '12:30'}).status_code == 303
    assert _get(client, 'schedule-patient')['slot_1_LUNCH_start'] == '12:30'


@pytest.mark.parametrize('token_source', ['raw', 'other_profile', 'other_purpose'])
def test_schedule_requires_its_scoped_csrf(client, database_engine, token_source):  # noqa: F811
    form = _get(client, 'schedule-patient')
    if token_source == 'raw':
        token = _get(client, 'name-patient')['_csrf']
    elif token_source == 'other_profile':
        token = _get(client, 'schedule-staff_guest')['_csrf']
    else:
        scope = _scope(database_engine, _session_actor_id(client), 'patient')
        persist_week_header(database_engine, scope, WEEK, {'title': 'Testwoche', 'shared_note': ''}, 0)
        token = _form(client.get(f'/admin/patienten?week={DAY}').get_data(as_text=True), 'schedule-defaults')['_csrf']
    response = client.post(PATH, data={**form, '_csrf': token})
    assert response.status_code == (409 if token_source == 'other_profile' else 400)
    assert response.headers['Cache-Control'] == 'no-store'
    with database_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.settings WHERE setting_key='operations_schedule'")).scalar_one() == 0


@pytest.mark.parametrize('digest', ['', 'a' * 63, 'a' * 65, 'G' * 64, 'ä' * 64])
def test_exception_digest_format_is_rejected_without_writing(client, database_engine, digest):  # noqa: F811
    form = _load(client, profile='patient')
    response = client.post(PATH, data={**form, 'loaded': digest})
    assert response.status_code == 409
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'Bitte den Service erneut laden' in response.get_data(as_text=True)
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one() == 0
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == 0
