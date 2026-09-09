"""Real immutable SQL27 snapshots consumed through the public revision reader."""
import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy import text

from cafeteria import recipe_reads as reads
from cafeteria.admin.recipe_pdf import render_recipe_pdf
from cafeteria.print_template_config import default_config
from cafeteria.recipe_snapshot_v2 import MAX_BYTES, reconstructed_snapshots, verified_prepared
from cafeteria.recipe_snapshots import frozen_json
from cafeteria.recipe_types import RecipeConfigurationError
from test_recipe_pdf import prepared_revision, text as pdf_text
from prepared_food_fixtures import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, create_food, create_recipe,
    freeze, legacy_freeze, update_food, food_payload, state,
)
from prepared_food_fixtures import prepared as prepared


def shared_closure(engine, ids):
    raw = create_food(engine, ids, 'Rohgemüse')
    leaf = freeze(engine, ids, create_recipe(engine, ids, [raw], name='Gemüsebasis'))
    base = create_food(engine, ids, 'Gemüsebasis', pin=leaf)
    left = freeze(engine, ids, create_recipe(engine, ids, [base], name='Helle Sauce'))
    right = freeze(engine, ids, create_recipe(engine, ids, [base], name='Dunkle Sauce'))
    first = create_food(engine, ids, 'Helle Sauce', pin=left)
    second = create_food(engine, ids, 'Dunkle Sauce', pin=right)
    root = freeze(engine, ids, create_recipe(engine, ids, [first, second, first], name='Tellergericht'))
    return root, base


def test_reader_reconstructs_shared_grandchild_against_original_pg_bytes(prepared):
    owner, engine, ids = prepared
    root, _ = shared_closure(engine, ids)
    before = state(owner)
    revision = reads.get_revision(engine, root['public_id'])
    children = getattr(revision, 'prepared_revisions', ())
    assert len(children) == 3
    assert [child.public_id for child in children] == sorted(child.public_id for child in children)
    with owner.connect() as connection:
        for child in children:
            original = connection.execute(text('''SELECT snapshot_json::text FROM cafeteria.recipe_revisions
                WHERE public_id=CAST(:id AS uuid)'''), {'id': child.public_id}).scalar_one()
            assert child.canonical_snapshot_text == original
            assert hashlib.sha256(original.encode()).hexdigest() == child.content_hash_sha256
    assert state(owner) == before


def test_real_v2_pdf_prints_both_uses_and_original_child_content(prepared):
    _, engine, ids = prepared
    root, _ = shared_closure(engine, ids)
    revision = reads.get_revision(engine, root['public_id'])
    data = render_recipe_pdf(revision, config=default_config(), images={}, target='2')
    body = pdf_text(data)
    assert 'Tellergericht' in body
    assert body.count('Helle Sauce') == 2
    assert body.count('Dunkle Sauce') == 1
    assert body.count('Gemüsebasis') == 3
    assert 'Zubereitung für' in body


@pytest.mark.parametrize('change', ['missing', 'extra', 'duplicate', 'order', 'identity', 'hash', 'body'])
def test_real_reader_rejects_self_hashed_but_inconsistent_stored_closure(prepared, change):
    owner, engine, ids = prepared
    root, _ = shared_closure(engine, ids)
    original = reads.get_revision(engine, root['public_id'])
    snapshot = json.loads(original.canonical_snapshot_text)
    entries = snapshot['prepared_revisions']
    if change == 'missing':
        entries.pop()
    elif change == 'extra':
        entries.append(deepcopy(entries[0]) | {'revision_public_id': str(UUID(int=999))})
        entries.sort(key=lambda item: item['revision_public_id'])
    elif change == 'duplicate':
        entries.append(deepcopy(entries[0]))
    elif change == 'order':
        entries.reverse()
    elif change == 'identity':
        entries[0]['recipe_public_id'] = str(UUID(int=998))
    elif change == 'hash':
        entries[0]['content_hash_sha256'] = '0' * 64
    elif change == 'body':
        entries[0]['snapshot']['recipe']['title'] = 'Nicht das gespeicherte Original'
    # Privileged synthetic corruption fixture, no disabled guard or rewritten original.
    # Its own table hash is valid; the reader must reject the invalid captured closure.
    with owner.begin() as connection:
        invalid_id = connection.execute(text('''INSERT INTO cafeteria.recipe_revisions
            (location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
            SELECT location_id,recipe_id,999,CAST(:body AS jsonb),
                encode(public.digest(convert_to(CAST(:body AS jsonb)::text,'UTF8'),'sha256'),'hex'),created_by
            FROM cafeteria.recipe_revisions WHERE public_id=CAST(:root AS uuid) RETURNING public_id'''),
            {'root': root['public_id'], 'body': json.dumps(snapshot)}).scalar_one()
    before = state(owner)
    with pytest.raises(RecipeConfigurationError):
        reads.get_revision(engine, str(invalid_id))
    assert state(owner) == before


