from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from psycopg import Error
import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool
from werkzeug.security import check_password_hash

from cafeteria.auth import local_users as users

from test_auth_database import (
    APP_PASSWORD, DEFAULT_ACTOR, ISSUER_PASSWORD, _role_database_url, owner_engine,
)

__all__ = ['owner_engine']


@pytest.fixture
def issuer_engine(owner_engine: Engine) -> Iterator[Engine]:
    engine = create_engine(_role_database_url('cafeteria_auth_issuer', ISSUER_PASSWORD),
                           poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.dispose()


def test_context_is_read_only_and_has_exact_four_parameter_contract(
    issuer_engine: Engine, owner_engine: Engine,
) -> None:
    with owner_engine.connect() as connection:
        before = connection.execute(text('SELECT count(*) FROM cafeteria.audit_events')).scalar_one()
    with issuer_engine.connect() as connection:
        row = connection.execute(text('SELECT * FROM cafeteria.local_user_command_context_v19('
                                      'NULL, :actor, NULL, NULL)'),
                                 {'actor': DEFAULT_ACTOR}).mappings().one()
    assert set(row) == {'actor_user_id', 'actor_authz_version', 'resolved_target_public_id',
                        'target_authz_version', 'resolved_target_username'}
    assert row.actor_user_id > 0
    assert row.resolved_target_public_id is None
    assert row.target_authz_version is None
    assert row.resolved_target_username is None
    with owner_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.audit_events')).scalar_one() == before


def test_versioned_lifecycle_keeps_audit_and_revokes_sessions(issuer_engine: Engine) -> None:
    from cafeteria.auth import local_users as users

    actor = users.load_local_command_context(issuer_engine, actor_identifier=DEFAULT_ACTOR).actor
    created = users.create_local_user(issuer_engine, actor=actor, username='managed.editor',
                                     display_name='Managed Editor', password='Valide!Wolken77Kette',
                                     roles=('Cafeteria.Editor',))
    target = users.TargetExpectation(created.public_id, created.authz_version)
    roles = users.replace_local_roles(issuer_engine, actor=actor, target=target,
                                      roles=('Cafeteria.Publisher',))
    assert roles.changed and roles.authz_version > created.authz_version
    with pytest.raises(users.StaleTarget):
        users.deactivate_local_user(issuer_engine, actor=actor, target=target)
    target = users.TargetExpectation(roles.public_id, roles.authz_version)
    disabled = users.deactivate_local_user(issuer_engine, actor=actor, target=target)
    assert disabled.authz_version > roles.authz_version
    target = users.TargetExpectation(disabled.public_id, disabled.authz_version)
    assert not users.deactivate_local_user(issuer_engine, actor=actor, target=target).changed
    reset = users.reset_local_password(issuer_engine, actor=actor, target=target,
                                      password='Frische!Sterne92Tanne')
    assert reset.authz_version > disabled.authz_version
    target = users.TargetExpectation(reset.public_id, reset.authz_version)
    active = users.reactivate_local_user(issuer_engine, actor=actor, target=target)
    assert active.changed and active.authz_version > reset.authz_version


@pytest.mark.parametrize('signature', [
    'provision_local_user(text,text,text,text,text[])',
    'set_local_password(text,text,text)',
    'disable_local_user(text,text)',
])
def test_legacy_issuer_mutators_are_unavailable(issuer_engine: Engine, signature: str) -> None:
    with issuer_engine.connect() as connection:
        assert not connection.execute(text('SELECT has_function_privilege('
                                            "current_user, :signature, 'EXECUTE')"),
                                      {'signature': 'cafeteria.' + signature}).scalar_one()


@pytest.mark.parametrize('statement', [
    'UPDATE cafeteria.audit_events SET action=action',
    'DELETE FROM cafeteria.audit_events',
    'TRUNCATE cafeteria.audit_events',
    'UPDATE cafeteria.audit_events SET action=action WHERE false',
    'DELETE FROM cafeteria.audit_events WHERE false',
])
def test_audit_cannot_be_rewritten_even_by_accidental_owner_update(
    owner_engine: Engine, statement: str,
) -> None:
    with owner_engine.connect() as connection:
        before = connection.execute(text(
            'SELECT to_jsonb(a) FROM cafeteria.audit_events a ORDER BY id'
        )).scalars().all()
    with pytest.raises(DBAPIError) as immutable, owner_engine.begin() as connection:
        connection.execute(text("INSERT INTO cafeteria.audit_events(action,entity_type) "
                                "VALUES ('test.audit_rollback','user')"))
        connection.execute(text(statement))
    assert isinstance(immutable.value.orig, Error)
    assert immutable.value.orig.sqlstate == '55000'
    with owner_engine.connect() as connection:
        assert connection.execute(text(
            'SELECT to_jsonb(a) FROM cafeteria.audit_events a ORDER BY id'
        )).scalars().all() == before


@pytest.mark.parametrize('role', ['cafeteria_app', 'cafeteria_auth_issuer'])
@pytest.mark.parametrize('statement', [
    'UPDATE cafeteria.audit_events SET action=action',
    'DELETE FROM cafeteria.audit_events',
    'TRUNCATE cafeteria.audit_events',
    'UPDATE cafeteria.audit_events SET action=action WHERE false',
    'DELETE FROM cafeteria.audit_events WHERE false',
])
def test_audit_rewrites_keep_role_permission_error(
    owner_engine: Engine, role: str, statement: str,
) -> None:
    password = APP_PASSWORD if role == 'cafeteria_app' else ISSUER_PASSWORD
    engine = create_engine(_role_database_url(role, password), poolclass=NullPool)
    with owner_engine.connect() as connection:
        before = connection.execute(text(
            'SELECT to_jsonb(a) FROM cafeteria.audit_events a ORDER BY id'
        )).scalars().all()
    try:
        with pytest.raises(DBAPIError) as denied, engine.begin() as connection:
            connection.execute(text(statement))
        assert isinstance(denied.value.orig, Error)
        assert denied.value.orig.sqlstate == '42501'
    finally:
        engine.dispose()
    with owner_engine.connect() as connection:
        assert connection.execute(text(
            'SELECT to_jsonb(a) FROM cafeteria.audit_events a ORDER BY id'
        )).scalars().all() == before


def _create(engine: Engine, username: str, role: str = 'Cafeteria.Editor') -> users.LocalUserContext:
    context = users.load_local_command_context(engine, actor_identifier=DEFAULT_ACTOR)
    users.create_local_user(engine, actor=context.actor, username=username, display_name=username,
                            password='Valide!Wolken77Kette', roles=(role,))
    return users.load_local_command_context(engine, actor_identifier=DEFAULT_ACTOR,
                                           target_username=username)


@pytest.mark.parametrize('selector', [
    (None, None, None, None), (1, DEFAULT_ACTOR, None, None),
    (1, None, None, None), (None, DEFAULT_ACTOR, uuid4(), None),
    (1, None, uuid4(), 'mixed.name'), (None, '', None, None),
    (None, DEFAULT_ACTOR, None, ''), (None, DEFAULT_ACTOR, None, 'UPPER'),
])
def test_context_rejects_mixed_or_incomplete_selectors(issuer_engine: Engine, selector: tuple) -> None:
    with pytest.raises(DBAPIError) as error:
        with issuer_engine.connect() as connection:
            connection.execute(text('SELECT * FROM cafeteria.local_user_command_context_v19('
                'CAST(:a AS bigint), CAST(:n AS text), CAST(:t AS uuid), CAST(:u AS text))'),
                dict(zip(('a', 'n', 't', 'u'), selector, strict=True)))
    assert getattr(error.value.orig, 'sqlstate', None) == 'P1901'


@pytest.mark.parametrize('action', ['deactivate_local_user', 'replace_local_roles'])
def test_last_admin_and_temporarily_locked_remaining_admin_are_protected(
    issuer_engine: Engine, owner_engine: Engine, action: str,
) -> None:
    context = _create(issuer_engine, 'first.admin', 'Cafeteria.Admin')
    assert context.target is not None
    command = getattr(users, action)
    kwargs = {'roles': ('Cafeteria.Editor',)} if action == 'replace_local_roles' else {}
    with pytest.raises(users.LastLocalAdmin):
        command(issuer_engine, actor=context.actor, target=context.target, **kwargs)
    _create(issuer_engine, 'second.admin', 'Cafeteria.Admin')
    with owner_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.local_credentials SET failed_login_count=5, "
            "locked_until=clock_timestamp()+interval '5 minutes' WHERE username='second.admin'"))
    with pytest.raises(users.LastLocalAdmin):
        command(issuer_engine, actor=context.actor, target=context.target, **kwargs)
    with owner_engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.local_credentials SET locked_until=NULL "
                                 "WHERE username='second.admin'"))
    assert command(issuer_engine, actor=context.actor, target=context.target, **kwargs).changed


