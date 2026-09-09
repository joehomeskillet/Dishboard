"""Bounded reconstruction of captured SQL27 children, never current Food pins."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from .recipe_snapshots import frozen_json
from .recipe_types import RecipeConfigurationError, RecipeRevisionDTO, RecipeValidationError
from .recipe_values import identifier, recipe_payload

MAX_BYTES = 2 * 1024 * 1024
_BODY_FIELDS = {'schema_version', 'recipe', 'calculation', 'units', 'foods'}
_PIN_FIELDS = {'recipe_public_id', 'revision_public_id', 'content_hash_sha256'}
_CALCULATION = {'precision': 50, 'rounding': 'ROUND_HALF_UP', 'quantity_places': 6,
                'bases': {'mass': 'G', 'volume': 'ML', 'count': 'STK'}, 'contextual': 'same-code-only'}


def invalid() -> RecipeConfigurationError:
    return RecipeConfigurationError('Der gespeicherte Zubereitungsstand ist unvollständig oder beschädigt.')


def _array(value: object, maximum: int) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) > maximum:
        raise invalid()
    return value


def _uuid(value: object) -> str:
    result = identifier(value)
    if value != result:
        raise invalid()
    return result


def _pin(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _PIN_FIELDS:
        raise invalid()
    for key in ('recipe_public_id', 'revision_public_id'):
        _uuid(value[key])
    if not isinstance(value['content_hash_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', value['content_hash_sha256']):
        raise invalid()
    return value


def _body(value: object, *, root: bool = False) -> tuple[Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    fields = _BODY_FIELDS | ({'prepared_revisions'} if root else set())
    if not isinstance(value, Mapping) or set(value) != fields:
        raise invalid()
    if type(value['schema_version']) is not int or value['schema_version'] not in (1, 2):
        raise invalid()
    recipe_payload(value['recipe'])  # Bounds only: preserve every original captured value.
    if value['calculation'] != _CALCULATION:
        raise invalid()
    _array(value['units'], 129)
    foods = {}
    for food in _array(value['foods'], 64):
        if not isinstance(food, Mapping):
            raise invalid()
        key = _uuid(food.get('public_id'))
        if key in foods:
            raise invalid()
        foods[key] = food
        if value['schema_version'] == 2:
            if not {'prepared_recipe', 'base_unit', 'storage_locations'} <= food.keys():
                raise invalid()
            if food['prepared_recipe'] is not None:
                _pin(food['prepared_recipe'])
    recipe = cast(Mapping[str, Any], value['recipe'])
    # SQL27 checks recipe_snapshot_complete_v27 for every queued body before the
    # v1-terminal continue, so a captured v1 child must be linked and quantified too.
    # recipe_payload keeps permitting historical gaps for standalone v1 reads, which
    # never reach this closure. quantity_pair already binds a quantity to a valid unit.
    ingredients = recipe['ingredients']
    if not ingredients or any(item['food_public_id'] is None or item['quantity'] is None for item in ingredients):
        raise invalid()
    if value['schema_version'] == 2 and set(foods) != {item['food_public_id'] for item in ingredients}:
        raise invalid()
    return recipe, foods


def reconstructed_snapshots(snapshot: Mapping[str, object], recipe_public_id: str,
                            canonical_size: int) -> dict[str, Mapping[str, Any]]:
    """Recover each original child body; caller verifies PostgreSQL canonical bytes."""
    try:
        if not 0 < canonical_size <= MAX_BYTES or snapshot.get('schema_version') != 2:
            raise invalid()
        _uuid(recipe_public_id)
        root_recipe, root_foods = _body(snapshot, root=True)
        index: dict[str, Mapping[str, Any]] = {}
        bodies = {}
        for entry in _array(snapshot['prepared_revisions'], 64):
            if not isinstance(entry, Mapping) or set(entry) != _PIN_FIELDS | {'snapshot'}:
                raise invalid()
            pin = _pin({key: entry[key] for key in _PIN_FIELDS})
            key = pin['revision_public_id']
            if key in index:
                raise invalid()
            index[key] = entry
            bodies[key] = _body(entry['snapshot'])
        if list(index) != sorted(index):
            raise invalid()
        # Each usage has its own ancestors and quantity; only the index is deduplicated.
        queue: list[tuple[str | None, tuple[str, ...], tuple[str, ...], int]] = [(None, (recipe_public_id,), (), 0)]
        used: set[str] = set()
        expanded, position = 0, 0
        while position < len(queue):
            key, recipe_path, food_path, depth = queue[position]
            position += 1
            recipe, foods = (root_recipe, root_foods) if key is None else bodies[key]
            body = snapshot if key is None else index[key]['snapshot']
            expanded += len(recipe['ingredients'])
            if expanded > 4096:
                raise invalid()
            for ingredient in recipe['ingredients']:
                food_id = ingredient['food_public_id']
                if food_id in food_path:
                    raise invalid()
                if body['schema_version'] == 1:
                    continue
                pin = foods[food_id]['prepared_recipe']
                if pin is None:
                    continue
                child = pin['revision_public_id']
                entry = index.get(child)
                if entry is None or any(entry[field] != pin[field] for field in _PIN_FIELDS):
                    raise invalid()
                if pin['recipe_public_id'] in recipe_path or depth >= 8 or len(queue) >= 4096:
                    raise invalid()
                used.add(child)
                queue.append((child, (*recipe_path, pin['recipe_public_id']), (*food_path, food_id), depth + 1))
        if used != index.keys():
            raise invalid()
        result = {}
        for key, entry in index.items():
            body = entry['snapshot']
            if body['schema_version'] == 1:
                result[key] = body
                continue
            reachable: set[str] = set()
            pending = [body]
            while pending:
                current = pending.pop()
                if current['schema_version'] == 1:
                    continue
                for food in current['foods']:
                    pin = food['prepared_recipe']
                    if pin is not None and pin['revision_public_id'] not in reachable:
                        child = pin['revision_public_id']
                        reachable.add(child)
                        pending.append(index[child]['snapshot'])
            result[key] = frozen_json({**body, 'prepared_revisions': [index[child] for child in sorted(reachable)]})
        return result
    except (RecipeValidationError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, RecipeConfigurationError):
            raise
        raise invalid() from None


def verify_canonical(revision: RecipeRevisionDTO) -> None:
    """Hash only PostgreSQL-provided canonical text, then bind it to immutable DTO values."""
    raw = revision.canonical_snapshot_text
    if not isinstance(raw, str) or not 0 < len(raw.encode('utf-8')) <= MAX_BYTES:
        raise invalid()
    if hashlib.sha256(raw.encode('utf-8')).hexdigest() != revision.content_hash_sha256:
        raise invalid()
    try:
        if frozen_json(json.loads(raw)) != revision.snapshot:
            raise invalid()
    except (ValueError, RecursionError):
        raise invalid() from None


def verified_prepared(revision: RecipeRevisionDTO) -> tuple[RecipeRevisionDTO, ...]:
    """Bind every reconstructed node to its exact original identity and canonical bytes."""
    verify_canonical(revision)
    assert revision.canonical_snapshot_text is not None
    reconstructed = reconstructed_snapshots(revision.snapshot, revision.recipe_public_id,
                                             len(revision.canonical_snapshot_text.encode('utf-8')))
    children = revision.prepared_revisions
    if [child.public_id for child in children] != list(reconstructed):
        raise invalid()
    entries = {entry['revision_public_id']: entry for entry in cast(Sequence[Any], revision.snapshot['prepared_revisions'])}
    for child in children:
        entry = entries[child.public_id]
        if child.prepared_revisions or child.recipe_public_id != entry['recipe_public_id'] or child.content_hash_sha256 != entry['content_hash_sha256']:
            raise invalid()
        verify_canonical(child)
        if child.snapshot != reconstructed[child.public_id]:
            raise invalid()
    return children
