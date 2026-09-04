from __future__ import annotations

# ruff: noqa: F401, F811

import hashlib
from threading import Event

import pytest
from sqlalchemy import Engine, event, text, create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.db import issue_publication_capability, withdraw_publication_revision

import test_admin_workflow_db as workflow_support
from test_component_metadata_master_lock_db import (
    SCHEMA,
    PERMISSIONS,
    _drop_schema,
    pg16,
)
from test_component_catalog_db import CatalogDatabase, catalog_database
from test_workflow_copy_store_db import (
    TARGET_WEEK,
    _separate_engine,
    _blocked_pair,
    _prepare_replacement,
    _patient_values,
)


def _get_func_info(engine: Engine, func_sig: str) -> dict:
    with engine.connect() as conn:
        return dict(conn.execute(text("""
            SELECT prosecdef, prosrc, proconfig,
                   has_function_privilege('cafeteria_app', oid, 'EXECUTE') as app_exec,
                   has_function_privilege('cafeteria_auth_issuer', oid, 'EXECUTE') as issuer_exec,
                   has_function_privilege('cafeteria_backup', oid, 'EXECUTE') as backup_exec,
                   has_function_privilege('public', oid, 'EXECUTE') as public_exec
            FROM pg_proc WHERE oid = to_regprocedure(:sig)
        """), {'sig': func_sig}).mappings().one())


def test_v14_database_with_original_0011_checksum_upgrades_with_exactly_0012(pg16: Engine) -> None:
    plan = list(database.migration_plan(SCHEMA))
    for migration in plan:
        if migration.version <= 14:
            database._execute_migration(pg16, migration)

    with pg16.connect() as conn:
        v14_checksum = conn.execute(text(
            "SELECT checksum_sha256 FROM cafeteria.schema_migrations WHERE version=14"
        )).scalar_one()
    assert v14_checksum == '75c6d6cc777f1dbf3d2bb914688b8ff9529ddca51fc9250ea91170b5482d0953'

    database.run_migrations(pg16, SCHEMA)

    with pg16.connect() as conn:
        versions = conn.execute(text(
            "SELECT version FROM cafeteria.schema_migrations ORDER BY version"
        )).scalars().all()
        assert versions == list(range(4, 16))

        v15_row = conn.execute(text(
            "SELECT name, application_version, checksum_sha256 FROM cafeteria.schema_migrations WHERE version=15"
        )).one()

    m12_path = SCHEMA.parent / 'migrations' / '0012_v14_to_v15.sql'
    m12_hash = hashlib.sha256(m12_path.read_bytes()).hexdigest()

    assert v15_row == ('0012_v14_to_v15.sql', 'dishboard-schema-v15', m12_hash)

    database.run_migrations(pg16, SCHEMA)
    with pg16.connect() as conn:
        new_versions = conn.execute(text(
            "SELECT version FROM cafeteria.schema_migrations ORDER BY version"
        )).scalars().all()
        assert new_versions == versions
        assert conn.execute(text(
            "SELECT checksum_sha256 FROM cafeteria.schema_migrations WHERE version=15"
        )).scalar_one() == m12_hash

    database._execute_script(pg16, str(PERMISSIONS))

    funcs = [
        'cafeteria.lock_expected_active_location(bigint)',
        'cafeteria.lock_active_publication(bigint)',
        'cafeteria.issue_publication_capability(bigint,bigint,interval)',
        'cafeteria.withdraw_publication_revision(bigint,text,text)',
    ]

    migrated_infos = {}
    for sig in funcs:
        info = _get_func_info(pg16, sig)
        migrated_infos[sig] = info
        assert info['prosecdef'] is True
        assert info['backup_exec'] is False
        assert info['public_exec'] is False
        if 'lock' in sig:
            assert info['app_exec'] is True
            assert info['issuer_exec'] is False
        elif 'issue' in sig:
            assert info['app_exec'] is False
            assert info['issuer_exec'] is True
        elif 'withdraw' in sig:
            assert info['app_exec'] is True
            assert info['issuer_exec'] is False

    _drop_schema(pg16)
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))

    for sig in funcs:
        fresh_info = _get_func_info(pg16, sig)
        assert fresh_info['prosrc'] == migrated_infos[sig]['prosrc']
        assert fresh_info['proconfig'] == migrated_infos[sig]['proconfig']


def test_v14_registry_drift_on_0011_aborts_upgrade(pg16: Engine) -> None:
    plan = list(database.migration_plan(SCHEMA))
    for migration in plan:
        if migration.version <= 14:
            database._execute_migration(pg16, migration)

    with pg16.begin() as conn:
        conn.execute(text(
            "UPDATE cafeteria.schema_migrations SET checksum_sha256 = repeat('0', 64) WHERE version = 14"
        ))

    with pytest.raises(RuntimeError):
        database.run_migrations(pg16, SCHEMA)

    with pg16.connect() as conn:
        assert conn.execute(text("SELECT max(version) FROM cafeteria.schema_migrations")).scalar_one() == 14


