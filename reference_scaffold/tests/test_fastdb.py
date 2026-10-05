"""Real PostgreSQL proof that golden resets retain schema, data and role contracts."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from test_admin_workflow_routes import (  # noqa: F401
    APP_PASSWORD, BACKUP_PASSWORD, DATABASE_URL, ISSUER_PASSWORD, ROOT, database, database_engine,
)


def catalog(engine):
    queries = {
        'columns': "SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='cafeteria' ORDER BY table_name,ordinal_position",
        'table_grants': "SELECT grantor,grantee,table_name,privilege_type,is_grantable FROM information_schema.role_table_grants WHERE table_schema='cafeteria' ORDER BY 1,2,3,4,5",
        'routine_grants': "SELECT grantor,grantee,routine_name,privilege_type,is_grantable FROM information_schema.role_routine_grants WHERE specific_schema='cafeteria' ORDER BY 1,2,3,4,5",
        'roles': "SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolconnlimit,rolvaliduntil::text,rolbypassrls,rolconfig FROM pg_roles WHERE rolname LIKE 'cafeteria%' ORDER BY rolname",
        'constraints': "SELECT c.relname,con.conname,pg_get_constraintdef(con.oid) FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='cafeteria' ORDER BY 1,2",
        'functions': "SELECT p.proname,pg_get_function_identity_arguments(p.oid),p.proacl,p.proconfig,p.prosecdef FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='cafeteria' ORDER BY 1,2",
    }
    with engine.connect() as connection:
        result = {name: connection.execute(text(query)).all() for name, query in queries.items()}
        tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='cafeteria' ORDER BY tablename")).scalars().all()
        for table in tables:
            quoted = engine.dialect.identifier_preparer.quote(table)
            # Includes complete migration-checksum rows and every seeded table, not only counts.
            result['table:' + table] = connection.execute(text(
                f"SELECT count(*),md5(string_agg(row_to_json(t)::text, '' ORDER BY row_to_json(t)::text)) FROM cafeteria.{quoted} t"
            )).all()
        return result


def test_reset_preserves_catalog_counts_checksums_and_role_logins(database_engine):  # noqa: F811
    from _support.fastdb import cleanup, restore_database
    before = catalog(database_engine)
    calls = []
    identity = str(uuid4())
    try:
        restore_database(database_engine, identity, lambda: calls.append('build'))
        with database_engine.begin() as connection:
            connection.execute(text('CREATE TABLE cafeteria.fastdb_probe (id integer)'))
            connection.execute(text('INSERT INTO cafeteria.fastdb_probe VALUES (1)'))
        restore_database(database_engine, identity, lambda: calls.append('build'))
        assert calls == ['build']
        assert catalog(database_engine) == before
        for role, password in [('cafeteria_app', APP_PASSWORD), ('cafeteria_backup', BACKUP_PASSWORD),
                               ('cafeteria_auth_issuer', ISSUER_PASSWORD)]:
            engine = create_engine(make_url(DATABASE_URL).set(username=role, password=password))
            try:
                with engine.connect() as connection:
                    assert connection.execute(text('SELECT current_user')).scalar_one() == role
            finally:
                engine.dispose()
    finally:
        cleanup()


def test_reset_refuses_connected_clients_without_terminating_them(database_engine):  # noqa: F811
    from _support.fastdb import cleanup, restore_database
    identity = str(uuid4())
    try:
        restore_database(database_engine, identity, lambda: None)
        original_pool = database_engine.pool
        with database_engine.connect() as connection:
            with pytest.raises(RuntimeError, match='active connections'):
                restore_database(database_engine, identity, lambda: None)
            assert database_engine.pool is original_pool
            assert connection.execute(text('SELECT count(*) FROM cafeteria.locations')).scalar_one() > 0
    finally:
        cleanup()


@pytest.mark.parametrize('url', ['postgresql://example.invalid/test_db', 'postgresql://127.0.0.1/live'])
def test_reset_rejects_non_test_targets_before_connecting(url):
    from _support.fastdb import restore_database
    engine = create_engine(url.replace('postgresql:', 'postgresql+psycopg:'))
    try:
        with pytest.raises(ValueError, match='loopback'):
            restore_database(engine, 'unused', lambda: pytest.fail('must not build'))
    finally:
        engine.dispose()


def test_init_adapter_reprovisions_roles_and_runs_real_validation(database_engine):  # noqa: F811
    from _support.fastdb import cleanup, init_database
    options = dict(permissions_path=str(ROOT / 'database' / 'permissions.sql'),
                   app_password=APP_PASSWORD, backup_password=BACKUP_PASSWORD,
                   auth_issuer_password=ISSUER_PASSWORD)
    try:
        database_engine.dispose()
        first = init_database(DATABASE_URL, str(ROOT / 'database' / 'schema.sql'),
                              str(ROOT / 'database' / 'seed.sql'), **options)
        expected = catalog(database_engine)
        with database_engine.begin() as connection:
            connection.execute(text('ALTER ROLE cafeteria_app NOLOGIN'))
        database_engine.dispose()
        second = init_database(DATABASE_URL, str(ROOT / 'database' / 'schema.sql'),
                               str(ROOT / 'database' / 'seed.sql'), **options)
        assert second == first
        assert catalog(database_engine) == expected
    finally:
        database.provision_database_roles(database_engine, app_password=APP_PASSWORD,
                                          backup_password=BACKUP_PASSWORD,
                                          auth_issuer_password=ISSUER_PASSWORD)
        cleanup()


def test_reset_waits_for_a_connection_which_is_already_closing(database_engine):  # noqa: F811
    from threading import Timer
    from sqlalchemy.pool import NullPool
    from _support.fastdb import cleanup, restore_database
    identity = str(uuid4())
    restore_database(database_engine, identity, lambda: None)
    other = create_engine(DATABASE_URL, poolclass=NullPool)
    connection = other.connect()
    timer = Timer(0.1, connection.close)
    timer.start()
    try:
        restore_database(database_engine, identity, lambda: None)
        assert connection.closed
        with database_engine.connect() as current:
            assert current.execute(text('SELECT count(*) FROM cafeteria.locations')).scalar_one() > 0
    finally:
        timer.join()
        connection.close()
        other.dispose()
        cleanup()


def test_reset_finalizes_unreachable_pooled_clients_without_closing_live_clients(database_engine):  # noqa: F811
    import gc
    import weakref
    from _support.fastdb import cleanup, restore_database
    identity = str(uuid4())
    restore_database(database_engine, identity, lambda: None)
    enabled = gc.isenabled()
    gc.disable()
    try:
        abandoned = create_engine(DATABASE_URL)
        with abandoned.connect() as connection:
            connection.execute(text('SELECT 1'))
        del connection
        reference = weakref.ref(abandoned)
        cycle = [abandoned]
        cycle.append(cycle)
        del abandoned, cycle
        assert reference() is not None
        restore_database(database_engine, identity, lambda: pytest.fail('must reuse snapshot'))
        assert reference() is None
    finally:
        if enabled:
            gc.enable()
        gc.collect()
        cleanup()
