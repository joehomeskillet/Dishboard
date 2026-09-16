"""Month grid for the kitchen calendar; no JavaScript calendar library."""
from __future__ import annotations

from calendar import Calendar
from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Mapping

_DEFAULT_PROFILES = ('patient', 'staff_guest')
_ISO_CALENDAR = Calendar(firstweekday=0)


def month_weeks(year: int, month: int) -> list[list[date]]:
    """Monday-first ISO weeks covering the month, including adjacent-month days."""
    return [list(week) for week in _ISO_CALENDAR.monthdatescalendar(year, month)]


def annotate_month(
    year: int, month: int, services: Iterable[Mapping[str, Any]],
    *, profiles: Iterable[str] = _DEFAULT_PROFILES,
) -> list[list[dict[str, Any]]]:
    allowed = frozenset(profiles)
    by_date: dict[date, list[Mapping[str, Any]]] = defaultdict(list)
    for row in services:
        profile = str(row['profile_code'])
        if profile not in allowed:
            continue
        day = row['service_date']
        if not isinstance(day, date):
            day = date.fromisoformat(str(day))
        by_date[day].append(row)
    return [
        [
            {
                'date': day,
                'in_month': day.month == month,
                'services': tuple(by_date.get(day, ())),
            }
            for day in week
        ]
        for week in month_weeks(year, month)
    ]
