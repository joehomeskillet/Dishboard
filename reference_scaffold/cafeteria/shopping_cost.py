"""CHF for a shopping-list revision via line_cost. Manual/freetext stay incomplete."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine

from .cost_calc import CostIssue, CostLine, line_cost, total_cost
from .food_price_store import get_price_on, list_price_revisions
from .quantities import Unit
from .shopping_list_reads import ShoppingScope, get_shopping_list

_SEED = {
    'G': ('mass', '1'), 'KG': ('mass', '1000'), 'ML': ('volume', '1'),
    'L': ('volume', '1000'), 'STK': ('count', '1'),
}


def _unit(code: str, snapshot: Mapping[str, Any] | None = None) -> Unit:
    if snapshot:
        factor = snapshot.get('base_factor')
        return Unit(
            str(snapshot['code']), str(snapshot['dimension']),
            None if factor in (None, 'null') else Decimal(str(factor)),
        )
    if code in _SEED:
        dimension, factor = _SEED[code]
        return Unit(code, dimension, Decimal(factor))
    return Unit(code, 'mass', Decimal('1'))


def cost_snapshot_lines(
    lines: list[Mapping[str, Any]],
    prices: Mapping[str, Mapping[str, Any] | None],
) -> tuple[CostLine, ...]:
    result: list[CostLine] = []
    for row in lines:
        food_id = row.get('food_public_id')
        quantity = row.get('quantity')
        unit_code = str(row.get('unit_code') or '')
        if not food_id or quantity in (None, ''):
            result.append(CostLine(
                str(food_id) if food_id else None, None, unit_code, None, None, 'incomplete', None,
                (CostIssue('manual', 'food_public_id', 'Ohne Kalkulation: Freitext oder unvollständige Zeile.'),),
            ))
            continue
        price = prices.get(str(food_id))
        from_unit = _unit(unit_code or 'KG')
        if price is None:
            result.append(line_cost(str(quantity), from_unit, from_unit, None, food_public_id=str(food_id)))
            continue
        price_unit = _unit(str(price['unit']['code']), price['unit'])
        result.append(line_cost(
            str(quantity), from_unit, price_unit, price['unit_price'],
            yield_factor=price.get('yield_factor'), food_public_id=str(food_id),
        ))
    return tuple(result)


def shopping_list_cost(
    engine: Engine, scope: ShoppingScope, list_public_id: str, on_date: date,
) -> dict[str, Any]:
    view = get_shopping_list(engine, scope, list_public_id)
    revision = view.get('revision') or {}
    snapshot = revision.get('snapshot_json') or revision.get('snapshot') or {}
    lines = (snapshot.get('result') or {}).get('lines') or [] if isinstance(snapshot, Mapping) else []
    prices: dict[str, Any] = {}
    for row in lines:
        food_id = row.get('food_public_id')
        if not food_id:
            continue
        revisions = list_price_revisions(engine, str(food_id))
        current = next((item for item in revisions if item.get('is_current')), None)
        if current is None:
            prices[str(food_id)] = None
            continue
        prices[str(food_id)] = get_price_on(engine, str(food_id), on_date, str(current['public_id']))
    cost_lines = cost_snapshot_lines(list(lines), prices)
    complete, total = total_cost(cost_lines)
    return {'currency': 'CHF', 'complete': complete, 'total': total, 'lines': cost_lines}
