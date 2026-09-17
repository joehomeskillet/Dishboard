"""Supplier catalog: preferred unique per food, articles without food allowed."""
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

import pytest

from cafeteria.auth.local_users import ActorExpectation
from cafeteria.master_data_types import MasterDataConflictError
from cafeteria.supplier_store import create_article, create_supplier
from prepared_food_fixtures import create_food, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_preferred_unique_and_article_without_food(prepared):  # noqa: F811
    owner, engine, ids = prepared
    actor = ActorExpectation(ids['actor'], ids['authz'])
    supplier = create_supplier(engine, actor, {'code': 'HOFER', 'name': 'Hofer'})
    food = create_food(engine, ids, 'Mehl', unit='KG')
    first = create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': food['public_id'],
        'article_code': 'MEHL-1', 'name': 'Mehl 1kg', 'order_unit_code': 'KG',
        'pack_size': '1', 'preferred': True,
    })
    assert first.public_id
    with pytest.raises((MasterDataConflictError, DBAPIError)):
        create_article(engine, actor, {
            'supplier_public_id': supplier.public_id, 'food_public_id': food['public_id'],
            'article_code': 'MEHL-2', 'name': 'Mehl alt', 'order_unit_code': 'KG',
            'pack_size': '1', 'preferred': True,
        })
    free = create_article(engine, actor, {
        'supplier_public_id': supplier.public_id, 'food_public_id': None,
        'article_code': 'FREI-1', 'name': 'Putzmittel', 'order_unit_code': 'STK',
        'pack_size': '1', 'preferred': False,
    })
    with owner.connect() as connection:
        without = connection.execute(text(
            'SELECT food_id FROM cafeteria.supplier_articles WHERE public_id=CAST(:id AS uuid)'
        ), {'id': free.public_id}).scalar_one()
    assert without is None
