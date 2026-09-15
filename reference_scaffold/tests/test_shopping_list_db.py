"""SDD 8.4 acceptance + store contract for MP-REC-SHOPPING-PERSIST (real PostgreSQL, app role).

Recipes/foods are built through the real ``create_food_v27``/``create_recipe_v22``/
``freeze_recipe_v27`` flow (``prepared_food_fixtures``), never hand-crafted snapshot JSON, so
every ``recipe_revisions`` row here is byte-for-byte what production would freeze -- including
its canonical-hash/closure verification chain that ``shopping_list_store`` reads through.
Concurrency tests hold a real lock on a second owner connection and wait on ``pg_locks`` until
the store call is blocked, so every conflict below is a genuine PostgreSQL outcome.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import text

from cafeteria.shopping_list_store import (
    ShoppingListActorDeniedError, ShoppingListConflictError, ShoppingListNotFoundError, ShoppingListRetryError,
    ShoppingListStaleActorError, ShoppingListUnavailableError, ShoppingListValidationError, ShoppingScope,
    add_manual_item, archive_shopping_list, candidate_components, compute_revision, create_shopping_list,
    delete_manual_item, get_shopping_list, list_shopping_lists, set_line_checked, set_manual_item_checked,
    update_manual_item,
)
from prepared_food_fixtures import (  # noqa: F401
    app_engine, create_food, execute, food_payload, freeze, installed_pg16, pg16, preview, seeded_pg16, update_food,
)
from test_component_scope_invariants_db import _seed_scope_probe
from test_master_data_db import make_actor

SHOPPING_TABLES = ('shopping_lists', 'shopping_list_revisions', 'shopping_list_manual_items', 'shopping_list_line_status')


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
    return ShoppingScope(ids['actor'], ids['location'], ids['authz'])


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


def _computed_list(store, title='Nebenlaeufig'):
    """List with one computed revision (row_version 2) holding exactly one line."""
    owner, engine, ids = store
    ids['owner'] = owner
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, _scope(ids), title=title)
    revision_1 = _compute(engine, ids, list_id)
    line = get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines'][0]
    return list_id, revision_1, line


def _shopping_state(owner):
    with owner.connect() as c:
        return {table: c.execute(text(f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY 1')).scalars().all()
                for table in SHOPPING_TABLES}


def _count(owner, table):
    with owner.connect() as c:
        return c.execute(text(f'SELECT count(*) FROM cafeteria.{table}')).scalar_one()


def _wait_for_blocked(owner, count):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        with owner.connect() as c:
            blocked = c.execute(text('''SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid
                                        WHERE NOT l.granted AND a.datname=current_database()''')).scalar_one()
        if blocked >= count:
            return
        time.sleep(0.02)
    raise AssertionError(f'expected {count} blocked lock requests, saw {blocked}')


def _status_revision(owner, list_id):
    with owner.connect() as c:
        return c.execute(text('''SELECT r.public_id::text FROM cafeteria.shopping_list_line_status s
                                 JOIN cafeteria.shopping_list_revisions r ON r.id=s.revision_id
                                 JOIN cafeteria.shopping_lists l ON l.id=s.shopping_list_id
                                 WHERE l.public_id=CAST(:id AS uuid)'''), {'id': list_id}).scalars().all()


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


def test_older_revision_reads_its_own_snapshot_with_names_captured_at_compute(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    food = create_food(engine, ids, 'Alter Name')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Beleg')
    revision_1 = _compute(engine, ids, list_id)
    key = get_shopping_list(engine, scope, list_id)['selected_revision']['lines'][0]['line_key']
    set_line_checked(engine, scope, list_id, revision_public_id=revision_1, line_key=key, checked=True)
    update_food(engine, ids, food, food_payload(ids, 'Neuer Name'))
    revision_2 = _compute(engine, ids, list_id, expected_row_version=2)
    old = get_shopping_list(engine, scope, list_id, revision_public_id=revision_1)['selected_revision']
    latest = get_shopping_list(engine, scope, list_id)['selected_revision']
    assert (old['public_id'], old['is_latest'], latest['public_id'], latest['is_latest']) == (revision_1, False, revision_2, True)
    view = [(line['food_name'], Decimal(line['quantity']), line['unit_code'], line['unit_name'], line['checked_status'])
            for line in (old['lines'][0], latest['lines'][0])]
    assert view == [('Alter Name', Decimal('100'), 'G', 'Gramm', 'not_current'), ('Neuer Name', Decimal('100'), 'G', 'Gramm', 'checked')]
    with pytest.raises(ShoppingListNotFoundError):
        get_shopping_list(engine, scope, list_id, revision_public_id='11111111-1111-4111-8111-111111111111')


def test_manual_item_check_and_delete_require_the_current_row_version(store):  # noqa: F811
    owner, engine, ids = store
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Positionen')
    item = add_manual_item(engine, scope, list_id, item_text='Becher')
    assert update_manual_item(engine, scope, list_id, item, expected_row_version=1, item_text='Tassen') == 2
    before = _shopping_state(owner)
    for call in (lambda: set_manual_item_checked(engine, scope, list_id, item, expected_row_version=1, checked=True),
                 lambda: delete_manual_item(engine, scope, list_id, item, expected_row_version=1)):
        with pytest.raises(ShoppingListConflictError):
            call()
    assert _shopping_state(owner) == before
    assert set_manual_item_checked(engine, scope, list_id, item, expected_row_version=2, checked=True) == 3
    delete_manual_item(engine, scope, list_id, item, expected_row_version=3)
    assert get_shopping_list(engine, scope, list_id)['manual_items'] == ()


def test_validation_errors_name_the_offending_field_and_write_nothing(store):  # noqa: F811
    owner, engine, ids = store
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Felder')
    before = _shopping_state(owner)
    foreign = '11111111-1111-4111-8111-111111111111'
    cases = (
        ('title', lambda: create_shopping_list(engine, scope, title='  ')),
        ('note', lambda: create_shopping_list(engine, scope, title='Neu', note='x' * 2001)),
        ('menu_week_public_id', lambda: create_shopping_list(engine, scope, title='Neu', menu_week_public_id=foreign)),
        ('item_text', lambda: add_manual_item(engine, scope, list_id, item_text='')),
        ('quantity', lambda: add_manual_item(engine, scope, list_id, item_text='Becher', quantity='viele', unit_code='STK')),
        ('quantity', lambda: add_manual_item(engine, scope, list_id, item_text='Becher', unit_code='STK')),
        ('unit_code', lambda: add_manual_item(engine, scope, list_id, item_text='Becher', quantity='2')),
        ('unit_code', lambda: add_manual_item(engine, scope, list_id, item_text='Becher', quantity='2', unit_code='NIX')),
        ('component_ids', lambda: compute_revision(engine, scope, list_id, component_ids=[], policy='leaf', expected_row_version=1)),
        ('component_ids', lambda: compute_revision(engine, scope, list_id, component_ids=[f'{foreign}:1'], policy='leaf',
                                                   expected_row_version=1)),
        ('policy', lambda: compute_revision(engine, scope, list_id, component_ids=[], policy='alles', expected_row_version=1)),
    )
    for field, call in cases:
        with pytest.raises(ShoppingListValidationError) as invalid:
            call()
        assert invalid.value.field == field, (field, str(invalid.value))
    assert _shopping_state(owner) == before


def test_location_isolation_foreign_scope_cannot_read_or_write(store):  # noqa: F811
    owner, engine, ids = store
    list_id = create_shopping_list(engine, _scope(ids), title='Standortliste')
    foreign_scope = ShoppingScope(ids['actor'], ids['other_location'], ids['authz'])
    with pytest.raises(ShoppingListNotFoundError):
        get_shopping_list(engine, foreign_scope, list_id)
    with pytest.raises(ShoppingListNotFoundError):
        archive_shopping_list(engine, foreign_scope, list_id, expected_row_version=1)
    with owner.connect() as c:
        assert c.execute(text('SELECT archived_at FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid)'),
                         {'id': list_id}).scalar_one() is None


def test_foreign_menu_week_is_rejected_on_create_and_writes_nothing(store):  # noqa: F811
    owner, engine, ids = store
    with owner.begin() as c:
        foreign_week = str(c.execute(text('''INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start)
            SELECT :other_location, id, DATE '2026-09-14' FROM cafeteria.offer_profiles WHERE code='patient'
            RETURNING public_id'''), ids).scalar_one())
    before = _shopping_state(owner)
    with pytest.raises(ShoppingListValidationError):
        create_shopping_list(engine, _scope(ids), title='Fremdwoche', menu_week_public_id=foreign_week)
    assert _shopping_state(owner) == before


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


def test_authz_change_between_load_and_write_is_stale_and_writes_nothing(store):  # noqa: F811
    owner, engine, ids = store
    list_id, revision_1, line = _computed_list(store)
    scope = _scope(ids)
    manual_id = add_manual_item(engine, scope, list_id, item_text='Servietten')
    item_public = _item_public(owner, ids['item'])
    with owner.begin() as c:
        c.execute(text("INSERT INTO cafeteria.user_role_cache(user_id, role_code, source) VALUES (:actor, 'Cafeteria.Editor', 'local')"), ids)
        assert c.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:actor'), ids).scalar_one() != ids['authz']
    before = _shopping_state(owner)
    calls = (
        lambda: create_shopping_list(engine, scope, title='Neu'),
        lambda: archive_shopping_list(engine, scope, list_id, expected_row_version=2),
        lambda: compute_revision(engine, scope, list_id, component_ids=[f'{item_public}:1'], policy='leaf', expected_row_version=2),
        lambda: set_line_checked(engine, scope, list_id, revision_public_id=revision_1, line_key=line['line_key'], checked=True),
        lambda: add_manual_item(engine, scope, list_id, item_text='Becher'),
        lambda: update_manual_item(engine, scope, list_id, manual_id, expected_row_version=1, item_text='Tassen'),
        lambda: set_manual_item_checked(engine, scope, list_id, manual_id, expected_row_version=1, checked=True),
        lambda: delete_manual_item(engine, scope, list_id, manual_id, expected_row_version=1),
        lambda: list_shopping_lists(engine, scope),
        lambda: get_shopping_list(engine, scope, list_id),
    )
    for call in calls:
        with pytest.raises(ShoppingListStaleActorError):
            call()
    assert _shopping_state(owner) == before


def test_disabled_or_roleless_actor_is_denied_for_reads_and_writes(store):  # noqa: F811
    owner, engine, ids = store
    list_id = create_shopping_list(engine, _scope(ids), title='Sperre')
    with owner.begin() as c:
        roleless = c.execute(text("INSERT INTO cafeteria.users(auth_provider, display_name) VALUES ('local', 'Ohne Rolle') "
                                  'RETURNING id, authz_version')).one()
        c.execute(text('UPDATE cafeteria.users SET disabled_at=clock_timestamp() WHERE id=:actor'), ids)
        disabled_authz = c.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:actor'), ids).scalar_one()
    before = _shopping_state(owner)
    for scope in (ShoppingScope(ids['actor'], ids['location'], disabled_authz),
                  ShoppingScope(roleless.id, ids['location'], roleless.authz_version)):
        for call in (lambda: create_shopping_list(engine, scope, title='Neu'),
                     lambda: add_manual_item(engine, scope, list_id, item_text='Becher'),
                     lambda: get_shopping_list(engine, scope, list_id)):
            with pytest.raises(ShoppingListActorDeniedError) as denied:
                call()
            assert not isinstance(denied.value, ShoppingListStaleActorError)
    assert _shopping_state(owner) == before


def test_serialization_failure_during_compute_maps_to_retry(store):  # noqa: F811
    owner, engine, ids = store
    list_id = create_shopping_list(engine, _scope(ids), title='Serialisierung')
    ids['owner'] = owner
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    item_public = _item_public(owner, ids['item'])
    with ThreadPoolExecutor(1) as pool, owner.connect() as blocker:
        blocker.execute(text("UPDATE cafeteria.shopping_lists SET note='Parallel' WHERE public_id=CAST(:id AS uuid)"), {'id': list_id})
        call = pool.submit(compute_revision, engine, _scope(ids), list_id, component_ids=[f'{item_public}:1'],
                           policy='leaf', expected_row_version=1)
        _wait_for_blocked(owner, 1)
        blocker.commit()
        with pytest.raises(ShoppingListRetryError) as retry:
            call.result(timeout=30)
    assert str(retry.value) == 'Die Einkaufsliste wird gerade bearbeitet. Bitte erneut versuchen.'
    assert retry.value.__cause__ is None and retry.value.__suppress_context__
    assert _count(owner, 'shopping_list_revisions') == 0


def test_concurrent_revision_number_unique_conflict_maps_to_conflict(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    item_public = _item_public(owner, ids['item'])
    list_id = create_shopping_list(engine, _scope(ids), title='Eindeutig')
    snapshot = json.dumps({'inputs': [], 'result': {'lines': []}})
    with ThreadPoolExecutor(1) as pool, owner.connect() as blocker:
        blocker.execute(text('''INSERT INTO cafeteria.shopping_list_revisions(
                shopping_list_id, revision_number, policy, snapshot_json, content_hash_sha256, computed_by)
            SELECT id, 1, 'leaf', CAST(:snap AS jsonb),
                   encode(public.digest(convert_to(CAST(:snap AS jsonb)::text, 'UTF8'), 'sha256'), 'hex'), :actor
            FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid)'''),
            {'snap': snapshot, 'actor': ids['actor'], 'id': list_id})
        call = pool.submit(compute_revision, engine, _scope(ids), list_id, component_ids=[f'{item_public}:1'],
                           policy='leaf', expected_row_version=1)
        _wait_for_blocked(owner, 1)
        blocker.commit()
        with pytest.raises(ShoppingListConflictError) as conflict:
            call.result(timeout=30)
    assert type(conflict.value) is ShoppingListConflictError
    assert 'duplicate' not in str(conflict.value) and conflict.value.__cause__ is None
    assert _count(owner, 'shopping_list_revisions') == 1


def test_lock_timeout_maps_to_retry(store):  # noqa: F811
    owner, engine, ids = store
    list_id = create_shopping_list(engine, _scope(ids), title='Sperrfrist')
    with ThreadPoolExecutor(1) as pool, owner.connect() as blocker:
        blocker.execute(text('SELECT id FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid) FOR UPDATE'), {'id': list_id})
        call = pool.submit(archive_shopping_list, engine, _scope(ids), list_id, expected_row_version=1)
        with pytest.raises(ShoppingListRetryError):
            call.result(timeout=15)
        blocker.rollback()
    with owner.connect() as c:
        assert c.execute(text('SELECT archived_at FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid)'),
                         {'id': list_id}).scalar_one() is None


def test_database_data_exception_maps_to_validation(store):  # noqa: F811
    owner, engine, ids = store
    ids['owner'] = owner
    item_public = _item_public(owner, ids['item'])
    list_id = create_shopping_list(engine, _scope(ids), title='Datenfehler')
    with pytest.raises(ShoppingListValidationError) as invalid:
        compute_revision(engine, _scope(ids), list_id, component_ids=[f'{item_public}:99999999999'],
                         policy='leaf', expected_row_version=1)
    assert str(invalid.value) == 'Die Angaben sind ungültig.' and invalid.value.__cause__ is None
    assert invalid.value.field is None
    assert _count(owner, 'shopping_list_revisions') == 0


def test_other_database_error_maps_to_unavailable_without_details(store):  # noqa: F811
    owner, engine, ids = store
    create_shopping_list(engine, _scope(ids), title='Rechte')
    with owner.begin() as c:
        c.execute(text('REVOKE SELECT ON cafeteria.shopping_lists FROM cafeteria_app'))
    with pytest.raises(ShoppingListUnavailableError) as unavailable:
        list_shopping_lists(engine, _scope(ids))
    assert str(unavailable.value) == 'Einkaufslisten sind derzeit nicht verfügbar.'
    assert unavailable.value.__cause__ is None and unavailable.value.__suppress_context__


def test_running_compute_blocks_check_which_never_lands_on_superseded_revision(store):  # noqa: F811
    owner, engine, ids = store
    list_id, revision_1, line = _computed_list(store)
    item_public = _item_public(owner, ids['item'])
    with ThreadPoolExecutor(2) as pool, owner.connect() as blocker:
        blocker.execute(text('SELECT id FROM cafeteria.shopping_lists WHERE public_id=CAST(:id AS uuid) FOR UPDATE'), {'id': list_id})
        compute = pool.submit(compute_revision, engine, _scope(ids), list_id, component_ids=[f'{item_public}:1'],
                              policy='leaf', expected_row_version=2)
        _wait_for_blocked(owner, 1)
        check = pool.submit(set_line_checked, engine, _scope(ids), list_id, revision_public_id=revision_1,
                            line_key=line['line_key'], checked=True)
        _wait_for_blocked(owner, 2)
        assert not check.done()
        blocker.commit()
        revision_2 = compute.result(timeout=30)
        with pytest.raises(ShoppingListValidationError):
            check.result(timeout=30)
    assert _status_revision(owner, list_id) == []
    assert get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines'][0]['checked_status'] == 'open'
    set_line_checked(engine, _scope(ids), list_id, revision_public_id=revision_2, line_key=line['line_key'], checked=True)
    assert _status_revision(owner, list_id) == [revision_2]
    assert get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines'][0]['checked_status'] == 'checked'


def test_in_flight_check_is_seen_by_compute_and_carried_to_newest_revision(store):  # noqa: F811
    owner, engine, ids = store
    list_id, revision_1, line = _computed_list(store)
    item_public = _item_public(owner, ids['item'])
    signature = f"{format(Decimal(line['quantity']), 'f')} {line['unit_code']}"
    with ThreadPoolExecutor(2) as pool, owner.connect() as blocker:
        blocker.execute(text('''INSERT INTO cafeteria.shopping_list_line_status(
                shopping_list_id, line_key, revision_id, checked_quantity, checked_by)
            SELECT l.id, :key, r.id, :signature, :actor FROM cafeteria.shopping_lists l
            JOIN cafeteria.shopping_list_revisions r ON r.shopping_list_id=l.id AND r.public_id=CAST(:revision AS uuid)
            WHERE l.public_id=CAST(:id AS uuid)'''),
            {'key': line['line_key'], 'signature': signature, 'actor': ids['actor'], 'revision': revision_1, 'id': list_id})
        check = pool.submit(set_line_checked, engine, _scope(ids), list_id, revision_public_id=revision_1,
                            line_key=line['line_key'], checked=True)
        _wait_for_blocked(owner, 1)
        compute = pool.submit(compute_revision, engine, _scope(ids), list_id, component_ids=[f'{item_public}:1'],
                              policy='leaf', expected_row_version=2)
        _wait_for_blocked(owner, 2)
        blocker.rollback()
        assert check.result(timeout=30) is None
        revision_2 = compute.result(timeout=30)
    assert _status_revision(owner, list_id) == [revision_2]
    assert get_shopping_list(engine, _scope(ids), list_id)['selected_revision']['lines'][0]['checked_status'] == 'checked'
