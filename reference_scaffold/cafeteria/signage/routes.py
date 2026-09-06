from __future__ import annotations

from flask import Blueprint, render_template, request

from ..public.routes import effective_today, published_snapshot, service
from ..template_filters import cafeteria_visible_days, service_is_open, weekday_range_label

bp = Blueprint('signage', __name__)


def no_store_failure(message: str, status_code: int):
    response = render_template('signage/unavailable.html', message=message)
    return response, status_code, {'Cache-Control': 'no-store'}


@bp.before_request
def reject_query_parameters():
    if request.query_string or request.args:
        return no_store_failure('Player-URLs akzeptieren keine Query-Parameter.', 400)
    return None


def context(profile_code: str) -> dict:
    date_value = effective_today().isoformat()
    snapshot = published_snapshot(profile_code)
    day = next((item for item in (snapshot or {}).get('days', []) if item.get('date') == date_value), None)
    return {
        'snapshot': snapshot, 'day': day, 'today': date_value, 'error': None,
        'area_name': (snapshot or {}).get('area_name', ''),
    }


def cafeteria_context() -> dict:
    """Cafeteria players name the days they show, weekends only when a service is open."""
    values = context('staff_guest')
    values['open_days'] = cafeteria_visible_days((values.get('snapshot') or {}).get('days', []))
    values['weekday_range'] = weekday_range_label(values['open_days'])
    return values


def signage_response(template: str, **values):
    if values.get('error'):
        return no_store_failure(values['error'], 400)
    if not values.get('snapshot'):
        return no_store_failure('Kein publizierter Menüplan für diesen Player.', 404)
    response = render_template(template, **values)
    headers = {'Cache-Control': 'public, max-age=60, stale-if-error=86400'}
    snapshot = values.get('snapshot')
    if snapshot:
        headers['X-Snapshot-Revision'] = snapshot.get('revision_id', '')
    return response, 200, headers


@bp.get('/signage/cafeteria/tag')
def cafeteria_day():
    values = cafeteria_context()
    lunch = service(values.get('day'), 'LUNCH')
    values['lunch'] = lunch
    # A weekend player only shows menus for an open service; otherwise it stays a closed board.
    shows_menus = bool(lunch) and (
        service_is_open(lunch) if effective_today().isoweekday() > 5 else True
    )
    template = 'signage/cafeteria_day.html' if shows_menus else 'signage/cafeteria_closed.html'
    return signage_response(template, **values)


@bp.get('/signage/cafeteria/woche')
def cafeteria_week():
    return signage_response('signage/cafeteria_week.html', **cafeteria_context())


@bp.get('/signage/patienten/tag')
def patient_day():
    values = context('patient')
    values['lunch'] = service(values.get('day'), 'LUNCH')
    values['dinner'] = service(values.get('day'), 'DINNER')
    return signage_response('signage/patient_day.html', **values)


@bp.get('/signage/patienten/woche')
def patient_week():
    return signage_response('signage/patient_week.html', **context('patient'))
