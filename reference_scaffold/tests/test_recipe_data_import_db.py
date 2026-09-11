"""Import the reviewed linked dish drafts through Foundations and recipe batches."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

WORKTREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE / 'tools'))
import build_recipe_draft_import as importer  # noqa: E402

from cafeteria import master_data_store as masters  # noqa: E402
from cafeteria import recipe_import_store as import_store  # noqa: E402
from cafeteria import recipe_store as recipes  # noqa: E402
from test_master_data_db import (  # noqa: E402,F401
    app_engine, installed_pg16, make_actor, master, pg16, seeded_pg16, signed_in,
)

DRAFT_PATH = WORKTREE / 'demo' / 'linked_recipe_drafts.json'
IMPORT_PATH = WORKTREE / 'demo' / 'linked_recipe_drafts_import.json'
TARGET_STORAGE = {'Trockenlager', 'Kühlraum', 'Tiefkühler'}


def load_import() -> dict:
    draft = importer.load_draft(DRAFT_PATH)
    return importer.translate_draft(draft, draft_path=DRAFT_PATH)


def snapshot(owner):
    tables = (
        'storage_locations', 'foods', 'food_storage_locations', 'recipes', 'recipe_ingredients',
        'recipe_import_batches', 'audit_events', 'publication_revisions',
    )
    with owner.connect() as current:
        return {
            table: current.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text'
            )).all()
            for table in tables
        }


def storage_names(engine):
    return {
        item.name
        for item in masters.list_vocabulary(engine, 'storage_location', include_archived=True, limit=200)
    }


def audit_count(owner, action: str) -> int:
    with owner.connect() as current:
        return current.execute(
            text('SELECT count(*) FROM cafeteria.audit_events WHERE action=:action'),
            {'action': action},
        ).scalar_one()


def allergen_reviews(owner) -> int:
    with owner.connect() as current:
        return current.execute(
            text("SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE '%allergen%review%'")
        ).scalar_one()


def run_apply(engine, actor, document):
    with signed_in(engine, actor):
        return importer.apply_import(document, engine, actor, dry_run=False, write_back=IMPORT_PATH)


def test_linked_draft_import_full_pipeline(master):  # noqa: F811
    owner, engine, actor = master
    document = load_import()
    before_pub = snapshot(owner)['publication_revisions']
    before = snapshot(owner)
    summary = run_apply(engine, actor, document)
    after = snapshot(owner)
    assert summary['storage_locations'] == 3
    assert summary['foods'] == 100
    assert TARGET_STORAGE <= storage_names(engine)
    foods = masters.list_foods(engine, limit=200)
    assert len(foods) >= 100
    assert all(item.storage_locations for item in foods if item.name in {row['name'] for row in document['foods']})
    recipe_count = len(after['recipes']) - len(before['recipes'])
    assert recipe_count == 61
    imports = audit_count(owner, 'recipe.import')
    assert imports == 61
    loaded = json.loads(IMPORT_PATH.read_text(encoding='utf-8'))
    assert len(loaded['resolved']['food_keys']) == 100
    assert len(loaded['resolved']['recipe_keys']) == 61
    assert loaded['resolved']['batch_public_ids']['preparation']
    assert loaded['resolved']['batch_public_ids']['dish']
    titles = {item['title'] for item in document['dish_mappings']}
    imported_titles = {
        recipes.get_recipe(engine, recipe_id).payload['title']
        for recipe_id in loaded['resolved']['recipe_keys'].values()
    }
    assert titles <= imported_titles
    occurrences = sum(len(item['source_occurrences']) for item in document['dish_mappings'])
    assert occurrences == 76
    for recipe in document['recipes']:
        recipe_id = loaded['resolved']['recipe_keys'][recipe['key']]
        row = recipes.get_recipe(engine, recipe_id)
        expected_version = 2 if recipe['batch_group'] == 'preparation' else 1
        assert row.row_version == expected_version
        assert row.payload['source']['kind'] == 'ai_assisted'
        assert row.payload['source']['note']
        assert 'unreviewed' not in row.payload
    for batch_id in loaded['resolved']['batch_public_ids'].values():
        batch = import_store.get_batch(engine, batch_id)
        assert batch.adapter_kind == 'ai_assisted'
        assert set(batch.annotations) >= {'unreviewed', 'proposed_not_measured', 'allergen_not_checked'}
    pinned = [item for item in document['foods'] if item.get('preparation_recipe_key')]
    assert len(pinned) == 29
    for item in pinned:
        food = masters.get_food(engine, loaded['resolved']['food_keys'][item['key']])
        assert food.prepared_recipe is not None
        assert food.allergen_review_status == 'not_checked'
    assert snapshot(owner)['publication_revisions'] == before_pub
    assert allergen_reviews(owner) == 0


def test_linked_draft_import_replay_is_idempotent(master):  # noqa: F811
    owner, engine, actor = master
    document = load_import()
    run_apply(engine, actor, document)
    before = snapshot(owner)
    again = run_apply(engine, actor, json.loads(IMPORT_PATH.read_text(encoding='utf-8')))
    assert snapshot(owner) == before
    assert all(item['status'] == 'skipped' for item in again['batches'])


def test_linked_draft_import_invalid_row_rolls_back_batch(master):  # noqa: F811
    from cafeteria.master_data_types import ObjectExpectation
    from cafeteria.recipe_types import RecipeValidationError

    owner, engine, actor = master
    document = load_import()
    prep = [item for item in document['recipes'] if item['batch_group'] == 'preparation'][:1]
    isolated = json.loads(json.dumps(document))
    isolated['resolved'] = {'storage_keys': {}, 'food_keys': {}, 'recipe_keys': {}, 'batch_public_ids': {}}
    with signed_in(engine, actor):
        importer.ensure_storage(engine, actor, isolated)
        food_ids = importer.ensure_foods(engine, actor, isolated, isolated['resolved']['storage_keys'])
        location = recipes.get_location(engine)
        rows = []
        for index, recipe in enumerate(prep, start=1):
            payload = importer.resolve_payload(
                recipe['recipe_payload'], recipe['ingredient_food_keys'], food_ids,
            )
            rows.append({
                'row_number': index,
                'source_line': None,
                'original_payload': payload,
                'parse_errors': [],
                'candidate_payload': payload,
                'duplicate_decision': 'undecided',
                'target_recipe_public_id': None,
                'target_row_version': None,
            })
        payload = importer.batch_payload('preparation', rows, isolated['meta'])
        created = import_store.create_batch(engine, actor, payload, expected_location_id=location)
        batch = import_store.get_batch(engine, created.public_id)
        mapped = importer.mapped_rows(prep, food_ids)
        mapped[0]['candidate_payload']['ingredients'][-1]['food_public_id'] = None
        import_store.update_batch(
            engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
            {'action': 'save', 'annotations': list(isolated['meta']['annotations']), 'rows': mapped},
            expected_location_id=location,
        )
        batch = import_store.get_batch(engine, created.public_id)
        import_store.update_batch(
            engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
            {'action': 'acknowledge'}, expected_location_id=location,
        )
        batch = import_store.get_batch(engine, created.public_id)
        before = snapshot(owner)
        with pytest.raises(RecipeValidationError, match='unvollständig'):
            import_store.commit_batch(
                engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
                {'candidate_hash_sha256': batch.candidate_hash_sha256},
                expected_location_id=location,
            )
        assert snapshot(owner) == before
        assert import_store.get_batch(engine, batch.public_id).status == 'draft'
