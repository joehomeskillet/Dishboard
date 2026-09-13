"""Admin dish-template list and editor; CAS is the original updated_at timestamp."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Literal, cast

from flask import abort, current_app, g, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import NoResultFound
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from ..auth.local_users import ActorExpectation
from .. import dish_template_store as store
from .. import recipe_link_reads as links
from ..recipe_reads import get_location, get_recipe
from ..recipe_types import RecipeConflictError, RecipeNotFoundError, RecipeValidationError
from ..roles import capabilities, require_capability
from ..security import validate_csrf
from ..component_catalog_store import ComponentNotFoundError
from ..menu_template_binding import lock_templates, require_template_source
from ..workflow import PROFILE_MEALS
from ..workflow_partial_store import PartialWorkflowNotFoundError
from ..workflow_write_context import WriteConflictError, write_transaction
from .rendering import DAY_NAMES, MEAL_LABELS, MONTHS
from .workflow_scope import (
    _scope, _scoped_csrf, _validated, bind_template_target,
    issue_template_source, read_template_context,
)
from .workflow_routes import _abort_store, _load_item, _monday, _raster, _STORE_ERRORS, _week_arg
from .routes import bp

SCOPES = (('common', 'Gemeinsam'), ('patient', 'Patienten'), ('staff_guest', 'Cafeteria'))
TYPES = (('MENU_1', 'Menü 1'), ('VEGGIE', 'Vegetarisch'))
CHOICE_ACTIONS = {'recipe_search', 'recipe_previous', 'recipe_next'}
ACCOMPANIMENTS = {'none', 'soup', 'salad'}


def _db():
    return current_app.extensions['cafeteria_db']


def _actor() -> ActorExpectation:
    return ActorExpectation(g.auth_user.user_id, g.auth_user.authz_version)


def _can_write() -> bool:
    allowed = capabilities()
    return '*' in allowed or 'draft.write' in allowed


def _fields(form=None) -> dict[str, str]:
    source = request.form if form is None else form
    return {
        'title': source.get('title', ''),
        'description': source.get('description', ''),
        'menu_type_code': source.get('menu_type_code', ''),
        'profile_scope': source.get('profile_scope', 'common'),
        'recipe_public_id': source.get('recipe_public_id', ''),
        'accompaniment_default': source.get('accompaniment_default', 'none'),
    }


def _payload(values: dict[str, str]) -> dict[str, object]:
    recipe = values['recipe_public_id'].strip()
    menu = values['menu_type_code'].strip()
    accompaniment = values['accompaniment_default']
    if accompaniment not in ACCOMPANIMENTS:
        raise RecipeValidationError('Bitte eine gültige Beilage wählen.')
    return {
        'title': values['title'],
        'description': values['description'] or None,
        'menu_type_code': menu or None,
        'profile_scope': values['profile_scope'],
        'recipe_public_id': recipe or None,
        'accompaniment_default': accompaniment,
    }


def _page(
    *, row=None, values=None, error: str | None = None, status: int = 200, include_archived: bool = False,
    cas: datetime | None = None, search: str | None = None, offset: int | None = None,
) -> Response:
    location = get_location(_db())
    values = values if values is not None else _fields()
    template_rows = links.list_template_links(
        _db(), include_archived=include_archived or row is not None,
    )
    accompaniment_by_id = {
        item.public_id: item.accompaniment_default
        for item in store.list_templates(
            _db(), include_archived=include_archived or row is not None,
        )
    }
    template_rows = tuple(replace(
        item, accompaniment_default=accompaniment_by_id[item.public_id],
    ) for item in template_rows)
    cas_value = ''
    if row:
        cas_value = (request.form.get('updated_at', '') if request.method == 'POST'
                     else (cas or row.updated_at).isoformat())
    choices = None
    if row or request.endpoint in {'admin.dish_template_new', 'admin.dish_template_create'}:
        try:
            offset = int(request.args.get('recipe_offset', '0')) if offset is None else offset
            choices = links.list_recipe_choices(
                _db(), selected=values['recipe_public_id'],
                search=request.args.get('recipe_search', '') if search is None else search, offset=offset)
        except (ValueError, RecipeValidationError):
            error = error or 'Ungültige Rezeptsuche.'
            status = status if status != 200 else 400
            choices = links.list_recipe_choices(_db(), selected=values['recipe_public_id'])
    html = render_template(
        'admin/gerichtvorlagen.html', family='cafeteria', profile='staff_guest',
        rows=template_rows,
        row=row, values=values, error=error, can_write=_can_write(),
        location_id=location, scopes=SCOPES, types=TYPES, recipe_choices=choices,
        include_archived=include_archived, cas_value=cas_value,
        accompaniment_error=(
            'Bitte eine gültige Beilage wählen.'
            if values.get('accompaniment_default') not in ACCOMPANIMENTS else ''
        ),
    )
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


def _recipe_search(values, *, row=None, cas=None) -> Response:
    """Redisplay the original form without persisting or renewing its CAS."""
    try:
        offset = int(request.form.get('recipe_offset', '0'))
        action = request.form.get('action')
        offset = (offset + links.PAGE_SIZE if action == 'recipe_next' else
                  max(0, offset - links.PAGE_SIZE) if action == 'recipe_previous' else 0)
    except ValueError:
        offset = -1
    return _page(row=row, values=values, cas=cas,
                 search=request.form.get('recipe_search', ''), offset=offset)


@bp.get('/gerichtvorlagen')
@require_capability('draft.read')
def dish_templates_list() -> Response:
    archived = request.args.get('archived') == '1'
    return _page(include_archived=archived)


@bp.get('/gerichtvorlagen/neu')
@require_capability('draft.read')
def dish_template_new() -> Response:
    if not _can_write():
        return _page(error='Diese Aktion ist nicht erlaubt.', status=403)
    values = _fields({})
    recipe_id = request.args.get('recipe', '')
    if recipe_id:
        try:
            recipe = get_recipe(_db(), recipe_id)
        except (RecipeNotFoundError, RecipeValidationError):
            return _page(values=values, error='Rezept nicht gefunden.', status=404)
        values.update(recipe_public_id=recipe.public_id, title=str(recipe.payload.get('title') or ''))
    return _page(values=values)


@bp.post('/gerichtvorlagen/neu')
@require_capability('draft.write')
def dish_template_create() -> Response:
    validate_csrf(request.form.get('_csrf'))
    values = _fields()
    if request.form.get('action') in CHOICE_ACTIONS:
        return _recipe_search(values)
    try:
        extra_target = request.form.get('public_id') or None
        extra_expected = request.form.get('updated_at') or None
        expected = store.parse_updated_at(extra_expected) if extra_expected else None
        store.create_template(
            _db(), _actor(), _payload(values), expected_location_id=get_location(_db()),
            target=extra_target, expected=expected,
        )
    except RecipeValidationError as error:
        return _page(values=values, error=str(error), status=400)
    except RecipeConflictError as error:
        return _page(values=values, error=str(error), status=409)
    except RecipeNotFoundError as error:
        return _page(values=values, error=str(error), status=400)
    return redirect(url_for('admin.dish_templates_list'), 303)


@bp.get('/gerichtvorlagen/<public_id>')
@require_capability('draft.read')
def dish_template_edit(public_id: str) -> Response:
    try:
        row = store.get_template(_db(), store.as_uuid(public_id))
    except RecipeNotFoundError:
        return _page(error='Unbekannte Gerichtvorlage.', status=404)
    values = {
        'title': row.title, 'description': row.description or '',
        'menu_type_code': row.menu_type_code or '', 'profile_scope': row.profile_scope,
        'recipe_public_id': row.recipe_public_id or '',
        'accompaniment_default': row.accompaniment_default,
    }
    return _page(row=row, values=values)


@bp.post('/gerichtvorlagen/<public_id>')
@require_capability('draft.write')
def dish_template_save(public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    values = _fields()
    row = None
    expected = None
    try:
        row = store.get_template(_db(), store.as_uuid(public_id))
        if 'accompaniment_default' not in request.form:
            values['accompaniment_default'] = row.accompaniment_default
        expected = store.parse_updated_at(request.form.get('updated_at', ''))
        action = request.form.get('action', 'save')
        if action in CHOICE_ACTIONS:
            return _recipe_search(values, row=row, cas=expected)
        location = get_location(_db())
        if action == 'archive':
            store.set_template_active(
                _db(), _actor(), row.public_id, expected, active=False,
                expected_location_id=location,
            )
        elif action == 'reactivate':
            store.set_template_active(
                _db(), _actor(), row.public_id, expected, active=True,
                expected_location_id=location,
            )
        else:
            store.update_template(
                _db(), _actor(), row.public_id, expected, _payload(values),
                expected_location_id=location,
            )
    except RecipeValidationError as error:
        return _page(row=row, values=values, error=str(error), status=400)
    except RecipeConflictError as error:
        current = row
        try:
            current = store.get_template(_db(), store.as_uuid(public_id))
        except RecipeNotFoundError:
            current = row
        return _page(row=current, values=values, error=str(error), status=409, cas=expected)
    except RecipeNotFoundError as error:
        return _page(row=row, values=values, error=str(error), status=404 if row is None else 400)
    return redirect(url_for('admin.dish_template_edit', public_id=public_id), 303)


def _planning_page(public_id: str, values: dict[str, str], *, status: int = 200,
                   error: str = '', occupied: str | None = None,
                   existing_url: str = '', areas=SCOPES[1:]) -> Response:
    """Only supplied values: rejected authority never refreshes business data."""
    blocked_days = []
    if status == 200:
        week = date.fromisoformat(values['week'])
        for offset in range(7):
            try:
                _raster(values['area'], week, (week + timedelta(days=offset)).isoformat(),
                        values['meal'], values['option'])
            except HTTPException as grid_error:
                if grid_error.code != 404:
                    raise
                blocked_days.append(str(offset))
    summary_day = values.get('week', '')
    try:
        chosen_day = date.fromisoformat(values['week']) + timedelta(days=int(values['day']))
        summary_day = f'{DAY_NAMES[chosen_day.weekday()]}, {chosen_day.day}. {MONTHS[chosen_day.month - 1]} {chosen_day.year}'
    except (ValueError, OverflowError):
        pass
    response = make_response(render_template(
        'admin/gerichtvorlage_einplanen.html', public_id=public_id, values=values,
        error=error, occupied=occupied, existing_url=existing_url, areas=areas,
        day_names=DAY_NAMES, meals=MEAL_LABELS, types=TYPES, blocked_days=blocked_days,
        allowed_meals=PROFILE_MEALS.get(values.get('area', ''), tuple(MEAL_LABELS)),
        family='cafeteria', profile=values.get('area', 'staff_guest'),
        area_names={}, summary_day=summary_day, area_labels=dict(SCOPES),
    ), status)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/gerichtvorlagen/<public_id>/einplanen')
@require_capability('draft.write')
def dish_template_plan(public_id: str) -> Response:
    try:
        row = store.get_template(_db(), store.as_uuid(public_id))
    except RecipeNotFoundError:
        abort(404)
    profile = 'patient' if row.profile_scope == 'patient' else 'staff_guest'
    scope = _scope(profile)
    week = _week_arg()
    values = {'title': row.title, 'source_profile': profile, 'area': profile,
              'week': week.isoformat(), 'day': '0', 'meal': 'LUNCH',
              'option': row.menu_type_code or 'MENU_1', '_csrf': '', 'template_context': ''}
    try:
        token = issue_template_source(scope, row.public_id)
        original = read_template_context(token, target=False)
        if row.updated_at.isoformat() != original.expected_updated_at:
            raise WriteConflictError('Die Vorlage wurde geändert. Bitte erneut einplanen.')
    except WriteConflictError as error:
        return _planning_page(public_id, values, status=409, error=str(error))
    except _STORE_ERRORS as error:
        _abort_store(error)
    values.update(template_context=token, _csrf=_scoped_csrf(
        profile, 'proposal', scope, template_context=token))
    areas = SCOPES[1:] if row.profile_scope == 'common' else tuple(
        entry for entry in SCOPES if entry[0] == profile)
    return _planning_page(public_id, values, areas=areas)


@bp.post('/gerichtvorlagen/<public_id>/einplanen')
@require_capability('draft.write')
def dish_template_plan_post(public_id: str) -> Response:
    fields = {'_csrf', 'template_context', 'source_profile', 'title',
              'area', 'week', 'day', 'meal', 'option'}
    if (set(request.form) - {'action'} != fields
            or any(len(request.form.getlist(key)) != 1 for key in fields)
            or len(request.form.getlist('action')) > 1
            or request.form.get('action', 'continue') not in ('continue', 'refresh')):
        abort(400, description='Formularfelder sind ungültig.')
    values = {key: request.form[key] for key in fields}
    source_profile = values['source_profile']
    if source_profile not in PROFILE_MEALS:
        abort(400, description='Bereich ist ungültig.')
    scope, csrf_context = _validated(source_profile, {'proposal'}, check_current=False)
    token = values['template_context']
    if not hmac.compare_digest(csrf_context, 'proposal-' + hashlib.sha256(token.encode()).hexdigest()):
        abort(400, description='Formularkontext ist ungültig.')
    original = read_template_context(token, target=False)
    try:
        if scope != _scope(source_profile) or original.template_public_id != public_id:
            raise WriteConflictError('Berechtigung, Standort oder Vorlage wurde geändert.')
        original.require_source(scope)
        with write_transaction(_db(), scope) as connection:
            try:
                source = next(iter(lock_templates(connection, scope, [public_id]).values()))
            except ComponentNotFoundError as error:
                raise WriteConflictError('Die ursprüngliche Gerichtvorlage ist nicht mehr verfügbar.') from error
            require_template_source(source, scope, original)
            profile = values['area']
            if profile not in PROFILE_MEALS or source['profile_scope'] not in ('common', profile):
                abort(400, description='Diese Vorlage passt nicht zum gewählten Bereich.')
            week = _monday(values['week'])
            if values['day'] not in tuple(str(index) for index in range(7)):
                abort(400, description='Bitte einen Wochentag wählen.')
            if request.form.get('action') == 'refresh':
                if values['meal'] not in PROFILE_MEALS[profile]:
                    values['meal'] = 'LUNCH'
                areas = SCOPES[1:] if source['profile_scope'] == 'common' else tuple(
                    entry for entry in SCOPES if entry[0] == profile)
                return _planning_page(public_id, values, areas=areas)
            day = (week + timedelta(days=int(values['day']))).isoformat()
            meal, option = values['meal'], values['option']
            _raster(profile, week, day, meal, option)
            target_scope = replace(scope, profile_code=cast(Literal['patient', 'staff_guest'], profile))
            family = 'patienten' if profile == 'patient' else 'cafeteria'
            target_url = url_for('admin.menu_get', family=family, week=week.isoformat(),
                                 day=day, meal=meal, option=option)
            try:
                _, _, title = _load_item(target_scope, week, day, meal, option)
            except (PartialWorkflowNotFoundError, NoResultFound):
                pass
            else:
                return _planning_page(public_id, values, status=409, occupied=title,
                    existing_url=target_url)
        bound = bind_template_target(token, target_scope, week, day, meal, option)
    except WriteConflictError as error:
        return _planning_page(public_id, values, status=409, error=str(error))
    except HTTPException as error:
        if error.code not in (400, 404):
            raise
        message = (error.description or 'Dieses Ziel ist ungültig.') if error.code == 400 else 'Dieses Ziel ist nicht im erlaubten Planungsraster.'
        return _planning_page(public_id, values, status=400, error=message)
    except _STORE_ERRORS as error:
        _abort_store(error)
    return redirect(url_for('admin.menu_get', family=family, week=week.isoformat(),
                            day=day, meal=meal, option=option,
                            template=public_id, template_context=bound), 303)
