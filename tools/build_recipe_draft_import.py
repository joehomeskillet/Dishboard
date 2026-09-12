#!/usr/bin/env python3
"""Translate linked recipe drafts to import format and apply via Foundations + import batches."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / 'reference_scaffold'
DRAFT_PATH = ROOT / 'demo' / 'linked_recipe_drafts.json'
IMPORT_PATH = ROOT / 'demo' / 'linked_recipe_drafts_import.json'
ANNOTATIONS = ('unreviewed', 'proposed_not_measured', 'allergen_not_checked')
FETCHED_AT = '2026-09-08T21:51:49+00:00'
REQUIRED_IMPORT_CAPABILITIES = frozenset({'masterdata.write', 'recipe.write', 'recipe.import'})
STORAGE_CODES: dict[str, tuple[str, str, int]] = {
    'proposed.storage.trockenlager': ('TROCKEN', 'Trockenlager', 1),
    'proposed.storage.kuehlraum': ('KUEHL', 'Kühlraum', 2),
    'proposed.storage.tiefkuehler': ('TIEFKHL', 'Tiefkühler', 3),
}


class ActorResolutionError(ValueError):
    """Raised when requested local import actor is absent or unauthorized."""


def resolve_import_actor(engine: Any, identifier: str) -> Any:
    """Resolve active local account by public UUID or username without mutation."""
    if str(SCAFFOLD) not in sys.path:
        sys.path.insert(0, str(SCAFFOLD))
    from sqlalchemy import text
    from cafeteria.auth.local_users import ActorExpectation  # type: ignore[import-not-found]
    from cafeteria.auth.service import (  # type: ignore[import-not-found]
        load_user_authorization,
        normalize_username,
    )
    from cafeteria.roles import capabilities  # type: ignore[import-not-found]

    value = identifier.strip()
    try:
        public_id = UUID(value)
    except ValueError:
        public_id = None
    if public_id is None:
        lookup = normalize_username(value)
        query = text('''SELECT u.id FROM cafeteria.users u
                        JOIN cafeteria.local_credentials c ON c.user_id=u.id
                        WHERE u.auth_provider='local' AND c.username=:identifier''')
    else:
        lookup = public_id
        query = text('''SELECT u.id FROM cafeteria.users u
                        JOIN cafeteria.local_credentials c ON c.user_id=u.id
                        WHERE u.auth_provider='local' AND u.public_id=:identifier''')
    with engine.begin() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        user_id = connection.execute(
            query,
            {'identifier': lookup},
        ).scalar_one_or_none()
    authorization = load_user_authorization(engine, user_id) if user_id is not None else None
    if authorization is None or authorization.auth_provider != 'local':
        raise ActorResolutionError(
            f'Lokaler Import-Akteur {identifier!r} nicht gefunden oder deaktiviert.'
        )
    allowed = capabilities(list(authorization.roles))
    missing = set() if '*' in allowed else REQUIRED_IMPORT_CAPABILITIES - allowed
    if missing:
        names = ', '.join(sorted(missing))
        raise ActorResolutionError(
            f'Lokaler Import-Akteur {identifier!r} hat nicht alle nötigen Berechtigungen: {names}.'
        )
    return ActorExpectation(authorization.user_id, authorization.authz_version)


@contextmanager
def signed_in(engine: Any, actor: Any) -> Iterator[None]:
    """Create minimal request context expected by capability-protected stores."""
    from flask import Flask, session

    app = Flask(__name__)
    app.secret_key = os.environ.get('IMPORT_SECRET') or os.urandom(32)
    app.extensions['cafeteria_db'] = engine
    with app.test_request_context():
        session['user'] = {'id': actor.user_id}
        session['authz_version'] = actor.authz_version
        yield


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


def require_known_unit(code: str, *, allowed: set[str], draft_path: Path, field: str) -> None:
    if code not in allowed:
        raise ValueError(
            f'Unbekannter Einheiten-Code {code!r} in {draft_path} ({field}).'
        )


def validate_draft_units(draft: dict[str, Any], *, draft_path: Path) -> None:
    allowed = {str(code) for code in draft.get('existing_unit_codes') or []}
    if not allowed:
        raise ValueError(f'existing_unit_codes fehlt oder ist leer in {draft_path}.')
    for item in draft['foods']:
        require_known_unit(
            item['base_unit_code'], allowed=allowed, draft_path=draft_path,
            field=f"foods[{item['key']}].base_unit_code",
        )
    for recipe in draft['recipes']:
        require_known_unit(
            recipe['yield_unit_code'], allowed=allowed, draft_path=draft_path,
            field=f"recipes[{recipe['key']}].yield_unit_code",
        )
        for index, ingredient in enumerate(recipe['ingredients']):
            require_known_unit(
                ingredient['unit_code'], allowed=allowed, draft_path=draft_path,
                field=f"recipes[{recipe['key']}].ingredients[{index}].unit_code",
            )


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
    validate_draft_units(draft, draft_path=draft_path)
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', type=Path, default=DRAFT_PATH)
    parser.add_argument('--output', type=Path, default=IMPORT_PATH)
    parser.add_argument('--translate', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--database-url', default=None)
    parser.add_argument('--actor-user', default=None, metavar='PUBLIC_ID_OR_USERNAME')
    parser.add_argument('--skip-migrations', action='store_true')
    parser.add_argument('--write-back', type=Path, default=None)
    args = parser.parse_args()
    if args.translate or (not args.apply and not args.dry_run):
        draft = load_draft(args.draft)
        document = translate_draft(draft, draft_path=args.draft)
        write_import(document, args.output)
        print(json.dumps({'translated': str(args.output), 'foods': len(document['foods']),
                          'recipes': len(document['recipes'])}, ensure_ascii=False))
    if args.apply or args.dry_run:
        from recipe_draft_apply import BatchImportError, apply_import, scaffold_import

        document = json.loads(args.output.read_text(encoding='utf-8'))
        if args.dry_run and not args.apply:
            print(json.dumps(apply_import(document, None, None, dry_run=True), ensure_ascii=False, indent=2))
            return 0
        fixture_actor_allowed = os.environ.get('RECIPE_IMPORT_ALLOW_FIXTURE_ACTOR') == '1'
        if not args.actor_user and not fixture_actor_allowed:
            print(
                '--actor-user ist für --apply erforderlich; Test-Fixture nur mit '
                'RECIPE_IMPORT_ALLOW_FIXTURE_ACTOR=1.',
                file=sys.stderr,
            )
            return 2
        database_url = args.database_url or os.environ.get('DATABASE_URL')
        if not database_url:
            print('DATABASE_URL oder --database-url erforderlich.', file=sys.stderr)
            return 2
        scaffold_import()
        from sqlalchemy import create_engine
        from cafeteria import db as database  # type: ignore[import-not-found]

        engine = create_engine(database_url, future=True)
        if args.actor_user:
            try:
                actor = resolve_import_actor(engine, args.actor_user)
            except ActorResolutionError as error:
                print(str(error), file=sys.stderr)
                return 2
            if not args.skip_migrations:
                database.run_migrations(engine, database.SCHEMA)
        else:
            if not args.skip_migrations:
                database.run_migrations(engine, database.SCHEMA)
            actor_module = __import__('test_master_data_db', fromlist=['make_actor'])
            actor = actor_module.make_actor(engine, 'Cafeteria.Admin')
        with signed_in(engine, actor):
            try:
                summary = apply_import(
                    document, engine, actor, dry_run=args.dry_run, write_back=args.write_back,
                )
            except BatchImportError as error:
                print(json.dumps(error.summary, ensure_ascii=False, indent=2), file=sys.stderr)
                print(str(error), file=sys.stderr)
                return 1
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
