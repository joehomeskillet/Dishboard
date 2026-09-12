"""Apply a translated linked-recipe draft via Foundations, import batches, and prepared pins."""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from build_recipe_draft_import import FETCHED_AT, SCAFFOLD, write_import

ACCEPTED_BATCH_STATUS = frozenset({'imported', 'skipped'})


class BatchImportError(RuntimeError):
    """Raised when a batch group is not imported or skipped; pins must not run."""

    def __init__(self, summary: dict[str, Any]) -> None:
        self.summary = summary
        parts: list[str] = []
        for item in failed_batches(summary):
            public_id = item.get('public_id') or '—'
            group = item.get('group') or '?'
            status = item.get('status') or '?'
            parts.append(f'{group} {public_id} status={status}')
        super().__init__('Batch-Import abgebrochen vor Pins: ' + '; '.join(parts))


def failed_batches(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in summary.get('batches', [])
        if item.get('status') not in ACCEPTED_BATCH_STATUS
    ]


def scaffold_import() -> None:
    if str(SCAFFOLD) not in sys.path:
        sys.path.insert(0, str(SCAFFOLD))


def resolve_payload(payload: dict[str, Any], ingredient_keys: list[str], food_ids: dict[str, str]) -> dict[str, Any]:
    resolved = deepcopy(payload)
    for ingredient, key in zip(resolved['ingredients'], ingredient_keys, strict=True):
        ingredient['food_public_id'] = food_ids[key]
    return resolved


def batch_payload(group: str, rows: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        'adapter_kind': meta['adapter_kind'],
        'source_filename': f"linked_recipe_drafts_import:{meta['source_draft_sha256'][:16]}:{group}",
        'source_sha256': meta['source_draft_sha256'],
        'content_type': None,
        'source_url': None,
        'source_note': meta['source_note'],
        'fetched_at': FETCHED_AT,
        'annotations': list(meta['annotations']),
        'duplicate_groups': [],
        'rows': rows,
    }


def remember_imported_batch(
    document: dict[str, Any], group: str, recipes: list[dict[str, Any]], batch: Any,
) -> dict[str, Any]:
    """Restore resolved IDs from an already imported persistent batch."""
    if len(batch.imported_result) != len(recipes):
        raise RuntimeError(f'Importstapel {batch.public_id} passt nicht zur Gruppe {group}.')
    document['resolved'].setdefault('batch_public_ids', {})[group] = batch.public_id
    recipe_ids = dict(document['resolved'].get('recipe_keys') or {})
    for recipe, result in zip(recipes, batch.imported_result, strict=True):
        recipe_ids[recipe['key']] = result['recipe_public_id']
    document['resolved']['recipe_keys'] = recipe_ids
    return {'status': 'skipped', 'public_id': batch.public_id, 'imported': batch.imported_result}


def ensure_storage(engine: Any, actor: Any, document: dict[str, Any]) -> dict[str, str]:
    from cafeteria import master_data_store as masters  # type: ignore[import-not-found]

    resolved: dict[str, str] = dict(document['resolved'].get('storage_keys') or {})
    existing = {item.name: item for item in masters.list_vocabulary(engine, 'storage_location', include_archived=True, limit=200)}
    for item in document['storage_locations']:
        key = item['key']
        if key in resolved:
            continue
        current = existing.get(item['name'])
        if current is None:
            created = masters.create_vocabulary(
                engine, 'storage_location', actor,
                code=item['code'], name=item['name'], sort_order=item['sort_order'],
            )
            resolved[key] = created.public_id
            existing[item['name']] = masters.get_vocabulary(engine, 'storage_location', created.public_id)
        else:
            resolved[key] = current.public_id
    document['resolved']['storage_keys'] = resolved
    return resolved


