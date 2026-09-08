"""Real issuer-only authentication decisions, without submitted identity data."""
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from test_auth_routes import auth_app, _provision  # noqa: F401

CALL = text('''SELECT cafeteria.record_auth_access_v25(
    CAST(:event AS uuid),:provider,:action,:reason,:actor,:version)''')


def arguments(**changes):
    return dict(event=str(uuid4()), provider='local', action='auth.login.rejected',
                reason='credentials', actor=None, version=None) | changes


def test_issuer_records_bounded_unknown_identity_once(auth_app):  # noqa: F811
    app, owner, issuer = auth_app
    event = arguments()
    with issuer.begin() as connection:
        assert str(connection.execute(CALL, event).scalar_one()) == event['event']
    with owner.connect() as connection:
        before = connection.execute(text('SELECT * FROM cafeteria.audit_events WHERE public_id=CAST(:event AS uuid)'), event).one()
        sequence = connection.execute(text('SELECT last_value FROM cafeteria.audit_events_id_seq')).scalar_one()
    with issuer.begin() as connection:
        assert str(connection.execute(CALL, event).scalar_one()) == event['event']
    with owner.connect() as connection:
        after = connection.execute(text('SELECT * FROM cafeteria.audit_events WHERE public_id=CAST(:event AS uuid)'), event).one()
        assert connection.execute(text('SELECT last_value FROM cafeteria.audit_events_id_seq')).scalar_one() == sequence
    assert after == before
    assert after.actor_user_id is None and after.entity_type == 'authentication'
    assert after.entity_public_id is None and after.profile_code is None
    assert after.details == {'provider': 'local', 'reason': 'credentials', 'authz_version': None}
    with pytest.raises(DBAPIError) as caught:
        with issuer.begin() as connection:
            connection.execute(CALL, event | {'reason': 'flow'})
    assert caught.value.orig.sqlstate == 'P2501'


def test_accepted_requires_current_verified_identity_and_app_cannot_issue(auth_app):  # noqa: F811
    app, owner, issuer = auth_app
    actor = _provision(issuer, owner)
    with owner.connect() as connection:
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': actor}).scalar_one()
    event = arguments(action='auth.login.accepted', reason=None, actor=actor, version=version)
    with issuer.begin() as connection:
        connection.execute(CALL, event)
    for engine in (app.extensions['cafeteria_db'],):
        with pytest.raises(DBAPIError) as caught:
            with engine.begin() as connection:
                connection.execute(CALL, arguments())
        assert caught.value.orig.sqlstate == '42501'
    with pytest.raises(DBAPIError) as caught:
        with issuer.begin() as connection:
            connection.execute(CALL, event | {'event': str(uuid4()), 'version': version + 1})
    assert caught.value.orig.sqlstate == '42501'


@pytest.mark.parametrize('change', [
    {'event': None}, {'provider': None}, {'provider': 'local '}, {'provider': 'system'},
    {'action': None}, {'action': 'auth.forged'}, {'reason': 'unbounded-private-reason'},
    {'reason': None}, {'actor': 1}, {'version': 1}, {'actor': -1, 'version': -1},
    {'action': 'auth.login.accepted', 'reason': None},
    {'action': 'auth.login.unavailable', 'reason': 'credentials'},
    {'action': 'auth.logout.requested', 'reason': 'flow'},
    {'action': 'auth.frontchannel.requested', 'reason': 'flow'},
])
def test_malformed_event_never_writes(auth_app, change):  # noqa: F811
    _, owner, issuer = auth_app
    with owner.connect() as connection:
        before = connection.execute(text('SELECT to_jsonb(a) FROM cafeteria.audit_events a ORDER BY id')).all()
    with pytest.raises(DBAPIError) as caught:
        with issuer.begin() as connection:
            connection.execute(CALL, arguments(**change))
    assert caught.value.orig.sqlstate == 'P2501'
    with owner.connect() as connection:
        assert connection.execute(text('SELECT to_jsonb(a) FROM cafeteria.audit_events a ORDER BY id')).all() == before


