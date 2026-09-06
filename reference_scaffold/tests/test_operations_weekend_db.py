"""Seven-day operations contract on PostgreSQL; existing publication bytes stay valid."""
from __future__ import annotations

# ruff: noqa: F401, F811
import datetime as dt
from copy import deepcopy

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.operations_settings import (
    OperationsConflictError, SlotRule, get_area_profiles, get_schedule,
    save_schedule, save_weekend_switch, slot_defaults,
)
from cafeteria.patient_payload import validate_snapshot_payload
from cafeteria.workflow import load_draft
from cafeteria.workflow_snapshot import build_snapshot
from test_admin_workflow_db import WEEK_START, _actor_id, _save, _staff_values
from test_admin_workflow_routes import APP_PASSWORD, ROOT, app, database_engine
from test_operations_settings_db import _admin, _location_id, _publication_attempt, _raw_slots, _slot

SATURDAY = WEEK_START + dt.timedelta(days=5)


def test_weekend_switch_preserves_saved_rules_and_seed(app, database_engine):
    actor, version = _admin(app, database_engine)
    location = _location_id(database_engine)
    slots = _raw_slots('staff_guest', {(6, 'LUNCH'): _slot(start='11:30', end='13:30')})
    save_schedule(database_engine, actor, version, location, 'staff_guest', 0, slots)
    closed = SlotRule('closed', None, None, 'Am Wochenende geschlossen')
    assert slot_defaults(get_schedule(database_engine, location, 'staff_guest'), SATURDAY, 'LUNCH') == closed
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD),
                            poolclass=NullPool)
    try:
        assert save_weekend_switch(runtime, actor, version, 'staff_guest', False, True) is True
        with runtime.connect() as connection:
            assert get_area_profiles(connection) == get_area_profiles(runtime)
        for _ in range(2):
            database._execute_script(database_engine, str(ROOT / 'database' / 'seed.sql'))
        profiles = get_area_profiles(runtime)
        assert profiles['staff_guest']['allows_weekend'] is True
        assert profiles['staff_guest']['allowed_meals'] == ['LUNCH']
        assert profiles['staff_guest']['allows_prices'] is True
        enabled = get_schedule(runtime, location, 'staff_guest')
        assert enabled.allows_weekend is True
        assert slot_defaults(enabled, SATURDAY, 'LUNCH') == SlotRule('open', '11:30', '13:30', '')
        assert save_weekend_switch(runtime, actor, version, 'staff_guest', True, False) is False
        disabled = get_schedule(runtime, location, 'staff_guest')
        assert disabled.slots == enabled.slots and disabled.revision == enabled.revision
        assert slot_defaults(disabled, SATURDAY, 'LUNCH') == closed
        with pytest.raises(OperationsConflictError):
            save_weekend_switch(runtime, actor, version, 'staff_guest', True, False)
        with pytest.raises(PermissionError):
            save_weekend_switch(runtime, actor, version + 1, 'staff_guest', False, True)
    finally:
        runtime.dispose()


@pytest.mark.parametrize('profile,expected,value', [
    ('patient', True, False), ('unknown', False, True),
    ('staff_guest', 0, True), ('staff_guest', False, 'true'),
])
def test_weekend_switch_rejects_invalid_contract(app, database_engine, profile, expected, value):
    actor, version = _admin(app, database_engine)
    with pytest.raises(ValueError):
        save_weekend_switch(database_engine, actor, version, profile, expected, value)
    assert get_area_profiles(database_engine)['staff_guest']['allows_weekend'] is False


@pytest.mark.parametrize('expected', [1, 5])
def test_nonzero_revision_never_creates_missing_settings(app, database_engine, expected):
    actor, version = _admin(app, database_engine)
    with pytest.raises(OperationsConflictError):
        save_schedule(database_engine, actor, version, _location_id(database_engine),
                      'patient', expected, _raw_slots('patient'))
    assert get_schedule(database_engine, _location_id(database_engine), 'patient').revision == 0


