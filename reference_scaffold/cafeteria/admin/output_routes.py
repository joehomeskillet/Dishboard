"""Navigation to existing public screens and saved menu output."""
from __future__ import annotations

from flask import Response, abort, make_response, render_template, request

from ..roles import require_capability
from ..print_templates import PrintTemplateStateError, read_templates, template_revision
from ..screen_templates import choices, read_assignment
from .screen_template_routes import database_available
from .rendering import _template_context
from .workflow_routes import _db, _week_arg, bp


@bp.get('/screens')
@database_available
@require_capability('draft.read')
def screens() -> Response:
    if request.args:
        abort(400, description='Die Screen-Übersicht benötigt keine URL-Parameter.')
    with _db().connect() as connection:
        assignments = {profile: read_assignment(connection, profile) for profile in ('staff_guest', 'patient')}
    response = make_response(render_template(
        'admin/screens.html', family='cafeteria', profile='staff_guest',
        assignments=assignments,
        **_template_context(),
    ))
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/vorlagen')
@database_available
@require_capability('draft.read')
def vorlagen() -> Response:
    if set(request.args) - {'week'}:
        abort(400, description='Für Vorlagen ist nur die Woche erlaubt.')
    week = _week_arg().isoformat()
    catalogs = {}
    error = None
    with _db().connect() as connection:
        screen_catalogs = {family: {'active': read_assignment(connection, profile), 'choices': choices(profile)}
                           for family, profile in [('cafeteria', 'staff_guest'), ('patienten', 'patient')]}
    try:
        with _db().connect() as connection:
            for family, profile in [('cafeteria', 'staff_guest'), ('patienten', 'patient')]:
                document = read_templates(connection, profile)
                catalogs[family] = {
                    'document': document,
                    'active': template_revision(document, document['active_template'], document['active_revision']),
                }
    except PrintTemplateStateError as exc:
        error = str(exc)
    response = make_response(render_template(
        'admin/vorlagen.html', family='cafeteria', profile='staff_guest',
        week=week, catalogs=catalogs, catalog_error=error, **_template_context(),
        screen_catalogs=screen_catalogs,
    ), 503 if error else 200)
    response.headers['Cache-Control'] = 'no-store'
    return response
