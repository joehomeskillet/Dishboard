"""Demand fill rounds packs into a draft basket and never writes inventory."""
from decimal import Decimal

from sqlalchemy import text

from cafeteria.auth.local_users import ActorExpectation
from cafeteria.order_basket_store import create_basket, fill_from_demand, get_basket
from cafeteria.shopping_list_reads import ShoppingScope
from cafeteria.supplier_store import create_article, create_supplier
from prepared_food_fixtures import create_food, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_fill_from_demand_rounds_packs_without_journal(prepared):  # noqa: F811
    owner, engine, ids = prepared
    actor = ActorExpectation(ids['actor'], ids['authz'])
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    food = create_food(engine, ids, 'Reisbedarf', unit='KG')
    supplier = create_supplier(engine, actor, {'code': 'NORD', 'name': 'Nord'})
    create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': food['public_id'],
        'article_code': 'REIS-25', 'name': 'Reis 2.5', 'order_unit_code': 'KG',
        'pack_size': '2.5', 'preferred': True,
    })
    basket_id = create_basket(engine, scope, supplier.public_id)
    basket = get_basket(engine, ids['location'], basket_id)
    filled = fill_from_demand(
        engine, scope, basket_id, expected_row_version=basket['row_version'],
        demands=[{'food_public_id': food['public_id'], 'quantity': '8'}],
    )
    assert filled[0]['raw_quantity'] == Decimal('8')
    assert filled[0]['order_quantity'] == Decimal('10.0')
    updated = get_basket(engine, ids['location'], basket_id)
    assert updated['status'] == 'draft'
    assert Decimal(str(updated['lines'][0]['quantity'])) == Decimal('10.0')
    assert Decimal(str(updated['lines'][0]['raw_quantity'])) == Decimal('8')
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.inventory_movements')).scalar_one() == 0
