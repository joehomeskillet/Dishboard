from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from cafeteria import db as database


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'database' / 'schema.sql'
MIGRATION = ROOT / 'database' / 'migrations' / '0010_v12_to_v13.sql'
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
V12_RESTORE_DATABASE = 'menuplan_task1_v12_restore'
PG16_TEST_CONTAINER = os.getenv('TEST_DATABASE_CONTAINER')
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


@pytest.fixture
def v12_restore_probe(pg16: Engine, tmp_path: Path) -> Iterator[Path]:
    docker = shutil.which('docker')
    assert DATABASE_URL is not None
    url = make_url(DATABASE_URL)
    assert docker is not None, 'PG16 down-probe requires Docker.'
    assert PG16_TEST_CONTAINER is not None, 'PG16 down-probe requires TEST_DATABASE_CONTAINER.'
    assert url.database is not None
    assert url.username is not None
    assert url.password is not None
    docker_environment = f'PGPASSWORD={url.password}'

    _run_v12_migrations(pg16)
    database._execute_script(pg16, str(ROOT / 'database' / 'seed.sql'))
    backup_path = tmp_path / 'menuplan-task1-v12-pre-migration.dump'
    with backup_path.open('wb') as backup_file:
        dump = subprocess.run(
            [docker, 'exec', '-e', docker_environment, PG16_TEST_CONTAINER,
             'pg_dump', '--format=custom', '--username', url.username,
             '--dbname', url.database],
            check=False, stdout=backup_file, stderr=subprocess.PIPE, text=True,
        )
    assert dump.returncode == 0, dump.stderr
    assert backup_path.stat().st_size > 0

    with pg16.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS {V12_RESTORE_DATABASE} WITH (FORCE)'))
        connection.execute(
            text(
                f'CREATE DATABASE {V12_RESTORE_DATABASE} OWNER menuplan_test_owner'
            )
        )

    with backup_path.open('rb') as backup_file:
        restore = subprocess.run(
            [docker, 'exec', '-i', '-e', docker_environment, PG16_TEST_CONTAINER,
             'pg_restore', '--exit-on-error', '--no-owner', '--no-privileges',
             '--username', url.username, '--dbname', V12_RESTORE_DATABASE],
            check=False, stdin=backup_file, stderr=subprocess.PIPE, text=True,
        )
    if restore.returncode != 0:
        with pg16.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS {V12_RESTORE_DATABASE} WITH (FORCE)'))
        pytest.fail(restore.stderr)
    try:
        yield backup_path
    finally:
        with pg16.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS {V12_RESTORE_DATABASE} WITH (FORCE)'))


def _insert_legacy_component_with_origins(
    engine: Engine,
    country_codes: tuple[str, ...],
) -> None:
    with engine.begin() as connection:
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
                ), new_services AS (
                    INSERT INTO cafeteria.menu_services(menu_week_id, service_date, meal_period_id)
                    SELECT w.id, DATE '2026-09-07', m.id
                    FROM new_week w
                    JOIN cafeteria.meal_periods m ON m.code IN ('LUNCH', 'DINNER')
                    RETURNING id
                ), new_items AS (
                    INSERT INTO cafeteria.menu_items(
                        service_id, menu_type_id, external_id, title, sort_order
                    )
                    SELECT
                        s.id,
                        t.id,
                        'V13-LEGACY-ORIGIN-' || s.id,
                        'Poulet mit Reis',
                        1
                    FROM new_services s
                    JOIN cafeteria.menu_types t ON t.code='MENU_1'
                    RETURNING id
                )
                INSERT INTO cafeteria.menu_item_components(menu_item_id, sort_order, component_text)
                SELECT id, 1, 'Poulet' FROM new_items
                '''
            )
        )
        for offset, country_code in enumerate(country_codes):
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.origin_declarations(
                        menu_item_id, ingredient, country_code, declaration_text
                    )
                    SELECT id, 'Poulet', CAST(:country_code AS char(2)), :declaration_text
                    FROM cafeteria.menu_items
                    WHERE external_id = (
                        SELECT external_id
                        FROM cafeteria.menu_items
                        WHERE external_id LIKE 'V13-LEGACY-ORIGIN-%'
                        ORDER BY external_id
                        LIMIT 1 OFFSET :offset
                    )
                    '''
                ),
                {
                    'country_code': country_code,
                    'declaration_text': f'Poulet: {country_code}',
                    'offset': offset,
                },
            )


