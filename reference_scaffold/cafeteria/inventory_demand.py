"""Net demand = plan need minus captured stock. Unknown stock stays incomplete."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping


def net_demand(need_quantity: Decimal | None, stock: Mapping[str, Any]) -> dict[str, Any]:
    if need_quantity is None:
        return {'complete': False, 'quantity': None, 'reason': 'Bedarf unvollständig'}
    if not stock.get('captured'):
        return {'complete': False, 'quantity': None, 'reason': 'Kein Bestand erfasst'}
    remaining = need_quantity - Decimal(str(stock['quantity']))
    if remaining < 0:
        remaining = Decimal('0')
    return {'complete': True, 'quantity': remaining, 'reason': None}
