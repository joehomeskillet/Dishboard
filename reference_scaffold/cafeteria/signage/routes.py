from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from ..public.routes import effective_today, service
from ..db import active_snapshot

bp = Blueprint('signage', __name__)


def context(profile_code: str) -> dict:
    if request.args:
        return {'error': 'Player-URLs akzeptieren keine Query-Parameter.'}
    date_value = effective_today().isoformat()
    snapshot = active_snapshot(
        current_app.extensions['cafeteria_db'],
        profile_code,
        date_value,
        last_good_dir=current_app.config['LAST_GOOD_DIR'],
    )
    day = next((item for item in (snapshot or {}).get('days', []) if item.get('date') == date_value), None)
    return {'snapshot': snapshot, 'day': day, 'today': date_value, 'error': None}


def signage_response(template: str, **values):
    if values.get('error'):
        response = render_template('signage/unavailable.html', message=values['error'])
        return response, 400, {'Cache-Control': 'no-store'}
    response = render_template(template, **values)
    headers = {'Cache-Control': 'public, max-age=60, stale-if-error=86400'}
    snapshot = values.get('snapshot')
    if snapshot:
        headers['X-Snapshot-Revision'] = snapshot.get('revision_id', '')
    return response, 200, headers


@bp.get('/signage/cafeteria/tag')
def cafeteria_day():
    values = context('staff_guest')
    values['lunch'] = service(values.get('day'), 'LUNCH')
    template = 'signage/cafeteria_day.html' if values.get('lunch') else 'signage/cafeteria_closed.html'
    return signage_response(template, **values)


@bp.get('/signage/cafeteria/woche')
def cafeteria_week():
    values = context('staff_guest')
    values['open_days'] = [day for day in (values.get('snapshot') or {}).get('days', []) if day.get('services')]
    return signage_response('signage/cafeteria_week.html', **values)


@bp.get('/signage/patienten/tag')
def patient_day():
    values = context('patient')
    values['lunch'] = service(values.get('day'), 'LUNCH')
    values['dinner'] = service(values.get('day'), 'DINNER')
    return signage_response('signage/patient_day.html', **values)


@bp.get('/signage/patienten/woche')
def patient_week():
    return signage_response('signage/patient_week.html', **context('patient'))
