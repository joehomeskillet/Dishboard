"""Schema35 -> 36 food purchase price ledger migration."""
from __future__ import annotations

import hashlib

from sqlalchemy import text

from cafeteria import db as database
from prepared_food_fixtures import SCHEMA, app_engine, pg16, seeded_pg16  # noqa: F401
from test_component_scope_invariants_db import _seed_scope_probe
from test_rec_import_commit_migration_db import rows_and_sequences


def test_plan_ends_at_schema_36() -> None:
    plan = database.migration_plan(SCHEMA)
    assert database.SCHEMA_VERSION == 36
    assert (plan[-1].version, plan[-1].path.name) == (36, '0033_v35_to_v36.sql')


def test_v35_upgrade_adds_price_ledger_without_touching_weeks(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 35:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    _seed_scope_probe(pg16)
    with pg16.connect() as connection:
        weeks_before = connection.execute(text(
            'SELECT to_jsonb(w)::text FROM cafeteria.menu_weeks w ORDER BY id'
        )).all()
        max_before = connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one()
    assert max_before == 35
    before_rows, _ = rows_and_sequences(pg16)
    unaffected = {name for name in before_rows if name != 'schema_migrations'}
    assert database.run_migrations(pg16, SCHEMA) == plan
    after_rows, _ = rows_and_sequences(pg16)
    with pg16.connect() as connection:
        assert connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one() == 36
        assert connection.execute(text(
            "SELECT to_regclass('cafeteria.food_price_heads') IS NOT NULL"
        )).scalar_one() is True
        weeks_after = connection.execute(text(
            'SELECT to_jsonb(w)::text FROM cafeteria.menu_weeks w ORDER BY id'
        )).all()
        sha = connection.execute(text(
            "SELECT checksum_sha256 FROM cafeteria.schema_migrations WHERE version=36"
        )).scalar_one()
    assert weeks_after == weeks_before
    expected = hashlib.sha256(
        (SCHEMA.parent / 'migrations' / '0033_v35_to_v36.sql').read_bytes()
    ).hexdigest()
    assert sha == expected
    assert {k: v for k, v in after_rows.items() if k in unaffected} == \
        {k: v for k, v in before_rows.items() if k in unaffected}
