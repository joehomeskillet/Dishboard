"""Schema37 -> 38 suppliers and baskets."""
from sqlalchemy import text

from cafeteria import db as database
from prepared_food_fixtures import SCHEMA  # noqa: F401
from test_component_metadata_master_lock_db import installed_pg16, pg16  # noqa: F401
from test_component_scope_invariants_db import _seed_scope_probe
from test_rec_import_commit_migration_db import rows_and_sequences


def test_plan_ends_at_schema_38() -> None:
    plan = database.migration_plan(SCHEMA)
    assert database.SCHEMA_VERSION >= 38
    v38 = next(m for m in plan if m.version == 38)
    assert v38.path.name == '0035_v37_to_v38.sql'


def test_v37_upgrade_adds_supplier_tables_and_preferred_index(pg16, monkeypatch):  # noqa: F811
    monkeypatch.setattr(
        database,
        'MIGRATION_FILES',
        tuple(entry for entry in database.MIGRATION_FILES if entry[0] <= 38),
    )
    plan = database.migration_plan(SCHEMA)
    for migration in plan[:-1]:
        if migration.version <= 37:
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
        )).scalar_one() == 38
        assert connection.execute(text(
            "SELECT to_regclass('cafeteria.suppliers') IS NOT NULL"
        )).scalar_one() is True
        idx = connection.execute(text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='cafeteria' AND indexname='supplier_articles_preferred_food_idx'"
        )).scalar_one()
        assert 'WHERE' in idx and 'preferred' in idx and 'food_id IS NOT NULL' in idx
    assert {k: v for k, v in after_rows.items() if k in unaffected} == \
        {k: v for k, v in before_rows.items() if k in unaffected}
