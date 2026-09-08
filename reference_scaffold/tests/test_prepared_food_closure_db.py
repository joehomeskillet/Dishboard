"""Exact immutable closure bytes, semantic identities and bounded native SQL work."""
from copy import deepcopy
import json
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError

from prepared_food_fixtures import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, create_food, update_food,
    food_payload, create_recipe, preview, freeze, legacy_freeze, revision_snapshot, execute, state,
    recipe_payload,
)
from prepared_food_fixtures import prepared as prepared


def check(owner, snapshot, recipe):
    return execute(owner, 'SELECT cafeteria.check_prepared_snapshot_v27(CAST(:snapshot AS jsonb),CAST(:recipe AS uuid))',
                   {'snapshot': json.dumps(snapshot), 'recipe': recipe})


def reconstruct(node, index):
    result = deepcopy(node['snapshot'])
    if result['schema_version'] == 1:
        return result
    reachable = set()
    pending = [result]
    while pending:
        for food in pending.pop()['foods']:
            pin = food['prepared_recipe']
            if pin is not None and pin['revision_public_id'] not in reachable:
                reachable.add(pin['revision_public_id'])
                pending.append(index[pin['revision_public_id']]['snapshot'])
    result['prepared_revisions'] = [index[key] for key in sorted(reachable)]
    return result


def test_shared_grandchild_reconstructs_every_original_child_hash(prepared):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Ursprung')
    leaf = freeze(engine, ids, create_recipe(engine, ids, [raw], name='Basis'))
    prepared_leaf = create_food(engine, ids, 'Basismischung', pin=leaf)
    left = freeze(engine, ids, create_recipe(engine, ids, [prepared_leaf], name='Links'))
    right = freeze(engine, ids, create_recipe(engine, ids, [prepared_leaf], name='Rechts'))
    left_food = create_food(engine, ids, 'Linke Zubereitung', pin=left)
    right_food = create_food(engine, ids, 'Rechte Zubereitung', pin=right)
    root = create_recipe(engine, ids, [left_food, right_food, left_food], name='Gesamtrezept')
    frozen = freeze(engine, ids, root)
    snapshot = revision_snapshot(owner, frozen)
    nodes = snapshot['prepared_revisions']
    assert len(nodes) == 3 and len(snapshot['recipe']['ingredients']) == 3
    assert [n['revision_public_id'] for n in nodes] == sorted(n['revision_public_id'] for n in nodes)
    index = {node['revision_public_id']: node for node in nodes}
    for node in nodes:
        reconstructed = reconstruct(node, index)
        stored = revision_snapshot(owner, {'public_id': node['revision_public_id']})
        assert reconstructed == stored
        hashed = execute(owner, "SELECT encode(public.digest(convert_to(CAST(:snapshot AS jsonb)::text,'UTF8'),'sha256'),'hex')",
                         {'snapshot': json.dumps(reconstructed)})
        assert hashed == node['content_hash_sha256']
    original = deepcopy(snapshot)
    update_food(engine, ids, prepared_leaf, food_payload(ids, 'Heute anderer Name'))
    assert revision_snapshot(owner, frozen) == original


def test_v1_is_terminal_and_retains_original_json_hash_after_current_pin_changes(prepared):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Früher roh')
    old = legacy_freeze(owner, ids, create_recipe(engine, ids, [raw], name='Historisch'))
    before = revision_snapshot(owner, old)
    other = create_food(engine, ids, 'Andere Rohzutat')
    child = freeze(engine, ids, create_recipe(engine, ids, [other], name='Spätere Zubereitung'))
    update_food(engine, ids, raw, food_payload(ids, 'Jetzt vorbereitet', pin=child))
    historical_food = create_food(engine, ids, 'Historische Zubereitung', pin=old)
    root = freeze(engine, ids, create_recipe(engine, ids, [historical_food], name='Historie verwenden'))
    snapshot = revision_snapshot(owner, root)
    assert len(snapshot['prepared_revisions']) == 1
    assert snapshot['prepared_revisions'][0]['snapshot'] == before
    assert revision_snapshot(owner, old) == before and before['schema_version'] == 1
    assert snapshot['prepared_revisions'][0]['content_hash_sha256'] == old['content_hash_sha256']


