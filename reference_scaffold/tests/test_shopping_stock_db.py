"""Shopping lines subtract captured stock; unknown stock does not reduce need."""
from decimal import Decimal

from cafeteria.inventory_store import attach_stock, post_movement
from cafeteria.shopping_list_reads import ShoppingScope
from prepared_food_fixtures import create_food, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_unknown_stock_does_not_reduce_need(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'NettoReis', unit='G')
    lines = attach_stock(engine, ids['location'], [{
        'food_public_id': food['public_id'], 'quantity': '8', 'unit_code': 'KG', 'food_name': 'NettoReis',
    }])
    assert lines[0]['stock']['captured'] is False
    assert lines[0]['stock']['label'] == 'Kein Bestand erfasst'
    assert lines[0]['net']['complete'] is False
    assert lines[0]['net']['reason'] == 'Kein Bestand erfasst'


def test_need_eight_kg_minus_five_kg_is_three_thousand_g(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'NettoMehl', unit='G')
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    post_movement(
        engine, scope, food_public_id=food['public_id'], storage_public_id=ids['storage'],
        kind='receipt', quantity='5', unit_code='KG',
    )
    lines = attach_stock(engine, ids['location'], [{
        'food_public_id': food['public_id'], 'quantity': '8', 'unit_code': 'KG', 'food_name': 'NettoMehl',
    }])
    assert lines[0]['stock']['captured'] is True
    assert lines[0]['stock']['quantity'] == Decimal('5000')
    assert lines[0]['net']['complete'] is True
    assert lines[0]['net']['quantity'] == Decimal('3000')
    surplus = attach_stock(engine, ids['location'], [{
        'food_public_id': food['public_id'], 'quantity': '1', 'unit_code': 'KG',
    }])
    assert surplus[0]['net']['quantity'] == Decimal('0')
