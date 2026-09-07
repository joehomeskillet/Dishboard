"""Cookbook admin routes; writers always receive the original signed expectations."""
from __future__ import annotations

from collections.abc import Callable, Sequence

from flask import abort, current_app, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from .. import recipe_store as store
from ..master_data_types import ObjectExpectation
from ..recipe_types import RecipeConflictError, RecipeNotFoundError, RecipeValidationError
from ..recipe_values import identifier
from ..roles import capabilities
from . import cookbook_forms as forms
from .recipe_errors import protected, render_form_error
from .recipe_forms import LocationConflict, sign_context, read_context
from .routes import bp

PAGE = forms.PAGE_SIZE


def db():
    return current_app.extensions['cafeteria_db']


def parse_id(raw: str) -> str:
    try:
        return identifier(raw)
    except RecipeValidationError as error:
        raise RecipeNotFoundError('Kochbuch nicht gefunden.') from error


def can_write() -> bool:
    allowed = capabilities()
    return '*' in allowed or 'recipe.write' in allowed


def recipe_url(public_id: str) -> str | None:
    if 'admin.recipe_edit' not in current_app.view_functions:
        return None
    return url_for('admin.recipe_edit', recipe_id=public_id)


def recover(error, *, cookbook_id: str | None = None, create: bool = False) -> Response:
    if isinstance(error, LocationConflict):
        reload_url = '/admin/kochbuecher'
    elif create:
        reload_url = '/admin/kochbuecher/neu'
    elif cookbook_id:
        reload_url = f'/admin/kochbuecher/{cookbook_id}'
    else:
        reload_url = '/admin/kochbuecher'
    return render_form_error(error, reload_url=reload_url)


def collect(reader: Callable, **options) -> list:
    rows: list = []
    offset = 0
    while True:
        batch = reader(db(), limit=500, offset=offset, **options)
        rows.extend(batch)
        if len(batch) < 500:
            return rows
        offset += 500


def listed_cookbooks(page: int, include_archived: bool, search: str) -> tuple[list, bool]:
    if search:
        found = [
            book for book in collect(store.list_cookbooks, include_archived=include_archived)
            if search.casefold() in book.name.casefold()
        ]
        offset = (page - 1) * PAGE
        window = found[offset:offset + PAGE + 1]
        return window[:PAGE], len(window) > PAGE
    rows = list(store.list_cookbooks(
        db(), include_archived=include_archived, limit=PAGE + 1, offset=(page - 1) * PAGE,
    ))
    return rows[:PAGE], len(rows) > PAGE


def assignment_state(assigned: Sequence[str]) -> tuple[list[tuple[str, str]], dict[str, str], list[dict]]:
    recipes = collect(store.list_recipes, include_archived=True)
    by_id = {row.public_id: row for row in recipes}
    options: list[tuple[str, str]] = []
    seen: set[str] = set()
    for public_id in assigned:
        options.append((public_id, forms.recipe_label(by_id.get(public_id))))
        seen.add(public_id)
    for row in recipes:
        if row.public_id in seen or not row.active:
            continue
        options.append((row.public_id, forms.recipe_label(row)))
        seen.add(row.public_id)
    rows = []
    for index, public_id in enumerate(assigned, start=1):
        rows.append({'position': index, 'public_id': public_id, 'url': recipe_url(public_id)})
    start = len(assigned) + 1
    for extra in range(min(forms.BLANK_SLOTS, forms.MAX_RECIPES - len(assigned))):
        rows.append({'position': start + extra, 'public_id': '', 'url': None})
    return options, forms.signed_labels(assigned, recipes), rows


def render_list(page: int, include_archived: bool, search: str) -> Response:
    rows, has_next = listed_cookbooks(page, include_archived, search)
    return make_response(render_template(
        'admin/kochbuecher.html', family='cafeteria', profile='staff_guest',
        rows=rows, page=page, has_next=has_next, search=search, include_archived=include_archived,
        can_write=can_write(),
        prev_url=url_for('admin.cookbooks_list', archived='1' if include_archived else None, q=search or None, page=page - 1),
        next_url=url_for('admin.cookbooks_list', archived='1' if include_archived else None, q=search or None, page=page + 1),
    ))


