"""Admin dish-template list and editor; CAS is the original updated_at timestamp."""
from __future__ import annotations

from datetime import datetime

from flask import current_app, g, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..auth.local_users import ActorExpectation
from .. import dish_template_store as store
from ..recipe_reads import get_location, list_recipes
from ..recipe_types import RecipeConflictError, RecipeNotFoundError, RecipeValidationError
from ..roles import capabilities, require_capability
from ..security import validate_csrf
from .routes import bp

SCOPES = (('common', 'Gemeinsam'), ('patient', 'Patienten'), ('staff_guest', 'Cafeteria'))
TYPES = (('MENU_1', 'Menü 1'), ('VEGGIE', 'Vegetarisch'))


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
    }


def _payload(values: dict[str, str]) -> dict[str, object]:
    recipe = values['recipe_public_id'].strip()
    menu = values['menu_type_code'].strip()
    return {
        'title': values['title'],
        'description': values['description'] or None,
        'menu_type_code': menu or None,
        'profile_scope': values['profile_scope'],
        'recipe_public_id': recipe or None,
    }


def _page(
    *, row=None, values=None, error: str | None = None, status: int = 200, include_archived: bool = False,
    cas: datetime | None = None,
) -> Response:
    location = get_location(_db())
    recipes = [
        {'public_id': item.public_id, 'title': item.payload.get('title') or item.public_id, 'active': item.active}
        for item in list_recipes(_db(), include_archived=True)
    ]
    html = render_template(
        'admin/gerichtvorlagen.html', family='cafeteria', profile='staff_guest',
        rows=store.list_templates(_db(), include_archived=include_archived),
        row=row, values=values or _fields(), error=error, can_write=_can_write(),
        location_id=location, scopes=SCOPES, types=TYPES, recipes=recipes,
        include_archived=include_archived, cas=cas or (row.updated_at if row else None),
    )
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


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
    return _page(values=_fields({}))


@bp.post('/gerichtvorlagen/neu')
@require_capability('draft.write')
def dish_template_create() -> Response:
    validate_csrf(request.form.get('_csrf'))
    values = _fields()
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
        expected = store.parse_updated_at(request.form.get('updated_at', ''))
        action = request.form.get('action', 'save')
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
