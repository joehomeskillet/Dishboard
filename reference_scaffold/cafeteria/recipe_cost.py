"""Recipe, prepared and menu cost projection from frozen revisions and chosen prices."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping, Sequence

from sqlalchemy import Engine, text

from .cost_calc import CostLine, line_cost, total_cost
from .food_price_store import get_price_on
from .quantities import Unit
from .recipe_reads import get_revision


def _unit_row(engine: Engine, code: str) -> Unit:
    with engine.connect() as connection:
        row = connection.execute(text(
            'SELECT code, dimension, base_factor FROM cafeteria.measurement_units WHERE code=:code'
        ), {'code': code}).mappings().one()
    return Unit(str(row['code']), str(row['dimension']),
                None if row['base_factor'] is None else Decimal(str(row['base_factor'])))


def _price_unit(payload: Mapping[str, Any]) -> Unit:
    unit = payload['unit']
    factor = unit.get('base_factor')
    return Unit(str(unit['code']), str(unit['dimension']),
                None if factor in (None, 'null') else Decimal(str(factor)))


def _line_for_ingredient(
    engine: Engine, as_of: date, price_revisions: Mapping[str, str], ingredient: Mapping[str, Any],
) -> CostLine:
    food_id = ingredient.get('food_public_id')
    quantity = ingredient.get('quantity')
    unit_code = ingredient.get('unit_code') or ''
    if not food_id or quantity is None or not unit_code:
        return CostLine(food_id, None, unit_code, None, None, 'incomplete', None, ())
    from_unit = _unit_row(engine, unit_code)
    revision = price_revisions.get(str(food_id))
    if not revision:
        return line_cost(quantity, from_unit, from_unit, None, food_public_id=str(food_id))
    priced = get_price_on(engine, str(food_id), as_of, revision)
    if priced is None:
        return line_cost(quantity, from_unit, from_unit, None, food_public_id=str(food_id))
    return line_cost(
        quantity, from_unit, _price_unit(priced), priced['unit_price'],
        yield_factor=priced.get('yield_factor'), food_public_id=str(food_id),
    )


def project_recipe(
    engine: Engine, revision_public_id: str, as_of: date, price_revisions: Mapping[str, str],
) -> dict[str, Any]:
    revision = get_revision(engine, revision_public_id)
    ingredients = revision.snapshot['recipe']['ingredients']
    lines = tuple(_line_for_ingredient(engine, as_of, price_revisions, item) for item in ingredients)
    complete, total = total_cost(lines)
    return {
        'kind': 'recipe',
        'complete': complete,
        'total': total,
        'lines': lines,
        'revision_public_id': revision.public_id,
        'as_of': as_of.isoformat(),
        'price_revisions': dict(price_revisions),
    }


def project_prepared(
    engine: Engine, revision_public_id: str, as_of: date, price_revisions: Mapping[str, str],
) -> dict[str, Any]:
    """Same arithmetic as a recipe; prepared pins never add purchase price and graph cost."""
    return {**project_recipe(engine, revision_public_id, as_of, price_revisions), 'kind': 'prepared'}


def project_menu(
    engine: Engine, revision_public_ids: Sequence[str], as_of: date, price_revisions: Mapping[str, str],
) -> dict[str, Any]:
    parts = tuple(project_recipe(engine, item, as_of, price_revisions) for item in revision_public_ids)
    lines = tuple(line for part in parts for line in part['lines'])
    complete, total = total_cost(lines)
    return {
        'kind': 'menu',
        'complete': complete,
        'total': total,
        'lines': lines,
        'parts': parts,
        'as_of': as_of.isoformat(),
        'price_revisions': dict(price_revisions),
    }
