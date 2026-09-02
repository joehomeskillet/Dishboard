from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool
from werkzeug.security import generate_password_hash

from cafeteria import db as database

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
LIVE_DATABASE = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


def _snapshot(profile_code: str) -> dict[str, Any]:
    filename = 'patienten_kw36.json' if profile_code == 'patient' else 'cafeteria_kw36.json'
    return json.loads((ROOT / 'demo' / 'snapshots' / filename).read_text(encoding='utf-8'))


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


@pytest.fixture
def database_engine() -> Iterator[Engine]:
    database_url = DATABASE_URL
    if not database_url:
        pytest.skip('TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.')
    assert database_url is not None
    engine = create_engine(database_url, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    database.init_database(
        database_url,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    try:
        yield engine
    finally:
        _drop_schema(engine)
        engine.dispose()


def _insert_week(
    engine: Engine,
    profile_code: str,
    state: str = 'draft',
    week_start: str = '2026-08-31',
) -> int:
    with engine.begin() as connection:
        return int(
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start, workflow_state)
                    SELECT l.id, p.id, CAST(:week_start AS date), :state
                    FROM cafeteria.locations l
                    JOIN cafeteria.offer_profiles p ON p.code=:profile_code
                    WHERE l.code='KIRCHLINDACH'
                    RETURNING id
                    '''
                ),
                {'profile_code': profile_code, 'state': state, 'week_start': week_start},
            ).scalar_one()
        )


def _insert_service(engine: Engine, week_id: int, date: str, meal_code: str) -> int:
    with engine.begin() as connection:
        return int(
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.menu_services(menu_week_id, service_date, meal_period_id)
                    SELECT :week_id, CAST(:service_date AS date), id
                    FROM cafeteria.meal_periods WHERE code=:meal_code
                    RETURNING id
                    '''
                ),
                {'week_id': week_id, 'service_date': date, 'meal_code': meal_code},
            ).scalar_one()
        )


def _insert_item(engine: Engine, service_id: int) -> int:
    with engine.begin() as connection:
        return int(
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.menu_items(
                        service_id, menu_type_id, external_id, title, sort_order
                    )
                    SELECT :service_id, id, :external_id, 'Testgericht', 1
                    FROM cafeteria.menu_types WHERE code='MENU_1'
                    RETURNING id
                    '''
                ),
                {'service_id': service_id, 'external_id': f'TEST-{service_id}'},
            ).scalar_one()
        )


def _insert_revision(
    engine: Engine,
    week_id: int,
    profile_code: str,
    *,
    snapshot: dict[str, Any] | None = None,
) -> int:
    payload = snapshot or _snapshot(profile_code)
    with engine.begin() as connection:
        return int(
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.publication_revisions(
                        menu_week_id, revision_number, revision_code, snapshot_json, published_by
                    )
                    SELECT :week_id, 1, :revision_code, CAST(:snapshot AS jsonb), u.id
                    FROM cafeteria.users u
                    WHERE u.public_id='00000000-0000-0000-0000-000000000001'
                    RETURNING id
                    '''
                ),
                {
                    'week_id': week_id,
                    'revision_code': payload['revision_id'],
                    'snapshot': json.dumps(payload, ensure_ascii=False),
                },
            ).scalar_one()
        )


def test_migration_plan_is_ordered_and_preserves_0001_bytes() -> None:
    plan = database.migration_plan(ROOT / 'database' / 'schema.sql')
    assert [(migration.version, migration.path.name) for migration in plan] == [
        (4, '0001_initial_postgresql.sql'),
        (5, '0002_profile_publication_and_local_auth.sql'),
        (6, '0003_patient_key_and_withdrawal_contracts.sql'),
        (7, '0004_patient_key_lock_and_capability_contracts.sql'),
        (8, '0005_least_privilege_identity_contracts.sql'),
        (9, '0006_auth_issuer_and_local_login.sql'),
        (10, '0007_auth_security_hardening.sql'),
        (11, '0008_auth_final_hardening.sql'),
            (12, '0009_bootstrap_first_local_admin.sql'),
        (12, '0009_bootstrap_first_local_admin.sql'),
    ]
    assert database.SCHEMA_VERSION == 12
    migrations = ROOT / 'database' / 'migrations'
    assert hashlib.sha256((migrations / '0001_initial_postgresql.sql').read_bytes()).hexdigest() == (
        'd1001f657858b4fec9a466517bf4117add8b28160dda7aebf7c43c21e6e6fff0'
    )
    assert hashlib.sha256((migrations / '0002_profile_publication_and_local_auth.sql').read_bytes()).hexdigest() == (
        '7f8696eb886a99d841ac82be1e4b3abf1b51080c18aac07ea5290325f3e5e863'
    )
    assert hashlib.sha256((migrations / '0003_patient_key_and_withdrawal_contracts.sql').read_bytes()).hexdigest() == (
        'eda9c5e851525367af62a3f056b3592a521d871f6ac818d4d50c18d8f720d1de'
    )
    assert hashlib.sha256((migrations / '0004_patient_key_lock_and_capability_contracts.sql').read_bytes()).hexdigest() == (
        '7309069f1b52d41a756a315af8b6ccf0771afe113875a6c5f82d42775f74b066'
    )


@LIVE_DATABASE
def test_empty_database_runs_0001_then_0002(database_engine: Engine) -> None:
    with database_engine.connect() as connection:
        rows = connection.execute(
            text('SELECT version, name FROM cafeteria.schema_migrations ORDER BY version')
        ).all()
        local_credentials = connection.execute(
            text("SELECT to_regclass('cafeteria.local_credentials')")
        ).scalar_one()
    assert [row.version for row in rows] == [4, 5, 6, 7, 8, 9, 10, 11]
    assert rows[0].name == '0001_initial_postgresql.sql'
    assert rows[1].name == '0002_profile_publication_and_local_auth.sql'
    assert rows[2].name == '0003_patient_key_and_withdrawal_contracts.sql'
    assert rows[3].name == '0004_patient_key_lock_and_capability_contracts.sql'
    assert rows[4].name == '0005_least_privilege_identity_contracts.sql'
    assert rows[5].name == '0006_auth_issuer_and_local_login.sql'
    assert rows[6].name == '0007_auth_security_hardening.sql'
    assert rows[7].name == '0008_auth_final_hardening.sql'
    assert local_credentials == 'cafeteria.local_credentials'


