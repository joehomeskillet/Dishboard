"""Draft order baskets. Preview/CSV never change status. No HTTP clients."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence
from uuid import UUID

from sqlalchemy import Engine, text

from .calendar_event_store import CalendarEventConflictError, CalendarEventValidationError
from .inventory_demand import packs_for
from .shopping_list_reads import ShoppingScope, _transaction as _shop_tx


class OrderBasketError(ValueError):
    pass


class OrderBasketConflictError(OrderBasketError):
    pass


def _uuid(value: str) -> str:
    return str(UUID(value))


def create_basket(engine: Engine, scope: ShoppingScope, supplier_public_id: str) -> str:
    with _shop_tx(engine, scope, 'write') as connection:
        supplier = connection.execute(text(
            'SELECT id FROM cafeteria.suppliers WHERE public_id=CAST(:id AS uuid) AND location_id=:location AND active'
        ), {'id': _uuid(supplier_public_id), 'location': scope.location_id}).scalar_one_or_none()
        if supplier is None:
            raise CalendarEventValidationError('Lieferant nicht gefunden.')
        return str(connection.execute(text('''
            INSERT INTO cafeteria.order_baskets(location_id, supplier_id, created_by, updated_by)
            VALUES (:location, :supplier, :actor, :actor) RETURNING public_id
        '''), {'location': scope.location_id, 'supplier': supplier, 'actor': scope.actor_id}).scalar_one())


def replace_basket_lines(
    engine: Engine, scope: ShoppingScope, basket_public_id: str, *, expected_row_version: int,
    lines: Sequence[Mapping[str, Any]],
) -> None:
    if len(lines) > 64:
        raise CalendarEventValidationError('Höchstens 64 Positionen.')
    with _shop_tx(engine, scope, 'write') as connection:
        basket = connection.execute(text(
            'SELECT id, row_version, status FROM cafeteria.order_baskets '
            'WHERE public_id=CAST(:id AS uuid) AND location_id=:location FOR UPDATE'
        ), {'id': _uuid(basket_public_id), 'location': scope.location_id}).mappings().one_or_none()
        if basket is None:
            raise CalendarEventValidationError('Korb nicht gefunden.')
        if basket['status'] != 'draft':
            raise CalendarEventValidationError('Nur Entwurfskörbe sind editierbar.')
        if basket['row_version'] != expected_row_version:
            raise CalendarEventConflictError('Der Korb wurde zwischenzeitlich geändert.')
        existing = connection.execute(text(
            'SELECT count(*) FROM cafeteria.order_basket_lines WHERE basket_id=:id'
        ), {'id': basket['id']}).scalar_one()
        if existing:
            raise OrderBasketError('Bestehende Korbzeilen können nicht ersetzt werden.')
        for index, line in enumerate(lines, start=1):
            article = connection.execute(text(
                'SELECT id FROM cafeteria.supplier_articles WHERE public_id=CAST(:id AS uuid) AND location_id=:location AND active'
            ), {'id': _uuid(str(line['article_public_id'])), 'location': scope.location_id}).scalar_one_or_none()
            if article is None:
                raise CalendarEventValidationError('Artikel nicht gefunden.')
            qty = Decimal(str(line['quantity']))
            if qty <= 0:
                raise CalendarEventValidationError('Menge muss positiv sein.')
            connection.execute(text('''
                INSERT INTO cafeteria.order_basket_lines(basket_id, article_id, quantity, sort_order)
                VALUES (:basket, :article, :qty, :sort)
            '''), {'basket': basket['id'], 'article': article, 'qty': qty, 'sort': index})
        connection.execute(text(
            'UPDATE cafeteria.order_baskets SET updated_by=:actor WHERE id=:id'
        ), {'actor': scope.actor_id, 'id': basket['id']})


def get_basket(engine: Engine, location_id: int, public_id: str) -> dict[str, Any]:
    with engine.connect() as connection:
        head = connection.execute(text('''
            SELECT b.public_id, b.status, b.row_version, s.public_id AS supplier_public_id, s.name AS supplier_name
            FROM cafeteria.order_baskets b
            JOIN cafeteria.suppliers s ON s.id=b.supplier_id
            WHERE b.public_id=CAST(:id AS uuid) AND b.location_id=:location
        '''), {'id': _uuid(public_id), 'location': location_id}).mappings().one_or_none()
        if head is None:
            raise CalendarEventValidationError('Korb nicht gefunden.')
        lines = connection.execute(text('''
            SELECT l.public_id, l.quantity, l.sort_order, a.public_id AS article_public_id, a.name AS article_name,
                   a.article_code, a.pack_size, a.food_id IS NULL AS without_food, u.code AS order_unit_code
            FROM cafeteria.order_basket_lines l
            JOIN cafeteria.supplier_articles a ON a.id=l.article_id
            JOIN cafeteria.measurement_units u ON u.id=a.order_unit_id
            WHERE l.basket_id=(SELECT id FROM cafeteria.order_baskets WHERE public_id=CAST(:id AS uuid))
            ORDER BY l.sort_order
        '''), {'id': _uuid(public_id)}).mappings().all()
    return {**dict(head), 'lines': tuple(dict(row) for row in lines)}


def list_baskets(engine: Engine, location_id: int) -> tuple[dict[str, Any], ...]:
    with engine.connect() as connection:
        rows = connection.execute(text('''
            SELECT b.public_id, b.status, b.row_version, s.name AS supplier_name
            FROM cafeteria.order_baskets b
            JOIN cafeteria.suppliers s ON s.id=b.supplier_id
            WHERE b.location_id=:location ORDER BY b.updated_at DESC
        '''), {'location': location_id}).mappings().all()
    return tuple(dict(row) for row in rows)


def fill_from_demand(
    engine: Engine, scope: ShoppingScope, basket_public_id: str, *,
    expected_row_version: int, demands: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Draft lines from net need, rounded to packs. Never writes inventory movements."""
    lines: list[dict[str, Any]] = []
    filled: list[dict[str, Any]] = []
    needs: dict[str, Decimal] = {}
    for demand in demands:
        food = _uuid(str(demand['food_public_id']))
        needs[food] = needs.get(food, Decimal('0')) + Decimal(str(demand['quantity']))
    with engine.connect() as connection:
        for food, need in needs.items():
            article = connection.execute(text('''
                SELECT a.public_id, a.pack_size
                FROM cafeteria.supplier_articles a
                JOIN cafeteria.foods f ON f.id=a.food_id
                JOIN cafeteria.order_baskets b ON b.supplier_id=a.supplier_id
                WHERE b.public_id=CAST(:basket AS uuid) AND b.location_id=:location
                  AND f.public_id=CAST(:food AS uuid) AND a.location_id=:location
                  AND a.preferred AND a.active
            '''), {
                'basket': _uuid(basket_public_id), 'location': scope.location_id, 'food': food,
            }).mappings().one_or_none()
            if article is None:
                raise OrderBasketError('Kein bevorzugter Artikel für die Zutat.')
            pack = Decimal(str(article['pack_size']))
            packs = packs_for(need, pack)
            order_qty = packs * pack
            lines.append({'article_public_id': str(article['public_id']), 'quantity': str(order_qty)})
            filled.append({
                'article_public_id': str(article['public_id']),
                'raw_quantity': need,
                'order_quantity': order_qty,
                'pack_size': pack,
            })
    replace_basket_lines(
        engine, scope, basket_public_id, expected_row_version=expected_row_version, lines=lines,
    )
    return tuple(filled)
