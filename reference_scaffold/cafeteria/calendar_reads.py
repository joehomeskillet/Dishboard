"""Kitchen calendar range reader: one service_date query, Zurich today."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, text

ZURICH = ZoneInfo('Europe/Zurich')

_SERVICES = """
    SELECT p.code AS profile_code, s.service_date, mp.code AS meal_code,
           s.service_state, COALESCE(s.notice, '') AS notice, s.row_version,
           to_char(s.service_start, 'HH24:MI') AS service_start,
           to_char(s.service_end, 'HH24:MI') AS service_end,
           w.week_start, w.workflow_state, w.public_id AS week_public_id,
           coalesce(items.menus, '[]'::jsonb) AS menus
    FROM cafeteria.menu_services s
    JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
    JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
    JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
    LEFT JOIN LATERAL (
        SELECT jsonb_agg(jsonb_build_object('title', i.title, 'type_code', mt.code)
                         ORDER BY mt.sort_order, i.sort_order) AS menus
        FROM cafeteria.menu_items i
        JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
        WHERE i.service_id=s.id
    ) items ON true
    WHERE w.location_id=:location_id AND s.service_date BETWEEN :start AND :end
    ORDER BY s.service_date, p.code, mp.sort_order
"""


def effective_today(*, now: datetime | None = None) -> date:
    """Calendar-today, period bounds and price as-of share this Zurich clock."""
    instant = now if now is not None else datetime.now(ZURICH)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=ZURICH)
    return instant.astimezone(ZURICH).date()


def list_calendar_range(
    engine: Engine, location_id: int, date_from: date, date_to: date,
) -> tuple[dict[str, Any], ...]:
    """Menus and dated service rows for [date_from, date_to] in one query."""
    if date_to < date_from:
        raise ValueError('date_to liegt vor date_from')
    with engine.connect() as connection:
        rows = connection.execute(text(_SERVICES), {
            'location_id': location_id, 'start': date_from, 'end': date_to,
        }).mappings().all()
    return tuple({
        'profile_code': row['profile_code'],
        'service_date': row['service_date'],
        'meal_code': row['meal_code'],
        'service_state': row['service_state'],
        'notice': row['notice'],
        'row_version': row['row_version'],
        'service_start': row['service_start'],
        'service_end': row['service_end'],
        'week_start': row['week_start'],
        'workflow_state': row['workflow_state'],
        'week_public_id': str(row['week_public_id']),
        'menus': _menus(row['menus']),
    } for row in rows)


def _menus(raw: object) -> tuple[dict[str, str], ...]:
    if raw in (None, '', b''):
        payload: object = []
    elif isinstance(raw, (bytes, bytearray)):
        payload = json.loads(raw)
    elif isinstance(raw, str):
        payload = json.loads(raw)
    else:
        payload = raw
    if not isinstance(payload, list):
        return ()
    items = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or '').strip()
        if not title:
            continue
        items.append({'title': title, 'type_code': str(item.get('type_code') or 'MENU_1')})
    return tuple(items)
