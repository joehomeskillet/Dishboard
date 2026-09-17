"""Inventory journal: unknown until first movement; no negative stock; frozen base."""
from decimal import Decimal

import pytest
from sqlalchemy import text

from cafeteria.inventory_store import InventoryInsufficientError, balance, post_movement
from cafeteria.shopping_list_reads import ShoppingScope
from prepared_food_fixtures import create_food, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)
from test_master_data_db import STORAGE_PUBLIC_ID


def test_unknown_until_movement_then_kg_minus_issue(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Reis', unit='G')
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    storage = ids.get('storage') or STORAGE_PUBLIC_ID
    empty = balance(engine, ids['location'], food['public_id'], storage)
    assert empty['captured'] is False
    assert empty['label'] == 'Kein Bestand erfasst'
    post_movement(engine, scope, food_public_id=food['public_id'], storage_public_id=storage,
                  kind='receipt', quantity='5', unit_code='KG')
    post_movement(engine, scope, food_public_id=food['public_id'], storage_public_id=storage,
                  kind='issue', quantity='1', unit_code='KG')
    stock = balance(engine, ids['location'], food['public_id'], storage)
    assert stock['captured'] is True
    assert stock['quantity'] == Decimal('4000')
    assert stock['unit_code'] == 'G'
    with pytest.raises(InventoryInsufficientError):
        post_movement(engine, scope, food_public_id=food['public_id'], storage_public_id=storage,
                      kind='issue', quantity='9', unit_code='KG')
    with owner.connect() as connection:
        cols = connection.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='cafeteria' AND table_name='foods'"
        )).scalars().all()
    assert 'stock' not in cols and 'quantity_on_hand' not in cols
