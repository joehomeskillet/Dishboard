"""Real app-role SQL boundaries; no R5b writer/HTTP acceptance is claimed here."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from test_component_metadata_master_lock_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine,
)
from test_component_scope_invariants_db import _seed_scope_probe
from test_master_data_db import make_actor


@pytest.fixture
def binding(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as c:
        c.execute(text('UPDATE cafeteria.locations SET active=false WHERE id=:other_location'), ids)
        for key in ('location', 'other_location'):
            params = {'loc': ids[key], 'actor': actor.user_id}
            ids[key + '_recipe'] = c.execute(text("""INSERT INTO cafeteria.recipes(
                location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
                VALUES(:loc,:actor,:actor,'Suppe',4,(SELECT id FROM cafeteria.measurement_units
                WHERE code='PORTION'),'manual') RETURNING id"""), params).scalar_one()
            params['recipe'] = ids[key + '_recipe']
            ids[key + '_revision'] = c.execute(text("""INSERT INTO cafeteria.recipe_revisions(
                location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
                VALUES(:loc,:recipe,1,'{}',encode(pg_catalog.sha256(convert_to('{}','UTF8')),'hex'),:actor)
                RETURNING id"""), params).scalar_one()
            ids[key + '_food'] = c.execute(text("""INSERT INTO cafeteria.foods(
                location_id,created_by,updated_by,name,base_unit_id) VALUES(:loc,:actor,:actor,'Karotte',
                (SELECT id FROM cafeteria.measurement_units WHERE code='G')) RETURNING id"""), params).scalar_one()
            code = 'LAGER_LOC' if key == 'location' else 'LAGER_OTHER'
            ids[key + '_storage'] = c.execute(text("""INSERT INTO cafeteria.storage_locations(
                location_id,code,name) VALUES(:loc,:code,'Testlager') RETURNING id"""),
                {'loc': ids[key], 'code': code}).scalar_one()
            c.execute(text("""INSERT INTO cafeteria.food_storage_locations(
                location_id,food_id,storage_location_id) VALUES(:loc,:food,:storage)"""),
                {'loc': ids[key], 'food': ids[key + '_food'], 'storage': ids[key + '_storage']})
    return seeded_pg16, app_engine, ids


def begin(c, ids):
    c.execute(text('SELECT cafeteria.begin_menu_binding_write_v26(:actor,:authz,:location)'), ids)


def assert_rejected(engine, query, ids, state):
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as c:
            c.execute(text(query), ids)
    assert error.value.orig.sqlstate == state


def test_independent_nullable_references_and_revision_only_update(binding):
    _, engine, ids = binding
    with engine.begin() as c:
        c.execute(text("""INSERT INTO cafeteria.menu_item_components(menu_item_id,sort_order,component_text,
            component_id,component_row_version,recipe_revision_id) VALUES
            (:item,1,'Dual',:exact,1,:location_revision),(:item,2,'Recipe only',NULL,NULL,:location_revision),
            (:item,3,'Legacy',NULL,NULL,NULL)"""), ids)
        c.execute(text('UPDATE cafeteria.menu_components SET food_id=:location_food WHERE id=:exact'), ids)
    assert_rejected(engine, 'UPDATE cafeteria.menu_item_components SET recipe_revision_id=:other_location_revision '
                    'WHERE menu_item_id=:item AND sort_order=2', ids, '23514')
    assert_rejected(engine, 'UPDATE cafeteria.menu_components SET food_id=:other_location_food WHERE id=:exact', ids, '23503')
    with engine.connect() as c:
        assert c.execute(text('SELECT recipe_revision_id FROM cafeteria.menu_item_components '
                              'WHERE menu_item_id=:item ORDER BY sort_order'), ids).scalars().all() == [ids['location_revision']] * 2 + [None]


def test_both_global_template_scope_surfaces_and_parent_identity(binding):
    _, engine, ids = binding
    with engine.begin() as c:
        ids['template'] = c.execute(text("INSERT INTO cafeteria.dish_templates(title) VALUES('Vorlage') RETURNING id")).scalar_one()
        c.execute(text('UPDATE cafeteria.menu_items SET dish_template_id=:template WHERE id=:item'), ids)
    assert_rejected(engine, 'UPDATE cafeteria.dish_templates SET recipe_id=:other_location_recipe WHERE id=:template', ids, '23514')
    with engine.begin() as c:
        c.execute(text('UPDATE cafeteria.menu_items SET dish_template_id=NULL WHERE id=:item'), ids)
        c.execute(text('UPDATE cafeteria.dish_templates SET recipe_id=:other_location_recipe WHERE id=:template'), ids)
    assert_rejected(engine, 'UPDATE cafeteria.menu_items SET dish_template_id=:template WHERE id=:item', ids, '23514')
    assert_rejected(engine, 'UPDATE cafeteria.menu_items SET service_id=service_id+1000 WHERE id=:item', ids, '23514')
    assert_rejected(engine, 'UPDATE cafeteria.menu_services SET menu_week_id=menu_week_id+1000 WHERE menu_week_id=:week', ids, '23514')
    assert_rejected(engine, 'UPDATE cafeteria.menu_weeks SET location_id=:other_location WHERE id=:week', ids, '23514')


@pytest.mark.parametrize('change,state', [('stale','P1903'), ('disabled','P1902'), ('role','P1902'), ('definition','P1902')])
def test_original_actor_expectation_is_required(binding, change, state):
    owner, engine, ids = binding
    with owner.begin() as c:
        if change == 'stale':
            ids['authz'] -= 1
        elif change == 'disabled':
            c.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor'), ids)
        elif change == 'role':
            c.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor'), ids)
            ids['authz'] = c.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:actor'), ids).scalar_one()
        else:
            c.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Publisher'"))
    assert_rejected(engine, 'SELECT cafeteria.begin_menu_binding_write_v26(:actor,:authz,:location)', ids, state)


@pytest.mark.parametrize('kind', ['recipe', 'food'])
def test_head_helpers_return_archived_references_and_hold_real_share_locks(binding, kind):
    owner, engine, ids = binding
    table = 'recipes' if kind == 'recipe' else 'foods'
    with owner.begin() as c:
        c.execute(text(f'UPDATE cafeteria.{table} SET active=false WHERE id=:id'), {'id': ids['location_' + kind]})
    helper = 'lock_menu_recipe_revisions_v26' if kind == 'recipe' else 'lock_component_foods_v26'
    target = ids['location_revision' if kind == 'recipe' else 'location_food']
    def change_head():
        with pytest.raises(DBAPIError) as error:
            with owner.begin() as c:
                c.execute(text("SET LOCAL lock_timeout='300ms'"))
                c.execute(text(f'UPDATE cafeteria.{table} SET active=true WHERE id=:id'), {'id': ids['location_' + kind]})
        return error.value.orig.sqlstate
    with engine.begin() as c:
        begin(c, ids)  # Before heads and any aggregate lock.
        rows = c.execute(text(f'SELECT * FROM cafeteria.{helper}(:actor,:authz,:location,ARRAY[:target]::bigint[])'),
                         {**ids, 'target': target}).mappings().all()
        assert len(rows) == 1 and rows[0]['active'] is False
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(change_head).result(timeout=5) == '55P03'
    assert_rejected(engine, f'SELECT * FROM cafeteria.{helper}(:actor,:authz,:location,ARRAY[NULL]::bigint[])', ids, 'P1901')


@pytest.mark.parametrize('target', ['users', 'application_roles'])
def test_guard_holds_actor_and_role_definition_locks(binding, target):
    owner, engine, ids = binding
    def change_authorization():
        with pytest.raises(DBAPIError) as error:
            with owner.begin() as c:
                c.execute(text("SET LOCAL lock_timeout='300ms'"))
                c.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor' if target == 'users'
                               else "UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Publisher'"), ids)
        return error.value.orig.sqlstate
    with engine.begin() as c:
        begin(c, ids)
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(change_authorization).result(timeout=5) == '55P03'


def test_receipt_is_fixed_derived_exactly_once_and_rolls_back_writer_on_failure(binding):
    owner, engine, ids = binding
    with engine.begin() as c:
        begin(c, ids)
        c.execute(text('SELECT * FROM cafeteria.lock_menu_recipe_revisions_v26(:actor,:authz,:location,ARRAY[:location_revision]::bigint[])'), ids)
        c.execute(text('SELECT id FROM cafeteria.menu_weeks WHERE id=:week FOR UPDATE'), ids)
        c.execute(text('SELECT id FROM cafeteria.menu_services WHERE menu_week_id=:week FOR UPDATE'), ids)
        c.execute(text('SELECT id FROM cafeteria.menu_items WHERE id=:item FOR UPDATE'), ids)
        c.execute(text("INSERT INTO cafeteria.menu_item_components(menu_item_id,sort_order,component_text,recipe_revision_id) "
                       "VALUES(:item,1,'Gebunden',:location_revision)"), ids)
        version = c.execute(text("UPDATE cafeteria.menu_items SET title='Geändert' WHERE id=:item RETURNING row_version"), ids).scalar_one()
        assert version == 2
        event = c.execute(text('SELECT cafeteria.record_menu_binding_write_v26(:actor,:authz,:location,:item,1,2)'), ids).scalar_one()
    with owner.connect() as c:
        details = c.execute(text('SELECT details FROM cafeteria.audit_events WHERE public_id=:event'), {'event': event}).scalar_one()
        assert details['row_version_before'] == 1 and details['row_version_after'] == 2
        assert len(details['recipe_revisions']) == 1 and len(details['recipe_revisions'][0]['content_hash_sha256']) == 64
    assert_rejected(engine, 'SELECT cafeteria.record_menu_binding_write_v26(:actor,:authz,:location,:item,1,2)', ids, '55000')
    with pytest.raises(DBAPIError):
        with engine.begin() as c:
            begin(c, ids)
            c.execute(text("UPDATE cafeteria.menu_items SET title='Rollback' WHERE id=:item"), ids)
            c.execute(text('SELECT cafeteria.record_menu_binding_write_v26(:actor,:authz,:location,:item,1,3)'), ids)
    with engine.connect() as c:
        assert c.execute(text('SELECT title,row_version FROM cafeteria.menu_items WHERE id=:item'), ids).one() == ('Geändert', 2)


def dish_payload(**changes):
    return {'menu_type_code': 'MENU_1', 'profile_scope': 'common', 'title': 'Vorlage',
            'description': None, 'recipe_public_id': None, **changes}


def dish_call(engine, ids, verb, payload, previous=None):
    with engine.begin() as c:
        return c.execute(text(f'SELECT cafeteria.{verb}_dish_template_v26(:actor,:authz,:location,:target,:expected,CAST(:payload AS jsonb))'),
            {**ids, 'target': previous['public_id'] if previous else None,
             'expected': previous['updated_at'] if previous else None, 'payload': json.dumps(payload)}).scalar_one()


def test_template_crud_original_timestamp_noop_archive_and_scoped_recipe(binding):
    owner, engine, ids = binding
    with owner.connect() as c:
        recipe = str(c.execute(text('SELECT public_id FROM cafeteria.recipes WHERE id=:location_recipe'), ids).scalar_one())
    row = dish_call(engine, ids, 'create', dish_payload(recipe_public_id=recipe))
    assert dish_call(engine, ids, 'update', dish_payload(recipe_public_id=recipe), row) == row
    with owner.begin() as c:
        c.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:location_recipe'), ids)
    changed = dish_call(engine, ids, 'update', dish_payload(title='Neu', recipe_public_id=recipe), row)
    with pytest.raises(DBAPIError):
        dish_call(engine, ids, 'update', dish_payload(), row)
    with engine.begin() as c:
        archived = c.execute(text('SELECT cafeteria.set_dish_template_active_v26(:actor,:authz,:location,:target,:expected,CAST(:payload AS jsonb))'),
            {**ids, 'target': changed['public_id'], 'expected': changed['updated_at'], 'payload': '{"active":false}'}).scalar_one()
    assert archived['active'] is False
    with pytest.raises(DBAPIError):
        dish_call(engine, ids, 'create', dish_payload(recipe_public_id=recipe))
    for payload in (dish_payload(extra='x'), dish_payload(title=True), dish_payload(recipe_public_id=True)):
        with pytest.raises(DBAPIError):
            dish_call(engine, ids, 'create', payload)