@LIVE_DATABASE
def test_v4_fixture_migrates_without_replaying_0001() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    baseline_path = ROOT / 'database' / 'migrations' / '0001_initial_postgresql.sql'
    raw = engine.raw_connection()
    try:
        driver = raw.driver_connection
        assert driver is not None
        driver.execute(baseline_path.read_text(encoding='utf-8'), prepare=False)
        driver.execute(
            '''
            INSERT INTO cafeteria.schema_migrations(version, name, checksum_sha256, application_version)
            VALUES (4, 'sql_baseline_two_profiles', %s, 'fachmodell-2-profile')
            ''',
            (hashlib.sha256(baseline_path.read_bytes()).hexdigest(),),
        )
        driver.commit()
    finally:
        raw.close()
    database.provision_database_roles(
        engine,
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    database.run_migrations(engine, ROOT / 'database' / 'schema.sql')
    with engine.connect() as connection:
        versions = connection.execute(
            text('SELECT version FROM cafeteria.schema_migrations ORDER BY version')
        ).scalars().all()
    assert versions == [4, 5, 6, 7, 8, 9, 10, 11]
    _drop_schema(engine)
    engine.dispose()


@LIVE_DATABASE
def test_recorded_migration_checksum_drift_is_rejected(database_engine: Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(
            text("UPDATE cafeteria.schema_migrations SET checksum_sha256=repeat('0', 64) WHERE version=4")
        )
    with pytest.raises(RuntimeError, match='Checksum-Abweichung.*0001'):
        database.run_migrations(database_engine, ROOT / 'database' / 'schema.sql')


@LIVE_DATABASE
def test_patient_prices_are_rejected(database_engine: Engine) -> None:
    week_id = _insert_week(database_engine, 'patient')
    service_id = _insert_service(database_engine, week_id, '2026-08-31', 'LUNCH')
    item_id = _insert_item(database_engine, service_id)
    with pytest.raises(DBAPIError, match='Kosten.*Cafeteria'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.menu_item_prices(menu_item_id, internal_rappen, external_rappen)
                    VALUES (:item_id, 1100, 1660)
                    '''
                ),
                {'item_id': item_id},
            )


@pytest.mark.parametrize(
    ('date', 'meal_code', 'message'),
    [
        ('2026-08-31', 'DINNER', 'ausschliesslich LUNCH'),
        ('2026-09-05', 'LUNCH', 'Wochenende'),
    ],
)
@LIVE_DATABASE
def test_invalid_cafeteria_services_are_rejected(
    database_engine: Engine,
    date: str,
    meal_code: str,
    message: str,
) -> None:
    week_id = _insert_week(database_engine, 'staff_guest')
    with pytest.raises(DBAPIError, match=message):
        _insert_service(database_engine, week_id, date, meal_code)


@LIVE_DATABASE
def test_draft_week_cannot_receive_publication(database_engine: Engine) -> None:
    week_id = _insert_week(database_engine, 'patient', 'draft')
    with pytest.raises(DBAPIError, match='publiziert'):
        _insert_revision(database_engine, week_id, 'patient')


@LIVE_DATABASE
def test_publication_revisions_reject_snapshot_mutation_and_delete(database_engine: Engine) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published')
    revision_id = _insert_revision(database_engine, week_id, 'patient')
    with pytest.raises(DBAPIError, match='unveränderlich'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    UPDATE cafeteria.publication_revisions
                    SET snapshot_json = snapshot_json || jsonb_build_object('x', 1)
                    WHERE id=:id
                    '''
                ),
                {'id': revision_id},
            )
    with pytest.raises(DBAPIError, match='unveränderlich'):
        with database_engine.begin() as connection:
            connection.execute(
                text('DELETE FROM cafeteria.publication_revisions WHERE id=:id'),
                {'id': revision_id},
            )
    with pytest.raises(DBAPIError, match='foreign key|unveränderlich'):
        with database_engine.begin() as connection:
            connection.execute(text('DELETE FROM cafeteria.menu_weeks WHERE id=:id'), {'id': week_id})


@LIVE_DATABASE
def test_active_revisions_are_independent_per_profile(database_engine: Engine) -> None:
    patient_week = _insert_week(database_engine, 'patient', 'published')
    staff_week = _insert_week(database_engine, 'staff_guest', 'published')
    _insert_revision(database_engine, patient_week, 'patient')
    _insert_revision(database_engine, staff_week, 'staff_guest')
    with database_engine.connect() as connection:
        counts = {
            str(profile_code): int(total)
            for profile_code, total in connection.execute(
                text('SELECT profile_code, count(*) FROM cafeteria.active_publications GROUP BY profile_code')
            )
        }
    assert counts == {'patient': 1, 'staff_guest': 1}


@pytest.mark.parametrize(
    ('mutation', 'message'),
    [
        ('date', 'Kalendertage'),
        ('weekday', 'Wochentag'),
        ('meal', 'Mittag und Abend'),
        ('menu_type', 'Menüarten'),
        ('hidden_cost', 'Kosteninformationen'),
    ],
)
@LIVE_DATABASE
def test_patient_snapshot_requires_exact_grid(
    database_engine: Engine,
    mutation: str,
    message: str,
) -> None:
    payload = copy.deepcopy(_snapshot('patient'))
    if mutation == 'date':
        payload['days'][0]['date'] = '2026-09-01'
    elif mutation == 'weekday':
        payload['days'][0]['weekday'] = 'Dienstag'
    elif mutation == 'meal':
        payload['days'][0]['services'][1]['meal_code'] = 'LUNCH'
    elif mutation == 'menu_type':
        payload['days'][0]['services'][0]['options'][1]['type_code'] = 'MENU_1'
    else:
        payload['days'][0]['services'][0]['options'][0]['note'] = 'Intern CHF 0.00'
    week_id = _insert_week(database_engine, 'patient', 'published')
    with pytest.raises(DBAPIError, match=message):
        _insert_revision(database_engine, week_id, 'patient', snapshot=payload)


@LIVE_DATABASE
def test_cafeteria_snapshot_requires_exact_price_shape(database_engine: Engine) -> None:
    payload = copy.deepcopy(_snapshot('staff_guest'))
    payload['days'][0]['services'][0]['options'][0]['prices']['discount_rappen'] = 100
    week_id = _insert_week(database_engine, 'staff_guest', 'published')
    with pytest.raises(DBAPIError, match='Kostenstruktur'):
        _insert_revision(database_engine, week_id, 'staff_guest', snapshot=payload)


@LIVE_DATABASE
def test_local_credentials_only_accept_local_users_and_werkzeug_hashes(database_engine: Engine) -> None:
    with database_engine.begin() as connection:
        user_id = connection.execute(
            text(
                '''
                INSERT INTO cafeteria.users(auth_provider, display_name)
                VALUES ('local', 'Lokale Küche') RETURNING id
                '''
            )
        ).scalar_one()
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.local_credentials(user_id, username, password_hash)
                VALUES (:user_id, 'lokale.kueche', :password_hash)
                '''
            ),
            {'user_id': user_id, 'password_hash': generate_password_hash('correct horse battery staple')},
        )
    with pytest.raises(DBAPIError, match='(?i)werkzeug'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    UPDATE cafeteria.local_credentials SET password_hash='cleartext' WHERE user_id=:user_id
                    '''
                ),
                {'user_id': user_id},
            )


def _profile_id(engine: Engine, profile_code: str) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(
                text('SELECT id FROM cafeteria.offer_profiles WHERE code=:code'),
                {'code': profile_code},
            ).scalar_one()
        )


def _dated_snapshot(profile_code: str, week_start: str) -> dict[str, Any]:
    payload = copy.deepcopy(_snapshot(profile_code))
    start = date.fromisoformat(week_start)
    payload['week_start'] = start.isoformat()
    payload['week_end'] = (start + timedelta(days=6)).isoformat()
    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    for index, day in enumerate(payload['days']):
        day['date'] = (start + timedelta(days=index)).isoformat()
        day['weekday'] = weekdays[index]
    return payload


def _closed_patient_snapshot(week_start: str = '2026-08-31') -> dict[str, Any]:
    payload = _dated_snapshot('patient', week_start)
    dinner = payload['days'][0]['services'][1]
    dinner['service_state'] = 'closed'
    dinner['options'] = []
    return payload


@LIVE_DATABASE
def test_week_profile_service_and_item_reparent_are_rejected(database_engine: Engine) -> None:
    patient_week = _insert_week(database_engine, 'patient')
    staff_week = _insert_week(database_engine, 'staff_guest')
    patient_service = _insert_service(database_engine, patient_week, '2026-08-31', 'LUNCH')
    staff_service = _insert_service(database_engine, staff_week, '2026-08-31', 'LUNCH')
    patient_item = _insert_item(database_engine, patient_service)
    staff_item = _insert_item(database_engine, staff_service)
    staff_profile_id = _profile_id(database_engine, 'staff_guest')
    with pytest.raises(DBAPIError, match='Angebotsprofil'):
        with database_engine.begin() as connection:
            connection.execute(
                text('UPDATE cafeteria.menu_weeks SET profile_id=:profile_id WHERE id=:id'),
                {'profile_id': staff_profile_id, 'id': patient_week},
            )
    with pytest.raises(DBAPIError, match='andere Woche'):
        with database_engine.begin() as connection:
            connection.execute(
                text('UPDATE cafeteria.menu_services SET menu_week_id=:week_id WHERE id=:id'),
                {'week_id': staff_week, 'id': patient_service},
            )
    with pytest.raises(DBAPIError, match='anderen Service'):
        with database_engine.begin() as connection:
            connection.execute(
                text('UPDATE cafeteria.menu_items SET service_id=:service_id WHERE id=:id'),
                {'service_id': staff_service, 'id': patient_item},
            )
    with pytest.raises(DBAPIError, match='anderen Service'):
        with database_engine.begin() as connection:
            connection.execute(
                text('UPDATE cafeteria.menu_items SET service_id=:service_id WHERE id=:id'),
                {'service_id': patient_service, 'id': staff_item},
            )


@LIVE_DATABASE
def test_active_publications_bind_frozen_identity_and_published_state(
    database_engine: Engine,
) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published')
    _insert_revision(database_engine, week_id, 'patient')
    with database_engine.connect() as connection:
        view_sql = connection.execute(
            text(
                '''
                SELECT pg_get_viewdef('cafeteria.active_publications'::regclass, true)
                '''
            )
        ).scalar_one()
        row = connection.execute(
            text(
                '''
                SELECT profile_code, week_start, count(*) AS n
                FROM cafeteria.active_publications
                GROUP BY profile_code, week_start
                '''
            )
        ).mappings().one()
    assert 'profile_id' in view_sql
    assert 'week_start' in view_sql
    assert 'workflow_state' in view_sql
    assert 'published' in view_sql
    assert row['profile_code'] == 'patient'
    assert str(row['week_start']) == '2026-08-31'
    assert int(row['n']) == 1
    with pytest.raises(DBAPIError, match='Publikationsrevision kann nicht'):
        with database_engine.begin() as connection:
            connection.execute(
                text("UPDATE cafeteria.menu_weeks SET workflow_state='draft' WHERE id=:id"),
                {'id': week_id},
            )
    with database_engine.connect() as connection:
        visible = connection.execute(
            text('SELECT count(*) FROM cafeteria.active_publications')
        ).scalar_one()
    assert int(visible) == 1


@pytest.mark.parametrize(
    'key',
    (
        'cost',
        'amount',
        'kosten',
        'betrag',
        'unitPrice',
        'internalRappen',
        'totalAmount',
        'mealCost',
        'unit-price',
        'unit\u200bPrice',
        'total\u2060Amount',
        'unitPri\u0600ce',
        'mealCo\U000e0061st',
        'UNITPrice',
        'PRICEValue',
        'mysteryTariff',
    ),
)
@LIVE_DATABASE
def test_patient_snapshot_rejects_price_key_aliases(database_engine: Engine, key: str) -> None:
    payload = copy.deepcopy(_snapshot('patient'))
    payload['days'][0]['services'][0]['options'][0][key] = 1100
    week_id = _insert_week(database_engine, 'patient', 'published')
    with pytest.raises(DBAPIError, match='Kosteninformationen'):
        _insert_revision(database_engine, week_id, 'patient', snapshot=payload)


