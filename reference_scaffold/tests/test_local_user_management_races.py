"""Real issuer/app connections prove account ordering and identity boundaries."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria.auth import local_users as users, service
from test_auth_database import APP_PASSWORD, DEFAULT_ACTOR, _role_database_url, owner_engine
from test_local_user_management_db import _create, issuer_engine

__all__ = ['owner_engine', 'issuer_engine']


def test_context_hides_foreign_targets_and_requires_current_admin(
    owner_engine: Engine, issuer_engine: Engine,
) -> None:
    context = _create(issuer_engine, 'scoped.target')
    assert context.target is not None
    with owner_engine.connect() as connection:
        actor_public_id = connection.execute(text('SELECT public_id FROM cafeteria.users WHERE id=:id'),
                                             {'id': context.actor.user_id}).scalar_one()
        target_id = connection.execute(text('SELECT id FROM cafeteria.users WHERE public_id=:id'),
                                        {'id': context.target.public_id}).scalar_one()
    for unknown in (uuid4(), actor_public_id):
        with pytest.raises(users.UnknownTarget):
            users.load_local_target_context(issuer_engine, actor=context.actor,
                target=users.TargetExpectation(unknown, 1))
    with pytest.raises(users.ActorDenied) as error:
        users.load_local_target_context(issuer_engine,
            actor=users.ActorExpectation(target_id, context.target.authz_version), target=context.target)
    assert 'scoped.target' not in str(error.value)


def test_actor_revoked_after_reset_context_cannot_commit(
    owner_engine: Engine, issuer_engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _create(issuer_engine, 'revoked.target')
    assert context.target is not None
    original = users.load_local_target_context

    def revoke_after_read(*args, **kwargs):
        result = original(*args, **kwargs)
        with owner_engine.begin() as connection:
            connection.execute(text("DELETE FROM cafeteria.user_role_cache WHERE user_id=:id "
                                     "AND role_code='Cafeteria.Admin'"), {'id': context.actor.user_id})
        return result

    monkeypatch.setattr(users, 'load_local_target_context', revoke_after_read)
    with pytest.raises(users.ActorDenied):
        users.reset_local_password(issuer_engine, actor=context.actor, target=context.target,
                                   password='Neue!Wolken77Kette')
    with owner_engine.connect() as connection:
        assert connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE public_id=:id'),
                                   {'id': context.target.public_id}).scalar_one() == context.target.authz_version


def test_login_and_reset_have_one_lock_order_and_old_sessions_are_stale(
    owner_engine: Engine, issuer_engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _create(issuer_engine, 'login.race')
    assert context.target is not None
    app_engine = create_engine(_role_database_url('cafeteria_app', APP_PASSWORD), poolclass=NullPool)
    entered, release = Event(), Event()
    original = service.check_password_hash

    def pause_login_after_locks(password_hash, password):
        valid = original(password_hash, password)
        if password == 'Valide!Wolken77Kette':
            entered.set()
            assert release.wait(timeout=8), 'test did not release locked login'
        return valid

    monkeypatch.setattr(service, 'check_password_hash', pause_login_after_locks)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            login = executor.submit(service.authenticate_local_user, app_engine,
                username='login.race', password='Valide!Wolken77Kette')
            try:
                assert entered.wait(timeout=5)
                reset = executor.submit(users.reset_local_password, issuer_engine, actor=context.actor,
                    target=context.target, password='Neue!Wolken77Kette')
                deadline = monotonic() + 5
                blocked = False
                while monotonic() < deadline:
                    with owner_engine.connect() as connection:
                        blocked = connection.execute(text('''SELECT EXISTS (
                            SELECT 1 FROM pg_stat_activity WHERE usename='cafeteria_auth_issuer'
                            AND wait_event_type='Lock' AND query LIKE :pattern)'''),
                            {'pattern': '%SELECT * FROM cafeteria.reset_local_password_v19(%'}).scalar_one()
                    if blocked:
                        break
                    Event().wait(0.01)
                assert blocked, 'reset never waited for the already locked login account'
            finally:
                release.set()
            authenticated = login.result(timeout=5)
            changed = reset.result(timeout=5)
        assert authenticated is not None
        assert authenticated.authz_version < changed.authz_version
        current = service.load_user_authorization(app_engine, authenticated.user_id)
        assert current is not None and current.authz_version == changed.authz_version
        assert service.authenticate_local_user(app_engine, username='login.race',
            password='Valide!Wolken77Kette') is None
        assert service.authenticate_local_user(app_engine, username='login.race',
            password='Neue!Wolken77Kette') is not None
    finally:
        release.set()
        app_engine.dispose()


def test_missing_issuer_is_controlled_without_database_fallback() -> None:
    with pytest.raises(users.IssuerUnavailable):
        # Intentionally exercise an unconfigured runtime issuer, outside the typed contract.
        users.load_local_command_context(None, actor_identifier=DEFAULT_ACTOR)  # type: ignore[arg-type]
