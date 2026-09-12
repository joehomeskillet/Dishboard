"""Versioned operations forms, with a database boundary outside authorization."""
from __future__ import annotations

import datetime as dt
import hmac
import re
import unicodedata
from zoneinfo import ZoneInfo

from flask import abort, current_app, flash, g, make_response, redirect, render_template, request, url_for
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from ..component_catalog_store import AdminScope
from ..operations_settings import (
    PROFILE_SLOTS, OperationsConflictError, get_schedule_connection, normalise_time,
    save_area_name, save_schedule, save_weekend_switch,
)
from ..operations_store import list_service_exceptions, load_dated_service
from ..patient_payload import patient_text_is_forbidden
from ..public.routes import effective_today
from ..roles import require_capability
from ..security import csrf_token
from ..workflow import WorkflowValidationError
from ..workflow_partial_form import parse_service_form
from ..workflow_partial_store import (
    PartialWorkflowConflictError, PartialWorkflowNotFoundError, PartialWorkflowValidationError,
    apply_schedule_defaults_to_week, persist_service_state,
)
from .rendering import DAY_NAMES, MEAL_LABELS, _template_context
from .workflow_routes import (
    FAMILIES, _csrf_digest, _db, _exact, _scope, _scoped_csrf, _validate_scoped_csrf, _version_field, bp,
    profile_from_endpoint,
)

PARTS = ('state', 'start', 'end', 'notice')
STATES = {'open': 'Offen', 'closed': 'Geschlossen', 'holiday': 'Feiertag', 'company_holiday': 'Betriebsferien'}


def _profile() -> str:
    profile = request.form.get('profile', '')
    if profile not in PROFILE_SLOTS:
        abort(400, description='Bereich ist ungültig.')
    return profile


def _date(value: str) -> dt.date:
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is None:
        raise ValueError('Bitte ein gültiges Datum wählen.')
    return dt.date.fromisoformat(value)


def _redirect() -> Response:
    return redirect(url_for('admin.operations_settings'), 303)


def _render(status: int = 200, *, values: dict[str, str] | None = None,
            errors: dict[str, str] | None = None, preview: bool = False) -> Response:
    values, errors = values or {}, errors or {}
    scope = _scope('staff_guest')
    location_id = scope.location_id
    with _db().connect() as connection:
        timezone = str(connection.execute(text('SELECT timezone FROM cafeteria.locations WHERE id=:id'),
                                          {'id': location_id}).scalar_one())
        today = (effective_today() if current_app.config.get('DEMO_MODE')
                 else dt.datetime.now(ZoneInfo(timezone)).date())
        schedules = {profile: get_schedule_connection(connection, location_id, profile)
                     for profile in PROFILE_SLOTS}
        exceptions = list_service_exceptions(connection, location_id, today - dt.timedelta(days=7),
                                            today + dt.timedelta(days=56), schedules)
    return make_response(render_template(
        'admin/operations.html', family='cafeteria', profile='staff_guest', csrf=csrf_token(),
        values=values, errors=errors, preview=preview, schedules=schedules, exceptions=exceptions,
        timezone=timezone, today=today, day_names=DAY_NAMES, meal_labels=MEAL_LABELS,
        schedule_csrf={profile: _scoped_csrf(
            profile, 'operations_schedule', scope,
        ) for profile in PROFILE_SLOTS},
        operations_csrf={profile: {action: _scoped_csrf(
            profile, f'operations_{action}', scope,
        ) for action in ('save_name', 'save_weekend', 'load_exception', 'save_exception')}
            for profile in PROFILE_SLOTS},
        state_labels=STATES, families={v: k for k, v in FAMILIES.items()}, **_template_context(),
    ), status)


def _save_name(profile: str) -> Response:
    _validate_scoped_csrf(profile, {'operations_save_name'})
    field = f'name_{profile}'
    _exact({'_csrf', 'action', field, f'expected_{profile}'})
    try:
        save_area_name(_db(), g.auth_user.user_id, g.auth_user.authz_version, profile,
                       request.form[f'expected_{profile}'], request.form[field])
    except OperationsConflictError as error:
        return _render(409, errors={field: str(error)})
    except ValueError as error:
        return _render(400, values=request.form.to_dict(), errors={field: str(error)})
    flash('Anzeigename gespeichert.')
    return _redirect()


