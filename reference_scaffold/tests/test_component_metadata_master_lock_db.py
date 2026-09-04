from __future__ import annotations

import os
import shutil
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from cafeteria import db as database


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'database' / 'schema.sql'
PERMISSIONS = ROOT / 'database' / 'permissions.sql'
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
PG16_TEST_CONTAINER = os.getenv('TEST_DATABASE_CONTAINER')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
FUNCTION_SIGNATURE = 'cafeteria.lock_component_metadata_masters(text[],text[])'
LIVE_DATABASE = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-16-Testdatenbank fehlt.',
)


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


def _role_url(role: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role,
        password=password,
    ).render_as_string(hide_password=False)


def _role_engine(role: str, password: str) -> Engine:
    return create_engine(_role_url(role, password), poolclass=NullPool, pool_pre_ping=True)


@pytest.fixture
def pg16() -> Iterator[Engine]:
    if not DATABASE_URL:
        pytest.skip('TEST_DATABASE_URL für eine isolierte PostgreSQL-16-Testdatenbank fehlt.')
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.provision_database_roles(
        engine,
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    try:
        with engine.connect() as connection:
            version = int(connection.execute(text('SHOW server_version_num')).scalar_one())
        assert 160_000 <= version < 170_000
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


def _install_migrated_schema(engine: Engine) -> None:
    database.run_migrations(engine, SCHEMA)
    database._execute_script(engine, str(PERMISSIONS))


@pytest.fixture
def installed_pg16(pg16: Engine) -> Engine:
    _install_migrated_schema(pg16)
    return pg16


@pytest.fixture
def seeded_pg16(installed_pg16: Engine) -> Engine:
    database._execute_script(installed_pg16, str(ROOT / 'database' / 'seed.sql'))
    return installed_pg16


@pytest.fixture
def app_engine(installed_pg16: Engine) -> Iterator[Engine]:
    engine = _role_engine('cafeteria_app', APP_PASSWORD)
    try:
        yield engine
    finally:
        engine.dispose()


def _function_contract(engine: Engine) -> tuple[object, ...]:
    with engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    '''
                    WITH fn AS (
                        SELECT p.*, n.nspowner
                        FROM pg_proc p
                        JOIN pg_namespace n ON n.oid=p.pronamespace
                        WHERE p.oid=to_regprocedure(:signature)
                    )
                    SELECT prosecdef, provolatile, proparallel, proconfig,
                           pg_get_userbyid(proowner), pg_get_userbyid(nspowner),
                           pg_get_function_result(oid),
                           has_function_privilege('cafeteria_app', oid, 'EXECUTE'),
                           has_function_privilege('cafeteria_backup', oid, 'EXECUTE'),
                           has_function_privilege('cafeteria_auth_issuer', oid, 'EXECUTE'),
                           EXISTS (
                               SELECT 1
                               FROM aclexplode(COALESCE(proacl, acldefault('f', proowner))) acl
                               WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE'
                           )
                    FROM fn
                    '''
                ),
                {'signature': FUNCTION_SIGNATURE},
            ).one()
        )


def _dump_and_restore_schema(engine: Engine, backup_path: Path) -> None:
    docker = shutil.which('docker')
    assert docker is not None and DATABASE_URL is not None and PG16_TEST_CONTAINER is not None
    url = make_url(DATABASE_URL)
    assert url.database and url.username and url.password
    password_environment = f'PGPASSWORD={url.password}'
    with backup_path.open('wb') as backup_file:
        dump = subprocess.run(
            [docker, 'exec', '-e', password_environment, PG16_TEST_CONTAINER, 'pg_dump',
             '--format=custom', '--schema=cafeteria', '--username', url.username,
             '--dbname', url.database],
            check=False, stdout=backup_file, stderr=subprocess.PIPE, text=True,
        )
    assert dump.returncode == 0, dump.stderr
    _drop_schema(engine)
    with backup_path.open('rb') as backup_file:
        restore = subprocess.run(
            [docker, 'exec', '-i', '-e', password_environment, PG16_TEST_CONTAINER,
             'pg_restore', '--exit-on-error', '--no-owner', '--no-privileges',
             '--username', url.username, '--dbname', url.database],
            check=False, stdin=backup_file, stderr=subprocess.PIPE, text=True,
        )
    assert restore.returncode == 0, restore.stderr
    database._execute_script(engine, str(PERMISSIONS))


