"""DB-free validator for namespaced recipe example data.

Temporary uuid5 values exist only in memory for R1 recipe_payload checks.
They are never production public_ids and are not written back to the JSON.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))

from cafeteria.master_data_proposals import code as vocab_code, factor, plain  # noqa: E402
from cafeteria.quantities import Unit, parse_quantity  # noqa: E402
from cafeteria.recipe_values import recipe_payload  # noqa: E402
from cafeteria.recipe_snapshots import image_payload  # noqa: E402

DATASET = ROOT / 'demo' / 'recipe_examples.json'
VALIDATION_NS = UUID('8f3e2c10-0907-4d2a-9b61-6c7d8e9f0a1b')
KEY_RE = re.compile(r'^example\.(unit|category|tag|food|recipe|cookbook|week|revision)\.[A-Za-z0-9._-]+$')
SEED_UNITS = {
    'G': ('Gramm', 'mass', '1'), 'KG': ('Kilogramm', 'mass', '1000'),
    'ML': ('Milliliter', 'volume', '1'), 'L': ('Liter', 'volume', '1000'),
    'EL': ('Esslöffel (15 ml)', 'volume', '15'), 'TL': ('Teelöffel (5 ml)', 'volume', '5'),
    'STK': ('Stück', 'count', '1'), 'PORTION': ('Portion', 'contextual', None),
    'PRISE': ('Prise', 'contextual', None),
}
# Mirrors cafeteria.workflow constants; that module pulls DB credentials on import.
PROFILE_MEALS = {'patient': ('LUNCH', 'DINNER'), 'staff_guest': ('LUNCH',)}
PROFILE_DAYS = {'patient': 7, 'staff_guest': 5}
MENU_TYPES = ('MENU_1', 'VEGGIE')
WEEK_KEYS = {
    'example.week.staff_guest.2026-08-31', 'example.week.patient.2026-08-31',
}
MEAT_TAGS = frozenset({'MEAT', 'FISH'})
VEGAN_EXCLUDED = frozenset({'MEAT', 'FISH', 'DAIRY', 'EGG'})
LABEL_CODES = frozenset({'VEGETARIAN', 'VEGAN', 'LACTOSE_FREE', 'GLUTEN_FREE'})
FOOD_CREATE = {
    'name', 'category_public_id', 'base_unit_code', 'density_g_per_ml', 'piece_weight_g',
    'note', 'source_kind', 'source_reference', 'source_url', 'source_note', 'fetched_at',
}
ING_FILE = {
    'line_public_id', 'group_label', 'ingredient_text', 'food_key', 'quantity',
    'unit_code', 'note', 'source_kind', 'source_reference', 'fetched_at',
}
IMPORT_SERVICES = (
    'list_units', 'create_vocabulary', 'create_food', 'replace_food_tags', 'create_recipe',
    'freeze_revision', 'create_cookbook', 'replace_cookbook_recipes', 'persist_draft',
)


class ExampleValidationError(ValueError):
    """Invalid example dataset; contains no database details."""


def fail(message: str) -> NoReturn:
    raise ExampleValidationError(message)


def mapped(kind: str, key: str) -> str:
    return str(uuid5(VALIDATION_NS, f'{kind}:{key}'))


def as_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f'{label} muss eine Liste sein.')
    return value


def as_map(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        fail(f'{label} muss ein Objekt sein.')
    return dict(value)


def require_keys(row: Mapping[str, Any], fields: set[str], label: str) -> None:
    if set(row) != fields:
        fail(f'{label}: unerwartete oder fehlende Felder ({sorted(set(row) ^ fields)}).')


def index_rows(rows: Sequence[Any], kind: str) -> dict[str, dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = as_map(raw, kind)
        key = row.get('key')
        if not isinstance(key, str) or KEY_RE.fullmatch(key) is None or f'.{kind}.' not in f'.{key}.':
            fail(f'Ungültiger Schlüssel für {kind}: {key!r}.')
        if key in seen:
            fail(f'Doppelter Schlüssel: {key}.')
        seen[key] = row
    return seen


def tag_codes(keys: Sequence[str], tags: Mapping[str, Any]) -> set[str]:
    if any(not isinstance(key, str) or key not in tags for key in keys):
        fail('Unbekannter Tag in symbolischen Referenzen.')
    return {tags[key]['code'] for key in keys}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_units(rows: dict[str, dict[str, Any]]) -> set[str]:
    codes = {row.get('code') for row in rows.values()}
    if len(rows) != len(SEED_UNITS) or codes != set(SEED_UNITS):
        fail('Einheiten müssen genau dem Seed G/KG/ML/L/EL/TL/STK/PORTION/PRISE entsprechen.')
    for row in rows.values():
        require_keys(row, {'key', 'code', 'display_name', 'dimension', 'base_factor', 'import'}, 'unit')
        if (row['display_name'], row['dimension'], row['base_factor']) != SEED_UNITS[row['code']]:
            fail(f'Einheit {row["code"]} weicht vom Seed ab.')
        if row['import'] != 'skip_if_exists':
            fail(f'Einheit {row["code"]} darf nicht neu angelegt werden.')
        Unit(row['code'], row['dimension'], None if row['base_factor'] is None else row['base_factor'])
    return set(SEED_UNITS)


def check_vocab(rows: dict[str, dict[str, Any]], kind: str, ordered: bool) -> None:
    fields = {'key', 'code', 'name', 'import'} | ({'sort_order'} if ordered else set())
    codes: set[str] = set()
    for row in rows.values():
        require_keys(row, fields, kind)
        vocab_code(row['code'])
        plain(row['name'])
        if row['code'] in codes or row['import'] != 'create_if_missing':
            fail(f'{kind} {row["code"]} ist doppelt oder nicht additiv markiert.')
        codes.add(row['code'])
        if ordered and (type(row['sort_order']) is not int or not 1 <= row['sort_order'] <= 9999):
            fail(f'Ungültige {kind}-Reihenfolge.')


def check_foods(foods: dict[str, dict[str, Any]], categories: Mapping[str, Any],
                tags: Mapping[str, Any], units: set[str]) -> None:
    names: set[str] = set()
    for food in foods.values():
        require_keys(food, {
            'key', 'name', 'category_key', 'base_unit_code', 'density_g_per_ml', 'piece_weight_g',
            'note', 'source_kind', 'source_reference', 'source_url', 'source_note', 'fetched_at',
            'tag_keys', 'allergen_review_status', 'allergens', 'labels',
        }, 'food')
        name = plain(food['name'])
        if name is None or name in names:
            fail(f'Doppelter Zutatenname: {name}.')
        names.add(name)
        if food['category_key'] not in categories or food['base_unit_code'] not in units:
            fail(f'Zutat {food["key"]} hat unbekannte Kategorie oder Einheit.')
        factor(food['density_g_per_ml'])
        factor(food['piece_weight_g'])
        note = plain(food['note'], 500, required=False) or ''
        if food['key'] not in note or 'Beispiel' not in note:
            fail(f'Zutat {food["key"]} ist nicht als Beispiel gekennzeichnet.')
        if food['source_kind'] != 'manual' or food['fetched_at'] or food['source_url']:
            fail(f'Zutat {food["key"]} hat keine manuelle Beispielherkunft.')
        if food['allergen_review_status'] != 'not_checked' or food['allergens'] or food['labels']:
            fail(f'Zutat {food["key"]} darf keine geprüften Allergene oder Labels tragen.')
        if any(tag not in tags for tag in food['tag_keys']):
            fail(f'Zutat {food["key"]} verweist auf einen unbekannten Tag.')
        if not FOOD_CREATE <= ({*food, 'category_public_id'}):
            fail(f'create_food-Felder für {food["key"]} fehlen.')


def check_image(image: Mapping[str, Any] | None, title: str, components: Sequence[str]) -> None:
    if image is None:
        return
    require_keys(image, {
        'status', 'reason', 'title', 'components', 'file', 'sha256', 'usage_notice',
    }, 'matched_menu_image')
    if image['status'] != 'absent_from_recipe_assets':
        fail('Menübilder dürfen nicht als recipe_assets gelten.')
    if image['title'] != title or list(image['components']) != list(components):
        fail('Menübild muss Titel und Komponenten des Rezepts treffen.')
    raw_path = image['file']
    if not isinstance(raw_path, str):
        fail('Menübildpfad muss relativ im Bildkatalog liegen.')
    relative = Path(raw_path)
    asset_root = (ROOT / 'design' / 'menu-images').resolve()
    if relative.is_absolute() or '..' in relative.parts or '\\' in raw_path:
        fail('Menübildpfad muss relativ im Bildkatalog liegen.')
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(asset_root):
        fail('Menübildpfad liegt ausserhalb des Bildkatalogs.')
    catalog = json.loads((asset_root / 'manifest.json').read_text(encoding='utf-8'))
    matches = [row for row in catalog['images'] if row.get('status') == 'ready'
               and row.get('title') == title and row.get('components') == list(components)]
    if len(matches) != 1 or any(image[field] != matches[0].get(field) for field in ('file', 'sha256')):
        fail('Menübild stimmt nicht mit dem originalen Bildkatalog überein.')
    if image['usage_notice'] != catalog['usage_notice']:
        fail('Menübild muss den originalen Nutzungshinweis bewahren.')
    if not path.is_file() or file_sha256(path) != image['sha256']:
        fail(f'Menübild fehlt oder SHA-256 stimmt nicht: {image["file"]}.')
    mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}.get(path.suffix.lower())
    if mime is None:
        fail('Menübild muss PNG oder JPEG sein.')
    image_payload(path.read_bytes(), mime)
    notice = str(image['usage_notice']).lower()
    if 'ki' not in notice or 'kein beleg' not in notice:
        fail('Menübild braucht den vorhandenen Herkunftshinweis.')


def r1_payload(recipe: Mapping[str, Any], foods: Mapping[str, Any],
               tags: Mapping[str, Any], units: set[str]) -> dict[str, Any]:
    payload = as_map(recipe['payload'], 'recipe payload')
    require_keys(payload, {
        'title', 'description', 'servings', 'servings_unit_code', 'prep_minutes',
        'cook_minutes', 'source', 'ingredients', 'steps', 'images',
    }, 'recipe payload')
    if payload['servings_unit_code'] not in units:
        fail(f'Unbekannte Ausbeute-Einheit in {recipe["key"]}.')
    parse_quantity(payload['servings'])
    source = as_map(payload['source'], 'source')
    if source.get('kind') != 'manual' or source.get('url') or source.get('fetched_at'):
        fail(f'Rezept {recipe["key"]} braucht kind=manual ohne URL/fetched_at.')
    if recipe['key'] not in str(source.get('note') or '') or 'Beispiel' not in str(source.get('note') or ''):
        fail(f'Rezept {recipe["key"]} ist nicht als Beispiel gekennzeichnet.')
    if payload['images'] != []:
        fail(f'Rezept {recipe["key"]} darf keine recipe_images beanspruchen.')
    ingredients = []
    food_codes: set[str] = set()
    for item in as_list(payload['ingredients'], 'ingredients'):
        row = as_map(item, 'ingredient')
        require_keys(row, ING_FILE, 'ingredient')
        if row['food_key'] not in foods or row['unit_code'] not in units:
            fail(f'Unbekannte Zutat oder Einheit in {recipe["key"]}.')
        food_codes |= tag_codes(foods[row['food_key']]['tag_keys'], tags)
        canonical = {key: row[key] for key in ING_FILE if key != 'food_key'}
        canonical['food_public_id'] = mapped('food', row['food_key'])
        ingredients.append(canonical)
    recipe_codes = tag_codes(as_list(recipe['tag_keys'], 'recipe tags'), tags)
    if 'VEGAN' in recipe_codes and food_codes & VEGAN_EXCLUDED:
        fail(f'Rezept {recipe["key"]} ist vegan, enthält aber {sorted(food_codes & VEGAN_EXCLUDED)}.')
    if 'VEG' in recipe_codes and food_codes & MEAT_TAGS:
        fail(f'Rezept {recipe["key"]} ist vegetarisch, enthält aber Fleisch oder Fisch.')
    if 'MEAT' in recipe_codes and not food_codes & MEAT_TAGS:
        fail(f'Rezept {recipe["key"]} ist als Fleischgericht markiert, ohne Fleisch/Fisch-Zutat.')
    return recipe_payload({
        **payload, 'ingredients': ingredients,
        'tag_public_ids': [mapped('tag', key) for key in recipe['tag_keys']], 'images': [],
    })
