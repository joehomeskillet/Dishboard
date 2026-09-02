from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria import db as database


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'database' / 'schema.sql'
MIGRATION = ROOT / 'database' / 'migrations' / '0010_v12_to_v13.sql'
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
LIVE_DATABASE = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-16-Testdatenbank fehlt.',
)


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


@pytest.fixture
def pg16() -> Iterator[Engine]:
    if not DATABASE_URL:
        pytest.skip('TEST_DATABASE_URL für eine isolierte PostgreSQL-16-Testdatenbank fehlt.')
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.provision_database_roles(
        engine,
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    try:
        with engine.connect() as connection:
            server_version = int(connection.execute(text("SHOW server_version_num")).scalar_one())
        assert 160_000 <= server_version < 170_000
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


def _run_v12_migrations(engine: Engine) -> None:
    for migration in database.migration_plan(SCHEMA):
        if migration.version > 12:
            break
        database._execute_migration(engine, migration)


def _v13_migration() -> database.Migration:
    return next(migration for migration in database.migration_plan(SCHEMA) if migration.version == 13)


def test_schema_v13_migration_is_registered_and_has_a_strict_terminator() -> None:
    plan = database.migration_plan(SCHEMA)

    assert database.SCHEMA_VERSION == 13
    assert database.APPLICATION_VERSION == 'dishboard-schema-v13'
    assert (plan[-1].version, plan[-1].path.name) == (13, '0010_v12_to_v13.sql')
    assert MIGRATION.read_text(encoding='utf-8').startswith('BEGIN;')
    assert MIGRATION.read_text(encoding='utf-8').rstrip().endswith('COMMIT;')


@LIVE_DATABASE
def test_v13_migration_is_idempotent_and_exposes_internal_and_public_component_ids(
    pg16: Engine,
) -> None:
    database.run_migrations(pg16, SCHEMA)
    database.run_migrations(pg16, SCHEMA)

    with pg16.connect() as connection:
        version = connection.execute(
            text('SELECT version FROM cafeteria.schema_migrations ORDER BY version DESC LIMIT 1')
        ).scalar_one()
        columns = connection.execute(
            text(
                '''
                SELECT column_name, data_type, is_nullable, identity_generation
                FROM information_schema.columns
                WHERE table_schema='cafeteria' AND table_name='menu_components'
                ORDER BY ordinal_position
                '''
            )
        ).mappings().all()
        index_definition = connection.execute(
            text(
                '''
                SELECT pg_get_indexdef(indexrelid)
                FROM pg_index
                WHERE indrelid='cafeteria.menu_components'::regclass AND indisunique
                  AND pg_get_indexdef(indexrelid) ILIKE '%lower(btrim(name))%'
                '''
            )
        ).scalar_one()
        modes = connection.execute(
            text(
                '''
                SELECT allergen_mode, origin_mode, label_mode
                FROM cafeteria.menu_items
                LIMIT 0
                '''
            )
        ).keys()

    by_name = {row.column_name: row for row in columns}
    assert version == 13
    assert by_name['id'].data_type == 'bigint'
    assert by_name['id'].identity_generation == 'ALWAYS'
    assert by_name['public_id'].data_type == 'uuid'
    assert by_name['public_id'].is_nullable == 'NO'
    assert 'location_id, profile_scope, lower(btrim(name))' in index_definition
    assert tuple(modes) == ('allergen_mode', 'origin_mode', 'label_mode')


@LIVE_DATABASE
def test_v13_migration_backfills_legacy_component_links_and_manual_modes(pg16: Engine) -> None:
    _run_v12_migrations(pg16)
    database._execute_script(pg16, str(ROOT / 'database' / 'seed.sql'))
    with pg16.begin() as connection:
        connection.execute(
            text(
                '''
                WITH new_week AS (
                    INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start)
                    SELECT l.id, p.id, DATE '2026-09-07'
                    FROM cafeteria.locations l
                    JOIN cafeteria.offer_profiles p ON p.code='patient'
                    WHERE l.code='KIRCHLINDACH'
                    RETURNING id
                ), new_service AS (
                    INSERT INTO cafeteria.menu_services(menu_week_id, service_date, meal_period_id)
                    SELECT w.id, DATE '2026-09-07', m.id
                    FROM new_week w
                    JOIN cafeteria.meal_periods m ON m.code='LUNCH'
                    RETURNING id
                ), new_item AS (
                    INSERT INTO cafeteria.menu_items(
                        service_id, menu_type_id, external_id, title, sort_order
                    )
                    SELECT s.id, t.id, 'V13-LEGACY-1', 'Poulet mit Reis', 1
                    FROM new_service s
                    JOIN cafeteria.menu_types t ON t.code='MENU_1'
                    RETURNING id
                )
                INSERT INTO cafeteria.menu_item_components(menu_item_id, sort_order, component_text)
                SELECT id, 1, 'Poulet' FROM new_item
                UNION ALL
                SELECT id, 2, 'Reis' FROM new_item
                '''
            )
        )
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.menu_item_allergens(menu_item_id, allergen_id, presence)
                SELECT i.id, a.id, v.presence
                FROM cafeteria.menu_items i
                JOIN cafeteria.allergens a ON a.code='GLUTEN'
                CROSS JOIN (VALUES ('may_contain'), ('contains')) AS v(presence)
                WHERE i.external_id='V13-LEGACY-1'
                '''
            )
        )
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.menu_item_labels(menu_item_id, label_id)
                SELECT i.id, l.id
                FROM cafeteria.menu_items i
                JOIN cafeteria.dietary_labels l ON l.code='VEGAN'
                WHERE i.external_id='V13-LEGACY-1'
                '''
            )
        )
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.origin_declarations(
                    menu_item_id, ingredient, country_code, declaration_text
                )
                SELECT id, 'Poulet', 'CH', 'Poulet: CH'
                FROM cafeteria.menu_items WHERE external_id='V13-LEGACY-1'
                '''
            )
        )

    database._execute_migration(pg16, _v13_migration())

    with pg16.connect() as connection:
        links = connection.execute(
            text(
                '''
                SELECT mic.component_text, mc.name, mc.profile_scope,
                       mic.component_row_version, mc.row_version, mc.origin_country_code
                FROM cafeteria.menu_item_components mic
                JOIN cafeteria.menu_components mc ON mc.id=mic.component_id
                JOIN cafeteria.menu_items i ON i.id=mic.menu_item_id
                WHERE i.external_id='V13-LEGACY-1'
                ORDER BY mic.sort_order
                '''
            )
        ).all()
        modes = connection.execute(
            text(
                '''
                SELECT allergen_mode, origin_mode, label_mode
                FROM cafeteria.menu_items WHERE external_id='V13-LEGACY-1'
                '''
            )
        ).one()
        allergen_rows = connection.execute(
            text(
                '''
                SELECT mc.name, a.code, ca.presence
                FROM cafeteria.component_allergens ca
                JOIN cafeteria.menu_components mc ON mc.id=ca.component_id
                JOIN cafeteria.allergens a ON a.id=ca.allergen_id
                ORDER BY mc.name
                '''
            )
        ).all()
        label_rows = connection.execute(
            text(
                '''
                SELECT mc.name, l.code
                FROM cafeteria.component_labels cl
                JOIN cafeteria.menu_components mc ON mc.id=cl.component_id
                JOIN cafeteria.dietary_labels l ON l.id=cl.label_id
                ORDER BY mc.name
                '''
            )
        ).all()

    assert [(row.component_text, row.name) for row in links] == [
        ('Poulet', 'Poulet'),
        ('Reis', 'Reis'),
    ]
    assert all(row.profile_scope == 'patient' for row in links)
    assert all(row.component_row_version == row.row_version == 1 for row in links)
    assert links[0].origin_country_code == 'CH'
    assert links[1].origin_country_code is None
    assert tuple(modes) == ('manual', 'manual', 'manual')
    assert [(row.name, row.code, row.presence) for row in allergen_rows] == [
        ('Poulet', 'GLUTEN', 'contains'),
        ('Reis', 'GLUTEN', 'contains'),
    ]
    assert [(row.name, row.code) for row in label_rows] == [
        ('Poulet', 'VEGAN'),
        ('Reis', 'VEGAN'),
    ]


@LIVE_DATABASE
def test_v13_migration_failure_rolls_back_every_schema_change(
    pg16: Engine,
    tmp_path: Path,
) -> None:
    _run_v12_migrations(pg16)
    failing_path = tmp_path / '0010_v12_to_v13_failing.sql'
    script = MIGRATION.read_text(encoding='utf-8').rstrip()
    failing_path.write_text(
        script.removesuffix('COMMIT;') + 'SELECT 1 / 0;\nCOMMIT;\n',
        encoding='utf-8',
    )
    failing = database.Migration(
        version=13,
        path=failing_path,
        checksum_sha256=hashlib.sha256(failing_path.read_bytes()).hexdigest(),
    )

    with pytest.raises(psycopg.Error):
        database._execute_migration(pg16, failing)

    with pg16.connect() as connection:
        component_table = connection.execute(
            text("SELECT to_regclass('cafeteria.menu_components')")
        ).scalar_one()
        mode_columns = connection.execute(
            text(
                '''
                SELECT count(*)
                FROM information_schema.columns
                WHERE table_schema='cafeteria' AND table_name='menu_items'
                  AND column_name IN ('allergen_mode', 'origin_mode', 'label_mode')
                '''
            )
        ).scalar_one()
        latest_version = connection.execute(
            text('SELECT max(version) FROM cafeteria.schema_migrations')
        ).scalar_one()

    assert component_table is None
    assert mode_columns == 0
    assert latest_version == 12


@LIVE_DATABASE
def test_v13_permissions_cover_component_tables_and_identity_sequence(pg16: Engine) -> None:
    database.run_migrations(pg16, SCHEMA)
    database._execute_script(pg16, str(ROOT / 'database' / 'permissions.sql'))

    with pg16.connect() as connection:
        privileges = connection.execute(
            text(
                '''
                SELECT
                    has_table_privilege(
                        'cafeteria_app', 'cafeteria.menu_components',
                        'SELECT,INSERT,UPDATE'
                    ) AS app_components,
                    has_table_privilege(
                        'cafeteria_app', 'cafeteria.menu_components', 'DELETE'
                    ) AS app_components_delete,
                    has_table_privilege(
                        'cafeteria_app', 'cafeteria.component_allergens',
                        'SELECT,INSERT,UPDATE,DELETE'
                    ) AS app_allergens,
                    has_table_privilege(
                        'cafeteria_app', 'cafeteria.component_labels',
                        'SELECT,INSERT,UPDATE,DELETE'
                    ) AS app_labels,
                    has_sequence_privilege(
                        'cafeteria_app', 'cafeteria.menu_components_id_seq', 'USAGE'
                    ) AS app_sequence,
                    has_table_privilege(
                        'cafeteria_backup', 'cafeteria.menu_components', 'SELECT'
                    ) AS backup_components,
                    has_table_privilege(
                        'cafeteria_backup', 'cafeteria.component_allergens', 'SELECT'
                    ) AS backup_allergens,
                    has_table_privilege(
                        'cafeteria_backup', 'cafeteria.component_labels', 'SELECT'
                    ) AS backup_labels,
                    has_sequence_privilege(
                        'cafeteria_backup', 'cafeteria.menu_components_id_seq', 'SELECT'
                    ) AS backup_sequence
                '''
            )
        ).one()

    assert privileges.app_components
    assert not privileges.app_components_delete
    assert all(privileges[index] for index in range(2, len(privileges)))
