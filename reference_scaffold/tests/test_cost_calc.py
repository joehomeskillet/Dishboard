"""R2 line_cost: missing price is incomplete, never zero."""
from decimal import Decimal

from cafeteria.cost_calc import line_cost, total_cost
from cafeteria.quantities import Unit

G = Unit('G', 'mass', Decimal('1'))
KG = Unit('KG', 'mass', Decimal('1000'))


def test_line_cost_grams_against_kg_price() -> None:
    line = line_cost('250', G, KG, '4.00', food_public_id='food-1')
    assert line.status == 'complete'
    assert line.amount == Decimal('1.00')


def test_line_cost_same_unit() -> None:
    line = line_cost('0.750', KG, KG, '2.40')
    assert line.amount == Decimal('1.80')


def test_missing_price_is_incomplete_not_zero() -> None:
    line = line_cost('0.750', KG, KG, None)
    assert line.status == 'incomplete'
    assert line.amount is None
    assert line.issues[0].code == 'unit_price'
    complete, total = total_cost((line,))
    assert complete is False
    assert total is None
