from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date, timedelta
from html import escape
from typing import Literal, cast

from flask import (
    abort, current_app, flash, get_flashed_messages, make_response, redirect,
    render_template, request, url_for,
)
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from ..component_assignment_store import (
    ComponentAssignmentConflictError,
    ComponentAssignmentValidationError,
    resolve_component_effects,
)
from ..component_catalog_store import (
    AdminScope, ComponentCatalogConfigurationError, ComponentCatalogValidationError,
    ComponentConflictError, ComponentNotFoundError, StaleComponentError, archive_component,
    create_component, find_components, get_component, resolve_single_active_location_connection,
    unarchive_component, update_component,
)
from ..component_catalog_metadata import AllergenInput
from ..public.routes import effective_today
from ..roles import require_capability
from ..security import csrf_token, validate_csrf
from ..workflow import (
    MENU_TYPES, PROFILE_DAYS, PROFILE_MEALS, AutoOriginConflictError,
    PublicationConfigurationError, StaleDraftError, StaleItemError, WorkflowValidationError,
    derive_admin_status, get_component_review_token, publish_draft_scoped as publish_draft, review_component,
)
from ..workflow_copy_store import copy_previous_week
from ..workflow_partial_form import (
    parse_component_archive_form, parse_component_create_form, parse_component_unarchive_form,
    parse_component_update_form, parse_menu_item_form, parse_service_form, parse_week_header_form)
from ..workflow_partial_store import (
    PartialWorkflowConflictError, PartialWorkflowNotFoundError, PartialWorkflowValidationError,
    persist_menu_item, persist_service_state, persist_week_header, resolve_item_id, resolve_week_ref)
from ..workflow_store import load_draft_connection
from ..workflow_review import _review_open_connection
from .rendering import (
    CATEGORY_LABELS, render_admin_preview, render_admin_week,
    menu_form_values, render_component_detail, render_components, render_menu_editor)
from .routes import _actor_id, bp

FAMILIES = {'cafeteria': 'staff_guest', 'patienten': 'patient'}
ORIGIN_CONFLICT = 'Herkunftskonflikt: Komponente bearbeiten oder Herkunft dieses Menüs auf manuell stellen.'
REVIEW_HINT = 'Betroffene Gerichte müssen erneut geprüft werden.'
_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')
_SLOT_404 = {'Tag liegt ausserhalb des Menürasters.', 'Mahlzeit ist für dieses Profil ungültig.', 'Menüoption ist ungültig.'}
_STORE_ERRORS = (
    WorkflowValidationError, ComponentCatalogValidationError, ComponentCatalogConfigurationError,
    ComponentConflictError, ComponentNotFoundError, StaleComponentError, ComponentAssignmentValidationError,
    ComponentAssignmentConflictError, PartialWorkflowValidationError, PartialWorkflowNotFoundError,
    PartialWorkflowConflictError, StaleDraftError, StaleItemError, PublicationConfigurationError, NoResultFound,
)
_MENU_VALIDATION_ERRORS = (
    WorkflowValidationError,
    ComponentCatalogValidationError,
    PartialWorkflowValidationError,
    ComponentAssignmentValidationError,
)
_MENU_CONFLICT_ERRORS = (
    StaleComponentError,
    ComponentConflictError,
    ComponentAssignmentConflictError,
    PartialWorkflowConflictError,
    StaleDraftError,
    StaleItemError,
)
_MENU_VALUE_FIELDS = (
    'title', 'description', 'note', 'allergen_mode', 'origin_mode', 'label_mode',
    'internal_chf', 'external_chf',
)
_MENU_LIST_FIELDS = (
    'component_public_id', 'component_text', 'allergen_code', 'allergen_presence',
    'origin_ingredient', 'origin_country_code', 'label_code',
)
def profile_from_endpoint(endpoint: str) -> str:
    profile = FAMILIES.get(endpoint)
    if profile is None:
        raise ValueError('Unbekannte URL-Familie.')
    return profile

def _reject_override() -> None:
    form = request.form if request.method in {'POST', 'PUT', 'PATCH'} else {}
    if 'profile' in request.args or 'profile_scope' in request.args or 'profile' in form or 'profile_scope' in form:
        abort(400, description='Profil kommt nur aus der URL.')