@pytest.mark.parametrize('indirect', [False, True])
def test_current_food_cycles_include_v1_ingredient_identities(prepared, indirect):
    owner, engine, ids = prepared
    first = create_food(engine, ids, 'F')
    second = create_food(engine, ids, 'G')
    first_revision = legacy_freeze(owner, ids, create_recipe(engine, ids, [first], name='Enthält F'))
    if indirect:
        update_food(engine, ids, second, food_payload(ids, 'G', pin=first_revision))
        selected = legacy_freeze(owner, ids, create_recipe(engine, ids, [second], name='Enthält G'))
    else:
        selected = first_revision
    before = state(owner)
    with pytest.raises(DBAPIError) as error:
        update_food(engine, ids, first, food_payload(ids, 'F', pin=selected))
    assert error.value.orig.sqlstate == '55000' and state(owner) == before


def synthetic_chain(depth, *, width=1):
    """Closed deterministic shape; only private validation runs against these test values."""
    recipe_ids = [str(uuid4()) for _ in range(depth + 1)]
    revision_ids = [str(uuid4()) for _ in range(depth)]
    food_ids = [str(uuid4()) for _ in range(depth + 1)]
    bodies = []
    for level in range(depth + 1):
        pin = None if level == depth else {'recipe_public_id': recipe_ids[level + 1],
            'revision_public_id': revision_ids[level], 'content_hash_sha256': 'a' * 64}
        bodies.append({'schema_version': 2,
            'recipe': {'ingredients': [{'food_public_id': food_ids[level], 'quantity': '1', 'unit_code': 'G'}] * width},
            'foods': [{'public_id': food_ids[level], 'prepared_recipe': pin}]})
    index = [{'recipe_public_id': recipe_ids[i + 1], 'revision_public_id': revision_ids[i],
              'content_hash_sha256': 'a' * 64, 'snapshot': bodies[i + 1]} for i in range(depth)]
    root = bodies[0] | {'prepared_revisions': sorted(index, key=lambda n: n['revision_public_id'])}
    return root, recipe_ids[0]


def test_native_closure_limits_and_uniform_incomplete_rejection(prepared):
    owner, _, _ = prepared
    valid, recipe = synthetic_chain(8)
    check(owner, valid, recipe)
    too_deep, recipe_deep = synthetic_chain(9)
    with pytest.raises(DBAPIError) as error:
        check(owner, too_deep, recipe_deep)
    assert error.value.orig.sqlstate == 'P1901'
    for mutate in (lambda s: s.pop('schema_version'),
                   lambda s: s['recipe']['ingredients'][0].update(quantity=None),
                   lambda s: s.update(note='x' * 2097152),
                   lambda s: s['prepared_revisions'].append(deepcopy(s['prepared_revisions'][0]))):
        invalid = deepcopy(valid)
        mutate(invalid)
        with pytest.raises(DBAPIError) as error:
            check(owner, invalid, recipe)
        assert error.value.orig.sqlstate == 'P1901'
    wide, wide_recipe = synthetic_chain(2, width=16)
    with pytest.raises(DBAPIError) as error:
        check(owner, wide, wide_recipe)
    assert error.value.orig.sqlstate == 'P1901'  # 16 + 256 + 4096 occurrences.


