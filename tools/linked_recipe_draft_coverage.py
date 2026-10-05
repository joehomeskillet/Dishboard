#!/usr/bin/env python3
"""Coverage of recorded week Gerichtstitel → draft recipes → Zutaten.

Reads the frozen draft and week snapshots. Does not rewrite them and does
not import into a database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence, TypedDict

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'demo' / 'linked_recipe_drafts.json'
SNAPSHOTS = (
    ROOT / 'demo' / 'snapshots' / 'cafeteria_kw36.json',
    ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json',
)


class DishCoverage(TypedDict):
    title: str
    recipe_key: str
    ingredient_count: int
    occurrences: int
    yield_status: str
    review_status: str
    allergen_review_status: str


class CoverageReport(TypedDict):
    runtime_import_format: bool
    source_titles: int
    mapped_titles: int
    recipes_with_ingredients: int
    all_recipes: int
    missing_titles: list[str]
    empty_ingredient_recipes: list[str]
    dishes: list[DishCoverage]
    ok: bool


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_option_titles(snapshot: Mapping[str, Any]) -> list[str]:
    """Gerichtstitel are option titles inside days/services, not the week heading."""
    titles: list[str] = []
    days = snapshot.get('days')
    if not isinstance(days, list):
        raise ValueError('Snapshot has no days list.')
    for day in days:
        if not isinstance(day, Mapping):
            raise ValueError('Snapshot day is not an object.')
        for service in day.get('services') or []:
            if not isinstance(service, Mapping):
                raise ValueError('Snapshot service is not an object.')
            for option in service.get('options') or []:
                if not isinstance(option, Mapping):
                    raise ValueError('Snapshot option is not an object.')
                title = option.get('title')
                if not isinstance(title, str) or not title.strip():
                    raise ValueError('Snapshot option is missing a title.')
                titles.append(title)
    return titles


def build_coverage(root: Path = ROOT) -> CoverageReport:
    draft_path = root / 'demo' / 'linked_recipe_drafts.json'
    snapshot_paths = (
        root / 'demo' / 'snapshots' / 'cafeteria_kw36.json',
        root / 'demo' / 'snapshots' / 'patienten_kw36.json',
    )
    draft = _load(draft_path)
    if not isinstance(draft, Mapping):
        raise ValueError('Draft is not an object.')
    meta = draft.get('meta')
    if not isinstance(meta, Mapping):
        raise ValueError('Draft meta is missing.')
    runtime = meta.get('runtime_import_format')
    if runtime is not False:
        raise ValueError('Draft is marked as a runtime import format.')

    expected_sources = meta.get('snapshot_sources')
    if not isinstance(expected_sources, list) or len(expected_sources) != 2:
        raise ValueError('Draft meta.snapshot_sources must list both week files.')
    for declared, path in zip(expected_sources, snapshot_paths, strict=True):
        if not isinstance(declared, Mapping):
            raise ValueError('snapshot_sources entry is not an object.')
        relative = declared.get('file')
        digest = declared.get('sha256')
        if relative != str(path.relative_to(root)) or digest != _sha256(path):
            raise ValueError(f'Snapshot hash mismatch for {path.name}.')

    recipes_raw = draft.get('recipes')
    mappings_raw = draft.get('dish_mappings')
    if not isinstance(recipes_raw, list) or not isinstance(mappings_raw, list):
        raise ValueError('Draft recipes or dish_mappings is not a list.')
    recipes = {row['key']: row for row in recipes_raw if isinstance(row, Mapping) and 'key' in row}
    mappings = {row['title']: row for row in mappings_raw if isinstance(row, Mapping) and 'title' in row}

    source_titles: list[str] = []
    for path in snapshot_paths:
        source_titles.extend(snapshot_option_titles(_load(path)))
    unique_titles = list(dict.fromkeys(source_titles))

    missing_titles = [title for title in unique_titles if title not in mappings]
    dishes: list[DishCoverage] = []
    empty_ingredient_recipes: list[str] = []
    for title in unique_titles:
        mapping = mappings.get(title)
        if mapping is None:
            continue
        key = mapping.get('recipe_key')
        recipe = recipes.get(key) if isinstance(key, str) else None
        ingredients = recipe.get('ingredients') if isinstance(recipe, Mapping) else None
        count = len(ingredients) if isinstance(ingredients, Sequence) and not isinstance(ingredients, (str, bytes)) else 0
        if count < 1:
            empty_ingredient_recipes.append(title)
        occurrences = mapping.get('source_occurrences')
        dishes.append({
            'title': title,
            'recipe_key': key if isinstance(key, str) else '',
            'ingredient_count': count,
            'occurrences': len(occurrences) if isinstance(occurrences, list) else 0,
            'yield_status': str(recipe.get('yield_status')) if isinstance(recipe, Mapping) else '',
            'review_status': str(recipe.get('review_status')) if isinstance(recipe, Mapping) else '',
            'allergen_review_status': str(recipe.get('allergen_review_status')) if isinstance(recipe, Mapping) else '',
        })

    all_empty = [
        str(row.get('key'))
        for row in recipes_raw
        if isinstance(row, Mapping) and not (
            isinstance(row.get('ingredients'), Sequence)
            and not isinstance(row.get('ingredients'), (str, bytes))
            and len(row['ingredients']) >= 1
        )
    ]
    empty_ingredient_recipes.extend(key for key in all_empty if key not in empty_ingredient_recipes)

    ok = (
        runtime is False
        and not missing_titles
        and not empty_ingredient_recipes
        and len(dishes) == len(unique_titles)
        and all(item['ingredient_count'] >= 1 for item in dishes)
    )
    return {
        'runtime_import_format': False,
        'source_titles': len(unique_titles),
        'mapped_titles': len(dishes),
        'recipes_with_ingredients': sum(1 for row in recipes_raw if isinstance(row, Mapping) and isinstance(row.get('ingredients'), list) and row['ingredients']),
        'all_recipes': len(recipes_raw),
        'missing_titles': missing_titles,
        'empty_ingredient_recipes': empty_ingredient_recipes,
        'dishes': dishes,
        'ok': ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Gericht → Rezept → Zutaten coverage of the frozen draft.')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--json-out', type=Path)
    args = parser.parse_args(argv)
    report = build_coverage(args.root)
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.json_out is not None:
        args.json_out.write_text(encoded, encoding='utf-8')
    sys.stdout.write(encoded)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