def test_v1_terminal_and_parent_bytes_survive_current_food_pin_and_name_changes(prepared):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Alte Rohzutat')
    old = legacy_freeze(owner, ids, create_recipe(engine, ids, [raw], name='Alte Zubereitung'))
    historical = create_food(engine, ids, 'Historischer Einsatz', pin=old)
    parent = freeze(engine, ids, create_recipe(engine, ids, [historical], name='Festgehaltener Teller'))
    original = reads.get_revision(engine, parent['public_id'])
    new_raw = create_food(engine, ids, 'Neue Zutat')
    new = freeze(engine, ids, create_recipe(engine, ids, [new_raw], name='Neue Zubereitung'))
    update_food(engine, ids, raw, food_payload(ids, 'Jetzt vorbereitet', pin=new))
    update_food(engine, ids, historical, food_payload(ids, 'Anderer Name und Pin', pin=new))
    after = reads.get_revision(engine, parent['public_id'])
    assert after == original and len(after.prepared_revisions) == 1
    assert after.prepared_revisions[0].snapshot['schema_version'] == 1
    assert after.prepared_revisions[0].public_id == old['public_id']
    assert reads.get_revision(engine, old['public_id']).prepared_revisions == ()


def test_real_reader_rejects_an_incomplete_captured_v1_child(prepared):
    owner, engine, ids = prepared
    raw = create_food(engine, ids, 'Alte Rohzutat')
    old = legacy_freeze(owner, ids, create_recipe(engine, ids, [raw], name='Alte Zubereitung'))
    historical = create_food(engine, ids, 'Historischer Einsatz', pin=old)
    parent = freeze(engine, ids, create_recipe(engine, ids, [historical], name='Festgehaltener Teller'))
    accepted = reads.get_revision(engine, parent['public_id'])
    assert accepted.prepared_revisions[0].snapshot['schema_version'] == 1
    snapshot = json.loads(accepted.canonical_snapshot_text)
    snapshot['prepared_revisions'][0]['snapshot']['recipe']['ingredients'][0]['food_public_id'] = None
    # Privileged synthetic corruption fixture; both stored originals stay untouched and
    # the new row hashes itself correctly, so only the captured closure is invalid.
    with owner.begin() as connection:
        invalid_id = connection.execute(text('''INSERT INTO cafeteria.recipe_revisions
            (location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
            SELECT location_id,recipe_id,998,CAST(:body AS jsonb),
                encode(public.digest(convert_to(CAST(:body AS jsonb)::text,'UTF8'),'sha256'),'hex'),created_by
            FROM cafeteria.recipe_revisions WHERE public_id=CAST(:root AS uuid) RETURNING public_id'''),
            {'root': parent['public_id'], 'body': json.dumps(snapshot)}).scalar_one()
    before = state(owner)
    with pytest.raises(RecipeConfigurationError):
        reads.get_revision(engine, str(invalid_id))
    assert state(owner) == before
    assert reads.get_revision(engine, parent['public_id']) == accepted


