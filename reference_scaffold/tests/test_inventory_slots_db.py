"""Lager slots follow Grundlagen food_storage_locations, not UUID typing."""
from decimal import Decimal

from cafeteria.inventory_store import list_assigned_slots, post_movement
from cafeteria.shopping_list_reads import ShoppingScope
from prepared_food_fixtures import create_food, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_assigned_slot_unknown_until_movement(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Lagermehl', unit='G')
    slots = list_assigned_slots(engine, ids['location'])
    match = [item for item in slots if item['food_public_id'] == food['public_id']]
    assert len(match) == 1
    assert match[0]['storage_public_id'] == ids['storage']
    assert match[0]['captured'] is False
    assert match[0]['label'] == 'Kein Bestand erfasst'
    assert match[0]['food_name'] == 'Lagermehl'
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    post_movement(
        engine, scope, food_public_id=food['public_id'], storage_public_id=ids['storage'],
        kind='receipt', quantity='5', unit_code='KG',
    )
    after = [item for item in list_assigned_slots(engine, ids['location'])
             if item['food_public_id'] == food['public_id']][0]
    assert after['captured'] is True
    assert after['quantity'] == Decimal('5000')
    assert after['unit_code'] == 'G'