@LIVE_DATABASE
def test_migration_fresh_schema_and_restore_share_exact_function_contract(
    pg16: Engine,
    tmp_path: Path,
) -> None:
    for migration in database.migration_plan(SCHEMA):
        if migration.version > 13:
            break
        database._execute_migration(pg16, migration)
    v14 = next(migration for migration in database.migration_plan(SCHEMA) if migration.version == 14)
    database._execute_migration(pg16, v14)
    v15 = next(migration for migration in database.migration_plan(SCHEMA) if migration.version == 15)
    database._execute_migration(pg16, v15)
    database._execute_script(pg16, str(PERMISSIONS))
    migrated = _function_contract(pg16)
    with pg16.connect() as connection:
        migration_row = tuple(connection.execute(text('''
            SELECT version, name, application_version
            FROM cafeteria.schema_migrations WHERE version=14
        ''')).one())
        migration_row_v15 = tuple(connection.execute(text('''
            SELECT version, name, application_version
            FROM cafeteria.schema_migrations WHERE version=15
        ''')).one())
    _dump_and_restore_schema(pg16, tmp_path / 'schema-v15.dump')
    restored = _function_contract(pg16)
    _drop_schema(pg16)
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    fresh = _function_contract(pg16)
    assert migrated == restored == fresh
    assert migrated == (
        True, 'v', 'u', ['search_path=pg_catalog, cafeteria, pg_temp'],
        migrated[4], migrated[4],
        'TABLE(master_kind text, master_id smallint, code text, active boolean)',
        True, False, False, False,
    )
    assert migrated[4] != 'cafeteria_app'
    assert migration_row == (14, '0011_v13_to_v14.sql', 'dishboard-schema-v15')
    assert migration_row_v15 == (15, '0012_v14_to_v15.sql', 'dishboard-schema-v15')


def _call_helper(engine: Engine, labels: list[str | None], allergens: list[str | None]) -> list[tuple]:
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(
            text('SELECT * FROM cafeteria.lock_component_metadata_masters(:labels, :allergens)'),
            {'labels': labels, 'allergens': allergens},
        ).all()]


@LIVE_DATABASE
def test_helper_orders_deduplicates_and_preserves_namespaces_and_inactive_rows(
    seeded_pg16: Engine,
    app_engine: Engine,
) -> None:
    with seeded_pg16.begin() as connection:
        labels = connection.execute(text(
            'SELECT id, code FROM cafeteria.dietary_labels ORDER BY id LIMIT 2'
        )).all()
        allergens = connection.execute(text(
            'SELECT id, code FROM cafeteria.allergens ORDER BY id LIMIT 2'
        )).all()
        connection.execute(text(
            'UPDATE cafeteria.dietary_labels SET active=false WHERE id=:id'
        ), {'id': labels[0].id})
        connection.execute(text('''
            INSERT INTO cafeteria.dietary_labels(code, display_name)
            VALUES (:code, 'Namespace collision')
        '''), {'code': allergens[0].code})
    rows = _call_helper(
        app_engine,
        [labels[1].code, labels[0].code, labels[1].code, 'UNKNOWN', allergens[0].code],
        [allergens[1].code, allergens[0].code, allergens[1].code, 'UNKNOWN'],
    )

    assert [row[0] for row in rows] == ['label', 'label', 'label', 'allergen', 'allergen']
    assert [row[1] for row in rows[:3]] == sorted(row[1] for row in rows[:3])
    assert [row[1] for row in rows[3:]] == sorted(row[1] for row in rows[3:])
    assert ('label', labels[0].id, labels[0].code, False) in rows
    assert {row[0] for row in rows if row[2] == allergens[0].code} == {'label', 'allergen'}
    assert all(row[2] != 'UNKNOWN' for row in rows)


@LIVE_DATABASE
def test_helper_uses_bound_arrays_and_ignores_temp_shadow_objects(
    seeded_pg16: Engine,
    app_engine: Engine,
) -> None:
    injection = "X'); DELETE FROM cafeteria.dietary_labels; --"
    with app_engine.begin() as connection:
        connection.execute(text(
            'CREATE TEMP TABLE dietary_labels(id smallint, code text, active boolean)'
        ))
        connection.execute(text("INSERT INTO dietary_labels VALUES (1, 'VEGAN', false)"))
        rows = [tuple(row) for row in connection.execute(
            text('SELECT * FROM cafeteria.lock_component_metadata_masters(:l, :a)'),
            {'l': ['VEGAN', injection], 'a': []},
        ).all()]
        empty = connection.execute(text(
            'SELECT * FROM cafeteria.lock_component_metadata_masters('
            'CAST(ARRAY[] AS text[]), CAST(ARRAY[] AS text[]))'
        )).all()
    assert rows[0][0] == 'label' and rows[0][2] == 'VEGAN' and rows[0][3] is True
    assert all(row[2] != injection for row in rows)
    assert empty == []
    with seeded_pg16.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.dietary_labels')).scalar_one() > 0