def _monday(raw: str | None) -> date:
    if raw is None or _ISO.fullmatch(raw) is None:
        abort(400, description='Woche muss YYYY-MM-DD sein.')
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        abort(400, description='Woche ist ungültig.')
    if parsed.isoweekday() != 1:
        abort(400, description='Woche muss an einem Montag beginnen.')
    return parsed

def _week_arg() -> date:
    values = request.args.getlist('week')
    if not values:
        today = effective_today()
        return today - timedelta(days=today.isoweekday() - 1)
    if len(values) != 1:
        abort(400, description='Woche ist ungültig.')
    return _monday(values[0])

def _raster(profile: str, week: date, day: str, meal: str, option: str | None) -> date:
    if _ISO.fullmatch(day) is None:
        abort(400, description='Tag muss YYYY-MM-DD sein.')
    try:
        service_day = date.fromisoformat(day)
    except ValueError:
        abort(400, description='Tag ist ungültig.')
    if (service_day - week).days not in range(PROFILE_DAYS[profile]):
        abort(404)
    if meal not in PROFILE_MEALS[profile] or (option is not None and option not in MENU_TYPES):
        abort(404)
    return service_day

def _scope(profile: str) -> AdminScope:
    try:
        with current_app.extensions['cafeteria_db'].connect() as connection:
            location_id = resolve_single_active_location_connection(connection)
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    return AdminScope(_actor_id(), location_id, cast(Literal['patient', 'staff_guest'], profile))

def _page(body: str, status: int = 200):
    return make_response(f'<!doctype html><html lang="de"><body>{body}</body></html>', status)

def _hidden(name: str, value: object) -> str:
    return f'<input type="hidden" name="{escape(name)}" value="{escape(str(value))}">'

def _abort_store(error: BaseException) -> None:
    if isinstance(error, (ComponentCatalogConfigurationError, PublicationConfigurationError)):
        abort(503, description=str(error))
    if isinstance(error, WorkflowValidationError) and str(error) in _SLOT_404:
        abort(404)
    if isinstance(error, (ComponentNotFoundError, PartialWorkflowNotFoundError, NoResultFound)):
        abort(404)
    if isinstance(error, (StaleComponentError, ComponentConflictError, ComponentAssignmentConflictError,
                          PartialWorkflowConflictError, StaleDraftError, StaleItemError)):
        abort(409, description=str(error))
    if isinstance(error, (WorkflowValidationError, ComponentCatalogValidationError,
                          PartialWorkflowValidationError, ComponentAssignmentValidationError)):
        abort(400, description=str(error))
    raise error

def _call(action):
    try:
        return action()
    except AutoOriginConflictError:
        raise
    except _STORE_ERRORS as error:
        _abort_store(error)

def _exact(required: set[str]) -> None:
    if set(request.form.keys()) != required:
        abort(400, description='Formularfelder sind ungültig.')
    for key in required:
        if len(request.form.getlist(key)) != 1:
            abort(400, description=f'Formularfeld mehrfach gesendet: {key}')

def _version_field(name: str) -> int:
    raw = request.form[name]
    if re.fullmatch(r'\d{1,19}', raw) is None:
        abort(400, description='Versionsnummer muss eine nichtnegative ganze Zahl sein.')
    value = int(raw, 10)
    if value > 2**63 - 1:
        abort(400, description='Versionsnummer ist zu gross.')
    return value

def _db():
    return current_app.extensions['cafeteria_db']

def _csrf_digest(scope: AdminScope, profile: str, purpose: str, raw: str) -> str:
    secret = current_app.secret_key
    if not isinstance(secret, (str, bytes)) or not secret:
        abort(503, description='Formularsignatur ist nicht konfiguriert.')
    key = secret.encode('utf-8') if isinstance(secret, str) else secret
    binding = f'dishboard-admin-v1\0{raw}\0{scope.actor_id}\0{profile}\0{purpose}\0{scope.location_id}'
    return hmac.new(key, binding.encode(), hashlib.sha256).hexdigest()

