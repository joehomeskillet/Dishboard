"""Wochenvorgaben, Bereichsnamen und der Schema-20-Vertrag auf echtem PostgreSQL."""
from __future__ import annotations

# ruff: noqa: F401, F811

import hashlib
import json
import os
import threading
from copy import deepcopy
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.operations_settings import (
    PROFILE_SLOTS,
    OperationsConflictError,
    SlotRule,
    default_schedule,
    get_area_names,
    get_schedule,
    get_schedule_connection,
    normalise_time,
    parse_schedule,
    save_area_name,
    save_schedule,
    slot_defaults,
)
from cafeteria.patient_payload import patient_text_is_forbidden, validate_snapshot_payload
from cafeteria.workflow import load_draft
from cafeteria.workflow_snapshot import build_snapshot

from test_admin_workflow_db import (
    WEEK_START, _actor_id, _patient_values, _save, _staff_values,
)
from test_admin_workflow_routes import (  # noqa: F401
    APP_PASSWORD, ROOT, _login, app, database_engine,
)
from test_component_metadata_master_lock_db import (  # noqa: F401
    PERMISSIONS, SCHEMA, _drop_schema, pg16,
)

pytestmark = pytest.mark.skipif(
    not os.getenv('TEST_DATABASE_URL'),
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)

PATIENT_AREA_NAME = 'Patientinnen und Patienten'
STAFF_AREA_NAME = 'Mitarbeitende und externe Gäste'
SCHOOL_AREA_NAME = 'Schülerinnen und Schüler'
_INSERT_REVISION_SQL = """
    INSERT INTO cafeteria.publication_revisions(
        menu_week_id, revision_number, revision_code, snapshot_json, published_by
    ) VALUES (:week_id, :revision_number, :revision_code, CAST(:snapshot AS jsonb), :actor)
"""
_V20_FUNCTION_SQL = """
    SELECT proname, prosrc, prosecdef, provolatile, proconfig,
           has_function_privilege('cafeteria_app', oid, 'EXECUTE') AS app,
           has_function_privilege('cafeteria_backup', oid, 'EXECUTE') AS backup
    FROM pg_proc WHERE pronamespace='cafeteria'::regnamespace
      AND proname IN ('patient_key_is_forbidden', 'validate_publication_revision',
                      'workflow_week_context')
    ORDER BY proname
"""


def _slot(state: str = 'open', start: Any = None, end: Any = None, notice: str = '') -> dict[str, Any]:
    return {'state': state, 'start': start, 'end': end, 'notice': notice}


def _raw_slots(profile: str, changes: dict[tuple[int, str], Any] | None = None) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    for day, meal in PROFILE_SLOTS[profile]:
        slots.setdefault(str(day), {})[meal] = _slot()
    for (day, meal), value in (changes or {}).items():
        slots[str(day)][meal] = value
    return slots


def _location_id(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(
            text("SELECT id FROM cafeteria.locations WHERE code='KIRCHLINDACH'")
        ).scalar_one())


def _admin(app, database_engine: Engine) -> tuple[int, int]:  # noqa: F811
    admin, actor = _login(app, database_engine, ['Cafeteria.Admin'])
    with admin.session_transaction() as session:
        return actor, int(session['authz_version'])


def _schedule_rows(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text(
            "SELECT count(*) FROM cafeteria.settings WHERE setting_key='operations_schedule'"
        )).scalar_one())


def _patient_snapshot(engine: Engine, revision_code: str = 'PAT-2026-KW36-R1') -> dict[str, Any]:
    actor = _actor_id(engine)
    _save(engine, 'patient', _patient_values())
    draft = load_draft(engine, 'patient', WEEK_START, actor_id=actor)
    return build_snapshot('patient', draft, revision_code)


def _schema_two(
    snapshot: dict[str, Any],
    *,
    area_name: str | None = SCHOOL_AREA_NAME,
    start: str | None = '11:30',
    end: str | None = '12:30',
) -> dict[str, Any]:
    result = deepcopy(snapshot)
    result['schema_version'] = 2
    if area_name is not None:
        result['area_name'] = area_name
    for day in result['days']:
        for service in day['services']:
            if start is not None:
                service['service_start'] = start
            if end is not None:
                service['service_end'] = end
    return result


