"""Pure recipe input parsing on the existing quantity storage contract."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from .quantities import QuantityError, parse_quantity
from .recipe_types import IngredientQuantity, RecipeValidationError


def parse_ingredient_quantity(
    quantity: str | Decimal | None, unit_code: str | None,
) -> IngredientQuantity:
    """Parse a complete optional pair without resolving or converting its unit."""
    if quantity is None and unit_code is None:
        return IngredientQuantity(None, None)
    if quantity is None or unit_code is None:
        raise RecipeValidationError('Menge und Einheit müssen gemeinsam angegeben werden.')
    if not isinstance(unit_code, str) or re.fullmatch(r'[A-Z][A-Z0-9_]{0,15}', unit_code) is None:
        raise RecipeValidationError('Einheitencode hat ein ungültiges Format.')
    try:
        amount = parse_quantity(quantity)
    except QuantityError as error:
        raise RecipeValidationError(str(error)) from error
    return IngredientQuantity(amount, unit_code)


def recipe_text(value: object, maximum: int, *, multiline: bool = False, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise RecipeValidationError('Text erforderlich.')
    value = unicodedata.normalize('NFC', value)
    if multiline:
        value = value.replace('\r\n', '\n').replace('\r', '\n')
    if any(char in '<>' or (unicodedata.category(char).startswith('C') and not (multiline and char == '\n')) for char in value):
        raise RecipeValidationError('Ungültiges Textzeichen.')
    value = value.strip() if multiline else ' '.join(value.split())
    if len(value) > maximum or (required and not value):
        raise RecipeValidationError('Ungültige Textlänge.')
    return value


def recipe_minutes(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 10080:
        raise RecipeValidationError('Minuten müssen zwischen 0 und 10080 liegen.')
    return value


def identifier(value: object) -> str:
    if not isinstance(value, str):
        raise RecipeValidationError('UUID erforderlich.')
    try:
        return str(UUID(value))
    except ValueError:
        raise RecipeValidationError('Ungültige UUID.') from None


def positive(value: object) -> int:
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise RecipeValidationError('Positive Originalversion erforderlich.')
    return value


def object_fields(value: object, fields: set[str]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise RecipeValidationError('Felder fehlen oder sind unerwartet.')
    return dict(value)


def rows(value: object) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > 64:
        raise RecipeValidationError('Höchstens 64 Einträge erforderlich.')
    return list(value)


def timestamp(value: object) -> str | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.isoformat()
    except ValueError:
        raise RecipeValidationError('Zeitpunkt mit Zeitzone erforderlich.') from None


def source(value: object) -> dict[str, object]:
    result = object_fields(value, {'kind', 'reference', 'url', 'note', 'fetched_at'})
    if result['kind'] not in ('manual', 'url', 'file_import', 'ai_assisted'):
        raise RecipeValidationError('Ungültige Quelle.')
    for field, limit in [('reference', 200), ('url', 2048), ('note', 500)]:
        result[field] = recipe_text(result[field], limit, required=False)
    result['fetched_at'] = timestamp(result['fetched_at'])
    if result['url'] is not None and re.match(r'^https?://', str(result['url'])) is None:
        raise RecipeValidationError('HTTP-Quellenadresse erforderlich.')
    if result['kind'] != 'manual' and (not result['reference'] or not result['fetched_at']):
        raise RecipeValidationError('Quellenbeleg fehlt.')
    if result['kind'] == 'url' and not result['url']:
        raise RecipeValidationError('Quellenadresse fehlt.')
    if result['kind'] in ('file_import', 'ai_assisted') and not result['note']:
        raise RecipeValidationError('Quellennotiz fehlt.')
    return result


def image_fields(value: object) -> dict[str, object]:
    result = object_fields(value, {'sha256', 'caption', 'source_url', 'source_license', 'fetched_at'})
    if not isinstance(result['sha256'], str) or re.fullmatch('[0-9a-f]{64}', result['sha256']) is None:
        raise RecipeValidationError('Ungültiger Bildhash.')
    for field, limit in [('caption', 500), ('source_url', 2048), ('source_license', 500)]:
        result[field] = recipe_text(result[field], limit, required=False)
    result['fetched_at'] = timestamp(result['fetched_at'])
    if result['source_url'] and (re.match(r'^https?://', str(result['source_url'])) is None or not result['source_license'] or not result['fetched_at']):
        raise RecipeValidationError('Bildquelle benötigt Lizenz und Abrufzeit.')
    return result


def quantity_pair(amount: object, code: object) -> IngredientQuantity:
    if amount is not None and not isinstance(amount, (str, Decimal)):
        raise RecipeValidationError('Dezimale Menge als Text erforderlich.')
    if code is not None and not isinstance(code, str):
        raise RecipeValidationError('Einheitencode als Text erforderlich.')
    return parse_ingredient_quantity(amount, code)


def recipe_payload(value: object) -> dict[str, object]:
    result = object_fields(value, {'title', 'description', 'servings', 'servings_unit_code', 'prep_minutes', 'cook_minutes', 'source', 'ingredients', 'steps', 'tag_public_ids', 'images'})
    result['title'] = recipe_text(result['title'], 120)
    result['description'] = recipe_text(result['description'], 2000, multiline=True, required=False)
    amount = quantity_pair(result['servings'], result['servings_unit_code'])
    if amount.quantity is None:
        raise RecipeValidationError('Ausbeute erforderlich.')
    result['servings'], result['servings_unit_code'] = str(amount.quantity), amount.unit_code
    for field in ['prep_minutes', 'cook_minutes']:
        result[field] = recipe_minutes(result[field])
    result['source'] = source(result['source'])
    ingredients = []
    for value in rows(result['ingredients']):
        row = object_fields(value, {'line_public_id', 'group_label', 'ingredient_text', 'food_public_id', 'quantity', 'unit_code', 'note', 'source_kind', 'source_reference', 'fetched_at'})
        if row['line_public_id'] is not None:
            row['line_public_id'] = identifier(row['line_public_id'])
        row['ingredient_text'] = recipe_text(row['ingredient_text'], 500)
        for field, limit in [('group_label', 120), ('note', 500), ('source_reference', 200)]:
            row[field] = recipe_text(row[field], limit, required=False)
        if row['food_public_id'] is not None:
            row['food_public_id'] = identifier(row['food_public_id'])
        amount = quantity_pair(row['quantity'], row['unit_code'])
        row['quantity'], row['unit_code'] = str(amount.quantity) if amount.quantity is not None else None, amount.unit_code
        row['fetched_at'] = timestamp(row['fetched_at'])
        if row['source_kind'] not in ('manual', 'url', 'file_import', 'ai_assisted') or (row['source_kind'] != 'manual' and (not row['source_reference'] or not row['fetched_at'])):
            raise RecipeValidationError('Quellenbeleg der Zutat fehlt.')
        ingredients.append(row)
    result['ingredients'] = ingredients
    steps = []
    for value in rows(result['steps']):
        row = object_fields(value, {'instruction', 'duration_minutes', 'image_sha256'})
        row['instruction'] = recipe_text(row['instruction'], 8000, multiline=True)
        row['duration_minutes'] = recipe_minutes(row['duration_minutes'])
        if row['image_sha256'] is not None and (not isinstance(row['image_sha256'], str) or re.fullmatch('[0-9a-f]{64}', row['image_sha256']) is None):
            raise RecipeValidationError('Ungültiger Schrittbildhash.')
        steps.append(row)
    result['steps'] = steps
    tags = [identifier(value) for value in rows(result['tag_public_ids'])]
    if len(tags) != len(set(tags)):
        raise RecipeValidationError('Doppelte Tags.')
    result['tag_public_ids'] = sorted(tags)
    result['images'] = [image_fields(value) for value in rows(result['images'])]
    return result
