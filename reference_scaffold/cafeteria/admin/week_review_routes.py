from __future__ import annotations

from flask import abort, flash, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..roles import capabilities, require_capability
from ..workflow_review_context import get_week_review, review_week_context
from .rendering import _template_context
from .workflow_routes import (
    _call, _db, _exact, _monday, _reject_override, _scope, _scoped_csrf,
    _validate_scoped_csrf, bp, profile_from_endpoint,
)


@bp.get('/<any(cafeteria, patienten):family>/wochen/pruefung')
@require_capability('draft.read')
def week_review_get(family: str) -> Response:
    profile = profile_from_endpoint(family)
    _reject_override()
    if set(request.args) != {'week'} or len(request.args.getlist('week')) != 1:
        abort(400, description='Genau eine gespeicherte Woche auswählen.')
    week = _monday(request.args['week'])
    scope = _scope(profile)
    review = _call(lambda: get_week_review(_db(), scope, week))
    allowed = capabilities()
    response = make_response(render_template(
        'admin/week_review.html', family=family, profile=profile, week=week.isoformat(),
        review=review, can_write='*' in allowed or 'draft.write' in allowed,
        csrf=_scoped_csrf(profile, 'week-review', scope),
        service_labels={'open': 'Geöffnet', 'closed': 'Geschlossen', 'holiday': 'Feiertag',
                        'company_holiday': 'Betriebsferien'},
        **_template_context(),
    ))
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.post('/<any(cafeteria, patienten):family>/wochen/pruefung')
@require_capability('draft.write')
def week_review_post(family: str) -> Response:
    profile = profile_from_endpoint(family)
    _reject_override()
    if request.args:
        abort(400, description='Formularparameter gehören in das Formular.')
    _exact({'_csrf', 'week', 'context_version'})
    scope = _validate_scoped_csrf(profile, {'week-review'})
    week = _monday(request.form['week'])
    try:
        _call(lambda: review_week_context(_db(), scope, week, request.form['context_version']))
    except ValueError as error:
        abort(400, description=str(error))
    flash('Wochenkopf und Servicehinweise sind für diesen gespeicherten Stand geprüft.')
    response = redirect(url_for('admin.week_review_get', family=family, week=week.isoformat()), 303)
    response.headers['Cache-Control'] = 'no-store'
    return response
