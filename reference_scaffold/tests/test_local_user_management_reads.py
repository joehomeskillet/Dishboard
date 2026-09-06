from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict
from uuid import UUID, uuid4

from flask import Flask, session
import pytest
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool
from werkzeug.exceptions import Forbidden, Unauthorized

from cafeteria.auth import local_users as users
from test_auth_database import (
    APP_PASSWORD, DEFAULT_ACTOR, _role_database_url, owner_engine,
)
from test_local_user_management_db import issuer_engine

__all__ = ['owner_engine', 'issuer_engine']


@pytest.fixture
def app_reader(owner_engine: Engine) -> Iterator[Engine]:
    engine = create_engine(_role_database_url('cafeteria_app', APP_PASSWORD), poolclass=NullPool)
    app = Flask(__name__)
    app.secret_key = 'isolated-reader-test-key'
    app.extensions['cafeteria_db'] = engine
    with owner_engine.connect() as connection:
        actor = connection.execute(text('SELECT id, authz_version FROM cafeteria.users '
            'WHERE preferred_username=:name'), {'name': DEFAULT_ACTOR}).one()
    try:
        with app.test_request_context():
            session['user'] = {'id': actor.id}
            session['authz_version'] = actor.authz_version
            yield engine
    finally:
        engine.dispose()


def _seed(owner: Engine, count: int = 1) -> list[tuple[int, UUID]]:
    result = []
    with owner.begin() as connection:
        for index in range(count):
            row = connection.execute(text("INSERT INTO cafeteria.users(auth_provider,display_name) "
                "VALUES ('local',:name) RETURNING id,public_id"),
                {'name': f'Lokales Konto {index:03d}'}).one()
            connection.execute(text('INSERT INTO cafeteria.local_credentials(user_id,username,password_hash) '
                "VALUES (:id,:name,'pbkdf2:sha256:1000$test$deadbeef')"),
                {'id': row.id, 'name': f'local.{index:03d}'})
            connection.execute(text('INSERT INTO cafeteria.user_role_cache(user_id,role_code,source) '
                "VALUES (:id,'Cafeteria.Editor','local')"), {'id': row.id})
            result.append((row.id, row.public_id))
    return result


def test_exact_local_dto_projection_and_read_only(app_reader: Engine, owner_engine: Engine) -> None:
    target_id, target = _seed(owner_engine)[0]
    with owner_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.users SET last_login_at='2026-09-05 12:00Z' WHERE id=:id"),
                           {'id': target_id})
        before = connection.execute(text('SELECT row_to_json(c) FROM cafeteria.local_credentials c '
                                          'WHERE user_id=:id'), {'id': target_id}).scalar_one()
        events = connection.execute(text('SELECT count(*) FROM cafeteria.audit_events')).scalar_one()
    account = users.get_local_user(app_reader, public_id=target)
    assert account is not None
    assert set(asdict(account)) == {'public_id', 'username', 'display_name', 'roles', 'disabled_at',
        'locked_until', 'last_login_at', 'password_changed_at', 'authz_version'}
    assert account.username == 'local.000' and account.roles == ('Cafeteria.Editor',)
    assert account.last_login_at is not None and account.password_changed_at is not None
    assert 'deadbeef' not in repr(account)
    assert users.list_local_users(app_reader, page=1, status='all') == (account,)
    with owner_engine.connect() as connection:
        assert connection.execute(text('SELECT row_to_json(c) FROM cafeteria.local_credentials c '
                                       'WHERE user_id=:id'), {'id': target_id}).scalar_one() == before
        assert connection.execute(text('SELECT count(*) FROM cafeteria.audit_events')).scalar_one() == events


