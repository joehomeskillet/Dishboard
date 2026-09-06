from __future__ import annotations

import io
from copy import deepcopy
from datetime import timedelta

import pytest
from sqlalchemy import text

from cafeteria.csvio import snapshot_to_csv, validate_upload
from cafeteria.workflow import StaleDraftError, _draft_values, import_draft
from cafeteria.workflow_copy_store import copy_previous_week
from cafeteria.workflow_partial_store import (
    PartialWorkflowConflictError,
    PartialWorkflowValidationError,
    apply_schedule_defaults_to_week,
    persist_menu_item,
    persist_service_state,
    persist_week_header,
)
from cafeteria.workflow_snapshot import build_snapshot
from cafeteria.workflow_store import load_draft_connection
from tests.test_workflow_partial_store_db import (
    WEEK,
    WorkflowDatabase,
    _full_values,
    _payload,
    _save_schedule,
    _scope,
    _service_payload,
    _service_row,
    workflow_database as workflow_database,
)


def _switch(db: WorkflowDatabase, enabled: bool) -> None:
    with db.owner.begin() as connection:
        connection.execute(text(
            "UPDATE cafeteria.offer_profiles SET allows_weekend=:enabled WHERE code='staff_guest'"
        ), {'enabled': enabled})


def _draft(db: WorkflowDatabase, profile: str = 'staff_guest') -> dict:
    with db.app.connect() as connection:
        return load_draft_connection(connection, profile, WEEK)


def _staff_values(day_count: int = 5) -> dict:
    values = _full_values('Wochenangebot')
    days = values['days']
    assert isinstance(days, list)
    values['days'] = days[:day_count]
    for day in days:
        day['services'] = day['services'][:1]
        for option in day['services'][0]['options']:
            option.update(internal_rappen=950, external_rappen=1450)
    return values


def _import(db: WorkflowDatabase, values: dict, expected: int) -> int:
    return import_draft(db.app, 'staff_guest', WEEK, expected_row_version=expected,
                        actor_id=db.actor_id, values=values)


def test_schedule_apply_fills_only_missing_slots_and_wholly_unset_open_times(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db)
    for offset, payload in enumerate([
        _service_payload(notice='Eigener Hinweis'),
        _service_payload(start='10:00'),
        _service_payload(state='closed', notice='Eigene Schliessung'),
    ]):
        persist_service_state(db.app, scope, WEEK, (WEEK + timedelta(days=offset)).isoformat(),
                              'LUNCH', payload, 0)
    persist_menu_item(db.app, scope, WEEK, WEEK.isoformat(), 'LUNCH', 'MENU_1', _payload(), 0)
    before = _draft(db, 'patient')
    option = deepcopy(before['days'][0]['services'][0]['options'][0])
    _save_schedule(db, 'patient', {
        str(day): {'LUNCH': {'state': 'open', 'start': '11:30', 'end': '13:30', 'notice': ''}}
        for day in range(1, 8)
    })
    version = apply_schedule_defaults_to_week(
        db.app, scope, WEEK, expected_week_row_version=before['row_version'])
    after = _draft(db, 'patient')
    assert version == before['row_version'] + 1 == after['row_version']
    assert after['days'][0]['services'][0]['options'][0] == option
    assert _service_row(db, '2026-08-31', 'LUNCH') == ('open', 'Eigener Hinweis', '11:30', '13:30')
    assert _service_row(db, '2026-09-01', 'LUNCH') == ('open', '', '10:00', None)
    assert _service_row(db, '2026-09-02', 'LUNCH') == ('closed', 'Eigene Schliessung', None, None)
    assert _service_row(db, '2026-09-03', 'LUNCH') == ('open', '', '11:30', '13:30')
    with db.app.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one() == 14
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 1
    with pytest.raises(PartialWorkflowConflictError):
        apply_schedule_defaults_to_week(db.app, scope, WEEK,
                                       expected_week_row_version=before['row_version'])
    assert _draft(db, 'patient') == after


