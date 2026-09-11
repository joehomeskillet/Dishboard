"""Store contracts for persistent recipe-import drafts; no recipe creation."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from cafeteria import recipe_import_store as store
from cafeteria import recipe_store as recipes
from cafeteria.master_data_types import ObjectExpectation
from cafeteria.recipe_types import RecipeConflictError, RecipeValidationError
from test_master_data_db import (  # noqa: F401
    app_engine, installed_pg16, master, pg16, seeded_pg16,
)
from test_recipe_import import json_bytes, parse, recipe
from test_recipe_store_db import payload as recipe_payload


def snapshot(owner):
    tables = (
        'recipe_import_batches', 'recipe_import_candidates', 'recipes',
        'recipe_ingredients', 'audit_events',
    )
    with owner.connect() as current:
        return {
            table: current.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
            )).all()
            for table in tables
        }


def make_payload(*, annotations=('unreviewed',), title='Kartoffelsuppe'):
    preview = parse(json_bytes(recipe(title)))
    return store.payload_from_preview(preview, annotations=annotations), preview


def test_create_keeps_origin_and_unresolved_food(master):  # noqa: F811
    owner, engine, actor = master
    before = snapshot(owner)
    payload, preview = make_payload()
    location = recipes.get_location(engine)
    result = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, result.public_id)
    assert result.row_version == 1
    assert batch.adapter_kind == 'file_import'
    assert batch.source_sha256 == preview.source_sha256
    assert batch.status == 'draft'
    assert batch.confirmation_hash_sha256 is None
    candidate = batch.candidates[0]
    assert candidate.origin_ref == f'{batch.public_id}:1'
    assert candidate.original_source_kind == 'file_import'
    assert candidate.original_payload['source']['kind'] == 'file_import'
    assert candidate.original_payload['ingredients'][0]['food_public_id'] is None
    assert 'unreviewed' in batch.annotations
    note = candidate.candidate_payload['source']['note']
    assert preview.source_sha256 in note and 'ungeprüft' in note
    assert 'unreviewed' not in candidate.candidate_payload
    assert snapshot(owner)['recipes'] == before['recipes']
    assert len(snapshot(owner)['recipe_import_batches']) == 1


def test_candidate_edit_preserves_origin_and_invalidates_confirmation(master):  # noqa: F811
    owner, engine, actor = master
    payload, preview = make_payload()
    location = recipes.get_location(engine)
    created = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'acknowledge'}, expected_location_id=location,
    )
    confirmed = store.get_batch(engine, batch.public_id)
    assert confirmed.confirmation_hash_sha256 == confirmed.candidate_hash_sha256
    original = dict(confirmed.candidates[0].original_payload)
    origin_hash = confirmed.source_sha256
    edited = dict(store.thaw(confirmed.candidates[0].candidate_payload))
    edited['title'] = 'Geänderte Vorschau'
    before = snapshot(owner)
    store.update_batch(
        engine, actor, ObjectExpectation(confirmed.public_id, confirmed.row_version),
        {'action': 'save', 'annotations': ['unreviewed', 'allergen_not_checked'], 'rows': [{
            'row_number': 1, 'candidate_payload': edited,
            'duplicate_decision': 'create_new',
            'target_recipe_public_id': None, 'target_row_version': None,
        }]},
        expected_location_id=location,
    )
    updated = store.get_batch(engine, batch.public_id)
    assert updated.row_version == confirmed.row_version + 1
    assert updated.candidate_hash_sha256 != confirmed.candidate_hash_sha256
    assert updated.confirmation_hash_sha256 is None
    assert dict(updated.candidates[0].original_payload) == original
    assert updated.source_sha256 == origin_hash
    assert updated.candidates[0].origin_ref == confirmed.candidates[0].origin_ref
    assert updated.candidates[0].candidate_payload['title'] == 'Geänderte Vorschau'
    assert updated.candidates[0].original_source_kind == 'file_import'
    assert snapshot(owner)['recipes'] == before['recipes']
    note = updated.candidates[0].candidate_payload['source']['note']
    assert 'ungeprüft' in note and 'Allergene nicht geprüft' in note
    assert 'unreviewed' not in updated.candidates[0].candidate_payload


def test_identical_save_does_not_bump_and_stale_cas_is_conflict(master):  # noqa: F811
    owner, engine, actor = master
    payload, _preview = make_payload()
    location = recipes.get_location(engine)
    created = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, created.public_id)
    row = {
        'row_number': 1,
        'candidate_payload': dict(store.thaw(batch.candidates[0].candidate_payload)),
        'duplicate_decision': 'undecided',
        'target_recipe_public_id': None,
        'target_row_version': None,
    }
    before = snapshot(owner)
    again = store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'save', 'annotations': list(batch.annotations), 'rows': [row]},
        expected_location_id=location,
    )
    assert again.row_version == batch.row_version
    assert snapshot(owner) == before
    with pytest.raises(RecipeConflictError, match='Importstapel wurde geändert'):
        store.update_batch(
            engine, actor, ObjectExpectation(batch.public_id, 99),
            {'action': 'save', 'annotations': list(batch.annotations), 'rows': [row]},
            expected_location_id=location,
        )
    assert snapshot(owner) == before


def test_unknown_annotation_keys_are_rejected(master):  # noqa: F811
    _owner, engine, actor = master
    payload, _preview = make_payload()
    with pytest.raises(RecipeValidationError, match='Ungültige Importannotation'):
        store.payload_from_preview(parse(json_bytes(recipe())), annotations=('secret_flag',))
    location = recipes.get_location(engine)
    created = store.create_batch(engine, actor, payload, expected_location_id=location)
    batch = store.get_batch(engine, created.public_id)
    bad = dict(store.thaw(batch.candidates[0].candidate_payload))
    bad['unreviewed'] = True
    with pytest.raises(RecipeValidationError):
        store.update_batch(
            engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
            {'action': 'save', 'annotations': ['unreviewed'], 'rows': [{
                'row_number': 1, 'candidate_payload': bad,
                'duplicate_decision': 'undecided',
                'target_recipe_public_id': None, 'target_row_version': None,
            }]},
            expected_location_id=location,
        )


def test_create_does_not_write_recipes_or_relabel_source(master):  # noqa: F811
    owner, engine, actor = master
    location = recipes.get_location(engine)
    existing = recipes.create_recipe(engine, actor, recipe_payload(), expected_location_id=location)
    before = snapshot(owner)
    payload, preview = make_payload()
    store.create_batch(engine, actor, payload, expected_location_id=location)
    after = snapshot(owner)
    assert after['recipes'] == before['recipes']
    assert existing.public_id
    batch = store.list_batches(engine)[0]
    loaded = store.get_batch(engine, batch.public_id)
    assert loaded.candidates[0].original_payload['source']['kind'] == 'file_import'
    assert loaded.candidates[0].original_payload['source']['reference'] == (
        f'sha256:{preview.source_sha256}:row:1'
    )
