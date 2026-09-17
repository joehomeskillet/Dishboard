"""Calculation receipts keep patient cost keys forbidden and replay/409."""
from datetime import date

import pytest
from sqlalchemy import text

from cafeteria.auth.local_users import ActorExpectation
from cafeteria.calculation_receipts import CalculationReceiptConflictError, append_receipt, patient_forbidden_keys
from cafeteria.food_price_store import append_price_revision
from cafeteria.patient_payload import PATIENT_FORBIDDEN_COST_KEYS
from cafeteria.recipe_cost import project_recipe
from cafeteria.shopping_list_reads import ShoppingScope
from prepared_food_fixtures import create_food, execute, freeze, prepared, recipe_payload  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def test_patient_guard_unchanged() -> None:
    keys = patient_forbidden_keys()
    assert keys is PATIENT_FORBIDDEN_COST_KEYS
    assert 'costtotal' in keys


def test_append_receipt_replay_same_hash_conflict_on_change(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Belegzutat', unit='G')
    actor = ActorExpectation(ids['actor'], ids['authz'])
    first_price = append_price_revision(
        engine, actor, food['public_id'],
        intervals=[{'valid_from': '2026-01-01', 'valid_to': None, 'unit_price': '4.00', 'unit_code': 'KG'}],
    )
    payload = recipe_payload([food], name='Belegrezept', unit='G', quantity='1')
    payload['ingredients'][0]['quantity'] = '250'
    recipe = execute(engine, '''SELECT cafeteria.create_recipe_v22(:actor,:authz,:location,NULL,NULL,
        CAST(:payload AS jsonb))''', ids, payload)
    frozen = freeze(engine, ids, recipe)
    projection = project_recipe(
        engine, frozen['public_id'], date(2026, 9, 17),
        {food['public_id']: first_price['revision_public_id']},
    )
    blob = {
        'complete': projection['complete'],
        'total': str(projection['total']),
        'as_of': projection['as_of'],
    }
    scope = ShoppingScope(ids['actor'], ids['location'], ids['authz'])
    first = append_receipt(engine, scope, kind='recipe', subject_public_id=frozen['public_id'], payload=blob)
    replay = append_receipt(engine, scope, kind='recipe', subject_public_id=frozen['public_id'], payload=blob)
    assert replay == first
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.calculation_receipts')).scalar_one() == 1
    with pytest.raises(CalculationReceiptConflictError):
        append_receipt(
            engine, scope, kind='recipe', subject_public_id=frozen['public_id'], payload={**blob, 'total': '9.99'},
        )
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.calculation_receipts')).scalar_one() == 1
