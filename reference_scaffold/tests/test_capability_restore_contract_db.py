"""Canonical recovery contract; run against disposable PostgreSQL 16 and 18."""
from __future__ import annotations

import hashlib

import pytest
from psycopg import Error as PsycopgError
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from cafeteria import db as database
from test_database_invariants import ROOT, database_engine as database_engine


def state(engine: Engine) -> tuple[object, ...]:
    with engine.connect() as connection:
        return tuple(connection.execute(text("""SELECT
            (SELECT md5(coalesce(jsonb_agg(to_jsonb(s) ORDER BY id)::text,''))
             FROM cafeteria.auth_capability_secrets s),
            (SELECT md5(coalesce(jsonb_agg(to_jsonb(n) ORDER BY nonce)::text,''))
             FROM cafeteria.auth_capability_nonces n),
            (SELECT md5(coalesce(jsonb_agg(to_jsonb(a) ORDER BY id)::text,''))
             FROM cafeteria.audit_events a),
            (SELECT md5(coalesce(jsonb_agg(to_jsonb(u) ORDER BY id)::text,''))
             FROM cafeteria.users u),
            (SELECT md5(coalesce(jsonb_agg(to_jsonb(s) ORDER BY id)::text,''))
             FROM cafeteria.settings s)""")).one())


def function_contract(engine: Engine) -> tuple[object, ...]:
    with engine.connect() as connection:
        return tuple(connection.execute(text("""SELECT p.prosrc,p.prosecdef,p.proconfig,
            p.proowner=n.nspowner,p.proacl::text
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE p.oid='cafeteria.ensure_auth_capability_state()'::regprocedure""")).one())


@pytest.mark.parametrize('mutation', [
    'ALTER TABLE cafeteria.auth_capability_secrets ALTER COLUMN secret DROP NOT NULL',
    '''UPDATE cafeteria.auth_capability_secrets SET active=false,retired_at=clock_timestamp();
       ALTER TABLE cafeteria.auth_capability_secrets ALTER COLUMN retired_at SET NOT NULL''',
    'ALTER TABLE cafeteria.auth_capability_secrets DROP CONSTRAINT auth_capability_secrets_pkey',
    'ALTER TABLE cafeteria.auth_capability_nonces DROP CONSTRAINT auth_capability_nonces_nonce_check',
    'ALTER TABLE cafeteria.auth_capability_nonces ADD CHECK (octet_length(nonce)>0)',
    'ALTER TABLE cafeteria.auth_capability_nonces ADD UNIQUE (actor_user_id,revision_id)',
    "UPDATE pg_constraint SET connamespace='public'::regnamespace WHERE conrelid='cafeteria.auth_capability_secrets'::regclass AND contype='c'",
    '''ALTER TABLE cafeteria.auth_capability_nonces DROP CONSTRAINT auth_capability_nonces_nonce_check;
       ALTER TABLE cafeteria.auth_capability_nonces ADD CHECK (octet_length(nonce)=15)''',
    '''ALTER TABLE cafeteria.auth_capability_nonces DROP CONSTRAINT auth_capability_nonces_actor_user_id_fkey;
       ALTER TABLE cafeteria.auth_capability_nonces ADD FOREIGN KEY (actor_user_id) REFERENCES cafeteria.locations(id)''',
    '''ALTER TABLE cafeteria.auth_capability_nonces DROP CONSTRAINT auth_capability_nonces_actor_user_id_fkey;
       ALTER TABLE cafeteria.auth_capability_nonces ADD FOREIGN KEY (actor_user_id) REFERENCES cafeteria.users(id) ON DELETE CASCADE''',
    '''ALTER TABLE cafeteria.auth_capability_nonces ALTER CONSTRAINT auth_capability_nonces_actor_user_id_fkey DEFERRABLE''',
    '''ALTER TABLE cafeteria.auth_capability_nonces DROP CONSTRAINT auth_capability_nonces_actor_user_id_fkey;
       ALTER TABLE cafeteria.auth_capability_nonces ADD FOREIGN KEY (actor_user_id) REFERENCES cafeteria.users(id) NOT VALID''',
    'ALTER SEQUENCE cafeteria.auth_capability_secrets_id_seq RENAME TO noncanonical_identity',
    '''DROP INDEX cafeteria.uq_auth_capability_one_active;
       CREATE UNIQUE INDEX uq_auth_capability_one_active ON cafeteria.auth_capability_secrets (id)''',
    '''DROP INDEX cafeteria.uq_auth_capability_one_active;
       CREATE INDEX uq_auth_capability_one_active ON cafeteria.auth_capability_secrets ((true)) WHERE active''',
])
def test_malformed_constraints_fail_before_reset(database_engine: Engine, mutation: str) -> None:
    with database_engine.begin() as connection:
        connection.exec_driver_sql(mutation)
    before = state(database_engine)
    with pytest.raises(DBAPIError) as failure, database_engine.begin() as connection:
        connection.execute(text('SELECT cafeteria.hard_reset_auth_capability_state()'))
    assert isinstance(failure.value.orig, PsycopgError) and failure.value.orig.sqlstate == '55000'
    assert state(database_engine) == before


