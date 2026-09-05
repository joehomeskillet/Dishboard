from __future__ import annotations

import datetime as dt

from flask import Flask
from .menu_images import menu_image

MONTHS = {
    1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni',
    7: 'Juli', 8: 'August', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember',
}


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def date_long(value: str) -> str:
    parsed = _date(value)
    return f'{parsed.day}. {MONTHS[parsed.month]} {parsed.year}'


def date_short(value: str) -> str:
    parsed = _date(value)
    return f'{parsed.day}. {MONTHS[parsed.month]}'


def chf(value: int) -> str:
    return f'{int(value) / 100:.2f}'


def iso_week(value: str) -> int:
    return _date(value).isocalendar().week


def register_template_filters(app: Flask) -> None:
    app.add_template_filter(menu_image, 'menu_image')
    app.add_template_filter(date_long, 'date_long')
    app.add_template_filter(date_short, 'date_short')
    app.add_template_filter(chf, 'chf')
    app.add_template_filter(iso_week, 'iso_week')
