from __future__ import annotations

from flask import Response, abort
from sqlalchemy.exc import NoResultFound

from ..component_catalog_store import ComponentCatalogConfigurationError
from ..roles import require_capability
from ..workflow_store import load_draft_connection
from .week_pdf import WeekPdfFitError, render_week_pdf
from .workflow_routes import _db, _reject_override, _scope, _week_arg, bp, profile_from_endpoint


@bp.get('/<any(cafeteria, patienten):family>/preview/print')
@require_capability('preview.read')
def print_week(family: str) -> Response:
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
    try:
        document = render_week_pdf(draft, profile, week)
    except WeekPdfFitError as error:
        abort(422, description=str(error))
    return Response(
        document, mimetype='application/pdf', headers={
            'Content-Disposition': f'inline; filename="wochenplan-{family}-{week.isoformat()}.pdf"',
            'Cache-Control': 'no-store',
        },
    )
