"""Read-only presentation of recipe yields; no unit conversion or persistence."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, cast

from ..quantities import FoodFactors, QuantityError, Unit, _arithmetic, convert, parse_factor, parse_quantity, scale_servings
from ..recipe_snapshot_v2 import verified_prepared
from ..recipe_types import RecipeConfigurationError, RecipeRevisionDTO
from .recipe_forms import FormError


def scaled_recipe(payload: Mapping[str, object], target: str | None = None, *,
                  revision: RecipeRevisionDTO | None = None) -> dict[str, Any]:
    try:
        if target is not None:
            wanted = parse_quantity(target)
        else:
            wanted = None
    except QuantityError as error:
        raise FormError(str(error), 'yield') from None
    try:
        source = parse_quantity(str(payload['servings']))
        wanted = source if wanted is None else wanted
        ingredients = payload['ingredients']
        if not isinstance(ingredients, Sequence) or isinstance(ingredients, (str, bytes)):
            raise ValueError
        result = []
        for ingredient in ingredients:
            if not isinstance(ingredient, Mapping):
                raise ValueError
            original = ingredient['quantity']
            amount = parse_quantity(str(original)) if original is not None else None
            result.append({'ingredient': ingredient, 'original': original, 'unit': ingredient['unit_code'],
                           'scaled': format(scale_servings(amount, source, wanted), 'f') if amount is not None else None})
        calculated = {'source': format(source, 'f'), 'target': format(wanted, 'f'),
                      'unit': payload['servings_unit_code'], 'rows': result}
        if revision is not None and revision.snapshot.get('schema_version') == 2:
            if payload != revision.snapshot['recipe']:
                raise RecipeConfigurationError('Rezept und Revisionsstand passen nicht zusammen.')
            calculated['prepared'] = _prepared(revision, calculated)
        return calculated
    except (QuantityError, KeyError, TypeError, ValueError):
        raise RecipeConfigurationError('Gespeicherte Rezeptmengen sind nicht verfügbar.') from None


def _unit(snapshot: Mapping[str, object], code: str) -> Unit:
    units = cast(Sequence[Mapping[str, Any]], snapshot['units'])
    selected = [unit for unit in units if unit['code'] == code]
    if len(selected) != 1:
        raise QuantityError('Die gespeicherte Einheit fehlt oder ist mehrdeutig.')
    unit = selected[0]
    factor = unit['base_factor']
    return Unit(code, unit['dimension'], parse_factor(factor) if factor is not None else None)


def _prepared(revision: RecipeRevisionDTO, calculated: dict[str, Any]) -> list[dict[str, Any]]:
    index = {child.public_id: child for child in verified_prepared(revision)}
    pending = [(revision, calculated)]
    result = []
    while pending:
        parent, amounts = pending.pop(0)
        if parent.snapshot['schema_version'] == 1:
            continue
        foods = {food['public_id']: food for food in cast(Sequence[Mapping[str, Any]], parent.snapshot['foods'])}
        for row in amounts['rows']:
            food = foods[row['ingredient']['food_public_id']]
            pin = food['prepared_recipe']
            if pin is None:
                continue
            child = index[pin['revision_public_id']]
            recipe = cast(Mapping[str, Any], child.snapshot['recipe'])
            factors = FoodFactors(
                parse_factor(food['density_g_per_ml']) if food['density_g_per_ml'] is not None else None,
                parse_factor(food['piece_weight_g']) if food['piece_weight_g'] is not None else None,
            )
            wanted = convert(Decimal(row['scaled']), _unit(parent.snapshot, row['unit']),
                             _unit(child.snapshot, recipe['servings_unit_code']), factors)
            source = parse_quantity(recipe['servings'])
            # Computed targets are not storage input; periodic results retain 50-digit precision.
            with _arithmetic():
                rows = [{'ingredient': ingredient, 'original': ingredient['quantity'], 'unit': ingredient['unit_code'],
                         'scaled': format(parse_quantity(ingredient['quantity']) * wanted / source, 'f')
                         if ingredient['quantity'] is not None else None} for ingredient in recipe['ingredients']]
            values = {'source': format(source, 'f'), 'target': format(wanted, 'f'),
                      'unit': recipe['servings_unit_code'], 'rows': rows}
            result.append({'revision': child, 'recipe': recipe, 'calculated': values,
                           'for_ingredient': row['ingredient']['ingredient_text']})
            pending.append((child, values))
    return result