def incomplete_child(change):
    """Rebuild the frozen fixture with one incomplete captured v1 child and valid hashes.

    Every pin, index hash and canonical text stays self-consistent, so SQL27 completeness
    is the only remaining reason the reader may reject the closure.
    """
    original = prepared_revision()
    body = json.loads(original.prepared_revisions[0].canonical_snapshot_text)
    ingredients = body['recipe']['ingredients']
    if change == 'null_food':
        ingredients[0]['food_public_id'] = None
    elif change == 'null_amount':
        ingredients[0]['quantity'], ingredients[0]['unit_code'] = None, None
    else:
        body['recipe']['ingredients'] = []
    raw = json.dumps(body, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    child = replace(original.prepared_revisions[0], snapshot=frozen_json(body),
                    canonical_snapshot_text=raw, content_hash_sha256=digest)
    parent = json.loads(original.canonical_snapshot_text)
    parent['foods'][0]['prepared_recipe']['content_hash_sha256'] = digest
    parent['prepared_revisions'][0]['content_hash_sha256'] = digest
    parent['prepared_revisions'][0]['snapshot'] = body
    parent_raw = json.dumps(parent, ensure_ascii=False)
    return replace(original, snapshot=frozen_json(parent), canonical_snapshot_text=parent_raw,
                   content_hash_sha256=hashlib.sha256(parent_raw.encode()).hexdigest(),
                   prepared_revisions=(child,))


@pytest.mark.parametrize('change', ['null_food', 'null_amount', 'empty_ingredients'])
def test_incomplete_captured_v1_child_is_rejected_like_sql27(change):
    # 0024_v26_to_v27.sql:319-321 applies recipe_snapshot_complete_v27 to every queued
    # body before the v1-terminal continue at 329; the reader must not be more permissive.
    with pytest.raises(RecipeConfigurationError):
        verified_prepared(incomplete_child(change))


def test_complete_captured_v1_child_is_still_reconstructed():
    original = prepared_revision()
    assert [child.public_id for child in verified_prepared(original)] == [
        original.prepared_revisions[0].public_id]
    assert original.prepared_revisions[0].snapshot['schema_version'] == 1


def synthetic_chain(depth, width=1):
    template = json.loads(prepared_revision().canonical_snapshot_text)
    index = []
    bodies = []
    for level in range(depth + 1):
        body = deepcopy(template)
        body.pop('prepared_revisions')
        food_id = str(UUID(int=1000 + level))
        body['recipe']['ingredients'] = [dict(body['recipe']['ingredients'][0], food_public_id=food_id)] * width
        food = body['foods'][0]
        food['public_id'] = food_id
        food['prepared_recipe'] = None if level == depth else {
            'recipe_public_id': str(UUID(int=2001 + level)), 'revision_public_id': str(UUID(int=3001 + level)),
            'content_hash_sha256': 'a' * 64}
        bodies.append(body)
        if level:
            index.append({'recipe_public_id': str(UUID(int=2000 + level)),
                'revision_public_id': str(UUID(int=3000 + level)), 'content_hash_sha256': 'a' * 64, 'snapshot': body})
    return bodies[0] | {'prepared_revisions': index}, str(UUID(int=2000))


@pytest.mark.parametrize(('depth', 'width', 'valid'), [(8, 1, True), (9, 1, False), (2, 15, True), (2, 16, False)])
def test_depth_and_expanded_occurrence_boundaries_before_expansion(depth, width, valid):
    snapshot, recipe_id = synthetic_chain(depth, width)
    if valid:
        assert len(reconstructed_snapshots(snapshot, recipe_id, 10000)) == depth
    else:
        with pytest.raises(RecipeConfigurationError):
            reconstructed_snapshots(snapshot, recipe_id, 10000)


def test_exact_size_boundary_and_unknown_versions_are_controlled():
    snapshot, recipe_id = synthetic_chain(0)
    assert reconstructed_snapshots(snapshot, recipe_id, MAX_BYTES) == {}
    for size in (0, MAX_BYTES + 1):
        with pytest.raises(RecipeConfigurationError):
            reconstructed_snapshots(snapshot, recipe_id, size)
    for version in (True, 2.0, '2', None, 3):
        with pytest.raises(RecipeConfigurationError):
            reconstructed_snapshots(snapshot | {'schema_version': version}, recipe_id, 10000)


def test_exact_64_unique_children_and_duplicate_use_work_boundary():
    snapshot, recipe_id = synthetic_chain(1)
    ingredient, food, child = (deepcopy(snapshot['recipe']['ingredients'][0]),
                              deepcopy(snapshot['foods'][0]), deepcopy(snapshot['prepared_revisions'][0]))
    snapshot['recipe']['ingredients'], snapshot['foods'], snapshot['prepared_revisions'] = [], [], []
    for number in range(64):
        food_id = str(UUID(int=10000 + number))
        pin = {'recipe_public_id': str(UUID(int=20000 + number)), 'revision_public_id': str(UUID(int=30000 + number)),
               'content_hash_sha256': 'a' * 64}
        snapshot['recipe']['ingredients'].append(ingredient | {'food_public_id': food_id})
        snapshot['foods'].append(food | {'public_id': food_id, 'prepared_recipe': pin})
        snapshot['prepared_revisions'].append(child | pin)
    assert len(reconstructed_snapshots(snapshot, recipe_id, 100000)) == 64
    snapshot['prepared_revisions'].append(child)
    with pytest.raises(RecipeConfigurationError):
        reconstructed_snapshots(snapshot, recipe_id, 100000)


def test_canonical_dto_text_body_and_child_original_hash_cannot_be_replaced():
    original = prepared_revision()
    for broken in (replace(original, canonical_snapshot_text='{}'),
                   replace(original, content_hash_sha256='0' * 64),
                   replace(original, prepared_revisions=()),
                   replace(original, snapshot=frozen_json({'schema_version': 2})),
                   replace(original, prepared_revisions=(replace(original.prepared_revisions[0],
                       content_hash_sha256='0' * 64),))):
        with pytest.raises(RecipeConfigurationError):
            verified_prepared(broken)


@pytest.mark.parametrize('extra_byte', [False, True])
def test_actual_pg_canonical_two_mib_boundary_without_changing_existing_revision(prepared, extra_byte):
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Rohzutat')
    root = freeze(engine, ids, create_recipe(engine, ids, [food]))
    revision = reads.get_revision(engine, root['public_id'])
    body = json.loads(revision.canonical_snapshot_text)
    body['foods'][0]['factor_decisions'] = ['']
    with owner.begin() as connection:
        size = connection.execute(text("SELECT octet_length(CAST(:body AS jsonb)::text)"),
                                  {'body': json.dumps(body)}).scalar_one()
        body['foods'][0]['factor_decisions'] = ['x' * (MAX_BYTES - size + int(extra_byte))]
        candidate = connection.execute(text('''INSERT INTO cafeteria.recipe_revisions
            (location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
            SELECT location_id,recipe_id,999,CAST(:body AS jsonb),
                encode(public.digest(convert_to(CAST(:body AS jsonb)::text,'UTF8'),'sha256'),'hex'),created_by
            FROM cafeteria.recipe_revisions WHERE public_id=CAST(:root AS uuid)
            RETURNING public_id,octet_length(snapshot_json::text) AS size'''),
            {'body': json.dumps(body), 'root': root['public_id']}).one()
    assert candidate.size == MAX_BYTES + int(extra_byte)
    if extra_byte:
        with pytest.raises(RecipeConfigurationError):
            reads.get_revision(engine, str(candidate.public_id))
    else:
        accepted = reads.get_revision(engine, str(candidate.public_id))
        assert len(accepted.canonical_snapshot_text.encode()) == MAX_BYTES
    assert reads.get_revision(engine, root['public_id']) == revision


def test_exact_4096_ingredient_uses_and_graph_work_overflow():
    snapshot, recipe_id = synthetic_chain(1, 64)
    snapshot['prepared_revisions'][0]['snapshot']['recipe']['ingredients'].pop()
    assert len(reconstructed_snapshots(snapshot, recipe_id, 100000)) == 1  # 64 + 64*63 = 4096.
    overflow, recipe_id = synthetic_chain(2, 64)
    with pytest.raises(RecipeConfigurationError):
        reconstructed_snapshots(overflow, recipe_id, 100000)
