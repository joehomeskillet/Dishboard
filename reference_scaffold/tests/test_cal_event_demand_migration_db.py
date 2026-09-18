"""Schema36 -> 37 kitchen event demand copies."""
from __future__ import annotations

from sqlalchemy import text

from cafeteria import db as database
from prepared_food_fixtures import SCHEMA  # noqa: F401
from test_component_metadata_master_lock_db import installed_pg16, pg16  # noqa: F401
from test_component_scope_invariants_db import _seed_scope_probe
from test_rec_import_commit_migration_db import rows_and_sequences


def test_plan_ends_at_schema_37() -> None:
    plan = database.migration_plan(SCHEMA)
    assert database.SCHEMA_VERSION >= 37
    v37 = next(m for m in plan if m.version == 37)
    assert v37.path.name == '0034_v36_to_v37.sql'


def test_v36_upgrade_adds_event_demand_table(pg16, monkeypatch):  # noqa: F811
    monkeypatch.setattr(
        database,
        'MIGRATION_FILES',
        tuple(entry for entry in database.MIGRATION_FILES if entry[0] <= 37),
    )
    plan = database.migration_plan(SCHEMA)
    for migration in plan[:-1]:
        if migration.version <= 36:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    _seed_scope_probe(pg16)
    before_rows, _ = rows_and_sequences(pg16)
    unaffected = {name for name in before_rows if name != 'schema_migrations'}
    assert database.run_migrations(pg16, SCHEMA) == plan
    after_rows, _ = rows_and_sequences(pg16)
    with pg16.connect() as connection:
        assert connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one() == 37
        assert connection.execute(text(
            "SELECT to_regclass('cafeteria.kitchen_event_demand_items') IS NOT NULL"
        )).scalar_one() is True
    assert {k: v for k, v in after_rows.items() if k in unaffected} == \
        {k: v for k, v in before_rows.items() if k in unaffected}
