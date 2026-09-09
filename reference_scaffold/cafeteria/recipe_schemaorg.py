"""Pure Schema.org Recipe adapter. No network, no files, no script execution."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any

from .recipe_import_types import RecipeImportIssue, RecipeImportPreview, RecipeImportRow
from .recipe_snapshots import frozen_json
from .recipe_types import RecipeValidationError
from .recipe_values import recipe_minutes, recipe_payload, recipe_text, source as recipe_source

MAX_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 8
_YIELD = re.compile(r'^(\d+) Portionen$')
_TYPE_RECIPE = frozenset({'Recipe', 'http://schema.org/Recipe', 'https://schema.org/Recipe'})


class _FileError(ValueError):
    def __init__(self, field: str, code: str, message: str) -> None:
        self.issue = RecipeImportIssue(None, field, code, message)


class _LdJson(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._on = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'script' and dict(attrs).get('type', '').lower() == 'application/ld+json':
            self._on = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script' and self._on:
            self.blocks.append(''.join(self._buf))
            self._on = False

    def handle_data(self, data: str) -> None:
        if self._on:
            self._buf.append(data)


def _depth(value: object, level: int = 1) -> None:
    if level > MAX_DEPTH:
        raise _FileError('file', 'json_depth', 'JSON-LD darf höchstens acht Ebenen enthalten.')
    if isinstance(value, Mapping):
        for item in value.values():
            _depth(item, level + 1)
    elif isinstance(value, list):
        for item in value:
            _depth(item, level + 1)


def _types(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    return set()


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in pairs:
        if key in result:
            raise _FileError('file', 'duplicate_key', 'Doppelte JSON-Felder sind nicht erlaubt.')
        result[key] = item
    return result


def _load(raw: str) -> object:
    try:
        return json.loads(raw, object_pairs_hook=_pairs)
    except _FileError:
        raise
    except (ValueError, RecursionError):
        raise _FileError('file', 'json_syntax', 'Ungültiges JSON-LD.') from None


def _index_graph(document: object) -> dict[str, dict[str, object]]:
    nodes: dict[str, dict[str, object]] = {}

    def visit(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, Mapping):
            return
        ident = value.get('@id')
        if isinstance(ident, str) and ident:
            existing = nodes.get(ident, {})
            merged = {**existing, **dict(value)}
            nodes[ident] = merged
        if isinstance(value.get('@graph'), list):
            visit(value['@graph'])

    visit(document)
    return nodes


def _resolve(value: object, nodes: dict[str, dict[str, object]], stack: frozenset[str]) -> object:
    if isinstance(value, list):
        return [_resolve(item, nodes, stack) for item in value]
    if not isinstance(value, Mapping):
        return value
    ident = value.get('@id')
    if isinstance(ident, str) and ident in nodes and set(value) <= {'@id'}:
        if ident in stack:
            raise _FileError('file', 'graph_cycle', '@graph-Selbstreferenz ist nicht erlaubt.')
        return _resolve(nodes[ident], nodes, stack | {ident})
    return {key: _resolve(item, nodes, stack) for key, item in value.items()}


def _recipes(document: object) -> list[Mapping[str, object]]:
    found: list[Mapping[str, object]] = []

    def visit(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, Mapping):
            return
        if _types(value.get('@type')) & _TYPE_RECIPE:
            found.append(value)
        graph = value.get('@graph')
        if isinstance(graph, list):
            visit(graph)

    visit(document)
    return found


def _issue(row: int, field: str, code: str, message: str) -> RecipeImportIssue:
    return RecipeImportIssue(row, field, code, message)


def _text(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Mapping) and isinstance(value.get('@value'), str):
        return value['@value'].strip() or None
    return None


def _yield_pair(value: object) -> tuple[str, str]:
    if isinstance(value, Mapping) and (_types(value.get('@type')) & {
        'QuantitativeValue', 'http://schema.org/QuantitativeValue', 'https://schema.org/QuantitativeValue',
    }):
        amount = value.get('value')
        unit = _text(value.get('unitText')) or ''
        if type(amount) is int and amount > 0 and unit == 'Portionen':
            return str(amount), 'PORTION'
        raise RecipeValidationError('Ausbeute ist nicht eindeutig.')
    text = _text(value)
    if text is None:
        raise RecipeValidationError('Ausbeute fehlt.')
    match = _YIELD.fullmatch(text)
    if match is None:
        raise RecipeValidationError('Ausbeute ist nicht eindeutig.')
    return match.group(1), 'PORTION'


def _pull(chunk: str, symbol: str) -> tuple[str, int]:
    if symbol not in chunk:
        return chunk, 0
    left, _, right = chunk.partition(symbol)
    if not left.isdigit() or symbol in right:
        raise RecipeValidationError('Dauer muss ISO-8601 sein.')
    return right, int(left)


def _minutes(value: object) -> int | None:
    if value is None:
        return None
    text = _text(value)
    if text is None or not text.startswith('P') or text in {'P', 'PT'}:
        raise RecipeValidationError('Dauer muss ISO-8601 sein.')
    body = text[1:]
    date_part, _, time_part = body.partition('T') if 'T' in body else (body, '', '')
    if 'T' not in text:
        time_part = ''
    rest, weeks = _pull(date_part, 'W')
    rest, days = _pull(rest, 'D')
    if rest or weeks:
        raise RecipeValidationError('Dauer muss ISO-8601 sein.')
    rest, hours = _pull(time_part, 'H')
    rest, minutes = _pull(rest, 'M')
    rest, seconds = _pull(rest, 'S')
    if rest or seconds:
        raise RecipeValidationError('Dauer muss ISO-8601 sein.')
    return recipe_minutes(days * 1440 + hours * 60 + minutes)


def _ingredients(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    rows = []
    for item in items:
        text = _text(item)
        if isinstance(item, Mapping) and text is None:
            text = _text(item.get('text') or item.get('name'))
        if not text:
            raise RecipeValidationError('Zutatentext fehlt.')
        rows.append({
            'line_public_id': None, 'group_label': None, 'ingredient_text': text,
            'food_public_id': None, 'quantity': None, 'unit_code': None, 'note': None,
        })
    return rows


def _steps(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    rows = []
    for item in items:
        if isinstance(item, Mapping) and (_types(item.get('@type')) & {
            'HowToSection', 'http://schema.org/HowToSection', 'https://schema.org/HowToSection',
        }):
            rows.extend(_steps(item.get('itemListElement')))
            continue
        text = _text(item)
        if isinstance(item, Mapping) and text is None:
            text = _text(item.get('text') or item.get('name'))
        if not text:
            raise RecipeValidationError('Arbeitsschritt fehlt.')
        duration = None
        if isinstance(item, Mapping) and 'performTime' in item:
            duration = _minutes(item.get('performTime'))
        rows.append({'instruction': text, 'duration_minutes': duration, 'image_sha256': None})
    return rows


def _row(recipe: Mapping[str, object], number: int, url: str, fetched_at: str) -> RecipeImportRow:
    errors: list[RecipeImportIssue] = []

    def catch(field: str, action: Any) -> object:
        try:
            return action()
        except RecipeValidationError as error:
            errors.append(_issue(number, field, 'invalid_value', str(error)))
            return None

    title = catch('name', lambda: recipe_text(_text(recipe.get('name')), 120))
    description = catch('description', lambda: recipe_text(_text(recipe.get('description')), 2000, multiline=True, required=False))
    servings = catch('recipeYield', lambda: _yield_pair(recipe.get('recipeYield')))
    prep = catch('prepTime', lambda: _minutes(recipe.get('prepTime')))
    cook = catch('cookTime', lambda: _minutes(recipe.get('cookTime')))
    ingredients = catch('recipeIngredient', lambda: _ingredients(recipe.get('recipeIngredient')))
    steps = catch('recipeInstructions', lambda: _steps(recipe.get('recipeInstructions')))
    src = catch('source_url', lambda: recipe_source({
        'kind': 'url', 'reference': url, 'url': url, 'note': None, 'fetched_at': fetched_at,
    }))
    payload = None
    if not errors and isinstance(title, str) and isinstance(servings, tuple) and isinstance(src, dict):
        built = {
            'title': title, 'description': description,
            'servings': servings[0], 'servings_unit_code': servings[1],
            'prep_minutes': prep, 'cook_minutes': cook, 'source': src,
            'ingredients': [
                {**item, 'source_kind': 'url', 'source_reference': url, 'fetched_at': fetched_at}
                for item in (ingredients or [])
            ],
            'steps': steps or [], 'tag_public_ids': [], 'images': [],
        }
        try:
            payload = frozen_json(recipe_payload(built))
        except RecipeValidationError as error:
            errors.append(_issue(number, 'row', 'invalid_value', str(error)))
    return RecipeImportRow(number, None, payload if not errors else None, tuple(errors))


def parse_schemaorg(document: str, source_url: str, fetched_at: str) -> RecipeImportPreview:
    """Map already-present HTML or JSON-LD text onto RecipeImportPreview."""
    if not isinstance(document, str) or not isinstance(source_url, str) or not isinstance(fetched_at, str):
        issue = RecipeImportIssue(None, 'file', 'type', 'Dokument, Quellenadresse und Abrufzeit sind Pflicht.')
        return RecipeImportPreview(None, None, 'application/ld+json', fetched_at, (), (issue,))
    raw = document.encode('utf-8')
    if not 1 <= len(raw) <= MAX_BYTES:
        issue = RecipeImportIssue(None, 'file', 'size', 'Dokument darf höchstens 2 MiB enthalten.')
        return RecipeImportPreview(None, None, 'application/ld+json', fetched_at, (), (issue,))
    stripped = document.lstrip()
    try:
        if stripped.startswith('<') or '<script' in document.lower():
            parser = _LdJson()
            parser.feed(document)
            parser.close()
            if not parser.blocks:
                raise _FileError('file', 'missing_recipe', 'Kein Schema.org-Rezept gefunden.')
            loaded = [_load(block) for block in parser.blocks]
            data: object = loaded[0] if len(loaded) == 1 else loaded
        else:
            data = _load(document)
        _depth(data)
        nodes = _index_graph(data)
        resolved = _resolve(data, nodes, frozenset())
        recipes = _recipes(resolved)
        if not recipes:
            raise _FileError('file', 'missing_recipe', 'Kein Schema.org-Rezept gefunden.')
    except _FileError as error:
        return RecipeImportPreview(None, None, 'application/ld+json', fetched_at, (), (error.issue,))
    rows = tuple(_row(recipe, index + 1, source_url, fetched_at) for index, recipe in enumerate(recipes))
    return RecipeImportPreview(None, None, 'application/ld+json', fetched_at, rows, ())
