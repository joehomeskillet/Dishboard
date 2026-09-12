#!/usr/bin/env python3
"""Create native common dish templates from an authenticated, persisted recipe import."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from build_recipe_draft_import import IMPORT_PATH, resolve_import_actor, signed_in
from recipe_draft_apply import scaffold_import

DESCRIPTION = 'Ungeprüfter KI-Rezeptentwurf; Mengen vorgeschlagen, Allergene nicht geprüft.'


class TemplateImportError(ValueError):
    """The persisted import or existing templates do not match the requested input."""


def _source(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise TemplateImportError('Ungültige Rezeptdaten.')
    source = payload.get('source')
    if not isinstance(source, Mapping):
        raise TemplateImportError('Ursprüngliche Rezeptquelle fehlt.')
    return source


def _input(document: dict[str, Any]) -> tuple[str, dict[int, str], list[dict[str, str]]]:
    if not isinstance(document, dict) or not isinstance(document.get('meta'), dict):
        raise TemplateImportError('Ungültiges Importdokument.')
    meta = document.get('meta', {})
    digest = meta.get('source_draft_sha256')
    if (meta.get('kind') != 'linked_recipe_drafts_import' or meta.get('format_version') != 1
            or meta.get('adapter_kind') != 'ai_assisted'
            or not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None):
        raise TemplateImportError('Ungültige Importquelle oder SHA-256.')
    rows, mappings = document.get('recipes'), document.get('dish_mappings')
    if (not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows)
            or not isinstance(mappings, list) or not all(isinstance(row, dict) for row in mappings)):
        raise TemplateImportError('Ungültige Rezeptzeilen oder Gerichtzuordnungen.')
    recipes = [row for row in rows if row.get('batch_group') == 'dish']
    by_number: dict[int, str] = {}
    for number, recipe in enumerate(recipes, start=1):
        key = recipe.get('key')
        source = _source(recipe.get('recipe_payload', {}))
        if (not isinstance(key, str) or not key or key in by_number.values()
                or source.get('kind') != 'ai_assisted' or source.get('reference') != f'draft:{key}'):
            raise TemplateImportError('Ungültige oder mehrdeutige Rezeptreferenz.')
        by_number[number] = key
    keys: set[str] = set()
    titles: set[str] = set()
    for mapping in mappings:
        key, title = mapping.get('recipe_key'), mapping.get('title')
        if (key not in by_number.values() or key in keys or not isinstance(title, str)
                or not title.strip() or title != title.strip() or len(title) > 120
                or '\x00' in title or title.casefold() in titles):
            raise TemplateImportError('Ungültige oder mehrdeutige Gerichtzuordnung.')
        keys.add(key)
        titles.add(title.casefold())
    if not keys or keys != set(by_number.values()):
        raise TemplateImportError('Gerichtzuordnungen müssen sämtliche Gerichtsrezepte enthalten.')
    return digest, by_number, mappings


def _resolve_recipes(
    engine: Any, digest: str, by_number: dict[int, str],
) -> tuple[str, dict[str, str]]:
    from cafeteria import recipe_import_store as batches
    from cafeteria import recipe_store as recipes

    filename = f'linked_recipe_drafts_import:{digest[:16]}:dish'
    matches = [batch for batch in batches.list_batches(engine)
               if batch.adapter_kind == 'ai_assisted' and batch.source_sha256 == digest
               and batch.source_filename == filename and batch.status == 'imported']
    if len(matches) != 1:
        raise TemplateImportError('Importierter Gerichtstapel fehlt oder ist mehrdeutig.')
    batch = batches.get_batch(engine, matches[0].public_id)
    candidates = {row.row_number: row for row in batch.candidates}
    results = {row.get('row_number'): row for row in batch.imported_result}
    if (len(results) != len(batch.imported_result) or set(results) != set(by_number)
            or len(candidates) != len(batch.candidates) or set(candidates) != set(by_number)):
        raise TemplateImportError('Gerichtstapel enthält abweichende Rezeptzeilen.')
    resolved: dict[str, str] = {}
    for number, key in by_number.items():
        candidate, result = candidates[number], results[number]
        expected_ref = f'draft:{key}'
        source = _source(candidate.original_payload)
        if (candidate.original_source_kind != 'ai_assisted'
                or source.get('kind') != 'ai_assisted' or source.get('reference') != expected_ref
                or result.get('decision') not in ('create_new', 'skip_existing')):
            raise TemplateImportError(f'Ursprüngliche Rezeptreferenz stimmt nicht: Zeile {number}.')
        try:
            public_id = str(UUID(str(result.get('recipe_public_id'))))
        except ValueError as error:
            raise TemplateImportError(f'Ungültiges Rezeptziel: Zeile {number}.') from error
        if public_id in resolved.values():
            raise TemplateImportError('Mehrere Importzeilen verweisen auf dasselbe Rezept.')
        recipe = recipes.get_recipe(engine, public_id)
        current_source = _source(recipe.payload)
        if (not recipe.active or current_source.get('kind') != 'ai_assisted'
                or current_source.get('reference') != expected_ref):
            raise TemplateImportError(f'Rezept archiviert oder Quelle abweichend: Zeile {number}.')
        resolved[key] = public_id
    return batch.public_id, resolved


def _plan(
    engine: Any, mappings: list[dict[str, str]], resolved: dict[str, str],
) -> tuple[list[dict[str, object]], int]:
    from cafeteria import dish_template_store as templates

    existing = templates.list_templates(engine, include_archived=True)
    planned = []
    skipped = 0
    for mapping in mappings:
        payload: dict[str, object] = {
            'title': mapping['title'], 'description': DESCRIPTION, 'profile_scope': 'common',
            'menu_type_code': None, 'recipe_public_id': resolved[mapping['recipe_key']],
        }
        matches = [row for row in existing
                   if row.recipe_public_id == payload['recipe_public_id']
                   or row.title.casefold() == mapping['title'].casefold()]
        if matches:
            if (len(matches) != 1 or not matches[0].active
                    or any(getattr(matches[0], name) != value for name, value in payload.items())):
                raise TemplateImportError(f'Vorhandene Gerichtvorlage widerspricht Import: {mapping["title"]}.')
            skipped += 1
        else:
            planned.append(payload)
    return planned, skipped


def import_templates(
    document: dict[str, Any], engine: Any, *, actor_user: str, profile_scope: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Preflight every target before writing; retries skip identical native templates."""
    scaffold_import()
    from sqlalchemy import text
    from cafeteria import dish_template_store as templates
    from cafeteria import recipe_store as recipes

    if profile_scope != 'common':
        raise TemplateImportError('Expliziter Geltungsbereich common erforderlich.')
    digest, by_number, mappings = _input(document)
    actor = resolve_import_actor(engine, actor_user)
    with signed_in(engine, actor), engine.begin() as guard:
        guard.execute(text('SET TRANSACTION READ ONLY'))
        # Native writers own their transactions. This lock serializes this CLI across all batches.
        if not guard.execute(text('SELECT pg_try_advisory_xact_lock(190912, 29)')).scalar_one():
            raise TemplateImportError('Ein Gerichtvorlagenimport läuft bereits.')
        location = recipes.get_location(engine)
        batch_id, resolved = _resolve_recipes(engine, digest, by_number)
        planned, skipped = _plan(engine, mappings, resolved)
        created = []
        if not dry_run:
            for payload in planned:
                result = templates.create_template(
                    engine, actor, payload, expected_location_id=location,
                )
                created.append(result['public_id'])
        return {
            'dry_run': dry_run, 'batch_public_id': batch_id, 'profile_scope': profile_scope,
            'planned': len(planned), 'created': len(created), 'skipped': skipped,
            'template_public_ids': created,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=IMPORT_PATH)
    parser.add_argument('--actor-user', required=True, metavar='PUBLIC_ID_OR_USERNAME')
    parser.add_argument('--profile-scope', required=True, choices=['common'])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    scaffold_import()
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from werkzeug.exceptions import HTTPException
    from cafeteria.config import Config

    engine = None
    try:
        document = json.loads(args.input.read_text(encoding='utf-8'))
        engine = create_engine(Config().DATABASE_URL, future=True)
        summary = import_templates(
            document, engine, actor_user=args.actor_user,
            profile_scope=args.profile_scope, dry_run=args.dry_run,
        )
    except (ValueError, OSError, HTTPException) as error:
        print(str(error), file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print('Datenbankzugriff für Gerichtvorlagenimport fehlgeschlagen.', file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
