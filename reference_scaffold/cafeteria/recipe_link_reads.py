"""Scoped read projections for the existing recipe/template/menu edges.

Each list is one bound statement in recipe_reads.connection's read-only snapshot.
Choices read 50 plus a next-page probe and at most one retained recipe head; no
recipe payloads or revision snapshots are loaded to label an option.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, text

from . import recipe_reads as reads
from .dish_template_store import DishTemplate
from .recipe_commands import safe
from .recipe_types import RecipeValidationError
from .recipe_values import identifier
from .roles import require_capability

PAGE_SIZE = 50


@dataclass(frozen=True)
class TemplateLink(DishTemplate):
    recipe_active: bool | None
    revision_count: int
    menu_count: int


@dataclass(frozen=True)
class TemplateReference:
    public_id: str
    title: str
    active: bool
    menu_type_code: str | None
    profile_scope: str


@dataclass(frozen=True)
class RevisionReference:
    public_id: str
    revision_number: int
    created_at: datetime


@dataclass(frozen=True)
class RecipeLinks:
    public_id: str
    templates: tuple[TemplateReference, ...]
    latest_revision: RevisionReference | None


@dataclass(frozen=True)
class RecipeChoice:
    public_id: str
    title: str
    active: bool
    available: bool = True


@dataclass(frozen=True)
class RecipeChoicePage:
    choices: tuple[RecipeChoice, ...]
    retained: RecipeChoice | None
    search: str
    offset: int
    has_next: bool


@safe
@require_capability('draft.read')
def list_template_links(engine: Engine, *, include_archived: bool = False) -> tuple[TemplateLink, ...]:
    if type(include_archived) is not bool:
        raise RecipeValidationError('Ungültiger Vorlagenfilter.')
    with reads.connection(engine) as (current, location):
        rows = current.execute(text('''SELECT d.public_id::text AS public_id,
            d.updated_at,d.active,d.title,d.description,d.profile_scope,d.accompaniment_default,
            mt.code AS menu_type_code,
            r.public_id::text AS recipe_public_id,r.title AS recipe_title,r.active AS recipe_active,
            (SELECT count(*) FROM cafeteria.recipe_revisions h
             WHERE h.recipe_id=r.id AND h.location_id=:location) AS revision_count,
            (SELECT count(*) FROM cafeteria.menu_items i
             JOIN cafeteria.menu_services s ON s.id=i.service_id
             JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
             WHERE i.dish_template_id=d.id AND w.location_id=:location) AS menu_count
            FROM cafeteria.dish_templates d
            LEFT JOIN cafeteria.menu_types mt ON mt.id=d.menu_type_id
            LEFT JOIN cafeteria.recipes r ON r.id=d.recipe_id
            WHERE (:archived OR d.active) AND (d.recipe_id IS NULL OR r.location_id=:location)
            ORDER BY lower(d.title),d.public_id'''),
            {'location': location, 'archived': include_archived}).mappings()
        return tuple(TemplateLink(**row) for row in rows)


@safe
@require_capability('draft.read')
def list_recipe_links(engine: Engine, recipe_public_ids: Sequence[str]) -> dict[str, RecipeLinks]:
    """Project a caller's bounded recipe page, excluding unknown/foreign UUIDs."""
    if isinstance(recipe_public_ids, str) or len(recipe_public_ids) > 500:
        raise RecipeValidationError('Ungültiger Rezeptausschnitt.')
    ids = tuple(dict.fromkeys(identifier(value) for value in recipe_public_ids))
    if not ids:
        return {}
    with reads.connection(engine) as (current, location):
        rows = current.execute(text('''SELECT r.public_id::text AS public_id,
            coalesce((SELECT jsonb_agg(jsonb_build_object(
                'public_id',d.public_id,'title',d.title,'active',d.active,
                'menu_type_code',mt.code,'profile_scope',d.profile_scope)
                ORDER BY lower(d.title),d.public_id)
                FROM cafeteria.dish_templates d
                LEFT JOIN cafeteria.menu_types mt ON mt.id=d.menu_type_id
                WHERE d.recipe_id=r.id),'[]'::jsonb) AS templates,
            latest.public_id::text AS revision_public_id,latest.revision_number,latest.created_at
            FROM cafeteria.recipes r
            LEFT JOIN LATERAL (SELECT h.public_id,h.revision_number,h.created_at
                FROM cafeteria.recipe_revisions h
                WHERE h.recipe_id=r.id AND h.location_id=:location
                ORDER BY h.revision_number DESC,h.public_id LIMIT 1) latest ON true
            WHERE r.location_id=:location
              AND r.public_id=ANY(CAST(string_to_array(:ids,',') AS uuid[]))'''),
            {'location': location, 'ids': ','.join(ids)})
        return {row.public_id: RecipeLinks(
            row.public_id, tuple(TemplateReference(**value) for value in row.templates),
            RevisionReference(row.revision_public_id, row.revision_number, row.created_at)
            if row.revision_public_id else None,
        ) for row in rows}


@safe
@require_capability('draft.read')
def list_recipe_choices(
    engine: Engine, *, selected: str = '', search: str = '', offset: int = 0,
) -> RecipeChoicePage:
    """Search all active heads; retain a bound archived/off-page/unknown value."""
    reads.paging(PAGE_SIZE, offset, False)
    if not isinstance(search, str) or len(search) > 200 or '\x00' in search:
        raise RecipeValidationError('Ungültige Rezeptsuche.')
    try:
        canonical = identifier(selected) if selected else None
    except RecipeValidationError:
        canonical = None
    with reads.connection(engine) as (current, location):
        rows = current.execute(text('''WITH page AS (
            SELECT r.public_id,r.title,r.active FROM cafeteria.recipes r
            WHERE r.location_id=:location AND r.active
              AND strpos(lower(r.title),lower(:search))>0
            ORDER BY lower(r.title),r.public_id LIMIT :limit OFFSET :offset)
            SELECT public_id::text,title,active,false AS retained,lower(title) AS sort_title FROM page
            UNION ALL
            SELECT r.public_id::text,r.title,r.active,true AS retained,lower(r.title) FROM cafeteria.recipes r
            WHERE r.location_id=:location AND r.public_id=CAST(:selected AS uuid)
            ORDER BY retained,sort_title,public_id'''),
            {'location': location, 'search': search, 'limit': PAGE_SIZE + 1,
             'offset': offset, 'selected': canonical}).all()
    page_rows = [row for row in rows if not row.retained]
    choices = tuple(RecipeChoice(row.public_id, row.title, row.active) for row in page_rows[:PAGE_SIZE])
    retained = None
    if selected and selected not in {choice.public_id for choice in choices}:
        found = next((row for row in rows if row.retained), None)
        retained = (RecipeChoice(selected, found.title, found.active) if found
                    else RecipeChoice(selected, 'Rezept nicht verfügbar', False, False))
    return RecipeChoicePage(choices, retained, search, offset, len(page_rows) > PAGE_SIZE)