def test_local_pagination_status_and_provider_boundary(app_reader: Engine, owner_engine: Engine) -> None:
    targets = _seed(owner_engine, 53)
    with owner_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'),
                           {'id': targets[2][0]})
        foreign = connection.execute(text("SELECT public_id FROM cafeteria.users WHERE auth_provider='entra'"))
        foreign_ids = tuple(foreign.scalars())
    first = users.list_local_users(app_reader, page=1, status='all')
    second = users.list_local_users(app_reader, page=2, status='all')
    assert len(first) == 50 and len(second) == 3
    assert tuple(row.username for row in first + second) == tuple(f'local.{i:03d}' for i in range(53))
    assert len(users.list_local_users(app_reader, page=2, status='active')) == 2
    assert tuple(row.public_id for row in users.list_local_users(app_reader, page=1, status='disabled')) == (targets[2][1],)
    assert users.list_local_users(app_reader, page=3, status='all') == ()
    for target in (*foreign_ids, uuid4()):
        assert users.get_local_user(app_reader, public_id=target) is None
        assert users.list_local_user_events(app_reader, page=1, target_public_id=target) == ()


@pytest.mark.parametrize('page', [0, -1, True, '1', 10001])
def test_invalid_pages_are_rejected(app_reader: Engine, page: object) -> None:
    with pytest.raises(users.InvalidInput):
        users.list_local_users(app_reader, page=page, status='all')  # type: ignore[arg-type]
    with pytest.raises(users.InvalidInput):
        users.list_local_user_events(app_reader, page=page, target_public_id=None)  # type: ignore[arg-type]


def test_invalid_filters_are_rejected(app_reader: Engine) -> None:
    for status in ('', 'ACTIVE', "all' OR true", None):
        with pytest.raises(users.InvalidInput):
            users.list_local_users(app_reader, page=1, status=status)  # type: ignore[arg-type]
    with pytest.raises(users.InvalidInput):
        users.get_local_user(app_reader, public_id='wrong')  # type: ignore[arg-type]
    with pytest.raises(users.InvalidInput):
        users.list_local_user_events(app_reader, page=1, target_public_id='wrong')  # type: ignore[arg-type]


@pytest.mark.parametrize('reader', ['list_local_users', 'get_local_user', 'list_local_user_events'])
def test_users_manage_is_required_even_for_publisher_audit_read(
    app_reader: Engine, owner_engine: Engine, reader: str,
) -> None:
    call = getattr(users, reader)
    kwargs = ({'page': 1, 'status': 'all'} if reader == 'list_local_users' else
              {'public_id': uuid4()} if reader == 'get_local_user' else
              {'page': 1, 'target_public_id': None})
    actor_id = session['user']['id']
    with owner_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.user_role_cache SET role_code='Cafeteria.Publisher' "
            'WHERE user_id=:id'), {'id': actor_id})
    with pytest.raises(Unauthorized):
        call(app_reader, **kwargs)
    assert not session
    with owner_engine.connect() as connection:
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                                     {'id': actor_id}).scalar_one()
    session['user'], session['authz_version'] = {'id': actor_id}, version
    with pytest.raises(Forbidden):
        call(app_reader, **kwargs)
    session.clear()
    with pytest.raises(Unauthorized):
        call(app_reader, **kwargs)


