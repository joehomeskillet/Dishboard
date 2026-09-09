"""Drive shopping_aggregate on captured DTOs; no database or inventory writes."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from cafeteria.quantities import FoodFactors, Unit
from cafeteria.shopping_aggregate import (
    POLICY_LEAF, POLICY_PREPARED, AggregateLine, IngredientNeed, RevisionNeed, aggregate,
)

G = Unit('G', 'mass', Decimal('1'))
KG = Unit('KG', 'mass', Decimal('1000'))
ML = Unit('ML', 'volume', Decimal('1'))
STK = Unit('STK', 'count', Decimal('1'))
FLOUR = '11111111-1111-4111-8111-111111111111'
SAUCE = '22222222-2222-4222-8222-222222222222'


def _need(*items: IngredientNeed, target: str = '1', source: str = '1') -> RevisionNeed:
    return RevisionNeed('rev-1', 'b' * 64, Decimal(source), Decimal(target), items)


def test_mass_units_of_the_same_food_sum_to_grams() -> None:
    need = _need(
        IngredientNeed(FLOUR, Decimal('500'), G, None),
        IngredientNeed(FLOUR, Decimal('1'), KG, None),
    )
    lines = aggregate((need,))
    assert len(lines) == 1
    assert lines[0].quantity == Decimal('1500') and lines[0].unit_code == 'G'
    assert lines[0].status == 'complete'


def test_volume_with_captured_density_joins_mass() -> None:
    food = FoodFactors(density_g_per_ml=Decimal('1.2'))
    need = _need(
        IngredientNeed(FLOUR, Decimal('500'), ML, food),
        IngredientNeed(FLOUR, Decimal('400'), G, food),
    )
    lines = aggregate((need,))
    assert len(lines) == 1 and lines[0].quantity == Decimal('1000')


def test_volume_without_density_stays_separate() -> None:
    need = _need(
        IngredientNeed(FLOUR, Decimal('500'), ML, None),
        IngredientNeed(FLOUR, Decimal('400'), G, None),
    )
    lines = aggregate((need,))
    assert len(lines) == 2
    units = {line.unit_code for line in lines}
    assert units == {'ML', 'G'}


def test_later_factor_mutation_does_not_change_captured_result() -> None:
    captured = FoodFactors(density_g_per_ml=Decimal('1.2'))
    need = _need(IngredientNeed(FLOUR, Decimal('500'), ML, captured))
    first = aggregate((need,))
    other = FoodFactors(density_g_per_ml=Decimal('9.9'))
    second = aggregate((need,))
    assert first[0].quantity == second[0].quantity == Decimal('600')
    assert other.density_g_per_ml != captured.density_g_per_ml


def _sauce_child(grams: str = '100') -> RevisionNeed:
    return RevisionNeed(
        'child-1', 'c' * 64, Decimal('1'), Decimal('1'),
        (IngredientNeed(FLOUR, Decimal(grams), G, None),),
    )


def test_prepared_leaf_policy_counts_leaves_not_the_intermediate() -> None:
    parent = _need(IngredientNeed(SAUCE, Decimal('2'), STK, None, prepared_child=_sauce_child()))
    lines = aggregate((parent,), policy=POLICY_LEAF)
    assert [line.food_public_id for line in lines] == [FLOUR]
    assert lines[0].quantity == Decimal('200')


def test_prepared_policy_counts_intermediate_not_leaves() -> None:
    parent = _need(IngredientNeed(SAUCE, Decimal('2'), STK, None, prepared_child=_sauce_child()))
    lines = aggregate((parent,), policy=POLICY_PREPARED, stop_prepared_food_ids=frozenset({SAUCE}))
    assert [line.food_public_id for line in lines] == [SAUCE]
    assert lines[0].quantity == Decimal('2') and lines[0].unit_code == 'STK'


def test_shared_child_index_does_not_collapse_two_occurrences() -> None:
    child = _sauce_child('100')
    parent = _need(
        IngredientNeed(SAUCE, Decimal('1'), STK, None, prepared_child=child),
        IngredientNeed(SAUCE, Decimal('1'), STK, None, prepared_child=child),
    )
    lines = aggregate((parent,), policy=POLICY_LEAF)
    assert lines[0].quantity == Decimal('200')


def test_unknown_quantity_is_incomplete_not_zero() -> None:
    need = _need(IngredientNeed(FLOUR, None, G, None, text='etwas Mehl'))
    lines = aggregate((need,))
    assert lines[0].status == 'incomplete'
    assert lines[0].quantity is None


def test_module_has_no_database_or_network_imports() -> None:
    text = (Path(__file__).resolve().parents[1] / 'cafeteria' / 'shopping_aggregate.py').read_text(encoding='utf-8')
    assert 'sqlalchemy' not in text and 'psycopg' not in text
    assert 'urllib' not in text and 'socket' not in text
    assert isinstance(AggregateLine, type)
