"""Pure adapter: structured extraction JSON → RecipeImportPreview. No provider I/O."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

from .recipe_import_types import RecipeImportIssue, RecipeImportPreview, RecipeImportRow
from .recipe_snapshots import frozen_json
from .recipe_types import RecipeValidationError
from .recipe_values import recipe_minutes, recipe_payload, recipe_text, source as recipe_source

_SHA = re.compile(r'^[0-9a-f]{64}$')
_ALLOWED = frozenset({
    'document_sha256', 'page', 'line', 'note', 'fetched_at', 'model', 'recipes',
})
_RECIPE_KEYS = frozenset({
    'title', 'description', 'servings', 'servings_unit_code', 'prep_minutes',
    'cook_minutes', 'ingredients', 'steps', 'nutrition', 'allergens',
})


def _issue(row: int | None, field: str, code: str, message: str) -> RecipeImportIssue:
    return RecipeImportIssue(row, field, code, message)


def parse_ai_extraction(document: object) -> RecipeImportPreview:
    """Map an already-present structured extraction result onto the import DTO."""
    if isinstance(document, (bytes, bytearray)):
        return RecipeImportPreview(None, None, 'application/json', None, (), (
            _issue(None, 'file', 'type', 'Strukturiertes JSON-Objekt ist Pflicht.'),
        ))
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except (ValueError, RecursionError):
            return RecipeImportPreview(None, None, 'application/json', None, (), (
                _issue(None, 'file', 'json_syntax', 'Ungültiges JSON.'),
            ))
    if not isinstance(document, Mapping):
        return RecipeImportPreview(None, None, 'application/json', None, (), (
            _issue(None, 'file', 'type', 'Strukturiertes JSON-Objekt ist Pflicht.'),
        ))
    extra = set(document) - _ALLOWED
    if extra:
        return RecipeImportPreview(None, None, 'application/json', None, (), (
            _issue(None, 'file', 'unexpected', 'Unerwartetes Feld.'),
        ))
    sha = document.get('document_sha256')
    note = document.get('note')
    fetched = document.get('fetched_at')
    file_errors: list[RecipeImportIssue] = []
    if not isinstance(sha, str) or _SHA.fullmatch(sha) is None:
        file_errors.append(_issue(None, 'document_sha256', 'missing_source', 'Quellbezug fehlt.'))
    if not isinstance(note, str) or not note.strip():
        file_errors.append(_issue(None, 'note', 'missing_note', 'Quellennotiz fehlt.'))
    recipes = document.get('recipes')
    if not isinstance(recipes, Sequence) or isinstance(recipes, (str, bytes)) or not recipes:
        file_errors.append(_issue(None, 'recipes', 'missing_recipes', 'Mindestens ein Rezeptkopf ist Pflicht.'))
        recipes = ()
    if file_errors:
        return RecipeImportPreview(None, sha if isinstance(sha, str) else None, 'application/json', None, (), tuple(file_errors))
    page = document.get('page')
    line = document.get('line')
    reference = f'sha256:{sha}'
    if type(page) is int:
        reference += f':page:{page}'
    if type(line) is int:
        reference += f':line:{line}'
    rows = tuple(
        _row(item, index + 1, sha, note, fetched, reference)
        for index, item in enumerate(recipes)
    )
    return RecipeImportPreview(None, sha, 'application/json', fetched if isinstance(fetched, str) else None, rows, ())


def _row(
    item: object, number: int, sha: str, note: str, fetched: object, reference: str,
) -> RecipeImportRow:
    errors: list[RecipeImportIssue] = []
    if not isinstance(item, Mapping):
        return RecipeImportRow(number, None, None, (_issue(number, 'row', 'type', 'Rezeptkopf muss ein Objekt sein.'),))
    extra = set(item) - _RECIPE_KEYS
    if extra:
        errors.append(_issue(number, 'row', 'unexpected', 'Unerwartetes Feld.'))
    if item.get('allergens') is not None:
        errors.append(_issue(number, 'allergens', 'suggestion', 'Allergene werden nicht automatisch bestätigt.'))
    if item.get('nutrition') is not None:
        errors.append(_issue(number, 'nutrition', 'suggestion', 'Nährwerte bleiben unbestätigte Vorschläge.'))

    def catch(field: str, action):
        try:
            return action()
        except RecipeValidationError as error:
            errors.append(_issue(number, field, 'invalid_value', str(error)))
            return None

    title = catch('title', lambda: recipe_text(item.get('title'), 120, required=False))
    description = catch('description', lambda: recipe_text(item.get('description'), 2000, multiline=True, required=False))
    servings = item.get('servings')
    unit = item.get('servings_unit_code')
    prep = catch('prep_minutes', lambda: recipe_minutes(item.get('prep_minutes')))
    cook = catch('cook_minutes', lambda: recipe_minutes(item.get('cook_minutes')))
    src = catch('source', lambda: recipe_source({
        'kind': 'ai_assisted', 'reference': reference, 'url': None, 'note': note, 'fetched_at': fetched,
    }))
    ingredients, ingredient_uncertain = _ingredients(item.get('ingredients'), number, reference, fetched, errors)
    steps = catch('steps', lambda: _steps(item.get('steps')))
    payload = None
    if title and servings is not None and unit and isinstance(src, dict):
        built = {
            'title': title, 'description': description, 'servings': servings,
            'servings_unit_code': unit, 'prep_minutes': prep, 'cook_minutes': cook,
            'source': src, 'ingredients': ingredients, 'steps': steps or [],
            'tag_public_ids': [], 'images': [],
        }
        try:
            payload = frozen_json(recipe_payload(built))
        except RecipeValidationError as error:
            errors.append(_issue(number, 'row', 'invalid_value', str(error)))
            payload = None
    if payload is None and not errors:
        errors.append(_issue(number, 'row', 'incomplete', 'Unvollständiger Rezeptkopf bleibt editierbar.'))
    if ingredient_uncertain:
        errors.append(_issue(number, 'ingredients', 'unresolved', 'Unaufgelöste Zutat verhindert den bestätigten Import.'))
    return RecipeImportRow(number, None, payload, tuple(errors))


def _ingredients(
    value: object, number: int, reference: str, fetched: object, errors: list[RecipeImportIssue],
) -> tuple[list[dict[str, object]], bool]:
    if value is None:
        return [], False
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        errors.append(_issue(number, 'ingredients', 'type', 'Zutaten müssen eine Liste sein.'))
        return [], False
    rows: list[dict[str, object]] = []
    uncertain = False
    for index, item in enumerate(value):
        path = f'ingredients[{index}]'
        if not isinstance(item, Mapping):
            errors.append(_issue(number, path, 'type', 'Zutat muss ein Objekt sein.'))
            continue
        text = item.get('ingredient_text') or item.get('text')
        food = item.get('food_public_id')
        try:
            ingredient_text = recipe_text(text, 500)
        except RecipeValidationError as error:
            errors.append(_issue(number, f'{path}.ingredient_text', 'invalid_value', str(error)))
            continue
        if food is None or item.get('uncertainty'):
            uncertain = True
            errors.append(_issue(number, path, 'uncertainty', 'Zutat ist nicht zugeordnet.'))
        rows.append({
            'line_public_id': None, 'group_label': None, 'ingredient_text': ingredient_text,
            'food_public_id': food if isinstance(food, str) else None,
            'quantity': item.get('quantity'), 'unit_code': item.get('unit_code'),
            'note': None, 'source_kind': 'ai_assisted', 'source_reference': reference,
            'fetched_at': fetched,
        })
    return rows, uncertain


def _steps(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RecipeValidationError('Schritte müssen eine Liste sein.')
    rows = []
    for item in value:
        if isinstance(item, str):
            rows.append({'instruction': recipe_text(item, 8000, multiline=True), 'duration_minutes': None, 'image_sha256': None})
            continue
        if not isinstance(item, Mapping):
            raise RecipeValidationError('Arbeitsschritt fehlt.')
        rows.append({
            'instruction': recipe_text(item.get('instruction') or item.get('text'), 8000, multiline=True),
            'duration_minutes': recipe_minutes(item.get('duration_minutes')),
            'image_sha256': None,
        })
    return rows
