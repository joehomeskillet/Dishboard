"""Append-only inventory journal. No stock column on foods. Unknown until first capture."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from .inventory_demand import net_demand
from .quantities import FoodFactors, QuantityError, Unit, convert
from .shopping_list_reads import ShoppingScope


class InventoryError(ValueError):
    pass


class InventoryInsufficientError(InventoryError):
    pass


def _uuid(value: str) -> str:
    return str(UUID(value))


def _unit_from_row(row: Any) -> dict[str, Any]:
    return {
        'public_id': str(row['public_id']),
        'code': row['code'],
        'dimension': row['dimension'],
        'base_factor': None if row['base_factor'] is None else str(row['base_factor']),
    }


def _to_base(quantity: Decimal, src: dict[str, Any], base: dict[str, Any], factors: dict[str, Any]) -> Decimal:
    source = Unit(str(src['code']), str(src['dimension']),
                  None if src.get('base_factor') in (None, 'null') else Decimal(str(src['base_factor'])))
    target = Unit(str(base['code']), str(base['dimension']),
                  None if base.get('base_factor') in (None, 'null') else Decimal(str(base['base_factor'])))
    food = FoodFactors(
        None if factors.get('density_g_per_ml') in (None, 'null') else Decimal(str(factors['density_g_per_ml'])),
        None if factors.get('piece_weight_g') in (None, 'null') else Decimal(str(factors['piece_weight_g'])),
    )
    return convert(quantity, source, target, food)


def _ensure_account(connection, scope: ShoppingScope, food_public_id: str, storage_public_id: str) -> dict[str, Any]:
    account = connection.execute(text('''
        SELECT a.id, a.public_id, a.base_unit_snapshot, a.food_factors_snapshot
        FROM cafeteria.inventory_accounts a
        JOIN cafeteria.foods f ON f.id=a.food_id
        JOIN cafeteria.storage_locations s ON s.id=a.storage_location_id
        WHERE a.location_id=:location AND f.public_id=CAST(:food AS uuid)
          AND s.public_id=CAST(:storage AS uuid)
    '''), {'location': scope.location_id, 'food': _uuid(food_public_id), 'storage': _uuid(storage_public_id)}).mappings().one_or_none()
    if account is not None:
        return dict(account)
    food = connection.execute(text('''
        SELECT f.id AS food_id, f.density_g_per_ml, f.piece_weight_g, u.id AS unit_id, u.public_id, u.code, u.dimension, u.base_factor
        FROM cafeteria.foods f JOIN cafeteria.measurement_units u ON u.id=f.base_unit_id
        WHERE f.public_id=CAST(:food AS uuid) AND f.location_id=:location
    '''), {'food': _uuid(food_public_id), 'location': scope.location_id}).mappings().one()
    storage = connection.execute(text(
        'SELECT id FROM cafeteria.storage_locations WHERE public_id=CAST(:id AS uuid) AND location_id=:location'
    ), {'id': _uuid(storage_public_id), 'location': scope.location_id}).scalar_one()
    snapshot = _unit_from_row(food)
    factors = {
        'density_g_per_ml': None if food['density_g_per_ml'] is None else str(food['density_g_per_ml']),
        'piece_weight_g': None if food['piece_weight_g'] is None else str(food['piece_weight_g']),
    }
    return dict(connection.execute(text('''
        INSERT INTO cafeteria.inventory_accounts(
            location_id, food_id, storage_location_id, base_unit_id, base_unit_snapshot, food_factors_snapshot)
        VALUES (:location, :food, :storage, :unit, CAST(:snap AS jsonb), CAST(:factors AS jsonb))
        RETURNING id, public_id, base_unit_snapshot, food_factors_snapshot
    '''), {
        'location': scope.location_id, 'food': food['food_id'], 'storage': storage,
        'unit': food['unit_id'], 'snap': json.dumps(snapshot),
        'factors': json.dumps(factors),
    }).mappings().one())


def _lock_account(connection, account_id: int) -> None:
    connection.execute(text(
        'SELECT id FROM cafeteria.inventory_accounts WHERE id=:id FOR UPDATE'
    ), {'id': account_id}).scalar_one()


def _sum_base(connection, account_id: int) -> Decimal:
    current = connection.execute(text(
        'SELECT COALESCE(SUM(sign * normalized_base_quantity), 0) FROM cafeteria.inventory_movements WHERE account_id=:id'
    ), {'id': account_id}).scalar_one()
    return Decimal(str(current))


def _lookup_unit(connection, unit_code: str) -> dict[str, Any]:
    return dict(connection.execute(text(
        'SELECT public_id, code, dimension, base_factor FROM cafeteria.measurement_units WHERE code=:code'
    ), {'code': unit_code}).mappings().one())


def _sign_for(kind: str, sign: int | None) -> int:
    if kind in ('receipt', 'transfer_in'):
        return 1
    if kind in ('issue', 'transfer_out'):
        return -1
    if kind in ('count_adjust', 'correction'):
        if sign not in (-1, 1):
            raise InventoryError('Korrektur braucht ein Vorzeichen.')
        return sign
    raise InventoryError('Ungültige Bewegungsart.')


def post_movement_on(
    connection, scope: ShoppingScope, *, food_public_id: str, storage_public_id: str,
    kind: str, quantity: str | Decimal, unit_code: str, note: str | None = None,
    sign: int | None = None,
) -> str:
    qty = Decimal(str(quantity))
    if qty <= 0:
        raise InventoryError('Menge muss positiv sein.')
    resolved = _sign_for(kind, sign)
    account = _ensure_account(connection, scope, food_public_id, storage_public_id)
    _lock_account(connection, account['id'])
    unit_snap = _unit_from_row(_lookup_unit(connection, unit_code))
    try:
        base_qty = _to_base(qty, unit_snap, account['base_unit_snapshot'], account['food_factors_snapshot'])
    except QuantityError as error:
        raise InventoryError(str(error)) from error
    if resolved < 0 and _sum_base(connection, account['id']) - base_qty < 0:
        raise InventoryInsufficientError('Bestand würde negativ.')
    return str(connection.execute(text('''
        INSERT INTO cafeteria.inventory_movements(
            account_id, kind, quantity, sign, unit_id, unit_snapshot, normalized_base_quantity, note, created_by)
        VALUES (:account, :kind, :qty, :sign,
                (SELECT id FROM cafeteria.measurement_units WHERE code=:unit),
                CAST(:usnap AS jsonb), :base, :note, :actor)
        RETURNING public_id
    '''), {
        'account': account['id'], 'kind': kind, 'qty': qty, 'sign': resolved,
        'unit': unit_code, 'usnap': json.dumps(unit_snap),
        'base': base_qty, 'note': note, 'actor': scope.actor_id,
    }).scalar_one())


def post_movement(
    engine: Engine, scope: ShoppingScope, *, food_public_id: str, storage_public_id: str,
    kind: str, quantity: str | Decimal, unit_code: str, note: str | None = None,
    sign: int | None = None,
) -> str:
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        return post_movement_on(
            connection, scope, food_public_id=food_public_id, storage_public_id=storage_public_id,
            kind=kind, quantity=quantity, unit_code=unit_code, note=note, sign=sign,
        )


def transfer(
    engine: Engine, scope: ShoppingScope, *, food_public_id: str,
    source_storage_public_id: str, dest_storage_public_id: str,
    quantity: str | Decimal, unit_code: str,
) -> dict[str, str]:
    if _uuid(source_storage_public_id) == _uuid(dest_storage_public_id):
        raise InventoryError('Quelle und Ziel müssen verschieden sein.')
    pair = str(uuid4())
    note = f'transfer:{pair}'
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        source = _ensure_account(connection, scope, food_public_id, source_storage_public_id)
        dest = _ensure_account(connection, scope, food_public_id, dest_storage_public_id)
        for account_id in sorted((source['id'], dest['id'])):
            _lock_account(connection, account_id)
        outgoing = post_movement_on(
            connection, scope, food_public_id=food_public_id, storage_public_id=source_storage_public_id,
            kind='transfer_out', quantity=quantity, unit_code=unit_code, note=note,
        )
        incoming = post_movement_on(
            connection, scope, food_public_id=food_public_id, storage_public_id=dest_storage_public_id,
            kind='transfer_in', quantity=quantity, unit_code=unit_code, note=note,
        )
    return {'pair': pair, 'transfer_out': outgoing, 'transfer_in': incoming}


def post_count(
    engine: Engine, scope: ShoppingScope, *, food_public_id: str, storage_public_id: str,
    counted_quantity: str | Decimal, unit_code: str,
) -> dict[str, Any]:
    counted = Decimal(str(counted_quantity))
    if counted < 0:
        raise InventoryError('Zählmenge darf nicht negativ sein.')
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        account = _ensure_account(connection, scope, food_public_id, storage_public_id)
        _lock_account(connection, account['id'])
        current = _sum_base(connection, account['id'])
        unit_snap = _unit_from_row(_lookup_unit(connection, unit_code))
        try:
            counted_base = Decimal('0') if counted == 0 else _to_base(
                counted, unit_snap, account['base_unit_snapshot'], account['food_factors_snapshot'])
        except QuantityError as error:
            raise InventoryError(str(error)) from error
        delta = counted_base - current
        if delta == 0:
            return {'posted': True, 'movement_public_id': None, 'delta': Decimal('0'), 'sign': None}
        sign = 1 if delta > 0 else -1
        abs_delta = abs(delta)
        qty_field = _to_base(
            abs_delta, account['base_unit_snapshot'], unit_snap, account['food_factors_snapshot'])
        public_id = post_movement_on(
            connection, scope, food_public_id=food_public_id, storage_public_id=storage_public_id,
            kind='count_adjust', quantity=qty_field, unit_code=unit_code, note='count', sign=sign,
        )
        return {'posted': True, 'movement_public_id': public_id, 'delta': qty_field, 'sign': sign}


def balance(engine: Engine, location_id: int, food_public_id: str, storage_public_id: str) -> dict[str, Any]:
    with engine.connect() as connection:
        row = connection.execute(text('''
            SELECT a.public_id, a.base_unit_snapshot,
                   (SELECT COALESCE(SUM(sign * normalized_base_quantity), 0)
                    FROM cafeteria.inventory_movements m WHERE m.account_id=a.id) AS qty
            FROM cafeteria.inventory_accounts a
            JOIN cafeteria.foods f ON f.id=a.food_id
            JOIN cafeteria.storage_locations s ON s.id=a.storage_location_id
            WHERE a.location_id=:location AND f.public_id=CAST(:food AS uuid)
              AND s.public_id=CAST(:storage AS uuid)
        '''), {
            'location': location_id, 'food': _uuid(food_public_id), 'storage': _uuid(storage_public_id),
        }).mappings().one_or_none()
    if row is None:
        return {'captured': False, 'quantity': None, 'unit_code': None, 'label': 'Kein Bestand erfasst'}
    snap = row['base_unit_snapshot']
    qty = Decimal(str(row['qty']))
    return {
        'captured': True,
        'quantity': qty,
        'unit_code': snap['code'],
        'label': f'{qty} {snap["code"]}',
    }


def list_assigned_slots(engine: Engine, location_id: int) -> tuple[dict[str, Any], ...]:
    """Food × Lagerort pairs from Grundlagen assignments. Unknown until first capture."""
    with engine.connect() as connection:
        rows = connection.execute(text('''
            SELECT f.public_id::text AS food_public_id, f.name AS food_name, u.code AS unit_code,
                   s.public_id::text AS storage_public_id, s.name AS storage_name,
                   a.id AS account_id, a.base_unit_snapshot,
                   (SELECT COALESCE(SUM(m.sign * m.normalized_base_quantity), 0)
                    FROM cafeteria.inventory_movements m WHERE m.account_id=a.id) AS qty
            FROM cafeteria.foods f
            JOIN cafeteria.food_storage_locations fs
              ON fs.food_id=f.id AND fs.location_id=f.location_id
            JOIN cafeteria.storage_locations s
              ON s.id=fs.storage_location_id AND s.location_id=fs.location_id
            JOIN cafeteria.measurement_units u ON u.id=f.base_unit_id
            LEFT JOIN cafeteria.inventory_accounts a
              ON a.food_id=f.id AND a.storage_location_id=s.id AND a.location_id=f.location_id
            WHERE f.location_id=:location AND f.active AND s.active
            ORDER BY lower(btrim(f.name)), s.sort_order, s.public_id
            LIMIT 200
        '''), {'location': location_id}).mappings().all()
    slots = []
    for row in rows:
        if row['account_id'] is None:
            slots.append({
                'food_public_id': row['food_public_id'], 'food_name': row['food_name'],
                'storage_public_id': row['storage_public_id'], 'storage_name': row['storage_name'],
                'captured': False, 'quantity': None, 'unit_code': row['unit_code'],
                'label': 'Kein Bestand erfasst',
            })
            continue
        snap = row['base_unit_snapshot']
        qty = Decimal(str(row['qty']))
        unit = snap['code']
        slots.append({
            'food_public_id': row['food_public_id'], 'food_name': row['food_name'],
            'storage_public_id': row['storage_public_id'], 'storage_name': row['storage_name'],
            'captured': True, 'quantity': qty, 'unit_code': unit,
            'label': f'{qty} {unit}',
        })
    return tuple(slots)


def food_stock(engine: Engine, location_id: int, food_public_id: str) -> dict[str, Any]:
    """Sum captured accounts for one food. Mixed frozen bases stay unknown."""
    with engine.connect() as connection:
        rows = connection.execute(text('''
            SELECT a.base_unit_snapshot,
                   (SELECT COALESCE(SUM(m.sign * m.normalized_base_quantity), 0)
                    FROM cafeteria.inventory_movements m WHERE m.account_id=a.id) AS qty
            FROM cafeteria.inventory_accounts a
            JOIN cafeteria.foods f ON f.id=a.food_id
            WHERE a.location_id=:location AND f.public_id=CAST(:food AS uuid)
        '''), {'location': location_id, 'food': _uuid(food_public_id)}).mappings().all()
    if not rows:
        return {'captured': False, 'quantity': None, 'unit_code': None, 'label': 'Kein Bestand erfasst'}
    codes = {row['base_unit_snapshot']['code'] for row in rows}
    if len(codes) != 1:
        return {'captured': False, 'quantity': None, 'unit_code': None, 'label': 'Bestand nicht vergleichbar'}
    qty = sum((Decimal(str(row['qty'])) for row in rows), Decimal('0'))
    code = next(iter(codes))
    return {'captured': True, 'quantity': qty, 'unit_code': code, 'label': f'{qty} {code}'}


def _convert_need(connection, quantity: Decimal, from_code: str, to_code: str,
                  food_public_id: str, location_id: int) -> Decimal:
    if from_code == to_code:
        return quantity
    src = _unit_from_row(_lookup_unit(connection, from_code))
    dest = _unit_from_row(_lookup_unit(connection, to_code))
    food = connection.execute(text('''
        SELECT density_g_per_ml, piece_weight_g FROM cafeteria.foods
        WHERE public_id=CAST(:food AS uuid) AND location_id=:location
    '''), {'food': _uuid(food_public_id), 'location': location_id}).mappings().one()
    factors = {
        'density_g_per_ml': None if food['density_g_per_ml'] is None else str(food['density_g_per_ml']),
        'piece_weight_g': None if food['piece_weight_g'] is None else str(food['piece_weight_g']),
    }
    return _to_base(quantity, src, dest, factors)


def attach_stock(engine: Engine, location_id: int, lines: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Annotate shopping lines with captured stock and net demand. Unknown stock does not reduce need."""
    attached = []
    with engine.connect() as connection:
        for line in lines:
            food = line.get('food_public_id')
            raw = line.get('quantity')
            need = None if raw in (None, '') else Decimal(str(raw))
            if not food:
                attached.append({
                    **line,
                    'stock': {'captured': False, 'quantity': None, 'unit_code': None, 'label': 'Kein Bestand erfasst'},
                    'net': {'complete': False, 'quantity': None, 'reason': 'Keine Zutat'},
                })
                continue
            stock = food_stock(engine, location_id, str(food))
            if need is None or not stock.get('captured') or not stock.get('unit_code') or not line.get('unit_code'):
                attached.append({**line, 'stock': stock, 'net': net_demand(need, stock)})
                continue
            try:
                converted = _convert_need(
                    connection, need, str(line['unit_code']), str(stock['unit_code']),
                    str(food), location_id,
                )
            except QuantityError:
                attached.append({
                    **line, 'stock': stock,
                    'net': {'complete': False, 'quantity': None, 'reason': 'Bestand nicht umrechenbar'},
                })
                continue
            attached.append({**line, 'stock': stock, 'net': net_demand(converted, stock)})
    return tuple(attached)
