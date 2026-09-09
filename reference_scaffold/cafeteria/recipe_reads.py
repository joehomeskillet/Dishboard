"""Read-only active-location recipe, historical revision and cookbook queries."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Connection, Engine, text

from .component_catalog_store import resolve_single_active_location_connection
from .recipe_snapshots import frozen_json
from .recipe_snapshot_v2 import invalid, reconstructed_snapshots, verified_prepared
from .recipe_types import (
    CookbookDTO, RecipeAssetDTO, RecipeDTO, RecipeNotFoundError,
    RecipeRevisionDTO, RecipeRevisionSummaryDTO, RecipeUnavailableError, RecipeValidationError,
)
from .recipe_values import identifier, recipe_payload, rows


@contextmanager
def connection(engine: Engine) -> Iterator[tuple[Connection, int]]:
    if engine is None:
        raise RecipeUnavailableError('Rezepte sind derzeit nicht verfügbar.')
    with engine.begin() as current:
        current.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        yield current, resolve_single_active_location_connection(current)


def paging(limit: int, offset: int, include_archived: bool) -> dict[str, object]:
    if type(limit) is not int or not 1 <= limit <= 500 or type(offset) is not int or offset < 0 or type(include_archived) is not bool:
        raise RecipeValidationError('Ungültiger Seitenausschnitt.')
    return {'limit': limit, 'offset': offset, 'archived': include_archived}


def get_location(engine: Engine) -> int:
    with connection(engine) as (_, location):
        return location


def list_recipes(engine: Engine, *, include_archived: bool = False, search: str | None = None,
                 ingredient: str | None = None, tag: str | None = None,
                 limit: int = 200, offset: int = 0) -> tuple[RecipeDTO, ...]:
    values = paging(limit, offset, include_archived)
    for value in (search, ingredient):
        if value is not None and (not isinstance(value, str) or len(value) > 200 or '\x00' in value):
            raise RecipeValidationError('Ungültige Suche.')
    values['search'] = search or ''
    values['ingredient'] = ingredient or ''
    values['tag'] = None if tag is None or tag == '' else identifier(tag)
    with connection(engine) as (current, location):
        values['location'] = location
        return tuple(RecipeDTO(str(row.public_id), row.row_version, row.active, frozen_json(row.payload))
                     for row in current.execute(text('''SELECT r.public_id,r.row_version,r.active,
            cafeteria.recipe_payload_v22(r.id) AS payload FROM cafeteria.recipes r
            WHERE r.location_id=:location AND (:archived OR r.active)
            AND strpos(lower(r.title),lower(:search))>0
            AND (:ingredient='' OR EXISTS (
                SELECT 1 FROM cafeteria.recipe_ingredients i
                LEFT JOIN cafeteria.foods f ON f.id=i.food_id AND f.location_id=i.location_id
                WHERE i.recipe_id=r.id AND i.location_id=r.location_id
                AND (strpos(lower(i.ingredient_text),lower(:ingredient))>0
                     OR strpos(lower(f.name),lower(:ingredient))>0)))
            AND (CAST(:tag AS uuid) IS NULL OR EXISTS (
                SELECT 1 FROM cafeteria.recipe_tags rt
                JOIN cafeteria.tags t ON t.id=rt.tag_id AND t.location_id=rt.location_id
                WHERE rt.recipe_id=r.id AND rt.location_id=r.location_id
                AND t.public_id=CAST(:tag AS uuid)))
            ORDER BY lower(r.title),r.public_id LIMIT :limit OFFSET :offset'''), values))


def get_recipe(engine: Engine, public_id: str) -> RecipeDTO:
    public_id = identifier(public_id)
    with connection(engine) as (current, location):
        row = current.execute(text('''SELECT public_id,row_version,active,cafeteria.recipe_payload_v22(id) AS payload
            FROM cafeteria.recipes WHERE location_id=:location AND public_id=CAST(:id AS uuid)'''),
            {'location': location, 'id': public_id}).one_or_none()
        if row is None:
            raise RecipeNotFoundError('Rezept nicht gefunden.')
        return RecipeDTO(str(row.public_id), row.row_version, row.active, frozen_json(row.payload))


def get_revision(engine: Engine, public_id: str) -> RecipeRevisionDTO:
    public_id = identifier(public_id)
    with connection(engine) as (current, location):
        return _get_revision_connection(current, location, public_id)


def _get_revision_connection(current: Connection, location: int, public_id: str) -> RecipeRevisionDTO:
    row = current.execute(text('''SELECT h.*,h.snapshot_json::text AS canonical_text,r.public_id AS recipe_public_id
        FROM cafeteria.recipe_revisions h JOIN cafeteria.recipes r ON r.id=h.recipe_id AND r.location_id=h.location_id
        WHERE h.location_id=:location AND h.public_id=CAST(:id AS uuid)'''),
        {'location': location, 'id': public_id}).one_or_none()
    if row is None:
        raise RecipeNotFoundError('Rezeptrevision nicht gefunden.')
    version = row.snapshot_json.get('schema_version')
    if type(version) is not int or version not in (1, 2):
        raise invalid()
    if version == 2:
        children = _prepared_revisions_connection(current, location, public_id, str(row.recipe_public_id),
                                                   row.snapshot_json, row.canonical_text)
        revision = RecipeRevisionDTO(str(row.public_id), str(row.recipe_public_id), row.revision_number,
            row.content_hash_sha256, frozen_json(row.snapshot_json), row.created_at, row.created_by,
            children, row.canonical_text)
        verified_prepared(revision)
        return revision
    return RecipeRevisionDTO(str(row.public_id), str(row.recipe_public_id), row.revision_number,
                             row.content_hash_sha256, frozen_json(row.snapshot_json), row.created_at, row.created_by)


def _prepared_revisions_connection(current: Connection, location: int, public_id: str,
                                   recipe_public_id: str, snapshot: Mapping[str, object],
                                   canonical_text: str) -> tuple[RecipeRevisionDTO, ...]:
    reconstructed = reconstructed_snapshots(snapshot, recipe_public_id, len(canonical_text.encode('utf-8')))
    subsets = {key: [entry['revision_public_id'] for entry in body.get('prepared_revisions', ())]
               for key, body in reconstructed.items()}
    if not subsets:
        return ()
    # Only UUID subsets cross into this projection. PostgreSQL retains the original
    # jsonb numeric representation, key ordering and escaping; Python never reserializes it.
    selected = current.execute(text('''WITH root AS (
        SELECT snapshot_json FROM cafeteria.recipe_revisions
        WHERE location_id=:location AND public_id=CAST(:root AS uuid)
    ), requested AS (SELECT key,value FROM jsonb_each(CAST(:subsets AS jsonb)))
    SELECT h.*,r.public_id AS recipe_public_id,h.snapshot_json::text AS canonical_text,
        (CASE WHEN node->'snapshot'->>'schema_version'='1' THEN node->'snapshot'
         ELSE (node->'snapshot')||jsonb_build_object('prepared_revisions',(
             SELECT COALESCE(jsonb_agg(child ORDER BY (child->>'revision_public_id')::uuid),'[]'::jsonb)
             FROM jsonb_array_elements(root.snapshot_json->'prepared_revisions') child
             WHERE child->>'revision_public_id' IN (SELECT jsonb_array_elements_text(requested.value))
         )) END)::text AS reconstructed_text
    FROM root CROSS JOIN requested
    CROSS JOIN LATERAL jsonb_array_elements(root.snapshot_json->'prepared_revisions') node
    JOIN cafeteria.recipe_revisions h ON h.location_id=:location AND h.public_id=CAST(requested.key AS uuid)
    JOIN cafeteria.recipes r ON r.id=h.recipe_id AND r.location_id=h.location_id
        AND r.public_id=CAST(node->>'recipe_public_id' AS uuid)
    WHERE node->>'revision_public_id'=requested.key ORDER BY h.public_id'''),
        {'location': location, 'root': public_id, 'subsets': json.dumps(subsets)}).all()
    if len(selected) != len(subsets):
        raise invalid()
    children = []
    for row in selected:
        if row.reconstructed_text != row.canonical_text:
            raise invalid()
        children.append(RecipeRevisionDTO(str(row.public_id), str(row.recipe_public_id), row.revision_number,
            row.content_hash_sha256, frozen_json(row.snapshot_json), row.created_at, row.created_by,
            canonical_snapshot_text=row.canonical_text))
    return tuple(children)


def list_revisions(engine: Engine, recipe_public_id: str, *, limit: int = 50,
                   offset: int = 0) -> tuple[RecipeRevisionSummaryDTO, ...]:
    recipe_public_id = identifier(recipe_public_id)
    values = paging(limit, offset, True)
    with connection(engine) as (current, location):
        values.update(location=location, public_id=recipe_public_id)
        recipe_id = current.execute(text('''SELECT id FROM cafeteria.recipes
            WHERE location_id=:location AND public_id=CAST(:public_id AS uuid)'''), values).scalar_one_or_none()
        if recipe_id is None:
            raise RecipeNotFoundError('Rezept nicht gefunden.')
        values['recipe_id'] = recipe_id
        return tuple(RecipeRevisionSummaryDTO(str(row.public_id), recipe_public_id, row.revision_number,
                                             row.content_hash_sha256, row.created_at, row.created_by)
                     for row in current.execute(text('''SELECT public_id,revision_number,
                content_hash_sha256,created_at,created_by FROM cafeteria.recipe_revisions
                WHERE location_id=:location AND recipe_id=:recipe_id
                ORDER BY revision_number DESC,public_id LIMIT :limit OFFSET :offset'''), values))


def get_recipe_asset(engine: Engine, recipe_public_id: str, sha256: str) -> RecipeAssetDTO:
    recipe_public_id = identifier(recipe_public_id)
    if not isinstance(sha256, str) or re.fullmatch('[0-9a-f]{64}', sha256) is None:
        raise RecipeValidationError('Ungültiger Bildhash.')
    with connection(engine) as (current, location):
        return _get_recipe_asset_connection(current, location, recipe_public_id, sha256)


def _get_recipe_asset_connection(
    current: Connection, location: int, recipe_public_id: str, sha256: str,
) -> RecipeAssetDTO:
    row = current.execute(text('''SELECT a.sha256,a.image_data,a.content_type,a.width,a.height
        FROM cafeteria.recipes r JOIN cafeteria.recipe_assets a ON a.location_id=r.location_id
        WHERE r.public_id=CAST(:recipe AS uuid) AND r.location_id=:location AND a.sha256=:sha
        AND (EXISTS(SELECT 1 FROM cafeteria.recipe_images i WHERE i.recipe_id=r.id AND i.sha256=a.sha256)
         OR EXISTS(SELECT 1 FROM cafeteria.recipe_steps s WHERE s.recipe_id=r.id AND s.image_sha256=a.sha256)
         OR EXISTS(SELECT 1 FROM cafeteria.recipe_revisions h WHERE h.recipe_id=r.id AND h.location_id=r.location_id
          AND (EXISTS(SELECT 1 FROM jsonb_array_elements(h.snapshot_json->'recipe'->'images') i WHERE i->>'sha256'=a.sha256)
           OR EXISTS(SELECT 1 FROM jsonb_array_elements(h.snapshot_json->'recipe'->'steps') s WHERE s->>'image_sha256'=a.sha256))))'''),
        {'location': location, 'recipe': recipe_public_id, 'sha': sha256}).one_or_none()
    if row is None:
        raise RecipeNotFoundError('Rezeptbild nicht gefunden.')
    return RecipeAssetDTO(row.sha256, bytes(row.image_data), row.content_type, row.width, row.height)


def recipe_print_input(
    current: Connection, recipe_public_id: str, revision_public_id: str,
) -> tuple[RecipeRevisionDTO, dict[str, RecipeAssetDTO]]:
    """Read only the selected immutable recipe and its images on the caller's transaction."""
    recipe_public_id, revision_public_id = identifier(recipe_public_id), identifier(revision_public_id)
    location = resolve_single_active_location_connection(current)
    revision = _get_revision_connection(current, location, revision_public_id)
    if revision.recipe_public_id != recipe_public_id:
        raise RecipeNotFoundError('Rezeptrevision nicht gefunden.')
    images = {}
    for selected in (revision, *revision.prepared_revisions):
        recipe = recipe_payload(selected.snapshot.get('recipe'))
        digests: set[str] = set()
        for collection, field in (('images', 'sha256'), ('steps', 'image_sha256')):
            for item in rows(recipe[collection]):
                if not isinstance(item, Mapping):
                    raise RecipeValidationError('Ungültiger Bildeintrag in der Rezeptrevision.')
                digest = item.get(field)
                if digest is None and collection == 'steps':
                    continue
                if not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None:
                    raise RecipeValidationError('Ungültiger Bildhash in der Rezeptrevision.')
                digests.add(digest)
        for digest in sorted(digests):
            images[digest] = _get_recipe_asset_connection(current, location, selected.recipe_public_id, digest)
    return revision, images


