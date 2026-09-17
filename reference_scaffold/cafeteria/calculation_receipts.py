"""Append-only calculation receipts. Patient guard remains unchanged."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import Engine, text

from .patient_payload import PATIENT_FORBIDDEN_COST_KEYS
from .shopping_list_reads import ShoppingScope


def append_receipt(
    engine: Engine, scope: ShoppingScope, *, kind: str, subject_public_id: str, payload: Mapping[str, Any],
) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(blob.encode('utf-8')).hexdigest()
    with engine.begin() as connection:
        return str(connection.execute(text('''
            INSERT INTO cafeteria.calculation_receipts(
                location_id, kind, subject_public_id, payload, content_hash_sha256, created_by)
            VALUES (:location, :kind, CAST(:subject AS uuid), CAST(:payload AS jsonb), :hash, :actor)
            RETURNING public_id
        '''), {
            'location': scope.location_id, 'kind': kind, 'subject': str(UUID(subject_public_id)),
            'payload': blob, 'hash': digest, 'actor': scope.actor_id,
        }).scalar_one())


def patient_forbidden_keys() -> frozenset[str]:
    return PATIENT_FORBIDDEN_COST_KEYS