def test_native_index_bound_and_consistent_duplicate_merge(prepared):
    owner, _, _ = prepared
    nodes = {str(uuid4()): {'content': 'stable'} for _ in range(64)}
    key = next(iter(nodes))
    node = {'revision_public_id': key}
    nodes[key] = node
    sql = 'SELECT cafeteria.merge_prepared_node_v27(CAST(:nodes AS jsonb),CAST(:node AS jsonb))'
    assert execute(owner, sql, {'nodes': json.dumps(nodes), 'node': json.dumps(node)}) == nodes
    with pytest.raises(DBAPIError) as error:
        execute(owner, sql, {'nodes': json.dumps(nodes), 'node': json.dumps({'revision_public_id': str(uuid4())})})
    assert error.value.orig.sqlstate == 'P1901'
    with pytest.raises(DBAPIError) as error:
        execute(owner, sql, {'nodes': json.dumps(nodes), 'node': json.dumps(node | {'changed': True})})
    assert error.value.orig.sqlstate == '55000'


@pytest.mark.parametrize(('width', 'allowed'), [(63, True), (64, False)])
def test_current_graph_work_is_bounded_before_enqueuing_all_occurrences(prepared, width, allowed):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Rohzutat')
    child = legacy_freeze(owner, ids, create_recipe(engine, ids, [raw] * width, name='Wiederholte Rohzutat'))
    middle = create_food(engine, ids, 'Mischung', pin=child)
    selected = legacy_freeze(owner, ids, create_recipe(engine, ids, [middle] * width, name='Wiederholte Mischung'))
    before = state(owner)
    if allowed:
        assert create_food(engine, ids, 'Fertige Mischung', pin=selected)['row_version'] == 1
    else:
        with pytest.raises(DBAPIError) as error:
            create_food(engine, ids, 'Zu viele Graphschritte', pin=selected)
        assert error.value.orig.sqlstate == 'P1901' and state(owner) == before


def test_repeated_recipe_identity_is_rejected_across_distinct_revisions(prepared):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Rohzutat')
    recipe = create_recipe(engine, ids, [raw], name='Identische Rezeptidentität')
    first = legacy_freeze(owner, ids, recipe)
    middle = create_food(engine, ids, 'Historische Zubereitung', pin=first)
    updated = execute(engine, '''SELECT cafeteria.update_recipe_v22(:actor,:authz,:location,
        CAST(:target AS uuid),:version,CAST(:payload AS jsonb))''', ids | {'target': recipe['public_id'],
        'version': first['recipe_row_version']}, recipe_payload([middle], name='Identische Rezeptidentität'))
    second = legacy_freeze(owner, ids, updated)
    before = state(owner)
    with pytest.raises(DBAPIError) as error:
        create_food(engine, ids, 'Rezeptkreis', pin=second)
    assert error.value.orig.sqlstate == '55000' and state(owner) == before


def test_exact_64_child_closure_boundary_and_expanded_quantity_boundary(prepared):
    owner, _, _ = prepared
    root, recipe = synthetic_chain(1)
    root['recipe']['ingredients'] = []
    root['foods'] = []
    root['prepared_revisions'] = []
    for _ in range(64):
        child, _ = synthetic_chain(0)
        food, child_recipe, revision = str(uuid4()), str(uuid4()), str(uuid4())
        pin = {'recipe_public_id': child_recipe, 'revision_public_id': revision, 'content_hash_sha256': 'a' * 64}
        root['recipe']['ingredients'].append({'food_public_id': food, 'quantity': '1', 'unit_code': 'G'})
        root['foods'].append({'public_id': food, 'prepared_recipe': pin})
        root['prepared_revisions'].append(pin | {'snapshot': child})
    check(owner, root, recipe)
    extra = deepcopy(root['prepared_revisions'][0]) | {'revision_public_id': str(uuid4())}
    root['prepared_revisions'].append(extra)
    with pytest.raises(DBAPIError) as error:
        check(owner, root, recipe)
    assert error.value.orig.sqlstate == 'P1901'
    accepted, accepted_recipe = synthetic_chain(2, width=15)
    check(owner, accepted, accepted_recipe)  # 3615 real ingredient occurrences.
