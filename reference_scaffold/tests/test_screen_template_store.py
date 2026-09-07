"""Screen assignments use actual runtime-role PostgreSQL CAS and audit."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import monotonic

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import DBAPIError

from cafeteria import screen_templates as screens
from test_admin_workflow_routes import APP_PASSWORD, _login, app, database_engine  # noqa: F401


def actor(application, engine):
    client, user = _login(application, engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        return user, session['authz_version']


def state(engine):
    with engine.connect() as connection:
        return tuple(connection.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).all()
                     for table in ('settings', 'audit_events'))


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_virtual_read_runtime_write_and_audit_are_atomic(app, database_engine, profile):  # noqa: F811
    user, version = actor(app, database_engine)
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD), poolclass=NullPool)
    try:
        before = state(database_engine)
        with runtime.connect() as connection:
            original = screens.read_assignment(connection, profile)
        assert original.version == 0 and original.template.show_menu_images
        assert state(database_engine) == before
        selected = screens.choices(profile)[1]
        result = screens.activate(runtime, profile, user, version, 0, selected.id, 1)
        assert result.version == 1 and not result.template.show_menu_images
        with runtime.connect() as connection:
            assert screens.read_assignment(connection, profile) == result
        after = state(database_engine)
        assert len(after[0]) == len(before[0]) + 1 and len(after[1]) == len(before[1]) + 1
        with database_engine.connect() as connection:
            audit = connection.execute(text("SELECT actor_user_id,profile_code,details FROM cafeteria.audit_events WHERE action='screen_assignment.activate'")).one()
        assert audit.actor_user_id == user and audit.profile_code == profile
        assert audit.details == {'actor_authz_version': version, 'profile': profile,
            'target': 'public.cafeteria_week' if profile == 'staff_guest' else 'public.patient_week',
            'before': original.document(), 'after': result.document()}
        with pytest.raises(screens.ScreenConflict):
            screens.activate(runtime, profile, user, version, 1, selected.id, 1)
        assert state(database_engine) == after
    finally:
        runtime.dispose()


def test_first_writer_race_has_one_winner(app, database_engine):  # noqa: F811
    user, version = actor(app, database_engine)
    barrier = Barrier(2)
    def write(_):
        barrier.wait(timeout=10)
        try:
            return screens.activate(database_engine, 'patient', user, version, 0, 'patient-week-text', 1).version
        except screens.ScreenConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(map(str, workers.map(write, range(2)))) == ['1', 'conflict']


@pytest.mark.parametrize('value', [True, -1, 2**63 - 1, '0'])
def test_strict_versions_rejected_before_write(app, database_engine, value):  # noqa: F811
    user, version = actor(app, database_engine)
    before = state(database_engine)
    with pytest.raises(screens.ScreenValidation):
        screens.activate(database_engine, 'patient', user, version, value, 'patient-week-text', 1)
    assert state(database_engine) == before


def test_virtual_same_state_and_stale_cas_leave_no_settings_or_audit(app, database_engine):  # noqa: F811
    user, version = actor(app, database_engine)
    before = state(database_engine)
    with pytest.raises(screens.ScreenConflict):
        screens.activate(database_engine, 'patient', user, version, 0, 'patient-week-photo', 1)
    assert state(database_engine) == before
    screens.activate(database_engine, 'patient', user, version, 0, 'patient-week-text', 1)
    before = state(database_engine)
    with pytest.raises(screens.ScreenConflict):
        screens.activate(database_engine, 'patient', user, version, 0, 'patient-week-photo', 1)
    assert state(database_engine) == before


@pytest.mark.parametrize('kind', ['authz', 'role', 'disabled'])
def test_original_actor_revalidated_inside_writer(app, database_engine, kind):  # noqa: F811
    user, version = actor(app, database_engine)
    with database_engine.begin() as connection:
        if kind == 'authz':
            connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:id'), {'id': user})
        elif kind == 'disabled':
            connection.execute(text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'), {'id': user})
        else:
            connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': user})
    before = state(database_engine)
    with pytest.raises(PermissionError):
        screens.activate(database_engine, 'patient', user, version, 0, 'patient-week-text', 1)
    assert state(database_engine) == before


def test_original_actor_lock_timeout_is_bounded_and_atomic(app, database_engine):  # noqa: F811
    user, version = actor(app, database_engine)
    before = state(database_engine)
    with database_engine.begin() as blocker:
        blocker.execute(text('SELECT id FROM cafeteria.users WHERE id=:id FOR UPDATE'), {'id': user})
        with ThreadPoolExecutor(max_workers=1) as worker:
            start = monotonic()
            future = worker.submit(screens.activate, database_engine, 'patient', user, version, 0, 'patient-week-text', 1)
            with pytest.raises(DBAPIError) as failure:
                future.result(timeout=12)
            assert getattr(failure.value.orig, 'sqlstate', None) == '55P03'
            assert 4 <= monotonic() - start < 10
    assert state(database_engine) == before


@pytest.mark.parametrize('changes', [
    {'version': True}, {'version': 2**63 - 1}, {'schema_version': 2}, {'schema_version': True},
    {'template_id': 'unknown'}, {'template_id': 'cafeteria-week-text'},
    {'renderer_revision': True}, {'renderer_revision': 2}, {'extra': 1},
])
def test_corrupt_document_never_becomes_default(app, database_engine, changes):  # noqa: F811
    actor(app, database_engine)
    value = {'schema_version': 1, 'version': 0, 'template_id': 'patient-week-photo', 'renderer_revision': 1} | changes
    with database_engine.begin() as connection:
        connection.execute(text('INSERT INTO cafeteria.settings(setting_key,setting_value) VALUES (:key,CAST(:value AS jsonb))'),
                           {'key': screens.key('patient'), 'value': json.dumps(value)})
    before = state(database_engine)
    with database_engine.connect() as connection, pytest.raises(screens.ScreenStateError):
        screens.read_assignment(connection, 'patient')
    assert state(database_engine) == before