@pytest.mark.parametrize(
    'key',
    (
        'unitPrice', 'internalRappen', 'totalAmount', 'mealCost', 'unit-price',
        'unit\u200bPrice', 'unitPri\u0600ce', 'mealCo\U000e0061st',
        'UNITPrice', 'PRICEValue', 'mysteryTariff',
    ),
)
def test_python_patient_snapshot_rejects_normalized_price_key_aliases(key: str) -> None:
    payload = copy.deepcopy(_snapshot('patient'))
    payload['days'][0]['services'][0]['options'][0][key] = 1100
    with pytest.raises(ValueError, match='Kostenschlüssel'):
        database.validate_snapshot_payload('patient', payload)


@pytest.mark.parametrize(
    'clock_text',
    ('Ausgabe 11.30 Uhr', 'Ausgabe 11.00 Uhr', 'Mitternacht 00:00 Uhr', 'Mitternacht 00.00 Uhr'),
)
@LIVE_DATABASE
def test_patient_snapshot_allows_serving_time_but_rejects_money_decimals(
    database_engine: Engine,
    clock_text: str,
) -> None:
    allowed = copy.deepcopy(_snapshot('patient'))
    allowed['days'][0]['services'][0]['options'][0]['note'] = clock_text
    week_id = _insert_week(database_engine, 'patient', 'published')
    revision_id = _insert_revision(database_engine, week_id, 'patient', snapshot=allowed)
    assert revision_id > 0
    rejected = _dated_snapshot('patient', '2026-09-07')
    rejected['days'][1]['services'][0]['options'][0]['note'] = 'Menü 11.00'
    week_id_two = _insert_week(database_engine, 'patient', 'published', '2026-09-07')
    with pytest.raises(DBAPIError, match='Kosteninformationen'):
        _insert_revision(database_engine, week_id_two, 'patient', snapshot=rejected)


def test_python_patient_snapshot_allows_clocks_but_rejects_prices() -> None:
    for note in ('Ausgabe 11.00 Uhr', 'Mitternacht 00:00 Uhr', 'Mitternacht 00.00 Uhr'):
        allowed = copy.deepcopy(_snapshot('patient'))
        allowed['days'][0]['services'][0]['options'][0]['note'] = note
        database.validate_snapshot_payload('patient', allowed)
    for note in ('Menü 11.00', 'Menü CHF 11.00', 'Menü Fr. 11,00'):
        rejected = copy.deepcopy(_snapshot('patient'))
        rejected['days'][0]['services'][0]['options'][0]['note'] = note
        with pytest.raises(ValueError, match='Kostenwerte'):
            database.validate_snapshot_payload('patient', rejected)


@LIVE_DATABASE
def test_patient_snapshot_models_closed_and_open_service_state(database_engine: Engine) -> None:
    closed = _closed_patient_snapshot()
    week_id = _insert_week(database_engine, 'patient', 'published')
    assert _insert_revision(database_engine, week_id, 'patient', snapshot=closed) > 0
    open_without_dishes = _dated_snapshot('patient', '2026-09-07')
    open_without_dishes['days'][0]['services'][0]['service_state'] = 'open'
    open_without_dishes['days'][0]['services'][0]['options'] = []
    week_two = _insert_week(database_engine, 'patient', 'published', '2026-09-07')
    with pytest.raises(DBAPIError, match='offene Mahlzeit'):
        _insert_revision(database_engine, week_two, 'patient', snapshot=open_without_dishes)
    closed_with_dishes = _closed_patient_snapshot('2026-09-14')
    closed_with_dishes['days'][0]['services'][1]['options'] = copy.deepcopy(
        _snapshot('patient')['days'][0]['services'][1]['options']
    )
    week_three = _insert_week(database_engine, 'patient', 'published', '2026-09-14')
    with pytest.raises(DBAPIError, match='geschlossene Mahlzeit'):
        _insert_revision(database_engine, week_three, 'patient', snapshot=closed_with_dishes)


@LIVE_DATABASE
def test_withdrawal_history_allows_replacement_but_keeps_snapshot_bytes(
    database_engine: Engine,
) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published')
    first_id = _insert_revision(database_engine, week_id, 'patient')
    with database_engine.begin() as connection:
        original_hash = connection.execute(
            text('SELECT content_hash_sha256 FROM cafeteria.publication_revisions WHERE id=:id'),
            {'id': first_id},
        ).scalar_one()
        published_by = int(
            connection.execute(
                text('SELECT published_by FROM cafeteria.publication_revisions WHERE id=:id'),
                {'id': first_id},
            ).scalar_one()
        )
        withdrawal_actor = int(
            connection.execute(
                text("SELECT id FROM cafeteria.users WHERE public_id='00000000-0000-0000-0000-000000000002'")
            ).scalar_one()
        )
    assert withdrawal_actor != published_by
    with pytest.raises(DBAPIError, match='nicht aktiv oder nicht zur Publikation berechtigt'):
        database.issue_publication_capability(database_engine, published_by, first_id)
    with pytest.raises(DBAPIError, match='kontrollierten Rückzug'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    UPDATE cafeteria.publication_revisions
                    SET withdrawn_at=clock_timestamp(), withdrawal_reason='Freitext', withdrawn_by=:actor
                    WHERE id=:id
                    '''
                ),
                {'actor': withdrawal_actor, 'id': first_id},
            )
    capability = database.issue_publication_capability(database_engine, withdrawal_actor, first_id)
    with database_engine.begin() as connection:
        before = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
    returned_at = database.withdraw_publication_revision(
        database_engine, first_id, capability, 'Korrektur der Woche'
    )
    with database_engine.begin() as connection:
        after = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
    replacement = copy.deepcopy(_snapshot('patient'))
    replacement['revision_id'] = 'PAT-2026-KW36-R2'
    with database_engine.begin() as connection:
        second_id = int(
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.publication_revisions(
                        menu_week_id, revision_number, revision_code, snapshot_json, published_by
                    )
                    SELECT :week_id, 2, :revision_code, CAST(:snapshot AS jsonb), u.id
                    FROM cafeteria.users u
                    WHERE u.public_id='00000000-0000-0000-0000-000000000001'
                    RETURNING id
                    '''
                ),
                {
                    'week_id': week_id,
                    'revision_code': replacement['revision_id'],
                    'snapshot': json.dumps(replacement, ensure_ascii=False),
                },
            ).scalar_one()
        )
    with database_engine.connect() as connection:
        events = connection.execute(
            text(
                '''
                SELECT revision_id, event_type, reason, actor_user_id, occurred_at
                FROM cafeteria.publication_lifecycle_events
                ORDER BY id
                '''
            )
        ).all()
        active = connection.execute(
            text('SELECT revision_code FROM cafeteria.active_publications')
        ).scalars().all()
        frozen_hash = connection.execute(
            text('SELECT content_hash_sha256 FROM cafeteria.publication_revisions WHERE id=:id'),
            {'id': first_id},
        ).scalar_one()
        withdrawal_row = connection.execute(
            text(
                '''
                SELECT withdrawn_at, withdrawn_by, withdrawal_reason
                FROM cafeteria.publication_revisions WHERE id=:id
                '''
            ),
            {'id': first_id},
        ).one()
    assert [(int(row.revision_id), row.event_type) for row in events] == [
        (first_id, 'activated'),
        (first_id, 'withdrawn'),
        (second_id, 'activated'),
    ]
    withdrawn_event = events[1]
    assert int(withdrawn_event.actor_user_id) == withdrawal_actor
    assert int(withdrawn_event.actor_user_id) != published_by
    assert withdrawn_event.reason == 'Korrektur der Woche'
    assert withdrawn_event.occurred_at == returned_at == withdrawal_row.withdrawn_at
    assert before <= returned_at <= after
    assert int(withdrawal_row.withdrawn_by) == withdrawal_actor
    assert withdrawal_row.withdrawal_reason == 'Korrektur der Woche'
    assert active == ['PAT-2026-KW36-R2']
    assert frozen_hash == original_hash
    with pytest.raises(DBAPIError, match='unveränderlich'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    UPDATE cafeteria.publication_lifecycle_events
                    SET reason='Manipuliert'
                    WHERE revision_id=:id AND event_type='withdrawn'
                    '''
                ),
                {'id': first_id},
            )
    with pytest.raises(DBAPIError, match='unveränderlich'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    UPDATE cafeteria.publication_revisions
                    SET snapshot_json = snapshot_json || jsonb_build_object('note', 'x')
                    WHERE id=:id
                    '''
                ),
                {'id': first_id},
            )


@LIVE_DATABASE
def test_cafeteria_prices_reject_json_strings(database_engine: Engine) -> None:
    payload = copy.deepcopy(_snapshot('staff_guest'))
    payload['days'][0]['services'][0]['options'][0]['prices']['internal_rappen'] = '1100'
    week_id = _insert_week(database_engine, 'staff_guest', 'published')
    with pytest.raises(DBAPIError, match='JSON-Ganzzahlen'):
        _insert_revision(database_engine, week_id, 'staff_guest', snapshot=payload)


