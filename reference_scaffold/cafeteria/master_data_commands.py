"""Fixed bound definer commands and outer database-failure translation."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .auth.local_users import ActorExpectation
from .component_catalog_store import ComponentCatalogConfigurationError, resolve_single_active_location_connection
from .master_data_proposals import identifier, normalize, positive
from .master_data_types import (
    ActorDeniedError, MasterDataConfigurationError, MasterDataConflictError,
    MasterDataNotFoundError, MasterDataUnavailableError, MasterDataValidationError,
    MutationResult, ObjectExpectation, ProposalDecision, StaleActorError, StaleObjectError,
)


P = ParamSpec('P')
T = TypeVar('T')
_ERRORS = {
    'P1901': MasterDataValidationError, 'P1902': ActorDeniedError,
    'P1903': StaleActorError, '22023': MasterDataNotFoundError,
    '55000': MasterDataConflictError, '23505': MasterDataConflictError,
    '42501': ActorDeniedError,
}


def safe(function: Callable[P, T]) -> Callable[P, T]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return function(*args, **kwargs)
        except ComponentCatalogConfigurationError:
            raise MasterDataConfigurationError('Genau ein aktiver Standort ist erforderlich.') from None
        except SQLAlchemyError as exc:
            original = getattr(exc, 'orig', None)
            state = getattr(original, 'sqlstate', '')
            detail = getattr(getattr(original, 'diag', None), 'message_detail', '') or ''
            if detail == 'master_location':
                raise MasterDataConfigurationError('Standortkonfiguration wurde geändert.') from None
            if detail == 'stale_object':
                raise StaleObjectError('Der Datensatz wurde zwischenzeitlich geändert.') from None
            if detail.startswith('storage_assignments:'):
                count = detail.removeprefix('storage_assignments:')
                if count.isascii() and count.isdigit() and len(count) <= 19:
                    raise MasterDataConflictError(f'Der Lagerort ist noch {count} Zutaten zugeordnet.') from None
            error = _ERRORS.get(state, MasterDataUnavailableError)
            raise error('Stammdatenaktion derzeit nicht möglich.') from None
    return wrapped


_SQL = {
    'create_food_category': '''SELECT cafeteria.create_food_category_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'update_food_category': '''SELECT cafeteria.update_food_category_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'set_active_food_category': '''SELECT cafeteria.set_active_food_category_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'create_tag': '''SELECT cafeteria.create_tag_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'update_tag': '''SELECT cafeteria.update_tag_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'set_active_tag': '''SELECT cafeteria.set_active_tag_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'create_storage_location': '''SELECT cafeteria.create_storage_location_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'update_storage_location': '''SELECT cafeteria.update_storage_location_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'set_active_storage_location': '''SELECT cafeteria.set_active_storage_location_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'create_unit': '''SELECT cafeteria.create_unit_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'rename_unit': '''SELECT cafeteria.rename_unit_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'set_active_unit': '''SELECT cafeteria.set_active_unit_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'create_food': '''SELECT cafeteria.create_food_v27(
        :actor, :actor_version, :location, CAST(:payload AS jsonb))''',
    'update_food': '''SELECT cafeteria.update_food_v27(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'set_food_active': '''SELECT cafeteria.set_food_active_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'replace_food_tags': '''SELECT cafeteria.replace_food_tags_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'replace_food_metadata': '''SELECT cafeteria.replace_food_metadata_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'set_food_allergen_review': '''SELECT cafeteria.set_food_allergen_review_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'replace_food_storage_locations': '''SELECT cafeteria.replace_food_storage_locations_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'create_proposal': '''SELECT cafeteria.create_proposal_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'accept_proposal': '''SELECT cafeteria.accept_proposal_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
    'reject_proposal': '''SELECT cafeteria.reject_proposal_v21(
        :actor, :actor_version, :location, CAST(:target AS uuid),
        CAST(:target_version AS bigint), CAST(:payload AS jsonb))''',
}


def command(engine: Engine, name: str, actor: ActorExpectation,
            target: ObjectExpectation | None, payload: Mapping[str, object], *,
            original_location: int | None = None) -> dict[str, Any]:
    if not isinstance(actor, ActorExpectation):
        raise MasterDataValidationError('Ungültige Akteurserwartung.')
    values: dict[str, Any] = {'actor': positive(actor.user_id), 'actor_version': positive(actor.authz_version),
                              'target': None, 'target_version': None}
    if original_location is not None:
        original_location = positive(original_location)
    if name in {'create_food', 'update_food'} and 'storage_location_public_ids' not in payload:
        raise MasterDataValidationError('Mindestens einen Lagerort auswählen.')
    if target is not None:
        if not isinstance(target, ObjectExpectation):
            raise MasterDataValidationError('Ungültige Objekterwartung.')
        values.update(target=identifier(target.public_id), target_version=positive(target.row_version))
    try:
        values['payload'] = json.dumps(normalize(payload), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, (MasterDataValidationError, MasterDataNotFoundError)):
            raise
        raise MasterDataValidationError('Ungültige Eingabedaten.') from None
    if engine is None:
        raise MasterDataUnavailableError('Stammdaten sind derzeit nicht verfügbar.')
    with engine.begin() as connection:
        current_location = resolve_single_active_location_connection(connection)
        if original_location is not None and current_location != original_location:
            raise MasterDataConfigurationError('Der ursprüngliche Standort ist nicht mehr aktiv.')
        values['location'] = original_location if original_location is not None else current_location
        return dict(connection.execute(text(_SQL[name]), values).scalar_one())


def mutation(engine: Engine, name: str, actor: ActorExpectation,
             target: ObjectExpectation | None, payload: Mapping[str, object], *,
             original_location: int | None = None) -> MutationResult:
    row = command(engine, name, actor, target, payload, original_location=original_location)
    return MutationResult(str(row['public_id']), int(row['row_version']))


def decision(row: Mapping[str, Any]) -> ProposalDecision:
    return ProposalDecision(row['status'], datetime.fromisoformat(row['decided_at']),
        tuple(row['adopted']), tuple(row['unchanged']), tuple(row['not_supported']),
        row['food_public_id'], row['food_row_version_before'], row['food_row_version_after'])
