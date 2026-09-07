from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'reference_scaffold'))

from validate_recipe_examples import (  # noqa: E402
    DATASET, VALIDATION_NS, ExampleValidationError, validate,
)
import recipe_example_validation as validation  # noqa: E402

SNAPSHOTS = (
    ROOT / 'demo' / 'snapshots' / 'cafeteria_kw36.json',
    ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json',
)


def load() -> dict:
    return json.loads(DATASET.read_text(encoding='utf-8'))


def test_full_dataset_validates_with_real_parsers() -> None:
    result = validate(DATASET)
    assert result['ok'] is True
    assert result['imported'] is False
    assert result['published'] is False
    assert result['validation_uuid_namespace'] == str(VALIDATION_NS)
    assert result['validation_uuids'] == 'in-memory only; not production public_ids'
    counts = result['counts']
    assert 12 <= counts['recipes'] <= 18
    assert counts['cookbooks'] >= 3
    assert counts['weekly_drafts'] == 2
    assert counts['menu_recipe_intents'] == 38
    assert counts['foods'] >= 1
    assert counts['units'] == 9


def test_validation_only_uuids_are_absent_from_source() -> None:
    text = DATASET.read_text(encoding='utf-8')
    data = json.loads(text)
    assert str(VALIDATION_NS) == data['meta']['validation_uuid_namespace']
    blob = json.dumps({key: value for key, value in data.items() if key != 'meta'})
    assert str(VALIDATION_NS) not in blob
    assert '8f3e2c10' not in blob


def test_existing_snapshots_remain_schema2_and_separate() -> None:
    cafeteria = json.loads(SNAPSHOTS[0].read_text(encoding='utf-8'))
    patient = json.loads(SNAPSHOTS[1].read_text(encoding='utf-8'))
    assert cafeteria['profile_code'] == 'staff_guest'
    assert patient['profile_code'] == 'patient'
    assert cafeteria['schema_version'] == patient['schema_version'] == 2
    assert cafeteria['revision_id'] == 'CAF-2026-KW36-R1'
    assert patient['revision_id'] == 'PAT-2026-KW36-R1'


def test_every_open_menu_item_resolves_to_a_recipe() -> None:
    data = load()
    recipes = {row['key']: row for row in data['recipes']}
    intents = {(
        row['profile_code'], row['date'], row['meal_code'], row['type_code'],
    ): row['recipe_key'] for row in data['menu_recipe_intents']}
    for week in data['weekly_drafts']:
        assert week['status'] == 'DRAFT'
        assert week['publication'] == 'not_requested'
        for day in week['values']['days']:
            for service in day['services']:
                if service['service_state'] != 'open':
                    continue
                for option in service['options']:
                    key = intents[(week['profile_code'], day['date'], service['meal_code'], option['type_code'])]
                    recipe = recipes[key]
                    assert option['title'] == recipe['payload']['title']
                    assert option['components'] == recipe['menu_components']


def test_recipe_payloads_have_empty_images_and_manual_source() -> None:
    for recipe in load()['recipes']:
        payload = recipe['payload']
        assert payload['images'] == []
        assert payload['source']['kind'] == 'manual'
        assert payload['source']['url'] is None
        assert payload['source']['fetched_at'] is None
        assert recipe['key'] in payload['source']['note']


def test_foods_are_unreviewed_and_namespaced() -> None:
    for food in load()['foods']:
        assert food['allergen_review_status'] == 'not_checked'
        assert food['allergens'] == []
        assert food['labels'] == []
        assert food['source_kind'] == 'manual'
        assert food['key'] in food['note']


def test_cookbooks_have_explicit_unique_order() -> None:
    data = load()
    recipe_keys = {row['key'] for row in data['recipes']}
    assert len(data['cookbooks']) >= 3
    for book in data['cookbooks']:
        assert book['name'].startswith('Beispiel:')
        assert book['key'] in book['description']
        assert book['recipe_keys']
        assert len(book['recipe_keys']) == len(set(book['recipe_keys']))
        assert set(book['recipe_keys']) <= recipe_keys


def test_no_r5_binding_is_claimed() -> None:
    data = load()
    for intent in data['menu_recipe_intents']:
        assert intent['binding'] == 'intent_only_r5_unavailable'
    assert any(gap['id'] == 'r5-menu-binding' for gap in data['unresolved_gaps'])
    mapping = data['import_mapping']
    assert 'persist_draft' in mapping
    assert 'create_recipe' in mapping
    assert 'recipe_import_batches' in mapping['not_called']


def test_duplicate_key_is_rejected(tmp_path: Path) -> None:
    data = load()
    data['foods'].append(deepcopy(data['foods'][0]))
    path = tmp_path / 'dup.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ExampleValidationError, match='Doppelter Schlüssel'):
        validate(path)


def test_vegan_recipe_with_meat_is_rejected(tmp_path: Path) -> None:
    data = load()
    vegan = next(row for row in data['recipes'] if 'example.tag.VEGAN' in row['tag_keys'])
    meat = next(
        row['key'] for row in data['foods'] if 'example.tag.MEAT' in row['tag_keys']
    )
    vegan['payload']['ingredients'][0]['food_key'] = meat
    path = tmp_path / 'vegan-meat.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ExampleValidationError, match='vegan'):
        validate(path)


def test_invalid_quantity_uses_r1_parser(tmp_path: Path) -> None:
    data = load()
    data['recipes'][0]['payload']['ingredients'][0]['quantity'] = '1.0000001'
    path = tmp_path / 'qty.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(Exception, match='Nachkommastellen|Menge'):
        validate(path)