def _save_weekend() -> Response:
    _validate_scoped_csrf('staff_guest', {'operations_save_weekend'})
    required = {'_csrf', 'action', 'expected_allows_weekend'}
    _exact(required | ({'allows_weekend'} if 'allows_weekend' in request.form else set()))
    expected = request.form['expected_allows_weekend']
    if expected not in {'0', '1'} or request.form.get('allows_weekend', 'on') != 'on':
        abort(400, description='Wochenendschalter ist ungültig.')
    try:
        save_weekend_switch(_db(), g.auth_user.user_id, g.auth_user.authz_version,
                            'staff_guest', expected == '1', 'allows_weekend' in request.form)
    except OperationsConflictError as error:
        return _render(409, errors={'allows_weekend': str(error)})
    flash('Wochenendbetrieb gespeichert.')
    return _redirect()


def _schedule_errors(profile: str, slots: dict[str, dict[str, dict[str, str]]]) -> dict[str, str]:
    errors = {}
    for day, meal in PROFILE_SLOTS[profile]:
        rule = slots[str(day)][meal]
        prefix = f'{profile}-slot_{day}_{meal}_'
        if rule['state'] not in {'open', 'closed'}:
            errors[prefix + 'state'] = 'Bitte Offen oder Geschlossen wählen.'
        for part in ('start', 'end'):
            try:
                normalise_time(rule[part])
            except ValueError as error:
                errors[prefix + part] = str(error)
        if (rule['start'] and rule['end'] and rule['end'] <= rule['start']
                and prefix + 'start' not in errors and prefix + 'end' not in errors):
            errors[prefix + 'end'] = 'Das Serviceende muss nach dem Servicebeginn liegen.'
        notice = rule['notice']
        if (len(notice) > 200 or any(unicodedata.category(c).startswith('C') for c in notice)
                or (rule['state'] == 'closed' and not notice.strip())
                or (profile == 'patient' and patient_text_is_forbidden(notice))):
            errors[prefix + 'notice'] = 'Bitte einen gültigen Hinweis mit höchstens 200 Zeichen eingeben.'
    return errors


def _save_schedule() -> Response:
    profile = _profile()
    scope = _validate_scoped_csrf(profile, {'operations_schedule'})
    fields = {f'slot_{day}_{meal}_{part}' for day, meal in PROFILE_SLOTS[profile] for part in PARTS}
    _exact({'_csrf', 'action', 'profile', 'revision', *fields})
    slots = {str(day): {meal: {part: request.form[f'slot_{day}_{meal}_{part}'] for part in PARTS}
                       for other_day, meal in PROFILE_SLOTS[profile] if other_day == day}
             for day, _ in PROFILE_SLOTS[profile]}
    errors = _schedule_errors(profile, slots)
    if errors:
        return _render(400, values=request.form.to_dict(), errors=errors)
    try:
        save_schedule(_db(), g.auth_user.user_id, g.auth_user.authz_version,
                      scope.location_id, profile, _version_field('revision'), slots)
    except OperationsConflictError as error:
        return _render(409, errors={f'{profile}-slot_1_LUNCH_state': str(error)})
    flash('Wochenvorgaben gespeichert.')
    return _redirect()


def _exception_signature(values: dict[str, str], scope: AdminScope) -> str:
    profile = values['profile']
    purpose = f"exception:{values['date']}:{values['meal']}:{values['row_version']}"
    return _csrf_digest(scope, profile, purpose, csrf_token())


def _load_exception() -> Response:
    _exact({'_csrf', 'action', 'profile', 'date', 'meal'})
    values = request.form.to_dict()
    profile = _profile()
    scope = _validate_scoped_csrf(profile, {'operations_load_exception'})
    try:
        service_date = _date(values['date'])
    except ValueError:
        return _render(400, values=values, errors={'date': 'Bitte ein gültiges Datum wählen.'})
    if (service_date.isoweekday(), values['meal']) not in PROFILE_SLOTS[profile]:
        return _render(400, values=values, errors={'meal': 'Diese Mahlzeit gibt es in diesem Bereich nicht.'})
    with _db().connect() as connection:
        schedule = get_schedule_connection(connection, scope.location_id, profile)
        values = load_dated_service(connection, scope.location_id, profile, service_date, values['meal'], schedule)
    if (profile == 'staff_guest' and service_date.isoweekday() > 5
            and not schedule.allows_weekend and values['row_version'] == '0'):
        return _render(400, values=values, errors={'date': 'Bitte zuerst den Wochenendbetrieb aktivieren.'})
    values['loaded'] = _exception_signature(values, scope)
    return _render(values=values, preview=True)


