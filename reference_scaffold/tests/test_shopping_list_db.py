"""SDD 8.4 acceptance + store contract for MP-REC-SHOPPING-PERSIST (real PostgreSQL, app role).

Recipes/foods are built through the real ``create_food_v27``/``create_recipe_v22``/
``freeze_recipe_v27`` flow (``prepared_food_fixtures``), never hand-crafted snapshot JSON, so
every ``recipe_revisions`` row here is byte-for-byte what production would freeze -- including
its canonical-hash/closure verification chain that ``shopping_list_store`` reads through.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

from cafeteria.shopping_list_store import (
    ShoppingListConflictError, ShoppingListNotFoundError, ShoppingListValidationError, ShoppingScope,
    add_manual_item, archive_shopping_list, candidate_components, compute_revision, create_shopping_list,
    get_shopping_list, list_shopping_lists, set_line_checked,
)
from prepared_food_fixtures import (  # noqa: F401
    app_engine, create_food, execute, freeze, installed_pg16, pg16, preview, seeded_pg16,
)
from test_component_scope_invariants_db import _seed_scope_probe
from test_master_data_db import make_actor


@pytest.fixture
def store(seeded_pg16, app_engine):  # noqa: F811
    ids = _seed_scope_probe(seeded_pg16)
    actor = make_actor(seeded_pg16)
    ids.update(actor=actor.user_id, authz=actor.authz_version)
    with seeded_pg16.begin() as c:
        c.execute(text('UPDATE cafeteria.locations SET active=false WHERE id=:other_location'), ids)
        ids['storage'] = str(c.execute(
            text("INSERT INTO cafeteria.storage_locations(location_id, code, name) "
                 "VALUES (:location, 'SP_STORE', 'Testlager') RETURNING public_id"),
            ids,
        ).scalar_one())
    return seeded_pg16, app_engine, ids


def _scope(ids):
    return ShoppingScope(ids['actor'], ids['location'])


def _item_public(owner, item_id):
    with owner.connect() as c:
        return str(c.execute(text('SELECT public_id FROM cafeteria.menu_items WHERE id=:id'), {'id': item_id}).scalar_one())


def _revision_id(owner, public_id):
    with owner.connect() as c:
        return c.execute(
            text('SELECT id FROM cafeteria.recipe_revisions WHERE public_id=CAST(:id AS uuid)'), {'id': public_id},
        ).scalar_one()


def _unit_id(owner, code):
    with owner.connect() as c:
        return c.execute(text('SELECT id FROM cafeteria.measurement_units WHERE code=:code'), {'code': code}).scalar_one()


def _bind(owner, item_id, sort_order, label, revision_id, target_quantity=None, target_unit_code=None):
    unit_id = _unit_id(owner, target_unit_code) if target_unit_code else None
    with owner.begin() as c:
        c.execute(
            text('''INSERT INTO cafeteria.menu_item_components(
                        menu_item_id, sort_order, component_text, recipe_revision_id, target_quantity, target_quantity_unit_id)
                    VALUES (:item, :sort, :label, :revision, :qty, :unit)'''),
            {'item': item_id, 'sort': sort_order, 'label': label, 'revision': revision_id, 'qty': target_quantity, 'unit': unit_id},
        )


def _ingredient(food, quantity, unit, text_value='Zutat'):
    return {'line_public_id': None, 'ingredient_text': text_value, 'group_label': None,
            'food_public_id': food['public_id'], 'quantity': quantity, 'unit_code': unit, 'note': None,
            'source_kind': 'manual', 'source_reference': None, 'fetched_at': None}


def _recipe(engine, ids, ingredients, *, servings='1', unit='PORTION'):
    payload = {'title': 'Testrezept', 'description': None, 'servings': servings, 'servings_unit_code': unit,
               'prep_minutes': None, 'cook_minutes': None,
               'source': {'kind': 'manual', 'reference': None, 'url': None, 'note': None, 'fetched_at': None},
               'ingredients': ingredients, 'steps': [], 'tag_public_ids': [], 'images': []}
    return execute(engine, 'SELECT cafeteria.create_recipe_v22(:actor,:authz,:location,NULL,NULL,CAST(:payload AS jsonb))', ids, payload)


def _bound_component(owner, engine, ids, ingredients, *, servings='1', unit='PORTION', sort_order=1,
                     target_quantity=None, target_unit_code=None, label='Baustein'):
    recipe = _recipe(engine, ids, ingredients, servings=servings, unit=unit)
    revision = freeze(engine, ids, recipe)
    _bind(owner, ids['item'], sort_order, label, _revision_id(owner, revision['public_id']),
         target_quantity, target_unit_code)
    return revision


def _compute(engine, ids, list_id, *, item_public=None, sort_order=1, policy='leaf', expected_row_version=1):
    item_public = item_public or _item_public(ids['owner'], ids['item'])
    return compute_revision(
        engine, _scope(ids), list_id, component_ids=[f'{item_public}:{sort_order}'], policy=policy,
        expected_row_version=expected_row_version,
    )


def test_mass_units_of_same_food_sum_via_real_bound_revision(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    flour = create_food(engine, ids, 'Mehl')
    _bound_component(owner, engine, ids, [_ingredient(flour, '500', 'G'), _ingredient(flour, '1', 'KG')])
    list_id = create_shopping_list(engine, _scope(ids), title='Testliste')
    _compute(engine, ids, list_id)
    lines = get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines']
    assert len(lines) == 1
    assert lines[0]['food_public_id'] == flour['public_id']
    assert Decimal(lines[0]['quantity']) == Decimal('1500') and lines[0]['unit_code'] == 'G'


def test_volume_with_captured_density_joins_mass(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    milk = create_food(engine, ids, 'Milch', density_g_per_ml='1.2')
    _bound_component(owner, engine, ids, [_ingredient(milk, '500', 'ML'), _ingredient(milk, '400', 'G')])
    list_id = create_shopping_list(engine, _scope(ids), title='Testliste')
    _compute(engine, ids, list_id)
    lines = get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines']
    assert len(lines) == 1 and Decimal(lines[0]['quantity']) == Decimal('1000')


def test_volume_without_density_stays_separate(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    water = create_food(engine, ids, 'Wasser')
    _bound_component(owner, engine, ids, [_ingredient(water, '500', 'ML'), _ingredient(water, '400', 'G')])
    list_id = create_shopping_list(engine, _scope(ids), title='Testliste')
    _compute(engine, ids, list_id)
    lines = get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines']
    assert {line['unit_code'] for line in lines} == {'ML', 'G'}


def test_prepared_branch_is_either_intermediate_or_leaves_never_both(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    raw = create_food(engine, ids, 'Rohzutat')
    fond_recipe = _recipe(engine, ids, [_ingredient(raw, '100', 'G')], servings='100', unit='G')
    fond_revision = freeze(engine, ids, fond_recipe)
    fond = create_food(engine, ids, 'Fond', pin=fond_revision)
    _bound_component(owner, engine, ids, [_ingredient(fond, '200', 'G')], servings='1', unit='PORTION')
    item_public = _item_public(owner, ids['item'])
    leaf_list = create_shopping_list(engine, _scope(ids), title='Blattbedarf')
    _compute(engine, ids, leaf_list, item_public=item_public, policy='leaf')
    leaf_lines = get_shopping_list(engine, _scope(ids), leaf_list)['selected_revision']['lines']
    assert [line['food_public_id'] for line in leaf_lines] == [raw['public_id']]
    assert Decimal(leaf_lines[0]['quantity']) == Decimal('200')
    prepared_list = create_shopping_list(engine, _scope(ids), title='Vorbereitet')
    _compute(engine, ids, prepared_list, item_public=item_public, policy='prepared')
    prepared_lines = get_shopping_list(engine, _scope(ids), prepared_list)['selected_revision']['lines']
    assert [line['food_public_id'] for line in prepared_lines] == [fond['public_id']]
    assert Decimal(prepared_lines[0]['quantity']) == Decimal('200') and prepared_lines[0]['unit_code'] == 'G'


def test_target_quantity_scales_and_later_binding_change_never_alters_old_revision(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    butter = create_food(engine, ids, 'Butter')
    _bound_component(
        owner, engine, ids, [_ingredient(butter, '400', 'G')], servings='4', unit='PORTION',
        target_quantity='8', target_unit_code='PORTION',
    )
    item_public = _item_public(owner, ids['item'])
    list_id = create_shopping_list(engine, _scope(ids), title='Skaliert')
    revision_1 = _compute(engine, ids, list_id, item_public=item_public)
    with owner.connect() as c:
        before = c.execute(
            text('SELECT snapshot_json::text AS text, content_hash_sha256 FROM cafeteria.shopping_list_revisions WHERE public_id=CAST(:id AS uuid)'),
            {'id': revision_1},
        ).mappings().one()
    first_lines = get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines']
    assert Decimal(first_lines[0]['quantity']) == Decimal('800')
    with owner.begin() as c:
        c.execute(
            text("UPDATE cafeteria.menu_item_components SET target_quantity='16' WHERE menu_item_id=:item"),
            {'item': ids['item']},
        )
    _compute(engine, ids, list_id, item_public=item_public, expected_row_version=2)
    second_lines = get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines']
    assert Decimal(second_lines[0]['quantity']) == Decimal('1600')
    with owner.connect() as c:
        after = c.execute(
            text('SELECT snapshot_json::text AS text, content_hash_sha256 FROM cafeteria.shopping_list_revisions WHERE public_id=CAST(:id AS uuid)'),
            {'id': revision_1},
        ).mappings().one()
    assert after['text'] == before['text'] and after['content_hash_sha256'] == before['content_hash_sha256']


def test_original_cas_conflict_on_compute_revision(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, _scope(ids), title='CAS')
    with owner.connect() as c:
        before = c.execute(text('SELECT count(*) FROM cafeteria.shopping_list_revisions')).scalar_one()
    with pytest.raises(ShoppingListConflictError):
        _compute(engine, ids, list_id, expected_row_version=999)
    with owner.connect() as c:
        after = c.execute(text('SELECT count(*) FROM cafeteria.shopping_list_revisions')).scalar_one()
    assert before == after


def test_empty_or_foreign_component_selection_is_a_validation_error(store):  # noqa: F811
    owner, engine, ids = store
    list_id = create_shopping_list(engine, _scope(ids), title='Auswahl')
    with pytest.raises(ShoppingListValidationError):
        compute_revision(engine, _scope(ids), list_id, component_ids=[], policy='leaf', expected_row_version=1)
    with pytest.raises(ShoppingListValidationError):
        compute_revision(
            engine, _scope(ids), list_id, component_ids=['11111111-1111-4111-8111-111111111111:1'],
            policy='leaf', expected_row_version=1,
        )


def test_checked_status_persists_when_unchanged_and_becomes_changed_open_when_quantity_changes(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    stable = create_food(engine, ids, 'Reis')
    changing = create_food(engine, ids, 'Zucker')
    _bound_component(owner, engine, ids, [_ingredient(stable, '100', 'G')], sort_order=1, label='Beilage')
    _bound_component(
        owner, engine, ids, [_ingredient(changing, '50', 'G')], servings='4', unit='PORTION', sort_order=2,
        target_quantity='4', target_unit_code='PORTION', label='Dessert',
    )
    item_public = _item_public(owner, ids['item'])
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Abhaken')
    revision_1 = compute_revision(
        engine, scope, list_id, component_ids=[f'{item_public}:1', f'{item_public}:2'], policy='leaf', expected_row_version=1,
    )
    lines = get_shopping_list(engine, scope, list_id)['selected_revision']['lines']
    by_food = {line['food_public_id']: line for line in lines}
    for line in lines:
        set_line_checked(engine, scope, list_id, revision_public_id=revision_1, line_key=line['line_key'], checked=True)
    with owner.begin() as c:
        c.execute(text("UPDATE cafeteria.menu_item_components SET target_quantity='8' WHERE menu_item_id=:item AND sort_order=2"), {'item': ids['item']})
    compute_revision(
        engine, scope, list_id, component_ids=[f'{item_public}:1', f'{item_public}:2'], policy='leaf', expected_row_version=2,
    )
    after = get_shopping_list(engine, scope, list_id)['selected_revision']['lines']
    status_by_food = {line['food_public_id']: line['checked_status'] for line in after}
    assert status_by_food[stable['public_id']] == 'checked'
    assert status_by_food[changing['public_id']] == 'changed_open'
    assert Decimal(by_food[changing['public_id']]['quantity']) == Decimal('50')


def test_manual_items_survive_recompute(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Manuell')
    manual_id = add_manual_item(engine, scope, list_id, item_text='Servietten', quantity='2', unit_code='STK')
    _compute(engine, ids, list_id)
    manual_items = get_shopping_list(engine, scope, list_id)['manual_items']
    assert len(manual_items) == 1 and manual_items[0]['public_id'] == manual_id
    assert manual_items[0]['quantity'] == '2.000000' and manual_items[0]['item_text'] == 'Servietten'


def test_location_isolation_foreign_scope_cannot_read_or_write(store):  # noqa: F811
    owner, engine, ids = store
    list_id = create_shopping_list(engine, _scope(ids), title='Standortliste')
    foreign_scope = ShoppingScope(ids['actor'], ids['other_location'])
    with pytest.raises(ShoppingListNotFoundError):
        get_shopping_list(engine, foreign_scope, list_id)
    with pytest.raises(ShoppingListNotFoundError):
        archive_shopping_list(engine, foreign_scope, list_id, expected_row_version=1)
    with owner.connect() as c:
        assert c.execute(text('SELECT archived_at FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid)'),
                         {'id': list_id}).scalar_one() is None


def test_read_functions_write_nothing(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Lesetest')
    _compute(engine, ids, list_id)
    week_public = None
    with owner.connect() as c:
        week_public = str(c.execute(text('SELECT public_id FROM cafeteria.menu_weeks WHERE id=:id'), {'id': ids['week']}).scalar_one())

    def _fingerprint():
        with owner.connect() as c:
            return tuple(
                c.execute(text(f'SELECT count(*) FROM cafeteria.{table}')).scalar_one()
                for table in ('shopping_lists', 'shopping_list_revisions', 'shopping_list_manual_items',
                             'shopping_list_line_status', 'menu_item_components', 'foods', 'recipe_revisions')
            )

    before = _fingerprint()
    list_shopping_lists(engine, scope)
    get_shopping_list(engine, scope, list_id)
    candidate_components(engine, scope, menu_week_public_id=week_public)
    assert _fingerprint() == before


def test_app_role_engine_suffices_for_every_store_call(store):  # noqa: F811
    """Every call above already runs on ``app_engine`` (cafeteria_app); this asserts it directly."""
    owner, engine, ids = store
    ids['owner'] = owner
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Rollentest')
    with engine.connect() as c:
        assert c.execute(text('SELECT current_user')).scalar_one() == 'cafeteria_app'
    _compute(engine, ids, list_id)
    assert get_shopping_list(engine, scope, list_id)['selected_revision'] is not None
