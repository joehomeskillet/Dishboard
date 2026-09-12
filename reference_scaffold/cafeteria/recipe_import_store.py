"""Persistent versioned recipe-import drafts; commit creates recipes in one TX."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .auth.local_users import ActorExpectation
from .master_data_types import MutationResult, ObjectExpectation
from .recipe_commands import ERRORS
from .recipe_import_types import RecipeImportPreview
from .recipe_reads import connection
from .recipe_snapshots import frozen_json
from .recipe_types import (
    RecipeConflictError, RecipeNotFoundError, RecipeUnavailableError, RecipeValidationError,
)
from .recipe_values import identifier, positive
from .roles import require_capability

P = ParamSpec('P')
T = TypeVar('T')
CREATE_SQL = (
    'SELECT cafeteria.create_recipe_import_batch_v28('
    ':actor,:authz,:location,CAST(:payload AS jsonb))'
)
UPDATE_SQL = (
    'SELECT cafeteria.update_recipe_import_batch_v28('
    ':actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))'
)
COMMIT_SQL = (
    'SELECT cafeteria.commit_recipe_import_batch_v29('
    ':actor,:authz,:location,CAST(:target AS uuid),CAST(:version AS bigint),CAST(:payload AS jsonb))'
)
ANNOTATIONS = ('unreviewed', 'proposed_not_measured', 'allergen_not_checked')
LIST_SQL = '''SELECT b.public_id::text AS public_id, b.row_version, b.status, b.adapter_kind,
    b.source_filename, b.source_sha256, b.content_type, b.source_url, b.fetched_at,
    b.candidate_hash_sha256, b.confirmation_hash_sha256, b.imported_result, b.annotations,
    b.duplicate_groups, b.created_at, b.updated_at
    FROM cafeteria.recipe_import_batches b
    WHERE b.location_id=:location
    ORDER BY b.created_at DESC, b.public_id'''
CANDIDATE_SQL = '''SELECT row_number, source_line, origin_ref, original_payload, candidate_payload,
    duplicate_decision, target_recipe_public_id::text AS target_recipe_public_id,
    target_row_version, parse_errors, original_source_kind
    FROM cafeteria.recipe_import_candidates
    WHERE batch_id=(SELECT id FROM cafeteria.recipe_import_batches
        WHERE public_id=CAST(:id AS uuid) AND location_id=:location)
    ORDER BY row_number'''


@dataclass(frozen=True)
class RecipeImportCandidate:
    row_number: int
    source_line: int | None
    origin_ref: str
    original_payload: Mapping[str, object]
    candidate_payload: Mapping[str, object]
    duplicate_decision: str
    target_recipe_public_id: str | None
    target_row_version: int | None
    parse_errors: tuple[Mapping[str, object], ...]
    original_source_kind: str


@dataclass(frozen=True)
class RecipeImportBatch:
    public_id: str
    row_version: int
    status: str
    adapter_kind: str
    source_filename: str | None
    source_sha256: str | None
    content_type: str | None
    source_url: str | None
    fetched_at: datetime | None
    candidate_hash_sha256: str
    confirmation_hash_sha256: str | None
    imported_result: tuple[Mapping[str, object], ...]
    annotations: tuple[str, ...]
    duplicate_groups: tuple[Mapping[str, object], ...]
    created_at: datetime
    updated_at: datetime
    candidates: tuple[RecipeImportCandidate, ...] = ()


def thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw(item) for item in value]
    return value


def _safe(function: Callable[P, T]) -> Callable[P, T]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return function(*args, **kwargs)
        except SQLAlchemyError as exc:
            original = getattr(exc, 'orig', None)
            message = getattr(getattr(original, 'diag', None), 'message_primary', None)
            detail = getattr(getattr(original, 'diag', None), 'message_detail', '') or ''
            if detail == 'master_location':
                raise RecipeConflictError('Der ursprüngliche Standort ist nicht mehr aktiv.') from None
            error = ERRORS.get(getattr(original, 'sqlstate', ''), RecipeUnavailableError)
            raise error(message or 'Importaktion derzeit nicht möglich.') from None
    return wrapped


def payload_from_preview(
    preview: RecipeImportPreview, *, annotations: Sequence[str] = (),
    adapter_kind: str = 'file_import',
) -> dict[str, object]:
    if adapter_kind not in ('file_import', 'url', 'ai_assisted'):
        raise RecipeValidationError('Ungültige Quelle.')
    unknown = [item for item in annotations if item not in ANNOTATIONS]
    if unknown or len(annotations) != len(set(annotations)):
        raise RecipeValidationError('Ungültige Importannotation.')
    rows = []
    for row in preview.rows:
        original = thaw(row.payload) if row.payload is not None else {}
        if not isinstance(original, dict):
            original = {}
        rows.append({
            'row_number': row.row_number,
            'source_line': row.source_line,
            'original_payload': original,
            'parse_errors': [
                {'row_number': issue.row_number, 'field': issue.field,
                 'code': issue.code, 'message': issue.message}
                for issue in row.errors
            ],
            'candidate_payload': original,
            'duplicate_decision': 'undecided',
            'target_recipe_public_id': None,
            'target_row_version': None,
        })
    if not rows:
        raise RecipeValidationError('Die Datei muss zwischen 1 und 2000 Rezeptzeilen enthalten.')
    return {
        'adapter_kind': adapter_kind,
        'source_filename': preview.source_filename,
        'source_sha256': preview.source_sha256,
        'content_type': preview.content_type,
        'source_url': None,
        'source_note': None,
        'fetched_at': preview.fetched_at,
        'annotations': list(annotations),
        'duplicate_groups': [
            {'title': group.title, 'row_numbers': list(group.row_numbers)}
            for group in preview.duplicate_groups
        ],
        'rows': rows,
    }


def _dump(payload: Mapping[str, object]) -> str:
    try:
        return json.dumps(thaw(dict(payload)), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise RecipeValidationError('Ungültige Importdaten.') from error


@_safe
def _create(engine: Engine, actor: ActorExpectation, location: int, payload: Mapping[str, object]) -> dict[str, Any]:
    values = {
        'actor': positive(actor.user_id), 'authz': positive(actor.authz_version),
        'location': positive(location), 'payload': _dump(payload),
    }
    with engine.begin() as current:
        return dict(current.execute(text(CREATE_SQL), values).scalar_one())


@_safe
def _update(
    engine: Engine, actor: ActorExpectation, location: int, target: ObjectExpectation,
    payload: Mapping[str, object],
) -> dict[str, Any]:
    values = {
        'actor': positive(actor.user_id), 'authz': positive(actor.authz_version),
        'location': positive(location), 'target': identifier(target.public_id),
        'version': positive(target.row_version), 'payload': _dump(payload),
    }
    with engine.begin() as current:
        return dict(current.execute(text(UPDATE_SQL), values).scalar_one())


def _candidate(row: Mapping[str, Any]) -> RecipeImportCandidate:
    return RecipeImportCandidate(
        row_number=int(row['row_number']),
        source_line=None if row['source_line'] is None else int(row['source_line']),
        origin_ref=str(row['origin_ref']),
        original_payload=frozen_json(row['original_payload'] or {}),
        candidate_payload=frozen_json(row['candidate_payload'] or {}),
        duplicate_decision=str(row['duplicate_decision']),
        target_recipe_public_id=row['target_recipe_public_id'],
        target_row_version=None if row['target_row_version'] is None else int(row['target_row_version']),
        parse_errors=tuple(frozen_json(row['parse_errors'] or [])),
        original_source_kind=str(row['original_source_kind']),
    )


def _batch(row: Mapping[str, Any], candidates: tuple[RecipeImportCandidate, ...] = ()) -> RecipeImportBatch:
    fetched = row['fetched_at']
    return RecipeImportBatch(
        public_id=str(row['public_id']), row_version=int(row['row_version']),
        status=str(row['status']), adapter_kind=str(row['adapter_kind']),
        source_filename=row['source_filename'], source_sha256=row['source_sha256'],
        content_type=row['content_type'], source_url=row['source_url'],
        fetched_at=fetched, candidate_hash_sha256=str(row['candidate_hash_sha256']),
        confirmation_hash_sha256=row['confirmation_hash_sha256'],
        imported_result=tuple(frozen_json(row['imported_result'] or [])),
        annotations=tuple(row['annotations'] or ()),
        duplicate_groups=tuple(frozen_json(row['duplicate_groups'] or [])),
        created_at=row['created_at'], updated_at=row['updated_at'], candidates=candidates,
    )


@require_capability('recipe.write')
def list_batches(engine: Engine) -> tuple[RecipeImportBatch, ...]:
    with connection(engine) as (current, location):
        rows = current.execute(text(LIST_SQL), {'location': location}).mappings()
        return tuple(_batch(dict(row)) for row in rows)


@require_capability('recipe.write')
def get_batch(engine: Engine, public_id: str) -> RecipeImportBatch:
    public_id = identifier(public_id)
    with connection(engine) as (current, location):
        row = current.execute(
            text(LIST_SQL.replace(
                'WHERE b.location_id=:location',
                'WHERE b.location_id=:location AND b.public_id=CAST(:id AS uuid)',
            )),
            {'location': location, 'id': public_id},
        ).mappings().one_or_none()
        if row is None:
            raise RecipeNotFoundError('Unbekannter Importstapel.')
        candidates = tuple(
            _candidate(dict(item))
            for item in current.execute(text(CANDIDATE_SQL), {'location': location, 'id': public_id}).mappings()
        )
        return _batch(dict(row), candidates)


@require_capability('recipe.write')
def create_batch(
    engine: Engine, actor: ActorExpectation, payload: Mapping[str, object], *,
    expected_location_id: int,
) -> MutationResult:
    if not isinstance(actor, ActorExpectation):
        raise RecipeValidationError('Originalakteur erforderlich.')
    with connection(engine) as (_, location):
        if location != expected_location_id:
            raise RecipeConflictError('Der ursprüngliche Standort ist nicht mehr aktiv.')
    result = _create(engine, actor, expected_location_id, payload)
    return MutationResult(str(result['public_id']), int(result['row_version']))


@require_capability('recipe.write')
def update_batch(
    engine: Engine, actor: ActorExpectation, target: ObjectExpectation,
    payload: Mapping[str, object], *, expected_location_id: int,
) -> MutationResult:
    if not isinstance(actor, ActorExpectation):
        raise RecipeValidationError('Originalakteur erforderlich.')
    if not isinstance(target, ObjectExpectation):
        raise RecipeValidationError('Originalobjekt erforderlich.')
    with connection(engine) as (_, location):
        if location != expected_location_id:
            raise RecipeConflictError('Der ursprüngliche Standort ist nicht mehr aktiv.')
    result = _update(engine, actor, expected_location_id, target, payload)
    return MutationResult(str(result['public_id']), int(result['row_version']))


@_safe
def _commit(
    engine: Engine, actor: ActorExpectation, location: int, target: ObjectExpectation,
    payload: Mapping[str, object],
) -> dict[str, Any]:
    values = {
        'actor': positive(actor.user_id), 'authz': positive(actor.authz_version),
        'location': positive(location), 'target': identifier(target.public_id),
        'version': positive(target.row_version), 'payload': _dump(payload),
    }
    with engine.begin() as current:
        return dict(current.execute(text(COMMIT_SQL), values).scalar_one())


@require_capability('recipe.import')
def commit_batch(
    engine: Engine, actor: ActorExpectation, target: ObjectExpectation,
    payload: Mapping[str, object], *, expected_location_id: int,
) -> MutationResult:
    if not isinstance(actor, ActorExpectation):
        raise RecipeValidationError('Originalakteur erforderlich.')
    if not isinstance(target, ObjectExpectation):
        raise RecipeValidationError('Originalobjekt erforderlich.')
    with connection(engine) as (_, location):
        if location != expected_location_id:
            raise RecipeConflictError('Der ursprüngliche Standort ist nicht mehr aktiv.')
    result = _commit(engine, actor, expected_location_id, target, payload)
    return MutationResult(str(result['public_id']), int(result['row_version']))