def test_service_guard_preserves_existing_weekend_when_switch_turns_off(app, database_engine):
    actor, version = _admin(app, database_engine)
    _save(database_engine, 'staff_guest', _staff_values())
    week = load_draft(database_engine, 'staff_guest', WEEK_START, actor_id=actor)['id']
    insert = text("""INSERT INTO cafeteria.menu_services(menu_week_id,service_date,meal_period_id,
        service_state,notice) SELECT :week,:date,id,'closed','Samstags geschlossen'
        FROM cafeteria.meal_periods WHERE code='LUNCH' RETURNING id""")
    params = {'week': week, 'date': SATURDAY}
    with pytest.raises(DBAPIError) as error:
        with database_engine.begin() as connection:
            connection.execute(insert, params)
    assert error.value.orig.sqlstate == '23514'
    save_weekend_switch(database_engine, actor, version, 'staff_guest', False, True)
    with database_engine.begin() as connection:
        service = connection.execute(insert, params).scalar_one()
    save_weekend_switch(database_engine, actor, version, 'staff_guest', True, False)
    with database_engine.begin() as connection:
        connection.execute(text("""UPDATE cafeteria.menu_services
            SET service_state='closed',notice='Bestehender Samstag',service_start='11:30'
            WHERE id=:id"""), {'id': service})
        assert connection.execute(text('SELECT notice FROM cafeteria.menu_services WHERE id=:id'),
                                  {'id': service}).scalar_one() == 'Bestehender Samstag'
    for statement, values in [
        (insert, {'week': week, 'date': SATURDAY + dt.timedelta(days=1)}),
        (text('UPDATE cafeteria.menu_services SET service_date=:date WHERE id=:id'),
         {'id': service, 'date': SATURDAY + dt.timedelta(days=1)}),
    ]:
        with pytest.raises(DBAPIError) as error:
            with database_engine.begin() as connection:
                connection.execute(statement, values)
        assert error.value.orig.sqlstate == '23514'
    with pytest.raises(DBAPIError):
        with database_engine.begin() as connection:
            connection.execute(text("UPDATE cafeteria.offer_profiles SET allows_weekend=false WHERE code='patient'"))


def _staff_snapshot(engine):
    actor = _actor_id(engine)
    _save(engine, 'staff_guest', _staff_values())
    draft = load_draft(engine, 'staff_guest', WEEK_START, actor_id=actor)
    snapshot = build_snapshot('staff_guest', draft, 'CAF-2026-KW36-R1')
    with engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_weeks SET workflow_state='published' WHERE id=:id"),
                           {'id': draft['id']})
    return actor, draft['id'], snapshot


@pytest.mark.parametrize('weekend_days', [0, 1, 2])
def test_python_and_sql_accept_five_six_seven_days_without_global_join(database_engine, weekend_days):
    actor, week, snapshot = _staff_snapshot(database_engine)
    for day in range(5, 5 + weekend_days):
        snapshot['days'][day]['services'] = deepcopy(snapshot['days'][0]['services'])
    # Switch is still off: an existing publication stays valid independently of current settings.
    assert get_area_profiles(database_engine)['staff_guest']['allows_weekend'] is False
    validate_snapshot_payload('staff_guest', snapshot)
    _publication_attempt(database_engine, week, snapshot, actor)
    if weekend_days:
        snapshot['days'][5]['services'] = [
            {'meal_code': 'LUNCH', 'meal_name': 'Mittag', 'service_state': 'closed',
             'notice': 'Samstag geschlossen', 'options': []}
        ]
        validate_snapshot_payload('staff_guest', snapshot)
        _publication_attempt(database_engine, week, snapshot, actor)


@pytest.mark.parametrize('invalid', ['duplicate', 'dinner', 'missing_weekday', 'prices', 'time', 'area'])
def test_python_and_sql_reject_invalid_weekend_snapshots(database_engine, invalid):
    actor, week, snapshot = _staff_snapshot(database_engine)
    service = deepcopy(snapshot['days'][0]['services'][0])
    snapshot['days'][5]['services'] = [service]
    if invalid == 'duplicate':
        snapshot['days'][5]['services'].append(deepcopy(service))
    elif invalid == 'dinner':
        service['meal_code'] = 'DINNER'
    elif invalid == 'missing_weekday':
        snapshot['days'][0]['services'] = []
    elif invalid == 'prices':
        del service['options'][0]['prices']
    elif invalid == 'time':
        service['service_start'] = '24:00'
    else:
        snapshot['area_name'] = 'X' * 81
    with pytest.raises(ValueError):
        validate_snapshot_payload('staff_guest', snapshot)
    with pytest.raises(DBAPIError):
        _publication_attempt(database_engine, week, snapshot, actor)