def ensure_foods(engine: Any, actor: Any, document: dict[str, Any], storage_ids: dict[str, str]) -> dict[str, str]:
    from cafeteria import master_data_store as masters  # type: ignore[import-not-found]

    resolved: dict[str, str] = dict(document['resolved'].get('food_keys') or {})
    for item in document['foods']:
        key = item['key']
        if key in resolved:
            continue
        matches = masters.list_foods(engine, search=item['name'], limit=20)
        current = next((row for row in matches if row.name == item['name']), None)
        storage = [storage_ids[storage_key] for storage_key in item['storage_keys']]
        note = item['source']['note']
        if current is None:
            created = masters.create_food(engine, actor, {
                'name': item['name'],
                'base_unit_code': item['base_unit_code'],
                'note': note,
                'storage_location_public_ids': storage,
            })
            resolved[key] = created.public_id
        else:
            resolved[key] = current.public_id
            if [slot.public_id for slot in current.storage_locations] != storage:
                masters.replace_food_storage_locations(
                    engine, actor,
                    __import__('cafeteria.master_data_types', fromlist=['ObjectExpectation']).ObjectExpectation(
                        current.public_id, current.row_version,
                    ),
                    storage,
                )
    document['resolved']['food_keys'] = resolved
    return resolved


def mapped_rows(recipes: list[dict[str, Any]], food_ids: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, recipe in enumerate(recipes, start=1):
        payload = resolve_payload(recipe['recipe_payload'], recipe['ingredient_food_keys'], food_ids)
        rows.append({
            'row_number': index,
            'candidate_payload': payload,
            'duplicate_decision': 'create_new',
            'target_recipe_public_id': None,
            'target_row_version': None,
        })
    return rows


def commit_group(
    engine: Any, actor: Any, location: int, group: str, recipes: list[dict[str, Any]],
    food_ids: dict[str, str], meta: dict[str, Any], document: dict[str, Any], *, dry_run: bool,
) -> dict[str, Any]:
    from cafeteria import recipe_import_store as store  # type: ignore[import-not-found]
    from cafeteria.master_data_types import ObjectExpectation  # type: ignore[import-not-found]
    from cafeteria.recipe_types import RecipeConflictError  # type: ignore[import-not-found]

    existing = document['resolved'].get('batch_public_ids', {}).get(group)
    if existing:
        loaded = store.get_batch(engine, existing)
        if loaded.status == 'imported':
            return remember_imported_batch(document, group, recipes, loaded)
    source_filename = f"linked_recipe_drafts_import:{meta['source_draft_sha256'][:16]}:{group}"
    loaded = next((
        batch for batch in store.list_batches(engine)
        if batch.status == 'imported'
        and batch.adapter_kind == meta['adapter_kind']
        and batch.source_filename == source_filename
        and batch.source_sha256 == meta['source_draft_sha256']
    ), None)
    if loaded is not None:
        return remember_imported_batch(document, group, recipes, loaded)
    batch_rows: list[dict[str, Any]] = []
    for index, recipe in enumerate(recipes, start=1):
        payload = resolve_payload(recipe['recipe_payload'], recipe['ingredient_food_keys'], food_ids)
        batch_rows.append({
            'row_number': index,
            'source_line': None,
            'original_payload': payload,
            'parse_errors': [],
            'candidate_payload': payload,
            'duplicate_decision': 'undecided',
            'target_recipe_public_id': None,
            'target_row_version': None,
        })
    payload = batch_payload(group, batch_rows, meta)
    if dry_run:
        return {'status': 'planned', 'group': group, 'rows': len(batch_rows)}
    try:
        created = store.create_batch(engine, actor, payload, expected_location_id=location)
    except RecipeConflictError as error:
        return {'status': 'conflict', 'group': group, 'public_id': None, 'message': str(error)}
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'save', 'annotations': list(meta['annotations']), 'rows': mapped_rows(recipes, food_ids)},
        expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    store.update_batch(
        engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
        {'action': 'acknowledge'}, expected_location_id=location,
    )
    batch = store.get_batch(engine, created.public_id)
    try:
        store.commit_batch(
            engine, actor, ObjectExpectation(batch.public_id, batch.row_version),
            {'candidate_hash_sha256': batch.candidate_hash_sha256},
            expected_location_id=location,
        )
    except RecipeConflictError as error:
        return {
            'status': 'conflict', 'group': group, 'public_id': batch.public_id, 'message': str(error),
        }
    loaded = store.get_batch(engine, batch.public_id)
    document['resolved'].setdefault('batch_public_ids', {})[group] = loaded.public_id
    recipe_ids = dict(document['resolved'].get('recipe_keys') or {})
    for recipe, result in zip(recipes, loaded.imported_result, strict=True):
        recipe_ids[recipe['key']] = result['recipe_public_id']
    document['resolved']['recipe_keys'] = recipe_ids
    return {'status': 'imported', 'public_id': loaded.public_id, 'imported': loaded.imported_result}


