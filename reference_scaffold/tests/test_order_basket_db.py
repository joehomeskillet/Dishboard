"""Basket replace is UPDATE-in-place; stale CAS does not partial-write."""
from decimal import Decimal

import pytest
from sqlalchemy import text

from cafeteria.auth.local_users import ActorExpectation
from cafeteria.calendar_event_store import CalendarEventConflictError
from cafeteria.order_basket_store import create_basket, fill_from_demand, get_basket, replace_basket_lines
from cafeteria.shopping_list_reads import ShoppingScope
from cafeteria.supplier_store import create_article, create_supplier
from prepared_food_fixtures import create_food, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_stale_409_without_partial_replace(prepared):  # noqa: F811
    owner, engine, ids = prepared
    actor = ActorExpectation(ids['actor'], ids['authz'])
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    food = create_food(engine, ids, 'Korbzutat', unit='KG')
    supplier = create_supplier(engine, actor, {'code': 'SUD', 'name': 'Süd'})
    article = create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': food['public_id'],
        'article_code': 'MEHL-1', 'name': 'Mehl', 'order_unit_code': 'KG',
        'pack_size': '1', 'preferred': True,
    })
    basket_id = create_basket(engine, scope, supplier.public_id)
    head = get_basket(engine, ids['location'], basket_id)
    replace_basket_lines(
        engine, scope, basket_id, expected_row_version=head['row_version'],
        lines=[{'article_public_id': article.public_id, 'quantity': '1', 'raw_quantity': '1'}],
    )
    saved = get_basket(engine, ids['location'], basket_id)
    assert Decimal(str(saved['lines'][0]['quantity'])) == Decimal('1')
    with pytest.raises(CalendarEventConflictError):
        replace_basket_lines(
            engine, scope, basket_id, expected_row_version=saved['row_version'] - 1,
            lines=[{'article_public_id': article.public_id, 'quantity': '9', 'raw_quantity': '9'}],
        )
    after_stale = get_basket(engine, ids['location'], basket_id)
    assert Decimal(str(after_stale['lines'][0]['quantity'])) == Decimal('1')
    assert after_stale['row_version'] == saved['row_version']
    replace_basket_lines(
        engine, scope, basket_id, expected_row_version=after_stale['row_version'],
        lines=[{'article_public_id': article.public_id, 'quantity': '2', 'raw_quantity': '1.5'}],
    )
    updated = get_basket(engine, ids['location'], basket_id)
    assert Decimal(str(updated['lines'][0]['quantity'])) == Decimal('2')
    assert Decimal(str(updated['lines'][0]['raw_quantity'])) == Decimal('1.5')
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.order_basket_lines')).scalar_one() == 1


def test_fill_persists_raw_quantity_next_to_packs(prepared):  # noqa: F811
    owner, engine, ids = prepared
    actor = ActorExpectation(ids['actor'], ids['authz'])
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    food = create_food(engine, ids, 'Rohkorb', unit='KG')
    supplier = create_supplier(engine, actor, {'code': 'OST', 'name': 'Ost'})
    create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': food['public_id'],
        'article_code': 'REIS-25', 'name': 'Reis 2.5', 'order_unit_code': 'KG',
        'pack_size': '2.5', 'preferred': True,
    })
    basket_id = create_basket(engine, scope, supplier.public_id)
    basket = get_basket(engine, ids['location'], basket_id)
    fill_from_demand(
        engine, scope, basket_id, expected_row_version=basket['row_version'],
        demands=[{'food_public_id': food['public_id'], 'quantity': '8'}],
    )
    stored = get_basket(engine, ids['location'], basket_id)
    assert Decimal(str(stored['lines'][0]['quantity'])) == Decimal('10.0')
    assert Decimal(str(stored['lines'][0]['raw_quantity'])) == Decimal('8')