def list_cookbooks(engine: Engine, *, include_archived: bool = False, limit: int = 200,
                   offset: int = 0) -> tuple[CookbookDTO, ...]:
    values = paging(limit, offset, include_archived)
    with connection(engine) as (current, location):
        values['location'] = location
        return tuple(CookbookDTO(str(row.public_id), row.row_version, row.name, row.description, row.active,
                                 tuple(str(value) for value in row.recipe_ids))
                     for row in current.execute(text('''SELECT c.*,ARRAY(SELECT r.public_id
                FROM cafeteria.cookbook_recipes cr JOIN cafeteria.recipes r ON r.id=cr.recipe_id AND r.location_id=cr.location_id
                WHERE cr.cookbook_id=c.id AND cr.location_id=c.location_id ORDER BY cr.sort_order) AS recipe_ids
             FROM cafeteria.cookbooks c WHERE c.location_id=:location AND (:archived OR c.active)
             ORDER BY lower(c.name),c.public_id LIMIT :limit OFFSET :offset'''), values))


def get_cookbook(engine: Engine, public_id: str) -> CookbookDTO:
    public_id = identifier(public_id)
    with connection(engine) as (current, location):
        row = current.execute(text('''SELECT c.*,ARRAY(SELECT r.public_id
             FROM cafeteria.cookbook_recipes cr JOIN cafeteria.recipes r ON r.id=cr.recipe_id AND r.location_id=cr.location_id
             WHERE cr.cookbook_id=c.id AND cr.location_id=c.location_id ORDER BY cr.sort_order) AS recipe_ids
            FROM cafeteria.cookbooks c WHERE c.location_id=:location AND c.public_id=CAST(:id AS uuid)'''),
            {'location': location, 'id': public_id}).one_or_none()
        if row is None:
            raise RecipeNotFoundError('Kochbuch nicht gefunden.')
        return CookbookDTO(str(row.public_id), row.row_version, row.name, row.description, row.active,
                           tuple(str(value) for value in row.recipe_ids))
