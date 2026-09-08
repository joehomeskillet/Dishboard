"""Data-only review checks, using pure existing quantity helpers; no database imports."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
from cafeteria.quantities import QuantityError, Unit, convert, parse_quantity  # noqa: E402

CAPTURE = ROOT.parent / 'sdd-bindings-root-0908/.claude/live-dish-source-0908.json'
DATA = ROOT / 'demo/linked_recipe_drafts.json'
EXAMPLES = ROOT / 'demo/recipe_examples.json'
NUMBER = re.compile(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def positive(value: Any) -> None:
    require(isinstance(value, str) and NUMBER.fullmatch(value) is not None, 'decimal-string')
    try:
        parse_quantity(value)
    except QuantityError as error:
        raise ValueError('quantity-boundary') from error


def indexed(rows: list[dict[str, Any]], prefix: str) -> dict[str, dict[str, Any]]:
    require(isinstance(rows, list) and bool(rows), 'empty-rows')
    keys = [row['key'] for row in rows]
    require(len(set(keys)) == len(keys), 'duplicate-key')
    require(all(re.fullmatch(re.escape(prefix) + r'[a-z0-9-]+', key) is not None for key in keys), 'symbolic-key')
    return dict(zip(keys, rows, strict=True))


def check_source(row: dict[str, Any]) -> None:
    require(row['source']['kind'] == 'ai_assisted' and row['review_status'] == 'unreviewed', 'unreviewed-source')
    require(row['allergen_review_status'] == 'not_checked', 'allergen-approval')
    legacy = row['source'].get('legacy_example')
    if legacy:
        require(legacy['declared_kind'] == 'manual' and legacy['status'] == 'example_only_not_kitchen_verified', 'legacy-provenance')


def check_legacy(foods: dict[str, Any], recipes: dict[str, Any], old: dict[str, Any]) -> None:
    require(len(old['foods']) == 54 and len(old['recipes']) == 18, 'example-source-count')
    for f in old['foods']:
        new = foods[f['key'].replace('example.', 'draft.', 1)]
        require(new['source']['legacy_example']['key'] == f['key'], 'legacy-food-key')
        require(new['base_unit_code'] == f['base_unit_code'], 'legacy-food-unit')
        if f['key'] != 'example.food.kichererbsen':
            require(new['name'] == f['name'], 'legacy-food-name')
    for old_recipe in old['recipes']:
        new = recipes[old_recipe['key'].replace('example.', 'draft.', 1)]
        p = old_recipe['payload']
        require(new['title'] == p['title'] and new['yield_quantity'] == p['servings'], 'legacy-title-yield')
        require(new['source']['legacy_example']['key'] == old_recipe['key'], 'legacy-recipe-key')
        removed = new['source']['replaced_legacy_lines']
        require(len(removed) == len(set(removed)), 'legacy-disposition-duplicate')
        kept = {i['legacy_line']: i for i in new['ingredients'] if 'legacy_line' in i}
        require(set(kept).isdisjoint(removed), 'legacy-double-count')
        require(set(kept) | set(removed) == set(range(1, len(p['ingredients']) + 1)), 'legacy-line-coverage')
        for n, row in kept.items():
            original = p['ingredients'][n - 1]
            require((row['food_key'], row['quantity'], row['unit_code']) == (original['food_key'].replace('example.', 'draft.', 1), original['quantity'], original['unit_code']), 'legacy-retained-quantity')


def validate(data: dict[str, Any]) -> dict[str, int]:
    live = json.loads(CAPTURE.read_text(), parse_int=Decimal, parse_float=Decimal)
    old = json.loads(EXAMPLES.read_text())
    meta = data['meta']
    require(meta['runtime_import_format'] is False and meta['status'] == 'unreviewed_preparation_only', 'not-runtime-import')
    require(meta['capture_sha256'] == hashlib.sha256(CAPTURE.read_bytes()).hexdigest(), 'capture-hash')
    require(meta['examples_sha256'] == hashlib.sha256(EXAMPLES.read_bytes()).hexdigest(), 'examples-hash')
    require(meta['source_commit'] == live['production_commit'] and meta['source_schema_version'] == live['schema_version'], 'source-pin')
    require(set(data['existing_unit_codes']) == {u['code'] for u in live['units']} and len(data['existing_unit_codes']) == 9, 'unit-code-coverage')
    require(all(u['active'] for u in live['units']), 'inactive-foundation-unit')
    units = {u['code']: Unit(u['code'], u['dimension'], u['base_factor']) for u in live['units']}
    storages = indexed(data['storage_proposals'], 'proposed.storage.')
    require({s['name'] for s in storages.values()} == {'Trockenlager', 'Kühlraum', 'Tiefkühler'}, 'storage-proposals')
    require(all(s['status'] == 'proposed' and s['editable'] is True for s in storages.values()), 'storage-unconfirmed')
    foods = indexed(data['foods'], 'draft.food.')
    recipes = indexed(data['recipes'], 'draft.recipe.')
    require(len({r['title'] for r in recipes.values()}) == len(recipes), 'duplicate-recipe-title')
    edges: dict[str, set[str]] = {}
    for f in foods.values():
        check_source(f)
        require(f['base_unit_code'] in units, 'food-unit')
        require(bool(f['storage_keys']) and set(f['storage_keys']) <= set(storages), 'food-storage')
        require(f['storage_status'] == 'proposed_editable', 'food-storage-unconfirmed')
        require(set(f['culinary_groups']) <= {'MEAT', 'FISH', 'DAIRY', 'EGG'}, 'culinary-group')
        if 'preparation_recipe_key' in f:
            require(f['preparation_recipe_key'] in recipes, 'prepared-recipe-missing')
            p = recipes[f['preparation_recipe_key']]
            require(p['role'] == 'preparation', 'prepared-recipe-role')
            require(p['yield_unit_code'] in units, 'prepared-yield-unit')
            try:
                convert(parse_quantity('1'), units[p['yield_unit_code']], units[f['base_unit_code']])
            except QuantityError as error:
                raise ValueError('prepared-unit-incompatible') from error
    for key, r in recipes.items():
        check_source(r)
        require(r['role'] in {'dish', 'preparation'}, 'recipe-role')
        positive(r['yield_quantity'])
        require(r['yield_unit_code'] in units and r['yield_status'] == 'proposed_not_measured', 'yield-unmeasured')
        require(bool(r['ingredients']) and bool(r['steps']) and all(isinstance(s, str) and s.strip() for s in r['steps']), 'recipe-content')
        require(set(r['proposed_dietary_labels']) <= {'VEGETARIAN', 'VEGAN'}, 'dietary-approval')
        edges[key] = set()
        for i in r['ingredients']:
            positive(i['quantity'])
            require(i['food_key'] in foods, 'ingredient-food-missing')
            require(i['unit_code'] in units, 'ingredient-unit')
            f = foods[i['food_key']]
            try:
                convert(parse_quantity(i['quantity']), units[i['unit_code']], units[f['base_unit_code']])
            except QuantityError as error:
                raise ValueError('ingredient-unit-incompatible') from error
            if 'preparation_recipe_key' in f:
                edges[key].add(f['preparation_recipe_key'])
        side_rows = [i['menu_side_text'] for i in r['ingredients'] if 'menu_side_text' in i]
        require(len(side_rows) == len(set(side_rows)), 'side-double-count')
    visiting: set[str] = set()
    done: dict[str, set[str]] = {}

    def groups(key: str) -> set[str]:
        require(key not in visiting, 'recipe-cycle')
        if key in done:
            return done[key]
        visiting.add(key)
        result = {g for i in recipes[key]['ingredients'] for g in foods[i['food_key']]['culinary_groups']}
        for dependency in edges[key]:
            result |= groups(dependency)
        visiting.remove(key)
        done[key] = result
        return result

    for key, r in recipes.items():
        animal = groups(key)
        require('VEGAN' not in r['proposed_dietary_labels'] or not animal, 'vegan-animal-ingredient')
        require('VEGETARIAN' not in r['proposed_dietary_labels'] or not animal & {'MEAT', 'FISH'}, 'vegetarian-meat-ingredient')
    titles = {m['title'] for m in live['menus']}
    mappings = data['dish_mappings']
    require(len(titles) == len(mappings) == 32 and {m['title'] for m in mappings} == titles, 'title-coverage')
    require({r['title'] for r in recipes.values() if r['role'] == 'dish'} == titles, 'dish-title-coverage')
    require(data['source_components'] == live['components'] and len(live['components']) == 37, 'component-source-exact')
    actual_occurrences = []
    label_sources: dict[str, set[str]] = {}
    for pin in meta['snapshot_sources']:
        path = ROOT / pin['file']
        require(path in {ROOT / 'demo/snapshots/cafeteria_kw36.json', ROOT / 'demo/snapshots/patienten_kw36.json'}, 'snapshot-path')
        require(pin['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest(), 'snapshot-hash')
        for day in json.loads(path.read_text())['days']:
            for service in day['services']:
                for option in service['options']:
                    label_sources.setdefault(option['title'], set()).update(x['code'] for x in option['labels'])
    for m in mappings:
        require(m['recipe_key'] in recipes and recipes[m['recipe_key']]['title'] == m['title'], 'title-recipe-mismatch')
        r = recipes[m['recipe_key']]
        require(set(r['proposed_dietary_labels']) == label_sources[m['title']] & {'VEGETARIAN', 'VEGAN'}, 'source-culinary-label')
        side_rows = [i for i in r['ingredients'] if 'menu_side_text' in i]
        for occurrence in m['source_occurrences']:
            components = occurrence['components']
            require([(i['menu_side_text'], i['food_key']) for i in side_rows] == [(c['text'], c['food_key']) for c in components], 'side-exactly-once')
            for c in components:
                require(sum(i['food_key'] == c['food_key'] for i in r['ingredients']) == 1, 'side-food-double-count')
            actual_occurrences.append((occurrence['menu_public_id'], m['title'], occurrence['profile'], occurrence['location_public_id'], tuple((c['text'], c['component_id']) for c in components)))
    expected_occurrences = [(m['public_id'], m['title'], m['profile'], m['location_public_id'], tuple((c['text'], c['component_id']) for c in m['components'])) for m in live['menus']]
    require(len(actual_occurrences) == 76 and Counter(actual_occurrences) == Counter(expected_occurrences), 'occurrence-source-exact')
    check_legacy(foods, recipes, old)
    return {'exact_titles': 32, 'occurrences': 76, 'source_components': 37, 'existing_units': 9, 'foods': len(foods), 'recipes': len(recipes), 'preparations': sum(r['role'] == 'preparation' for r in recipes.values()), 'legacy_recipes': 18, 'new_dishes': 14}


if __name__ == '__main__':
    print('DATA VALIDATION PASS: ' + json.dumps(validate(json.loads(DATA.read_text())), sort_keys=True))
