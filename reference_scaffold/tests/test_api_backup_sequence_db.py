from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from tests.test_component_metadata_master_lock_db import (
    BACKUP_PASSWORD,
    DATABASE_URL,
    PERMISSIONS,
    PG16_TEST_CONTAINER,
    SCHEMA,
    _role_url,
    pg16 as pg16,
)


def _install_v17(engine: Engine, source: str) -> None:
    if source == 'migration':
        database.run_migrations(engine, SCHEMA)
    else:
        database._execute_script(engine, str(SCHEMA))


def _assert_backup_sequence_read_only(engine: Engine) -> None:
    with engine.connect() as connection:
        role = connection.execute(text('''
            SELECT rolsuper, rolinherit,
                   (SELECT count(*) FROM pg_auth_members WHERE member=roles.oid)
            FROM pg_roles roles WHERE rolname='cafeteria_backup'
        ''')).one()
        assert tuple(role) == (False, False, 0)
    backup = create_engine(_role_url('cafeteria_backup', BACKUP_PASSWORD), poolclass=NullPool)
    try:
        with backup.connect() as connection:
            privileges = connection.execute(text('''
                SELECT current_user,
                       has_sequence_privilege(current_user, 'cafeteria.api_keys_id_seq', 'SELECT'),
                       has_sequence_privilege(current_user, 'cafeteria.api_keys_id_seq', 'USAGE'),
                       has_sequence_privilege(current_user, 'cafeteria.api_keys_id_seq', 'UPDATE')
            ''')).one()
            assert tuple(privileges) == ('cafeteria_backup', True, False, False)
    finally:
        backup.dispose()


@pytest.mark.parametrize('source', ['migration', 'schema'])
def test_api_key_backup_sequence_grant_at_install(pg16: Engine, source: str) -> None:
    _install_v17(pg16, source)
    _assert_backup_sequence_read_only(pg16)


@pytest.mark.parametrize('source', ['migration', 'schema'])
def test_api_key_backup_dump_after_permissions_reapply(
    pg16: Engine, source: str, tmp_path: Path,
) -> None:
    _install_v17(pg16, source)
    # Restore and maintenance both reapply the complete least-privilege contract.
    database._execute_script(pg16, str(PERMISSIONS))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.begin() as connection:
        connection.execute(text("SELECT setval('cafeteria.api_keys_id_seq', 17, true)"))

    docker = shutil.which('docker')
    assert docker is not None and PG16_TEST_CONTAINER and DATABASE_URL
    assert pg16.url.database and pg16.url.database.startswith(('menuplan_test', 'menuplan_task'))
    environment = {**os.environ, 'PGPASSWORD': BACKUP_PASSWORD}
    dump_path = tmp_path / 'backup.dump'
    with dump_path.open('wb') as dump_file:
        result = subprocess.run(
            [docker, 'exec', '-e', 'PGPASSWORD', PG16_TEST_CONTAINER,
             'pg_dump', '--host=127.0.0.1', '--username=cafeteria_backup',
             '--dbname', pg16.url.database, '--schema=cafeteria',
             '--exclude-table=cafeteria.auth_capability_secrets',
             '--exclude-table=cafeteria.auth_capability_nonces',
             '--exclude-table=cafeteria.auth_capability_secrets_id_seq',
             '--format=custom', '--compress=9', '--no-owner', '--no-privileges',
             '--lock-wait-timeout=10s'],
            env=environment, check=False, stdout=dump_file, stderr=subprocess.PIPE,
            text=True, timeout=60,
        )
    assert result.returncode == 0, result.stderr
    with dump_path.open('rb') as dump_file:
        contents = subprocess.run(
            [docker, 'exec', '-i', PG16_TEST_CONTAINER, 'pg_restore', '--list'],
            check=False, stdin=dump_file, capture_output=True, text=True, timeout=60,
        )
    assert contents.returncode == 0, contents.stderr
    assert 'SEQUENCE SET cafeteria api_keys_id_seq' in contents.stdout
    assert 'TABLE DATA cafeteria api_keys' in contents.stdout
    assert 'auth_capability_secrets' not in contents.stdout
    assert 'auth_capability_nonces' not in contents.stdout
    _assert_backup_sequence_read_only(pg16)
