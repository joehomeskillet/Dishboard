"""Count 5→3 books 2 / sign -1; 3→3 posted without movement."""
from decimal import Decimal

from sqlalchemy import text

from cafeteria.inventory_store import balance, post_count, post_movement
from cafeteria.shopping_list_reads import ShoppingScope
from prepared_food_fixtures import create_food, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_count_five_to_three_then_noop(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Zucker', unit='G')
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    storage = ids['storage']
    post_movement(engine, scope, food_public_id=food['public_id'], storage_public_id=storage,
                  kind='receipt', quantity='5', unit_code='KG')
    first = post_count(engine, scope, food_public_id=food['public_id'], storage_public_id=storage,
                       counted_quantity='3', unit_code='KG')
    assert first['movement_public_id']
    assert first['sign'] == -1
    assert first['delta'] == Decimal('2')
    stock = balance(engine, ids['location'], food['public_id'], storage)
    assert stock['quantity'] == Decimal('3000')
    with owner.connect() as connection:
        row = connection.execute(text(
            'SELECT kind, quantity, sign FROM cafeteria.inventory_movements WHERE public_id=CAST(:id AS uuid)'
        ), {'id': first['movement_public_id']}).mappings().one()
    assert row['kind'] == 'count_adjust'
    assert row['quantity'] == Decimal('2')
    assert row['sign'] == -1
    second = post_count(engine, scope, food_public_id=food['public_id'], storage_public_id=storage,
                        counted_quantity='3', unit_code='KG')
    assert second['movement_public_id'] is None
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.inventory_movements')).scalar_one() == 2
    assert balance(engine, ids['location'], food['public_id'], storage)['quantity'] == Decimal('3000')
