from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, ROUND_DOWN, Rounded, localcontext
from typing import Any

import pytest

from cafeteria.quantities import (
    FoodFactors, QuantityError, Unit, convert, parse_factor, parse_quantity,
    scale_servings, sum_in_base, to_base,
)


D = Decimal
G = Unit('G', 'mass', D('1'))
KG = Unit('KG', 'mass', D('1000'))
ML = Unit('ML', 'volume', D('1'))
L = Unit('L', 'volume', D('1000'))
STK = Unit('STK', 'count', D('1'))
PORTION = Unit('PORTION', 'contextual', None)
PRISE = Unit('PRISE', 'contextual', None)


@pytest.mark.parametrize(('raw', 'expected'), [
    ('999999999999.999999', '999999999999.999999'),
    ('0.000001', '0.000001'), ('12.340000000', '12.34'),
    ('1E+11', '100000000000'), ('  +001.5000  ', '1.5'),
    (D('2.00000000'), '2'),
])
def test_quantity_storage_boundary_preserves_exact_value(raw: str | Decimal, expected: str) -> None:
    assert parse_quantity(raw) == D(expected)


@pytest.mark.parametrize('raw', ['1000000000000', '0.0000001', '1.0000001', D('999999999999.9999991')])
def test_quantity_rejects_out_of_range_without_rounding(raw: str | Decimal) -> None:
    with pytest.raises(QuantityError):
        parse_quantity(raw)


@pytest.mark.parametrize(('raw', 'expected'), [
    ('99999999999.999999999', '99999999999.999999999'),
    ('0.000000001', '0.000000001'), ('1.1234567890000', '1.123456789'),
])
def test_factor_storage_boundary(raw: str, expected: str) -> None:
    assert parse_factor(raw) == D(expected)


@pytest.mark.parametrize('raw', ['100000000000', '0.0000000001', '1.1234567891'])
def test_factor_rejects_out_of_range(raw: str) -> None:
    with pytest.raises(QuantityError):
        parse_factor(raw)


@pytest.mark.parametrize('raw', [
    None, True, False, 1, 0.1, D('0'), D('-0'), D('-1'), '', 'abc', '1,5',
    'NaN', 'sNaN', 'Infinity', '-Infinity', D('NaN'), D('sNaN'), D('Infinity'),
    '1_000', '1e999999999999999999999',
])
def test_both_parsers_reject_invalid_values(raw: Any) -> None:
    for parser in (parse_quantity, parse_factor):
        with pytest.raises(QuantityError):
            parser(raw)


@pytest.mark.parametrize(('code', 'dimension', 'factor'), [
    ('G', 'mass', D('1000')), ('G', 'volume', D('1')),
    ('ML', 'count', D('1')), ('STK', 'mass', D('1')),
    ('KG', 'mass', D('100')), ('L', 'volume', D('1')),
    ('EL', 'volume', D('20')), ('TL', 'volume', D('4')),
    ('PORTION', 'count', D('1')), ('PRISE', 'mass', D('1')),
    ('PINCH', 'contextual', D('1')), ('X', 'mass', None),
    ('X', 'length', D('1')), ('kg', 'mass', D('1000')),
    ('', 'mass', D('1')), ('X' * 17, 'mass', D('1')),
    ('X', 'mass', D('NaN')), ('X', 'mass', D('0')),
    ('X', 'mass', 1.0), (None, 'mass', D('1')), ('X', [], D('1')),
])
def test_units_reject_invalid_or_conflicting_metadata(code: Any, dimension: Any, factor: Any) -> None:
    with pytest.raises(QuantityError):
        Unit(code, dimension, factor)


def test_value_objects_are_immutable_and_factors_are_validated() -> None:
    food = FoodFactors(D('1.2000'), D('50'))
    assert food.density_g_per_ml == D('1.2')
    with pytest.raises(FrozenInstanceError):
        setattr(food, 'piece_weight_g', D('60'))
    with pytest.raises(FrozenInstanceError):
        setattr(G, 'base_factor', D('2'))
    assert hash(G) == hash(Unit('G', 'mass', D('1.000')))


@pytest.mark.parametrize('bad', [0.1, True, D('NaN'), D('-1'), D('0'), D('1.0000000001')])
def test_optional_food_factors_use_factor_storage_validation(bad: Any) -> None:
    with pytest.raises(QuantityError):
        FoodFactors(density_g_per_ml=bad)
    with pytest.raises(QuantityError):
        FoodFactors(piece_weight_g=bad)


@pytest.mark.parametrize(('quantity', 'source', 'target', 'expected'), [
    ('2.5', KG, G, '2500'), ('375', G, KG, '0.375'), ('0.5', L, ML, '500'),
    ('2', Unit('EL', 'volume', D('15')), ML, '30'),
    ('3', Unit('TL', 'volume', D('5')), ML, '15'),
    ('2', Unit('DOZEN', 'count', D('12')), STK, '24'),
])
def test_real_same_dimension_conversions(quantity: str, source: Unit, target: Unit, expected: str) -> None:
    assert convert(D(quantity), source, target) == D(expected)


@pytest.mark.parametrize(('quantity', 'source', 'target', 'expected'), [
    ('2', L, KG, '2.4'), ('2.4', KG, L, '2'),
    ('2', STK, G, '120'), ('0.12', KG, STK, '2'),
    ('2', STK, ML, '100'), ('0.1', L, STK, '2'),
])
def test_food_specific_cross_dimension_conversions(quantity: str, source: Unit, target: Unit,
                                                   expected: str) -> None:
    assert convert(D(quantity), source, target, FoodFactors(D('1.2'), D('60'))) == D(expected)