@LIVE_DATABASE
def test_local_auth_updates_keep_provider_roles_and_bump_both_users(
    database_engine: Engine,
) -> None:
    password_hash = generate_password_hash('correct horse battery staple')
    with database_engine.begin() as connection:
        first_id = int(
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.users(auth_provider, display_name)
                    VALUES ('local', 'Küche A') RETURNING id
                    '''
                )
            ).scalar_one()
        )
        second_id = int(
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.users(auth_provider, display_name)
                    VALUES ('local', 'Küche B') RETURNING id
                    '''
                )
            ).scalar_one()
        )
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.local_credentials(user_id, username, password_hash)
                VALUES (:user_id, 'kueche.a', :password_hash)
                '''
            ),
            {'user_id': first_id, 'password_hash': password_hash},
        )
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.user_role_cache(user_id, role_code, source)
                VALUES (:user_id, 'Cafeteria.Editor', 'local')
                '''
            ),
            {'user_id': first_id},
        )
    with pytest.raises(DBAPIError, match='auth_provider=local|Rollenquelle'):
        with database_engine.begin() as connection:
            connection.execute(
                text("UPDATE cafeteria.users SET auth_provider='system' WHERE id=:id"),
                {'id': first_id},
            )
    with pytest.raises(DBAPIError, match='Rollenquelle'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.user_role_cache(user_id, role_code, source)
                    VALUES (:user_id, 'Cafeteria.Publisher', 'entra_token')
                    '''
                ),
                {'user_id': first_id},
            )
    with database_engine.begin() as connection:
        before = {
            int(row.id): int(row.authz_version)
            for row in connection.execute(
                text('SELECT id, authz_version FROM cafeteria.users WHERE id IN (:a, :b)'),
                {'a': first_id, 'b': second_id},
            )
        }
        connection.execute(
            text(
                '''
                UPDATE cafeteria.user_role_cache
                SET user_id=:new_user
                WHERE user_id=:old_user AND role_code='Cafeteria.Editor'
                '''
            ),
            {'new_user': second_id, 'old_user': first_id},
        )
        after = {
            int(row.id): int(row.authz_version)
            for row in connection.execute(
                text('SELECT id, authz_version FROM cafeteria.users WHERE id IN (:a, :b)'),
                {'a': first_id, 'b': second_id},
            )
        }
    assert after[first_id] == before[first_id] + 1
    assert after[second_id] == before[second_id] + 1


@LIVE_DATABASE
def test_validate_publication_revision_is_defined_once(database_engine: Engine) -> None:
    with database_engine.connect() as connection:
        count = connection.execute(
            text(
                '''
                SELECT count(*)
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname='cafeteria' AND p.proname='validate_publication_revision'
                '''
            )
        ).scalar_one()
    assert int(count) == 1


@LIVE_DATABASE
def test_v4_draft_revision_is_withdrawn_and_not_public() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    baseline_path = ROOT / 'database' / 'migrations' / '0001_initial_postgresql.sql'
    payload = _snapshot('patient')
    raw = engine.raw_connection()
    try:
        driver = raw.driver_connection
        assert driver is not None
        driver.execute(baseline_path.read_text(encoding='utf-8'), prepare=False)
        driver.execute(
            '''
            INSERT INTO cafeteria.schema_migrations(version, name, checksum_sha256, application_version)
            VALUES (4, 'sql_baseline_two_profiles', %s, 'fachmodell-2-profile')
            ''',
            (hashlib.sha256(baseline_path.read_bytes()).hexdigest(),),
        )
        driver.execute(
            '''
            INSERT INTO cafeteria.users(public_id, auth_provider, display_name)
            VALUES ('00000000-0000-0000-0000-000000000001', 'system', 'System');
            INSERT INTO cafeteria.locations(code, name) VALUES ('KIRCHLINDACH', 'Klinik Südhang');
            INSERT INTO cafeteria.offer_profiles(code, display_name, allows_prices, allows_weekend, allowed_meals)
            VALUES
                ('patient', 'Patienten', false, true, ARRAY['LUNCH','DINNER']::text[]),
                ('staff_guest', 'Cafeteria', true, false, ARRAY['LUNCH']::text[]);
            INSERT INTO cafeteria.meal_periods(code, display_name, sort_order)
            VALUES ('LUNCH', 'Mittag', 10), ('DINNER', 'Abend', 20);
            INSERT INTO cafeteria.menu_types(code, display_name, sort_order)
            VALUES ('MENU_1', 'Menü 1', 10), ('VEGGIE', 'Vegetarisch', 20);
            '''
        )
        driver.execute(
            '''
            INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start, workflow_state)
            SELECT l.id, p.id, DATE '2026-08-31', 'draft'
            FROM cafeteria.locations l
            JOIN cafeteria.offer_profiles p ON p.code='patient'
            WHERE l.code='KIRCHLINDACH'
            '''
        )
        driver.execute(
            '''
            INSERT INTO cafeteria.publication_revisions(
                menu_week_id, revision_number, revision_code, snapshot_json, published_by
            )
            SELECT w.id, 1, %s, %s::jsonb, u.id
            FROM cafeteria.menu_weeks w
            JOIN cafeteria.users u ON u.public_id='00000000-0000-0000-0000-000000000001'
            '''
            ,
            (payload['revision_id'], json.dumps(payload, ensure_ascii=False)),
        )
        driver.commit()
    finally:
        raw.close()
    with engine.connect() as connection:
        v4_public = connection.execute(
            text('SELECT count(*) FROM cafeteria.active_publications')
        ).scalar_one()
    assert int(v4_public) == 1
    database.provision_database_roles(
        engine,
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    database.run_migrations(engine, ROOT / 'database' / 'schema.sql')
    with engine.connect() as connection:
        versions = connection.execute(
            text('SELECT version FROM cafeteria.schema_migrations ORDER BY version')
        ).scalars().all()
        public_rows = connection.execute(
            text('SELECT count(*) FROM cafeteria.active_publications')
        ).scalar_one()
        withdrawn = connection.execute(
            text(
                '''
                SELECT withdrawn_at IS NOT NULL, withdrawal_reason
                FROM cafeteria.publication_revisions
                '''
            )
        ).one()
        events = connection.execute(
            text(
                '''
                SELECT event_type, actor_user_id
                FROM cafeteria.publication_lifecycle_events ORDER BY id
                '''
            )
        ).all()
    assert versions == [4, 5, 6, 7, 8, 9, 10, 11]
    assert int(public_rows) == 0
    assert withdrawn[0] is True
    assert 'v4' in withdrawn[1]
    assert [row.event_type for row in events] == ['activated', 'withdrawn']
    assert events[1].actor_user_id is None
    _drop_schema(engine)
    engine.dispose()


def _user_id(engine: Engine, public_id: str) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(
                text('SELECT id FROM cafeteria.users WHERE public_id=:public_id'),
                {'public_id': public_id},
            ).scalar_one()
        )


def _tamper_capability_field(token: str, index: int, value: str) -> str:
    parts = token.split('.')
    parts[index] = value
    return '.'.join(parts)


def _role_database_url(role_name: str, password: str) -> str:
    assert DATABASE_URL is not None
    return make_url(DATABASE_URL).set(
        username=role_name,
        password=password,
    ).render_as_string(hide_password=False)


def _apply_role_permissions(engine: Engine) -> None:
    database.provision_database_roles(
        engine,
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    database._execute_script(engine, str(ROOT / 'database' / 'permissions.sql'))


def _normalize_catalog_value(value: Any, schema_name: str) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.replace(f'{schema_name}.', '<schema>.')
    return normalized.replace('cafeteria.', '<schema>.').replace(
        'migrated_contract.', '<schema>.'
    )


def _schema_structure(engine: Engine, schema_name: str) -> dict[str, list[tuple[Any, ...]]]:
    queries = {
        'columns': '''
            SELECT table_name, ordinal_position, column_name, data_type, udt_name,
                   is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema=:schema_name
            ORDER BY table_name, ordinal_position
        ''',
        'constraints': '''
            SELECT rel.relname, con.conname, con.contype, pg_get_constraintdef(con.oid, true)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid=con.conrelid
            JOIN pg_namespace ns ON ns.oid=rel.relnamespace
            WHERE ns.nspname=:schema_name
            ORDER BY rel.relname, con.conname
        ''',
        'indexes': '''
            SELECT tab.relname, idx.relname, pg_get_indexdef(i.indexrelid)
            FROM pg_index i
            JOIN pg_class tab ON tab.oid=i.indrelid
            JOIN pg_class idx ON idx.oid=i.indexrelid
            JOIN pg_namespace ns ON ns.oid=tab.relnamespace
            WHERE ns.nspname=:schema_name
            ORDER BY tab.relname, idx.relname
        ''',
        'functions': '''
            SELECT p.proname, pg_get_function_identity_arguments(p.oid), p.prokind,
                   p.prosecdef, p.proconfig, p.prosrc
            FROM pg_proc p
            JOIN pg_namespace ns ON ns.oid=p.pronamespace
            WHERE ns.nspname=:schema_name
            ORDER BY p.proname, pg_get_function_identity_arguments(p.oid)
        ''',
        'triggers': '''
            SELECT rel.relname, trg.tgname, pg_get_triggerdef(trg.oid, true)
            FROM pg_trigger trg
            JOIN pg_class rel ON rel.oid=trg.tgrelid
            JOIN pg_namespace ns ON ns.oid=rel.relnamespace
            WHERE ns.nspname=:schema_name AND NOT trg.tgisinternal
            ORDER BY rel.relname, trg.tgname
        ''',
        'views': '''
            SELECT viewname, definition
            FROM pg_views
            WHERE schemaname=:schema_name
            ORDER BY viewname
        ''',
    }
    structure: dict[str, list[tuple[Any, ...]]] = {}
    with engine.connect() as connection:
        for name, query in queries.items():
            rows = connection.execute(text(query), {'schema_name': schema_name}).tuples().all()
            structure[name] = [
                tuple(_normalize_catalog_value(value, schema_name) for value in row)
                for row in rows
            ]
    return structure


@LIVE_DATABASE
def test_schema_baseline_matches_sequential_migration_structure() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    _drop_schema(engine)
    try:
        database.provision_database_roles(
            engine,
            app_password=APP_PASSWORD,
            backup_password=BACKUP_PASSWORD,
            auth_issuer_password=ISSUER_PASSWORD,
        )
        database.run_migrations(engine, ROOT / 'database' / 'schema.sql')
        with engine.begin() as connection:
            connection.execute(text('ALTER SCHEMA cafeteria RENAME TO migrated_contract'))
        database._execute_script(engine, str(ROOT / 'database' / 'schema.sql'))
        migrated = _schema_structure(engine, 'migrated_contract')
        baseline = _schema_structure(engine, 'cafeteria')
        for object_type in migrated:
            assert baseline[object_type] == migrated[object_type], object_type
    finally:
        with engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
            connection.execute(text('DROP SCHEMA IF EXISTS migrated_contract CASCADE'))
        engine.dispose()


@LIVE_DATABASE
def test_concurrent_insert_and_week_demotion_cannot_hide_revision(
    database_engine: Engine,
) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published', '2026-09-21')
    payload = _dated_snapshot('patient', '2026-09-21')
    payload['revision_id'] = 'PAT-2026-KW39-R1'
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def insert_revision() -> None:
        barrier.wait(timeout=10)
        try:
            _insert_revision(database_engine, week_id, 'patient', snapshot=payload)
            outcomes['insert'] = 'ok'
        except DBAPIError as exc:
            outcomes['insert'] = str(exc)

    def demote_week() -> None:
        barrier.wait(timeout=10)
        try:
            with database_engine.begin() as connection:
                connection.execute(
                    text("UPDATE cafeteria.menu_weeks SET workflow_state='draft' WHERE id=:id"),
                    {'id': week_id},
                )
            outcomes['demote'] = 'ok'
        except DBAPIError as exc:
            outcomes['demote'] = str(exc)

    insert_thread = threading.Thread(target=insert_revision)
    demote_thread = threading.Thread(target=demote_week)
    insert_thread.start()
    demote_thread.start()
    insert_thread.join(timeout=15)
    demote_thread.join(timeout=15)
    assert not insert_thread.is_alive()
    assert not demote_thread.is_alive()
    assert set(outcomes) == {'insert', 'demote'}
    assert (outcomes['insert'] == 'ok') != (outcomes['demote'] == 'ok')
    with database_engine.connect() as connection:
        state = connection.execute(
            text('SELECT workflow_state FROM cafeteria.menu_weeks WHERE id=:id'),
            {'id': week_id},
        ).scalar_one()
        revision = connection.execute(
            text(
                '''
                SELECT id, withdrawn_at
                FROM cafeteria.publication_revisions
                WHERE menu_week_id=:id
                '''
            ),
            {'id': week_id},
        ).first()
        visible = int(
            connection.execute(text('SELECT count(*) FROM cafeteria.active_publications')).scalar_one()
        )
        events = connection.execute(
            text(
                '''
                SELECT event_type
                FROM cafeteria.publication_lifecycle_events
                ORDER BY id
                '''
            )
        ).scalars().all()
    if outcomes['insert'] == 'ok':
        assert state == 'published'
        assert revision is not None
        assert revision.withdrawn_at is None
        assert visible == 1
        assert list(events) == ['activated']
    else:
        assert state == 'draft'
        assert revision is None
        assert visible == 0
        assert list(events) == []


@LIVE_DATABASE
def test_publication_capability_rejects_replay_wrong_binding_expiry_and_role_race(
    database_engine: Engine,
) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published', '2026-09-28')
    payload = _dated_snapshot('patient', '2026-09-28')
    payload['revision_id'] = 'PAT-2026-KW40-R1'
    first_id = _insert_revision(database_engine, week_id, 'patient', snapshot=payload)
    actor_id = _user_id(database_engine, database.DEMO_USER_PUBLIC_ID)
    other_week = _insert_week(database_engine, 'patient', 'published', '2026-10-05')
    other_payload = _dated_snapshot('patient', '2026-10-05')
    other_payload['revision_id'] = 'PAT-2026-KW41-R1'
    other_id = _insert_revision(database_engine, other_week, 'patient', snapshot=other_payload)

    replay_token = database.issue_publication_capability(database_engine, actor_id, first_id)
    database.withdraw_publication_revision(database_engine, first_id, replay_token, 'Erster Rückzug')
    with pytest.raises(DBAPIError, match='Nonce'):
        database.withdraw_publication_revision(database_engine, first_id, replay_token, 'Replay')

    replacement = copy.deepcopy(payload)
    replacement['revision_id'] = 'PAT-2026-KW40-R2'
    with database_engine.begin() as connection:
        replacement_id = int(
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.publication_revisions(
                        menu_week_id, revision_number, revision_code, snapshot_json, published_by
                    )
                    SELECT :week_id, 2, :revision_code, CAST(:snapshot AS jsonb), u.id
                    FROM cafeteria.users u
                    WHERE u.public_id='00000000-0000-0000-0000-000000000001'
                    RETURNING id
                    '''
                ),
                {
                    'week_id': week_id,
                    'revision_code': replacement['revision_id'],
                    'snapshot': json.dumps(replacement, ensure_ascii=False),
                },
            ).scalar_one()
        )

    bound_token = database.issue_publication_capability(database_engine, actor_id, replacement_id)
    with pytest.raises(DBAPIError, match='passt nicht zur Publikationsrevision'):
        database.withdraw_publication_revision(database_engine, other_id, bound_token, 'Falsche Revision')
    tampered_actor = _tamper_capability_field(bound_token, 2, '0')
    with pytest.raises(DBAPIError, match='ungültig oder abgelaufen'):
        database.withdraw_publication_revision(
            database_engine, replacement_id, tampered_actor, 'Falscher Akteur'
        )

    expired = database.issue_publication_capability(
        database_engine, actor_id, replacement_id, ttl=timedelta(seconds=1)
    )
    time.sleep(2)
    with pytest.raises(DBAPIError, match='ungültig oder abgelaufen'):
        database.withdraw_publication_revision(database_engine, replacement_id, expired, 'Abgelaufen')

    stale = database.issue_publication_capability(database_engine, actor_id, replacement_id)
    with database_engine.begin() as connection:
        connection.execute(
            text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor'),
            {'actor': actor_id},
        )
    with pytest.raises(DBAPIError, match='Rollenänderung|nicht zur Publikation berechtigt'):
        database.withdraw_publication_revision(database_engine, replacement_id, stale, 'Rollenentzug')
    with database_engine.connect() as connection:
        withdrawn = connection.execute(
            text('SELECT withdrawn_at FROM cafeteria.publication_revisions WHERE id=:id'),
            {'id': replacement_id},
        ).scalar_one()
        visible = connection.execute(
            text('SELECT revision_code FROM cafeteria.active_publications ORDER BY revision_code')
        ).scalars().all()
    assert withdrawn is None
    assert visible == ['PAT-2026-KW40-R2', 'PAT-2026-KW41-R1']