def test_closed_cafeteria_weekend_needs_notice() -> None:
    data = load()
    cafeteria = next(row for row in data['weekly_drafts'] if row['profile_code'] == 'staff_guest')
    weekend = [day for day in cafeteria['values']['days'] if day['date'] >= '2026-09-05']
    assert len(weekend) == 2
    for day in weekend:
        service = day['services'][0]
        assert service['service_state'] == 'closed'
        assert service['notice'].strip()


def test_python_modules_stay_under_hard_limit() -> None:
    validator = (ROOT / 'tools' / 'validate_recipe_examples.py').read_text(encoding='utf-8')
    tests = Path(__file__).read_text(encoding='utf-8')
    assert validator.count('\n') < 600
    assert tests.count('\n') < 400


@pytest.mark.parametrize('kind', ['revision', 'unit', 'tag', 'image_catalog', 'image_absolute'])
def test_invalid_reference_contracts_are_rejected(tmp_path: Path, kind: str) -> None:
    data = load()
    if kind == 'revision':
        duplicate = deepcopy(data['recipe_revision_intents'][0])
        duplicate['key'] += '.duplicate'
        data['recipe_revision_intents'].append(duplicate)
    elif kind == 'unit':
        duplicate = deepcopy(data['units'][0])
        duplicate['key'] += '.duplicate'
        data['units'].append(duplicate)
    elif kind == 'tag':
        data['recipes'][0]['tag_keys'].append('example.tag.UNKNOWN')
    elif kind == 'image_catalog':
        image = data['recipes'][0]['matched_menu_image']
        other = data['recipes'][1]['matched_menu_image']
        image['file'], image['sha256'] = other['file'], other['sha256']
    else:
        image = data['recipes'][0]['matched_menu_image']
        image['file'] = str(ROOT / image['file'])
    path = tmp_path / 'invalid-reference.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ExampleValidationError):
        validate(path)


@pytest.mark.parametrize('path', ['../menu.jpg', 'design/menu-images/../menu.jpg',
                                  'https://example.invalid/menu.jpg', 'design\\menu.jpg'])
def test_image_path_rejected_before_any_image_read(monkeypatch, path: str) -> None:
    recipe = load()['recipes'][0]
    image = recipe['matched_menu_image'] | {'file': path}
    monkeypatch.setattr(validation, 'file_sha256', lambda _: pytest.fail('unexpected image read'))
    with pytest.raises(ExampleValidationError, match='pfad'):
        validation.check_image(image, recipe['payload']['title'], recipe['menu_components'])


def test_image_symlink_must_stay_inside_asset_root(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / 'design' / 'menu-images'
    root.mkdir(parents=True)
    outside = tmp_path / 'outside.jpg'
    outside.write_bytes(b'local fixture')
    (root / 'menu.jpg').symlink_to(outside)
    monkeypatch.setattr(validation, 'ROOT', tmp_path)
    recipe = load()['recipes'][0]
    image = recipe['matched_menu_image'] | {'file': 'design/menu-images/menu.jpg'}
    with pytest.raises(ExampleValidationError, match='ausserhalb'):
        validation.check_image(image, recipe['payload']['title'], recipe['menu_components'])


def test_original_catalog_hash_and_usage_notice_are_binding() -> None:
    recipe = load()['recipes'][0]
    for changes in ({'sha256': '0' * 64}, {'usage_notice': 'KI; kein Beleg; veränderter Hinweis'}):
        with pytest.raises(ExampleValidationError):
            validation.check_image(recipe['matched_menu_image'] | changes,
                                   recipe['payload']['title'], recipe['menu_components'])


def test_corrected_ingredients_resolve_and_bread_is_measured_by_mass() -> None:
    data = load()
    foods = {row['key']: row for row in data['foods']}
    recipes = {row['key']: row['payload'] for row in data['recipes']}
    coconut = recipes['example.recipe.kokos-griessbrei']
    water = next(row for row in coconut['ingredients'] if row['food_key'] == 'example.food.wasser')
    assert water['ingredient_text'] == foods[water['food_key']]['name'] == 'Wasser'
    assert (water['quantity'], water['unit_code']) == ('900', 'ML')
    assert not any(row['food_key'] in ('example.food.gemuesebruehe', 'example.food.rapsoel') for row in coconut['ingredients'])
    assert 'Kokosmilch und Wasser' in coconut['steps'][1]['instruction']
    tofu = recipes['example.recipe.tofu-ruehrei']
    assert next(row for row in tofu['ingredients'] if row['food_key'] == 'example.food.paprikapulver')['ingredient_text'] == 'Paprikapulver'
    assert 'Paprikapulver' in tofu['steps'][2]['instruction']
    for key in ('example.recipe.kartoffelsuppe-wienerli', 'example.recipe.kartoffelsuppe-kraeuter'):
        bread = next(row for row in recipes[key]['ingredients'] if row['food_key'] == 'example.food.hausbrot')
        assert (bread['quantity'], bread['unit_code'], bread['note']) == ('1000', 'G', 'in 20 Scheiben schneiden')


def test_requested_later_images_and_draft_apply_do_not_claim_completed_import() -> None:
    data = load()
    assert len([row for row in data['recipes'] if row['matched_menu_image'] is not None]) == 18
    assert 'add_recipe_image' in data['import_mapping']
    assert 'add_recipe_image' not in data['import_mapping']['not_called']
    assert all(row['publication'] == 'not_requested' and row['status'] == 'DRAFT' for row in data['weekly_drafts'])
    assert validate()['imported'] is False