def test_reset_uses_real_username_and_keeps_original_versions(
    issuer_engine: Engine, owner_engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _create(issuer_engine, 'policy.target')
    assert context.target is not None
    with pytest.raises(ValueError, match='Benutzernamen'):
        users.reset_local_password(issuer_engine, actor=context.actor, target=context.target,
                                   password='Policy.Target!2026Long')
    with owner_engine.connect() as connection:
        before = connection.execute(text("SELECT password_hash FROM cafeteria.local_credentials "
                                          "WHERE username='policy.target'")).scalar_one()
    original = users.load_local_target_context

    def changed_after_context(*args, **kwargs):
        result = original(*args, **kwargs)
        users.deactivate_local_user(issuer_engine, actor=context.actor, target=context.target)
        return result

    monkeypatch.setattr(users, 'load_local_target_context', changed_after_context)
    with pytest.raises(users.StaleTarget):
        users.reset_local_password(issuer_engine, actor=context.actor, target=context.target,
                                   password='Neue!Wolken77Kette')
    with owner_engine.connect() as connection:
        assert connection.execute(text("SELECT password_hash FROM cafeteria.local_credentials "
                                        "WHERE username='policy.target'")).scalar_one() == before


@pytest.mark.parametrize('changed_identity', ['actor', 'target'])
def test_stale_expectation_is_rejected_before_reset_hash(
    issuer_engine: Engine, owner_engine: Engine, monkeypatch: pytest.MonkeyPatch,
    changed_identity: str,
) -> None:
    context = _create(issuer_engine, 'stale.target')
    assert context.target is not None
    with owner_engine.begin() as connection:
        if changed_identity == 'actor':
            connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 '
                                     'WHERE id=:id'), {'id': context.actor.user_id})
        else:
            connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 '
                                     'WHERE public_id=:id'), {'id': context.target.public_id})
    monkeypatch.setattr(users, 'generate_password_hash', lambda *_: pytest.fail('stale reset hashed'))
    with pytest.raises(users.StaleActor if changed_identity == 'actor' else users.StaleTarget):
        users.reset_local_password(issuer_engine, actor=context.actor, target=context.target,
                                   password='Neue!Wolken77Kette')


