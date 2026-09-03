from __future__ import annotations

import re
from datetime import date, timedelta
from html import escape
from typing import Literal, cast

from flask import (
    abort, current_app, flash, get_flashed_messages, make_response, redirect, request, url_for,
)
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from ..component_assignment_store import (
    ComponentAssignmentConflictError, ComponentAssignmentValidationError,
)
from ..component_catalog_store import (
    AdminScope, ComponentCatalogConfigurationError, ComponentCatalogValidationError,
    ComponentConflictError, ComponentNotFoundError, StaleComponentError, archive_component,
    create_component, find_components, get_component, resolve_single_active_location_connection,
    unarchive_component, update_component,
)
from ..public.routes import effective_today
from ..roles import require_capability
from ..security import csrf_token, validate_csrf
from ..workflow import (
    MENU_TYPES, PROFILE_DAYS, PROFILE_MEALS, AutoOriginConflictError,
    PublicationConfigurationError, StaleDraftError, StaleItemError, WorkflowValidationError,
    get_component_review_token, publish_draft, review_component,
)
from ..workflow_copy_store import copy_previous_week
from ..workflow_partial_form import (
    parse_component_archive_form, parse_component_create_form, parse_component_unarchive_form,
    parse_component_update_form, parse_menu_item_form, parse_service_form, parse_week_header_form,
)
from ..workflow_partial_store import (
    PartialWorkflowConflictError, PartialWorkflowNotFoundError, PartialWorkflowValidationError,
    persist_menu_item, persist_service_state, persist_week_header, resolve_item_id,
    resolve_week_ref,
)
from ..workflow_store import load_draft_connection
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

def _origin_page(context: str):
    return _page(f'<div class="error-region" role="alert">{ORIGIN_CONFLICT}</div>{context}', 409)

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
    if re.fullmatch(r'\d+', raw) is None:
        abort(400, description='Versionsnummer muss eine nichtnegative ganze Zahl sein.')
    return int(raw, 10)

def _db():
    return current_app.extensions['cafeteria_db']

def _flash() -> str:
    return ''.join(f'<p class="notice">{escape(message)}</p>' for message in get_flashed_messages())

def _menu_context(week: date, day: str, meal: str, option: str, title: str, version: int) -> str:
    return (
        f'<div data-week="{week.isoformat()}" data-day="{escape(day)}" '
        f'data-meal="{escape(meal)}" data-option="{escape(option)}">'
        f'{_hidden("week", week.isoformat())}{_hidden("day", day)}{_hidden("meal", meal)}'
        f'{_hidden("option", option)}{_hidden("row_version", version)}'
        f'<span class="title">{escape(title)}</span></div>'
    )


def _load_item(scope: AdminScope, week: date, day: str, meal: str, option: str):
    with _db().connect() as connection:
        week_ref = resolve_week_ref(connection, scope, week)
        item_id = resolve_item_id(connection, scope, week_ref, day, meal, option)
        row = connection.execute(
            text('SELECT row_version, title FROM cafeteria.menu_items WHERE id=:id'),
            {'id': item_id},
        ).mappings().one()
    return item_id, int(row['row_version']), str(row['title'])


def _week_overview(profile: str):
    _reject_override()
    week = _week_arg()
    _scope(profile)
    draft = None
    versions: dict[tuple[str, str, str], int] = {}
    try:
        with _db().connect() as connection:
            draft = load_draft_connection(connection, profile, week)
            rows = connection.execute(
                text(
                    'SELECT s.service_date::text AS day, mp.code AS meal, mt.code AS option, '
                    'i.row_version FROM cafeteria.menu_items i '
                    'JOIN cafeteria.menu_services s ON s.id=i.service_id '
                    'JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id '
                    'JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id '
                    'WHERE s.menu_week_id=:week_id'
                ),
                {'week_id': int(draft['id'])},
            )
            versions = {
                (str(row.day), str(row.meal), str(row.option)): int(row.row_version) for row in rows
            }
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    except NoResultFound:
        draft = None
    titles = {
        (entry['date'], service['meal_code'], item['type_code']): str(item['title'])
        for entry in (draft or {'days': []})['days']
        for service in entry['services']
        for item in service['options']
    }
    parts = [_flash(), f'<div data-profile="{profile}" data-week="{week.isoformat()}">',
             _hidden('_csrf', csrf_token()), _hidden('week', week.isoformat())]
    if profile == 'staff_guest':
        parts.append('<p>Samstag und Sonntag: Cafeteria geschlossen.</p>')
    for offset in range(PROFILE_DAYS[profile]):
        day = (week + timedelta(days=offset)).isoformat()
        for meal in PROFILE_MEALS[profile]:
            for option in MENU_TYPES:
                parts.append(
                    f'<article data-day="{day}" data-meal="{meal}" data-option="{option}">'
                    f'{_hidden("row_version", versions.get((day, meal, option), 0))}'
                    f'<span class="title">{escape(titles.get((day, meal, option), ""))}</span></article>'
                )
    return _page(''.join(parts) + '</div>')


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
    try:
        item_id, version, title = _load_item(scope, week, day, meal, option)
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    except (PartialWorkflowNotFoundError, NoResultFound):
        context = _menu_context(week, day, meal, option, '', 0)
        return _page(f'{_hidden("_csrf", csrf_token())}{context}')
    context = _menu_context(week, day, meal, option, title, version)
    try:
        token = get_component_review_token(_db(), scope, item_id)
    except AutoOriginConflictError:
        return _origin_page(context)
    except _STORE_ERRORS as error:
        _abort_store(error)
    return _page(
        f'{_hidden("_csrf", csrf_token())}{context}{_hidden("component_version", token)}'
    )


