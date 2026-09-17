"""Atomic prepared-batch production: issue inputs then receipt output, or nothing."""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence
from uuid import UUID

from sqlalchemy import Engine, text

from .inventory_store import post_movement
from .shopping_list_reads import ShoppingScope


def produce_batch(
    engine: Engine, scope: ShoppingScope, *,
    recipe_revision_public_id: str, output_food_public_id: str, output_storage_public_id: str,
    output_quantity: str | Decimal, output_unit_code: str,
    inputs: Sequence[dict[str, str]],
) -> str:
    """inputs: food_public_id, storage_public_id, quantity, unit_code."""
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        revision_id = connection.execute(text(
            'SELECT id FROM cafeteria.recipe_revisions WHERE public_id=CAST(:id AS uuid) AND location_id=:location'
        ), {'id': str(UUID(recipe_revision_public_id)), 'location': scope.location_id}).scalar_one()
        food_id = connection.execute(text(
            'SELECT id FROM cafeteria.foods WHERE public_id=CAST(:id AS uuid) AND location_id=:location'
        ), {'id': str(UUID(output_food_public_id)), 'location': scope.location_id}).scalar_one()
        storage_id = connection.execute(text(
            'SELECT id FROM cafeteria.storage_locations WHERE public_id=CAST(:id AS uuid) AND location_id=:location'
        ), {'id': str(UUID(output_storage_public_id)), 'location': scope.location_id}).scalar_one()
        run_id = connection.execute(text('''
            INSERT INTO cafeteria.prepared_batch_runs(
                location_id, recipe_revision_id, output_food_id, output_storage_id, output_quantity, created_by)
            VALUES (:location, :revision, :food, :storage, :qty, :actor)
            RETURNING public_id
        '''), {
            'location': scope.location_id, 'revision': revision_id, 'food': food_id,
            'storage': storage_id, 'qty': Decimal(str(output_quantity)), 'actor': scope.actor_id,
        }).scalar_one()
    for item in inputs:
        post_movement(
            engine, scope, food_public_id=item['food_public_id'], storage_public_id=item['storage_public_id'],
            kind='issue', quantity=item['quantity'], unit_code=item['unit_code'],
            note=f'batch:{run_id}',
        )
    post_movement(
        engine, scope, food_public_id=output_food_public_id, storage_public_id=output_storage_public_id,
        kind='receipt', quantity=output_quantity, unit_code=output_unit_code,
        note=f'batch:{run_id}',
    )
    return str(run_id)