def _save_exception() -> Response:
    _exact({'_csrf', 'action', 'profile', 'date', 'meal', 'row_version', 'loaded',
            'service_state', 'notice', 'service_start', 'service_end'})
    values = request.form.to_dict()
    profile = _profile()
    scope = _validate_scoped_csrf(profile, {'operations_save_exception'})
    if (re.fullmatch(r'[0-9a-f]{64}', values['loaded']) is None
            or not hmac.compare_digest(values['loaded'], _exception_signature(values, scope))):
        return _render(409, errors={'date': 'Bitte den Service erneut laden; die ursprüngliche Ansicht passt nicht mehr.'})
    try:
        service_date = _date(values['date'])
        week = service_date - dt.timedelta(days=service_date.weekday())
        form = {key: values[key] for key in ('_csrf', 'meal', 'row_version', 'service_state',
                                            'notice', 'service_start', 'service_end')}
        parsed = parse_service_form(profile, {**form, 'day': values['date'], 'week': week.isoformat()})
        notice = values['notice']
        if (len(notice) > 200 or any(unicodedata.category(c).startswith('C') for c in notice)
                or (profile == 'patient' and patient_text_is_forbidden(notice))):
            raise WorkflowValidationError('Bitte einen gültigen Hinweis eingeben.', field_name='notice')
        persist_service_state(_db(), scope, parsed.week_start, parsed.day, parsed.meal,
                              parsed.payload, parsed.expected_service_row_version)
    except WorkflowValidationError as error:
        return _render(400, values=values, errors={error.field_name or 'notice': str(error)}, preview=True)
    except (PartialWorkflowConflictError, PartialWorkflowNotFoundError) as error:
        return _render(409, errors={'date': f'{error} Bitte den Service erneut laden.'})
    except PartialWorkflowValidationError as error:
        return _render(400, values=values, errors={'notice': str(error)}, preview=True)
    flash('Ausnahme gespeichert.')
    return _redirect()


@require_capability('settings.write')
def _authorized_operations() -> Response:
    if request.args:
        abort(400, description='Bereiche & Zeiten benötigt keine URL-Parameter.')
    if request.method == 'GET':
        return _render()
    action = request.form.get('action')
    if action in {'save_name_patient', 'save_name_staff_guest'}:
        return _save_name(action.removeprefix('save_name_'))
    actions = {'save_weekend': _save_weekend, 'save_schedule': _save_schedule,
               'load_exception': _load_exception, 'save_exception': _save_exception}
    if action not in actions:
        abort(400, description='Aktion ist ungültig.')
    return actions[action]()


@require_capability('draft.write')
def _authorized_defaults(family: str) -> Response:
    if request.args:
        abort(400)
    profile = profile_from_endpoint(family)
    scope = _validate_scoped_csrf(profile, {'schedule_defaults'})
    _exact({'_csrf', 'week', 'row_version'})
    try:
        week = _date(request.form['week'])
        apply_schedule_defaults_to_week(_db(), scope, week,
                                       expected_week_row_version=_version_field('row_version'))
    except (PartialWorkflowConflictError, PartialWorkflowNotFoundError) as error:
        abort(409, description=str(error))
    except (ValueError, PartialWorkflowValidationError) as error:
        abort(400, description=str(error))
    flash('Wochenvorgaben übernommen.')
    return redirect(url_for(f'admin.{family}', week=week.isoformat()), 303)


@bp.route('/bereiche-zeiten', methods=['GET', 'POST'])
@bp.post('/<any(cafeteria, patienten):family>/wochenvorgaben', endpoint='schedule_defaults')
def operations_settings(family: str | None = None) -> Response:
    # Includes authorization and all context processors. Never render through a failed DB.
    try:
        response = _authorized_defaults(family) if family else _authorized_operations()
    except PermissionError:
        response = make_response('Aktuelle Berechtigung erforderlich.', 403)
    except HTTPException as error:
        response = error.get_response()
    except SQLAlchemyError:
        response = make_response('Bereiche & Zeiten ist vorübergehend nicht verfügbar. Bitte erneut versuchen.', 503)
    response.headers['Cache-Control'] = 'no-store'
    return response
