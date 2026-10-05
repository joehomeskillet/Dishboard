"""Process-local golden databases for explicitly opted-in disposable test fixtures.

Keep the original database name/URL. Never terminate another connection. Cluster
roles remain the responsibility of the existing fixture's provisioning step.
"""
from __future__ import annotations

import atexit
import gc
import hashlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool, QueuePool


@dataclass
class Snapshot:
    maintenance: Engine
    original: URL
    template: str


_snapshots: dict[tuple[URL, str], Snapshot] = {}


def source_fingerprint(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.rglob('*.sql')):
        digest.update(path.relative_to(directory).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _validate(engine: Engine) -> None:
    url = engine.url
    if (url.get_backend_name() != 'postgresql' or url.host not in {'localhost', '127.0.0.1', '::1'}
            or not url.database or 'test' not in url.database.lower() or url.query):
        raise ValueError('fastdb requires a loopback PostgreSQL test database without URL overrides')


def _sql(engine: Engine, statement: str) -> None:
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.exec_driver_sql(statement)


def _assert_idle(maintenance: Engine, database: str) -> None:
    deadline = time.monotonic() + 2.0
    collected = False
    while True:
        # A new transaction obtains fresh statistics after a backend disconnect.
        with maintenance.connect() as connection:
            count = connection.execute(text(
                'SELECT count(*) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()'
            ), {'name': database}).scalar_one()
        if not count:
            return
        if not collected:
            # Flask/engine reference cycles may outlive a completed fixture.
            # Finalize only unreachable Python objects; live clients remain protected.
            gc.collect()
            collected = True
            continue
        if time.monotonic() >= deadline:
            raise RuntimeError('fastdb refuses reset: active connections remain in the test database')
        time.sleep(0.01)  # Condition-based drain, never a fixed delay on a ready database.


def _dispose_idle(engine: Engine) -> None:
    # Disposing with checked-out connections can orphan a pool which later keeps
    # its returned connections alive. Refusal must leave that client's pool intact.
    if isinstance(engine.pool, QueuePool) and engine.pool.checkedout():
        raise RuntimeError('fastdb refuses reset: active connections remain in the test database')
    if isinstance(engine.pool, NullPool):
        # NullPool retains no idle clients. Keep its identity until the server-side
        # connection check accepts the reset; dispose cannot close its live clients.
        return
    if not isinstance(engine.pool, QueuePool):
        raise ValueError('fastdb requires QueuePool or NullPool')
    engine.dispose()


def _snapshot(engine: Engine, build: Callable[[], None]) -> Snapshot:
    # CREATE DATABASE TEMPLATE does not copy database-level ACL/configuration.
    # Refuse those non-default cases before creating or dropping anything.
    _dispose_idle(engine)
    _assert_idle(engine, str(engine.url.database))
    with engine.connect() as connection:
        supported = connection.execute(text('''
            SELECT d.datacl IS NULL AND d.datconnlimit=-1 AND d.datallowconn
                   AND NOT d.datistemplate AND pg_get_userbyid(d.datdba)=current_user
                   AND NOT EXISTS (SELECT 1 FROM pg_db_role_setting s WHERE s.setdatabase=d.oid)
              FROM pg_database d WHERE d.datname=current_database()
        ''')).scalar_one()
    if not supported:
        raise RuntimeError('fastdb refuses database with custom ownership, ACL or configuration')
    build()
    _dispose_idle(engine)
    tag = f'test_gate_{os.getpid()}_{uuid4().hex[:10]}'
    maintenance_name = tag + '_admin'
    template_name = tag + '_golden'
    quote = engine.dialect.identifier_preparer.quote
    _sql(engine, 'CREATE DATABASE ' + quote(maintenance_name))
    _dispose_idle(engine)
    maintenance = create_engine(engine.url.set(database=maintenance_name), poolclass=NullPool)
    try:
        _assert_idle(maintenance, str(engine.url.database))
        _sql(maintenance, 'CREATE DATABASE ' + quote(template_name) + ' TEMPLATE '
             + quote(str(engine.url.database)) + ' ALLOW_CONNECTIONS false')
    except (RuntimeError, SQLAlchemyError):
        # Cleanup then re-raise: never turn an unsuccessful clone into a passing reset.
        maintenance.dispose()
        _sql(engine, 'DROP DATABASE ' + quote(maintenance_name))
        raise
    return Snapshot(maintenance, engine.url, template_name)


def restore_database(engine: Engine, identity: str, build: Callable[[], None]) -> None:
    _validate(engine)
    key = (engine.url, identity)
    snapshot = _snapshots.get(key)
    if snapshot is None:
        _snapshots[key] = _snapshot(engine, build)
        return
    _dispose_idle(engine)
    _assert_idle(snapshot.maintenance, str(engine.url.database))
    quote = engine.dialect.identifier_preparer.quote
    _sql(snapshot.maintenance, 'DROP DATABASE ' + quote(str(engine.url.database)))
    _sql(snapshot.maintenance, 'CREATE DATABASE ' + quote(str(engine.url.database))
         + ' TEMPLATE ' + quote(snapshot.template))


def init_database(database_url: str, schema_path: str, seed_path: str, *,
                  permissions_path: str | None = None, demo_seed_path: str | None = None,
                  app_password: str = '', backup_password: str = '',
                  auth_issuer_password: str = '', seed_demo: bool = False) -> dict[str, Any]:
    """Fixture adapter: preserve role provisioning and run the real validator every time."""
    from cafeteria import db as database

    engine = create_engine(database_url, pool_pre_ping=True)
    identity = 'init:' + source_fingerprint(Path(schema_path).parent) + repr((
        schema_path, seed_path, permissions_path, demo_seed_path, seed_demo,
    ))

    def build() -> None:
        database.init_database(
            database_url, schema_path, seed_path, permissions_path=permissions_path,
            demo_seed_path=demo_seed_path, app_password=app_password,
            backup_password=backup_password, auth_issuer_password=auth_issuer_password,
            seed_demo=seed_demo,
        )

    try:
        _validate(engine)
        if (engine.url, identity) in _snapshots:
            database.provision_database_roles(
                engine, app_password=app_password, backup_password=backup_password,
                auth_issuer_password=auth_issuer_password,
            )
        restore_database(engine, identity, build)
        return database.validate_database(engine)
    finally:
        engine.dispose()


def cleanup() -> None:
    for key, snapshot in list(_snapshots.items()):
        quote = snapshot.maintenance.dialect.identifier_preparer.quote
        _sql(snapshot.maintenance, 'DROP DATABASE ' + quote(snapshot.template))
        maintenance_name = str(snapshot.maintenance.url.database)
        snapshot.maintenance.dispose()
        original = create_engine(snapshot.original, poolclass=NullPool)
        try:
            _sql(original, 'DROP DATABASE ' + quote(maintenance_name))
        finally:
            original.dispose()
        del _snapshots[key]


atexit.register(cleanup)
