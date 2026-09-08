from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask
from .food_symbols import food_legend, food_symbol
from .menu_images import menu_image

MONTHS = {
    1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni',
    7: 'Juli', 8: 'August', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember',
}
WEEKDAYS = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def date_long(value: str) -> str:
    parsed = _date(value)
    return f'{parsed.day}. {MONTHS[parsed.month]} {parsed.year}'


def date_short(value: str) -> str:
    parsed = _date(value)
    return f'{parsed.day}. {MONTHS[parsed.month]}'


def datetime_short(value: dt.datetime | str | None) -> str:
    if isinstance(value, str):
        try:
            value = dt.datetime.fromisoformat(value)
        except ValueError:
            return 'Noch nicht erfasst'
        if value.tzinfo is None:
            return 'Noch nicht erfasst'
    return value.astimezone(ZoneInfo('Europe/Zurich')).strftime('%d.%m.%Y %H:%M') if value else 'Noch nicht erfasst'


def chf(value: int) -> str:
    return f'{int(value) / 100:.2f}'


def iso_week(value: str) -> int:
    return _date(value).isocalendar().week


# The only place these fixed texts exist. They keep publications that predate the
# area/time keys ('area_name' missing) looking exactly as they do today.
LEGACY_PATIENT_MEAL_TIMES = {
    'LUNCH': 'Ausgabe ab 11:30 Uhr',
    'DINNER': 'Ausgabe ab 17:30 Uhr',
}


def service_is_open(service: Mapping[str, Any]) -> bool:
    return str(service.get('service_state') or 'open') == 'open'


def service_time_label(service: Mapping[str, Any], profile_code: str) -> str:
    """Serving time of one snapshot service, empty when it carries no time.

    Both times give 'Ausgabe 11:30–12:30 Uhr' (patient) or 'Mittag 11:30–13:30 Uhr'
    (staff_guest); a lone start gives 'ab 11:30 Uhr', a lone end 'bis 12:30 Uhr'.
    Closed services never show a time.
    """
    if not service_is_open(service):
        return ''
    start = str(service.get('service_start') or '')
    end = str(service.get('service_end') or '')
    prefix = 'Ausgabe' if profile_code == 'patient' else 'Mittag'
    if start and end:
        return f'{prefix} {start}–{end} Uhr'
    if start:
        return f'{prefix} ab {start} Uhr'
    if end:
        return f'{prefix} bis {end} Uhr'
    return ''


def patient_day_time_label(service: Mapping[str, Any], area_name: object = '') -> str:
    """Time line of the patient day views, including the pre-OPS fixed texts.

    Snapshots without 'area_name' predate the area and time keys, so they keep the
    fixed texts they show today. Newer snapshots show their own times or nothing.
    """
    label = service_time_label(service, 'patient')
    if label or area_name or not service_is_open(service):
        return label
    return LEGACY_PATIENT_MEAL_TIMES.get(str(service.get('meal_code') or ''), '')


def _weekday(day: Mapping[str, Any]) -> int:
    return _date(str(day.get('date') or '')).isoweekday()


def cafeteria_visible_days(days: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Cafeteria days an output shows: weekdays with a service, weekends only when open."""
    visible = []
    for day in days:
        services = day.get('services') or []
        if not services:
            continue
        if _weekday(day) > 5 and not any(service_is_open(service) for service in services):
            continue
        visible.append(day)
    return visible


def weekday_range_label(days: Sequence[Mapping[str, Any]]) -> str:
    """Name the shown weekdays: a run from Monday reads 'Montag bis Samstag'."""
    numbers = sorted({_weekday(day) for day in days})
    if not numbers:
        return ''
    names = [WEEKDAYS[number - 1] for number in numbers]
    if len(names) == 1:
        return names[0]
    if numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f'{names[0]} bis {names[-1]}'
    return f'{", ".join(names[:-1])} und {names[-1]}'


def register_template_filters(app: Flask) -> None:
    app.add_template_filter(food_symbol, 'food_symbol')
    app.add_template_filter(food_legend, 'food_legend')
    app.add_template_filter(menu_image, 'menu_image')
    app.add_template_filter(date_long, 'date_long')
    app.add_template_filter(date_short, 'date_short')
    app.add_template_filter(datetime_short, 'datetime_short')
    app.add_template_filter(chf, 'chf')
    app.add_template_filter(iso_week, 'iso_week')
    app.add_template_filter(service_time_label, 'service_time_label')
    app.add_template_filter(patient_day_time_label, 'patient_day_time_label')
    app.add_template_filter(weekday_range_label, 'weekday_range_label')
