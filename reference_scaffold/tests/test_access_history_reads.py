from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

from flask import session
import pytest
from sqlalchemy import Engine, event, text
from sqlalchemy.exc import DBAPIError, OperationalError
from werkzeug.exceptions import Forbidden, Unauthorized

from cafeteria.auth import access_history_reads as history
from cafeteria.auth.local_users import InvalidInput, ReadUnavailable
from test_local_user_management_reads import _seed, app_reader, owner_engine

__all__ = ['app_reader', 'owner_engine']


def _seed_history(owner: Engine, count: int = 6) -> list[UUID]:
    local_id, _ = _seed(owner)[0]
    ids = [UUID(int=index + 1) for index in range(count)]
    with owner.begin() as connection:
        entra_id = connection.execute(text("SELECT id FROM cafeteria.users "
            "WHERE auth_provider='entra' ORDER BY id LIMIT 1")).scalar_one()
        versions = dict(connection.execute(text('SELECT id,authz_version FROM cafeteria.users')).all())
        cases = (
            ('auth.login.accepted', 'local', None, local_id),
            ('auth.login.rejected', 'local', 'credentials', None),
            ('auth.login.unavailable', 'entra', 'unavailable', None),
            ('auth.logout.requested', 'local', None, local_id),
            ('auth.frontchannel.requested', 'entra', None, entra_id),
            ('auth.login.accepted', 'entra', None, entra_id),
        )
        for index, public_id in enumerate(ids):
            action, provider, reason, actor = cases[index % len(cases)]
            connection.execute(text('INSERT INTO cafeteria.audit_events '
                '(public_id,occurred_at,actor_user_id,action,entity_type,details) '
                "VALUES (:id,'2026-09-08 08:00Z',:actor,:action,'authentication',"
                "jsonb_build_object('provider',CAST(:provider AS text),'reason',CAST(:reason AS text),"
                "'authz_version',CAST(:version AS bigint)))"),
                {'id': public_id, 'actor': actor, 'action': action, 'provider': provider,
                 'reason': reason, 'version': versions.get(actor)})
    return ids


def test_fixed_projection_keeps_local_entra_and_unknown_identities(app_reader, owner_engine):
    ids = _seed_history(owner_engine)
    page = history.list_access_history(app_reader, page=1)
    assert not page.has_next and [row.public_id for row in page.rows] == ids[::-1]
    assert {row.action for row in page.rows} == set(history.ACTION_LABELS)
    assert {row.provider for row in page.rows} == {'local', 'entra'}
    assert sum(row.actor_display_name is None for row in page.rows) == 2
    assert set(asdict(page.rows[0])) == {
        'public_id', 'occurred_at', 'actor_display_name', 'provider', 'action', 'summary', 'reason_label',
    }
    assert all(row.summary == history.ACTION_LABELS[row.action] for row in page.rows)
    assert 'Zugangsdaten nicht bestätigt' in {row.reason_label for row in page.rows}


@pytest.mark.parametrize('count', [50, 53])
def test_stable_bounded_pagination_has_exact_lookahead(app_reader, owner_engine, count):
    ids = _seed_history(owner_engine, count)
    first = history.list_access_history(app_reader, page=1)
    second = history.list_access_history(app_reader, page=2)
    assert len(first.rows) == 50 and len(second.rows) == count - 50
    assert first.has_next == (count > 50) and not second.has_next
    assert [row.public_id for row in first.rows + second.rows] == ids[::-1]
    assert first == history.list_access_history(app_reader, page=1)


def test_provider_and_action_filters_combine_without_local_credentials_join(app_reader, owner_engine):
    _seed_history(owner_engine, 18)
    rows = history.list_access_history(app_reader, page=1, provider='entra', action='auth.login.accepted').rows
    assert len(rows) == 3 and all(row.provider == 'entra' for row in rows)
    assert all(row.action == 'auth.login.accepted' and row.actor_display_name for row in rows)
    assert history.list_access_history(app_reader, page=1, provider='local', action='auth.frontchannel.requested').rows == ()


@pytest.mark.parametrize('page', [0, -1, 10001, True, '1', None])
def test_page_boundary_rejects_invalid_types_and_values(app_reader, page):
    with pytest.raises(InvalidInput):
        history.list_access_history(app_reader, page=page)