def pin_prepared_foods(engine: Any, actor: Any, location: int, document: dict[str, Any], *, dry_run: bool) -> list[str]:
    from cafeteria import master_data_store as masters  # type: ignore[import-not-found]
    from cafeteria import recipe_store as recipes  # type: ignore[import-not-found]
    from cafeteria.master_data_types import ObjectExpectation  # type: ignore[import-not-found]

    foods = {item['key']: item for item in document['foods']}
    prep_keys = [item['key'] for item in document['recipes'] if item['batch_group'] == 'preparation']
    recipe_ids = document['resolved']['recipe_keys']
    actions: list[str] = []
    for key in prep_keys:
        recipe_id = recipe_ids[key]
        foods_for_key = [food_key for food_key, food in foods.items() if food.get('preparation_recipe_key') == key]
        if foods_for_key and all(
            masters.get_food(engine, document['resolved']['food_keys'][food_key]).prepared_recipe is not None
            for food_key in foods_for_key
        ):
            actions.append(f'skipped {key}')
            continue
        row = recipes.get_recipe(engine, recipe_id)
        preview = recipes.get_dependency_preview(
            engine, ObjectExpectation(row.public_id, row.row_version), expected_location_id=location,
        )
        if not preview.complete:
            raise RuntimeError(f'Unvollständiges Vorbereitungsrezept {key}.')
        if dry_run:
            actions.append(f'freeze+pin {key}')
            continue
        frozen = recipes.freeze_revision(
            engine, actor, ObjectExpectation(row.public_id, row.row_version),
            expected_location_id=location, expected_dependency_hash=preview.dependency_hash_sha256,
        )
        for food_key, food in foods.items():
            if food.get('preparation_recipe_key') != key:
                continue
            public_id = document['resolved']['food_keys'][food_key]
            current = masters.get_food(engine, public_id)
            if current.prepared_recipe and current.prepared_recipe.revision_public_id == frozen.public_id:
                actions.append(f'kept {food_key}')
                continue
            masters.update_food(
                engine, actor, ObjectExpectation(current.public_id, current.row_version), {
                    'name': current.name,
                    'base_unit_code': current.base_unit.code,
                    'note': current.note or food['source']['note'],
                    'storage_location_public_ids': [slot.public_id for slot in current.storage_locations],
                    'prepared_recipe_revision_public_id': frozen.public_id,
                    'prepared_recipe_content_hash_sha256': frozen.content_hash_sha256,
                },
            )
            actions.append(f'pinned {food_key}')
    return actions


def apply_import(
    document: dict[str, Any], engine: Any, actor: Any, *, dry_run: bool = False,
    write_back: Path | None = None,
) -> dict[str, Any]:
    if dry_run:
        prep = [item for item in document['recipes'] if item['batch_group'] == 'preparation']
        dish = [item for item in document['recipes'] if item['batch_group'] == 'dish']
        return {
            'dry_run': True,
            'storage_locations': len(document['storage_locations']),
            'foods': len(document['foods']),
            'preparation_recipes': len(prep),
            'dish_recipes': len(dish),
            'dish_titles': len(document['dish_mappings']),
            'source_occurrences': sum(len(item['source_occurrences']) for item in document['dish_mappings']),
        }
    scaffold_import()
    from cafeteria import recipe_store as recipes  # type: ignore[import-not-found]

    location = recipes.get_location(engine)
    storage_ids = ensure_storage(engine, actor, document)
    food_ids = ensure_foods(engine, actor, document, storage_ids)
    meta = document['meta']
    summary: dict[str, Any] = {
        'storage_locations': len(storage_ids),
        'foods': len(food_ids),
        'batches': [],
        'prepared_pins': [],
    }
    for group in ('preparation', 'dish'):
        group_recipes = [item for item in document['recipes'] if item['batch_group'] == group]
        result = commit_group(
            engine, actor, location, group, group_recipes, food_ids, meta, document, dry_run=False,
        )
        summary['batches'].append(result)
        if result.get('status') not in ACCEPTED_BATCH_STATUS:
            raise BatchImportError(summary)
    summary['prepared_pins'] = pin_prepared_foods(engine, actor, location, document, dry_run=False)
    if write_back is not None:
        write_import(document, write_back)
    return summary
