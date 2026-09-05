from __future__ import annotations

from datetime import timedelta

from flask import abort, render_template
from sqlalchemy.exc import NoResultFound

from ..component_catalog_store import ComponentCatalogConfigurationError
from ..roles import require_capability
from ..workflow_store import load_draft_connection
from .rendering import DAY_NAMES, MONTHS
from .workflow_routes import _db, _reject_override, _scope, _week_arg, bp, profile_from_endpoint


@bp.get('/<any(cafeteria, patienten):family>/preview/print')
@require_capability('preview.read')
def print_week(family: str) -> str:
    profile = profile_from_endpoint(family)
    _reject_override()
    week = _week_arg()
    _scope(profile)
    try:
        with _db().connect() as connection:
            draft = load_draft_connection(connection, profile, week)
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    except NoResultFound:
        abort(404)
    if draft['workflow_state'] not in {'draft', 'ready', 'published', 'archived'}:
        abort(404)
    end = week + timedelta(days=4 if profile == 'staff_guest' else 6)
    start_label = f'{week.day:02d}.'
    if week.month != end.month or week.year != end.year:
        start_label += f' {MONTHS[week.month - 1]} {week.year}'
    date_label = f'{start_label} bis {end.day:02d}. {MONTHS[end.month - 1]} {end.year}'
    price_pairs = set()
    if profile == 'staff_guest':
        price_pairs = {
            (option.get('internal_rappen'), option.get('external_rappen'))
            for day in draft['days'] for service in day['services']
            if service['service_state'] == 'open'
            for option in service['options'] if option['title']
        }
    common_prices = next(iter(price_pairs)) if len(price_pairs) == 1 else None
    return render_template(
        'admin/print_week.html', draft=draft, profile=profile, family=family,
        week=week, date_label=date_label, day_names=DAY_NAMES,
        meals=('LUNCH',) if profile == 'staff_guest' else ('LUNCH', 'DINNER'),
        common_prices=common_prices,
    )