@bp.post('/<any(cafeteria, patienten):family>/menu')
@require_capability('draft.write')
def menu_post(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    try:
        parsed = parse_menu_item_form(profile, request.form)
        version = persist_menu_item(
            _db(), _scope(profile), parsed.week_start, parsed.day, parsed.meal,
            parsed.option, parsed.payload, parsed.expected_item_row_version,
        )
    except AutoOriginConflictError:
        return _origin_page('')
    except _STORE_ERRORS as error:
        _abort_store(error)
    return redirect(url_for(
        'admin.menu_get', family=family, week=parsed.week_start.isoformat(),
        day=parsed.day, meal=parsed.meal, option=parsed.option, row_version=version,
    ), code=303)


@bp.post('/<any(cafeteria, patienten):family>/menu/review')
@require_capability('draft.write')
def menu_review(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    _exact({'_csrf', 'week', 'day', 'meal', 'option', 'row_version', 'component_version'})
    week, day, meal, option = _monday(request.form['week']), request.form['day'], request.form['meal'], request.form['option']
    _raster(profile, week, day, meal, option)
    expected, token = _version_field('row_version'), request.form['component_version']
    scope = _scope(profile)
    context = _menu_context(week, day, meal, option, '', expected)
    try:
        item_id, _, title = _load_item(scope, week, day, meal, option)
        context = _menu_context(week, day, meal, option, title, expected)
        version = review_component(_db(), scope, item_id, token, expected)
    except AutoOriginConflictError:
        return _origin_page(context)
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
        f'<div data-week="{week.isoformat()}">{_hidden("_csrf", csrf_token())}'
        f'{_hidden("week", week.isoformat())}{_hidden("row_version", draft["row_version"])}'
        f'<span class="title">{escape(str(draft["title"]))}</span>'
        f'<span class="shared-note">{escape(str(draft["shared_note"]))}</span></div>'
    )


@bp.post('/<any(cafeteria, patienten):family>/header')
@require_capability('draft.write')
def header_post(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    parsed = _call(lambda: parse_week_header_form(profile, request.form))
    _call(lambda: persist_week_header(
        _db(), _scope(profile), parsed.week_start, parsed.payload,
        parsed.expected_week_row_version,
    ))
    return redirect(url_for('admin.header_get', family=family, week=parsed.week_start.isoformat()), 303)


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
        f'{_hidden("_csrf", csrf_token())}{_hidden("row_version", int(row["row_version"]))}'
        f'<span class="service-state">{escape(str(row["service_state"]))}</span>'
        f'<span class="notice">{escape(str(row["notice"]))}</span></div>'
    )


@bp.post('/<any(cafeteria, patienten):family>/service')
@require_capability('draft.write')
def service_post(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    parsed = _call(lambda: parse_service_form(profile, request.form))
    _call(lambda: persist_service_state(
        _db(), _scope(profile), parsed.week_start, parsed.day, parsed.meal,
        parsed.payload, parsed.expected_service_row_version,
    ))
    return redirect(url_for(
        'admin.service_get', family=family, week=parsed.week_start.isoformat(),
        day=parsed.day, meal=parsed.meal,
    ), 303)


@bp.get('/<any(cafeteria, patienten):family>/komponenten')
@require_capability('draft.read')
def components_get(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    query, category, archived = request.args.get('q', ''), request.args.get('category'), request.args.get('include_archived', '')
    if archived not in {'', '0', '1'} or len(request.args.getlist('q')) > 1:
        abort(400, description='Suchfelder sind ungültig.')
    rows = _call(lambda: find_components(_db(), _scope(profile), query, category, archived == '1'))
    items = ''.join(
        f'<li data-public-id="{escape(str(row["public_id"]))}" data-active="{int(bool(row["active"]))}">'
        f'{escape(str(row["name"]))} usage={row["usage_count"]}</li>'
        for row in rows
    )
    return _page(f'<div data-profile="{profile}">{_flash()}{_hidden("_csrf", csrf_token())}<ul>{items}</ul></div>')


@bp.post('/<any(cafeteria, patienten):family>/komponenten')
@require_capability('draft.write')
def components_create(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    parsed = _call(lambda: parse_component_create_form(request.form))
    created = _call(lambda: create_component(
        _db(), _scope(profile), str(parsed.payload['category']), str(parsed.payload['name']),
        None if parsed.payload['origin_country_code'] is None else str(parsed.payload['origin_country_code']),
        cast(Literal['common', 'current'], parsed.payload['target_scope']),
        list(parsed.payload['label_codes']), list(parsed.payload['allergens']),
    ))
    flash(REVIEW_HINT)
    return redirect(url_for('admin.component_detail', family=family, public_id=created['public_id']), 303)


@bp.get('/<any(cafeteria, patienten):family>/komponenten/<public_id>')
@require_capability('draft.read')
def component_detail(family: str, public_id: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    row = _call(lambda: get_component(_db(), _scope(profile), public_id, include_archived=True))
    return _page(
        f'{_flash()}<div data-public-id="{escape(str(row["public_id"]))}" '
        f'data-profile-scope="{escape(str(row["profile_scope"]))}" data-active="{int(bool(row["active"]))}">'
        f'{_hidden("_csrf", csrf_token())}{_hidden("row_version", row["row_version"])}'
        f'<span class="name">{escape(str(row["name"]))}</span></div>'
    )


@bp.post('/<any(cafeteria, patienten):family>/komponenten/<public_id>')
@require_capability('draft.write')
def component_update(family: str, public_id: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    parsed = _call(lambda: parse_component_update_form(request.form))
    _call(lambda: get_component(_db(), _scope(profile), public_id, include_archived=True))
    _call(lambda: update_component(
        _db(), _scope(profile), public_id,
        {
            'category': parsed.payload['category'], 'name': parsed.payload['name'],
            'origin_country_code': parsed.payload['origin_country_code'],
            'label_codes': parsed.payload['label_codes'], 'allergens': parsed.payload['allergens'],
        },
        parsed.expected_component_row_version,
    ))
    flash(REVIEW_HINT)
    return redirect(url_for('admin.component_detail', family=family, public_id=public_id), 303)


def _component_status(family: str, public_id: str, *, archive: bool):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    parser = parse_component_archive_form if archive else parse_component_unarchive_form
    writer = archive_component if archive else unarchive_component
    parsed = _call(lambda: parser(request.form))
    _call(lambda: writer(_db(), _scope(profile), public_id, parsed.expected_component_row_version))
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

    def target_version() -> int:
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

    version = _call(target_version)
    return _page(
        f'<div data-profile="{profile}" data-source-week="{source.isoformat()}" '
        f'data-target-week="{target.isoformat()}">{_hidden("_csrf", csrf_token())}'
        f'{_hidden("source_week", source.isoformat())}{_hidden("target_week", target.isoformat())}{_hidden("target_row_version", version)}</div>'
    )


@bp.post('/<any(cafeteria, patienten):family>/copy')
@require_capability('draft.write')
def copy_post(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    _exact({'_csrf', 'source_week', 'target_week', 'target_row_version'})
    source, target = _monday(request.form['source_week']), _monday(request.form['target_week'])
    if source != target - timedelta(days=7):
        abort(400, description='source_week muss genau die Vorwoche sein.')
    _call(lambda: copy_previous_week(_db(), _scope(profile), target, _version_field('target_row_version')))
    return redirect(url_for(f'admin.{family}', week=target.isoformat()), 303)


@bp.get('/<any(cafeteria, patienten):family>/preview')
@require_capability('draft.read')
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
    titles = [
        escape(str(item['title']))
        for entry in draft['days']
        for service in entry['services']
        for item in service['options']
    ]
    return _page(
        f'<div class="preview-banner">PREVIEW</div>'
        f'<div data-preview="last-saved" data-workflow-state="{escape(state)}" '
        f'data-week="{week.isoformat()}" data-profile="{profile}">'
        f'<span class="title">{escape(str(draft["title"]))}</span>'
        f'<div class="dishes">{" ".join(titles)}</div></div>'
    )


@bp.post('/<any(cafeteria, patienten):family>/publish')
@require_capability('publication.publish')
def publish(family: str):
    profile = profile_from_endpoint(family)
    _reject_override()
    validate_csrf(request.form.get('_csrf'))
    _exact({'_csrf', 'week', 'row_version'})
    week, expected = _monday(request.form['week']), _version_field('row_version')
    _call(lambda: publish_draft(
        _db(), profile, week, expected_row_version=expected,
        actor_id=_scope(profile).actor_id,
        issuer_engine=current_app.extensions.get('cafeteria_auth_issuer_db'),
    ))
    return redirect(url_for(f'admin.{family}', week=week.isoformat()), 303)