def render_editor(public_id: str | None = None, *, confirm: bool = False) -> Response:
    location = store.get_location(db())
    book = store.get_cookbook(db(), public_id) if public_id is not None else None
    if store.get_location(db()) != location:
        raise LocationConflict('Der aktive Standort wurde geändert.')
    writable = can_write()
    if (book is None or confirm) and not writable:
        abort(403)
    status_action = ('cookbook.archive' if book.active else 'cookbook.reactivate') if confirm and book else None
    header_token = recipes_token = status_token = ''
    options: list[tuple[str, str]] = []
    names: dict[str, str] = {}
    assignment_rows: list[dict] = []
    if book is not None:
        options, labels, assignment_rows = assignment_state(book.recipe_public_ids)
        names = dict(options)
    if store.get_location(db()) != location:
        raise LocationConflict('Der aktive Standort wurde geändert.')
    if book is None:
        header_token = sign_context(action='cookbook.create', target=None, expected_location_id=location)
    else:
        target = ObjectExpectation(book.public_id, book.row_version)
        if writable and book.active:
            header_token = sign_context(
                action='cookbook.update', target=target, expected_location_id=location,
            )
            recipes_token = sign_context(
                action='cookbook.recipes', target=target, expected_location_id=location,
                display_values=labels,
            )
        if writable and status_action:
            status_token = sign_context(action=status_action, target=target, expected_location_id=location)
    return make_response(render_template(
        'admin/kochbuch_editor.html', family='cafeteria', profile='staff_guest',
        book=book, can_write=writable, header_token=header_token, recipes_token=recipes_token,
        status_token=status_token, status_action=status_action, options=options, names=names,
        assignment_rows=assignment_rows,
    ))


@protected
def cookbooks_list() -> Response:
    page, include_archived, search = forms.list_arguments()
    return render_list(page, include_archived, search)


@protected
def cookbook_new() -> Response:
    if request.method == 'GET':
        return render_editor()
    try:
        expected = read_context(action='cookbook.create', target_public_id=None)
        payload = forms.parse_cookbook_header(request.form)
        row = store.create_cookbook(
            db(), expected.actor, name=payload['name'], description=payload['description'],
            expected_location_id=expected.expected_location_id,
        )
    except (RecipeValidationError, RecipeConflictError, RecipeNotFoundError) as error:
        return recover(error, create=True)
    return redirect(url_for('admin.cookbook_edit', cookbook_id=row.public_id), 303)


@protected
def cookbook_edit(cookbook_id: str) -> Response:
    public_id = parse_id(cookbook_id)
    if request.method == 'GET':
        return render_editor(public_id)
    try:
        expected = read_context(action='cookbook.update', target_public_id=public_id)
        payload = forms.parse_cookbook_header(request.form)
        row = store.update_cookbook(
            db(), expected.actor, expected.target, name=payload['name'],
            description=payload['description'], expected_location_id=expected.expected_location_id,
        )
    except (RecipeValidationError, RecipeConflictError, RecipeNotFoundError) as error:
        return recover(error, cookbook_id=public_id)
    return redirect(url_for('admin.cookbook_edit', cookbook_id=row.public_id), 303)


@protected
def cookbook_recipes(cookbook_id: str) -> Response:
    public_id = parse_id(cookbook_id)
    try:
        expected = read_context(action='cookbook.recipes', target_public_id=public_id)
        identifiers = forms.parse_cookbook_recipes(request.form)
        row = store.replace_cookbook_recipes(
            db(), expected.actor, expected.target, identifiers,
            expected_location_id=expected.expected_location_id,
        )
    except (RecipeValidationError, RecipeConflictError, RecipeNotFoundError) as error:
        return recover(error, cookbook_id=public_id)
    return redirect(url_for('admin.cookbook_edit', cookbook_id=row.public_id), 303)


@protected
def cookbook_status(cookbook_id: str) -> Response:
    public_id = parse_id(cookbook_id)
    if request.method == 'GET':
        return render_editor(public_id, confirm=True)
    try:
        action = forms.parse_status_action(request.form)
        expected = read_context(action=action, target_public_id=public_id)
        row = store.set_cookbook_active(
            db(), expected.actor, expected.target, active=action == 'cookbook.reactivate',
            expected_location_id=expected.expected_location_id,
        )
    except (RecipeValidationError, RecipeConflictError, RecipeNotFoundError) as error:
        return recover(error, cookbook_id=public_id)
    return redirect(url_for('admin.cookbook_edit', cookbook_id=row.public_id), 303)


RULES = (
    ('/kochbuecher', 'cookbooks_list', cookbooks_list, ['GET']),
    ('/kochbuecher/neu', 'cookbook_new', cookbook_new, ['GET', 'POST']),
    ('/kochbuecher/<cookbook_id>', 'cookbook_edit', cookbook_edit, ['GET', 'POST']),
    ('/kochbuecher/<cookbook_id>/rezepte', 'cookbook_recipes', cookbook_recipes, ['POST']),
    ('/kochbuecher/<cookbook_id>/status', 'cookbook_status', cookbook_status, ['GET', 'POST']),
)


def register_on(target, *, url_prefix: str = '', endpoint_prefix: str = '') -> None:
    for rule, name, view, methods in RULES:
        endpoint = endpoint_prefix + name
        if endpoint in getattr(target, 'view_functions', {}):
            continue
        target.add_url_rule(url_prefix + rule, endpoint=endpoint, view_func=view, methods=methods)


register_on(bp)
