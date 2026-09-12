"""Bounded Dishboard recipe CSV/JSON-v1 previews, without I/O or persistence."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import cast

from .recipe_import_types import (
    RecipeImportDuplicate, RecipeImportIssue, RecipeImportPreview, RecipeImportRow,
)
from .recipe_snapshots import frozen_json
from .recipe_types import IngredientQuantity, RecipeValidationError
from .recipe_values import quantity_pair, recipe_minutes, recipe_payload, recipe_text, timestamp


_FIELDS = ('title', 'description', 'servings', 'servings_unit_code', 'prep_minutes',
           'cook_minutes', 'source_url', 'source_note', 'ingredients', 'steps')
_HEADER = ('schema_version', *_FIELDS)
_INGREDIENT = {'group_label', 'ingredient_text', 'quantity', 'unit_code', 'note'}
_STEP = {'instruction', 'duration_minutes'}
_FILE_LIMIT = 5 * 1024 * 1024
_FIELD_LIMIT = 120 * 1024
_ROW_LIMIT = 2000
_JSON_NUMBER = object()


class _FileError(ValueError):
    def __init__(self, code: str, message: str, field: str = 'file') -> None:
        self.issue = RecipeImportIssue(None, field, code, message)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _FileError('duplicate_key', 'Doppelte JSON-Felder sind nicht erlaubt.')
        result[key] = value
    return result


def _constant(_value: str) -> object:
    raise _FileError('json_number', 'NaN und Infinity sind nicht erlaubt.')


def _json(raw: str) -> object:
    depth, quoted, escaped = 0, False, False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > 12:
                raise _FileError('json_depth', 'JSON darf höchstens zwölf Ebenen enthalten.')
        elif char in ']}':
            depth -= 1
    try:
        # Noninteger JSON numbers are invalid in every v1 field. Keep their type
        # invalid without constructing a float/Decimal or changing its context.
        return json.loads(raw, object_pairs_hook=_pairs, parse_float=lambda _: _JSON_NUMBER,
                          parse_constant=_constant)
    except _FileError:
        raise
    except (ValueError, RecursionError):
        raise _FileError('json_syntax', 'Ungültiges JSON.') from None


def _records(raw: str, mime: str) -> list[tuple[int | None, object]]:
    records: list[tuple[int | None, object]]
    if mime == 'application/json':
        value = _json(raw)
        if (type(value) is not dict or set(value) != {'schema_version', 'recipes'}
                or type(value['schema_version']) is not int or value['schema_version'] != 1
                or type(value['recipes']) is not list):
            raise _FileError('json_schema', 'JSON-Rezeptschema Version 1 erforderlich.')
        records = [(None, row) for row in value['recipes']]
    else:
        reader = csv.reader(io.StringIO(raw, newline=''), delimiter=';', strict=True)
        records = []
        try:
            if next(reader, None) != list(_HEADER):
                raise _FileError('csv_header', 'CSV-Spalten entsprechen nicht dem Rezeptschema Version 1.')
            while True:
                start = reader.line_num + 1
                row = next(reader, None)
                if row is None:
                    break
                if any(len(field.encode('utf-8')) > _FIELD_LIMIT for field in row):
                    raise _FileError('csv_field_size', 'CSV-Felder dürfen höchstens 120 KiB UTF-8 enthalten.')
                records.append((start, row))
                if len(records) > _ROW_LIMIT:
                    break
        except csv.Error:
            raise _FileError('csv_syntax', 'CSV-Struktur oder Feldgröße ist ungültig.') from None
    if not 1 <= len(records) <= _ROW_LIMIT:
        raise _FileError('row_count', 'Die Datei muss zwischen 1 und 2000 Rezeptzeilen enthalten.')
    return records


def _csv_record(value: list[str], number: int) -> tuple[dict[str, object] | None, list[RecipeImportIssue]]:
    if len(value) != len(_HEADER):
        return None, [RecipeImportIssue(number, 'row', 'csv_columns', 'CSV-Zeile hat eine falsche Feldzahl.')]
    errors = []
    if value[0] != '1':
        errors.append(RecipeImportIssue(number, 'schema_version', 'version', 'Schemaversion 1 erforderlich.'))
    result: dict[str, object] = dict(zip(_FIELDS, value[1:], strict=True))
    for field in ('description', 'prep_minutes', 'cook_minutes', 'source_url', 'source_note'):
        if result[field] == '':
            result[field] = None
    for field in ('prep_minutes', 'cook_minutes'):
        text = result[field]
        if isinstance(text, str) and text.isascii() and text.isdecimal() and len(text) <= 5:
            result[field] = int(text)
    for field in ('ingredients', 'steps'):
        try:
            result[field] = _json(cast(str, result[field]))
        except _FileError as error:
            errors.append(RecipeImportIssue(number, field, error.issue.code, error.issue.message))
            result[field] = None
    return result, errors


def _check(errors: list[RecipeImportIssue], number: int, field: str,
           validate: Callable[[], object]) -> object:
    try:
        return validate()
    except RecipeValidationError as error:
        if len(errors) < 16:
            errors.append(RecipeImportIssue(number, field, 'invalid_value', str(error)))
        elif len(errors) == 16:
            errors.append(RecipeImportIssue(number, 'row', 'too_many_errors', 'Weitere Feldfehler vorhanden.'))
        return None


def _fields(value: object, keys: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise RecipeValidationError('Felder fehlen oder sind unerwartet.')
    return value


def _rows(value: object) -> list[object]:
    if type(value) is not list or len(value) > 64:
        raise RecipeValidationError('Eine Liste mit höchstens 64 Einträgen ist erforderlich.')
    return value


def _amount(value: object, code: object, *, required: bool = False) -> IngredientQuantity:
    if value is not None and type(value) is not str:
        raise RecipeValidationError('Dezimale Menge als Text erforderlich.')
    pair = quantity_pair(value, code)
    if required and pair.quantity is None:
        raise RecipeValidationError('Ausbeute erforderlich.')
    return pair


def _source_url(value: object) -> str | None:
    url = recipe_text(value, 2048, required=False)
    if url is not None and not url.startswith(('http://', 'https://')):
        raise RecipeValidationError('HTTP-Quellenadresse erforderlich.')
    return url


def _payload(value: object, number: int, sha: str, when: str,
             errors: list[RecipeImportIssue]) -> Mapping[str, object] | None:
    checked = _check(errors, number, 'row', lambda: _fields(value, set(_FIELDS)))
    if checked is None:
        return None
    row = cast(dict[str, object], checked)
    result: dict[str, object] = {'tag_public_ids': [], 'images': []}
    for field, limit, multiline, required in [('title', 120, False, True), ('description', 2000, True, False)]:
        result[field] = _check(errors, number, field, lambda: recipe_text(row[field], limit, multiline=multiline, required=required))
    pair = cast(IngredientQuantity | None, _check(errors, number, 'servings', lambda: _amount(row['servings'], row['servings_unit_code'], required=True)))
    result['servings'] = str(pair.quantity) if pair else None
    result['servings_unit_code'] = pair.unit_code if pair else None
    for field in ('prep_minutes', 'cook_minutes'):
        result[field] = _check(errors, number, field, lambda: recipe_minutes(row[field]))
    url = _check(errors, number, 'source_url', lambda: _source_url(row['source_url']))
    note = _check(errors, number, 'source_note', lambda: recipe_text(row['source_note'], 400, required=False))
    reference = f'sha256:{sha}:row:{number}'
    result['source'] = {'kind': 'file_import', 'reference': reference, 'url': url,
                        'note': f'sha256:{sha}' + (f'; {note}' if note else ''), 'fetched_at': when}
    for collection in ('ingredients', 'steps'):
        items = _check(errors, number, collection, lambda: _rows(row[collection]))
        converted = []
        for index, item in enumerate(cast(list[object], items or [])):
            path = f'{collection}[{index}]'
            keys = _INGREDIENT if collection == 'ingredients' else _STEP
            fields = _check(errors, number, path, lambda: _fields(item, keys))
            if fields is None:
                continue
            child = cast(dict[str, object], fields)
            output: dict[str, object]
            if collection == 'ingredients':
                output = {'line_public_id': None, 'food_public_id': None,
                          'source_kind': 'file_import', 'source_reference': reference, 'fetched_at': when}
                for field, limit in [('ingredient_text', 500), ('group_label', 120), ('note', 500)]:
                    output[field] = _check(errors, number, f'{path}.{field}', lambda: recipe_text(child[field], limit, required=field == 'ingredient_text'))
                pair = cast(IngredientQuantity | None, _check(errors, number, f'{path}.quantity', lambda: _amount(child['quantity'], child['unit_code'])))
                output['quantity'] = str(pair.quantity) if pair and pair.quantity is not None else None
                output['unit_code'] = pair.unit_code if pair else None
            else:
                output = {'image_sha256': None}
                output['instruction'] = _check(errors, number, f'{path}.instruction', lambda: recipe_text(child['instruction'], 8000, multiline=True))
                output['duration_minutes'] = _check(errors, number, f'{path}.duration_minutes', lambda: recipe_minutes(child['duration_minutes']))
            converted.append(output)
        result[collection] = converted
    if errors:
        return None
    canonical = _check(errors, number, 'row', lambda: recipe_payload(result))
    return cast(Mapping[str, object], frozen_json(canonical)) if canonical is not None else None


def parse_recipe_import(data: bytes, *, filename: str, content_type: str,
                        fetched_at: datetime) -> RecipeImportPreview:
    """Validate an entire preview. No row is imported, matched to the DB, or authorized."""
    name, sha, mime, when = None, None, None, None
    try:
        if type(data) is not bytes or not 0 < len(data) <= _FILE_LIMIT:
            raise _FileError('file_size', 'Datei muss zwischen 1 Byte und 5 MiB enthalten.')
        sha = hashlib.sha256(data).hexdigest()
        if content_type not in ('text/csv', 'application/json'):
            raise _FileError('content_type', 'Nur text/csv und application/json sind erlaubt.', 'content_type')
        mime = content_type
        try:
            name = recipe_text(filename, 200)
            if name in ('.', '..') or name is None or '/' in name or '\\' in name:
                raise RecipeValidationError('Ungültiger Dateiname.')
        except RecipeValidationError:
            raise _FileError('filename', 'Ein Dateiname ohne Pfadangabe ist erforderlich.', 'filename') from None
        try:
            when = timestamp(fetched_at)
            if when is None:
                raise RecipeValidationError('Abrufzeit erforderlich.')
        except RecipeValidationError:
            raise _FileError('fetched_at', 'Abrufzeit mit Zeitzone erforderlich.', 'fetched_at') from None
        try:
            raw = data.decode('utf-8-sig' if mime == 'text/csv' else 'utf-8')
            if '\x00' in raw:
                raise UnicodeError
        except UnicodeError:
            raise _FileError('encoding', 'UTF-8 ohne NUL-Zeichen erforderlich.') from None
        records = _records(raw, mime)
    except _FileError as error:
        return RecipeImportPreview(name, sha, mime, when, errors=(error.issue,))
    rows = []
    titles: dict[str, list[int]] = {}
    for number, (line, value) in enumerate(records, 1):
        errors: list[RecipeImportIssue] = []
        if mime == 'text/csv':
            value, errors = _csv_record(cast(list[str], value), number)
        if isinstance(value, dict):
            try:
                title = recipe_text(value.get('title'), 120)
                if title is not None:
                    titles.setdefault(title.casefold(), []).append(number)
            except RecipeValidationError:
                pass  # The row validator supplies the field error; no duplicate key is inferred.
        payload = _payload(value, number, sha, when, errors)
        rows.append(RecipeImportRow(number, line, payload, tuple(errors)))
    duplicates = tuple(RecipeImportDuplicate(title, tuple(numbers))
                       for title, numbers in titles.items() if len(numbers) > 1)
    return RecipeImportPreview(name, sha, mime, when, tuple(rows), duplicate_groups=duplicates)
