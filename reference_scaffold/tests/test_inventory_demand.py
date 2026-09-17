"""Net demand never treats uncaptured stock as zero."""
from decimal import Decimal

from cafeteria.inventory_demand import net_demand


def test_uncaptured_stock_is_incomplete() -> None:
    result = net_demand(Decimal('10'), {'captured': False, 'quantity': None})
    assert result['complete'] is False
    assert result['quantity'] is None
    assert result['reason'] == 'Kein Bestand erfasst'


def test_captured_stock_reduces_need() -> None:
    result = net_demand(Decimal('10'), {'captured': True, 'quantity': Decimal('4')})
    assert result['complete'] is True
    assert result['quantity'] == Decimal('6')
