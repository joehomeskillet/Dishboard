"""Read-only presentation of recipe yields; no unit conversion or persistence."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..quantities import QuantityError, parse_quantity, scale_servings
from ..recipe_types import RecipeConfigurationError
from .recipe_forms import FormError


def scaled_recipe(payload: Mapping[str, object], target: str | None = None) -> dict[str, Any]:
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
        return {'source': format(source, 'f'), 'target': format(wanted, 'f'),
                'unit': payload['servings_unit_code'], 'rows': result}
    except (QuantityError, KeyError, TypeError, ValueError):
        raise RecipeConfigurationError('Gespeicherte Rezeptmengen sind nicht verfügbar.') from None