@LIVE_DATABASE
def test_capability_consumption_rolls_back_with_withdrawal(database_engine: Engine) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published', '2026-11-09')
    payload = _dated_snapshot('patient', '2026-11-09')
    payload['revision_id'] = 'PAT-2026-KW46-R1'
    revision_id = _insert_revision(database_engine, week_id, 'patient', snapshot=payload)
    actor_id = _user_id(database_engine, database.DEMO_USER_PUBLIC_ID)
    capability = database.issue_publication_capability(database_engine, actor_id, revision_id)
    _apply_role_permissions(database_engine)
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        connection = app_engine.connect()
        transaction = connection.begin()
        try:
            connection.execute(
                text(
                    'SELECT cafeteria.withdraw_publication_revision('
                    ':revision, :capability, :reason)'
                ),
                {
                    'revision': revision_id,
                    'capability': capability,
                    'reason': 'Absichtlich zurückgerollt',
                },
            ).scalar_one()
            transaction.rollback()
        finally:
            connection.close()
        database.withdraw_publication_revision(
            app_engine,
            revision_id,
            capability,
            'Nach Rollback gültig',
        )
    finally:
        app_engine.dispose()

    with database_engine.connect() as connection:
        nonce_count = int(
            connection.execute(text('SELECT count(*) FROM cafeteria.auth_capability_nonces')).scalar_one()
        )
        event_count = int(
            connection.execute(
                text(
                    '''
                    SELECT count(*) FROM cafeteria.publication_lifecycle_events
                    WHERE revision_id=:revision AND event_type='withdrawn'
                    '''
                ),
                {'revision': revision_id},
            ).scalar_one()
        )
    assert nonce_count == 1
    assert event_count == 1


