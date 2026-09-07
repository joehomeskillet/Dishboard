"""Actual PostgreSQL lock waits, legacy CAS races and authorization revocation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import monotonic, sleep
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.pool import NullPool
from werkzeug.security import generate_password_hash

from cafeteria.print_templates import PrintTemplateConflictError, change_template, read_templates
from test_admin_workflow_routes import APP_PASSWORD, WEEK, database_engine  # noqa: F401
from test_admin_workflow_db import _patient_values, _save
from test_print_template_archive import COPY_ID, legacy_document, seed, snapshot
from test_print_template_routes import editor_app  # noqa: F401
from test_print_template_store import _actor


def other_admin(engine: Engine) -> tuple[int, int]:
    with engine.begin() as connection:
        actor = connection.execute(text("INSERT INTO cafeteria.users(auth_provider,display_name) VALUES('local','Other archive administrator') RETURNING id")).scalar_one()
        connection.execute(text("INSERT INTO cafeteria.user_role_cache(user_id,role_code,source) VALUES(:actor,'Cafeteria.Admin','local')"), {'actor': actor})
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:actor'), {'actor': actor}).scalar_one()
    return actor, version


def wait_blocked(engine: Engine, application: str) -> None:
    deadline = monotonic() + 4
    while monotonic() < deadline:
        with engine.connect() as connection:
            waiting = connection.execute(text('''
                SELECT count(*) FROM pg_stat_activity
                WHERE application_name=:application AND wait_event_type='Lock'
                  AND cardinality(pg_blocking_pids(pid)) > 0
            '''), {'application': application}).scalar_one()
        if waiting:
            return
        sleep(0.02)
    raise AssertionError('The writer never reached the expected real PostgreSQL lock wait.')


@pytest.mark.parametrize('change', ['role', 'version', 'disabled', 'membership'])
def test_authority_revoked_while_writer_waits(editor_app: Any, database_engine: Engine, change: str) -> None:  # noqa: F811
    _, actor, authz = _actor(editor_app, database_engine)
    seed(database_engine, 'patient', legacy_document())
    before = snapshot(database_engine)
    name = 'template-archive-revocation'
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD),
                            poolclass=NullPool, connect_args={'application_name': name})
    try:
        with ThreadPoolExecutor(max_workers=1) as workers:
            with database_engine.begin() as blocker:
                if change == 'role':
                    blocker.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Admin'"))
                else:
                    blocker.execute(text('SELECT id FROM cafeteria.users WHERE id=:actor FOR UPDATE'), {'actor': actor})
                    if change == 'version':
                        # IAM password reset and role replacement advance this original-session guard.
                        blocker.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:actor'), {'actor': actor})
                    elif change == 'disabled':
                        blocker.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor'), {'actor': actor})
                    else:
                        blocker.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor'), {'actor': actor})
                future = workers.submit(change_template, runtime, 'patient', actor, authz, 3, COPY_ID, 'archive')
                wait_blocked(database_engine, name)
                assert not future.done()
            with pytest.raises(PermissionError):
                future.result(timeout=10)
        assert snapshot(database_engine) == before
    finally:
        runtime.dispose()


def test_two_legacy_writers_have_one_atomic_upgrade(editor_app: Any, database_engine: Engine) -> None:  # noqa: F811
    _, actor, authz = _actor(editor_app, database_engine)
    original = legacy_document()
    seed(database_engine, 'patient', original)
    barrier = Barrier(2)
    identities = [(actor, authz), other_admin(database_engine)]

    def archive(identity: tuple[int, int]) -> str:
        barrier.wait(timeout=10)
        try:
            change_template(database_engine, 'patient', *identity, 3, COPY_ID, 'archive')
            return 'saved'
        except PrintTemplateConflictError:
            return 'conflict'

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(archive, identity) for identity in identities]
        assert sorted(future.result(timeout=15) for future in futures) == ['conflict', 'saved']
    with database_engine.connect() as connection:
        document = read_templates(connection, 'patient')
    assert document['schema_version'] == 2 and document['version'] == 4
    assert document['templates'][1]['archived'] is True
    assert [item['revisions'] for item in document['templates']] == [item['revisions'] for item in original['templates']]


def test_actual_password_reset_invalidates_waiting_original_actor(database_engine: Engine) -> None:  # noqa: F811
    password_hash = generate_password_hash('Isolierte-Vorlagen-Testpassphrase')
    actors = []
    with database_engine.begin() as connection:
        for username in ['archive.actor', 'archive.admin']:
            actor = connection.execute(text("INSERT INTO cafeteria.users(auth_provider,display_name) VALUES('local',:name) RETURNING id"), {'name': username}).scalar_one()
            connection.execute(text("INSERT INTO cafeteria.user_role_cache(user_id,role_code,source) VALUES(:id,'Cafeteria.Admin','local')"), {'id': actor})
            connection.execute(text('INSERT INTO cafeteria.local_credentials(user_id,username,password_hash) VALUES(:id,:name,:hash)'), {'id': actor, 'name': username, 'hash': password_hash})
            actors.append(connection.execute(text('SELECT id,authz_version,public_id FROM cafeteria.users WHERE id=:id'), {'id': actor}).one())
    actor, admin = actors
    seed(database_engine, 'patient', legacy_document())
    before = snapshot(database_engine)
    name = 'template-archive-password-reset'
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD),
                            poolclass=NullPool, connect_args={'application_name': name})
    try:
        with ThreadPoolExecutor(max_workers=1) as workers:
            with database_engine.begin() as blocker:
                blocker.execute(text('SELECT * FROM cafeteria.reset_local_password_v19(:admin,:admin_version,:target,:version,:hash)'), {
                    'admin': admin.id, 'admin_version': admin.authz_version, 'target': actor.public_id,
                    'version': actor.authz_version, 'hash': generate_password_hash('Neue-Isolierte-Vorlagen-Testpassphrase'),
                }).one()
                future = workers.submit(change_template, runtime, 'patient', actor.id, actor.authz_version, 3, COPY_ID, 'archive')
                wait_blocked(database_engine, name)
            with pytest.raises(PermissionError):
                future.result(timeout=10)
        assert snapshot(database_engine) == before
    finally:
        runtime.dispose()


@pytest.mark.parametrize('winner', ['archive', 'activate'])
def test_archive_and_activate_race_both_lock_orders(editor_app: Any, database_engine: Engine, winner: str) -> None:  # noqa: F811
    _, actor, authz = _actor(editor_app, database_engine)
    seed(database_engine, 'patient', legacy_document())
    _save(database_engine, 'patient', _patient_values())
    name = 'template-archive-activation'
    waiting = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD),
                            poolclass=NullPool, connect_args={'application_name': name})
    loser = 'activate' if winner == 'archive' else 'archive'
    second_actor, second_authz = other_admin(database_engine)
    winning = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD), poolclass=NullPool)
    locked, release = Event(), Event()

    def hold_settings(connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool) -> None:
        if 'SELECT setting_value' in statement and 'FOR UPDATE' in statement:
            locked.set()
            assert release.wait(timeout=10)

    event.listen(winning, 'after_cursor_execute', hold_settings)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(change_template, winning, 'patient', actor, authz, 3, COPY_ID, winner, week=WEEK)
            try:
                assert locked.wait(timeout=10)
                future = workers.submit(change_template, waiting, 'patient', second_actor, second_authz, 3, COPY_ID, loser, week=WEEK)
                wait_blocked(database_engine, name)
            finally:
                release.set()
            first.result(timeout=15)
            with pytest.raises(PrintTemplateConflictError):
                future.result(timeout=15)
        with database_engine.connect() as connection:
            document = read_templates(connection, 'patient')
        assert document['version'] == 4
        assert document['templates'][1]['archived'] is (winner == 'archive')
        assert document['active_template'] == (COPY_ID if winner == 'activate' else 'standard')
    finally:
        release.set()
        winning.dispose()
        waiting.dispose()
