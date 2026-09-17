"""Append-only inventory journal. No stock column on foods. Unknown until first movement."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from .quantities import FoodFactors, QuantityError, Unit, convert
from .shopping_list_reads import ShoppingScope, _transaction as _shop_tx


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


def post_movement(
    engine: Engine, scope: ShoppingScope, *, food_public_id: str, storage_public_id: str,
    kind: str, quantity: str | Decimal, unit_code: str, note: str | None = None,
) -> str:
    qty = Decimal(str(quantity))
    if qty <= 0:
        raise InventoryError('Menge muss positiv sein.')
    sign = 1 if kind in ('receipt', 'transfer_in') else -1
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        account = _ensure_account(connection, scope, food_public_id, storage_public_id)
        unit = connection.execute(text(
            'SELECT public_id, code, dimension, base_factor FROM cafeteria.measurement_units WHERE code=:code'
        ), {'code': unit_code}).mappings().one()
        unit_snap = _unit_from_row(unit)
        base_qty = _to_base(qty, unit_snap, account['base_unit_snapshot'], account['food_factors_snapshot'])
        if sign < 0:
            current = connection.execute(text(
                'SELECT COALESCE(SUM(sign * normalized_base_quantity), 0) FROM cafeteria.inventory_movements WHERE account_id=:id'
            ), {'id': account['id']}).scalar_one()
            if Decimal(str(current)) - base_qty < 0:
                raise InventoryInsufficientError('Bestand würde negativ.')
        public_id = connection.execute(text('''
            INSERT INTO cafeteria.inventory_movements(
                account_id, kind, quantity, sign, unit_id, unit_snapshot, normalized_base_quantity, note, created_by)
            VALUES (:account, :kind, :qty, :sign,
                    (SELECT id FROM cafeteria.measurement_units WHERE code=:unit),
                    CAST(:usnap AS jsonb), :base, :note, :actor)
            RETURNING public_id
        '''), {
            'account': account['id'], 'kind': kind, 'qty': qty, 'sign': sign,
            'unit': unit_code, 'usnap': json.dumps(unit_snap),
            'base': base_qty, 'note': note, 'actor': scope.actor_id,
        }).scalar_one()
        return str(public_id)


def balance(engine: Engine, location_id: int, food_public_id: str, storage_public_id: str) -> dict[str, Any]:
    with engine.connect() as connection:
        row = connection.execute(text('''
            SELECT a.public_id, a.base_unit_snapshot,
                   (SELECT COALESCE(SUM(sign * normalized_base_quantity), 0)
                    FROM cafeteria.inventory_movements m WHERE m.account_id=a.id) AS qty,
                   EXISTS (SELECT 1 FROM cafeteria.inventory_movements m WHERE m.account_id=a.id) AS captured
            FROM cafeteria.inventory_accounts a
            JOIN cafeteria.foods f ON f.id=a.food_id
            JOIN cafeteria.storage_locations s ON s.id=a.storage_location_id
            WHERE a.location_id=:location AND f.public_id=CAST(:food AS uuid)
              AND s.public_id=CAST(:storage AS uuid)
        '''), {
            'location': location_id, 'food': _uuid(food_public_id), 'storage': _uuid(storage_public_id),
        }).mappings().one_or_none()
    if row is None or not row['captured']:
        return {'captured': False, 'quantity': None, 'unit_code': None, 'label': 'Kein Bestand erfasst'}
    snap = row['base_unit_snapshot']
    return {
        'captured': True,
        'quantity': Decimal(str(row['qty'])),
        'unit_code': snap['code'],
        'label': f"{row['qty']} {snap['code']}",
    }
