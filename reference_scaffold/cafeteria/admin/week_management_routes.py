from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from flask import abort, redirect, render_template, request, url_for
from sqlalchemy import Engine, text
from werkzeug.wrappers import Response

from ..component_catalog_store import (
    AdminScope, ComponentCatalogConfigurationError,
    resolve_single_active_location_connection,
)
from ..public.routes import effective_today
from ..roles import capabilities, require_capability
from ..workflow import WorkflowValidationError, derive_admin_status
from ..workflow_partial_form import parse_week_header_form
from ..workflow_partial_store import (
    PartialWorkflowConflictError, PartialWorkflowValidationError, persist_week_header,
)
from .rendering import STATUS_LABELS, _template_context
from .workflow_routes import (
    _STORE_ERRORS, _abort_store, _call, _db, _reject_override, _scope, _scoped_csrf, _validate_scoped_csrf,
    bp, profile_from_endpoint,
)

PAGE_SIZE = 12


def find_weeks(engine: Engine, scope: AdminScope, page: int = 1) -> tuple[list[dict[str, Any]], bool]:
    if not 1 <= page <= 10000:
        raise ValueError('Ungültige Seitennummer.')
    with engine.connect() as connection:
        # Keep the active location stable while the existing status helper reads it.
        connection.execute(text('SELECT id FROM cafeteria.locations WHERE id=:id FOR SHARE'), {'id': scope.location_id})
        if resolve_single_active_location_connection(connection) != scope.location_id:
            raise ComponentCatalogConfigurationError('Der aktive Standort wurde geändert.')
        result = connection.execute(text('''
            SELECT w.id, w.week_start, w.title, w.workflow_state
            FROM cafeteria.menu_weeks w
            JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            WHERE w.location_id=:location_id AND p.code=:profile_code
            ORDER BY w.week_start DESC, w.id DESC LIMIT :limit OFFSET :offset
        '''), {
            'location_id': scope.location_id, 'profile_code': scope.profile_code,
            'limit': PAGE_SIZE + 1, 'offset': (page - 1) * PAGE_SIZE,
        }).mappings().all()
        rows = [dict(row) for row in result[:PAGE_SIZE]]
        # Bounded to twelve existing weeks; reuse the publication/review status contract.
        for row in rows:
            row['status'] = derive_admin_status(engine, scope.profile_code, row['week_start'])
            row['next_week'] = row['week_start'] + timedelta(days=7) if row['week_start'] <= date.max - timedelta(days=7) else None
    return rows, len(result) > PAGE_SIZE


def _render_weeks(
    family: str, profile: str, scope: AdminScope, page: int = 1,
    values: dict[str, str] | None = None, error: str | None = None,
) -> str:
    rows, has_next = _call(lambda: find_weeks(_db(), scope, page))
    today = effective_today()
    next_monday = today + timedelta(days=7 - today.weekday())
    allowed = capabilities()
    return render_template(
        'admin/week_management.html', family=family, profile=profile,
        rows=rows, page=page, has_next=has_next, status_labels=STATUS_LABELS,
        can_write='*' in allowed or 'draft.write' in allowed,
        can_preview='*' in allowed or 'preview.read' in allowed,
        csrf=_scoped_csrf(profile, 'week-create', scope), error=error,
        values=values if values is not None else {
            'week': next_monday.isoformat(), 'title': 'Wochenplan', 'shared_note': '',
        }, **_template_context(),
    )


@bp.get('/<any(cafeteria, patienten):family>/wochen')
@require_capability('draft.read')
def week_management(family: str) -> str:
    profile = profile_from_endpoint(family)
    _reject_override()
    raw_page = request.args.get('page', '1')
    if (set(request.args) - {'page'} or len(request.args.getlist('page')) > 1
            or re.fullmatch(r'[1-9][0-9]{0,4}', raw_page) is None or int(raw_page) > 10000):
        abort(400, description='Seitennummer ist ungültig.')
    return _render_weeks(family, profile, _scope(profile), int(raw_page))


@bp.post('/<any(cafeteria, patienten):family>/wochen')
@require_capability('draft.write')
def week_create(family: str) -> Response | tuple[str, int]:
    profile = profile_from_endpoint(family)
    _reject_override()
    if request.args:
        abort(400, description='Formularparameter gehören in das Formular.')
    scope = _validate_scoped_csrf(profile, {'week-create'})
    values = {key: request.form.get(key, '') for key in ('week', 'title', 'shared_note')}
    try:
        parsed = parse_week_header_form(profile, request.form)
        if parsed.expected_week_row_version != 0:
            raise WorkflowValidationError('Hier können nur neue Wochen angelegt werden.')
        persist_week_header(_db(), scope, parsed.week_start, parsed.payload, 0)
    except (WorkflowValidationError, PartialWorkflowValidationError) as error:
        return _render_weeks(family, profile, scope, values=values, error=str(error)), 400
    except PartialWorkflowConflictError as error:
        return _render_weeks(family, profile, scope, values=values, error=str(error)), 409
    except _STORE_ERRORS as error:
        _abort_store(error)
    return redirect(url_for('admin.' + family, week=parsed.week_start.isoformat()), 303)