def test_old_new_events_are_bounded_and_never_return_raw_details(
    app_reader: Engine, owner_engine: Engine,
) -> None:
    first, second = _seed(owner_engine, 2)
    with owner_engine.begin() as connection:
        foreign = connection.execute(text("SELECT public_id FROM cafeteria.users WHERE auth_provider='entra'"))
        foreign_id = foreign.scalar_one()
        for index in range(53):
            connection.execute(text('INSERT INTO cafeteria.audit_events(action,entity_type,entity_public_id,details) '
                "VALUES ('auth.local_user_reactivated','user',:target,'{\"password_hash\":\"DO-NOT-RETURN\"}')"),
                {'target': first[1]})
        connection.execute(text('INSERT INTO cafeteria.audit_events(action,entity_type,details) VALUES '
            "('auth.local_password_changed','user',jsonb_build_object('target_user_id',:target))"),
            {'target': second[0]})
        connection.execute(text('INSERT INTO cafeteria.audit_events(action,entity_type,details) VALUES '
            "('auth.local_login_locked','user',jsonb_build_object('user_id',:target))"), {'target': second[0]})
        for action, target in [('auth.local_user_disabled', foreign_id), ('unexpected.raw.secret', first[1])]:
            connection.execute(text('INSERT INTO cafeteria.audit_events(action,entity_type,entity_public_id) '
                "VALUES (:action,'user',:target)"), {'action': action, 'target': target})
        connection.execute(text('INSERT INTO cafeteria.audit_events(action,entity_type,details) VALUES '
            "('auth.local_password_changed','user','{\"target_user_id\":\"not-a-number\"}')"))
    events = users.list_local_user_events(app_reader, page=1, target_public_id=None)
    later = users.list_local_user_events(app_reader, page=2, target_public_id=None)
    assert len(events) == 50 and len(later) == 5
    assert set(asdict(events[0])) == {'public_id', 'occurred_at', 'action', 'actor_display_name',
                                     'target_public_id', 'target_display_name', 'summary'}
    assert all(row.target_public_id in (first[1], second[1]) for row in events + later)
    assert 'DO-NOT-RETURN' not in repr(events + later)
    assert tuple((row.occurred_at, row.public_id) for row in events + later) == tuple(sorted(
        ((row.occurred_at, row.public_id) for row in events + later), reverse=True))
    selected = users.list_local_user_events(app_reader, page=1, target_public_id=second[1])
    assert {row.action for row in selected} == {'auth.local_login_locked', 'auth.local_password_changed'}
    assert all(row.summary and row.target_display_name == 'Lokales Konto 001' for row in selected)


def test_real_mutation_events_have_actor_and_safe_summaries(
    app_reader: Engine, issuer_engine: Engine,
) -> None:
    actor = users.load_local_command_context(issuer_engine, actor_identifier=DEFAULT_ACTOR).actor
    result = users.create_local_user(issuer_engine, actor=actor, username='event.target',
        display_name='Ereignisziel', password='Valide!Wolken77Kette', roles=('Cafeteria.Editor',))
    for action, kwargs in (
        (users.replace_local_roles, {'roles': ('Cafeteria.Publisher',)}),
        (users.reset_local_password, {'password': 'Frische!Sterne92Tanne'}),
        (users.deactivate_local_user, {}), (users.reactivate_local_user, {}),
    ):
        result = action(issuer_engine, actor=actor,
            target=users.TargetExpectation(result.public_id, result.authz_version), **kwargs)
    events = users.list_local_user_events(app_reader, page=1, target_public_id=result.public_id)
    assert {row.action for row in events} == {
        'auth.local_user_provisioned', 'auth.local_role_granted', 'auth.local_roles_changed',
        'auth.local_password_changed', 'auth.local_user_disabled', 'auth.local_user_reactivated',
    }
    assert all(row.actor_display_name == 'Admin Actor 801' and row.target_display_name == 'Ereignisziel'
               and row.summary for row in events)
    assert 'Wolken' not in repr(events) and 'Sterne' not in repr(events)


def test_event_pagination_is_stable_for_equal_timestamps(app_reader: Engine, owner_engine: Engine) -> None:
    target_id, target = _seed(owner_engine)[0]
    with owner_engine.begin() as connection:
        connection.execute(text('INSERT INTO cafeteria.audit_events(action,entity_type,occurred_at,details) '
            "SELECT 'auth.local_admin_bootstrapped','user','2026-09-05 10:00Z', "
            "jsonb_build_object('target_user_id',:id) FROM generate_series(1,52)"), {'id': target_id})
    first = users.list_local_user_events(app_reader, page=1, target_public_id=target)
    second = users.list_local_user_events(app_reader, page=2, target_public_id=target)
    assert len(first) == 50 and len(second) == 2
    assert len({row.public_id for row in first + second}) == 52
    assert tuple(row.public_id for row in first + second) == tuple(sorted(
        (row.public_id for row in first + second), reverse=True))
    assert first == users.list_local_user_events(app_reader, page=1, target_public_id=target)


