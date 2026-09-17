"""Schema38 -> 39 inventory journal."""
from sqlalchemy import text

from cafeteria import db as database
from prepared_food_fixtures import SCHEMA  # noqa: F401
from test_component_metadata_master_lock_db import installed_pg16, pg16  # noqa: F401
from test_component_scope_invariants_db import _seed_scope_probe
from test_rec_import_commit_migration_db import rows_and_sequences


def test_plan_ends_at_schema_39() -> None:
    plan = database.migration_plan(SCHEMA)
    assert database.SCHEMA_VERSION == 39
    assert (plan[-1].version, plan[-1].path.name) == (39, '0036_v38_to_v39.sql')


def test_v38_upgrade_adds_inventory_tables(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 38:
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
        )).scalar_one() == 39
        assert connection.execute(text(
            "SELECT to_regclass('cafeteria.inventory_movements') IS NOT NULL"
        )).scalar_one() is True
        cols = connection.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='cafeteria' AND table_name='foods'"
        )).scalars().all()
        assert 'stock' not in cols
    assert {k: v for k, v in after_rows.items() if k in unaffected} == \
        {k: v for k, v in before_rows.items() if k in unaffected}
