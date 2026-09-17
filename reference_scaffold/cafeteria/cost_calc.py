"""DB-free purchase cost arithmetic. Missing price is incomplete, never zero."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .quantities import FoodFactors, QuantityError, Unit, convert, parse_factor, parse_quantity


@dataclass(frozen=True)
class CostIssue:
    code: str
    field: str
    message: str


@dataclass(frozen=True)
class CostLine:
    food_public_id: str | None
    quantity: Decimal | None
    unit_code: str
    unit_price: Decimal | None
    yield_factor: Decimal | None
    status: str
    amount: Decimal | None
    issues: tuple[CostIssue, ...]


def parse_money(value: str | Decimal) -> Decimal:
    return parse_quantity(value)


def line_cost(
    quantity: str | Decimal,
    from_unit: Unit,
    price_unit: Unit,
    unit_price: str | Decimal | None,
    *,
    yield_factor: str | Decimal | None = None,
    food: FoodFactors | None = None,
    food_public_id: str | None = None,
) -> CostLine:
    issues: list[CostIssue] = []
    qty: Decimal | None
    try:
        qty = parse_quantity(quantity)
    except QuantityError as error:
        return CostLine(food_public_id, None, from_unit.code, None, None, 'incomplete', None,
                        (CostIssue('quantity', 'quantity', str(error)),))
    if unit_price is None:
        return CostLine(food_public_id, qty, from_unit.code, None, None, 'incomplete', None,
                        (CostIssue('unit_price', 'unit_price', 'Einkaufspreis fehlt.'),))
    try:
        price = parse_money(unit_price)
        converted = convert(qty, from_unit, price_unit, food)
        factor = parse_factor(yield_factor) if yield_factor is not None else None
        if factor is not None:
            converted = converted / factor
        amount = converted * price
    except QuantityError as error:
        issues.append(CostIssue('unit', 'unit_code', str(error)))
        return CostLine(food_public_id, qty, from_unit.code, None, None, 'incomplete', None, tuple(issues))
    return CostLine(food_public_id, qty, from_unit.code, price, factor, 'complete', amount, ())


def total_cost(lines: Sequence[CostLine]) -> tuple[bool, Decimal | None]:
    if any(line.status != 'complete' or line.amount is None for line in lines):
        return False, None
    return True, sum((line.amount for line in lines), Decimal('0'))