@pytest.mark.parametrize(('source', 'target', 'food'), [
    (G, ML, None), (ML, G, FoodFactors(piece_weight_g=D('60'))),
    (G, STK, None), (STK, G, FoodFactors(density_g_per_ml=D('1.2'))),
    (STK, ML, FoodFactors(piece_weight_g=D('60'))),
    (ML, STK, FoodFactors(density_g_per_ml=D('1.2'))),
])
def test_missing_required_factor_is_an_error(source: Unit, target: Unit, food: FoodFactors | None) -> None:
    with pytest.raises(QuantityError):
        convert(D('1'), source, target, food)


@pytest.mark.parametrize('contextual', [PORTION, PRISE])
def test_contextual_units_only_allow_same_code_identity(contextual: Unit) -> None:
    assert convert(D('0.125'), contextual, contextual) == D('0.125')
    food = FoodFactors(D('1'), D('1'))
    for target in (G, ML, STK, PORTION, PRISE):
        if contextual == target:
            continue
        with pytest.raises(QuantityError):
            convert(D('1'), contextual, target, food)
        with pytest.raises(QuantityError):
            convert(D('1'), target, contextual, food)
    with pytest.raises(QuantityError):
        to_base(D('1'), contextual)
    with pytest.raises(QuantityError):
        sum_in_base([(D('1'), contextual)])
    assert scale_servings(D('0.25'), D('4'), D('10')) == D('0.625')


def test_base_aggregation_has_explicit_dimension_and_empty_identity() -> None:
    assert to_base(D('0.75'), KG) == D('750')
    assert sum_in_base([(D('0.75'), KG), (D('150'), G)]) == D('900')
    assert sum_in_base([]) == D('0')
    with pytest.raises(QuantityError):
        sum_in_base([(D('1'), G), (D('1'), ML)])
    left = Unit('CUP', 'volume', D('200'))
    right = Unit('CUP', 'volume', D('250'))
    with pytest.raises(QuantityError):
        convert(D('1'), left, right)
    with pytest.raises(QuantityError):
        sum_in_base([(D('1'), left), (D('1'), right)])


def test_periodic_results_are_reusable_but_not_silently_persistable() -> None:
    third = convert(D('1'), G, Unit('THREE_G', 'mass', D('3')))
    assert third == D('0.' + '3' * 50)
    assert scale_servings(D('1'), D('3'), D('1')) == third
    assert convert(third, G, G) == third
    assert to_base(third, G) == third
    assert sum_in_base([(third, G)]) == third
    assert scale_servings(third, D('1'), D('1')) == third
    with pytest.raises(QuantityError):
        parse_quantity(third)
    # A tiny valid quantity remains nonzero after conversion; no six-place quantize.
    assert convert(D('0.000001'), G, KG) == D('0.000000001')
    assert to_base(D('1000000000000'), G) == D('1000000000000')


def test_all_arithmetic_uses_own_complete_context_and_leaves_caller_unchanged() -> None:
    with localcontext() as caller:
        caller.prec = 2
        caller.rounding = ROUND_DOWN
        caller.Emax, caller.Emin = 2, -2
        caller.clamp = 1
        caller.traps[Inexact] = caller.traps[Rounded] = True
        caller.clear_flags()
        assert parse_quantity('999999999999.999999000') == D('999999999999.999999')
        assert parse_factor('1.123456789000') == D('1.123456789')
        assert convert(D('1'), G, Unit('THREE_G', 'mass', D('3'))) == D('0.' + '3' * 50)
        assert to_base(D('1.' + '0' * 48 + '15'), G) == D('1.' + '0' * 48 + '2')
        assert sum_in_base([(D('0.75'), KG), (D('150'), G)]) == D('900')
        assert scale_servings(D('2.5'), D('4'), D('10')) == D('6.25')
        assert caller.prec == 2 and caller.rounding == ROUND_DOWN and caller.clamp == 1
        assert caller.Emax == 2 and caller.Emin == -2
        assert caller.traps[Inexact] and caller.traps[Rounded] and not any(caller.flags.values())


@pytest.mark.parametrize('bad', [None, True, 1.0, '1', D('0'), D('-1'), D('NaN'), D('sNaN')])
def test_calculation_quantity_must_be_positive_finite_decimal(bad: Any) -> None:
    for calculate in (lambda: convert(bad, G, G), lambda: to_base(bad, G),
                      lambda: sum_in_base([(bad, G)]), lambda: scale_servings(bad, D('1'), D('2'))):
        with pytest.raises(QuantityError):
            calculate()


@pytest.mark.parametrize('bad', [D('0'), D('1.0000001'), D('1000000000000'), True, 1.0])
def test_serving_counts_use_quantity_storage_boundary(bad: Any) -> None:
    with pytest.raises(QuantityError):
        scale_servings(D('1'), bad, D('2'))
    with pytest.raises(QuantityError):
        scale_servings(D('1'), D('2'), bad)


def test_malformed_units_factors_and_aggregate_shape_fail_clearly() -> None:
    bad: Any = None
    with pytest.raises(QuantityError):
        convert(D('1'), bad, G)
    with pytest.raises(QuantityError):
        to_base(D('1'), bad)
    with pytest.raises(QuantityError):
        convert(D('1'), G, G, food={})  # type: ignore[arg-type]
    for value in (None, '1', [(D('1'),)], [(D('1'), G, G)]):
        with pytest.raises(QuantityError):
            sum_in_base(value)  # type: ignore[arg-type]
