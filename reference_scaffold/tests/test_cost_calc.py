"""Pure cost_calc contract: Decimal amounts or explicit incomplete, never a silent zero."""
from __future__ import annotations

import ast
from decimal import Decimal, Inexact, localcontext
from pathlib import Path

import pytest

from cafeteria.cost_calc import CostLine, line_cost, parse_money, scale_recipe_costs
from cafeteria.quantities import FoodFactors, QuantityError, Unit


D = Decimal
KG = Unit('KG', 'mass', D('1000'))
G = Unit('G', 'mass', D('1'))
STK = Unit('STK', 'count', D('1'))
PORTION = Unit('PORTION', 'contextual', None)
MODULE = Path(__file__).resolve().parents[1] / 'cafeteria' / 'cost_calc.py'


def test_line_cost_a1_potatoes_without_yield() -> None:
    line = line_cost('0.750', KG, KG, '2.40')
    assert line.status == 'complete'
    assert line.amount == D('1.80')
    assert line.issues == ()


def test_line_cost_yield_factor_uses_purchase_quantity() -> None:
    line = line_cost('0.750', KG, KG, '2.40', yield_factor='0.8')
    assert line.status == 'complete'
    assert line.amount == D('2.250')


def test_missing_price_is_incomplete_none_not_zero() -> None:
    line = line_cost('0.750', KG, KG, None)
    assert line.status == 'incomplete'
    assert line.amount is None
    assert line.amount is not D('0')
    assert any(issue.field == 'unit_price' for issue in line.issues)


def test_portion_against_kg_is_incomplete_even_with_piece_weight() -> None:
    food = FoodFactors(piece_weight_g=D('250'))
    line = line_cost('1', PORTION, KG, '2.40', food=food)
    assert line.status == 'incomplete'
    assert line.amount is None


def test_stk_against_kg_needs_explicit_piece_weight() -> None:
    missing = line_cost('2', STK, KG, '4.00')
    assert missing.status == 'incomplete'
    assert missing.amount is None
    weighed = line_cost('2', STK, KG, '4.00', food=FoodFactors(piece_weight_g=D('500')))
    assert weighed.status == 'complete'
    assert weighed.amount == D('4.00')


def test_scale_recipe_costs_blanks_total_when_any_line_is_incomplete() -> None:
    result = scale_recipe_costs(
        (('0.750', KG, KG, '2.40'), ('1', PORTION, KG, '2.40')),
        servings='4', servings_unit_code='PORTION', target_servings='4',
    )
    assert result.complete is False
    assert result.total is None
    assert result.lines[0].amount == D('1.80')
    assert result.currency == 'CHF'


def test_scale_recipe_costs_complete_total_and_per_portion() -> None:
    four = scale_recipe_costs(
        (('0.750', KG, KG, '2.40'),),
        servings='4', servings_unit_code='PORTION', target_servings='4',
    )
    assert four.complete is True
    assert four.total == D('1.80')
    one = scale_recipe_costs(
        (('0.750', KG, KG, '2.40'),),
        servings='4', servings_unit_code='PORTION', target_servings='1',
    )
    assert one.total == D('0.45')


def test_parse_money_rejects_float_and_zero() -> None:
    assert parse_money('2.40') == D('2.40')
    with pytest.raises(QuantityError):
        parse_money(D('0'))


def test_inexact_caller_context_does_not_hide_the_amount() -> None:
    with localcontext() as context:
        context.traps[Inexact] = True
        line = line_cost('0.750', KG, KG, '2.40', yield_factor='0.8')
    assert line.amount == D('2.250')


def test_module_has_no_float_call_or_sqlalchemy_import() -> None:
    tree = ast.parse(MODULE.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != 'float'
        if isinstance(node, ast.Attribute) and node.attr == 'float':
            raise AssertionError('float attribute used')
        if isinstance(node, ast.Import):
            assert all('sqlalchemy' not in alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith('sqlalchemy')
    assert CostLine.__dataclass_params__.frozen is True