@LIVE_DATABASE
def test_capability_hard_reset_invalidates_history_and_bootstraps_one_secret(
    database_engine: Engine,
) -> None:
    first_week_id = _insert_week(database_engine, 'patient', 'published', '2026-11-16')
    first_payload = _dated_snapshot('patient', '2026-11-16')
    first_payload['revision_id'] = 'PAT-2026-KW47-R1'
    first_revision_id = _insert_revision(
        database_engine,
        first_week_id,
        'patient',
        snapshot=first_payload,
    )
    second_week_id = _insert_week(database_engine, 'patient', 'published', '2026-11-23')
    second_payload = _dated_snapshot('patient', '2026-11-23')
    second_payload['revision_id'] = 'PAT-2026-KW48-R1'
    second_revision_id = _insert_revision(
        database_engine,
        second_week_id,
        'patient',
        snapshot=second_payload,
    )
    actor_id = _user_id(database_engine, database.DEMO_USER_PUBLIC_ID)

    old_capability = database.issue_publication_capability(
        database_engine,
        actor_id,
        first_revision_id,
    )
    database.withdraw_publication_revision(
        database_engine,
        first_revision_id,
        old_capability,
        'Vor Wiederherstellung verbraucht',
    )
    unused_old_capability = database.issue_publication_capability(
        database_engine,
        actor_id,
        second_revision_id,
    )
    assert old_capability.split('.')[1] == unused_old_capability.split('.')[1] == '1'

    with database_engine.begin() as connection:
        connection.execute(
            text(
                'DROP TABLE cafeteria.auth_capability_nonces, '
                'cafeteria.auth_capability_secrets'
            )
        )
        assert int(
            connection.execute(
                text('SELECT cafeteria.ensure_auth_capability_state()')
            ).scalar_one()
        ) == 1
        assert int(
            connection.execute(
                text('SELECT cafeteria.ensure_auth_capability_state()')
            ).scalar_one()
        ) == 1
        new_secret_id = int(
            connection.execute(
                text('SELECT cafeteria.hard_reset_auth_capability_state()')
            ).scalar_one()
        )
        state = connection.execute(
            text(
                '''
                SELECT count(*) AS secret_count,
                       count(*) FILTER (WHERE active) AS active_count,
                       min(octet_length(secret)) AS secret_bytes
                FROM cafeteria.auth_capability_secrets
                '''
            )
        ).one()
        nonce_count = int(
            connection.execute(
                text('SELECT count(*) FROM cafeteria.auth_capability_nonces')
            ).scalar_one()
        )
        reset_events = int(
            connection.execute(
                text(
                    '''
                    SELECT count(*)
                    FROM cafeteria.audit_events
                    WHERE action='auth_capability.hard_reset'
                      AND entity_type='auth_capability_state'
                    '''
                )
            ).scalar_one()
        )
    assert new_secret_id == 1
    assert tuple(state) == (1, 1, 32)
    assert nonce_count == 0
    assert reset_events == 1

    with pytest.raises(DBAPIError, match='ungültig oder abgelaufen'):
        database.withdraw_publication_revision(
            database_engine,
            first_revision_id,
            old_capability,
            'Replay nach Wiederherstellung',
        )
    with pytest.raises(DBAPIError, match='ungültig oder abgelaufen'):
        database.withdraw_publication_revision(
            database_engine,
            second_revision_id,
            unused_old_capability,
            'Unverbrauchte Alt-Capability nach Wiederherstellung',
        )

    new_capability = database.issue_publication_capability(
        database_engine,
        actor_id,
        second_revision_id,
    )
    assert new_capability.split('.')[1] == '1'
    withdrawn_at = database.withdraw_publication_revision(
        database_engine,
        second_revision_id,
        new_capability,
        'Nach Wiederherstellung gültig',
    )
    assert withdrawn_at is not None


@LIVE_DATABASE
def test_committed_empty_entra_role_sync_wins_against_in_flight_withdrawal(
    database_engine: Engine,
) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published', '2026-11-16')
    payload = _dated_snapshot('patient', '2026-11-16')
    payload['revision_id'] = 'PAT-2026-KW47-R1'
    revision_id = _insert_revision(database_engine, week_id, 'patient', snapshot=payload)
    claims = {
        'tid': '33333333-3333-3333-3333-333333333333',
        'oid': '44444444-4444-4444-4444-444444444444',
        'sub': 'entra-role-revocation-race',
        'name': 'Entra Rollenentzug',
        'email': 'revoked@example.invalid',
        'preferred_username': 'revoked@example.invalid',
    }
    actor_id = database.upsert_entra_user(
        database_engine,
        claims,
        ['Cafeteria.Publisher'],
    )
    capability = database.issue_publication_capability(database_engine, actor_id, revision_id)
    token_authz_version = int(capability.split('.')[4])
    _apply_role_permissions(database_engine)
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    revocation_locked = threading.Event()
    allow_commit = threading.Event()
    withdrawal_started = threading.Event()
    outcomes: dict[str, str] = {}

    def revoke_role() -> None:
        connection = database_engine.connect()
        transaction = connection.begin()
        try:
            connection.execute(
                text(
                    '''
                    SELECT cafeteria.sync_entra_user(
                        CAST(:tenant_id AS uuid),
                        CAST(:object_id AS uuid),
                        :subject_id,
                        :display_name,
                        :email,
                        :preferred_username,
                        CAST(:roles AS text[])
                    )
                    '''
                ),
                {
                    'tenant_id': claims['tid'],
                    'object_id': claims['oid'],
                    'subject_id': claims['sub'],
                    'display_name': claims['name'],
                    'email': claims['email'],
                    'preferred_username': claims['preferred_username'],
                    'roles': [],
                },
            ).scalar_one()
            revocation_locked.set()
            assert allow_commit.wait(timeout=10)
            transaction.commit()
            outcomes['revoke'] = 'committed'
        finally:
            if transaction.is_active:
                transaction.rollback()
            connection.close()

    def withdraw() -> None:
        assert revocation_locked.wait(timeout=10)
        withdrawal_started.set()
        try:
            database.withdraw_publication_revision(
                app_engine,
                revision_id,
                capability,
                'Rennen gegen Rollenentzug',
            )
            outcomes['withdraw'] = 'unexpected-success'
        except DBAPIError as exc:
            outcomes['withdraw'] = str(exc)

    revoke_thread = threading.Thread(target=revoke_role)
    withdraw_thread = threading.Thread(target=withdraw)
    revoke_thread.start()
    withdraw_thread.start()
    assert withdrawal_started.wait(timeout=10)
    time.sleep(0.2)
    assert withdraw_thread.is_alive()
    allow_commit.set()
    revoke_thread.join(timeout=10)
    withdraw_thread.join(timeout=10)
    app_engine.dispose()
    assert not revoke_thread.is_alive()
    assert not withdraw_thread.is_alive()
    assert outcomes['revoke'] == 'committed'
    assert 'Rollenänderung' in outcomes['withdraw'] or 'nicht zur Publikation berechtigt' in outcomes['withdraw']
    with database_engine.connect() as connection:
        withdrawn_at, role_count, authz_version = connection.execute(
            text(
                '''
                SELECT p.withdrawn_at,
                       (SELECT count(*) FROM cafeteria.user_role_cache r WHERE r.user_id=:actor),
                       u.authz_version
                FROM cafeteria.publication_revisions p
                JOIN cafeteria.users u ON u.id=:actor
                WHERE p.id=:revision
                '''
            ),
            {'actor': actor_id, 'revision': revision_id},
        ).one()
        nonce_count = int(
            connection.execute(text('SELECT count(*) FROM cafeteria.auth_capability_nonces')).scalar_one()
        )
    assert withdrawn_at is None
    assert int(role_count) == 0
    assert int(authz_version) > token_authz_version
    assert nonce_count == 0


@LIVE_DATABASE
def test_cafeteria_app_cannot_spoof_actor_or_read_capability_secrets(
    database_engine: Engine,
) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published', '2026-10-12')
    payload = _dated_snapshot('patient', '2026-10-12')
    payload['revision_id'] = 'PAT-2026-KW42-R1'
    revision_id = _insert_revision(database_engine, week_id, 'patient', snapshot=payload)
    actor_id = _user_id(database_engine, database.DEMO_USER_PUBLIC_ID)
    _apply_role_permissions(database_engine)
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text(
                        'SELECT cafeteria.issue_publication_capability(:actor, :revision, interval \'5 minutes\')'
                    ),
                    {'actor': actor_id, 'revision': revision_id},
                )
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(text('SELECT secret FROM cafeteria.auth_capability_secrets'))
        with pytest.raises(DBAPIError, match='ungültig oder abgelaufen|permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text(
                        'SELECT cafeteria.withdraw_publication_revision(:revision, :capability, :reason)'
                    ),
                    {
                        'revision': revision_id,
                        'capability': 'v1.1.1.1.1.0.00.00',
                        'reason': 'Spoof',
                    },
                )
        with pytest.raises(DBAPIError, match='kontrollierten Rückzug|permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text(
                        '''
                        UPDATE cafeteria.publication_revisions
                        SET withdrawn_at=clock_timestamp(),
                            withdrawal_reason='Direkt',
                            withdrawn_by=:actor
                        WHERE id=:id
                        '''
                    ),
                    {'actor': actor_id, 'id': revision_id},
                )
    finally:
        app_engine.dispose()
    with database_engine.connect() as connection:
        remaining = connection.execute(
            text('SELECT withdrawn_at FROM cafeteria.publication_revisions WHERE id=:id'),
            {'id': revision_id},
        ).scalar_one()
        visible = int(connection.execute(text('SELECT count(*) FROM cafeteria.active_publications')).scalar_one())
    assert remaining is None
    assert visible == 1


