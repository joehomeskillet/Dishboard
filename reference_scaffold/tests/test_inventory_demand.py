"""Net demand never treats uncaptured stock as zero."""
from decimal import Decimal

from cafeteria.inventory_demand import net_demand, packs_for


def test_uncaptured_stock_is_incomplete() -> None:
    result = net_demand(Decimal('10'), {'captured': False, 'quantity': None})
    assert result['complete'] is False
    assert result['quantity'] is None
    assert result['reason'] == 'Kein Bestand erfasst'


def test_captured_stock_reduces_need() -> None:
    result = net_demand(Decimal('10'), {'captured': True, 'quantity': Decimal('4')})
    assert result['complete'] is True
    assert result['quantity'] == Decimal('6')


def test_need_eight_captured_five_is_three() -> None:
    result = net_demand(Decimal('8'), {'captured': True, 'quantity': Decimal('5')})
    assert result['complete'] is True
    assert result['quantity'] == Decimal('3')


def test_surplus_captured_stock_nets_to_zero() -> None:
    result = net_demand(Decimal('8'), {'captured': True, 'quantity': Decimal('10')})
    assert result['complete'] is True
    assert result['quantity'] == Decimal('0')


def test_unknown_stock_does_not_reduce_need() -> None:
    result = net_demand(Decimal('8'), {'captured': False, 'quantity': Decimal('0')})
    assert result['complete'] is False
    assert result['quantity'] is None


def test_packs_round_up_raw_stays_caller_owned() -> None:
    assert packs_for(Decimal('8'), Decimal('2.5')) == Decimal('4')
    assert packs_for(Decimal('10'), Decimal('2.5')) == Decimal('4')
    assert packs_for(Decimal('0'), Decimal('2.5')) == Decimal('0')
