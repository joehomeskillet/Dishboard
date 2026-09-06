"""Real transaction ordering: OPS writes and IAM revocation cannot pass each other."""
from __future__ import annotations

# ruff: noqa: F401, F811
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool

from cafeteria.operations_settings import (
    get_area_names, get_area_profiles, get_schedule, save_area_name,
    save_schedule, save_weekend_switch,
)
from test_admin_workflow_routes import APP_PASSWORD, _login, app, database_engine
from test_operations_settings_db import STAFF_AREA_NAME, _admin, _location_id, _raw_slots


def _write(engine, actor, version, location, operation):
    if operation == 'schedule':
        return save_schedule(engine, actor, version, location, 'staff_guest', 0, _raw_slots('staff_guest'))
    if operation == 'name':
        return save_area_name(engine, actor, version, 'staff_guest', STAFF_AREA_NAME, 'Bistro')
    return save_weekend_switch(engine, actor, version, 'staff_guest', False, True)


def _revoke(connection, actor, change):
    statements = {
        'version': 'UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:actor',
        'disabled': 'UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:actor',
        'role': "UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Admin'",
        'membership': "DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor AND role_code='Cafeteria.Admin'",
    }
    connection.execute(text(statements[change]), {'actor': actor})


def _assert_blocked(engine, pid):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            if connection.execute(text('SELECT cardinality(pg_blocking_pids(:pid))'),
                                  {'pid': pid}).scalar_one() > 0:
                return
        time.sleep(0.02)
    pytest.fail('Concurrent transaction did not wait on the expected PostgreSQL lock.')


@pytest.mark.parametrize('operation', ['schedule', 'name', 'weekend'])
@pytest.mark.parametrize('change', ['version', 'disabled', 'role', 'membership'])
@pytest.mark.parametrize('writer_first', [True, False], ids=['write-before-revoke', 'revoke-before-write'])
def test_actor_and_role_locks_order_all_writes(app, database_engine, operation, change, writer_first):
    actor, version = _admin(app, database_engine)
    location = _location_id(database_engine)
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD),
                            poolclass=NullPool)
    guard_reached, release_guard, revoke_started = Event(), Event(), Event()
    writer_pids, revoker_pids = [], []

    def before_guard(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT cafeteria.lock_operations_actor'):
            writer_pids.append(connection.execute(text('SELECT pg_backend_pid()')).scalar_one())
            if not writer_first:
                guard_reached.set()

    def after_guard(connection, cursor, statement, parameters, context, executemany):
        if writer_first and statement.startswith('SELECT cafeteria.lock_operations_actor'):
            guard_reached.set()
            assert release_guard.wait(4), 'Coordinator did not release guarded writer.'

    def revoke():
        with database_engine.begin() as connection:
            revoker_pids.append(connection.execute(text('SELECT pg_backend_pid()')).scalar_one())
            revoke_started.set()
            _revoke(connection, actor, change)

    event.listen(runtime, 'before_cursor_execute', before_guard)
    event.listen(runtime, 'after_cursor_execute', after_guard)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            if writer_first:
                writer = pool.submit(_write, runtime, actor, version, location, operation)
                try:
                    assert guard_reached.wait(3)
                    revoker = pool.submit(revoke)
                    assert revoke_started.wait(3)
                    _assert_blocked(database_engine, revoker_pids[0])
                finally:
                    release_guard.set()
                assert writer.result(timeout=5) in (1, True, 'Bistro')
                revoker.result(timeout=5)
            else:
                with database_engine.begin() as connection:
                    _revoke(connection, actor, change)
                    writer = pool.submit(_write, runtime, actor, version, location, operation)
                    assert guard_reached.wait(3)
                    _assert_blocked(database_engine, writer_pids[0])
                with pytest.raises(PermissionError):
                    writer.result(timeout=5)
                assert get_area_names(database_engine)['staff_guest'] == STAFF_AREA_NAME
                assert get_area_profiles(database_engine)['staff_guest']['allows_weekend'] is False
                assert get_schedule(database_engine, location, 'staff_guest').revision == 0
    finally:
        release_guard.set()
        event.remove(runtime, 'before_cursor_execute', before_guard)
        event.remove(runtime, 'after_cursor_execute', after_guard)
        runtime.dispose()


@pytest.mark.parametrize('operation', ['schedule', 'name', 'weekend'])
@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_operations_keep_settings_write_authorization(app, database_engine, operation, role):
    client, actor = _login(app, database_engine, [role])
    with client.session_transaction() as session:
        version = session['authz_version']
    with pytest.raises(PermissionError):
        _write(database_engine, actor, version, _location_id(database_engine), operation)


def test_actor_guard_is_app_only_and_rejects_snapshot_isolation(app, database_engine):
    actor, version = _admin(app, database_engine)
    with database_engine.connect() as connection:
        grants = {role: connection.execute(text(
            "SELECT has_function_privilege(:role,'cafeteria.lock_operations_actor(bigint,bigint)','EXECUTE')"
        ), {'role': role}).scalar_one() for role in (
            'cafeteria_app', 'cafeteria_backup', 'cafeteria_auth_issuer', 'public'
        )}
    assert grants == {'cafeteria_app': True, 'cafeteria_backup': False,
                      'cafeteria_auth_issuer': False, 'public': False}
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError) as error:
        with database_engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            connection.execute(text('SELECT cafeteria.lock_operations_actor(:actor,:version)'),
                               {'actor': actor, 'version': version})
    assert error.value.orig.sqlstate == '25001'
