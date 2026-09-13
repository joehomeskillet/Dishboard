"""Pure reading document shared by HTML and PDF; never a stored snapshot."""
from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from ..recipe_snapshot_v2 import verify_canonical
from ..recipe_types import RecipeConfigurationError, RecipeRevisionDTO, RecipeValidationError
from ..recipe_values import identifier, positive, recipe_payload
from .recipe_scaling import scaled_recipe

DOCUMENT_VERSION = 'recipe-reading-v1'
SOURCE_NAMES = {'manual': 'Manuell erfasst', 'url': 'Internetquelle',
                'file_import': 'Dateiimport', 'ai_assisted': 'KI-unterstützt'}


def _identity(payload: Mapping[str, Any], revision: RecipeRevisionDTO | None) -> dict[str, Any]:
    if revision is None:
        return {'kind': 'draft', 'recipe_public_id': None, 'revision_public_id': None,
                'revision_number': None, 'content_hash_sha256': None, 'created_at': None}
    if (type(revision.snapshot.get('schema_version')) is not int
            or revision.snapshot['schema_version'] not in (1, 2)
            or payload != revision.snapshot['recipe']):
        raise RecipeConfigurationError('Rezept und Revisionsstand passen nicht zusammen.')
    identifier(revision.public_id)
    identifier(revision.recipe_public_id)
    positive(revision.revision_number)
    if not re.fullmatch('[0-9a-f]{64}', revision.content_hash_sha256):
        raise RecipeConfigurationError('Die Identität der Rezeptrevision ist ungültig.')
    if revision.canonical_snapshot_text is not None:
        verify_canonical(revision)
    return {'kind': 'revision', 'recipe_public_id': revision.recipe_public_id,
            'revision_public_id': revision.public_id, 'revision_number': revision.revision_number,
            'content_hash_sha256': revision.content_hash_sha256,
            'created_at': revision.created_at.isoformat()}


def _section(payload: Mapping[str, Any], calculated: Mapping[str, Any],
             revision: RecipeRevisionDTO | None) -> dict[str, Any]:
    recipe_payload(payload)  # Bounds only: keep every original captured value below.
    identity = _identity(payload, revision)
    provenance: list[dict[str, Any]] = []

    def source_id(source: dict[str, Any], use: str) -> int:
        for entry in provenance:
            if entry['source'] == source:
                entry['uses'].append(use)
                return cast(int, entry['id'])
        number = len(provenance) + 1
        provenance.append({'id': number, 'label': SOURCE_NAMES[source['kind']],
                           'source': source, 'uses': [use]})
        return number

    recipe_source_id = source_id(dict(payload['source']), 'recipe')
    ingredients = []
    for number, row in enumerate(calculated['rows'], 1):
        item = row['ingredient']
        origin = {'kind': item['source_kind'], 'reference': item['source_reference'],
                  'url': None, 'note': None, 'fetched_at': item['fetched_at']}
        ingredients.append({
            'number': number, 'line_public_id': item['line_public_id'],
            'food_public_id': item['food_public_id'], 'group_label': item['group_label'],
            'text': item['ingredient_text'], 'amount': row['scaled'], 'unit': row['unit'],
            'original_amount': row['original'], 'note': item['note'],
            'source_id': source_id(origin, f'ingredient:{number}'),
        })
    warnings = [{'code': 'allergens_unrecorded',
                 'text': 'Allergenangaben sind in diesen Rezeptdaten nicht erfasst.'}]
    if any(entry['source']['kind'] == 'ai_assisted' for entry in provenance):
        warnings.append({'code': 'ai_source',
                         'text': 'KI-unterstützte Angaben; vor Verwendung fachlich prüfen.'})
    steps = [{'number': number, 'instruction': step['instruction'],
              'duration_minutes': step['duration_minutes'], 'image_sha256': step['image_sha256']}
             for number, step in enumerate(payload['steps'], 1)]
    return {
        'document_version': DOCUMENT_VERSION, 'identity': identity,
        'title': payload['title'], 'description': payload['description'],
        'yield': {'amount': calculated['target'], 'unit': calculated['unit'],
                  'original_amount': payload['servings'],
                  'is_scaled': Decimal(calculated['target']) != Decimal(calculated['source']),
                  'measurement_status': None},
        'times': {'prep_minutes': payload['prep_minutes'], 'cook_minutes': payload['cook_minutes']},
        'warnings': warnings,
        'source_notes': [entry['source']['note'] for entry in provenance
                         if entry['source']['note'] is not None],
        'ingredients': ingredients, 'steps': steps,
        'empty_ingredients': 'Keine Zutaten gespeichert.' if not ingredients else None,
        'empty_steps': 'Keine Schritte gespeichert.' if not steps else None,
        'images': [dict(image) for image in payload['images']],
        'tag_public_ids': list(payload['tag_public_ids']),
        'recipe_source_id': recipe_source_id, 'provenance': provenance, 'prepared': [],
    }


def build_recipe_document(payload: Mapping[str, Any], target: str | None = None, *,
                          revision: RecipeRevisionDTO | None = None) -> dict[str, Any]:
    """Project one payload and its exact captured children; no I/O or input mutation.

    Invalid user targets retain scaled_recipe's named FormError. Invalid stored
    data raises RecipeConfigurationError. See the reading-document design contract.
    """
    try:
        recipe_payload(payload)
        _identity(payload, revision)
    except (RecipeValidationError, KeyError, TypeError, AttributeError):
        raise RecipeConfigurationError('Gespeicherte Rezeptdaten sind ungültig.') from None
    calculated = scaled_recipe(payload, target, revision=revision)
    document = _section(payload, calculated, revision)
    first_uses: dict[tuple[str, str], int] = {}
    for number, prepared in enumerate(calculated.get('prepared', ()), 1):
        child = prepared['revision']
        key = (child.public_id, child.content_hash_sha256)
        document['prepared'].append({
            'use_number': number, 'first_use_number': first_uses.setdefault(key, number),
            'for_ingredient': prepared['for_ingredient'],
            'document': _section(prepared['recipe'], prepared['calculated'], child),
        })
    return document
