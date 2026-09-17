"""Recipe projection: 250 G at 4.00 CHF/KG is 1.00 CHF; old editions stay frozen."""
from datetime import date
from decimal import Decimal

from sqlalchemy import text

from cafeteria.auth.local_users import ActorExpectation
from cafeteria.food_price_store import append_price_revision
from cafeteria.recipe_cost import project_menu, project_prepared, project_recipe
from prepared_food_fixtures import create_food, execute, freeze, prepared, recipe_payload  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_recipe_250g_at_four_per_kg_and_old_edition_stable(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Kartoffeln', unit='G')
    actor = ActorExpectation(ids['actor'], ids['authz'])
    first = append_price_revision(
        engine, actor, food['public_id'],
        intervals=[{'valid_from': '2026-01-01', 'valid_to': None, 'unit_price': '4.00', 'unit_code': 'KG'}],
    )
    payload = recipe_payload([food], name='Kartoffelpüree', unit='G', quantity='1')
    payload['ingredients'][0]['quantity'] = '250'
    payload['ingredients'][0]['unit_code'] = 'G'
    recipe = execute(engine, '''SELECT cafeteria.create_recipe_v22(:actor,:authz,:location,NULL,NULL,
        CAST(:payload AS jsonb))''', ids, payload)
    frozen = freeze(engine, ids, recipe)
    as_of = date(2026, 9, 17)
    prices = {food['public_id']: first['revision_public_id']}
    with owner.connect() as connection:
        receipts_before = connection.execute(text('SELECT count(*) FROM cafeteria.calculation_receipts')).scalar_one()
        audits_before = connection.execute(text('SELECT count(*) FROM cafeteria.audit_events')).scalar_one()
    projection = project_recipe(engine, frozen['public_id'], as_of, prices)
    assert projection['complete'] is True
    assert projection['total'] == Decimal('1.00')
    same = project_recipe(engine, frozen['public_id'], as_of, prices)
    assert same['total'] == projection['total']
    prepared_view = project_prepared(engine, frozen['public_id'], as_of, prices)
    assert prepared_view['total'] == Decimal('1.00')
    menu = project_menu(engine, [frozen['public_id']], as_of, prices)
    assert menu['total'] == Decimal('1.00')
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.calculation_receipts')).scalar_one() == receipts_before
        assert connection.execute(text('SELECT count(*) FROM cafeteria.audit_events')).scalar_one() == audits_before
    append_price_revision(
        engine, actor, food['public_id'], expected_head_version=int(first['row_version']),
        intervals=[{'valid_from': '2026-01-01', 'valid_to': None, 'unit_price': '9.00', 'unit_code': 'KG'}],
    )
    still = project_recipe(engine, frozen['public_id'], as_of, prices)
    assert still['total'] == Decimal('1.00')
    missing = project_recipe(engine, frozen['public_id'], as_of, {})
    assert missing['complete'] is False
    assert missing['total'] is None
