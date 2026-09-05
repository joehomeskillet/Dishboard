"""Navigation to existing public screens and saved menu output."""
from __future__ import annotations

from flask import Response, abort, make_response, render_template, request

from ..roles import require_capability
from .rendering import _template_context
from .workflow_routes import _week_arg, bp


@bp.get('/screens')
@require_capability('draft.read')
def screens() -> Response:
    if request.args:
        abort(400, description='Die Screen-Übersicht benötigt keine URL-Parameter.')
    response = make_response(render_template(
        'admin/screens.html', family='cafeteria', profile='staff_guest',
        **_template_context(),
    ))
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/vorlagen')
@require_capability('draft.read')
def vorlagen() -> Response:
    if set(request.args) - {'week'}:
        abort(400, description='Für Vorlagen ist nur die Woche erlaubt.')
    response = make_response(render_template(
        'admin/vorlagen.html', family='cafeteria', profile='staff_guest',
        week=_week_arg().isoformat(), **_template_context(),
    ))
    response.headers['Cache-Control'] = 'no-store'
    return response
