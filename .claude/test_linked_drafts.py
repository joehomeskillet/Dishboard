"""Private mutation probes for the symbolic review dataset; entirely offline."""
from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from validate_linked_drafts import DATA, validate


def dataset() -> dict[str, Any]:
    return json.loads(DATA.read_text())


def test_complete_dataset() -> None:
    assert validate(dataset()) == {'exact_titles': 32, 'occurrences': 76, 'source_components': 37,
                                  'existing_units': 9, 'foods': 100, 'recipes': 61,
                                  'preparations': 29, 'legacy_recipes': 18, 'new_dishes': 14}


@pytest.mark.parametrize('quantity', [1.25, True, 'NaN', '-1', '0', '0.0000001', '1000000000000', '1e2'])
def test_invalid_decimal_quantities(quantity: Any) -> None:
    data = dataset()
    data['recipes'][0]['ingredients'][0]['quantity'] = quantity
    with pytest.raises(ValueError, match='decimal-string|quantity-boundary'):
        validate(data)


@pytest.mark.parametrize('fault,expected', [
    ('food', 'ingredient-food-missing'), ('unit', 'ingredient-unit'),
    ('storage', 'food-storage'), ('empty-storage', 'food-storage'),
    ('recipe', 'prepared-recipe-missing'), ('portion', 'prepared-unit-incompatible'),
    ('mass-volume', 'ingredient-unit-incompatible'), ('self-cycle', 'recipe-cycle'),
    ('indirect-cycle', 'recipe-cycle'), ('title', 'title-coverage'),
    ('profile', 'occurrence-source-exact'), ('side', 'side-exactly-once'),
    ('duplicate-side', 'side-double-count'), ('duplicate-food', 'side-food-double-count'),
    ('vegan', 'vegan-animal-ingredient'), ('vegetarian', 'vegetarian-meat-ingredient'),
    ('approved', 'allergen-approval'), ('legacy', 'legacy-retained-quantity'),
    ('units-catalog', 'unit-code-coverage'), ('runtime', 'not-runtime-import'),
])
def test_invalid_links_and_claims(fault: str, expected: str) -> None:
    data = dataset()
    foods = {f['key']: f for f in data['foods']}
    recipes = {r['key']: r for r in data['recipes']}
    first = data['recipes'][0]
    falafel = recipes['draft.recipe.falafel-teller']
    if fault == 'food':
        first['ingredients'][0]['food_key'] = 'draft.food.absent'
    elif fault == 'unit':
        first['ingredients'][0]['unit_code'] = 'CUP'
    elif fault == 'storage':
        data['foods'][0]['storage_keys'] = ['proposed.storage.absent']
    elif fault == 'empty-storage':
        data['foods'][0]['storage_keys'] = []
    elif fault == 'recipe':
        foods['draft.food.hummus']['preparation_recipe_key'] = 'draft.recipe.absent'
    elif fault == 'portion':
        recipes['draft.recipe.hummus']['yield_unit_code'] = 'PORTION'
    elif fault == 'mass-volume':
        first['ingredients'][0]['unit_code'] = 'ML'
    elif fault == 'self-cycle':
        recipes['draft.recipe.hummus']['ingredients'][0]['food_key'] = 'draft.food.hummus'
    elif fault == 'indirect-cycle':
        recipes['draft.recipe.kichererbsen-gekocht']['ingredients'][0]['food_key'] = 'draft.food.hummus'
    elif fault == 'title':
        data['dish_mappings'].pop()
    elif fault == 'profile':
        data['dish_mappings'][0]['source_occurrences'][0]['profile'] = 'staff_guest'
    elif fault == 'side':
        data['dish_mappings'][0]['source_occurrences'][0]['components'][0]['text'] = 'Ersatzbeilage'
    elif fault == 'duplicate-side':
        falafel['ingredients'].append(copy.deepcopy(falafel['ingredients'][-1]))
    elif fault == 'duplicate-food':
        row = copy.deepcopy(falafel['ingredients'][-1])
        del row['menu_side_text']
        falafel['ingredients'].append(row)
    elif fault == 'vegan':
        recipes['draft.recipe.hummus']['ingredients'].append({'food_key': 'draft.food.milch', 'quantity': '100', 'unit_code': 'ML'})
    elif fault == 'vegetarian':
        recipes['draft.recipe.gemuese-toast']['ingredients'].append({'food_key': 'draft.food.schinken', 'quantity': '100', 'unit_code': 'G'})
    elif fault == 'approved':
        first['allergen_review_status'] = 'checked'
    elif fault == 'legacy':
        recipes['draft.recipe.pouletbrust-kraeuter']['ingredients'][0]['quantity'] = '999'
    elif fault == 'units-catalog':
        data['existing_unit_codes'][0] = 'CUP'
    elif fault == 'runtime':
        data['meta']['runtime_import_format'] = True
    with pytest.raises(ValueError, match=expected):
        validate(data)


def test_all_legacy_quantities_are_preserved_or_explicitly_replaced() -> None:
    data = dataset()
    for recipe in data['recipes']:
        if 'legacy_example' in recipe['source']:
            assert recipe['source']['replaced_legacy_lines']
            assert recipe['source']['adaptation']
    assert validate(data)['legacy_recipes'] == 18


def test_vegan_sources_keep_their_labels() -> None:
    data = dataset()
    labels = {r['title']: r['proposed_dietary_labels'] for r in data['recipes']}
    for title in ['Kichererbsen-Curry', 'Kichererbsen-Eintopf', 'Falafel-Teller', 'Tofu-Rührei', 'Kokos-Griessbrei']:
        assert 'VEGAN' in labels[title]
    assert validate(data)['exact_titles'] == 32