def _scoped_csrf(profile: str, purpose: str, scope: AdminScope) -> str:
    raw = csrf_token()
    return f'{raw}.{purpose}.{_csrf_digest(scope, profile, purpose, raw)}'

def _validate_scoped_csrf(profile: str, purposes: set[str]) -> AdminScope:
    candidate = request.form.get('_csrf', '')
    try:
        raw, purpose, digest = candidate.rsplit('.', 2)
    except ValueError:
        abort(400, description='CSRF-Prüfung fehlgeschlagen.')
    validate_csrf(raw)
    if purpose not in purposes:
        abort(400, description='Formularzweck ist ungültig.')
    scope = _scope(profile)
    if not hmac.compare_digest(digest, _csrf_digest(scope, profile, purpose, raw)):
        abort(409, description='Der aktive Standort wurde zwischenzeitlich geändert.')
    return scope

def _flash() -> list[str]:
    return get_flashed_messages()

def _load_item(scope: AdminScope, week: date, day: str, meal: str, option: str):
    with _db().connect() as connection:
        week_ref = resolve_week_ref(connection, scope, week)
        item_id = resolve_item_id(connection, scope, week_ref, day, meal, option)
        row = connection.execute(
            text('SELECT row_version, title FROM cafeteria.menu_items WHERE id=:id'),
            {'id': item_id},
        ).mappings().one()
    return item_id, int(row['row_version']), str(row['title'])


def _load_draft_option(
    profile: str,
    week: date,
    day: str,
    meal: str,
    option_code: str,
) -> dict[str, object]:
    with _db().connect() as connection:
        draft = load_draft_connection(connection, profile, week)
    return next(
        option
        for day_row in draft['days'] if day_row['date'] == day
        for service in day_row['services'] if service['meal_code'] == meal
        for option in service['options'] if option['type_code'] == option_code
    )


def _master_choices() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    with _db().connect() as connection:
        allergens = [
            dict(row)
            for row in connection.execute(text(
                'SELECT code, display_name AS name, eu_number '
                'FROM cafeteria.allergens WHERE active ORDER BY eu_number, code'
            )).mappings()
        ]
        labels = [
            dict(row)
            for row in connection.execute(text(
                'SELECT code, display_name AS name '
                'FROM cafeteria.dietary_labels WHERE active ORDER BY code'
            )).mappings()
        ]
    return allergens, labels


def _catalog_choices(
    scope: AdminScope,
    assignments: list[dict[str, object]],
) -> list[dict[str, object]]:
    choices = _call(lambda: find_components(_db(), scope, '', None, False))
    visible_ids = {str(choice['public_id']) for choice in choices}
    for assignment in assignments:
        public_id = str(assignment.get('component_public_id') or '')
        if not public_id or public_id in visible_ids:
            continue
        archived = _call(
            lambda public_id=public_id: get_component(
                _db(), scope, public_id, include_archived=True,
            )
        )
        choices.append({**archived, 'active': False})
        visible_ids.add(public_id)
    return choices


def _display_effects(effects: dict[str, object]) -> dict[str, list[str]]:
    rows = cast(dict[str, list[dict[str, object]]], effects)
    return {
        'labels': [str(row.get('name') or row.get('code') or '') for row in rows['labels']],
        'allergens': [
            ('Kann enthalten: ' if row.get('presence') == 'may_contain' else 'Enthält: ')
            + str(row.get('name') or row.get('code') or '') for row in rows['allergens']
        ],
        'origins': [str(row.get('text') or '') for row in rows['origins']],
    }


def _request_menu_values() -> dict[str, object]:
    values: dict[str, object] = {
        name: request.form.get(name, '') for name in _MENU_VALUE_FIELDS
        if name in request.form
    }
    for name in _MENU_LIST_FIELDS:
        request_name = name if name in request.form else f'{name}[]'
        values[name] = request.form.getlist(request_name)
    return values


def _menu_errors(error: BaseException) -> dict[str, str]:
    field_name = getattr(error, 'field_name', None)
    return {str(field_name or 'form'): str(error)}