@LIVE_DATABASE
def test_database_roles_use_real_password_authentication(database_engine: Engine) -> None:
    _apply_role_permissions(database_engine)
    wrong_password_engine = create_engine(
        _role_database_url('cafeteria_app', 'wrong-app-secret'),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with pytest.raises(DBAPIError, match='password authentication failed|28P01'):
            with wrong_password_engine.connect():
                pass
    finally:
        wrong_password_engine.dispose()

    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with app_engine.connect() as connection:
            assert connection.execute(text('SELECT current_user')).scalar_one() == 'cafeteria_app'
    finally:
        app_engine.dispose()


@LIVE_DATABASE
def test_app_cannot_restore_revoked_roles_or_authorization_version(
    database_engine: Engine,
) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published', '2026-10-19')
    payload = _dated_snapshot('patient', '2026-10-19')
    payload['revision_id'] = 'PAT-2026-KW43-R1'
    revision_id = _insert_revision(database_engine, week_id, 'patient', snapshot=payload)
    actor_id = _user_id(database_engine, database.DEMO_USER_PUBLIC_ID)
    capability = database.issue_publication_capability(database_engine, actor_id, revision_id)
    token_authz_version = int(capability.split('.')[4])
    _apply_role_permissions(database_engine)

    with database_engine.begin() as connection:
        connection.execute(
            text(
                '''
                DELETE FROM cafeteria.user_role_cache
                WHERE user_id=:actor AND role_code='Cafeteria.Publisher'
                '''
            ),
            {'actor': actor_id},
        )

    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text(
                        '''
                        INSERT INTO cafeteria.user_role_cache(user_id, role_code, source)
                        VALUES (:actor, 'Cafeteria.Publisher', 'demo')
                        '''
                    ),
                    {'actor': actor_id},
                )
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text('UPDATE cafeteria.users SET authz_version=:version WHERE id=:actor'),
                    {'actor': actor_id, 'version': token_authz_version},
                )
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text('UPDATE cafeteria.users SET disabled_at=NULL WHERE id=:actor'),
                    {'actor': actor_id},
                )
        with pytest.raises(DBAPIError, match='Rollenänderung|nicht zur Publikation berechtigt'):
            database.withdraw_publication_revision(
                app_engine,
                revision_id,
                capability,
                'Gestohlene Capability',
            )
    finally:
        app_engine.dispose()

    with database_engine.connect() as connection:
        state = connection.execute(
            text(
                '''
                SELECT u.authz_version,
                       EXISTS (
                           SELECT 1 FROM cafeteria.user_role_cache r
                           WHERE r.user_id=u.id AND r.role_code='Cafeteria.Publisher'
                       ) AS publisher,
                       p.withdrawn_at
                FROM cafeteria.users u
                CROSS JOIN cafeteria.publication_revisions p
                WHERE u.id=:actor AND p.id=:revision
                '''
            ),
            {'actor': actor_id, 'revision': revision_id},
        ).one()
    assert int(state.authz_version) > token_authz_version
    assert state.publisher is False
    assert state.withdrawn_at is None


@LIVE_DATABASE
def test_app_grants_are_column_scoped_and_owner_issuance_still_works(
    database_engine: Engine,
) -> None:
    _apply_role_permissions(database_engine)
    _apply_role_permissions(database_engine)
    with database_engine.connect() as connection:
        privileges = connection.execute(
            text(
                '''
                SELECT
                        has_table_privilege('cafeteria_app', 'cafeteria.users', 'SELECT') AS users_select,
                        has_table_privilege('cafeteria_app', 'cafeteria.users', 'INSERT') AS users_insert,
                        has_column_privilege('cafeteria_app', 'cafeteria.users', 'authz_version', 'UPDATE') AS authz_update,
                    has_column_privilege('cafeteria_app', 'cafeteria.users', 'disabled_at', 'UPDATE') AS disabled_update,
                    has_table_privilege('cafeteria_app', 'cafeteria.user_role_cache', 'INSERT') AS role_insert,
                    has_table_privilege('cafeteria_app', 'cafeteria.user_role_cache', 'UPDATE') AS role_update,
                    has_table_privilege('cafeteria_app', 'cafeteria.user_role_cache', 'DELETE') AS role_delete,
                        has_column_privilege('cafeteria_app', 'cafeteria.local_credentials', 'password_hash', 'UPDATE') AS password_update,
                        has_table_privilege('cafeteria_app', 'cafeteria.local_credentials', 'INSERT') AS credentials_insert,
                    has_table_privilege('cafeteria_app', 'cafeteria.auth_capability_nonces', 'INSERT') AS nonce_insert,
                    has_sequence_privilege(
                        'cafeteria_app',
                        'cafeteria.auth_capability_secrets_id_seq',
                        'USAGE'
                    ) AS secret_sequence_usage,
                    has_function_privilege(
                        'cafeteria_app',
                        'cafeteria.issue_publication_capability(bigint,bigint,interval)',
                        'EXECUTE'
                    ) AS capability_issue,
                    has_function_privilege(
                        'cafeteria_app',
                        'cafeteria.sync_entra_user(uuid,uuid,text,text,text,text,text[])',
                        'EXECUTE'
                    ) AS entra_sync,
                    has_function_privilege(
                        'cafeteria_app',
                        'cafeteria.ensure_auth_capability_state()',
                        'EXECUTE'
                    ) AS capability_state_ensure,
                    has_function_privilege(
                        'cafeteria_app',
                        'cafeteria.hard_reset_auth_capability_state()',
                        'EXECUTE'
                    ) AS capability_hard_reset,
                    NOT EXISTS (
                        SELECT 1
                        FROM pg_proc p
                        JOIN pg_namespace n ON n.oid=p.pronamespace
                        CROSS JOIN LATERAL aclexplode(
                            COALESCE(p.proacl, acldefault('f', p.proowner))
                        ) acl
                        WHERE n.nspname='cafeteria'
                          AND p.proname='hard_reset_auth_capability_state'
                          AND acl.grantee=0
                          AND acl.privilege_type='EXECUTE'
                    ) AS public_capability_hard_reset_revoked
                '''
            )
        ).mappings().one()
        definer_privileges = connection.execute(
            text(
                '''
                SELECT p.proname,
                       EXISTS (
                           SELECT 1
                           FROM aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) acl
                           WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE'
                       ) AS public_execute,
                       has_function_privilege('cafeteria_app', p.oid, 'EXECUTE') AS app_execute,
                       has_function_privilege('cafeteria_backup', p.oid, 'EXECUTE') AS backup_execute
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='cafeteria' AND p.prosecdef
                ORDER BY p.proname
                '''
            )
        ).mappings().all()
    assert privileges['users_select'] is True
    assert privileges['users_insert'] is False
    assert privileges['authz_update'] is False
    assert privileges['disabled_update'] is False
    assert privileges['role_insert'] is False
    assert privileges['role_update'] is False
    assert privileges['role_delete'] is False
    assert privileges['password_update'] is False
    assert privileges['credentials_insert'] is False
    assert privileges['nonce_insert'] is False
    assert privileges['secret_sequence_usage'] is False
    assert privileges['capability_issue'] is False
    assert privileges['entra_sync'] is False
    assert privileges['capability_state_ensure'] is False
    assert privileges['capability_hard_reset'] is False
    assert privileges['public_capability_hard_reset_revoked'] is True
    assert {row['proname'] for row in definer_privileges} == {
        'bootstrap_auth_capability_secret',
        'bootstrap_first_local_admin',
            'disable_local_user',
        'ensure_auth_capability_state',
        'hard_reset_auth_capability_state',
        'issue_publication_capability',
        'provision_local_user',
        'record_local_login_lock',
        'record_publication_lifecycle',
        'resolve_auth_actor',
        'rotate_auth_capability_secret',
        'bootstrap_first_local_admin',
            'set_local_password',
        'sync_entra_user',
        'withdraw_publication_revision',
    }
    for row in definer_privileges:
        assert row['public_execute'] is False
        assert row['backup_execute'] is False
        assert row['app_execute'] is (row['proname'] == 'withdraw_publication_revision')

    week_id = _insert_week(database_engine, 'patient', 'published', '2026-10-26')
    payload = _dated_snapshot('patient', '2026-10-26')
    payload['revision_id'] = 'PAT-2026-KW44-R1'
    revision_id = _insert_revision(database_engine, week_id, 'patient', snapshot=payload)
    actor_id = _user_id(database_engine, database.DEMO_USER_PUBLIC_ID)
    capability = database.issue_publication_capability(database_engine, actor_id, revision_id)
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text('SELECT cafeteria.ensure_auth_capability_state()')
                ).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text('SELECT cafeteria.hard_reset_auth_capability_state()')
                ).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text("SELECT nextval('cafeteria.auth_capability_secrets_id_seq')")
                ).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text(
                        '''
                        INSERT INTO cafeteria.audit_events(action, entity_type)
                        VALUES ('sequence-contract', 'test')
                        '''
                    )
                )
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with app_engine.begin() as connection:
                connection.execute(
                    text("SELECT nextval('cafeteria.audit_events_id_seq')")
                ).scalar_one()
        database.withdraw_publication_revision(
            app_engine,
            revision_id,
            capability,
            'Kontrollierter Rückzug',
        )
    finally:
        app_engine.dispose()


