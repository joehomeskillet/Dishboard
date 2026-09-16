"""Schema34 -> 35 kitchen event header migration."""
from __future__ import annotations

import hashlib

from sqlalchemy import text

from cafeteria import db as database
from test_component_metadata_master_lock_db import ROOT  # noqa: F401
from test_component_scope_invariants_db import _seed_scope_probe
from prepared_food_fixtures import pg16, seeded_pg16, app_engine, installed_pg16  # noqa: F401
from test_master_data_db import make_actor
from test_rec_import_commit_migration_db import rows_and_sequences

SCHEMA = ROOT / 'database' / 'schema.sql'


def test_plan_ends_at_schema_35() -> None:
    plan = database.migration_plan(SCHEMA)
    assert database.SCHEMA_VERSION == 35
    assert (plan[-1].version, plan[-1].path.name) == (35, '0032_v34_to_v35.sql')
    expected = hashlib.sha256(
        (SCHEMA.parent / 'migrations' / '0032_v34_to_v35.sql').read_bytes()
    ).hexdigest()
    assert expected == '6eeec799dad37cb60bc54cdaf691c5abd0c451244e4b4931fe34ea3ee359ca41'


def test_v34_upgrade_adds_kitchen_events_without_touching_weeks(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 34:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    _seed_scope_probe(pg16)
    with pg16.connect() as connection:
        weeks_before = connection.execute(text(
            'SELECT to_jsonb(w)::text FROM cafeteria.menu_weeks w ORDER BY id'
        )).all()
        pubs_before = connection.execute(text(
            'SELECT to_jsonb(r)::text FROM cafeteria.publication_revisions r ORDER BY id'
        )).all()
        max_before = connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one()
    assert max_before == 34
    before_rows, _ = rows_and_sequences(pg16)
    unaffected = {name for name in before_rows if name != 'schema_migrations'}
    assert database.run_migrations(pg16, SCHEMA) == plan
    after_rows, _ = rows_and_sequences(pg16)
    with pg16.connect() as connection:
        assert connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one() == 35
        assert connection.execute(text(
            "SELECT to_regclass('cafeteria.kitchen_events') IS NOT NULL"
        )).scalar_one() is True
        weeks_after = connection.execute(text(
            'SELECT to_jsonb(w)::text FROM cafeteria.menu_weeks w ORDER BY id'
        )).all()
        pubs_after = connection.execute(text(
            'SELECT to_jsonb(r)::text FROM cafeteria.publication_revisions r ORDER BY id'
        )).all()
        has_recipe_col = connection.execute(text(
            "SELECT exists(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='cafeteria' AND table_name='kitchen_events' "
            "AND column_name='recipe_revision_id')"
        )).scalar_one()
    assert weeks_after == weeks_before
    assert pubs_after == pubs_before
    assert has_recipe_col is False
    assert {k: v for k, v in after_rows.items() if k in unaffected} == \
        {k: v for k, v in before_rows.items() if k in unaffected}


def test_app_can_insert_kitchen_event(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    with app_engine.begin() as connection:
        public_id = connection.execute(text('''
            INSERT INTO cafeteria.kitchen_events(
                location_id, event_date, profile_scope, title, guest_count, created_by, updated_by)
            VALUES (:location, DATE '2026-09-22', 'patient', 'Visite', 0, :actor, :actor)
            RETURNING public_id
        '''), {'location': ids['location'], 'actor': actor.user_id}).scalar_one()
        assert public_id is not None