def _render_menu_page(
    profile: str,
    family: str,
    scope: AdminScope,
    week: date,
    day: str,
    meal: str,
    option_code: str,
    *,
    form_values: dict[str, object] | None = None,
    form_errors: dict[str, str] | None = None,
    status: int = 200,
    force_origin_conflict: bool = False,
):
    version, title, item_id = 0, '', None
    option: dict[str, object] = {
        'title': '', 'description': '', 'note': '',
        'allergen_mode': 'manual', 'origin_mode': 'manual', 'label_mode': 'manual',
        'assignments': [], 'allergens': [], 'origins': [], 'labels': [],
    }
    if profile == 'staff_guest':
        option.update(internal_rappen='', external_rappen='')
    try:
        item_id, version, title = _load_item(scope, week, day, meal, option_code)
        option = _load_draft_option(profile, week, day, meal, option_code)
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    except (PartialWorkflowNotFoundError, NoResultFound):
        pass

    assignments = cast(list[dict[str, object]], option.get('assignments') or [])
    catalog_choices = _catalog_choices(scope, assignments)
    allergens, labels = _master_choices()
    review_token = None
    effects: dict[str, list[str]] = {'labels': [], 'allergens': [], 'origins': []}
    origin_conflict = ORIGIN_CONFLICT if force_origin_conflict else None
    if item_id is not None and origin_conflict is None:
        try:
            review_token = get_component_review_token(_db(), scope, item_id)
            effects = _display_effects(resolve_component_effects(_db(), scope, item_id))
        except AutoOriginConflictError:
            origin_conflict = ORIGIN_CONFLICT
        except _STORE_ERRORS as error:
            _abort_store(error)

    cell = {
        'day': day,
        'meal': meal,
        'option': option_code,
        'row_version': version,
        'title': title,
        'components': list(option.get('assignments') or []),
    }
    html = render_menu_editor(
        profile, family, week, cell,
        menu_form_values(profile, option) if form_values is None else form_values,
        form_errors or {}, _scoped_csrf(profile, 'menu', scope), review_token,
        catalog_choices, allergens, labels, effects, _flash(),
        origin_conflict=origin_conflict,
    )
    response_status = 409 if origin_conflict is not None and status == 200 else status
    return html if response_status == 200 else make_response(html, response_status)


def _menu_error_response(
    profile: str,
    family: str,
    scope: AdminScope,
    error: BaseException,
    status: int,
    *,
    keep_request_values: bool,
    origin_conflict: bool = False,
):
    week = _monday(request.form.get('week'))
    day = request.form.get('day', '')
    meal = request.form.get('meal', '')
    option = request.form.get('option', '')
    _raster(profile, week, day, meal, option)
    return _render_menu_page(
        profile, family, scope, week, day, meal, option,
        form_values=_request_menu_values() if keep_request_values else None,
        form_errors=_menu_errors(error), status=status,
        force_origin_conflict=origin_conflict,
    )

def _week_overview(profile: str):
    _reject_override()
    week = _week_arg()
    scope = _scope(profile)
    status = derive_admin_status(_db(), profile, week)
    draft = None
    versions: dict[tuple[str, str, str], int] = {}
    services: dict[tuple[str, str], dict[str, object]] = {}
    try:
        with _db().connect() as connection:
            draft = load_draft_connection(connection, profile, week)
            service_rows = connection.execute(text(
                'SELECT s.service_date::text AS day, mp.code AS meal, '
                's.row_version, s.service_state, s.notice FROM cafeteria.menu_services s '
                'JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id '
                'WHERE s.menu_week_id=:week_id'
            ), {'week_id': int(draft['id'])}).mappings()
            services = {(str(row['day']), str(row['meal'])): dict(row) for row in service_rows}
            rows = connection.execute(
                text(
                    'SELECT s.service_date::text AS day, mp.code AS meal, mt.code AS option, '
                    'i.id,i.row_version FROM cafeteria.menu_items i '
                    'JOIN cafeteria.menu_services s ON s.id=i.service_id '
                    'JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id '
                    'JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id '
                    'WHERE s.menu_week_id=:week_id'
                ),
                {'week_id': int(draft['id'])},
            ).all()
            versions = {(str(row.day), str(row.meal), str(row.option)): int(row.row_version) for row in rows}
            reviews = {
                (str(row.day), str(row.meal), str(row.option)): _review_open_connection(connection, int(row.id))
                for row in rows
            }
            for day in draft['days']:
                for service in day['services']:
                    for option in service['options']:
                        key = (str(day['date']), str(service['meal_code']), str(option['type_code']))
                        option['review_open'] = reviews.get(key, True)
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    except NoResultFound:
        draft = None
    family = 'cafeteria' if profile == 'staff_guest' else 'patienten'
    return render_admin_week(
        profile, family, week, scope, status, draft, versions, services,
        _scoped_csrf(profile, 'overview', scope), _flash(),
    )

