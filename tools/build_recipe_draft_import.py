#!/usr/bin/env python3
"""Translate linked recipe drafts to import format and apply via Foundations + import batches."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / 'reference_scaffold'
DRAFT_PATH = ROOT / 'demo' / 'linked_recipe_drafts.json'
IMPORT_PATH = ROOT / 'demo' / 'linked_recipe_drafts_import.json'
ANNOTATIONS = ('unreviewed', 'proposed_not_measured', 'allergen_not_checked')
FETCHED_AT = '2026-09-08T21:51:49+00:00'
STORAGE_CODES: dict[str, tuple[str, str, int]] = {
    'proposed.storage.trockenlager': ('TROCKEN', 'Trockenlager', 1),
    'proposed.storage.kuehlraum': ('KUEHL', 'Kühlraum', 2),
    'proposed.storage.tiefkuehler': ('TIEFKHL', 'Tiefkühler', 3),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_draft(path: Path = DRAFT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def food_name(foods: dict[str, dict[str, Any]], key: str) -> str:
    return str(foods[key]['name'])


def preparation_deps(recipes: list[dict[str, Any]], foods: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    food_to_prep = {
        key: value.get('preparation_recipe_key')
        for key, value in foods.items()
        if value.get('preparation_recipe_key')
    }
    deps: dict[str, set[str]] = {}
    for recipe in recipes:
        if recipe['role'] != 'preparation':
            continue
        needed: set[str] = set()
        for ingredient in recipe['ingredients']:
            prep = food_to_prep.get(ingredient['food_key'])
            if prep and prep != recipe['key']:
                needed.add(prep)
        deps[recipe['key']] = needed
    return deps


def bottom_up_order(recipes: list[dict[str, Any]], foods: dict[str, dict[str, Any]]) -> list[str]:
    deps = preparation_deps(recipes, foods)
    remaining = {recipe['key'] for recipe in recipes if recipe['role'] == 'preparation'}
    ordered: list[str] = []
    while remaining:
        ready = sorted(key for key in remaining if not (deps[key] & remaining))
        if not ready:
            raise ValueError('Zyklus in Vorbereitungsrezepten.')
        ordered.extend(ready)
        remaining -= set(ready)
    ordered.extend(recipe['key'] for recipe in recipes if recipe['role'] == 'dish')
    return ordered


def build_source_note(*parts: str | None) -> str:
    return ' '.join(part.strip() for part in parts if part and part.strip())


def recipe_payload(recipe: dict[str, Any], foods: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    source = recipe.get('source') or {}
    note = build_source_note(
        source.get('note'),
        'Ausbeute proposed_not_measured.',
        'Allergene not_checked.',
        'Status unreviewed.',
    )
    ingredient_keys: list[str] = []
    ingredients: list[dict[str, Any]] = []
    for ingredient in recipe['ingredients']:
        key = ingredient['food_key']
        ingredient_keys.append(key)
        ingredients.append({
            'line_public_id': None,
            'group_label': None,
            'ingredient_text': food_name(foods, key),
            'food_public_id': None,
            'quantity': ingredient['quantity'],
            'unit_code': ingredient['unit_code'],
            'note': ingredient.get('menu_side_text'),
            'source_kind': 'ai_assisted',
            'source_reference': f"draft:{recipe['key']}",
            'fetched_at': FETCHED_AT,
        })
    steps = [
        {'instruction': step, 'duration_minutes': None, 'image_sha256': None}
        for step in recipe.get('steps') or []
    ]
    payload = {
        'title': recipe['title'],
        'description': None,
        'servings': recipe['yield_quantity'],
        'servings_unit_code': recipe['yield_unit_code'],
        'prep_minutes': None,
        'cook_minutes': None,
        'source': {
            'kind': 'ai_assisted',
            'reference': f"draft:{recipe['key']}",
            'url': None,
            'note': note,
            'fetched_at': FETCHED_AT,
        },
        'ingredients': ingredients,
        'steps': steps,
        'tag_public_ids': [],
        'images': [],
    }
    return payload, ingredient_keys


def translate_draft(draft: dict[str, Any], *, draft_path: Path = DRAFT_PATH) -> dict[str, Any]:
    foods = {item['key']: item for item in draft['foods']}
    order = bottom_up_order(draft['recipes'], foods)
    by_key = {recipe['key']: recipe for recipe in draft['recipes']}
    storage_locations = []
    for proposal in draft['storage_proposals']:
        code, name, sort_order = STORAGE_CODES[proposal['key']]
        storage_locations.append({
            'key': proposal['key'],
            'name': name,
            'code': code,
            'sort_order': sort_order,
            'status': proposal.get('status', 'proposed'),
            'editable': proposal.get('editable', True),
            'note': 'proposed_editable',
        })
    food_rows = []
    for item in draft['foods']:
        source = item.get('source') or {}
        food_rows.append({
            'key': item['key'],
            'name': item['name'],
            'base_unit_code': item['base_unit_code'],
            'storage_keys': list(item['storage_keys']),
            'storage_status': item.get('storage_status', 'proposed_editable'),
            'preparation_recipe_key': item.get('preparation_recipe_key'),
            'source': {
                'kind': source.get('kind', 'ai_assisted'),
                'note': build_source_note(source.get('note'), 'Lager proposed_editable.'),
            },
            'review_status': item.get('review_status', 'unreviewed'),
            'allergen_review_status': item.get('allergen_review_status', 'not_checked'),
        })
    recipe_rows = []
    for key in order:
        recipe = by_key[key]
        payload, ingredient_keys = recipe_payload(recipe, foods)
        recipe_rows.append({
            'key': key,
            'role': recipe['role'],
            'batch_group': 'preparation' if recipe['role'] == 'preparation' else 'dish',
            'title': recipe['title'],
            'ingredient_food_keys': ingredient_keys,
            'recipe_payload': payload,
        })
    return {
        'meta': {
            'kind': 'linked_recipe_drafts_import',
            'format_version': 1,
            'source_draft_path': str(draft_path.relative_to(ROOT)),
            'source_draft_sha256': sha256_file(draft_path),
            'created_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            'annotations': list(ANNOTATIONS),
            'adapter_kind': 'ai_assisted',
            'source_note': (
                'Gerichtsdatenentwurf linked_recipe_drafts.json; unreviewed, '
                'proposed_not_measured, allergen_not_checked.'
            ),
        },
        'storage_locations': storage_locations,
        'foods': food_rows,
        'recipes': recipe_rows,
        'dish_mappings': draft['dish_mappings'],
        'resolved': {
            'storage_keys': {},
            'food_keys': {},
            'recipe_keys': {},
            'batch_public_ids': {},
        },
    }


def write_import(document: dict[str, Any], path: Path = IMPORT_PATH) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


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
            return {'status': 'skipped', 'public_id': existing, 'imported': loaded.imported_result}
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
        return {'status': 'conflict', 'group': group, 'message': str(error)}
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
        return {'status': 'conflict', 'group': group, 'message': str(error)}
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
    document: dict[str, Any], engine: Any, actor: Any, *, dry_run: bool = False, write_back: Path | None = IMPORT_PATH,
) -> dict[str, Any]:
    scaffold_import()
    from cafeteria import recipe_store as recipes  # type: ignore[import-not-found]

    location = recipes.get_location(engine)
    storage_ids = ensure_storage(engine, actor, document) if not dry_run else {}
    food_ids = ensure_foods(engine, actor, document, storage_ids) if not dry_run else {}
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
    meta = document['meta']
    summary: dict[str, Any] = {
        'storage_locations': len(storage_ids),
        'foods': len(food_ids),
        'batches': [],
        'prepared_pins': [],
    }
    for group in ('preparation', 'dish'):
        group_recipes = [item for item in document['recipes'] if item['batch_group'] == group]
        summary['batches'].append(commit_group(
            engine, actor, location, group, group_recipes, food_ids, meta, document, dry_run=False,
        ))
    summary['prepared_pins'] = pin_prepared_foods(engine, actor, location, document, dry_run=False)
    if write_back is not None:
        write_import(document, write_back)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', type=Path, default=DRAFT_PATH)
    parser.add_argument('--output', type=Path, default=IMPORT_PATH)
    parser.add_argument('--translate', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--database-url', default=None)
    args = parser.parse_args()
    if args.translate or (not args.apply and not args.dry_run):
        draft = load_draft(args.draft)
        document = translate_draft(draft, draft_path=args.draft)
        write_import(document, args.output)
        print(json.dumps({'translated': str(args.output), 'foods': len(document['foods']),
                          'recipes': len(document['recipes'])}, ensure_ascii=False))
    if args.apply or args.dry_run:
        document = json.loads(args.output.read_text(encoding='utf-8'))
        if args.dry_run and not args.apply:
            print(json.dumps(apply_import(document, None, None, dry_run=True), ensure_ascii=False, indent=2))
            return 0
        database_url = args.database_url or __import__('os').environ.get('DATABASE_URL')
        if not database_url:
            print('DATABASE_URL oder --database-url erforderlich.', file=sys.stderr)
            return 2
        scaffold_import()
        from sqlalchemy import create_engine
        from cafeteria import db as database  # type: ignore[import-not-found]

        engine = create_engine(database_url, future=True)
        database.run_migrations(engine, database.SCHEMA)
        actor_module = __import__('test_master_data_db', fromlist=['make_actor'])
        actor = actor_module.make_actor(engine, 'Cafeteria.Admin')
        with actor_module.signed_in(engine, actor):
            summary = apply_import(document, engine, actor, dry_run=args.dry_run, write_back=args.output)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
