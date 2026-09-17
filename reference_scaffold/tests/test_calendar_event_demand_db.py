"""Event demand copies recipe revision and target portion; reader unions by date."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from cafeteria.calendar_event_demand import replace_event_demand
from cafeteria.calendar_event_store import EventScope, create_event
from cafeteria.shopping_list_reads import ShoppingScope, candidate_components
from prepared_food_fixtures import create_food, create_recipe, freeze, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_copied_target_quantity_survives_and_unions_into_candidates(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Anlasszutat', unit='G')
    recipe = create_recipe(engine, ids, [food], name='Anlassrezept', unit='G', quantity='4')
    frozen = freeze(engine, ids, recipe)
    event_scope = EventScope(ids['actor'], ids['location'], ids['authz'])
    event_id = create_event(
        engine, event_scope, event_date=date(2026, 9, 25), title='Festessen',
        profile_scope='both', guest_count=10,
    )
    replace_event_demand(engine, event_scope, event_id, [{
        'recipe_revision_public_id': frozen['public_id'],
        'target_quantity': '8',
        'target_quantity_unit_code': 'G',
        'component_text': 'Hauptgang',
    }])
    with owner.begin() as connection:
        copied = connection.execute(text(
            'SELECT target_quantity FROM cafeteria.kitchen_event_demand_items d '
            'JOIN cafeteria.kitchen_events e ON e.id=d.event_id '
            'WHERE e.public_id=CAST(:id AS uuid)'
        ), {'id': event_id}).scalar_one()
    assert str(copied) in ('8', '8.000000')
    shop = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    rows = candidate_components(engine, shop, date_from=date(2026, 9, 25), date_to=date(2026, 9, 25))
    event_rows = [row for row in rows if row.get('source') == 'event']
    assert event_rows
    assert event_rows[0]['target_quantity'] in ('8', '8.000000')
    assert event_rows[0]['recipe_revision_public_id'] == str(frozen['public_id'])
    assert event_rows[0]['meal_period_display_name'] == 'Anlass'
