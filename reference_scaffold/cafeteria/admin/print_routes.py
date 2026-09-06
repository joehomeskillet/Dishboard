from __future__ import annotations

from flask import Response, abort
from sqlalchemy.exc import NoResultFound

from ..component_catalog_store import ComponentCatalogConfigurationError
from ..branding import BrandingStateError
from ..print_branding import load_pdf_branding
from ..roles import require_capability
from ..print_templates import PrintTemplateStateError, active_template
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
            config, revision = active_template(connection, profile)
            branding = load_pdf_branding(connection, profile, config)
    except (ComponentCatalogConfigurationError, PrintTemplateStateError, BrandingStateError) as error:
        abort(503, description=str(error))
    except NoResultFound:
        abort(404)
    if draft['workflow_state'] not in {'draft', 'ready', 'published', 'archived'}:
        abort(404)
    try:
        document = render_week_pdf(draft, profile, week, config, branding=branding)
    except WeekPdfFitError as error:
        abort(422, description=str(error))
    return Response(
        document, mimetype='application/pdf', headers={
            'Content-Disposition': f'inline; filename="wochenplan-{family}-{week.isoformat()}.pdf"',
            'Cache-Control': 'no-store',
            'X-Print-Template-Revision': revision,
            **({'X-Brand-Revision': str(branding.revision_id)} if branding else {}),
        },
    )