@bp.after_request
def _admin_no_store(response):
    response.headers['Cache-Control'] = 'no-store'
    return response

@bp.get('/')
@require_capability('draft.read')
def dashboard():
    return redirect(url_for('admin.cafeteria'))

@bp.get('/cafeteria')
@require_capability('draft.read')
def cafeteria():
    return _week_overview('staff_guest')

@bp.get('/patienten')
@require_capability('draft.read')
def patienten():
    return _week_overview('patient')

@bp.get('/<any(cafeteria, patienten):family>/menu')
@require_capability('draft.read')
def menu_get(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    week = _week_arg()
    day, meal, option = request.args.get('day'), request.args.get('meal'), request.args.get('option')
    if day is None or meal is None or option is None:
        abort(400, description='Menüslot ist unvollständig.')
    _raster(profile, week, day, meal, option)
    scope = _scope(profile)
    return _render_menu_page(profile, family, scope, week, day, meal, option)

@bp.post('/<any(cafeteria, patienten):family>/menu')
@require_capability('draft.write')
def menu_post(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    if request.args and (
        set(request.args) != {'return_to'} or request.args.getlist('return_to') != ['week']
    ):
        abort(400, description='Rückkehrziel ist ungültig.')
    scope = _validate_scoped_csrf(profile, {'overview', 'menu'})
    try:
        parsed = parse_menu_item_form(profile, request.form)
        version = persist_menu_item(
            _db(), scope, parsed.week_start, parsed.day, parsed.meal,
            parsed.option, parsed.payload, parsed.expected_item_row_version,
        )
    except AutoOriginConflictError as error:
        return _menu_error_response(
            profile, family, scope, error, 409,
            keep_request_values=True, origin_conflict=True,
        )
    except _MENU_VALIDATION_ERRORS as error:
        return _menu_error_response(
            profile, family, scope, error, 400, keep_request_values=True,
        )
    except _MENU_CONFLICT_ERRORS as error:
        return _menu_error_response(
            profile, family, scope, error, 409, keep_request_values=True,
        )
    except _STORE_ERRORS as error:
        _abort_store(error)
    if request.args.get('return_to') == 'week':
        flash('Menü gespeichert.')
        return redirect(url_for(f'admin.{family}', week=parsed.week_start.isoformat()), 303)
    return redirect(url_for(
        'admin.menu_get', family=family, week=parsed.week_start.isoformat(),
        day=parsed.day, meal=parsed.meal, option=parsed.option, row_version=version,
    ), code=303)

@bp.post('/<any(cafeteria, patienten):family>/menu/review')
@require_capability('draft.write')
def menu_review(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _validate_scoped_csrf(profile, {'overview', 'menu'})
    _exact({'_csrf', 'week', 'day', 'meal', 'option', 'row_version', 'component_version'})
    week, day, meal, option = _monday(request.form['week']), request.form['day'], request.form['meal'], request.form['option']
    _raster(profile, week, day, meal, option)
    expected, token = _version_field('row_version'), request.form['component_version']
    try:
        item_id, _, _ = _load_item(scope, week, day, meal, option)
        version = review_component(_db(), scope, item_id, token, expected)
    except AutoOriginConflictError as error:
        return _menu_error_response(
            profile, family, scope, error, 409,
            keep_request_values=False, origin_conflict=True,
        )
    except _MENU_VALIDATION_ERRORS as error:
        return _menu_error_response(
            profile, family, scope, error, 400, keep_request_values=False,
        )
    except _MENU_CONFLICT_ERRORS as error:
        return _menu_error_response(
            profile, family, scope, error, 409, keep_request_values=False,
        )
    except _STORE_ERRORS as error:
        _abort_store(error)
    return redirect(url_for(
        'admin.menu_get', family=family, week=week.isoformat(), day=day, meal=meal,
        option=option, row_version=version,
    ), code=303)

@bp.get('/<any(cafeteria, patienten):family>/header')
@require_capability('draft.read')
def header_get(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    week = _week_arg()
    scope = _scope(profile)
    def load():
        with _db().connect() as connection:
            resolve_week_ref(connection, scope, week)
            return load_draft_connection(connection, profile, week)
    draft = _call(load)
    return _page(
        f'<div data-week="{week.isoformat()}">{_hidden("_csrf", _scoped_csrf(profile, "header", scope))}'
        f'{_hidden("week", week.isoformat())}{_hidden("row_version", draft["row_version"])}'
        f'<span class="title">{escape(str(draft["title"]))}</span>'
        f'<span class="shared-note">{escape(str(draft["shared_note"]))}</span></div>'
    )

@bp.post('/<any(cafeteria, patienten):family>/header')
@require_capability('draft.write')
def header_post(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _validate_scoped_csrf(profile, {'overview', 'header'})
    parsed = _call(lambda: parse_week_header_form(profile, request.form))
    _call(lambda: persist_week_header(
        _db(), scope, parsed.week_start, parsed.payload,
        parsed.expected_week_row_version,
    ))
    flash('Wochenangaben gespeichert.')
    return redirect(url_for(f'admin.{family}', week=parsed.week_start.isoformat()), 303)

@bp.get('/<any(cafeteria, patienten):family>/service')
@require_capability('draft.read')
def service_get(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    week = _week_arg()
    day, meal = request.args.get('day'), request.args.get('meal')
    if day is None or meal is None:
        abort(400, description='Service-Slot ist unvollständig.')
    _raster(profile, week, day, meal, None)
    scope = _scope(profile)
    def load():
        with _db().connect() as connection:
            week_ref = resolve_week_ref(connection, scope, week)
            return connection.execute(text(
                'SELECT s.row_version, s.service_state, COALESCE(s.notice, \'\') AS notice '
                'FROM cafeteria.menu_services s JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id '
                'WHERE s.menu_week_id=:week_id AND s.service_date=:day AND mp.code=:meal'
            ), {'week_id': week_ref.week_id, 'day': day, 'meal': meal}).mappings().one_or_none()
    row = _call(load)
    if row is None:
        abort(404)
    return _page(
        f'<div data-week="{week.isoformat()}" data-day="{escape(day)}" data-meal="{escape(meal)}">'
        f'{_hidden("_csrf", _scoped_csrf(profile, "service", scope))}'
        f'{_hidden("row_version", int(row["row_version"]))}'
        f'<span class="service-state">{escape(str(row["service_state"]))}</span>'
        f'<span class="notice">{escape(str(row["notice"]))}</span></div>'
    )

@bp.post('/<any(cafeteria, patienten):family>/service')
@require_capability('draft.write')
def service_post(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _validate_scoped_csrf(profile, {'overview', 'service'})
    parsed = _call(lambda: parse_service_form(profile, request.form))
    _call(lambda: persist_service_state(
        _db(), scope, parsed.week_start, parsed.day, parsed.meal,
        parsed.payload, parsed.expected_service_row_version,
    ))
    flash('Service gespeichert.')
    return redirect(url_for(f'admin.{family}', week=parsed.week_start.isoformat()), 303)


def _component_error_response(profile: str, family: str, scope: AdminScope, error: BaseException,
                              public_id: str | None = None):
    allergens, labels = _master_choices()
    values, errors = request.form.copy(), _menu_errors(error)
    if public_id is None:
        rows = _call(lambda: find_components(_db(), scope, '', None, False))
        return render_components(
            profile, family, rows, '', None, False,
            _scoped_csrf(profile, 'component-create', scope), _flash(), CATEGORY_LABELS,
            allergens, labels, form_values=values, form_errors=errors,
        ), 400
    row = _call(lambda: get_component(_db(), scope, public_id, include_archived=True))
    allergen_codes, label_codes = {choice['code'] for choice in allergens}, {choice['code'] for choice in labels}
    allergens.extend(choice for choice in row['allergens'] if choice['code'] not in allergen_codes)
    labels.extend(choice for choice in row['labels'] if choice['code'] not in label_codes)
    # Keep the submitted revision: a validation error must not approve a newer edit.
    row['row_version'] = values.get('row_version', '')
    return render_component_detail(
        profile, family, row, _scoped_csrf(profile, 'component', scope), _flash(), CATEGORY_LABELS,
        allergens, labels, form_values=values, form_errors=errors,
    ), 400

@bp.get('/<any(cafeteria, patienten):family>/komponenten')
@require_capability('draft.read')
def components_get(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _scope(profile)
    query, category, archived = request.args.get('q', ''), request.args.get('category') or None, request.args.get('include_archived', '')
    if archived not in {'', '0', '1'} or len(request.args.getlist('q')) > 1:
        abort(400, description='Suchfelder sind ungültig.')
    rows = _call(lambda: find_components(_db(), scope, query, category, archived == '1'))
    allergens, labels = _master_choices()
    return render_components(
        profile, family, rows, query, category, archived == '1',
        _scoped_csrf(profile, 'component-create', scope), _flash(), CATEGORY_LABELS,
        allergens, labels,
    )

@bp.post('/<any(cafeteria, patienten):family>/komponenten')
@require_capability('draft.write')
def components_create(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _validate_scoped_csrf(profile, {'component-create'})
    try:
        parsed = parse_component_create_form(request.form)
        created = create_component(
            _db(), scope, str(parsed.payload['category']), str(parsed.payload['name']),
            None if parsed.payload['origin_country_code'] is None else str(parsed.payload['origin_country_code']),
            cast(Literal['common', 'current'], parsed.payload['target_scope']),
            cast(list[str], parsed.payload['label_codes']), cast(list[AllergenInput], parsed.payload['allergens']),
        )
    except (WorkflowValidationError, ComponentCatalogValidationError) as error:
        return _component_error_response(profile, family, scope, error)
    except _STORE_ERRORS as error:
        _abort_store(error)
    flash(REVIEW_HINT)
    return redirect(url_for('admin.component_detail', family=family, public_id=created['public_id']), 303)

@bp.get('/<any(cafeteria, patienten):family>/komponenten/<public_id>')
@require_capability('draft.read')
def component_detail(family: str, public_id: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _scope(profile)
    row = _call(lambda: get_component(_db(), scope, public_id, include_archived=True))
    allergens, labels = _master_choices()
    allergen_codes = {choice['code'] for choice in allergens}
    label_codes = {choice['code'] for choice in labels}
    allergens.extend(choice for choice in row['allergens'] if choice['code'] not in allergen_codes)
    labels.extend(choice for choice in row['labels'] if choice['code'] not in label_codes)
    return render_component_detail(
        profile, family, row, _scoped_csrf(profile, 'component', scope), _flash(), CATEGORY_LABELS,
        allergens, labels,
    )

@bp.post('/<any(cafeteria, patienten):family>/komponenten/<public_id>')
@require_capability('draft.write')
def component_update(family: str, public_id: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _validate_scoped_csrf(profile, {'component'})
    try:
        parsed = parse_component_update_form(request.form)
        get_component(_db(), scope, public_id, include_archived=True)
        update_component(
            _db(), scope, public_id,
            {
                'category': parsed.payload['category'], 'name': parsed.payload['name'],
                'origin_country_code': parsed.payload['origin_country_code'],
                'label_codes': parsed.payload['label_codes'], 'allergens': parsed.payload['allergens'],
            },
            parsed.expected_component_row_version,
        )
    except (WorkflowValidationError, ComponentCatalogValidationError) as error:
        return _component_error_response(profile, family, scope, error, public_id)
    except _STORE_ERRORS as error:
        _abort_store(error)
    flash(REVIEW_HINT)
    return redirect(url_for('admin.component_detail', family=family, public_id=public_id), 303)

def _component_status(family: str, public_id: str, *, archive: bool):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _validate_scoped_csrf(profile, {'component'})
    parser = parse_component_archive_form if archive else parse_component_unarchive_form
    writer = archive_component if archive else unarchive_component
    parsed = _call(lambda: parser(request.form))
    _call(lambda: writer(_db(), scope, public_id, parsed.expected_component_row_version))
    flash(REVIEW_HINT)
    return redirect(url_for('admin.component_detail', family=family, public_id=public_id), 303)

@bp.post('/<any(cafeteria, patienten):family>/komponenten/<public_id>/archive')
@require_capability('draft.write')
def component_archive(family: str, public_id: str):
    return _component_status(family, public_id, archive=True)

@bp.post('/<any(cafeteria, patienten):family>/komponenten/<public_id>/unarchive')
@require_capability('draft.write')
def component_unarchive(family: str, public_id: str):
    return _component_status(family, public_id, archive=False)

@bp.get('/<any(cafeteria, patienten):family>/copy')
@require_capability('draft.read')
def copy_get(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    target = _week_arg()
    source = target - timedelta(days=7)
    scope = _scope(profile)
    def versions() -> int:
        with _db().connect() as connection:
            resolve_week_ref(connection, scope, source)
            try:
                target_ref = resolve_week_ref(connection, scope, target)
            except PartialWorkflowNotFoundError:
                return 0
            blocked = connection.execute(
                text('SELECT EXISTS (SELECT 1 FROM cafeteria.menu_services s '
                     'JOIN cafeteria.menu_items i ON i.service_id=s.id WHERE s.menu_week_id=:week_id) '
                     'OR EXISTS (SELECT 1 FROM cafeteria.publication_revisions r '
                     'WHERE r.menu_week_id=:week_id AND r.withdrawn_at IS NULL)'),
                {'week_id': target_ref.week_id},
            ).scalar_one()
            if blocked:
                raise PartialWorkflowConflictError('Zielwoche ist nicht leer oder publiziert.')
            return target_ref.row_version
    target_version = _call(versions)
    return render_template(
        'admin/copy.html', profile=profile, family=family, source=source, target=target,
        target_row_version=target_version, csrf=_scoped_csrf(profile, 'copy', scope),
    )

@bp.post('/<any(cafeteria, patienten):family>/copy')
@require_capability('draft.write')
def copy_post(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _validate_scoped_csrf(profile, {'copy'})
    _exact({'_csrf', 'source_week', 'target_week', 'target_row_version'})
    source, target = _monday(request.form['source_week']), _monday(request.form['target_week'])
    if source != target - timedelta(days=7):
        abort(400, description='source_week muss genau die Vorwoche sein.')
    _call(lambda: copy_previous_week(
        _db(), scope, target, _version_field('target_row_version'),
    ))
    return redirect(url_for(f'admin.{family}', week=target.isoformat()), 303)

@bp.get('/<any(cafeteria, patienten):family>/preview')
@require_capability('preview.read')
def preview(family: str):
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
    state = str(draft['workflow_state'])
    if state not in {'draft', 'ready', 'published', 'archived'}:
        abort(404)
    return render_admin_preview(profile, family, week, state, draft)

@bp.post('/<any(cafeteria, patienten):family>/publish')
@require_capability('publication.publish')
def publish(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    scope = _validate_scoped_csrf(profile, {'overview'})
    _exact({'_csrf', 'week', 'row_version'})
    week, expected = _monday(request.form['week']), _version_field('row_version')
    snapshot = _call(lambda: publish_draft(
        _db(), profile, week, expected_row_version=expected, actor_id=scope.actor_id,
        issuer_engine=current_app.extensions.get('cafeteria_auth_issuer_db'), expected_location_id=scope.location_id))
    flash(f'Publiziert: {snapshot["revision_id"]}')
    return redirect(url_for(f'admin.{family}', week=week.isoformat()), 303)


# Register saved-week printing after the shared workflow helpers are defined.
from . import print_routes as print_routes  # noqa: E402, F401
from . import week_review_routes as week_review_routes  # noqa: E402, F401
