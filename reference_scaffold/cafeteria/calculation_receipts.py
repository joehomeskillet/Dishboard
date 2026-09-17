"""Append-only calculation receipts. Patient guard remains unchanged."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from .patient_payload import PATIENT_FORBIDDEN_COST_KEYS
from .shopping_list_reads import ShoppingScope


class CalculationReceiptConflictError(ValueError):
    pass


def append_receipt(
    engine: Engine, scope: ShoppingScope, *, kind: str, subject_public_id: str, payload: Mapping[str, Any],
) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(blob.encode('utf-8')).hexdigest()
    subject = str(UUID(subject_public_id))
    with engine.begin() as connection:
        try:
            inserted = connection.execute(text('''
                INSERT INTO cafeteria.calculation_receipts(
                    location_id, kind, subject_public_id, payload, content_hash_sha256, created_by)
                VALUES (:location, :kind, CAST(:subject AS uuid), CAST(:payload AS jsonb), :hash, :actor)
                ON CONFLICT ON CONSTRAINT calculation_receipts_subject_key DO NOTHING
                RETURNING public_id
            '''), {
                'location': scope.location_id, 'kind': kind, 'subject': subject,
                'payload': blob, 'hash': digest, 'actor': scope.actor_id,
            }).scalar_one_or_none()
        except DBAPIError as error:
            raise CalculationReceiptConflictError('Kalkulationsbeleg konnte nicht gespeichert werden.') from error
        if inserted is not None:
            return str(inserted)
        existing = connection.execute(text('''
            SELECT public_id, content_hash_sha256 FROM cafeteria.calculation_receipts
            WHERE location_id=:location AND kind=:kind AND subject_public_id=CAST(:subject AS uuid)
        '''), {'location': scope.location_id, 'kind': kind, 'subject': subject}).mappings().one()
        if existing['content_hash_sha256'] == digest:
            return str(existing['public_id'])
        raise CalculationReceiptConflictError('Kalkulationsbeleg existiert bereits mit anderem Inhalt.')


def patient_forbidden_keys() -> frozenset[str]:
    return PATIENT_FORBIDDEN_COST_KEYS
