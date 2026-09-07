"""Runtime-role PostgreSQL evidence for the bounded screen assignment writer."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from test_master_data_db import make_actor
from test_component_metadata_master_lock_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine,
)

SIGNATURE = 'cafeteria.activate_screen_assignment_v23(bigint,bigint,text,bigint,text,integer)'
CALL = text('SELECT cafeteria.activate_screen_assignment_v23(:actor,:authz,:profile,:version,:template,:renderer)')
KEY = 'screen_assignment.v1.staff_guest.web.week'
LIMIT = 2**63 - 2


@pytest.fixture(autouse=True, scope='module')
def isolated_database():
    raw = os.environ.get('TEST_DATABASE_URL')
    assert raw and (make_url(raw).database or '').startswith(('menuplan_test', 'menuplan_task'))


@pytest.fixture
def screen(seeded_pg16, app_engine):  # noqa: F811
    return seeded_pg16, app_engine, make_actor(seeded_pg16, 'Cafeteria.Admin')


def activate(engine, expectation, **changes):
    params = dict(actor=expectation.user_id, authz=expectation.authz_version, profile='staff_guest',
                  version=0, template='cafeteria-week-text', renderer=1)
    params.update(changes)
    with engine.begin() as connection:
        return connection.execute(CALL, params).scalar_one()


def state(owner):
    with owner.connect() as connection:
        return {table: connection.execute(text(
            f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
        )).all() for table in ('settings', 'audit_events', 'users', 'user_role_cache',
                              'application_roles', 'recipes', 'menu_weeks', 'publication_revisions')}


def failure(engine, expectation, code, **changes):
    with pytest.raises(DBAPIError) as caught:
        activate(engine, expectation, **changes)
    assert caught.value.orig.sqlstate == code


def test_runtime_writer_returns_exact_document_and_one_atomic_audit(screen):
    owner, engine, actor = screen
    before = {'schema_version': 1, 'version': 0, 'template_id': 'cafeteria-week-photo', 'renderer_revision': 1}
    after = activate(engine, actor)
    assert after == {**before, 'version': 1, 'template_id': 'cafeteria-week-text'}
    with owner.connect() as connection:
        row = connection.execute(text("SELECT actor_user_id,profile_code,details FROM cafeteria.audit_events WHERE action='screen_assignment.activate'")).one()
        assert row.actor_user_id == actor.user_id and row.profile_code == 'staff_guest'
        assert row.details == {'actor_authz_version': actor.authz_version, 'profile': 'staff_guest',
                               'target': 'public.cafeteria_week', 'before': before, 'after': after}
        assert connection.execute(text('SELECT setting_value FROM cafeteria.settings WHERE setting_key=:key'), {'key': KEY}).scalar_one() == after
        assert not connection.execute(text("SELECT has_table_privilege('cafeteria_app','cafeteria.audit_events','INSERT')")).scalar_one()


def test_virtual_photo_noop_rolls_back_initial_insert(screen):
    owner, engine, actor = screen
    before = state(owner)
    failure(engine, actor, '55000', template='cafeteria-week-photo')
    assert state(owner) == before


@pytest.mark.parametrize('changes', [
    {'profile': None}, {'profile': 'other'}, {'profile': 'patient'},
    {'template': None}, {'template': 'unknown'}, {'renderer': None}, {'renderer': 2},
    {'version': None}, {'version': -1}, {'version': LIMIT + 1},
])
def test_sql_rejects_invalid_parameters_without_any_change(screen, changes):
    owner, engine, actor = screen
    before = state(owner)
    failure(engine, actor, 'P2001', **changes)
    assert state(owner) == before


@pytest.mark.parametrize('document', [
    None, [], {}, {'schema_version': 2, 'version': 0, 'template_id': 'cafeteria-week-photo', 'renderer_revision': 1},
    *[{'schema_version': 1, 'version': value, 'template_id': 'cafeteria-week-photo', 'renderer_revision': 1}
      for value in (True, '0', -1, 0.5, LIMIT + 1, 10**100)],
    {'schema_version': True, 'version': 0, 'template_id': 'cafeteria-week-photo', 'renderer_revision': 1},
    {'schema_version': 1, 'version': 0, 'template_id': 'patient-week-photo', 'renderer_revision': 1},
    {'schema_version': 1, 'version': 0, 'template_id': 'unknown', 'renderer_revision': 1},
    {'schema_version': 1, 'version': 0, 'template_id': 'cafeteria-week-photo', 'renderer_revision': True},
    {'schema_version': 1, 'version': 0, 'template_id': 'cafeteria-week-photo', 'renderer_revision': 2},
    {'schema_version': 1, 'version': 0, 'template_id': 'cafeteria-week-photo', 'renderer_revision': 1, 'extra': 0},
])
def test_invalid_persisted_json_is_unavailable_and_never_repaired(screen, document):
    owner, engine, actor = screen
    with owner.begin() as connection:
        connection.execute(text("INSERT INTO cafeteria.settings(setting_key,setting_value) VALUES(:key,CAST(:value AS jsonb))"),
                           {'key': KEY, 'value': json.dumps(document)})
    before = state(owner)
    failure(engine, actor, 'P2004')
    assert state(owner) == before


def test_stale_same_state_cap_and_both_profiles(screen):
    owner, engine, actor = screen
    activate(engine, actor)
    before = state(owner)
    failure(engine, actor, '55000', version=0, template='cafeteria-week-photo')
    failure(engine, actor, '55000', version=1)
    assert state(owner) == before
    assert activate(engine, actor, version=1, template='cafeteria-week-photo')['version'] == 2
    patient = activate(engine, actor, profile='patient', template='patient-week-text')
    assert patient['template_id'] == 'patient-week-text' and patient['version'] == 1
    assert activate(engine, actor, profile='patient', version=1, template='patient-week-photo')['version'] == 2
    with owner.begin() as connection:
        connection.execute(text("UPDATE cafeteria.settings SET setting_value=jsonb_set(setting_value,'{version}',to_jsonb(CAST(:cap AS bigint))) WHERE setting_key=:key"),
                           {'cap': LIMIT, 'key': KEY})
    before = state(owner)
    failure(engine, actor, '55000', version=LIMIT)
    assert state(owner) == before


@pytest.mark.parametrize('mode', ['stale', 'disabled', 'role_removed', 'role_inactive', 'publisher', 'invalid_actor'])
def test_original_actor_version_and_current_admin_capability(screen, mode):
    owner, engine, actor = screen
    changes = {}
    if mode == 'stale':
        changes['authz'] = actor.authz_version + 1
    elif mode == 'invalid_actor':
        changes['actor'] = None
    elif mode == 'publisher':
        actor = make_actor(owner)
    else:
        with owner.begin() as connection:
            if mode == 'disabled':
                connection.execute(text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'), {'id': actor.user_id})
            elif mode == 'role_removed':
                connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
            else:
                connection.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Admin'"))
    before = state(owner)
    failure(engine, actor, '42501', **changes)
    assert state(owner) == before


def test_two_first_writers_one_wins_with_different_original_actors(screen):
    owner, engine, first = screen
    second = make_actor(owner, 'Cafeteria.Admin')
    barrier = Barrier(2)

    def write(actor):
        barrier.wait(timeout=10)
        try:
            return activate(engine, actor)['version']
        except DBAPIError as error:
            return error.orig.sqlstate
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, (first, second)))
    assert sorted(map(str, results)) == ['1', '55000']
    with owner.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action='screen_assignment.activate'")).scalar_one() == 1
        assert connection.execute(text('SELECT count(*) FROM cafeteria.settings WHERE setting_key=:key'), {'key': KEY}).scalar_one() == 1


def test_audit_failure_rolls_back_settings_and_first_insert(screen):
    owner, engine, actor = screen
    before = state(owner)
    with owner.begin() as connection:
        connection.execute(text("""CREATE FUNCTION cafeteria.reject_screen_audit_test() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic audit failure'; END $$"""))
        connection.execute(text("""CREATE TRIGGER reject_screen_audit_test BEFORE INSERT ON cafeteria.audit_events
            FOR EACH ROW WHEN (NEW.action='screen_assignment.activate')
            EXECUTE FUNCTION cafeteria.reject_screen_audit_test()"""))
    failure(engine, actor, 'P0001')
    assert state(owner) == before


