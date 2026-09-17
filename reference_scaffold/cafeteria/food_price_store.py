"""Dated purchase-price ledger. Append-only editions; get_price_on needs a revision UUID."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .auth.local_users import ActorExpectation
from .component_catalog_store import ComponentCatalogConfigurationError, resolve_single_active_location_connection
from .master_data_types import (
    ActorDeniedError, MasterDataConfigurationError, MasterDataConflictError,
    MasterDataNotFoundError, MasterDataUnavailableError, MasterDataValidationError,
    StaleActorError, StaleObjectError,
)

_ERRORS = {
    'P1901': MasterDataValidationError, 'P1902': ActorDeniedError,
    'P1903': StaleActorError, '22023': MasterDataNotFoundError,
    '55000': MasterDataConflictError, '23505': MasterDataConflictError,
    '42501': ActorDeniedError,
}


def _mapped(exc: SQLAlchemyError) -> Exception:
    original = getattr(exc, 'orig', None)
    state = getattr(original, 'sqlstate', '') or ''
    detail = getattr(getattr(original, 'diag', None), 'message_detail', '') or ''
    if detail == 'master_location':
        return MasterDataConfigurationError('Standortkonfiguration wurde geändert.')
    if detail == 'stale_object':
        return StaleObjectError('Der Datensatz wurde zwischenzeitlich geändert.')
    return _ERRORS.get(state, MasterDataUnavailableError)('Preisaktion derzeit nicht möglich.')


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as error:
        raise MasterDataValidationError('Ungültige ID.') from error


def append_price_revision(
    engine: Engine, actor: ActorExpectation, food_public_id: str, *,
    intervals: Sequence[Mapping[str, Any]], expected_head_version: int | None = None,
    original_location: int | None = None,
) -> dict[str, Any]:
    if not isinstance(actor, ActorExpectation):
        raise MasterDataValidationError('Ungültige Akteurserwartung.')
    payload = json.dumps({'intervals': list(intervals)}, ensure_ascii=False, allow_nan=False)
    try:
        with engine.begin() as connection:
            location = resolve_single_active_location_connection(connection)
            if original_location is not None and location != original_location:
                raise MasterDataConfigurationError('Der ursprüngliche Standort ist nicht mehr aktiv.')
            row = connection.execute(text(
                '''SELECT cafeteria.append_food_price_revision_v36(
                    :actor, :actor_version, :location, CAST(:food AS uuid),
                    CAST(:head_version AS bigint), CAST(:payload AS jsonb))'''
            ), {
                'actor': actor.user_id, 'actor_version': actor.authz_version,
                'location': location, 'food': _uuid(food_public_id, 'food_public_id'),
                'head_version': expected_head_version, 'payload': payload,
            }).scalar_one()
    except ComponentCatalogConfigurationError as error:
        raise MasterDataConfigurationError('Genau ein aktiver Standort ist erforderlich.') from error
    except SQLAlchemyError as error:
        raise _mapped(error) from error
    return dict(row)


def list_price_revisions(engine: Engine, food_public_id: str) -> tuple[dict[str, Any], ...]:
    food = _uuid(food_public_id, 'food_public_id')
    with engine.connect() as connection:
        rows = connection.execute(text('''
            SELECT r.public_id, r.revision_number, r.edition_json, r.content_hash_sha256,
                   r.created_at, h.row_version AS head_row_version, h.public_id AS head_public_id,
                   (h.current_revision_id = r.id) AS is_current
            FROM cafeteria.food_purchase_price_revisions r
            JOIN cafeteria.food_price_heads h ON h.id = r.head_id
            JOIN cafeteria.foods f ON f.id = r.food_id
            WHERE f.public_id = CAST(:food AS uuid)
            ORDER BY r.revision_number
        '''), {'food': food}).mappings().all()
    return tuple(dict(row) for row in rows)


def get_price_on(
    engine: Engine, food_public_id: str, on_date: date, price_revision_uuid: str,
) -> dict[str, Any] | None:
    food = _uuid(food_public_id, 'food_public_id')
    revision = _uuid(price_revision_uuid, 'price_revision_uuid')
    with engine.connect() as connection:
        row = connection.execute(text('''
            SELECT r.edition_json, r.public_id
            FROM cafeteria.food_purchase_price_revisions r
            JOIN cafeteria.foods f ON f.id = r.food_id
            WHERE r.public_id = CAST(:revision AS uuid)
              AND f.public_id = CAST(:food AS uuid)
        '''), {'revision': revision, 'food': food}).mappings().one_or_none()
    if row is None:
        raise MasterDataNotFoundError('Preisrevision nicht gefunden.')
    intervals = row['edition_json'].get('intervals') or []
    for item in intervals:
        start = date.fromisoformat(str(item['valid_from']))
        raw_end = item.get('valid_to')
        end = date.fromisoformat(str(raw_end)) if raw_end not in (None, 'null') else None
        if on_date < start:
            continue
        if end is not None and on_date >= end:
            continue
        return {
            'revision_public_id': str(row['public_id']),
            'entry_id': str(item['entry_id']),
            'unit_price': Decimal(str(item['unit_price'])),
            'currency': item.get('currency') or 'CHF',
            'yield_factor': None if item.get('yield_factor') in (None, 'null') else Decimal(str(item['yield_factor'])),
            'unit': dict(item['unit']),
            'valid_from': start,
            'valid_to': end,
        }
    return None
