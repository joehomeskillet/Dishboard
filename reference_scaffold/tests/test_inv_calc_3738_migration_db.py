"""Schema39 -> 41 prepared batches and calculation receipts."""
from sqlalchemy import text

from cafeteria import db as database
from prepared_food_fixtures import SCHEMA  # noqa: F401
from test_component_metadata_master_lock_db import installed_pg16, pg16  # noqa: F401
from test_component_scope_invariants_db import _seed_scope_probe
from test_rec_import_commit_migration_db import rows_and_sequences


def test_plan_ends_at_schema_42() -> None:
    plan = database.migration_plan(SCHEMA)
    assert database.SCHEMA_VERSION == 42
    assert (plan[-1].version, plan[-1].path.name) == (42, '0039_v41_to_v42.sql')
    names = [item.path.name for item in plan[-2:]]
    assert names == ['0038_v40_to_v41.sql', '0039_v41_to_v42.sql']


def test_upgrade_adds_batch_and_receipt_tables(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 39:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    _seed_scope_probe(pg16)
    assert database.run_migrations(pg16, SCHEMA) == plan
    with pg16.connect() as connection:
        assert connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one() == 42
        assert connection.execute(text(
            "SELECT to_regclass('cafeteria.prepared_batch_runs') IS NOT NULL"
        )).scalar_one() is True
        assert connection.execute(text(
            "SELECT to_regclass('cafeteria.calculation_receipts') IS NOT NULL"
        )).scalar_one() is True
        assert connection.execute(text(
            "SELECT 1 FROM pg_constraint WHERE conname='calculation_receipts_subject_key'"
        )).scalar_one() == 1
        assert connection.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_schema='cafeteria' "
            "AND table_name='order_basket_lines' AND column_name='raw_quantity'"
        )).scalar_one() == 1
