"""Read-only views of dated services; all writes use workflow_partial_store."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import Connection, text

from .operations_settings import OperationsSchedule, slot_defaults

_SERVICES = """
    SELECT p.code AS profile_code, s.service_date, mp.code AS meal_code,
           s.service_state, COALESCE(s.notice, '') AS notice, s.row_version,
           to_char(s.service_start, 'HH24:MI') AS service_start,
           to_char(s.service_end, 'HH24:MI') AS service_end,
           w.week_start, w.workflow_state
    FROM cafeteria.menu_services s
    JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
    JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
    JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
    WHERE w.location_id=:location_id AND s.service_date BETWEEN :start AND :end
    ORDER BY s.service_date, p.code, mp.sort_order
"""


def list_service_exceptions(
    connection: Connection, location_id: int, start: date, end: date,
    schedules: Mapping[str, OperationsSchedule],
) -> list[dict[str, Any]]:
    exceptions = []
    for row in connection.execute(text(_SERVICES), {
        'location_id': location_id, 'start': start, 'end': end,
    }).mappings():
        rule = slot_defaults(schedules[row['profile_code']], row['service_date'], row['meal_code'])
        if row['service_state'] != 'open':
            kind = 'closure'
        elif rule.state != 'open':
            kind = 'open'
        elif (row['service_start'], row['service_end']) != (rule.start, rule.end):
            kind = 'time'
        else:
            continue
        exceptions.append({**row, 'kind': kind})
    return exceptions


def load_dated_service(
    connection: Connection, location_id: int, profile: str, service_date: date, meal: str,
    schedule: OperationsSchedule,
) -> dict[str, str]:
    """Return the original visible version, including zero for a not-yet-saved slot."""
    rows = connection.execute(text(_SERVICES), {
        'location_id': location_id, 'start': service_date, 'end': service_date,
    }).mappings()
    row = next((row for row in rows if row['profile_code'] == profile and row['meal_code'] == meal), None)
    rule = slot_defaults(schedule, service_date, meal)
    return {
        'profile': profile, 'date': service_date.isoformat(), 'meal': meal,
        'row_version': str(row['row_version']) if row else '0',
        'service_state': str(row['service_state']) if row else rule.state,
        'notice': str(row['notice']) if row else rule.notice,
        'service_start': (row['service_start'] if row else rule.start) or '',
        'service_end': (row['service_end'] if row else rule.end) or '',
    }