@pytest.mark.parametrize('change', ['disabled', 'provider', 'version', 'missing', 'roles', 'inactive_role'])
def test_verified_actor_guard_rejects_invalid_current_identity(auth_app, change):  # noqa: F811
    _, owner, issuer = auth_app
    actor = _provision(issuer, owner)
    with owner.begin() as connection:
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': actor}).scalar_one()
        if change == 'disabled':
            connection.execute(text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'), {'id': actor})
        if change == 'roles':
            connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor})
        if change == 'inactive_role':
            connection.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Editor'"))
    event = arguments(action='auth.login.accepted', reason=None, actor=actor, version=version)
    if change == 'provider':
        event['provider'] = 'entra'
    if change == 'version':
        event['version'] += 1
    if change == 'missing':
        event['actor'] = 9223372036854775807
    with pytest.raises(DBAPIError) as caught:
        with issuer.begin() as connection:
            connection.execute(CALL, event)
    assert caught.value.orig.sqlstate == '42501'


def test_concurrent_same_event_has_one_row_and_conflicting_tuple_is_rejected(auth_app):  # noqa: F811
    from concurrent.futures import ThreadPoolExecutor

    _, owner, issuer = auth_app
    event = arguments()

    def write():
        with issuer.begin() as connection:
            return connection.execute(CALL, event).scalar_one()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: write(), range(2)))
    assert [str(value) for value in outcomes] == [event['event'], event['event']]
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.audit_events WHERE public_id=CAST(:event AS uuid)'), event).scalar_one() == 1
    for change in ({'provider': 'entra'}, {'action': 'auth.login.unavailable', 'reason': 'unavailable'}):
        with pytest.raises(DBAPIError) as caught:
            with issuer.begin() as connection:
                connection.execute(CALL, event | change)
        assert caught.value.orig.sqlstate == 'P2501'


def test_v24_upgrade_preserves_all_history_and_matches_fresh_function(auth_app):  # noqa: F811
    from cafeteria import db as database
    from test_auth_routes import ROOT

    _, owner, _ = auth_app
    contract_sql = text('''SELECT p.prosrc,p.prosecdef,p.proconfig,p.proowner=n.nspowner,p.proacl::text
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE p.oid='cafeteria.record_auth_access_v25(uuid,text,text,text,bigint,bigint)'::regprocedure''')
    with owner.begin() as connection:
        fresh = connection.execute(contract_sql).one()
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    plan = database.migration_plan(ROOT / 'database/schema.sql')
    for migration in plan:
        if migration.version < 25:
            database._execute_migration(owner, migration)
    database._execute_script(owner, str(ROOT / 'database/seed.sql'))
    with owner.connect() as connection:
        assert connection.execute(text('SELECT max(version) FROM cafeteria.schema_migrations')).scalar_one() == 24
        before = connection.execute(text('SELECT to_jsonb(a) FROM cafeteria.audit_events a ORDER BY id')).all()
        ledger = connection.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m ORDER BY version')).all()
    database.run_migrations(owner, ROOT / 'database/schema.sql')
    database._execute_script(owner, str(ROOT / 'database/permissions.sql'))
    with owner.connect() as connection:
        assert connection.execute(contract_sql).one() == fresh
        assert fresh.prosecdef and fresh.proconfig == ['search_path=pg_catalog, cafeteria, pg_temp']
        assert connection.execute(text('SELECT to_jsonb(a) FROM cafeteria.audit_events a ORDER BY id')).all() == before
        assert connection.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m WHERE version<25 ORDER BY version')).all() == ledger
        for role, allowed in [('cafeteria_app', False), ('cafeteria_backup', False), ('cafeteria_auth_issuer', True)]:
            privileges = connection.execute(text('''SELECT
                has_function_privilege(:role,'cafeteria.record_auth_access_v25(uuid,text,text,text,bigint,bigint)','EXECUTE'),
                has_table_privilege(:role,'cafeteria.audit_events','INSERT,UPDATE,DELETE,TRUNCATE')'''), {'role': role}).one()
            assert tuple(privileges) == (allowed, False)
    assert database.validate_database(owner)['auth_issuer_ready']


def test_accepted_retry_returns_original_row_after_identity_changes(auth_app):  # noqa: F811
    _, owner, issuer = auth_app
    actor = _provision(issuer, owner)
    with owner.connect() as connection:
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': actor}).scalar_one()
    event = arguments(action='auth.login.accepted', reason=None, actor=actor, version=version)
    with issuer.begin() as connection:
        connection.execute(CALL, event)
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'), {'id': actor})
    with issuer.begin() as connection:
        assert str(connection.execute(CALL, event).scalar_one()) == event['event']
