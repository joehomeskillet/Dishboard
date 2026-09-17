"""Supplier and article catalog. masterdata.write via SECURITY DEFINER."""
from __future__ import annotations

import json
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .auth.local_users import ActorExpectation
from .component_catalog_store import ComponentCatalogConfigurationError, resolve_single_active_location_connection
from .master_data_types import (
    ActorDeniedError, MasterDataConfigurationError, MasterDataConflictError,
    MasterDataNotFoundError, MasterDataUnavailableError, MasterDataValidationError,
    MutationResult, ObjectExpectation, StaleActorError, StaleObjectError,
)

_ERRORS = {
    'P1901': MasterDataValidationError, 'P1902': ActorDeniedError, 'P1903': StaleActorError,
    '22023': MasterDataNotFoundError, '55000': MasterDataConflictError, '23505': MasterDataConflictError,
}


def _call(engine: Engine, sql: str, actor: ActorExpectation, target: ObjectExpectation | None,
          payload: Mapping[str, Any], original_location: int | None = None) -> MutationResult:
    values = {
        'actor': actor.user_id, 'actor_version': actor.authz_version,
        'target': None if target is None else str(UUID(target.public_id)),
        'target_version': None if target is None else target.row_version,
        'payload': json.dumps(payload, ensure_ascii=False),
    }
    try:
        with engine.begin() as connection:
            location = resolve_single_active_location_connection(connection)
            if original_location is not None and location != original_location:
                raise MasterDataConfigurationError('Der ursprüngliche Standort ist nicht mehr aktiv.')
            values['location'] = location
            row = connection.execute(text(sql), values).scalar_one()
    except ComponentCatalogConfigurationError as error:
        raise MasterDataConfigurationError('Genau ein aktiver Standort ist erforderlich.') from error
    except SQLAlchemyError as error:
        original = getattr(error, 'orig', None)
        state = getattr(original, 'sqlstate', '') or ''
        detail = getattr(getattr(original, 'diag', None), 'message_detail', '') or ''
        if detail == 'stale_object':
            raise StaleObjectError('Der Datensatz wurde zwischenzeitlich geändert.') from error
        raise _ERRORS.get(state, MasterDataUnavailableError)('Lieferantenaktion derzeit nicht möglich.') from error
    return MutationResult(str(row['public_id']), int(row['row_version']))


def create_supplier(engine: Engine, actor: ActorExpectation, payload: Mapping[str, Any], *, original_location: int | None = None) -> MutationResult:
    return _call(engine, '''SELECT cafeteria.supplier_mutate_v38('create', :actor, :actor_version, :location, CAST(:target AS uuid), CAST(:target_version AS bigint), CAST(:payload AS jsonb))''', actor, None, payload, original_location)


def update_supplier(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, payload: Mapping[str, Any], *, original_location: int | None = None) -> MutationResult:
    return _call(engine, '''SELECT cafeteria.supplier_mutate_v38('update', :actor, :actor_version, :location, CAST(:target AS uuid), CAST(:target_version AS bigint), CAST(:payload AS jsonb))''', actor, target, payload, original_location)


def create_article(engine: Engine, actor: ActorExpectation, payload: Mapping[str, Any], *, original_location: int | None = None) -> MutationResult:
    return _call(engine, '''SELECT cafeteria.supplier_article_mutate_v38('create', :actor, :actor_version, :location, CAST(:target AS uuid), CAST(:target_version AS bigint), CAST(:payload AS jsonb))''', actor, None, payload, original_location)


def update_article(engine: Engine, actor: ActorExpectation, target: ObjectExpectation, payload: Mapping[str, Any], *, original_location: int | None = None) -> MutationResult:
    return _call(engine, '''SELECT cafeteria.supplier_article_mutate_v38('update', :actor, :actor_version, :location, CAST(:target AS uuid), CAST(:target_version AS bigint), CAST(:payload AS jsonb))''', actor, target, payload, original_location)


def list_suppliers(engine: Engine, location_id: int) -> tuple[dict[str, Any], ...]:
    with engine.connect() as connection:
        rows = connection.execute(text(
            'SELECT public_id, code, name, active, row_version FROM cafeteria.suppliers '
            'WHERE location_id=:location ORDER BY name'
        ), {'location': location_id}).mappings().all()
    return tuple(dict(row) for row in rows)


def list_articles(engine: Engine, location_id: int, supplier_public_id: str | None = None) -> tuple[dict[str, Any], ...]:
    sql = '''SELECT a.public_id, a.article_code, a.name, a.pack_size, a.preferred, a.active, a.row_version,
                    a.food_id IS NULL AS without_food, u.code AS order_unit_code, s.public_id AS supplier_public_id
             FROM cafeteria.supplier_articles a
             JOIN cafeteria.suppliers s ON s.id=a.supplier_id
             JOIN cafeteria.measurement_units u ON u.id=a.order_unit_id
             WHERE a.location_id=:location'''
    params: dict[str, object] = {'location': location_id}
    if supplier_public_id:
        sql += ' AND s.public_id=CAST(:supplier AS uuid)'
        params['supplier'] = supplier_public_id
    sql += ' ORDER BY a.name'
    with engine.connect() as connection:
        rows = connection.execute(text(sql), params).mappings().all()
    return tuple(dict(row) for row in rows)
