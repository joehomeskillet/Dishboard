"""Kitchen event create/edit routes. draft.write. Does not touch menu_weeks."""
from __future__ import annotations

from datetime import date, time
from typing import Any

from flask import current_app, g, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..calendar_event_store import (
    CalendarEventActorDeniedError, CalendarEventConflictError, CalendarEventError,
    CalendarEventNotFoundError, CalendarEventValidationError, EventScope,
    create_event, get_event, update_event,
)
from ..calendar_reads import effective_today
from ..component_catalog_store import ComponentCatalogConfigurationError
from ..recipe_reads import get_location
from ..roles import require_capability
from .routes import bp

_SCOPES = ('both', 'staff_guest', 'patient')
_SCOPE_LABELS = {'both': 'Beide', 'staff_guest': 'Cafeteria', 'patient': 'Patienten'}


def _db():
    return current_app.extensions['cafeteria_db']


def _scope() -> EventScope:
    location = get_location(_db())
    return EventScope(g.auth_user.user_id, location, g.auth_user.authz_version)


def _parse_time(raw: str) -> time | None:
    text = (raw or '').strip()
    if not text:
        return None
    return time.fromisoformat(text)


def _values() -> dict[str, Any]:
    today = effective_today()
    return {
        'event_date': request.form.get('event_date') or today.isoformat(),
        'starts_at': request.form.get('starts_at') or '',
        'ends_at': request.form.get('ends_at') or '',
        'profile_scope': request.form.get('profile_scope') or 'both',
        'title': request.form.get('title') or '',
        'guest_count': request.form.get('guest_count') or '0',
        'note': request.form.get('note') or '',
        'row_version': request.form.get('row_version') or '',
    }


@bp.get('/kuechenkalender/anlass')
@require_capability('draft.write')
def kitchen_event_new() -> Response:
    today = effective_today()
    preset = request.args.get('date') or today.isoformat()
    values = {
        'event_date': preset, 'starts_at': '', 'ends_at': '', 'profile_scope': 'both',
        'title': '', 'guest_count': '0', 'note': '', 'row_version': '',
    }
    html = render_template(
        'admin/kuechenkalender_anlass.html', family='cafeteria', profile='staff_guest',
        values=values, event=None, scope_labels=_SCOPE_LABELS, scopes=_SCOPES, field_errors={},
    )
    return html


@bp.post('/kuechenkalender/anlass')
@require_capability('draft.write')
def kitchen_event_create() -> Response:
    values = _values()
    try:
        create_event(
            _db(), _scope(),
            event_date=date.fromisoformat(values['event_date']),
            title=values['title'], profile_scope=values['profile_scope'],
            guest_count=int(values['guest_count'] or 0),
            note=values['note'] or None,
            starts_at=_parse_time(values['starts_at']),
            ends_at=_parse_time(values['ends_at']),
        )
    except (CalendarEventValidationError, ValueError) as error:
        field = getattr(error, 'field', None) or 'title'
        html = render_template(
            'admin/kuechenkalender_anlass.html', family='cafeteria', profile='staff_guest',
            values=values, event=None, scope_labels=_SCOPE_LABELS, scopes=_SCOPES,
            field_errors={field: str(error)},
        )
        return html, 400
    except CalendarEventActorDeniedError:
        return ('', 403)
    except (CalendarEventError, ComponentCatalogConfigurationError):
        return ('', 503)
    day = date.fromisoformat(values['event_date'])
    return redirect(url_for('admin.kitchen_calendar', year=day.year, month=day.month), 303)


@bp.get('/kuechenkalender/anlass/<public_id>')
@require_capability('draft.read')
def kitchen_event_edit(public_id: str) -> Response:
    try:
        event = get_event(_db(), get_location(_db()), public_id)
    except CalendarEventNotFoundError:
        return ('', 404)
    except ComponentCatalogConfigurationError:
        return ('', 503)
    values = {
        'event_date': event['event_date'].isoformat() if hasattr(event['event_date'], 'isoformat') else str(event['event_date']),
        'starts_at': event['starts_at'].strftime('%H:%M') if event['starts_at'] else '',
        'ends_at': event['ends_at'].strftime('%H:%M') if event['ends_at'] else '',
        'profile_scope': event['profile_scope'],
        'title': event['title'],
        'guest_count': str(event['guest_count']),
        'note': event['note'] or '',
        'row_version': str(event['row_version']),
    }
    return render_template(
        'admin/kuechenkalender_anlass.html', family='cafeteria', profile='staff_guest',
        values=values, event=event, scope_labels=_SCOPE_LABELS, scopes=_SCOPES, field_errors={},
    )


@bp.post('/kuechenkalender/anlass/<public_id>')
@require_capability('draft.write')
def kitchen_event_save(public_id: str) -> Response:
    values = _values()
    try:
        update_event(
            _db(), _scope(), public_id,
            expected_row_version=int(values['row_version'] or 0),
            title=values['title'], profile_scope=values['profile_scope'],
            guest_count=int(values['guest_count'] or 0), note=values['note'] or None,
            event_date=date.fromisoformat(values['event_date']),
            starts_at=_parse_time(values['starts_at']), ends_at=_parse_time(values['ends_at']),
        )
    except CalendarEventConflictError:
        html = render_template(
            'admin/kuechenkalender_anlass.html', family='cafeteria', profile='staff_guest',
            values=values, event={'public_id': public_id}, scope_labels=_SCOPE_LABELS, scopes=_SCOPES,
            field_errors={'title': 'Der Anlass wurde zwischenzeitlich geändert.'},
        )
        return html, 409
    except (CalendarEventValidationError, ValueError) as error:
        field = getattr(error, 'field', None) or 'title'
        html = render_template(
            'admin/kuechenkalender_anlass.html', family='cafeteria', profile='staff_guest',
            values=values, event={'public_id': public_id}, scope_labels=_SCOPE_LABELS, scopes=_SCOPES,
            field_errors={field: str(error)},
        )
        return html, 400
    except CalendarEventNotFoundError:
        return ('', 404)
    day = date.fromisoformat(values['event_date'])
    return redirect(url_for('admin.kitchen_calendar', year=day.year, month=day.month), 303)
