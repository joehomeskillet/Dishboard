"""Bounded immutable recipe-revision choices for the menu editor.

Every label comes from the frozen revision snapshot. The mutable recipe head never
relabels a revision, so renaming or rescaling a recipe cannot change what an
already frozen option claims to be. A revision whose stored snapshot does not
carry title, servings and unit stays bound and readable as an unavailable
historical state; it never borrows head metadata and never becomes a new choice.

The reader stays inside the read boundary the menu editor already used: the
single-active-location ``REPEATABLE READ READ ONLY`` transaction of
``recipe_reads.connection``, the ``draft.read`` capability and the ``safe`` error
mapping of ``recipe_store``. It adds no schema, permission, endpoint or migration.

Cost boundary: one bounded page statement plus at most one bounded statement for
the selection retained outside that page. Neither statement count nor page row
count grows with the number of recipes or revisions. Title and yield are projected
inside PostgreSQL, so a multi-megabyte snapshot closure is never transferred to
label an option.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, Row, text

from . import recipe_reads as reads
from .recipe_commands import safe
from .recipe_types import RecipeValidationError
from .recipe_values import identifier
from .roles import require_capability

CHOICE_PAGE_LIMIT = 50
SEARCH_MAX_LENGTH = 200

_PROJECTION = '''SELECT h.public_id AS revision_public_id,r.public_id AS recipe_public_id,
 h.revision_number AS revision_number,h.content_hash_sha256 AS content_hash,r.active AS recipe_active,
 h.snapshot_json #>> '{recipe,title}' AS title,
 h.snapshot_json #>> '{recipe,servings}' AS servings,
 h.snapshot_json #>> '{recipe,servings_unit_code}' AS unit_code
 FROM cafeteria.recipe_revisions h
 JOIN cafeteria.recipes r ON r.id=h.recipe_id AND r.location_id=h.location_id'''
# Unique total order: the trailing revision public_id makes the page deterministic
# even for revisions that froze the same title.
_ORDER = ''' ORDER BY lower(coalesce(h.snapshot_json #>> '{recipe,title}','')),r.public_id,
 h.revision_number DESC,h.public_id'''
_PAGE_SQL = _PROJECTION + '''
 WHERE h.location_id=:location AND r.active
 AND strpos(lower(coalesce(h.snapshot_json #>> '{recipe,title}','')),lower(:search))>0''' + _ORDER + '''
 LIMIT :limit OFFSET :offset'''
_SELECTED_SQL = _PROJECTION + '''
 WHERE h.location_id=:location AND h.public_id=ANY(CAST(string_to_array(:ids,',') AS uuid[]))''' + _ORDER


@dataclass(frozen=True)
class RecipeChoice:
    """One option of the bounded choice contract, labelled from its own snapshot."""

    revision_public_id: str
    recipe_public_id: str
    revision_number: int | None
    content_hash_sha256: str
    title: str
    yield_label: str
    recipe_active: bool
    metadata_available: bool

    @property
    def selectable(self) -> bool:
        """A new binding needs readable immutable metadata on an active recipe."""
        return self.metadata_available and self.recipe_active


@dataclass(frozen=True)
class RecipeChoiceQuery:
    """Requested page of the full eligible revision set; search covers that set."""

    search: str = ''
    limit: int = CHOICE_PAGE_LIMIT
    offset: int = 0


@dataclass(frozen=True)
class RecipeChoicePage:
    """Bounded page plus the selection retained outside it.

    ``choices`` are the offered options of the requested page. ``retained`` holds
    the currently bound revisions that the page or search does not contain,
    including archived and unreadable ones, so a selection never disappears.
    ``has_next`` is real next-page evidence read from one extra probed row.
    """

    query: RecipeChoiceQuery
    choices: tuple[RecipeChoice, ...]
    retained: tuple[RecipeChoice, ...]
    has_next: bool
    next_offset: int | None
    previous_offset: int | None


EMPTY_RECIPE_PAGE = RecipeChoicePage(
    query=RecipeChoiceQuery(), choices=(), retained=(), has_next=False,
    next_offset=None, previous_offset=None,
)


def _page_values(query: RecipeChoiceQuery) -> dict[str, object]:
    if not isinstance(query, RecipeChoiceQuery):
        raise RecipeValidationError('Ungültiger Auswahlausschnitt.')
    search = query.search
    if not isinstance(search, str) or len(search) > SEARCH_MAX_LENGTH or '\x00' in search:
        raise RecipeValidationError('Ungültige Suche.')
    values = reads.paging(query.limit, query.offset, False)
    values.pop('archived')
    values['search'] = search
    # One extra row is next-page evidence, not a widened page.
    values['limit'] = query.limit + 1
    return values


def _requested(selected: Sequence[object]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split submitted bindings into canonical identifiers and unreadable raw values.

    A non-canonical or malformed value cannot address a revision and is kept as an
    opaque retained entry; it never reaches the database and never discloses metadata.
    """
    canonical: list[str] = []
    unreadable: list[str] = []
    for value in selected:
        if not isinstance(value, str) or value == '':
            continue
        try:
            resolved = identifier(value)
        except RecipeValidationError:
            resolved = ''
        if resolved != value:
            if value not in unreadable:
                unreadable.append(value)
        elif value not in canonical:
            canonical.append(value)
    return tuple(canonical), tuple(unreadable)


def _choice(row: Row[Any]) -> RecipeChoice:
    title, servings, unit = row.title, row.servings, row.unit_code
    available = all(isinstance(value, str) and value != '' for value in (title, servings, unit))
    return RecipeChoice(
        revision_public_id=str(row.revision_public_id),
        recipe_public_id=str(row.recipe_public_id),
        revision_number=int(row.revision_number),
        content_hash_sha256=str(row.content_hash),
        title=str(title) if available else '',
        yield_label=f'{servings} {unit}' if available else '',
        recipe_active=bool(row.recipe_active),
        metadata_available=available,
    )


def unreadable_choice(revision_public_id: str) -> RecipeChoice:
    """Keep an existing binding visible without claiming any metadata for it."""
    return RecipeChoice(
        revision_public_id=revision_public_id, recipe_public_id='', revision_number=None,
        content_hash_sha256='', title='', yield_label='', recipe_active=False,
        metadata_available=False,
    )


def _read_recipe_choices(
    engine: Engine, selected: Sequence[object], query: RecipeChoiceQuery,
) -> RecipeChoicePage:
    values = _page_values(query)
    canonical, unreadable = _requested(selected)
    with reads.connection(engine) as (current, location):
        values['location'] = location
        rows = list(current.execute(text(_PAGE_SQL), values))
        has_next = len(rows) > query.limit
        choices = tuple(_choice(row) for row in rows[:query.limit])
        offered = {choice.revision_public_id for choice in choices}
        outside = tuple(value for value in canonical if value not in offered)
        found = {}
        if outside:
            found = {str(row.revision_public_id): _choice(row) for row in current.execute(
                text(_SELECTED_SQL), {'location': location, 'ids': ','.join(outside)})}
    retained = [found.get(value) or unreadable_choice(value) for value in outside]
    retained.extend(unreadable_choice(value) for value in unreadable)
    return RecipeChoicePage(
        query=query, choices=choices, retained=tuple(retained), has_next=has_next,
        next_offset=query.offset + query.limit if has_next else None,
        previous_offset=max(query.offset - query.limit, 0) if query.offset > 0 else None,
    )


list_recipe_choices = safe(require_capability('draft.read')(_read_recipe_choices))
