"""Native Tabler recipe list/editor consuming the frozen R1/A1 contracts."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import abort, current_app, redirect, render_template, request, url_for
from werkzeug.datastructures import MultiDict

from .. import master_data_store as masters, recipe_store as store
from ..master_data_types import ObjectExpectation
from ..recipe_types import RecipeConflictError, RecipeValidationError
from ..recipe_values import identifier
from ..roles import capabilities
from ..security import csrf_token
from . import recipe_forms as forms
from .recipe_errors import protected
from .recipe_form_rows import apply_row_action
from .routes import bp


def _engine():
    return current_app.extensions['cafeteria_db']


def _recipe_id(value):
    try:
        return identifier(value)
    except RecipeValidationError:
        abort(404)


def _can_write() -> bool:
    allowed = capabilities()
    return '*' in allowed or 'recipe.write' in allowed


def _query(allowed: set[str]) -> None:
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        abort(400)


def _all(reader, *args) -> list:
    result, offset = [], 0
    while True:
        batch = reader(_engine(), *args, include_archived=True, limit=500, offset=offset)
        result.extend(batch)
        if len(batch) < 500:
            return result
        offset += 500


def _flat(payload: Mapping[str, Any]) -> MultiDict[str, str]:
    result: MultiDict[str, str] = MultiDict()
    for key, value in payload.items():
        if key == 'source':
            for field, entry in value.items():
                result.add('source.' + field, '' if entry is None else str(entry))
        elif key in forms.ROWS:
            for index, row in enumerate(value):
                for field, entry in row.items():
                    result.add(f'{key}.{index}.{field}', '' if entry is None else str(entry))
        elif key == 'tag_public_ids':
            for entry in value:
                result.add(key, entry)
        else:
            result.add(key, '' if value is None else str(value))
    return result


def _empty() -> MultiDict[str, str]:
    data = MultiDict((key, '') for key in forms.HEAD)
    for field in forms.SOURCE:
        data['source.' + field] = 'manual' if field == 'kind' else ''
    return data


def _choices(data: MultiDict[str, str]) -> dict[str, list[tuple[str, str]]]:
    selected = set(value for _, value in data.items(multi=True))
    result = {}
    for kind, rows in [('units', _all(masters.list_units)), ('foods', _all(masters.list_foods)),
                       ('tags', _all(masters.list_vocabulary, 'tag'))]:
        result[kind] = [(row.code if kind == 'units' else row.public_id,
                         (row.display_name if kind == 'units' else row.name) + (' · archiviert' if not row.active else ''))
                        for row in rows if row.active or (row.code if kind == 'units' else row.public_id) in selected]
    known_tags = {key for key, _ in result['tags']}
    result['tags'].extend((key, 'Ursprüngliche Auswahl · nicht mehr verfügbar')
                          for key in data.getlist('tag_public_ids') if key not in known_tags)
    return result


def _render_editor(data, recipe_id=None, *, active=True, confirmation=False, choices=None):
    payload = forms.parse_recipe_form(data, structural_only=True)
    if choices is None:
        choices = _choices(data) if not confirmation else {}
    image_names = {row['sha256']: row['caption'] or f'Bild {index + 1}'
                   for index, row in enumerate(payload['images']) if row['sha256']}
    for row in payload['steps']:
        if row['image_sha256']:
            image_names.setdefault(row['image_sha256'], 'Bestehendes Schrittbild')
    endpoints = current_app.view_functions
    links = {name: url_for('admin.' + name, recipe_id=recipe_id) for name in
             ('recipe_images', 'recipe_revisions', 'recipe_scale')
             if recipe_id and 'admin.' + name in endpoints}
    return render_template('admin/rezepte_editor.html', family='cafeteria', profile='staff_guest',
        data=data, payload=payload, recipe_id=recipe_id, active=active, confirmation=confirmation,
        can_write=_can_write(), choices=choices, image_names=image_names, links=links,
        action='recipe.update' if recipe_id else 'recipe.create',
        source_names={'manual': 'Manuell erfasst', 'url': 'Quellenadresse', 'file_import': 'Dateiimport', 'ai_assisted': 'KI-unterstützte Vorlage'})


def _get_editor(recipe_id=None, *, confirmation=False):
    location = store.get_location(_engine())
    row = store.get_recipe(_engine(), recipe_id) if recipe_id else None
    data = _flat(row.payload) if row else _empty()
    purpose = ('recipe.archive' if row.active else 'recipe.reactivate') if confirmation else (
        'recipe.update' if row else 'recipe.create')
    choice_rows = _choices(data)
    selected = set(value for _, value in data.items(multi=True))
    choices = [item for kind in ('foods', 'tags', 'units') for item in choice_rows[kind]]
    labels = {key: label for key, label in choices if key in selected}
    image_labels = [(image['sha256'], image['caption'] or f'Bild {index + 1}')
                    for index, image in enumerate(row.payload['images'])] if row else []
    # Original selected names take priority; optional names never truncate form values.
    for key, label in image_labels + choices:
        if len(labels) == 256:
            break  # Frozen A1 display metadata budget; unresolved references remain copyable.
        labels.setdefault(key, label)
    if store.get_location(_engine()) != location:
        raise forms.LocationConflict('Der Standort wurde während des Ladens geändert. Bitte neu laden.')
    data['_csrf'] = csrf_token()
    data['_form_context'] = forms.sign_context(action=purpose,
        target=ObjectExpectation(row.public_id, row.row_version) if row else None,
        expected_location_id=location, display_values=labels)
    if row:
        data['row_version'] = str(row.row_version)
    return _render_editor(data, row.public_id if row else None, active=row.active if row else True,
                          confirmation=confirmation, choices=choice_rows)


@bp.get('/rezepte')
@protected
def recipes_list():
    _query({'q', 'ingredient', 'tag', 'archived', 'page'})
    raw_page = request.args.get('page', '1')
    if not raw_page.isascii() or not raw_page.isdecimal() or len(raw_page) > 6 or not 1 <= int(raw_page) <= 100000:
        abort(400)
    archived = request.args.get('archived', '0')
    if archived not in ('0', '1'):
        abort(400)
    page, query = int(raw_page), request.args.get('q', '')
    ingredient, tag = request.args.get('ingredient', ''), request.args.get('tag', '')
    tag = identifier(tag) if tag else ''
    rows = store.list_recipes(_engine(), search=query, ingredient=ingredient, tag=tag,
                             include_archived=archived == '1', limit=51, offset=(page - 1) * 50)
    tags = [(row.public_id, row.name + (' · archiviert' if not row.active else ''))
            for row in _all(masters.list_vocabulary, 'tag')]
    if tag and tag not in {key for key, _ in tags}:
        tags.append((tag, 'Ausgewählter Tag · nicht mehr verfügbar'))
    filters = {'q': query, 'ingredient': ingredient, 'tag': tag, 'archived': archived}
    return render_template('admin/rezepte.html', family='cafeteria', profile='staff_guest', rows=rows[:50],
        page=page, has_next=len(rows) > 50, query=query, ingredient=ingredient, tag=tag, tags=tags,
        archived=archived == '1', can_write=_can_write(),
        prev_url=url_for('admin.recipes_list', **filters, page=page - 1),
        next_url=url_for('admin.recipes_list', **filters, page=page + 1))


@bp.route('/rezepte/neu', methods=['GET', 'POST'])
@protected
def recipe_new():
    _query(set())
    if request.method == 'GET':
        return _get_editor()
    expected = forms.read_context(action='recipe.create', target_public_id=None)
    result = store.create_recipe(_engine(), expected.actor, forms.parse_recipe_form(request.form),
                                 expected_location_id=expected.expected_location_id)
    return redirect(url_for('admin.recipe_edit', recipe_id=result.public_id), 303)


@bp.route('/rezepte/<recipe_id>', methods=['GET', 'POST'])
@protected
def recipe_edit(recipe_id):
    recipe_id = _recipe_id(recipe_id)
    _query(set())
    if request.method == 'GET':
        return _get_editor(recipe_id)
    expected = forms.read_context(action='recipe.update', target_public_id=recipe_id)
    result = store.update_recipe(_engine(), expected.actor, expected.target, forms.parse_recipe_form(request.form),
                                 expected_location_id=expected.expected_location_id)
    return redirect(url_for('admin.recipe_edit', recipe_id=result.public_id), 303)


@bp.post('/rezepte/formular')
@protected
def recipe_form_rows():
    _query({'action', 'recipe_id', 'row_kind', 'row_action', 'row_index'})
    if set(request.args) - {'recipe_id'} != {'action', 'row_kind', 'row_action', 'row_index'}:
        abort(400)
    if {'row_kind', 'row_action', 'row_index'} & set(request.form):
        abort(400)
    action = request.args['action']
    recipe_id = request.args.get('recipe_id')
    data = MultiDict(request.form)
    for key in ('row_kind', 'row_action', 'row_index'):
        data[key] = request.args[key]
    data = apply_row_action(data, action=action, target_public_id=recipe_id)
    if recipe_id:
        current = store.get_recipe(_engine(), recipe_id)
        if not current.active or current.row_version != int(data['row_version']):
            raise RecipeConflictError('Das Rezept wurde geändert oder archiviert. Ihre ursprünglichen Eingaben bleiben erhalten.')
    # No new form token/CAS is issued by this POST; values are the original draft.
    return _render_editor(data, recipe_id)


@bp.route('/rezepte/<recipe_id>/status', methods=['GET', 'POST'])
@protected
def recipe_status(recipe_id):
    recipe_id = _recipe_id(recipe_id)
    _query(set())
    if not _can_write():
        abort(403)
    if request.method == 'GET':
        return _get_editor(recipe_id, confirmation=True)
    if set(request.form) != {'_csrf', '_form_context', 'row_version', 'active'} or len(request.form.getlist('active')) != 1:
        abort(400)
    active = request.form['active']
    if active not in ('0', '1'):
        abort(400)
    expected = forms.read_context(action='recipe.reactivate' if active == '1' else 'recipe.archive', target_public_id=recipe_id)
    store.set_recipe_active(_engine(), expected.actor, expected.target, active=active == '1', expected_location_id=expected.expected_location_id)
    return redirect(url_for('admin.recipe_edit', recipe_id=recipe_id), 303)