@LIVE_DATABASE
def test_authorization_version_is_monotonic_for_privileged_writers(
    database_engine: Engine,
) -> None:
    actor_id = _user_id(database_engine, database.DEMO_USER_PUBLIC_ID)
    with database_engine.connect() as connection:
        current_version = int(
            connection.execute(
                text('SELECT authz_version FROM cafeteria.users WHERE id=:actor'),
                {'actor': actor_id},
            ).scalar_one()
        )
    assert current_version > 1
    with pytest.raises(DBAPIError, match='authz_version darf nicht zurückgesetzt werden|42501'):
        with database_engine.begin() as connection:
            connection.execute(
                text('UPDATE cafeteria.users SET authz_version=:version WHERE id=:actor'),
                {'actor': actor_id, 'version': current_version - 1},
            )
    with database_engine.connect() as connection:
        actual_version = int(
            connection.execute(
                text('SELECT authz_version FROM cafeteria.users WHERE id=:actor'),
                {'actor': actor_id},
            ).scalar_one()
        )
    assert actual_version == current_version


@LIVE_DATABASE
def test_capability_ttl_is_positive_and_at_most_fifteen_minutes(
    database_engine: Engine,
) -> None:
    week_id = _insert_week(database_engine, 'patient', 'published', '2026-11-02')
    payload = _dated_snapshot('patient', '2026-11-02')
    payload['revision_id'] = 'PAT-2026-KW45-R1'
    revision_id = _insert_revision(database_engine, week_id, 'patient', snapshot=payload)
    actor_id = _user_id(database_engine, database.DEMO_USER_PUBLIC_ID)

    for invalid_ttl in (
        timedelta(0),
        timedelta(seconds=-1),
        timedelta(minutes=15, microseconds=1),
        timedelta(days=36_500),
    ):
        with pytest.raises(ValueError, match='0.*15 Minuten'):
            database.issue_publication_capability(
                database_engine,
                actor_id,
                revision_id,
                ttl=invalid_ttl,
            )

    token = database.issue_publication_capability(
        database_engine,
        actor_id,
        revision_id,
        ttl=timedelta(minutes=15),
    )
    assert token.startswith('v1.')
    with pytest.raises(DBAPIError, match='höchstens 15 Minuten|22023'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    SELECT cafeteria.issue_publication_capability(
                        :actor, :revision, interval '100 years'
                    )
                    '''
                ),
                {'actor': actor_id, 'revision': revision_id},
            )


@LIVE_DATABASE
def test_backup_role_excludes_capability_secrets_and_nonces(database_engine: Engine) -> None:
    _apply_role_permissions(database_engine)
    backup_engine = create_engine(
        _role_database_url('cafeteria_backup', BACKUP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with backup_engine.connect() as connection:
            connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one()
            connection.execute(text('SELECT last_value FROM cafeteria.menu_weeks_id_seq')).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied|42501|read-only'):
            with backup_engine.connect() as connection:
                connection.execute(
                    text("SELECT nextval('cafeteria.auth_capability_secrets_id_seq')")
                ).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with backup_engine.connect() as connection:
                connection.execute(
                    text('SELECT cafeteria.ensure_auth_capability_state()')
                ).scalar_one()
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            with backup_engine.connect() as connection:
                connection.execute(
                    text('SELECT cafeteria.hard_reset_auth_capability_state()')
                ).scalar_one()
        denied_queries = (
            text('SELECT count(*) FROM cafeteria.auth_capability_secrets'),
            text('SELECT count(*) FROM cafeteria.auth_capability_nonces'),
        )
        for denied_query in denied_queries:
            with pytest.raises(DBAPIError, match='permission denied|42501'):
                with backup_engine.connect() as connection:
                    connection.execute(denied_query).scalar_one()
    finally:
        backup_engine.dispose()

    with database_engine.connect() as connection:
        (
            secret_select,
            nonce_select,
            secret_sequence_select,
            hard_reset_execute,
            ensure_execute,
        ) = connection.execute(
            text(
                '''
                SELECT
                    has_table_privilege(
                        'cafeteria_backup', 'cafeteria.auth_capability_secrets', 'SELECT'
                    ),
                    has_table_privilege(
                        'cafeteria_backup', 'cafeteria.auth_capability_nonces', 'SELECT'
                    ),
                    has_sequence_privilege(
                        'cafeteria_backup',
                        'cafeteria.auth_capability_secrets_id_seq',
                        'SELECT'
                    ),
                    has_function_privilege(
                        'cafeteria_backup',
                        'cafeteria.hard_reset_auth_capability_state()',
                        'EXECUTE'
                    ),
                    has_function_privilege(
                        'cafeteria_backup',
                        'cafeteria.ensure_auth_capability_state()',
                        'EXECUTE'
                    )
                '''
            )
        ).one()
    assert secret_select is False
    assert nonce_select is False
    assert secret_sequence_select is False
    assert hard_reset_execute is False
    assert ensure_execute is False


@LIVE_DATABASE
def test_entra_identity_sync_is_owner_only_and_does_not_reenable_user(
    database_engine: Engine,
) -> None:
    claims = {
        'tid': '11111111-1111-1111-1111-111111111111',
        'oid': '22222222-2222-2222-2222-222222222222',
        'sub': 'entra-subject',
        'name': 'Entra Test',
        'email': 'entra@example.invalid',
        'preferred_username': 'entra@example.invalid',
    }
    roles = ['Cafeteria.Publisher']
    invalid_role_inputs: tuple[object, ...] = (
        None,
        ('Cafeteria.Publisher',),
        ['Cafeteria.Publisher', 'Cafeteria.Publisher'],
        [' Cafeteria.Publisher'],
        ['cafeteria.publisher'],
        ['Cafeteria.\u200bPublisher'],
        ['Cafeteria.Future'],
        [None],
    )
    for invalid_roles in invalid_role_inputs:
        with pytest.raises(ValueError, match='Entra-Rollen'):
            database.upsert_entra_user(
                database_engine,
                claims,
                invalid_roles,  # type: ignore[arg-type]
            )

    user_id = database.upsert_entra_user(database_engine, claims, roles)
    with database_engine.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:user_id'),
            {'user_id': user_id},
        )
    database.upsert_entra_user(database_engine, claims, roles)
    with database_engine.connect() as connection:
        disabled, assigned_roles = connection.execute(
            text(
                '''
                SELECT u.disabled_at IS NOT NULL,
                       array_agg(r.role_code ORDER BY r.role_code)
                FROM cafeteria.users u
                JOIN cafeteria.user_role_cache r ON r.user_id=u.id
                WHERE u.id=:user_id
                GROUP BY u.id
                '''
            ),
            {'user_id': user_id},
        ).one()
    assert disabled is True
    assert assigned_roles == ['Cafeteria.Publisher']

    with pytest.raises(DBAPIError, match='unbekannte|doppelte|42501'):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    '''
                    SELECT cafeteria.sync_entra_user(
                        CAST(:tenant_id AS uuid), CAST(:object_id AS uuid),
                        :subject_id, :display_name, :email, :preferred_username,
                        CAST(:roles AS text[])
                    )
                    '''
                ),
                {
                    'tenant_id': claims['tid'],
                    'object_id': claims['oid'],
                    'subject_id': claims['sub'],
                    'display_name': claims['name'],
                    'email': claims['email'],
                    'preferred_username': claims['preferred_username'],
                    'roles': ['Cafeteria.Publisher', 'Cafeteria.Publisher'],
                },
            ).scalar_one()

    _apply_role_permissions(database_engine)
    app_engine = create_engine(
        _role_database_url('cafeteria_app', APP_PASSWORD),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with pytest.raises(DBAPIError, match='permission denied|42501'):
            database.upsert_entra_user(app_engine, claims, roles)
    finally:
        app_engine.dispose()


def test_config_database_paths_are_repo_local(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ('SCHEMA_PATH', 'SEED_PATH', 'DEMO_SEED_PATH', 'PERMISSIONS_PATH'):
        monkeypatch.delenv(name, raising=False)
    from cafeteria.config import Config

    cfg = Config()
    for path in (cfg.SCHEMA_PATH, cfg.SEED_PATH, cfg.DEMO_SEED_PATH, cfg.PERMISSIONS_PATH):
        resolved = Path(path)
        assert resolved.is_file(), path
        assert '/app/' not in resolved.as_posix()
        assert 'database' in resolved.parts