def test_fresh_install_reaches_schema_15_with_narrow_lock_helper_grants(catalog_database: CatalogDatabase) -> None:
    with catalog_database.owner.connect() as conn:
        assert conn.execute(text("SELECT max(version) FROM cafeteria.schema_migrations")).scalar_one() == 15

    funcs = [
        'cafeteria.lock_expected_active_location(bigint)',
        'cafeteria.lock_active_publication(bigint)',
        'cafeteria.issue_publication_capability(bigint,bigint,interval)',
        'cafeteria.withdraw_publication_revision(bigint,text,text)',
    ]

    for sig in funcs:
        info = _get_func_info(catalog_database.owner, sig)
        assert info['prosecdef'] is True
        assert info['backup_exec'] is False
        assert info['public_exec'] is False
        if 'lock' in sig:
            assert info['app_exec'] is True
            assert info['issuer_exec'] is False
        elif 'issue' in sig:
            assert info['app_exec'] is False
            assert info['issuer_exec'] is True
        elif 'withdraw' in sig:
            assert info['app_exec'] is True
            assert info['issuer_exec'] is False


def test_capability_issue_blocks_behind_direct_withdrawal_without_deadlock(catalog_database: CatalogDatabase) -> None:
    second_version, revision_id, direct_capability = _prepare_replacement(catalog_database)

    with catalog_database.owner.connect() as conn:
        week_id = conn.execute(
            text("SELECT menu_week_id FROM cafeteria.publication_revisions WHERE id=:id"),
            {"id": revision_id}
        ).scalar_one()

    app_engine = _separate_engine(catalog_database)
    owner_engine = create_engine(catalog_database.owner.url, poolclass=NullPool, pool_pre_ping=True)

    first_locked = Event()
    release = Event()
    second_attempted = Event()
    pids = {}

    def after_first(conn, cursor, statement, params, ctx, many):
        if 'withdraw_publication_revision' in statement:
            pids['first'] = int(cursor.connection.info.backend_pid)
            first_locked.set()
            assert release.wait(10)

    def before_second(conn, cursor, statement, params, ctx, many):
        if 'issue_publication_capability' in statement:
            pids['second'] = int(cursor.connection.info.backend_pid)
            second_attempted.set()

    event.listen(app_engine, 'after_cursor_execute', after_first)
    event.listen(owner_engine, 'before_cursor_execute', before_second)

    def first_task():
        with app_engine.begin() as conn:
            conn.execute(text("SELECT cafeteria.withdraw_publication_revision(:revision_id, :capability, 'Race')"), {
                "revision_id": revision_id,
                "capability": direct_capability
            })

    def second_task():
        try:
            return issue_publication_capability(owner_engine, 2, revision_id)
        except Exception as e:
            if getattr(getattr(e, 'orig', None), 'sqlstate', None) == '40P01':
                pytest.fail('deadlock 40P01')
            return e

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first_task)
            assert first_locked.wait(10)

            second_future = pool.submit(second_task)
            assert second_attempted.wait(10)

            with catalog_database.owner.connect() as conn:
                for _ in range(1000):
                    blockers = conn.execute(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids['second']}).scalar_one()
                    if blockers:
                        break
            assert blockers == [pids['first']]
            assert not second_future.done()

            release.set()

            first_future.result(timeout=10)
            res = second_future.result(timeout=10)

            assert isinstance(res, DBAPIError)
            assert getattr(res.orig, 'sqlstate', None) == '55000'

    finally:
        release.set()
        event.remove(app_engine, 'after_cursor_execute', after_first)
        event.remove(owner_engine, 'before_cursor_execute', before_second)
        app_engine.dispose()
        owner_engine.dispose()

    with catalog_database.owner.connect() as conn:
        revs = conn.execute(text("SELECT id, withdrawn_at FROM cafeteria.publication_revisions")).fetchall()
        assert len(revs) == 1
        assert revs[0].withdrawn_at is not None


