"""Original identity expectations, immutable provenance and legacy writer closure."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from prepared_food_fixtures import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, create_food, update_food,
    food_payload, create_recipe, preview, freeze, execute, state,
)
from prepared_food_fixtures import prepared as prepared


@pytest.mark.parametrize(('changed', 'code'), [
    ({'actor': None}, 'P1901'), ({'actor': 99999999}, 'P1902'),
    ({'authz': 1}, 'P1903'), ({'location': None}, '22023'),
    ({'location': 99999999}, 'P1901'),
])
def test_original_actor_and_location_expectations_preserve_all_rows(prepared, changed, code):
    owner, engine, ids = prepared
    food = create_food(engine, ids)
    recipe = create_recipe(engine, ids, [food])
    dependency = preview(engine, ids, recipe)['dependency_hash_sha256']
    before = state(owner)
    for action in (lambda: create_food(engine, ids | changed, 'Keine neue Zutat'),
                   lambda: update_food(engine, ids | changed, food, food_payload(ids, 'Keine Änderung')),
                   lambda: freeze(engine, ids | changed, recipe, dependency)):
        with pytest.raises(DBAPIError) as error:
            action()
        assert error.value.orig.sqlstate == code and state(owner) == before


def test_object_cas_hash_and_provenance_rejections_are_atomic(prepared):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Roh')
    recipe = create_recipe(engine, ids, [raw])
    revision = freeze(engine, ids, recipe)
    food = create_food(engine, ids, 'Vorbereitet', pin=revision)
    before = state(owner)
    for target, payload, code in [
        (food | {'row_version': 2}, food_payload(ids), '55000'),
        (food | {'public_id': str(uuid4())}, food_payload(ids), '22023'),
        (food, food_payload(ids) | {'source_note': 'Ursprung überschreiben'}, 'P1901'),
        (food, food_payload(ids, pin=revision | {'content_hash_sha256': '0' * 64}), '55000'),
        (food, food_payload(ids, pin=revision | {'public_id': str(uuid4())}), '22023'),
    ]:
        with pytest.raises(DBAPIError) as error:
            update_food(engine, ids, target, payload)
        assert error.value.orig.sqlstate == code and state(owner) == before
    with pytest.raises(DBAPIError) as error:
        with owner.begin() as c:
            c.execute(text("UPDATE cafeteria.foods SET source_note='forged' WHERE public_id=CAST(:id AS uuid)"),
                      {'id': food['public_id']})
    assert error.value.orig.sqlstate == '55000' and state(owner) == before
    # A retained v21 core verb cannot change dimensional compatibility of the pin.
    with pytest.raises(DBAPIError) as error:
        execute(engine, '''SELECT cafeteria.update_food_v21(:actor,:authz,:location,CAST(:target AS uuid),
            :version,CAST(:payload AS jsonb))''', ids | {'target': food['public_id'], 'version': food['row_version']},
            {'name': 'Falsche Basiseinheit', 'base_unit_code': 'ML'})
    assert error.value.orig.sqlstate == 'P1901' and state(owner) == before


def test_archived_preparation_preserves_existing_pin_and_explicit_removal(prepared):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Roh')
    recipe = create_recipe(engine, ids, [raw])
    revision = freeze(engine, ids, recipe)
    food = create_food(engine, ids, 'Vorbereitet', pin=revision)
    execute(engine, '''SELECT cafeteria.set_recipe_active_v22(:actor,:authz,:location,CAST(:target AS uuid),
        :version,CAST(:payload AS jsonb))''', ids | {'target': recipe['public_id'],
        'version': revision['recipe_row_version']}, {'active': False})
    before = state(owner)
    with pytest.raises(DBAPIError) as error:
        create_food(engine, ids, 'Neue archivierte Auswahl', pin=revision)
    assert error.value.orig.sqlstate == '55000' and state(owner) == before
    assert update_food(engine, ids, food, food_payload(ids, 'Vorbereitet', pin=revision)) == food
    updated = update_food(engine, ids, food, food_payload(ids, 'Historische Bindung behalten'))
    current = execute(owner, '''SELECT r.public_id::text FROM cafeteria.foods f
        JOIN cafeteria.recipe_revisions r ON r.id=f.prepared_recipe_revision_id WHERE f.public_id=CAST(:id AS uuid)''',
        {'id': food['public_id']})
    assert current == revision['public_id']
    parent = create_recipe(engine, ids, [updated], name='Mit historischer Zubereitung')
    assert freeze(engine, ids, parent)['revision_number'] == 1
    detached = update_food(engine, ids, updated, food_payload(ids, 'Jetzt roh') |
        {'prepared_recipe_revision_public_id': None, 'prepared_recipe_content_hash_sha256': None})
    assert detached['row_version'] == 3
    assert execute(owner, 'SELECT prepared_recipe_revision_id FROM cafeteria.foods WHERE public_id=CAST(:id AS uuid)',
                   {'id': food['public_id']}) is None


def test_foreign_revision_and_storage_are_rejected_by_verb_and_fk(prepared):
    owner, engine, ids = prepared
    local = create_food(engine, ids)
    with owner.begin() as c:
        c.execute(text('UPDATE cafeteria.locations SET active=false WHERE id=:location'), ids)
        other = c.execute(text("INSERT INTO cafeteria.locations(code,name) VALUES('OTHER','Anderer Standort') RETURNING id")).scalar_one()
    other_ids = ids | {'location': other}
    storage = execute(engine, "SELECT cafeteria.create_storage_location_v21(:actor,:authz,:location,NULL,NULL,'{\"code\":\"STORE\",\"name\":\"Anderes Lager\"}')", other_ids)
    other_ids['storage'] = storage['public_id']
    raw = create_food(engine, other_ids, 'Fremde Zutat')
    revision = freeze(engine, other_ids, create_recipe(engine, other_ids, [raw]))
    with owner.begin() as c:
        c.execute(text('UPDATE cafeteria.locations SET active=false WHERE id=:location'), other_ids)
        c.execute(text('UPDATE cafeteria.locations SET active=true WHERE id=:location'), ids)
    before = state(owner)
    for payload in (food_payload(ids, pin=revision), food_payload(ids | {'storage': storage['public_id']})):
        with pytest.raises(DBAPIError) as error:
            update_food(engine, ids, local, payload)
        assert error.value.orig.sqlstate in ('22023', 'P1901') and state(owner) == before
    with pytest.raises(DBAPIError) as error:
        with owner.begin() as c:
            c.execute(text('''UPDATE cafeteria.foods SET prepared_recipe_revision_id=(
                SELECT id FROM cafeteria.recipe_revisions WHERE public_id=CAST(:revision AS uuid))
                WHERE public_id=CAST(:food AS uuid)'''),
                {'revision': revision['public_id'], 'food': local['public_id']})
    assert error.value.orig.sqlstate == '23503' and state(owner) == before


def test_repeatable_read_preview_has_no_sequence_audit_or_business_writes(prepared):
    owner, engine, ids = prepared
    food = create_food(engine, ids)
    recipe = create_recipe(engine, ids, [food])
    before = state(owner)
    with owner.connect() as c:
        sequences = c.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='cafeteria' ORDER BY sequencename")).all()
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        with c.begin():
            c.execute(text('SET TRANSACTION READ ONLY'))
            first = c.execute(text('SELECT cafeteria.recipe_dependency_preview_v27(:location,CAST(:target AS uuid),:version)'),
                              ids | {'target': recipe['public_id'], 'version': recipe['row_version']}).scalar_one()
            assert json.dumps(first, sort_keys=True) == json.dumps(preview(engine, ids, recipe), sort_keys=True)
    assert state(owner) == before
    with owner.connect() as c:
        assert c.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='cafeteria' ORDER BY sequencename")).all() == sequences