@pytest.mark.parametrize('field,value', [
    ('provider', ''), ('provider', 'LOCAL'), ('provider', "local' OR true"), ('provider', []),
    ('action', ''), ('action', 'auth.local_login_locked'), ('action', '*'), ('action', None),
])
def test_filter_boundary_is_closed(app_reader, field, value):
    with pytest.raises(InvalidInput):
        history.list_access_history(app_reader, page=1, **{field: value})


@pytest.mark.parametrize('role', ['Cafeteria.Publisher', 'Cafeteria.Editor'])
def test_reader_revalidates_users_manage_and_stale_sessions(app_reader, owner_engine, role):
    actor = session['user']['id']
    with owner_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.user_role_cache SET role_code=:role WHERE user_id=:id'),
                           {'role': role, 'id': actor})
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                                     {'id': actor}).scalar_one()
    with pytest.raises(Unauthorized):
        history.list_access_history(app_reader, page=1)
    assert not session
    session['user'], session['authz_version'] = {'id': actor}, version
    with pytest.raises(Forbidden):
        history.list_access_history(app_reader, page=1)
    session.clear()
    with pytest.raises(Unauthorized):
        history.list_access_history(app_reader, page=1)


def test_malformed_and_unrelated_rows_cannot_leak_raw_details(app_reader, owner_engine):
    _seed_history(owner_engine)
    with owner_engine.begin() as connection:
        for action, entity, details in (
            ('unexpected.private', 'authentication', '{"provider":"local"}'),
            ('auth.login.accepted', 'user', '{"provider":"local"}'),
            ('auth.login.accepted', 'authentication', '{"provider":"PRIVATE-SENTINEL"}'),
            ('auth.login.accepted', 'authentication', '{"provider":null}'),
            ('auth.login.rejected', 'authentication', '{"provider":"local",'
                '"reason":"PRIVATE-SENTINEL","password":"PRIVATE-SENTINEL",'
                '"claims":{"sid":"PRIVATE-SENTINEL"}}'),
        ):
            connection.execute(text('INSERT INTO cafeteria.audit_events(action,entity_type,details) '
                'VALUES (:action,:entity,CAST(:details AS jsonb))'),
                {'action': action, 'entity': entity, 'details': details})
        before = connection.execute(text('SELECT count(*) FROM cafeteria.audit_events')).scalar_one()
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(app_reader, 'before_cursor_execute', capture)
    try:
        page = history.list_access_history(app_reader, page=1)
    finally:
        event.remove(app_reader, 'before_cursor_execute', capture)
    assert len(page.rows) == 7 and 'PRIVATE-SENTINEL' not in repr(page)
    assert 'SET TRANSACTION READ ONLY' in statements
    select = next(statement for statement in statements if 'FROM cafeteria.audit_events a' in statement)
    assert 'a.details,' not in select and 'SELECT *' not in select and 'password' not in select
    assert 'authz_version' not in select and 'local_credentials' not in select
    with owner_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.audit_events')).scalar_one() == before
    with pytest.raises(DBAPIError) as failure, app_reader.begin() as connection:
        connection.execute(text("INSERT INTO cafeteria.audit_events(action,entity_type) "
            "VALUES ('auth.login.accepted','authentication')"))
    assert failure.value.orig.sqlstate == '42501'


@pytest.mark.parametrize('stage', ['authorization', 'history'])
def test_outage_is_safe_and_preserves_session_for_recovery(app_reader, stage):
    before = dict(session)

    def fail(_connection, _cursor, statement, _parameters, _context, _executemany):
        if stage == 'authorization' or 'FROM cafeteria.audit_events a' in statement:
            raise OperationalError('PRIVATE-SENTINEL', {}, RuntimeError('PRIVATE-SENTINEL'))

    event.listen(app_reader, 'before_cursor_execute', fail)
    try:
        with pytest.raises(ReadUnavailable) as failure:
            history.list_access_history(app_reader, page=1)
        assert 'PRIVATE-SENTINEL' not in str(failure.value)
        assert failure.value.__suppress_context__ and dict(session) == before
    finally:
        event.remove(app_reader, 'before_cursor_execute', fail)
    assert history.list_access_history(app_reader, page=1).rows == ()
