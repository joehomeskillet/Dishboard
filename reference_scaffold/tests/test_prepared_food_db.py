"""Atomic Foods, explicit dependencies and least-privilege schema27 SQL contracts."""
import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prepared_food_fixtures import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, create_food, update_food,
    food_payload, create_recipe, preview, freeze, legacy_freeze, revision_snapshot, execute, state,
)
from prepared_food_fixtures import prepared as prepared


def test_complete_food_one_audit_noop_and_atomic_update(prepared):
    owner, engine, ids = prepared
    before = state(owner)
    food = create_food(engine, ids)
    assert food['row_version'] == 1
    created = state(owner)
    assert len(created['audit_events']) == len(before['audit_events']) + 1
    assert len(created['food_storage_locations']) == 1
    assert update_food(engine, ids, food, food_payload(ids, '  Gemüse  ')) == food
    assert state(owner) == created
    updated = update_food(engine, ids, food, food_payload(ids, 'Feines Gemüse'))
    assert updated['row_version'] == 2
    with owner.connect() as c:
        detail = c.execute(text('SELECT details FROM cafeteria.audit_events ORDER BY id DESC LIMIT 1')).scalar_one()
        assert detail['row_version_before'] == 1 and detail['row_version_after'] == 2
        assert detail['after']['storage_locations'] and detail['after']['name'] == 'Feines Gemüse'


@pytest.mark.parametrize('changes', [
    {'storage_location_public_ids': []}, {'storage_location_public_ids': None},
    {'unknown': 'field'}, {'prepared_recipe_revision_public_id': None},
    {'prepared_recipe_content_hash_sha256': '0' * 64},
])
def test_invalid_food_rolls_back_every_business_row(prepared, changes):
    owner, engine, ids = prepared
    before = state(owner)
    with pytest.raises(DBAPIError) as error:
        create_food(engine, ids, **changes)
    assert error.value.orig.sqlstate == 'P1901'
    assert state(owner) == before


def test_rr_preview_freeze_v2_and_stale_dependency(prepared):
    owner, engine, ids = prepared
    food = create_food(engine, ids)
    recipe = create_recipe(engine, ids, [food])
    expected = preview(engine, ids, recipe)
    assert expected['complete'] is True and expected['issues'] == []
    assert expected['snapshot']['schema_version'] == 2
    assert expected['snapshot']['foods'][0]['base_unit']['code'] == 'G'
    assert expected['snapshot']['foods'][0]['storage_locations'][0]['name'] == 'Realer Testlagerort'
    assert preview(engine, ids, recipe) == expected
    update_food(engine, ids, food, food_payload(ids, 'Anderer Name'))
    unchanged = state(owner)
    with pytest.raises(DBAPIError) as error:
        freeze(engine, ids, recipe, expected['dependency_hash_sha256'])
    assert error.value.orig.sqlstate == '55000' and state(owner) == unchanged
    current = preview(engine, ids, recipe)
    revision = freeze(engine, ids, recipe)
    assert revision_snapshot(owner, revision) == current['snapshot']
    assert revision['recipe_row_version'] == recipe['row_version'] + 1


@pytest.mark.parametrize('ingredients', [[], [None]])
def test_incomplete_heads_remain_drafts_but_cannot_freeze(prepared, ingredients):
    owner, engine, ids = prepared
    recipe = create_recipe(engine, ids, ingredients)
    expected = preview(engine, ids, recipe)
    assert expected['complete'] is False
    before = state(owner)
    with pytest.raises(DBAPIError) as error:
        freeze(engine, ids, recipe, expected['dependency_hash_sha256'])
    assert error.value.orig.sqlstate == 'P1901' and state(owner) == before


@pytest.mark.parametrize(('base', 'yield_unit', 'extra', 'allowed'), [
    ('G', 'KG', {}, True), ('L', 'ML', {}, True), ('STK', 'STK', {}, True),
    ('PORTION', 'PORTION', {}, True), ('PORTION', 'PRISE', {}, False),
    ('G', 'PORTION', {}, False), ('G', 'ML', {}, False),
    ('G', 'ML', {'density_g_per_ml': '1.05'}, True),
    ('G', 'STK', {'piece_weight_g': '10'}, False),
])
def test_prepared_yield_compatibility_without_inferred_factors(prepared, base, yield_unit, extra, allowed):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Rohzutat', yield_unit)
    recipe = create_recipe(engine, ids, [raw], unit=yield_unit)
    revision = legacy_freeze(owner, ids, recipe)
    if allowed:
        food = create_food(engine, ids, 'Zubereitet', base, revision, **extra)
        assert food['row_version'] == 1
    else:
        before = state(owner)
        with pytest.raises(DBAPIError) as error:
            create_food(engine, ids, 'Zubereitet', base, revision, **extra)
        assert error.value.orig.sqlstate == 'P1901' and state(owner) == before


def test_storage_final_state_constraints_and_old_writer_denial(prepared):
    owner, engine, ids = prepared
    food = create_food(engine, ids)
    original = state(owner)
    for sql, parameters, code in [
        ('SELECT cafeteria.create_food_v21(:actor,:authz,:location,NULL,NULL,CAST(:payload AS jsonb))',
         {**ids, 'payload': json.dumps({'name': 'Bypass', 'base_unit_code': 'G'})}, '42501'),
        ('SELECT cafeteria.freeze_recipe_revision_v22(:actor,:authz,:location,NULL,NULL,\'{}\')', ids, '42501'),
        ('UPDATE cafeteria.foods SET name=name WHERE false', {}, '42501'),
        ('SELECT cafeteria.food_save_v27(true,:actor,:authz,:location,NULL,NULL,\'{}\')', ids, '42501'),
    ]:
        with pytest.raises(DBAPIError) as error:
            execute(engine, sql, parameters)
        assert error.value.orig.sqlstate == code
    with pytest.raises(DBAPIError) as error:
        execute(engine, '''SELECT cafeteria.replace_food_storage_locations_v21(:actor,:authz,:location,
            CAST(:target AS uuid),:version,'{"storage_locations":[]}')''',
            {**ids, 'target': food['public_id'], 'version': food['row_version']})
    assert error.value.orig.sqlstate == '55000'
    with pytest.raises(DBAPIError) as error:
        with owner.begin() as c:
            c.execute(text('DELETE FROM cafeteria.food_storage_locations'))
    assert error.value.orig.sqlstate == '55000' and state(owner) == original