def test_system_and_demo_are_not_local_targets(app_reader: Engine, owner_engine: Engine) -> None:
    with owner_engine.begin() as connection:
        targets = connection.execute(text("INSERT INTO cafeteria.users(auth_provider,display_name) "
            "VALUES ('demo','Demo'),('system','System') RETURNING public_id")).scalars().all()
        for target in targets:
            connection.execute(text('INSERT INTO cafeteria.audit_events(action,entity_type,entity_public_id) '
                "VALUES ('auth.local_user_provisioned','user',:target)"), {'target': target})
    assert users.list_local_users(app_reader, page=1, status='all') == ()
    assert users.list_local_user_events(app_reader, page=1, target_public_id=None) == ()
    for target in targets:
        assert users.get_local_user(app_reader, public_id=target) is None


def test_reader_queries_do_not_select_hash_or_raw_audit_details(
    app_reader: Engine, owner_engine: Engine,
) -> None:
    _, target = _seed(owner_engine)[0]
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(app_reader, 'before_cursor_execute', capture)
    try:
        users.list_local_users(app_reader, page=1, status='all')
        users.get_local_user(app_reader, public_id=target)
        users.list_local_user_events(app_reader, page=1, target_public_id=None)
    finally:
        event.remove(app_reader, 'before_cursor_execute', capture)
    assert sum(statement == 'SET TRANSACTION READ ONLY' for statement in statements) == 3
    assert all('password_hash' not in statement and 'SELECT *' not in statement for statement in statements)
    assert all('a.details' not in statement.partition('FROM cafeteria.audit_events')[0]
               for statement in statements)


@pytest.mark.parametrize('reader', ['list_local_users', 'get_local_user', 'list_local_user_events'])
@pytest.mark.parametrize('stage', ['authorization_connect', 'authorization_query', 'account_query'])
def test_reader_outage_covers_authorization_and_recovers_without_session_loss(
    app_reader: Engine, reader: str, stage: str,
) -> None:
    call = getattr(users, reader)
    kwargs = ({'page': 1, 'status': 'all'} if reader == 'list_local_users' else
              {'public_id': uuid4()} if reader == 'get_local_user' else
              {'page': 1, 'target_public_id': None})
    before = dict(session)
    statements: list[str] = []

    def fail() -> None:
        raise OperationalError('private SQL statement', {}, RuntimeError('private DB detail'))

    def connect(_connection):
        if stage == 'authorization_connect':
            fail()

    def query(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
        if stage == 'authorization_query' or (stage == 'account_query' and
                statement.lstrip().startswith(('SELECT u.public_id', 'SELECT a.public_id'))):
            fail()

    event.listen(app_reader, 'engine_connect', connect)
    event.listen(app_reader, 'before_cursor_execute', query)
    try:
        with pytest.raises(users.ReadUnavailable) as error:
            call(app_reader, **kwargs)
        assert str(error.value) == 'Die Kontenansicht ist derzeit nicht verfügbar.'
        assert error.value.__cause__ is None and error.value.__suppress_context__
        assert dict(session) == before
        if stage == 'authorization_connect':
            assert statements == []
        elif stage == 'authorization_query':
            assert len(statements) == 1 and 'FROM cafeteria.users' in statements[0]
        else:
            assert 'SET TRANSACTION READ ONLY' in statements
            assert statements[-1].lstrip().startswith(('SELECT u.public_id', 'SELECT a.public_id'))
    finally:
        event.remove(app_reader, 'engine_connect', connect)
        event.remove(app_reader, 'before_cursor_execute', query)
    assert call(app_reader, **kwargs) == (None if reader == 'get_local_user' else ())
    assert dict(session) == before
