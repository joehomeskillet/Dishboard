"""Shopping list CHF totals never treat missing price as zero."""
from decimal import Decimal

from cafeteria.shopping_cost import cost_snapshot_lines


def test_freetext_and_missing_price_are_incomplete() -> None:
    kg = {'code': 'KG', 'dimension': 'mass', 'base_factor': '1000'}
    lines = [
        {'food_public_id': 'food-a', 'quantity': '0.750', 'unit_code': 'KG'},
        {'food_public_id': None, 'quantity': '1', 'unit_code': 'STK', 'ingredient_text': 'Salz extra'},
    ]
    prices = {
        'food-a': {
            'unit_price': Decimal('2.40'), 'yield_factor': None, 'unit': kg,
        },
    }
    result = cost_snapshot_lines(lines, prices)
    assert result[0].status == 'complete'
    assert result[0].amount == Decimal('1.80')
    assert result[1].status == 'incomplete'
    assert result[1].amount is None
    missing = cost_snapshot_lines(
        [{'food_public_id': 'food-b', 'quantity': '1', 'unit_code': 'KG'}],
        {'food-b': None},
    )
    assert missing[0].status == 'incomplete'
    assert missing[0].amount is None
    assert any(issue.code == 'unit_price' for issue in missing[0].issues)