def _assert_statement_rejected(engine: Engine, statement: str, parameters: dict[str, object]) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text(statement), parameters)


def _assert_v13_schema_rolled_back(engine: Engine) -> None:
    with engine.connect() as connection:
        result = connection.execute(
            text(
                '''
                SELECT
                    to_regclass('cafeteria.menu_components'),
                    (SELECT count(*) FROM information_schema.columns
                     WHERE table_schema='cafeteria' AND table_name='menu_items'
                       AND column_name IN ('allergen_mode', 'origin_mode', 'label_mode')),
                    (SELECT max(version) FROM cafeteria.schema_migrations)
                '''
            )
        ).one()
    assert tuple(result) == (None, 0, 12)


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
                ), new_services AS (
                    INSERT INTO cafeteria.menu_services(menu_week_id, service_date, meal_period_id)
                    SELECT w.id, DATE '2026-09-07', m.id
                    FROM new_week w
                    JOIN cafeteria.meal_periods m ON m.code IN ('LUNCH', 'DINNER')
                    RETURNING id, meal_period_id
                ), new_items AS (
                    INSERT INTO cafeteria.menu_items(
                        service_id, menu_type_id, external_id, title, sort_order
                    )
                    SELECT s.id, t.id, 'V13-LEGACY-' || lower(m.code),
                           CASE m.code WHEN 'LUNCH' THEN 'Poulet mit Reis' ELSE 'Kartoffel' END, 1
                    FROM new_services s
                    JOIN cafeteria.meal_periods m ON m.id=s.meal_period_id
                    JOIN cafeteria.menu_types t ON t.code='MENU_1'
                    RETURNING id, external_id
                )
                INSERT INTO cafeteria.menu_item_components(menu_item_id, sort_order, component_text)
                SELECT id, 1,
                       CASE external_id WHEN 'V13-LEGACY-lunch' THEN 'Poulet' ELSE 'Kartoffel' END
                FROM new_items
                UNION ALL
                SELECT id, 2, 'Reis' FROM new_items WHERE external_id='V13-LEGACY-lunch'
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
                WHERE i.external_id IN ('V13-LEGACY-lunch', 'V13-LEGACY-dinner')
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
                WHERE i.external_id IN ('V13-LEGACY-lunch', 'V13-LEGACY-dinner')
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
                FROM cafeteria.menu_items WHERE external_id='V13-LEGACY-lunch'
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
                WHERE i.external_id='V13-LEGACY-lunch'
                ORDER BY mic.sort_order
                '''
            )
        ).all()
        legacy_rows = connection.execute(text(
                '''
                SELECT i.external_id, i.allergen_mode, i.origin_mode, i.label_mode,
                       (SELECT count(*) FROM cafeteria.menu_item_allergens mia
                        WHERE mia.menu_item_id=i.id),
                       (SELECT count(*) FROM cafeteria.menu_item_labels mil
                        WHERE mil.menu_item_id=i.id)
                FROM cafeteria.menu_items i
                WHERE i.external_id IN ('V13-LEGACY-lunch', 'V13-LEGACY-dinner')
                ORDER BY i.external_id
                '''
        )).all()
        allergen_rows = connection.execute(text(
                '''
                SELECT mc.name, a.code, ca.presence
                FROM cafeteria.component_allergens ca
                JOIN cafeteria.menu_components mc ON mc.id=ca.component_id
                JOIN cafeteria.allergens a ON a.id=ca.allergen_id
                ORDER BY mc.name
                '''
        )).all()
        label_rows = connection.execute(text(
                '''
                SELECT mc.name, l.code
                FROM cafeteria.component_labels cl
                JOIN cafeteria.menu_components mc ON mc.id=cl.component_id
                JOIN cafeteria.dietary_labels l ON l.id=cl.label_id
                ORDER BY mc.name
                '''
        )).all()

    assert [tuple(row) for row in links] == [
        ('Poulet', 'Poulet', 'patient', 1, 1, 'CH'),
        ('Reis', 'Reis', 'patient', 1, 1, None),
    ]
    assert [tuple(row) for row in legacy_rows] == [
        ('V13-LEGACY-dinner', 'manual', 'manual', 'manual', 2, 1),
        ('V13-LEGACY-lunch', 'manual', 'manual', 'manual', 2, 1),
    ]
    assert [(row.name, row.code, row.presence) for row in allergen_rows] == [
        ('Kartoffel', 'GLUTEN', 'contains'),
    ]
    assert [(row.name, row.code) for row in label_rows] == [
        ('Kartoffel', 'VEGAN'),
    ]


@LIVE_DATABASE
def test_v13_migration_rejects_conflicting_legacy_origins_and_rolls_back(pg16: Engine) -> None:
    _run_v12_migrations(pg16)
    database._execute_script(pg16, str(ROOT / 'database' / 'seed.sql'))
    _insert_legacy_component_with_origins(pg16, ('CH', 'DE'))

    with pytest.raises(psycopg.Error, match='conflicting legacy origin country codes'):
        database._execute_migration(pg16, _v13_migration())

    _assert_v13_schema_rolled_back(pg16)


@LIVE_DATABASE
def test_v13_real_postgres_contract_covers_catalog_constraints_and_component_links(
    pg16: Engine,
) -> None:
    database.run_migrations(pg16, SCHEMA)
    database.run_migrations(pg16, SCHEMA)
    database._execute_script(pg16, str(ROOT / 'database' / 'seed.sql'))

    with pg16.begin() as connection:
        location_id = connection.execute(
            text("SELECT id FROM cafeteria.locations WHERE code='KIRCHLINDACH'")
        ).scalar_one()
        allergen_id = connection.execute(
            text("SELECT id FROM cafeteria.allergens WHERE code='GLUTEN'")
        ).scalar_one()
        menu_item_id = connection.execute(
            text(
                '''
                WITH new_week AS (
                    INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start)
                    SELECT l.id, p.id, DATE '2026-09-14'
                    FROM cafeteria.locations l
                    JOIN cafeteria.offer_profiles p ON p.code='patient'
                    WHERE l.id=:location_id
                    RETURNING id
                ), new_service AS (
                    INSERT INTO cafeteria.menu_services(menu_week_id, service_date, meal_period_id)
                    SELECT w.id, DATE '2026-09-14', m.id
                    FROM new_week w
                    JOIN cafeteria.meal_periods m ON m.code='LUNCH'
                    RETURNING id
                )
                INSERT INTO cafeteria.menu_items(
                    service_id, menu_type_id, external_id, title, sort_order
                )
                SELECT s.id, t.id, 'V13-CONTRACT-ITEM', 'Vertragsmenue', 1
                FROM new_service s
                JOIN cafeteria.menu_types t ON t.code='MENU_1'
                RETURNING id
                '''
            ),
            {'location_id': location_id},
        ).scalar_one()
        component_id = connection.execute(text('''
            INSERT INTO cafeteria.menu_components(location_id, profile_scope, category, name)
            VALUES (:location_id, 'patient', 'other', 'Kichererbse') RETURNING id
        '''), {'location_id': location_id}).scalar_one()
        component_public_id = connection.execute(
            text('SELECT public_id FROM cafeteria.menu_components WHERE id=:component_id'),
            {'component_id': component_id},
        ).scalar_one()

    with pg16.connect() as connection:
        version = connection.execute(text(
            'SELECT max(version) FROM cafeteria.schema_migrations'
        )).scalar_one()
        columns = connection.execute(
            text(
                '''
                SELECT table_name, column_name, data_type, is_nullable, identity_generation
                FROM information_schema.columns
                WHERE table_schema='cafeteria'
                  AND table_name IN (
                    'menu_components', 'component_allergens', 'component_labels',
                    'menu_items', 'menu_item_components'
                  )
                '''
            )
        ).all()
        constraints = connection.execute(
            text(
                '''
                SELECT conrelid::regclass::text AS table_name, conname, contype
                FROM pg_constraint
                WHERE connamespace='cafeteria'::regnamespace
                  AND conrelid IN (
                    'cafeteria.menu_components'::regclass,
                    'cafeteria.component_allergens'::regclass,
                    'cafeteria.component_labels'::regclass,
                    'cafeteria.menu_items'::regclass,
                    'cafeteria.menu_item_components'::regclass
                  )
                '''
            )
        ).all()

    plan = database.migration_plan(SCHEMA)
    catalog_columns = 'id public_id location_id profile_scope category name origin_country_code active row_version created_at updated_at'.split()
    expected_columns = {'menu_components': catalog_columns, 'component_allergens': 'component_id allergen_id presence'.split(), 'component_labels': 'component_id label_id'.split(), 'menu_items': 'allergen_mode origin_mode label_mode'.split(), 'menu_item_components': 'component_id component_row_version'.split()}
    column_contract = {(row[0], row[1]): row[2:] for row in columns}
    assert database.SCHEMA_VERSION == version == 13
    assert database.APPLICATION_VERSION == 'dishboard-schema-v13'
    assert (plan[-1].version, plan[-1].path.name) == (13, '0010_v12_to_v13.sql')
    assert MIGRATION.read_text(encoding='utf-8').startswith('BEGIN;')
    assert MIGRATION.read_text(encoding='utf-8').rstrip().endswith('COMMIT;')
    validator = (ROOT / 'database' / 'validate_schema.py').read_text(encoding='utf-8')
    assert "MIGRATION_0010: '82f22cc0dd439a8b1ca1e0dc324616871411d67700723f1ebebedc06185a1a72'" in validator
    assert 'v13 conflicting legacy origin country codes' in validator
    assert all((table, column) in column_contract for table, names in expected_columns.items() for column in names)
    assert column_contract[('menu_components', 'id')] == ('bigint', 'NO', 'ALWAYS')
    assert column_contract[('menu_components', 'public_id')][:2] == ('uuid', 'NO')
    assert all(column_contract[(table, column)][1] == 'NO' for table, names in expected_columns.items() for column in names if (table, column) not in {('menu_components', 'origin_country_code'), ('menu_item_components', 'component_id'), ('menu_item_components', 'component_row_version')})
    assert all(column_contract[('menu_item_components', column)][1] == 'YES' for column in expected_columns['menu_item_components'])
    expected_constraints = {
        'menu_components': 'pkey:p public_id_key:u location_id_fkey:f profile_scope_check:c category_check:c name_check:c origin_country_code_check:c row_version_check:c',
        'component_allergens': 'pkey:p component_id_fkey:f allergen_id_fkey:f presence_check:c',
        'component_labels': 'pkey:p component_id_fkey:f label_id_fkey:f',
        'menu_items': 'allergen_mode_check:c origin_mode_check:c label_mode_check:c',
        'menu_item_components': 'component_id_fkey:f component_row_version_check:c component_link_check:c',
    }
    contract_constraints = {(row[0].removeprefix('cafeteria.'), row[1], row[2]) for row in constraints}
    assert {(table, f'{table}_{name}', kind) for table, definitions in expected_constraints.items() for definition in definitions.split() for name, kind in [definition.rsplit(':', 1)]} <= contract_constraints
    invalid_statements = (
        ("INSERT INTO cafeteria.menu_components(location_id, profile_scope, category, name) VALUES (:location_id, 'patient', 'invalid', 'Ungültige Kategorie')", {'location_id': location_id}),
        ("INSERT INTO cafeteria.menu_components(location_id, profile_scope, category, name) VALUES (:location_id, 'patient', 'other', '  kichererbse  ')", {'location_id': location_id}),
        ("INSERT INTO cafeteria.menu_components(public_id, location_id, profile_scope, category, name) VALUES (:public_id, :location_id, 'patient', 'other', 'Duplikat UUID')", {'location_id': location_id, 'public_id': component_public_id}),
        ("INSERT INTO cafeteria.component_allergens(component_id, allergen_id, presence) VALUES (999999, :allergen_id, 'contains')", {'allergen_id': allergen_id}),
        ("INSERT INTO cafeteria.component_labels(component_id, label_id) VALUES (:component_id, 32767)", {'component_id': component_id}),
        ("INSERT INTO cafeteria.menu_components(location_id, profile_scope, category, name) VALUES (:location_id, 'invalid', 'other', 'Ungueltiger Scope')", {'location_id': location_id}),
        ("INSERT INTO cafeteria.menu_components(location_id, profile_scope, category, name) VALUES (:location_id, 'patient', 'other', '')", {'location_id': location_id}),
        ("INSERT INTO cafeteria.menu_components(location_id, profile_scope, category, name, origin_country_code) VALUES (:location_id, 'patient', 'other', 'Ungueltiges Land', 'C1')", {'location_id': location_id}),
        ("UPDATE cafeteria.menu_items SET allergen_mode='invalid' WHERE external_id='V13-CONTRACT-ITEM'", {}),
        ("UPDATE cafeteria.menu_items SET origin_mode='invalid' WHERE external_id='V13-CONTRACT-ITEM'", {}),
        ("UPDATE cafeteria.menu_items SET label_mode='invalid' WHERE external_id='V13-CONTRACT-ITEM'", {}),
        ("INSERT INTO cafeteria.component_allergens(component_id, allergen_id, presence) VALUES (:component_id, :allergen_id, 'invalid')", {'component_id': component_id, 'allergen_id': allergen_id}),
        ("INSERT INTO cafeteria.menu_item_components(menu_item_id, sort_order, component_text, component_id) VALUES (:menu_item_id, 1, 'Kichererbse', :component_id)", {'menu_item_id': menu_item_id, 'component_id': component_id}),
        ("INSERT INTO cafeteria.menu_item_components(menu_item_id, sort_order, component_text, component_row_version) VALUES (:menu_item_id, 2, 'Kichererbse', 1)", {'menu_item_id': menu_item_id}),
    )
    for statement, parameters in invalid_statements:
        _assert_statement_rejected(pg16, statement, parameters)


@LIVE_DATABASE
def test_v12_backup_restore_down_probe_preserves_v12_without_claiming_reverse_migration(
    v12_restore_probe: Path,
) -> None:
    docker = shutil.which('docker')
    assert DATABASE_URL is not None
    url = make_url(DATABASE_URL)
    assert docker is not None
    assert PG16_TEST_CONTAINER is not None
    assert url.database is not None
    assert url.username is not None
    assert url.password is not None
    query = subprocess.run(
        [docker, 'exec', '-e', f'PGPASSWORD={url.password}', PG16_TEST_CONTAINER,
         'psql', '--tuples-only', '--no-align', '--dbname', V12_RESTORE_DATABASE,
         '--username', url.username,
         '--command', 'SELECT current_database(), (SELECT max(version) FROM cafeteria.schema_migrations), (SELECT count(*) FROM cafeteria.locations)'],
        check=False, capture_output=True, text=True,
    )

    assert query.returncode == 0, query.stderr
    assert v12_restore_probe.name == 'menuplan-task1-v12-pre-migration.dump'
    assert query.stdout.strip().split('|') == [V12_RESTORE_DATABASE, '12', '1']


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

    _assert_v13_schema_rolled_back(pg16)


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
                    ) AS backup_sequence,
                    ARRAY(
                        SELECT has_table_privilege(
                            'cafeteria_backup', 'cafeteria.' || tables.table_name, privileges.privilege
                        )
                        FROM unnest(
                            ARRAY['menu_components', 'component_allergens', 'component_labels']
                        ) AS tables(table_name)
                        CROSS JOIN unnest(ARRAY['INSERT', 'UPDATE', 'DELETE']) AS privileges(privilege)
                    ) AS backup_write_grants
                '''
            )
        ).one()

    assert privileges.app_components
    assert not privileges.app_components_delete
    assert all(privileges[index] for index in range(2, 9))
    assert privileges.backup_write_grants == [False] * 9