def test_new_week_uses_seven_slots_but_saved_week_requires_explicit_apply(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    _import(db, _staff_values(), 0)
    before = _draft(db)
    _switch(db, True)
    assert _draft(db)['days'] == before['days']
    version = _import(db, _staff_values(), before['row_version'])
    before_apply = _draft(db)
    assert len(before_apply['days']) == 5
    version = apply_schedule_defaults_to_week(
        db.app, _scope(db, 'staff_guest'), WEEK, expected_week_row_version=version)
    after = _draft(db)
    assert after['row_version'] == version
    assert len(after['days']) == 7
    assert all(not option['title'] for day in after['days'][5:]
               for service in day['services'] for option in service['options'])
    assert after['days'][:5] == before_apply['days']


def test_new_week_header_synthesizes_seven_days_without_get_writes(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    _switch(db, True)
    persist_week_header(db.app, _scope(db, 'staff_guest'), WEEK,
                        {'title': 'Neue Woche', 'shared_note': ''}, 0)
    assert len(_draft(db)['days']) == 7
    with db.app.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one() == 0
    _import(db, _staff_values(), _draft(db)['row_version'])
    assert len(_draft(db)['days']) == 7


@pytest.mark.parametrize('day_count', [6, 7])
def test_saved_weekends_survive_full_replace_and_csv_with_switch_off(
    workflow_database: WorkflowDatabase, day_count: int,
) -> None:
    db = workflow_database
    _switch(db, True)
    values = _staff_values(day_count)
    for day in values['days']:
        day['services'][0].update(service_start='11:15', service_end='13:45')
    _import(db, values, 0)
    before = _draft(db)
    snapshot = build_snapshot('staff_guest', before, 'OPS-R1')
    frozen = deepcopy(snapshot)
    _switch(db, False)
    assert _draft(db)['days'] == before['days']
    # A five-day replacement has no authority to delete omitted saved weekends.
    _import(db, _staff_values(), before['row_version'])
    current = _draft(db)
    assert current['days'][5:] == before['days'][5:]
    assert all(service['service_start'] == '11:15' for day in current['days']
               for service in day['services'])
    upload = validate_upload(io.BytesIO(snapshot_to_csv(snapshot)))
    assert upload['valid'] is True, upload['issues']
    csv_values = upload['values']
    assert isinstance(csv_values, dict)
    _import(db, csv_values, current['row_version'])
    after = _draft(db)
    assert len(after['days']) == len(before['days'])
    for old_day, new_day in zip(before['days'], after['days'], strict=True):
        old, new = old_day['services'][0], new_day['services'][0]
        assert (new['service_start'], new['service_end']) == ('11:15', '13:45')
        assert [o['title'] for o in new['options']] == [o['title'] for o in old['options']]
    assert snapshot == frozen
    assert snapshot['schema_version'] == 2
    assert snapshot['days'][5]['services'][0]['options'][0]['title'] == 'Wochenangebot Gericht'


def test_weekend_import_does_not_enable_profile_or_leave_partial_rows(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    with pytest.raises(StaleDraftError, match='Wochenende'):
        _import(db, _staff_values(7), 0)
    with db.app.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == 0
        assert connection.execute(text(
            "SELECT allows_weekend FROM cafeteria.offer_profiles WHERE code='staff_guest'"
        )).scalar_one() is False


def test_partial_writes_invalidate_week_cas_and_preserve_disabled_weekend(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db, 'staff_guest')
    _switch(db, True)
    persist_service_state(db.app, scope, WEEK, '2026-09-05', 'LUNCH',
                          _service_payload(start='10:00'), 0)
    before = _draft(db)
    _switch(db, False)
    persist_menu_item(db.app, scope, WEEK, '2026-09-05', 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    after_item = _draft(db)
    assert after_item['row_version'] == before['row_version'] + 1
    with pytest.raises(PartialWorkflowConflictError):
        apply_schedule_defaults_to_week(db.app, scope, WEEK,
                                       expected_week_row_version=before['row_version'])
    persist_service_state(db.app, scope, WEEK, '2026-09-05', 'LUNCH',
                          _service_payload(start='10:30'), 1)
    assert _draft(db)['row_version'] == after_item['row_version'] + 1
    with pytest.raises(PartialWorkflowValidationError, match='Wochenende'):
        persist_menu_item(db.app, scope, WEEK, '2026-09-06', 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    before_apply = _draft(db)
    apply_schedule_defaults_to_week(db.app, scope, WEEK,
                                   expected_week_row_version=before_apply['row_version'])
    assert _draft(db)['days'][5:] == before_apply['days'][5:]


def test_patient_snapshot_and_full_replace_preserve_times_without_prices(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    persist_service_state(db.app, _scope(db), WEEK, WEEK.isoformat(), 'LUNCH',
                          _service_payload(start='11:30', end='13:00'), 0)
    before = _draft(db, 'patient')
    import_draft(db.app, 'patient', WEEK, expected_row_version=before['row_version'],
                 actor_id=db.actor_id, values=_full_values('Patient'))
    after = _draft(db, 'patient')
    snapshot = build_snapshot('patient', after, 'PAT-2026-KW36-R1')
    assert snapshot['days'][0]['services'][0]['service_start'] == '11:30'
    assert len(snapshot['days']) == 7
    assert sum(len(s['options']) for d in snapshot['days'] for s in d['services']) == 28
    assert all('prices' not in o for d in snapshot['days'] for s in d['services'] for o in s['options'])
    assert _draft_values(after)['days'][0]['services'][0]['service_end'] == '13:00'


def test_copy_keeps_service_times_and_enabled_weekends(workflow_database: WorkflowDatabase) -> None:
    db = workflow_database
    _switch(db, True)
    values = _staff_values(7)
    for day in values['days']:
        day['services'][0].update(service_start='11:15', service_end='13:45')
    _import(db, values, 0)
    source = _draft(db)
    target_week = WEEK + timedelta(days=7)
    assert copy_previous_week(db.app, _scope(db, 'staff_guest'), target_week, 0) == 1
    with db.app.connect() as connection:
        target = load_draft_connection(connection, 'staff_guest', target_week)
    assert len(target['days']) == 7
    for old, new in zip(source['days'], target['days'], strict=True):
        assert old['services'][0]['service_start'] == new['services'][0]['service_start'] == '11:15'
        assert old['services'][0]['service_end'] == new['services'][0]['service_end'] == '13:45'
        assert [o['title'] for o in new['services'][0]['options']] == [
            o['title'] for o in old['services'][0]['options']]
    assert _draft(db) == source
