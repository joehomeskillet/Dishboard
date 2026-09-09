"""Pure Decimal recipe-cost arithmetic; persistence and price lookup live elsewhere."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .quantities import FoodFactors, QuantityError, Unit, convert, parse_factor, parse_quantity, scale_servings

_STATUS_COMPLETE = 'complete'
_STATUS_INCOMPLETE = 'incomplete'


@dataclass(frozen=True)
class CostIssue:
    code: str
    field: str
    message: str


@dataclass(frozen=True)
class CostLine:
    food_public_id: str
    quantity: Decimal | None
    unit_code: str
    unit_price: Decimal | None
    yield_factor: Decimal | None
    status: str
    amount: Decimal | None
    issues: tuple[CostIssue, ...]


@dataclass(frozen=True)
class CostResult:
    currency: str
    complete: bool
    total: Decimal | None
    lines: tuple[CostLine, ...]
    servings: Decimal
    servings_unit_code: str
    target_servings: Decimal


def parse_money(value: str | Decimal) -> Decimal:
    """Purchase price per unit; same 12+6 storage boundary as quantities, never rappen-rounded."""
    return parse_quantity(value)


def _issue(code: str, field: str, message: str) -> CostIssue:
    return CostIssue(code=code, field=field, message=message)


def _incomplete(
    food_public_id: str, quantity: Decimal | None, unit_code: str,
    unit_price: Decimal | None, yield_factor: Decimal | None, issues: tuple[CostIssue, ...],
) -> CostLine:
    return CostLine(
        food_public_id=food_public_id, quantity=quantity, unit_code=unit_code,
        unit_price=unit_price, yield_factor=yield_factor, status=_STATUS_INCOMPLETE,
        amount=None, issues=issues,
    )


def line_cost(
    quantity: str | Decimal,
    quantity_unit: Unit,
    price_unit: Unit,
    unit_price: str | Decimal | None,
    *,
    yield_factor: str | Decimal | None = None,
    food: FoodFactors | None = None,
    food_public_id: str = '',
) -> CostLine:
    """One ingredient cost from explicit historical quantity, price unit and optional yield.

    A missing price or impossible conversion is incomplete with amount None, never Decimal('0').
    yield None means factor 1. PORTION cannot convert to mass even with piece weight.
    """
    issues: list[CostIssue] = []
    parsed_quantity: Decimal | None = None
    parsed_price: Decimal | None = None
    parsed_yield: Decimal | None = None
    unit_code = quantity_unit.code if isinstance(quantity_unit, Unit) else ''
    try:
        parsed_quantity = parse_quantity(quantity)
    except QuantityError as error:
        issues.append(_issue('quantity', 'quantity', str(error)))
    if unit_price is None:
        issues.append(_issue('unit_price', 'unit_price', 'Einkaufspreis fehlt.'))
    else:
        try:
            parsed_price = parse_money(unit_price)
        except QuantityError as error:
            issues.append(_issue('unit_price', 'unit_price', str(error)))
    if yield_factor is not None:
        try:
            parsed_yield = parse_factor(yield_factor)
            if parsed_yield > 1:
                issues.append(_issue(
                    'yield_factor', 'yield_factor',
                    'Ausbeutefaktor muss NULL oder (0 < x ≤ 1) sein.',
                ))
                parsed_yield = None
        except QuantityError as error:
            issues.append(_issue('yield_factor', 'yield_factor', str(error)))
    if issues:
        return _incomplete(food_public_id, parsed_quantity, unit_code, parsed_price, parsed_yield, tuple(issues))
    assert parsed_quantity is not None and parsed_price is not None
    factor = parsed_yield if parsed_yield is not None else Decimal('1')
    try:
        priced_quantity = convert(parsed_quantity, quantity_unit, price_unit, food)
        amount = priced_quantity / factor * parsed_price
    except QuantityError as error:
        return _incomplete(
            food_public_id, parsed_quantity, unit_code, parsed_price, parsed_yield,
            (_issue('conversion', 'unit_code', str(error)),),
        )
    return CostLine(
        food_public_id=food_public_id, quantity=parsed_quantity, unit_code=unit_code,
        unit_price=parsed_price, yield_factor=parsed_yield, status=_STATUS_COMPLETE,
        amount=amount, issues=(),
    )


def scale_recipe_costs(
    rows: Sequence[tuple[str | Decimal, Unit, Unit, str | Decimal | None]],
    *,
    servings: str | Decimal,
    servings_unit_code: str,
    target_servings: str | Decimal,
    yield_factors: Sequence[str | Decimal | None] | None = None,
    foods: Sequence[FoodFactors | None] | None = None,
    food_public_ids: Sequence[str] | None = None,
) -> CostResult:
    """Scale each row with scale_servings, then line_cost. Any incomplete line blanks total."""
    source = parse_quantity(servings)
    target = parse_quantity(target_servings)
    scaled: list[CostLine] = []
    for index, (quantity, quantity_unit, price_unit, unit_price) in enumerate(rows):
        try:
            scaled_quantity: str | Decimal = scale_servings(parse_quantity(quantity), source, target)
        except QuantityError:
            scaled_quantity = quantity
        factor = None if yield_factors is None else yield_factors[index]
        food = None if foods is None else foods[index]
        food_id = '' if food_public_ids is None else food_public_ids[index]
        scaled.append(line_cost(
            scaled_quantity, quantity_unit, price_unit, unit_price,
            yield_factor=factor, food=food, food_public_id=food_id,
        ))
    complete = bool(scaled) and all(line.status == _STATUS_COMPLETE for line in scaled)
    total = None
    if complete:
        total = sum((line.amount for line in scaled if line.amount is not None), Decimal('0'))
    return CostResult(
        currency='CHF', complete=complete, total=total, lines=tuple(scaled),
        servings=source, servings_unit_code=servings_unit_code, target_servings=target,
    )