def test_audit_failure_rolls_back_hash_and_version(issuer_engine: Engine, owner_engine: Engine) -> None:
    context = _create(issuer_engine, 'rollback.target')
    assert context.target is not None
    with owner_engine.begin() as connection:
        connection.execute(text('''CREATE FUNCTION cafeteria.test_fail_audit() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test audit failure'; END; $$'''))
        connection.execute(text('''CREATE TRIGGER test_fail_audit BEFORE INSERT
            ON cafeteria.audit_events FOR EACH ROW EXECUTE FUNCTION cafeteria.test_fail_audit()'''))
    with pytest.raises(users.IssuerUnavailable):
        users.reset_local_password(issuer_engine, actor=context.actor, target=context.target,
                                   password='Neue!Wolken77Kette')
    with owner_engine.connect() as connection:
        row = connection.execute(text('SELECT u.authz_version, c.password_hash FROM cafeteria.users u '
            'JOIN cafeteria.local_credentials c ON c.user_id=u.id WHERE u.public_id=:id'),
            {'id': context.target.public_id}).one()
    assert row.authz_version == context.target.authz_version
    assert check_password_hash(row.password_hash, 'Valide!Wolken77Kette')


def test_two_self_demotions_serialize_and_leave_one_admin(issuer_engine: Engine, owner_engine: Engine) -> None:
    for username in ('race.first', 'race.second'):
        _create(issuer_engine, username, 'Cafeteria.Admin')
    contexts = [users.load_local_command_context(issuer_engine, actor_identifier=name,
                target_username=name) for name in ('race.first', 'race.second')]
    barrier = Barrier(2)

    def demote(context: users.LocalUserContext) -> str:
        assert context.target is not None
        barrier.wait(timeout=5)
        try:
            users.replace_local_roles(issuer_engine, actor=context.actor, target=context.target,
                                       roles=('Cafeteria.Editor',))
        except users.LastLocalAdmin:
            return 'protected'
        return 'changed'

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(demote, contexts)) == ['changed', 'protected']
    with owner_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.users u "
            "JOIN cafeteria.user_role_cache r ON r.user_id=u.id "
            "WHERE u.auth_provider='local' AND u.disabled_at IS NULL "
            "AND r.role_code='Cafeteria.Admin'")).scalar_one() == 1


def test_mutations_reject_old_snapshot_isolation(issuer_engine: Engine) -> None:
    context = _create(issuer_engine, 'isolation.target')
    assert context.target is not None
    with issuer_engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with pytest.raises(DBAPIError) as error:
            connection.execute(text('SELECT * FROM cafeteria.deactivate_local_user_v19('
                ':actor, :version, :target, :target_version)'),
                {'actor': context.actor.user_id, 'version': context.actor.authz_version,
                 'target': context.target.public_id, 'target_version': context.target.authz_version})
        assert getattr(error.value.orig, 'sqlstate', None) == 'P1901'