def _price_insert(connection, item):
    connection.execute(text("""INSERT INTO cafeteria.menu_item_prices
        (menu_item_id,internal_rappen,external_rappen) VALUES (:item,1100,1300)"""), {'item': item})


def test_weekend_prices_stay_locked_behind_the_release(app, database_engine):
    """Ohne erteilte Freigabe entsteht kein Cafeteria-Wochenendservice und damit kein Preis."""
    from test_database_invariants import _insert_service, _insert_week
    actor, version = _admin(app, database_engine)
    assert get_area_profiles(database_engine)['staff_guest']['allows_weekend'] is False
    week = _insert_week(database_engine, 'staff_guest')
    with pytest.raises(DBAPIError) as error:
        _insert_service(database_engine, week, SATURDAY.isoformat(), 'LUNCH')
    assert error.value.orig.sqlstate == '23514'
    save_weekend_switch(database_engine, actor, version, 'staff_guest', False, True)
    service = _insert_service(database_engine, week, SATURDAY.isoformat(), 'LUNCH')
    from test_database_invariants import _insert_item
    with database_engine.begin() as connection:
        _price_insert(connection, _insert_item(database_engine, service))


@pytest.mark.parametrize('day', [5, 6], ids=['saturday', 'sunday'])
@pytest.mark.parametrize('switch_after_service', [True, False], ids=['enabled', 'disabled-after-creation'])
def test_existing_weekend_lunch_keeps_regular_prices(app, database_engine, day, switch_after_service):
    from test_database_invariants import _insert_item, _insert_service, _insert_week
    actor, version = _admin(app, database_engine)
    save_weekend_switch(database_engine, actor, version, 'staff_guest', False, True)
    week = _insert_week(database_engine, 'staff_guest')
    service = _insert_service(database_engine, week, (WEEK_START + dt.timedelta(days=day)).isoformat(), 'LUNCH')
    item = _insert_item(database_engine, service)
    if not switch_after_service:
        save_weekend_switch(database_engine, actor, version, 'staff_guest', True, False)
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD),
                            poolclass=NullPool)
    try:
        with runtime.begin() as connection:
            _price_insert(connection, item)
            connection.execute(text("""UPDATE cafeteria.menu_item_prices
                SET internal_rappen=1200,external_rappen=1400 WHERE menu_item_id=:item"""), {'item': item})
            assert connection.execute(text("""SELECT internal_rappen,external_rappen,currency
                FROM cafeteria.menu_item_prices WHERE menu_item_id=:item"""), {'item': item}).one() == (1200, 1400, 'CHF')
    finally:
        runtime.dispose()


def test_patient_weekend_still_rejects_prices(database_engine):
    from test_database_invariants import _insert_item, _insert_service, _insert_week
    week = _insert_week(database_engine, 'patient')
    service = _insert_service(database_engine, week, SATURDAY.isoformat(), 'LUNCH')
    item = _insert_item(database_engine, service)
    with pytest.raises(DBAPIError) as error:
        with database_engine.begin() as connection:
            _price_insert(connection, item)
    assert error.value.orig.sqlstate == '23514'


def test_cafeteria_dinner_prices_stay_forbidden(database_engine):
    """Die Mahlzeitenregel bleibt unverändert, auch ohne Wochentagsprüfung im Preis-Trigger."""
    from test_database_invariants import _insert_item, _insert_service, _insert_week
    week = _insert_week(database_engine, 'patient')
    service = _insert_service(database_engine, week, WEEK_START.isoformat(), 'DINNER')
    item = _insert_item(database_engine, service)
    with pytest.raises(DBAPIError) as error:
        with database_engine.begin() as connection:
            _price_insert(connection, item)
    assert error.value.orig.sqlstate == '23514'