def test_direct_withdrawal_blocks_behind_open_capability_issue_without_deadlock(catalog_database: CatalogDatabase) -> None:
    second_version, revision_id, direct_capability = _prepare_replacement(catalog_database)

    owner_engine = create_engine(catalog_database.owner.url, poolclass=NullPool, pool_pre_ping=True)
    app_engine = _separate_engine(catalog_database)

    first_locked = Event()
    release = Event()
    second_attempted = Event()
    pids = {}

    def after_first(conn, cursor, statement, params, ctx, many):
        if 'issue_publication_capability' in statement:
            pids['first'] = int(cursor.connection.info.backend_pid)
            first_locked.set()
            assert release.wait(10)

    def before_second(conn, cursor, statement, params, ctx, many):
        if 'withdraw_publication_revision' in statement:
            pids['second'] = int(cursor.connection.info.backend_pid)
            second_attempted.set()

    event.listen(owner_engine, 'after_cursor_execute', after_first)
    event.listen(app_engine, 'before_cursor_execute', before_second)

    def first_task():
        with owner_engine.begin() as conn:
            return conn.execute(text("SELECT cafeteria.issue_publication_capability(2, :revision_id)"), {"revision_id": revision_id}).scalar_one()

    def second_task():
        try:
            return withdraw_publication_revision(app_engine, revision_id, direct_capability, 'Race')
        except Exception as e:
            if getattr(getattr(e, 'orig', None), 'sqlstate', None) == '40P01':
                pytest.fail('deadlock 40P01')
            return e

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first_task)
            assert first_locked.wait(10)

            second_future = pool.submit(second_task)
            assert second_attempted.wait(10)

            with catalog_database.owner.connect() as conn:
                for _ in range(1000):
                    blockers = conn.execute(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids['second']}).scalar_one()
                    if blockers:
                        break
            assert blockers == [pids['first']]
            assert not second_future.done()

            release.set()

            t2_token = first_future.result(timeout=10)
            res = second_future.result(timeout=10)

            assert not isinstance(res, Exception)

            try:
                withdraw_publication_revision(app_engine, revision_id, t2_token, 'Race 2')
                pytest.fail("Should have failed")
            except Exception as e:
                if getattr(getattr(e, 'orig', None), 'sqlstate', None) == '40P01':
                    pytest.fail('deadlock 40P01')
                assert getattr(e.orig, 'sqlstate', None) == '55000'

    finally:
        release.set()
        event.remove(owner_engine, 'after_cursor_execute', after_first)
        event.remove(app_engine, 'before_cursor_execute', before_second)
        owner_engine.dispose()
        app_engine.dispose()


def test_capability_issue_blocks_behind_replacement_publish_without_deadlock(catalog_database: CatalogDatabase) -> None:
    second_version, revision_id, direct_capability = _prepare_replacement(catalog_database)

    publish_engine = _separate_engine(catalog_database)
    owner_engine = create_engine(catalog_database.owner.url, poolclass=NullPool, pool_pre_ping=True)

    publication_locked = Event()
    release = Event()
    issue_attempted = Event()
    pids = {}

    def after_publication_lock(conn, cursor, statement, params, ctx, many):
        if 'lock_active_publication' in statement:
            pids['first'] = int(cursor.connection.info.backend_pid)
            publication_locked.set()
            assert release.wait(10)

    def before_issue(conn, cursor, statement, params, ctx, many):
        if 'issue_publication_capability' in statement:
            pids['second'] = int(cursor.connection.info.backend_pid)
            issue_attempted.set()

    event.listen(publish_engine, 'after_cursor_execute', after_publication_lock)
    event.listen(owner_engine, 'before_cursor_execute', before_issue)

    def first_task():
        from cafeteria import workflow
        return workflow.publish_draft(
            publish_engine,
            'patient',
            TARGET_WEEK,
            expected_row_version=second_version,
            actor_id=2,
            issuer_engine=catalog_database.owner,
        )

    def second_task():
        try:
            return issue_publication_capability(owner_engine, 2, revision_id)
        except Exception as e:
            if getattr(getattr(e, 'orig', None), 'sqlstate', None) == '40P01':
                pytest.fail('deadlock 40P01')
            return e

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            publishing = pool.submit(first_task)
            assert publication_locked.wait(5)

            issuing = pool.submit(second_task)
            assert issue_attempted.wait(10)

            with catalog_database.owner.connect() as conn:
                for _ in range(1000):
                    blockers = conn.execute(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids['second']}).scalar_one()
                    if blockers:
                        break
            assert blockers == [pids['first']]
            assert not issuing.done()

            release.set()

            published = publishing.result(timeout=10)
            res = issuing.result(timeout=10)

            assert isinstance(res, DBAPIError)
            assert getattr(res.orig, 'sqlstate', None) == '55000'

    finally:
        release.set()
        event.remove(publish_engine, 'after_cursor_execute', after_publication_lock)
        event.remove(owner_engine, 'before_cursor_execute', before_issue)
        publish_engine.dispose()
        owner_engine.dispose()

    with catalog_database.owner.connect() as conn:
        all_revs = conn.execute(text("SELECT id, withdrawn_at FROM cafeteria.publication_revisions")).fetchall()
        assert len(all_revs) == 2
        active_revs = [r for r in all_revs if r.withdrawn_at is None]
        assert len(active_revs) == 1
        assert active_revs[0].id != revision_id

    assert published['revision_id'].endswith('-R2')


