"""Kitchen calendar admin route: month jump, prev/next, draft.read."""
from __future__ import annotations

from datetime import date

from flask import current_app, make_response, render_template, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.wrappers import Response

from ..calendar_month import annotate_month, month_weeks, present_month
from ..calendar_reads import effective_today, list_calendar_range
from ..component_catalog_store import ComponentCatalogConfigurationError
from ..recipe_reads import get_location
from ..roles import capabilities, require_capability
from .routes import bp

_MONTH_NAMES = (
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    value = year * 12 + (month - 1) + delta
    return value // 12, value % 12 + 1


def _parse_year_month(today: date) -> tuple[int, int]:
    jump = request.args.get('jump', default='', type=str) or ''
    if jump:
        try:
            jumped = date.fromisoformat(jump + '-01') if len(jump) == 7 else date.fromisoformat(jump)
            if 2000 <= jumped.year <= 2100:
                return jumped.year, jumped.month
        except ValueError:
            pass
    year = request.args.get('year', default=today.year, type=int)
    month = request.args.get('month', default=today.month, type=int)
    if year is None or month is None or not 1 <= month <= 12 or not 2000 <= year <= 2100:
        return today.year, today.month
    return year, month


@bp.get('/kuechenkalender')
@require_capability('draft.read')
def kitchen_calendar() -> Response:
    today = effective_today()
    year, month = _parse_year_month(today)
    profiles = request.args.get('profiles', 'both')
    if profiles == 'patient':
        allowed: tuple[str, ...] = ('patient',)
    elif profiles == 'cafeteria':
        allowed = ('staff_guest',)
    else:
        allowed = ('patient', 'staff_guest')
        profiles = 'both'
    grid = month_weeks(year, month)
    date_from, date_to = grid[0][0], grid[-1][-1]
    prev_year, prev_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, 1)
    services: tuple[dict, ...] = ()
    status = 200
    try:
        engine = current_app.extensions['cafeteria_db']
        location = get_location(engine)
        services = list_calendar_range(engine, location, date_from, date_to)
    except (ComponentCatalogConfigurationError, SQLAlchemyError, KeyError, TypeError):
        status = 503
    weeks = present_month(
        annotate_month(year, month, services, profiles=allowed), today,
    )
    allowed_caps = capabilities()
    can_write = '*' in allowed_caps or 'draft.write' in allowed_caps
    plan_family = 'patienten' if profiles == 'patient' else 'cafeteria'
    html = render_template(
        'admin/kuechenkalender.html',
        family='cafeteria',
        profile='staff_guest',
        weeks=weeks,
        weekday_names=('Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'),
        month_label=f'{_MONTH_NAMES[month - 1]} {year}',
        year=year,
        month=month,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        profiles=profiles,
        jump_value=f'{year:04d}-{month:02d}',
        can_write=can_write,
        plan_family=plan_family,
    )
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response