def test_definer_permissions_search_path_and_no_broad_audit_grant(screen):
    owner, engine, actor = screen
    with owner.connect() as connection:
        row = connection.execute(text("""SELECT p.prosecdef,p.proconfig,p.proowner=n.nspowner,
            has_function_privilege('cafeteria_app',p.oid,'EXECUTE'),
            has_function_privilege('cafeteria_backup',p.oid,'EXECUTE'),
            has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE'),
            has_function_privilege('public',p.oid,'EXECUTE')
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE p.oid=to_regprocedure(:signature)"""),
            {'signature': SIGNATURE}).one()
        assert tuple(row) == (True, ['search_path=pg_catalog, cafeteria, pg_temp'], True, True, False, False, False)
        assert not connection.execute(text("SELECT has_table_privilege('cafeteria_app','cafeteria.audit_events','INSERT,UPDATE,DELETE,TRUNCATE')")).scalar_one()
        assert not connection.execute(text("SELECT has_sequence_privilege('cafeteria_app','cafeteria.audit_events_id_seq','USAGE,UPDATE')")).scalar_one()
    with pytest.raises(DBAPIError) as caught:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO cafeteria.audit_events(action,entity_type) VALUES('forbidden-test','screen')"))
    assert caught.value.orig.sqlstate == '42501'
    assert activate(engine, actor)['version'] == 1


def test_canonical_isolation_and_role_lock_timeout(screen):
    owner, engine, actor = screen
    before = state(owner)
    with pytest.raises(DBAPIError) as caught:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            connection.execute(CALL, dict(actor=actor.user_id, authz=actor.authz_version, profile='staff_guest',
                                         version=0, template='cafeteria-week-text', renderer=1))
    assert caught.value.orig.sqlstate == '25001'
    with owner.begin() as connection:
        connection.execute(text('SELECT role_code FROM cafeteria.application_roles ORDER BY role_code FOR UPDATE'))
        failure(engine, actor, '55P03')
    assert state(owner) == before
