"""Month grid for the kitchen calendar; no JavaScript calendar library."""
from __future__ import annotations

from calendar import Calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable, Mapping

_DEFAULT_PROFILES = ('patient', 'staff_guest')
_ISO_CALENDAR = Calendar(firstweekday=0)
_PROFILE_LABELS = {'patient': 'Patienten', 'staff_guest': 'Cafeteria'}
_PROFILE_ORDER = ('staff_guest', 'patient')
_MEAL_LABELS = {'LUNCH': 'Mittagessen', 'DINNER': 'Abendessen'}
_STATE_LABELS = {
    'open': '',
    'closed': 'Geschlossen',
    'holiday': 'Feiertag',
    'company_holiday': 'Betriebsferien',
}
_FAMILY = {'patient': 'patienten', 'staff_guest': 'cafeteria'}
_WEEKDAY_SHORT = ('Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So')
_WEEKDAY_LONG = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')
_MONTH_NAMES = (
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
)
_VISIBLE = 3


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


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _label(mapping: Mapping[str, str], code: str) -> str:
    text = mapping.get(code)
    if text:
        return text
    cleaned = code.replace('_', ' ').strip()
    return cleaned[:1].upper() + cleaned[1:].lower() if cleaned else code


def _menus(row: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    raw = row.get('menus') or ()
    result = []
    for item in raw:
        title = str(item.get('title') or '').strip()
        if not title:
            continue
        result.append({'title': title, 'type_code': str(item.get('type_code') or 'MENU_1')})
    return tuple(result)


def present_month(
    weeks: list[list[dict[str, Any]]], today: date, *, extra_limit: int = _VISIBLE,
) -> list[list[dict[str, Any]]]:
    """German labels, today flag, grouped meals and overflow for the month grid."""
    presented = []
    for week in weeks:
        row = []
        for cell in week:
            day = cell['date']
            grouped: dict[str, dict[str, dict[str, Any]]] = {}
            for service in cell.get('services') or ():
                profile = str(service['profile_code'])
                meal = str(service['meal_code'])
                profile_bucket = grouped.setdefault(profile, {})
                entry = profile_bucket.get(meal)
                if entry is None:
                    week_start = service.get('week_start') or _week_start(day)
                    if not isinstance(week_start, date):
                        week_start = date.fromisoformat(str(week_start))
                    entry = {
                        'meal_code': meal,
                        'meal_label': _label(_MEAL_LABELS, meal),
                        'state': str(service.get('service_state') or 'open'),
                        'state_label': _STATE_LABELS.get(str(service.get('service_state') or ''), ''),
                        'notice': str(service.get('notice') or ''),
                        'week_start': week_start,
                        'week_public_id': str(service.get('week_public_id') or ''),
                        'items': [],
                    }
                    profile_bucket[meal] = entry
                entry['items'].extend(_menus(service))
            groups = []
            for profile in _PROFILE_ORDER:
                meals = grouped.get(profile)
                if not meals:
                    continue
                ordered = []
                for meal_code in ('LUNCH', 'DINNER'):
                    if meal_code not in meals:
                        continue
                    slot = meals[meal_code]
                    items = tuple(slot['items'])
                    slot['visible'] = items[:extra_limit]
                    slot['extra'] = items[extra_limit:]
                    ordered.append(slot)
                for meal_code, slot in meals.items():
                    if meal_code in ('LUNCH', 'DINNER'):
                        continue
                    items = tuple(slot['items'])
                    slot['visible'] = items[:extra_limit]
                    slot['extra'] = items[extra_limit:]
                    ordered.append(slot)
                groups.append({
                    'profile_code': profile,
                    'profile_label': _label(_PROFILE_LABELS, profile),
                    'family': _FAMILY.get(profile, 'cafeteria'),
                    'meals': ordered,
                })
            row.append({
                **cell,
                'is_today': day == today,
                'iso': day.isoformat(),
                'weekday_short': _WEEKDAY_SHORT[day.weekday()],
                'weekday_long': _WEEKDAY_LONG[day.weekday()],
                'list_label': (
                    f'{_WEEKDAY_SHORT[day.weekday()]}, {day.day}. {_MONTH_NAMES[day.month - 1]}'
                ),
                'plan_week_start': _week_start(day),
                'groups': groups,
            })
        presented.append(row)
    return presented
