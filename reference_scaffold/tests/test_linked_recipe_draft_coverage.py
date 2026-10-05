"""Coverage of recorded week dishes against the frozen linked recipe draft."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from linked_recipe_draft_coverage import DRAFT, SNAPSHOTS, build_coverage, snapshot_option_titles  # noqa: E402


def test_every_snapshot_gericht_maps_to_a_recipe_with_zutaten() -> None:
    report = build_coverage(ROOT)
    assert DRAFT.is_file()
    assert all(path.is_file() for path in SNAPSHOTS)
    draft = json.loads(DRAFT.read_text(encoding='utf-8'))
    assert draft['meta']['runtime_import_format'] is False
    assert report['runtime_import_format'] is False
    assert report['ok'] is True
    assert report['missing_titles'] == []
    assert report['empty_ingredient_recipes'] == []
    assert report['source_titles'] == report['mapped_titles']
    assert report['source_titles'] >= 1
    assert report['all_recipes'] == report['recipes_with_ingredients']
    titles = []
    for path in SNAPSHOTS:
        titles.extend(snapshot_option_titles(json.loads(path.read_text(encoding='utf-8'))))
    unique = list(dict.fromkeys(titles))
    assert [row['title'] for row in report['dishes']] == unique
    mapped = {row['title']: row['recipe_key'] for row in draft['dish_mappings']}
    recipes = {row['key']: row for row in draft['recipes']}
    for row in report['dishes']:
        assert mapped[row['title']] == row['recipe_key']
        ingredients = recipes[row['recipe_key']]['ingredients']
        assert ingredients and row['ingredient_count'] == len(ingredients)
        assert row['yield_status'] == 'proposed_not_measured'
        assert row['review_status'] == 'unreviewed'
        assert row['allergen_review_status'] == 'not_checked'


def test_week_heading_is_not_treated_as_a_gericht() -> None:
    cafeteria = json.loads(SNAPSHOTS[0].read_text(encoding='utf-8'))
    titles = snapshot_option_titles(cafeteria)
    assert cafeteria['title'] not in titles
    assert 'Pouletbrust an Kräutersauce' in titles
