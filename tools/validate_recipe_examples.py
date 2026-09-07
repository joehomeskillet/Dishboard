#!/usr/bin/env python3
"""DB-free validator for namespaced recipe example data.

Temporary uuid5 values exist only in memory for R1 recipe_payload checks.
They are never production public_ids and are not written back to the JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from recipe_example_validation import (
    DATASET, IMPORT_SERVICES, LABEL_CODES, MENU_TYPES, PROFILE_DAYS, PROFILE_MEALS,
    ROOT, VALIDATION_NS, WEEK_KEYS, ExampleValidationError, as_list, as_map,
    check_foods, check_image, check_units, check_vocab, fail, index_rows,
    r1_payload, require_keys, tag_codes,
)
from cafeteria.workflow_snapshot import build_snapshot


def check_recipes(recipes: dict[str, dict[str, Any]], foods: Mapping[str, Any],
                  tags: Mapping[str, Any], units: set[str]) -> None:
    if not 12 <= len(recipes) <= 18:
        fail('Es sind 12 bis 18 Rezepte erforderlich.')
    titles: set[str] = set()
    used_foods: set[str] = set()
    used_tags: set[str] = set()
    for recipe in recipes.values():
        require_keys(recipe, {
            'key', 'active', 'tag_keys', 'menu_components', 'image_subject',
            'matched_menu_image', 'payload',
        }, 'recipe')
        title = recipe['payload']['title']
        if title in titles or recipe['active'] is not True:
            fail(f'Rezept {recipe["key"]} ist doppelt oder inaktiv.')
        titles.add(title)
        components = as_list(recipe['menu_components'], 'menu_components')
        if any(type(item) is not str or not item.strip() for item in components):
            fail(f'Rezept {recipe["key"]} hat ungültige Menükomponenten.')
        if type(recipe['image_subject']) is not str or title not in recipe['image_subject']:
            fail(f'Bildsujet von {recipe["key"]} muss den Rezepttitel enthalten.')
        used_foods.update(item['food_key'] for item in recipe['payload']['ingredients'])
        used_tags.update(recipe['tag_keys'])
        r1_payload(recipe, foods, tags, units)
        check_image(recipe['matched_menu_image'], title, components)
    for food_key in used_foods:
        used_tags.update(foods[food_key]['tag_keys'])
    unused_foods, unused_tags = set(foods) - used_foods, set(tags) - used_tags
    if unused_foods or unused_tags:
        fail(f'Hängende Datensätze: foods={sorted(unused_foods)} tags={sorted(unused_tags)}.')


def check_cookbooks(books: dict[str, dict[str, Any]], recipes: Mapping[str, Any]) -> None:
    if len(books) < 3:
        fail('Mindestens drei Kochbücher sind erforderlich.')
    names: set[str] = set()
    for book in books.values():
        require_keys(book, {'key', 'name', 'description', 'recipe_keys'}, 'cookbook')
        if not str(book['name']).startswith('Beispiel:') or book['name'] in names:
            fail(f'Kochbuch {book["key"]} muss eindeutig als Beispiel benannt sein.')
        names.add(book['name'])
        if book['key'] not in str(book['description']):
            fail(f'Kochbuch {book["key"]} fehlt in der Beschreibung.')
        keys = as_list(book['recipe_keys'], 'cookbook recipes')
        if not keys or len(keys) != len(set(keys)) or any(key not in recipes for key in keys):
            fail(f'Kochbuch {book["key"]} hat leere, doppelte oder unbekannte Rezepte.')


def check_revisions(rows: dict[str, dict[str, Any]], recipes: Mapping[str, Any]) -> None:
    covered: set[str] = set()
    for row in rows.values():
        require_keys(row, {'key', 'recipe_key', 'action', 'note'}, 'revision')
        if row['action'] != 'freeze_revision' or row['recipe_key'] not in recipes:
            fail(f'Revisionsabsicht {row["key"]} ist ungültig.')
        if row['recipe_key'] in covered:
            fail('Jedes Rezept braucht genau eine freeze_revision-Absicht.')
        if 'Beispiel' not in str(row['note']):
            fail(f'Revision {row["key"]} ist nicht als Beispiel gekennzeichnet.')
        covered.add(row['recipe_key'])
    if covered != set(recipes):
        fail('Jedes Rezept braucht genau eine freeze_revision-Absicht.')


def check_option(profile: str, state: str, option: Mapping[str, Any]) -> None:
    required = {'type_code', 'title', 'components'}
    allowed = required | {
        'external_id', 'description', 'labels', 'allergens', 'origins', 'note', 'allergen_review_status',
    }
    if profile == 'staff_guest':
        required = required | {'internal_rappen', 'external_rappen'}
        allowed = allowed | required
    if set(option) - allowed or not required <= set(option):
        fail('Menüfelder fehlen oder sind unerwartet.')
    if option.get('allergen_review_status', 'not_checked') != 'not_checked':
        fail('Neue Beispielmenüs dürfen Allergene nicht als geprüft ausgeben.')
    if option.get('allergens') not in (None, []):
        fail('Neue Beispielmenüs dürfen keine Allergendeklaration erfinden.')
    for label in option.get('labels') or []:
        if as_map(label, 'label').get('code') not in LABEL_CODES:
            fail(f'Unbekanntes Label {label}.')
    if state != 'open':
        return
    if not str(option['title']).strip():
        fail('Offenes Menü braucht einen Titel.')
    if profile == 'staff_guest':
        internal, external = option['internal_rappen'], option['external_rappen']
        if type(internal) is not int or type(external) is not int or internal <= 0 or external < internal:
            fail('Cafeteria-Beträge sind ungültig.')


def check_week_values(profile: str, week_start: date, values: Mapping[str, Any]) -> None:
    if set(values) != {'title', 'shared_note', 'days'}:
        fail('Wochenentwurf darf nur title, shared_note, days enthalten.')
    days = as_list(values['days'], 'days')
    if len(days) not in range(PROFILE_DAYS[profile], 8):
        fail('Wochentage sind unvollständig.')
    for offset, raw in enumerate(days):
        day = as_map(raw, 'day')
        require_keys(day, {'date', 'services'}, 'day')
        if day['date'] != (week_start + timedelta(days=offset)).isoformat():
            fail(f'Servicedatum {day["date"]} passt nicht zur Woche.')
        services = as_list(day['services'], 'services')
        if [item.get('meal_code') for item in services] != list(PROFILE_MEALS[profile]):
            fail('Mahlzeitenraster ist unvollständig.')
        for raw_service in services:
            service = as_map(raw_service, 'service')
            extra = set(service) - {
                'meal_code', 'service_state', 'notice', 'options', 'service_start', 'service_end',
            }
            if extra or not {'meal_code', 'service_state', 'notice', 'options'} <= set(service):
                fail('Mahlzeitenfelder fehlen oder sind unerwartet.')
            if service['service_state'] not in {'open', 'closed', 'holiday', 'company_holiday'}:
                fail('Unzulässiger Schliessungsstatus.')
            if service['service_state'] != 'open' and not str(service['notice']).strip():
                fail('Geschlossene Mahlzeit braucht einen Hinweis.')
            options = as_list(service['options'], 'options')
            if {item.get('type_code') for item in options} != set(MENU_TYPES) or len(options) != 2:
                fail('Jede Rasterzelle braucht MENU_1 und VEGGIE.')
            for option in options:
                check_option(profile, service['service_state'], as_map(option, 'option'))


def option_at(weeks: Mapping[str, Any], intent: Mapping[str, Any]) -> dict[str, Any]:
    for week in weeks.values():
        if week['profile_code'] != intent['profile_code']:
            continue
        for day in week['values']['days']:
            if day['date'] != intent['date']:
                continue
            for service in day['services']:
                if service['meal_code'] != intent['meal_code']:
                    continue
                for option in service['options']:
                    if option['type_code'] == intent['type_code']:
                        return option
    fail(f'Menüabsicht ohne Rasterzelle: {intent}.')
    raise AssertionError


def check_weeks(weeks: dict[str, dict[str, Any]], recipes: Mapping[str, Any],
                tags: Mapping[str, Any], intents: list[Any]) -> None:
    if set(weeks) != WEEK_KEYS:
        fail('Es braucht genau die zwei KW36-Entwürfe cafeteria und patient.')
    expected: set[tuple[str, str, str, str]] = set()
    for week in weeks.values():
        require_keys(week, {
            'key', 'profile_code', 'week_start', 'status', 'publication',
            'area_name', 'location', 'values',
        }, 'week')
        if week['status'] != 'DRAFT' or week['publication'] != 'not_requested':
            fail(f'Woche {week["key"]} ist kein unveröffentlichter Entwurf.')
        profile, start = week['profile_code'], date.fromisoformat(week['week_start'])
        if start != date(2026, 8, 31) or profile not in PROFILE_MEALS:
            fail(f'Woche {week["key"]} hat Profil oder Startdatum falsch.')
        values = as_map(week['values'], 'week values')
        check_week_values(profile, start, values)
        build_snapshot(profile, {
            **values, 'week_start': week['week_start'], 'location': week['location'],
            'area_name': week['area_name'],
        }, f"{'PAT' if profile == 'patient' else 'CAF'}-2026-KW36-R99")
        for day in values['days']:
            for service in day['services']:
                if service['service_state'] != 'open':
                    continue
                for option in service['options']:
                    expected.add((profile, day['date'], service['meal_code'], option['type_code']))
    seen: set[tuple[str, str, str, str]] = set()
    for raw in intents:
        row = as_map(raw, 'intent')
        require_keys(row, {
            'profile_code', 'date', 'meal_code', 'type_code', 'recipe_key', 'binding', 'note',
        }, 'intent')
        slot = (row['profile_code'], row['date'], row['meal_code'], row['type_code'])
        if slot in seen or row['binding'] != 'intent_only_r5_unavailable':
            fail(f'Menüabsicht {slot} ist doppelt oder behauptet R5.')
        seen.add(slot)
        recipe = recipes.get(row['recipe_key'])
        if recipe is None:
            fail(f'Menüabsicht verweist auf unbekanntes Rezept {row["recipe_key"]}.')
        option = option_at(weeks, row)
        codes = tag_codes(recipe['tag_keys'], tags)
        labels = {item['code'] for item in option.get('labels') or []}
        if option['title'] != recipe['payload']['title'] or list(option['components']) != list(recipe['menu_components']):
            fail(f'Titel oder Komponenten von {option["title"]!r} passen nicht zum Rezept.')
        if 'VEGAN' in labels and 'VEGAN' not in codes:
            fail(f'{option["title"]} ist vegan gelabelt, das Rezept nicht.')
        if 'VEGETARIAN' in labels and not {'VEG', 'VEGAN'} & codes:
            fail(f'{option["title"]} ist vegetarisch gelabelt, das Rezept nicht.')
        if row['type_code'] == 'VEGGIE' and not {'VEG', 'VEGAN'} & codes:
            fail(f'VEGGIE-Menü {option["title"]} braucht ein vegetarisches Rezept.')
    if seen != expected:
        fail('Menüabsichten decken nicht alle offenen Rasterzellen.')


def validate(path: Path = DATASET) -> dict[str, Any]:
    for name in ('cafeteria_kw36.json', 'patienten_kw36.json'):
        snapshot = json.loads((ROOT / 'demo' / 'snapshots' / name).read_text(encoding='utf-8'))
        if snapshot.get('schema_version') != 2 or 'days' not in snapshot:
            fail(f'Snapshot {name} fehlt oder ist beschädigt.')
    data = json.loads(path.read_text(encoding='utf-8'))
    meta = as_map(data.get('meta'), 'meta')
    if meta.get('status') != 'examples_only_not_imported_not_published':
        fail('Datensatz darf nicht als importiert oder publiziert gelten.')
    if meta.get('validation_uuid_namespace') != str(VALIDATION_NS):
        fail('Validierungs-Namensraum ist falsch.')
    units = check_units(index_rows(as_list(data.get('units'), 'units'), 'unit'))
    categories = index_rows(as_list(data.get('food_categories'), 'food_categories'), 'category')
    tags = index_rows(as_list(data.get('tags'), 'tags'), 'tag')
    check_vocab(categories, 'category', True)
    check_vocab(tags, 'tag', False)
    foods = index_rows(as_list(data.get('foods'), 'foods'), 'food')
    check_foods(foods, categories, tags, units)
    if {food['category_key'] for food in foods.values()} != set(categories):
        fail('Kategorien müssen alle von Zutaten verwendet werden.')
    recipes = index_rows(as_list(data.get('recipes'), 'recipes'), 'recipe')
    check_recipes(recipes, foods, tags, units)
    books = index_rows(as_list(data.get('cookbooks'), 'cookbooks'), 'cookbook')
    check_cookbooks(books, recipes)
    check_revisions(index_rows(as_list(data.get('recipe_revision_intents'), 'revisions'), 'revision'), recipes)
    weeks = index_rows(as_list(data.get('weekly_drafts'), 'weekly_drafts'), 'week')
    check_weeks(weeks, recipes, tags, as_list(data.get('menu_recipe_intents'), 'menu_recipe_intents'))
    mapping = as_map(data.get('import_mapping'), 'import_mapping')
    if any(name not in mapping for name in IMPORT_SERVICES):
        fail('Importzuordnung unvollständig.')
    gaps = as_list(data.get('unresolved_gaps'), 'unresolved_gaps')
    if len(gaps) < 4:
        fail('Offene Import-/Featurelücken fehlen.')
    return {
        'ok': True, 'path': str(path),
        'counts': {
            'units': len(units), 'food_categories': len(categories), 'tags': len(tags),
            'foods': len(foods), 'recipes': len(recipes), 'cookbooks': len(books),
            'recipe_revision_intents': len(recipes), 'weekly_drafts': len(weeks),
            'menu_recipe_intents': len(data['menu_recipe_intents']), 'unresolved_gaps': len(gaps),
        },
        'validation_uuid_namespace': str(VALIDATION_NS),
        'validation_uuids': 'in-memory only; not production public_ids',
        'imported': False, 'published': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=DATASET)
    args = parser.parse_args()
    try:
        result = validate(args.path)
    except ExampleValidationError as error:
        json.dump({'ok': False, 'error': str(error)}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write('\n')
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