@LIVE_DATABASE
def test_requested_master_update_waits_but_unrelated_master_remains_writable(
    seeded_pg16: Engine,
    app_engine: Engine,
) -> None:
    with seeded_pg16.connect() as connection:
        codes = connection.execute(text(
            'SELECT code FROM cafeteria.dietary_labels ORDER BY id LIMIT 2'
        )).scalars().all()
    locked = threading.Event()
    attempted = threading.Event()
    release = threading.Event()
    target_done = threading.Event()
    state: dict[str, int] = {}
    errors: list[BaseException] = []

    def hold_app_lock() -> None:
        try:
            with app_engine.begin() as connection:
                state['app_pid'] = connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
                connection.execute(
                    text('SELECT * FROM cafeteria.lock_component_metadata_masters(:l, :a)'),
                    {'l': [codes[0]], 'a': []},
                ).all()
                locked.set()
                assert release.wait(timeout=10)
        except BaseException as exc:
            errors.append(exc)
            locked.set()

    def update_locked_master() -> None:
        try:
            assert locked.wait(timeout=10)
            with seeded_pg16.begin() as connection:
                state['owner_pid'] = connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
                attempted.set()
                connection.execute(text(
                    'UPDATE cafeteria.dietary_labels SET active=NOT active WHERE code=:code'
                ), {'code': codes[0]})
            target_done.set()
        except BaseException as exc:
            errors.append(exc)
            attempted.set()
            target_done.set()

    app_thread = threading.Thread(target=hold_app_lock)
    owner_thread = threading.Thread(target=update_locked_master)
    app_thread.start()
    owner_thread.start()
    assert attempted.wait(timeout=10)
    blockers: list[int] = []
    with seeded_pg16.connect() as connection:
        for _ in range(1_000):
            blockers = connection.execute(
                text('SELECT pg_blocking_pids(:pid)'), {'pid': state['owner_pid']}
            ).scalar_one()
            if blockers:
                break
    assert blockers == [state['app_pid']]
    assert not target_done.is_set()
    with seeded_pg16.begin() as connection:
        assert connection.execute(text('''
            UPDATE cafeteria.dietary_labels SET active=NOT active WHERE code=:code
            RETURNING code
        '''), {'code': codes[1]}).scalar_one() == codes[1]
    release.set()
    app_thread.join(timeout=10)
    owner_thread.join(timeout=10)
    assert not app_thread.is_alive() and not owner_thread.is_alive()
    assert errors == []


@LIVE_DATABASE
def test_opposite_request_order_completes_without_deadlock(seeded_pg16: Engine) -> None:
    with seeded_pg16.connect() as connection:
        labels = connection.execute(text(
            'SELECT code FROM cafeteria.dietary_labels ORDER BY id LIMIT 2'
        )).scalars().all()
        allergens = connection.execute(text(
            'SELECT code FROM cafeteria.allergens ORDER BY id LIMIT 2'
        )).scalars().all()
    barrier = threading.Barrier(3)
    errors: list[BaseException] = []
    results: list[list[tuple]] = []

    def invoke(label_order: list[str], allergen_order: list[str]) -> None:
        engine = _role_engine('cafeteria_app', APP_PASSWORD)
        try:
            with engine.begin() as connection:
                barrier.wait(timeout=10)
                results.append([tuple(row) for row in connection.execute(
                    text('SELECT * FROM cafeteria.lock_component_metadata_masters(:l, :a)'),
                    {'l': label_order, 'a': allergen_order},
                ).all()])
        except BaseException as exc:
            errors.append(exc)
        finally:
            engine.dispose()

    threads = [
        threading.Thread(target=invoke, args=(labels, allergens)),
        threading.Thread(target=invoke, args=(list(reversed(labels)), list(reversed(allergens)))),
    ]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=10)
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert not any(getattr(getattr(error, 'orig', None), 'sqlstate', None) == '40P01' for error in errors)
    assert errors == []
    assert len(results) == 2 and results[0] == results[1]
