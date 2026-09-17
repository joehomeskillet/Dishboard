"""Atomic transfer: two opposing lines, same normalized quantity, one TX."""
from decimal import Decimal

import pytest
from sqlalchemy import text

from cafeteria.inventory_store import InventoryInsufficientError, balance, post_movement, transfer
from cafeteria.shopping_list_reads import ShoppingScope
from prepared_food_fixtures import create_food, execute, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_transfer_pair_and_insufficient_rolls_back(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Mehl', unit='G')
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    source = ids['storage']
    dest = execute(engine, '''SELECT cafeteria.create_storage_location_v21(
        :actor,:authz,:location,NULL,NULL,CAST(:payload AS jsonb))''', ids,
        {'code': 'STORE_B', 'name': 'Zweiter Ort', 'sort_order': 2})['public_id']
    post_movement(engine, scope, food_public_id=food['public_id'], storage_public_id=source,
                  kind='receipt', quantity='5', unit_code='KG')
    pair = transfer(
        engine, scope, food_public_id=food['public_id'],
        source_storage_public_id=source, dest_storage_public_id=dest,
        quantity='1', unit_code='KG',
    )
    assert pair['transfer_out'] != pair['transfer_in']
    assert balance(engine, ids['location'], food['public_id'], source)['quantity'] == Decimal('4000')
    assert balance(engine, ids['location'], food['public_id'], dest)['quantity'] == Decimal('1000')
    with owner.connect() as connection:
        rows = connection.execute(text(
            'SELECT kind, sign, normalized_base_quantity, note FROM cafeteria.inventory_movements '
            'WHERE note=:note ORDER BY kind'
        ), {'note': f'transfer:{pair["pair"]}'}).mappings().all()
    assert [row['kind'] for row in rows] == ['transfer_in', 'transfer_out']
    assert rows[0]['normalized_base_quantity'] == rows[1]['normalized_base_quantity'] == Decimal('1000')
    assert rows[0]['sign'] == 1 and rows[1]['sign'] == -1
    with pytest.raises(InventoryInsufficientError):
        transfer(
            engine, scope, food_public_id=food['public_id'],
            source_storage_public_id=source, dest_storage_public_id=dest,
            quantity='9', unit_code='KG',
        )
    assert balance(engine, ids['location'], food['public_id'], source)['quantity'] == Decimal('4000')
    assert balance(engine, ids['location'], food['public_id'], dest)['quantity'] == Decimal('1000')
    with owner.connect() as connection:
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.inventory_movements'
        )).scalar_one() == 3