def _publication_attempt(
    engine: Engine, week_id: int, snapshot: dict[str, Any], actor: int
) -> None:
    """Fügt eine Revision ein und rollt immer zurück; geprüft wird nur der Trigger."""
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(_INSERT_REVISION_SQL), {
                'week_id': week_id,
                'revision_number': 1,
                'revision_code': snapshot['revision_id'],
                'snapshot': json.dumps(snapshot, ensure_ascii=False),
                'actor': actor,
            })
        finally:
            transaction.rollback()


def _invalid_schedules() -> list[tuple[str, dict[str, Any], str]]:
    weekend = _raw_slots('staff_guest')
    weekend['6'] = {'LUNCH': _slot()}
    missing_meal = _raw_slots('patient')
    del missing_meal['1']['DINNER']
    return [
        ('staff_guest', weekend, 'cafeteria-samstag'),
        ('patient', missing_meal, 'fehlende-mahlzeit'),
        ('staff_guest', _raw_slots('staff_guest', {(1, 'LUNCH'): _slot(state='holiday', notice='Feiertag')}), 'unbekannter-status'),
        ('staff_guest', _raw_slots('staff_guest', {(1, 'LUNCH'): _slot(start='24:00')}), 'stunde-24'),
        ('staff_guest', _raw_slots('staff_guest', {(1, 'LUNCH'): _slot(start='13:30', end='11:30')}), 'nachtfenster'),
        ('staff_guest', _raw_slots('staff_guest', {(1, 'LUNCH'): _slot(state='closed')}), 'geschlossen-ohne-hinweis'),
        ('staff_guest', _raw_slots('staff_guest', {(1, 'LUNCH'): _slot(notice='Zeile\numbruch')}), 'steuerzeichen'),
        ('patient', _raw_slots('patient', {(1, 'LUNCH'): _slot(notice='CHF 5')}), 'patientenpreis'),
    ]


_INVALID_SCHEDULES = _invalid_schedules()


def test_missing_row_yields_open_grid_without_cafeteria_weekend(database_engine):  # noqa: F811
    location = _location_id(database_engine)
    for profile in ('staff_guest', 'patient'):
        schedule = get_schedule(database_engine, location, profile)
        assert schedule == default_schedule(profile)
        assert schedule.profile_code == profile and schedule.revision == 0
        assert set(schedule.slots) == set(PROFILE_SLOTS[profile])
        assert all(rule == SlotRule('open', None, None, '') for rule in schedule.slots.values())
    cafeteria = get_schedule(database_engine, location, 'staff_guest')
    patient = get_schedule(database_engine, location, 'patient')
    assert len(cafeteria.slots) == 5 and len(patient.slots) == 14
    assert not [day for day, _ in cafeteria.slots if day > 5]
    assert slot_defaults(cafeteria, WEEK_START, 'LUNCH') == SlotRule('open', None, None, '')
    with pytest.raises(KeyError):
        slot_defaults(cafeteria, WEEK_START, 'DINNER')
    with database_engine.connect() as connection:
        assert get_schedule_connection(connection, location, 'patient') == patient