@pytest.mark.parametrize('field', ['convalidated', 'conenforced'])
def test_pg18_not_null_must_be_validated_and_enforced(database_engine: Engine, field: str) -> None:
    with database_engine.begin() as connection:
        if int(connection.execute(text('SHOW server_version_num')).scalar_one()) < 180000:
            pytest.skip('PG18 NOT NULL catalog representation only')
        # Simulate malformed restored catalog metadata without weakening attnotnull.
        if field == 'convalidated':
            connection.execute(text("""UPDATE pg_constraint SET convalidated=false
                WHERE conrelid='cafeteria.auth_capability_secrets'::regclass
                  AND contype='n' AND conkey=ARRAY[2]::smallint[]"""))
        else:
            connection.execute(text("""UPDATE pg_constraint SET conenforced=false
                WHERE conrelid='cafeteria.auth_capability_secrets'::regclass
                  AND contype='n' AND conkey=ARRAY[2]::smallint[]"""))
        assert connection.execute(text("""SELECT attnotnull FROM pg_attribute
            WHERE attrelid='cafeteria.auth_capability_secrets'::regclass AND attnum=2""")).scalar_one()
    before = state(database_engine)
    with pytest.raises(DBAPIError) as failure, database_engine.begin() as connection:
        connection.execute(text('SELECT cafeteria.hard_reset_auth_capability_state()'))
    assert isinstance(failure.value.orig, PsycopgError) and failure.value.orig.sqlstate == '55000'
    assert state(database_engine) == before


def test_v23_upgrade_preserves_state_and_matches_fresh_contract(database_engine: Engine) -> None:
    pg16 = database_engine
    with pg16.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    plan = database.migration_plan(ROOT / 'database/schema.sql')
    guard_migration = next(migration for migration in plan if migration.version == 24)
    for migration in plan:
        if migration.version >= 24:
            break
        database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(ROOT / 'database/seed.sql'))
    # Historical migrations supply the v23 grants; current permissions require v25.
    before = state(pg16)
    old_contract = function_contract(pg16)
    with pg16.connect() as connection:
        version = int(connection.execute(text('SHOW server_version_num')).scalar_one())
        ledger = connection.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m ORDER BY version')).all()
    # Reproduce the defect from the real historical product function.
    if version >= 180000:
        with pytest.raises(DBAPIError) as failure, pg16.begin() as connection:
            connection.execute(text('SELECT cafeteria.ensure_auth_capability_state()'))
        assert isinstance(failure.value.orig, PsycopgError) and failure.value.orig.sqlstate == '55000'
    else:
        with pg16.begin() as connection:
            assert connection.execute(text('SELECT cafeteria.ensure_auth_capability_state()')).scalar_one() == 1
    database.run_migrations(pg16, ROOT / 'database/schema.sql')
    assert state(pg16) == before
    upgraded = function_contract(pg16)
    assert upgraded[1:] == old_contract[1:]
    with pg16.begin() as connection:
        assert connection.execute(text('SELECT to_jsonb(m) FROM cafeteria.schema_migrations m WHERE version<24 ORDER BY version')).all() == ledger
        assert connection.execute(text('SELECT checksum_sha256 FROM cafeteria.schema_migrations WHERE version=24')).scalar_one() == hashlib.sha256(guard_migration.path.read_bytes()).hexdigest()
        for _ in range(2):
            assert connection.execute(text('SELECT cafeteria.ensure_auth_capability_state()')).scalar_one() == 1
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    database._execute_script(pg16, str(ROOT / 'database/schema.sql'))
    database._execute_script(pg16, str(ROOT / 'database/permissions.sql'))
    assert function_contract(pg16) == upgraded


def test_canonical_and_migration_function_bytes_match() -> None:
    schema = (ROOT / 'database/schema.sql').read_text()
    migration = (ROOT / 'database/migrations/0021_v23_to_v24.sql').read_text()
    start = schema.index('CREATE OR REPLACE FUNCTION ensure_auth_capability_state()')
    stop = schema.index('CREATE OR REPLACE FUNCTION hard_reset_auth_capability_state()', start)
    assert schema[start:stop].strip() in migration