def test_replacement_publish_blocks_behind_open_capability_issue_without_deadlock(catalog_database: CatalogDatabase) -> None:
    second_version, revision_id, direct_capability = _prepare_replacement(catalog_database)

    owner_engine = create_engine(catalog_database.owner.url, poolclass=NullPool, pool_pre_ping=True)
    publish_engine = _separate_engine(catalog_database)
    issuer_engine = create_engine(catalog_database.owner.url, poolclass=NullPool, pool_pre_ping=True)

    issue_locked = Event()
    release = Event()
    publish_attempted = Event()
    pids = {}

    def after_first(conn, cursor, statement, params, ctx, many):
        if 'issue_publication_capability' in statement:
            pids['first'] = int(cursor.connection.info.backend_pid)
            issue_locked.set()
            assert release.wait(10)

    def before_second(conn, cursor, statement, params, ctx, many):
        if 'issue_publication_capability' in statement:
            pids['second'] = int(cursor.connection.info.backend_pid)
            publish_attempted.set()

    event.listen(owner_engine, 'after_cursor_execute', after_first)
    event.listen(issuer_engine, 'before_cursor_execute', before_second)

    def first_task():
        with owner_engine.begin() as conn:
            return conn.execute(text("SELECT cafeteria.issue_publication_capability(2, :revision_id)"), {"revision_id": revision_id}).scalar_one()

    def second_task():
        try:
            from cafeteria import workflow
            return workflow.publish_draft(
                publish_engine,
                'patient',
                TARGET_WEEK,
                expected_row_version=second_version,
                actor_id=2,
                issuer_engine=issuer_engine,
            )
        except Exception as e:
            if getattr(getattr(e, 'orig', None), 'sqlstate', None) == '40P01':
                pytest.fail('deadlock 40P01')
            return e

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            issuing = pool.submit(first_task)
            if not issue_locked.wait(5):
                if issuing.exception():
                    raise issuing.exception()
                assert False

            publishing = pool.submit(second_task)
            assert publish_attempted.wait(10)

            with catalog_database.owner.connect() as conn:
                for _ in range(1000):
                    blockers = conn.execute(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids['second']}).scalar_one()
                    if blockers:
                        break
            assert blockers == [pids['first']]
            assert not publishing.done()

            release.set()

            issuing.result(timeout=10)
            res = publishing.result(timeout=10)

            assert not isinstance(res, Exception)

    finally:
        release.set()
        event.remove(owner_engine, 'after_cursor_execute', after_first)
        event.remove(issuer_engine, 'before_cursor_execute', before_second)
        owner_engine.dispose()
        publish_engine.dispose()

    with catalog_database.owner.connect() as conn:
        all_revs = conn.execute(text("SELECT id, withdrawn_at FROM cafeteria.publication_revisions")).fetchall()
        assert len(all_revs) == 2
        active_revs = [r for r in all_revs if r.withdrawn_at is None]
        assert len(active_revs) == 1


def test_withdrawal_replay_keeps_nonce_error_precedence(catalog_database: CatalogDatabase) -> None:
    _, revision_id, direct_capability = _prepare_replacement(catalog_database)
    app_engine = catalog_database.app
    owner_engine = catalog_database.owner

    withdraw_publication_revision(app_engine, revision_id, direct_capability, 'First')

    try:
        withdraw_publication_revision(app_engine, revision_id, direct_capability, 'Replay')
        pytest.fail("Should have failed")
    except DBAPIError as e:
        assert getattr(e.orig, 'sqlstate', None) == '42501'
        assert 'Capability-Nonce wurde bereits verwendet.' in str(e)

    try:
        issue_publication_capability(owner_engine, 2, revision_id)
        pytest.fail("Should have failed")
    except DBAPIError as e:
        assert getattr(e.orig, 'sqlstate', None) == '55000'


def test_issue_defers_revision_errors_behind_actor_checks(catalog_database: CatalogDatabase) -> None:
    _, revision_id, direct_capability = _prepare_replacement(catalog_database)
    owner_engine = catalog_database.owner

    try:
        issue_publication_capability(owner_engine, 999999, 999999)
        pytest.fail("Should have failed")
    except DBAPIError as e:
        assert getattr(e.orig, 'sqlstate', None) == '42501'

    try:
        issue_publication_capability(owner_engine, 2, 999999)
        pytest.fail("Should have failed")
    except DBAPIError as e:
        assert getattr(e.orig, 'sqlstate', None) == 'P0002'

    withdraw_publication_revision(catalog_database.app, revision_id, direct_capability, 'Withdraw')

    try:
        issue_publication_capability(owner_engine, 2, revision_id)
        pytest.fail("Should have failed")
    except DBAPIError as e:
        assert getattr(e.orig, 'sqlstate', None) == '55000'