def test_saving_is_compare_and_set_over_revision(app, database_engine):  # noqa: F811
    actor, version = _admin(app, database_engine)
    location = _location_id(database_engine)
    slots = _raw_slots('staff_guest', {(1, 'LUNCH'): _slot(start='11:30', end='13:30')})

    assert save_schedule(database_engine, actor, version, location, 'staff_guest', 0, slots) == 1
    with database_engine.connect() as connection:
        row = connection.execute(text("""
            SELECT s.location_id, s.profile_id, s.setting_value, s.updated_by, p.code
            FROM cafeteria.settings s JOIN cafeteria.offer_profiles p ON p.id=s.profile_id
            WHERE s.setting_key='operations_schedule'
        """)).mappings().one()
    assert row['location_id'] == location and row['code'] == 'staff_guest'
    assert row['updated_by'] == actor and row['setting_value']['revision'] == 1
    assert row['setting_value']['slots']['1']['LUNCH'] == {
        'state': 'open', 'start': '11:30', 'end': '13:30', 'notice': '',
    }
    stored = get_schedule(database_engine, location, 'staff_guest')
    assert stored.revision == 1
    assert slot_defaults(stored, WEEK_START, 'LUNCH') == SlotRule('open', '11:30', '13:30', '')

    assert save_schedule(database_engine, actor, version, location, 'staff_guest', 1, slots) == 2
    with pytest.raises(OperationsConflictError):
        save_schedule(database_engine, actor, version, location, 'staff_guest', 1, slots)
    with pytest.raises(OperationsConflictError):
        save_schedule(database_engine, actor, version, location, 'staff_guest', 0, slots)
    assert get_schedule(database_engine, location, 'staff_guest').revision == 2
    assert _schedule_rows(database_engine) == 1


def test_two_parallel_saves_leave_exactly_one_winner(app, database_engine):  # noqa: F811
    actor, version = _admin(app, database_engine)
    location = _location_id(database_engine)
    barrier = threading.Barrier(2)
    results: list[Any] = []
    lock = threading.Lock()

    def attempt() -> None:
        engine = create_engine(database_engine.url, poolclass=NullPool, pool_pre_ping=True)
        try:
            barrier.wait(timeout=30)
            outcome: Any = save_schedule(
                engine, actor, version, location, 'patient', 0, _raw_slots('patient')
            )
        except Exception as error:  # noqa: BLE001 - der Konflikt ist das Prüfergebnis
            outcome = error
        finally:
            engine.dispose()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads)
    assert [outcome for outcome in results if outcome == 1] == [1]
    assert sum(isinstance(outcome, OperationsConflictError) for outcome in results) == 1
    assert _schedule_rows(database_engine) == 1
    assert get_schedule(database_engine, location, 'patient').revision == 1


@pytest.mark.parametrize(
    'profile,slots',
    [(profile, slots) for profile, slots, _ in _INVALID_SCHEDULES],
    ids=[identifier for _, _, identifier in _INVALID_SCHEDULES],
)
def test_invalid_schedule_is_rejected_without_writing(app, database_engine, profile, slots):  # noqa: F811
    actor, version = _admin(app, database_engine)
    with pytest.raises(ValueError):
        save_schedule(
            database_engine, actor, version, _location_id(database_engine), profile, 0, slots
        )
    with pytest.raises(ValueError):
        parse_schedule(profile, {'revision': 1, 'slots': slots})
    assert _schedule_rows(database_engine) == 0


