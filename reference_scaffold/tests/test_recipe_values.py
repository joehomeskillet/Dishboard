from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, Rounded, localcontext
from typing import Any

import pytest

from cafeteria.recipe_types import IngredientQuantity, RecipeValidationError
from cafeteria.recipe_values import parse_ingredient_quantity


def test_missing_quantity_and_unit_remain_missing() -> None:
    assert parse_ingredient_quantity(None, None) == IngredientQuantity(None, None)


@pytest.mark.parametrize(('quantity', 'code'), [(None, 'G'), ('1', None)])
def test_quantity_and_unit_must_be_supplied_together(quantity: str | None, code: str | None) -> None:
    with pytest.raises(RecipeValidationError):
        parse_ingredient_quantity(quantity, code)


@pytest.mark.parametrize(('raw', 'expected'), [
    ('0.000001', '0.000001'),
    ('999999999999.999999', '999999999999.999999'),
    ('12.340000000', '12.34'),
    (Decimal('2.00000000'), '2'),
    ('  +001.5000  ', '1.5'),
])
def test_exact_quantity_and_input_preservation(raw: str | Decimal, expected: str) -> None:
    original = str(raw)
    result = parse_ingredient_quantity(raw, 'KG')
    assert result == IngredientQuantity(Decimal(expected), 'KG')
    assert result.quantity is not None
    assert result.quantity.as_tuple() == Decimal(expected).as_tuple()
    assert str(raw) == original


@pytest.mark.parametrize('raw', [
    '1000000000000', '0.0000001', '1.0000001', Decimal('999999999999.9999991'),
    '0', '-0', '-1', '', '1,5', 'NaN', 'sNaN', 'Infinity', '-Infinity',
    Decimal('NaN'), Decimal('sNaN'), Decimal('Infinity'), Decimal('-Infinity'),
    1.0, 1, True, False,
])
def test_invalid_quantity_has_recipe_validation_error(raw: Any) -> None:
    with pytest.raises(RecipeValidationError):
        parse_ingredient_quantity(raw, 'G')


@pytest.mark.parametrize('code', [
    '', 'g', ' G', 'G ', 'G\n', 'G\x00', '1G', '_G', 'G-KG', 'Ä',
    'A' * 17, 1, True, b'G', [],
])
def test_unit_code_is_strict_and_never_normalized(code: Any) -> None:
    with pytest.raises(RecipeValidationError):
        parse_ingredient_quantity('1', code)


@pytest.mark.parametrize('code', ['G', 'PORTION', 'PRISE', 'UNREGISTERED', 'A_' + '0' * 14])
def test_valid_code_does_not_claim_existence_or_convert(code: str) -> None:
    assert parse_ingredient_quantity('2.5', code) == IngredientQuantity(Decimal('2.5'), code)


def test_result_is_frozen() -> None:
    result = parse_ingredient_quantity('2', 'G')
    for name, replacement in [('quantity', Decimal('3')), ('unit_code', 'KG')]:
        with pytest.raises(FrozenInstanceError):
            setattr(result, name, replacement)
    assert result == IngredientQuantity(Decimal('2'), 'G')


def test_parser_preserves_callers_decimal_context() -> None:
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = context.traps[Rounded] = True
        context.clear_flags()
        result = parse_ingredient_quantity('999999999999.999999000', 'G')
        assert result.quantity == Decimal('999999999999.999999')
        assert context.prec == 2
        assert context.traps[Inexact] and context.traps[Rounded]
        assert not any(context.flags.values())


def test_recipe_multiline_normalizes_only_line_endings_and_exterior() -> None:
    from cafeteria.recipe_values import recipe_text

    assert recipe_text('  Cre\u0300me\r\n\rRühren  langsam.  ', 8000, multiline=True) == 'Crème\n\nRühren  langsam.'
    for invalid in ['a\tb', 'a\x00b', 'a\u200bb', '<b>', 'a\ufeffb']:
        with pytest.raises(RecipeValidationError):
            recipe_text(invalid, 8000, multiline=True)
    with pytest.raises(RecipeValidationError):
        recipe_text('a\nb', 120)


@pytest.mark.parametrize('value', [True, False, -1, 10081, 1.0, '1'])
def test_recipe_minutes_reject_noninteger_or_outside_range(value: Any) -> None:
    from cafeteria.recipe_values import recipe_minutes

    with pytest.raises(RecipeValidationError):
        recipe_minutes(value)


def test_recipe_minutes_and_text_boundaries() -> None:
    from cafeteria.recipe_values import recipe_minutes, recipe_text

    for value in [None, 0, 10080]:
        assert recipe_minutes(value) == value
    assert recipe_text('x' * 120, 120) == 'x' * 120
    for invalid_text in ['', 'x' * 121]:
        with pytest.raises(RecipeValidationError):
            recipe_text(invalid_text, 120)
