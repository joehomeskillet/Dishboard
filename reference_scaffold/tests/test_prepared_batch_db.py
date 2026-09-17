"""produce_batch is one transaction: partial failure leaves no run and no new movements."""
from decimal import Decimal

import pytest
from sqlalchemy import text

from cafeteria.inventory_store import InventoryInsufficientError, balance, post_movement
from cafeteria.prepared_batch import produce_batch
from cafeteria.shopping_list_reads import ShoppingScope
from prepared_food_fixtures import create_food, create_recipe, freeze, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_produce_batch_atomic_and_keeps_prior_journal(prepared):  # noqa: F811
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Roh', unit='G')
    output = create_food(engine, ids, 'Fond', unit='G')
    recipe = create_recipe(engine, ids, [raw], name='Fondrezept', unit='G', quantity='1')
    frozen = freeze(engine, ids, recipe)
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    storage = ids['storage']
    first = post_movement(engine, scope, food_public_id=raw['public_id'], storage_public_id=storage,
                          kind='receipt', quantity='5', unit_code='KG')
    run = produce_batch(
        engine, scope, recipe_revision_public_id=frozen['public_id'],
        output_food_public_id=output['public_id'], output_storage_public_id=storage,
        output_quantity='1', output_unit_code='KG',
        inputs=[{
            'food_public_id': raw['public_id'], 'storage_public_id': storage,
            'quantity': '1', 'unit_code': 'KG',
        }],
    )
    assert run
    assert balance(engine, ids['location'], raw['public_id'], storage)['quantity'] == Decimal('4000')
    assert balance(engine, ids['location'], output['public_id'], storage)['quantity'] == Decimal('1000')
    with pytest.raises(InventoryInsufficientError):
        produce_batch(
            engine, scope, recipe_revision_public_id=frozen['public_id'],
            output_food_public_id=output['public_id'], output_storage_public_id=storage,
            output_quantity='8', output_unit_code='KG',
            inputs=[{
                'food_public_id': raw['public_id'], 'storage_public_id': storage,
                'quantity': '8', 'unit_code': 'KG',
            }],
        )
    with owner.connect() as connection:
        runs = connection.execute(text('SELECT count(*) FROM cafeteria.prepared_batch_runs')).scalar_one()
        movements = connection.execute(text('SELECT count(*) FROM cafeteria.inventory_movements')).scalar_one()
        still = connection.execute(text(
            'SELECT 1 FROM cafeteria.inventory_movements WHERE public_id=CAST(:id AS uuid)'
        ), {'id': first}).scalar_one()
    assert runs == 1
    assert movements == 3
    assert still == 1
    assert balance(engine, ids['location'], raw['public_id'], storage)['quantity'] == Decimal('4000')