def test_broken_stored_value_and_unknown_profile_are_reported(database_engine):  # noqa: F811
    location = _location_id(database_engine)
    with pytest.raises(ValueError):
        get_schedule(database_engine, location, 'kiosk')
    with pytest.raises(ValueError):
        normalise_time('7:30')
    assert normalise_time('') is None and normalise_time(None) is None
    with database_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO cafeteria.settings(location_id, profile_id, setting_key, setting_value)
            SELECT :location_id, p.id, 'operations_schedule', '{"revision": 1}'::jsonb
            FROM cafeteria.offer_profiles p WHERE p.code='patient'
        """), {'location_id': location})
    with pytest.raises(ValueError):
        get_schedule(database_engine, location, 'patient')


def test_only_a_current_admin_may_save_the_schedule(app, database_engine):  # noqa: F811
    location = _location_id(database_engine)
    actor, version = _admin(app, database_engine)
    slots = _raw_slots('patient')
    for candidate_actor, candidate_version in ((actor, version + 1), (0, version), (actor, 0)):
        with pytest.raises(PermissionError):
            save_schedule(
                database_engine, candidate_actor, candidate_version, location, 'patient', 0, slots
            )

    editor, editor_actor = _login(app, database_engine, ['Cafeteria.Editor'])
    with editor.session_transaction() as session:
        editor_version = int(session['authz_version'])
    with pytest.raises(PermissionError):
        save_schedule(database_engine, editor_actor, editor_version, location, 'patient', 0, slots)

    disabled_actor, disabled_version = _admin(app, database_engine)
    with database_engine.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:id'),
            {'id': disabled_actor},
        )
    with pytest.raises(PermissionError):
        save_schedule(
            database_engine, disabled_actor, disabled_version, location, 'patient', 0, slots
        )
    assert _schedule_rows(database_engine) == 0


def test_area_names_are_compare_and_set_with_narrow_column_privilege(app, database_engine):  # noqa: F811
    actor, version = _admin(app, database_engine)
    assert get_area_names(database_engine) == {
        'patient': PATIENT_AREA_NAME, 'staff_guest': STAFF_AREA_NAME,
    }
    assert save_area_name(
        database_engine, actor, version, 'patient', PATIENT_AREA_NAME, f'  {SCHOOL_AREA_NAME}  '
    ) == SCHOOL_AREA_NAME
    assert get_area_names(database_engine)['patient'] == SCHOOL_AREA_NAME
    with pytest.raises(OperationsConflictError):
        save_area_name(database_engine, actor, version, 'patient', PATIENT_AREA_NAME, 'Zu spät')
    for name in ('', '   ', 'X' * 81, 'Mit' + chr(7) + 'Steuerzeichen'):
        with pytest.raises(ValueError):
            save_area_name(database_engine, actor, version, 'staff_guest', STAFF_AREA_NAME, name)
    with pytest.raises(ValueError):
        save_area_name(database_engine, actor, version, 'patient', SCHOOL_AREA_NAME, 'Preisliste')

    editor, editor_actor = _login(app, database_engine, ['Cafeteria.Editor'])
    with editor.session_transaction() as session:
        editor_version = int(session['authz_version'])
    with pytest.raises(PermissionError):
        save_area_name(
            database_engine, editor_actor, editor_version, 'staff_guest', STAFF_AREA_NAME, 'Bistro'
        )
    assert get_area_names(database_engine) == {
        'patient': SCHOOL_AREA_NAME, 'staff_guest': STAFF_AREA_NAME,
    }

    with database_engine.connect() as connection:
        privileges = connection.execute(text("""
            SELECT
                has_column_privilege('cafeteria_app','cafeteria.offer_profiles','display_name','UPDATE') AS display_name,
                has_column_privilege('cafeteria_app','cafeteria.offer_profiles','code','UPDATE') AS code,
                has_column_privilege('cafeteria_app','cafeteria.offer_profiles','allows_prices','UPDATE') AS allows_prices,
                has_column_privilege('cafeteria_app','cafeteria.offer_profiles','allows_weekend','UPDATE') AS allows_weekend,
                has_column_privilege('cafeteria_app','cafeteria.offer_profiles','allowed_meals','UPDATE') AS allowed_meals
        """)).mappings().one()
    assert privileges['display_name'] is True
    assert not any(
        privileges[column]
        for column in ('code', 'allows_prices', 'allows_weekend', 'allowed_meals')
    )


def test_runtime_role_can_write_schedule_and_area_name(app, database_engine):  # noqa: F811
    actor, version = _admin(app, database_engine)
    location = _location_id(database_engine)
    runtime = create_engine(
        database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD),
        poolclass=NullPool,
    )
    try:
        assert save_schedule(
            runtime, actor, version, location, 'patient', 0, _raw_slots('patient')
        ) == 1
        assert get_schedule(runtime, location, 'patient').revision == 1
        assert save_area_name(
            runtime, actor, version, 'staff_guest', STAFF_AREA_NAME, 'Bistro Südhang'
        ) == 'Bistro Südhang'
        assert get_area_names(runtime)['staff_guest'] == 'Bistro Südhang'
        with pytest.raises(DBAPIError):
            with runtime.begin() as connection:
                connection.execute(
                    text("UPDATE cafeteria.offer_profiles SET allows_weekend=true WHERE code='staff_guest'")
                )
    finally:
        runtime.dispose()


def test_repeated_seed_keeps_curated_names_and_reenforces_the_grid(app, database_engine):  # noqa: F811
    actor, version = _admin(app, database_engine)
    save_area_name(database_engine, actor, version, 'patient', PATIENT_AREA_NAME, SCHOOL_AREA_NAME)
    with database_engine.begin() as connection:
        connection.execute(text(
            "UPDATE cafeteria.meal_periods SET display_name='Mittagessen' WHERE code='LUNCH'"
        ))
        connection.execute(text(
            "UPDATE cafeteria.offer_profiles "
            "SET allowed_meals=ARRAY['LUNCH','DINNER','BRUNCH']::text[] WHERE code='patient'"
        ))
    for _ in range(2):
        database._execute_script(database_engine, str(ROOT / 'database' / 'seed.sql'))
    with database_engine.connect() as connection:
        profile = connection.execute(text(
            'SELECT display_name, allowed_meals, allows_prices, allows_weekend '
            "FROM cafeteria.offer_profiles WHERE code='patient'"
        )).mappings().one()
        staff = connection.execute(text(
            "SELECT display_name FROM cafeteria.offer_profiles WHERE code='staff_guest'"
        )).scalar_one()
        meal = connection.execute(text(
            "SELECT display_name FROM cafeteria.meal_periods WHERE code='LUNCH'"
        )).scalar_one()
    assert profile['display_name'] == SCHOOL_AREA_NAME and staff == STAFF_AREA_NAME
    assert profile['allowed_meals'] == ['LUNCH', 'DINNER']
    assert profile['allows_prices'] is False and profile['allows_weekend'] is True
    assert meal == 'Mittagessen'


def test_v19_upgrade_adds_times_without_touching_rows_or_receipts(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 19:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    _save(pg16, 'staff_guest', _staff_values())
    actor = _actor_id(pg16)
    draft = load_draft(pg16, 'staff_guest', WEEK_START, actor_id=actor)
    snapshot = build_snapshot('staff_guest', draft, 'CAF-2026-KW36-R1')
    with pg16.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_weeks SET workflow_state='published'"))
        connection.execute(text(_INSERT_REVISION_SQL), {
            'week_id': draft['id'], 'revision_number': 1,
            'revision_code': 'CAF-2026-KW36-R1',
            'snapshot': json.dumps(snapshot, ensure_ascii=False), 'actor': actor,
        })
        services = connection.execute(
            text('SELECT to_jsonb(s) FROM cafeteria.menu_services s ORDER BY id')
        ).scalars().all()
        revisions = connection.execute(
            text('SELECT to_jsonb(r) FROM cafeteria.publication_revisions r ORDER BY id')
        ).scalars().all()
        context_before = connection.execute(
            text('SELECT cafeteria.workflow_week_context(:id)::text'), {'id': draft['id']}
        ).scalar_one()

    applied = database.run_migrations(pg16, SCHEMA)
    assert [entry.version for entry in applied] == list(range(4, 21))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert connection.execute(text(
            "SELECT to_jsonb(s)-'service_start'-'service_end' FROM cafeteria.menu_services s ORDER BY id"
        )).scalars().all() == services
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.menu_services '
            'WHERE service_start IS NOT NULL OR service_end IS NOT NULL'
        )).scalar_one() == 0
        assert connection.execute(text(
            'SELECT to_jsonb(r) FROM cafeteria.publication_revisions r ORDER BY id'
        )).scalars().all() == revisions
        assert connection.execute(
            text('SELECT cafeteria.workflow_week_context(:id)::text'), {'id': draft['id']}
        ).scalar_one() == context_before
        assert connection.execute(text(
            'SELECT name, application_version, checksum_sha256 '
            'FROM cafeteria.schema_migrations WHERE version=20'
        )).one() == (
            '0017_v19_to_v20.sql', 'dishboard-schema-v20',
            hashlib.sha256(plan[-1].path.read_bytes()).hexdigest(),
        )
        migrated = connection.execute(text(_V20_FUNCTION_SQL)).all()
        ledger = connection.execute(
            text('SELECT * FROM cafeteria.schema_migrations ORDER BY version')
        ).all()

    database.run_migrations(pg16, SCHEMA)
    with pg16.connect() as connection:
        assert connection.execute(
            text('SELECT * FROM cafeteria.schema_migrations ORDER BY version')
        ).all() == ledger
    _drop_schema(pg16)
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert connection.execute(text(_V20_FUNCTION_SQL)).all() == migrated


def test_week_context_reports_times_only_when_they_are_set(database_engine):  # noqa: F811
    _save(database_engine, 'staff_guest', _staff_values())
    actor = _actor_id(database_engine)
    week_id = load_draft(database_engine, 'staff_guest', WEEK_START, actor_id=actor)['id']
    with database_engine.begin() as connection:
        before = json.loads(connection.execute(
            text('SELECT cafeteria.workflow_week_context(:id)::text'), {'id': week_id}
        ).scalar_one())
        connection.execute(text(
            "UPDATE cafeteria.menu_services SET service_start='11:30', service_end='13:30' "
            'WHERE id=(SELECT min(id) FROM cafeteria.menu_services)'
        ))
        after = json.loads(connection.execute(
            text('SELECT cafeteria.workflow_week_context(:id)::text'), {'id': week_id}
        ).scalar_one())
    assert before['services'] and all(
        'start' not in service and 'end' not in service for service in before['services']
    )
    assert after['services'][0]['start'] == '11:30' and after['services'][0]['end'] == '13:30'
    assert all(
        'start' not in service for service in after['services'][1:]
    )
    assert {key: value for key, value in after['services'][0].items()
            if key not in {'start', 'end'}} == before['services'][0]
    with database_engine.begin() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(text(
                "UPDATE cafeteria.menu_services SET service_start='13:30', service_end='11:30' "
                'WHERE id=(SELECT min(id) FROM cafeteria.menu_services)'
            ))


def test_sql_validator_accepts_schema_two_and_rejects_forbidden_values(database_engine):  # noqa: F811
    actor = _actor_id(database_engine)
    base = _patient_snapshot(database_engine)
    week_id = load_draft(database_engine, 'patient', WEEK_START, actor_id=actor)['id']
    with database_engine.begin() as connection:
        connection.execute(
            text("UPDATE cafeteria.menu_weeks SET workflow_state='published' WHERE id=:id"),
            {'id': week_id},
        )

    _publication_attempt(database_engine, week_id, _schema_two(base), actor)
    _publication_attempt(database_engine, week_id, base, actor)
    _publication_attempt(
        database_engine, week_id, _schema_two(base, start=None, end=None), actor
    )

    forbidden_key = _schema_two(base)
    forbidden_key['days'][0]['services'][0]['service_price'] = '5'
    rejected = (
        _schema_two(base, area_name='Preise intern'),
        _schema_two(base, area_name='   '),
        _schema_two(base, area_name='X' * 81),
        _schema_two(base, start='13:30', end='11:30'),
        _schema_two(base, start='24:00', end=None),
        _schema_two(base, start='7:30', end=None),
        forbidden_key,
    )
    for snapshot in rejected:
        with pytest.raises(DBAPIError):
            _publication_attempt(database_engine, week_id, snapshot, actor)


def test_python_validator_matches_the_schema_two_contract(database_engine):  # noqa: F811
    base = _patient_snapshot(database_engine)
    validate_snapshot_payload('patient', base)
    validate_snapshot_payload('patient', _schema_two(base))
    validate_snapshot_payload('patient', _schema_two(base, start=None, end=None))
    for snapshot in (
        _schema_two(base, area_name='Menü mit CHF Aufschlag'),
        _schema_two(base, start='7:30', end=None),
        _schema_two(base, start='13:30', end='11:30'),
    ):
        with pytest.raises(ValueError):
            validate_snapshot_payload('patient', snapshot)
    assert patient_text_is_forbidden('Ausgabe 11:30 Uhr') is True
    assert patient_text_is_forbidden(SCHOOL_AREA_NAME) is False
