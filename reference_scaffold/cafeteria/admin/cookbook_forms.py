"""Native cookbook header and ordered recipe-assignment forms."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from flask import abort, request
from werkzeug.datastructures import MultiDict

from .. import recipe_values as values
from ..recipe_types import RecipeValidationError
from .recipe_forms import FormError

PAGE_SIZE = 50
BLANK_SLOTS = 3
MAX_RECIPES = 64
CONTROL = frozenset({'_csrf', '_form_context', 'row_version'})
HEADER_FIELDS = frozenset({'name', 'description'})
RECIPE_FIELDS = frozenset({'recipe_public_ids', 'recipe_positions'})
UNKNOWN_RECIPE = 'Rezept ohne Anzeigenamen'
STATUS_ACTIONS = frozenset({'cookbook.archive', 'cookbook.reactivate'})


def _checked(field: str, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except RecipeValidationError as error:
        raise FormError(str(error), field) from error


def _reject_size(form: MultiDict[str, str]) -> None:
    if len(list(form.items(multi=True))) > 400:
        raise FormError('Zu viele Formularfelder.')
    for key, value in form.items(multi=True):
        maximum = 200000 if key == '_form_context' else 16000
        if not isinstance(value, str) or len(value) > maximum:
            raise FormError('Formularwert ist zu groß.', key)


def _single_controls(form: MultiDict[str, str]) -> None:
    for key in CONTROL & set(form):
        if len(form.getlist(key)) != 1:
            raise FormError('Steuerfeld ist mehrfach vorhanden.', key)


def parse_cookbook_header(form: MultiDict[str, str]) -> dict[str, str | None]:
    _reject_size(form)
    unexpected = sorted(set(form) - CONTROL - HEADER_FIELDS)
    if unexpected:
        raise FormError('Unerwartetes Formularfeld.', unexpected[0])
    _single_controls(form)
    for field in HEADER_FIELDS:
        if len(form.getlist(field)) != 1:
            raise FormError('Feld fehlt oder ist mehrfach vorhanden.', field)
    return {
        'name': _checked('name', values.recipe_text, form['name'] or None, 120),
        'description': _checked(
            'description', values.recipe_text, form['description'] or None, 2000,
            multiline=True, required=False,
        ),
    }


def parse_cookbook_recipes(form: MultiDict[str, str]) -> list[str]:
    _reject_size(form)
    unexpected = sorted(set(form) - CONTROL - RECIPE_FIELDS)
    if unexpected:
        raise FormError('Unerwartetes Formularfeld.', unexpected[0])
    _single_controls(form)
    identifiers = form.getlist('recipe_public_ids')
    positions = form.getlist('recipe_positions')
    if len(identifiers) != len(positions):
        raise FormError('Rezept und Position müssen paarweise vorliegen.', 'recipe_positions')
    ordered: list[tuple[int, int, str]] = []
    for index, (raw_id, raw_position) in enumerate(zip(identifiers, positions)):
        if raw_id == '':
            continue
        if not re.fullmatch(r'[1-9][0-9]{0,8}', raw_position):
            raise FormError('Position muss eine eindeutige positive Zahl sein.', 'recipe_positions')
        ordered.append((int(raw_position), index, _checked('recipe_public_ids', values.identifier, raw_id)))
    if len(ordered) > MAX_RECIPES:
        raise FormError('Höchstens 64 Rezepte.', 'recipe_public_ids')
    if len({item[0] for item in ordered}) != len(ordered):
        raise FormError('Positionen müssen eindeutig sein.', 'recipe_positions')
    if len({item[2] for item in ordered}) != len(ordered):
        raise FormError('Rezeptzuordnungen müssen eindeutig sein.', 'recipe_public_ids')
    ordered.sort()
    return [item[2] for item in ordered]


def parse_status_action(form: MultiDict[str, str]) -> str:
    _reject_size(form)
    unexpected = sorted(set(form) - CONTROL - {'status_action'})
    if unexpected:
        raise FormError('Unerwartetes Formularfeld.', unexpected[0])
    _single_controls(form)
    if len(form.getlist('status_action')) != 1 or form['status_action'] not in STATUS_ACTIONS:
        raise FormError('Ungültiger Formularzweck.', 'status_action')
    return form['status_action']


def list_arguments() -> tuple[int, bool, str]:
    args = request.args
    allowed = {'page', 'archived', 'q'}
    if set(args) - allowed or any(len(args.getlist(key)) != 1 for key in args):
        abort(400)
    archived = args.get('archived', '0')
    if archived not in ('0', '1'):
        abort(400)
    raw_page = args.get('page', '1')
    if not re.fullmatch(r'[1-9][0-9]{0,5}', raw_page):
        abort(400)
    search = args.get('q', '')
    if len(search) > 200:
        abort(400)
    return int(raw_page), archived == '1', search


def recipe_label(row: object | None) -> str:
    if row is None:
        return UNKNOWN_RECIPE
    payload = getattr(row, 'payload', None)
    title = payload.get('title') if isinstance(payload, Mapping) else None
    name = title if isinstance(title, str) and title.strip() else UNKNOWN_RECIPE
    if not getattr(row, 'active', True):
        name += ' (archiviert)'
    return name


def signed_labels(assigned: Sequence[str], recipes: Sequence[object]) -> dict[str, str]:
    by_id = {getattr(row, 'public_id'): row for row in recipes}
    labels: dict[str, str] = {}
    for public_id in assigned:
        labels[public_id] = recipe_label(by_id.get(public_id))
        if len(labels) >= 256:
            return labels
    for row in recipes:
        public_id = getattr(row, 'public_id')
        if public_id in labels or not getattr(row, 'active', False):
            continue
        labels[public_id] = recipe_label(row)
        if len(labels) >= 256:
            break
    return labels
