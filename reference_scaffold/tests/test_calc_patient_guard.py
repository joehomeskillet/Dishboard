"""Patient snapshots must reject shipped CALC/receipt keys; old snapshots stay valid."""
from __future__ import annotations

import sys
from copy import deepcopy
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

from cafeteria.cost_calc import CostLine, CostResult  # noqa: E402
from cafeteria.patient_payload import (  # noqa: E402
    PATIENT_ALLOWED_COMPACT_KEYS, PATIENT_FORBIDDEN_COST_KEYS, _normalize_patient_key,
    validate_snapshot_payload,
)
from demo_snapshots import cafeteria_snapshot, patient_snapshot  # noqa: E402

RECEIPT_KEYS = ('receipt', 'receipts', 'receipt_id', 'purchase_price')


def _calc_compact_keys() -> tuple[str, ...]:
    names = [item.name for item in (*dc_fields(CostLine), *dc_fields(CostResult))]
    return tuple(
        compact for name in names
        if (compact := _normalize_patient_key(name)) not in PATIENT_ALLOWED_COMPACT_KEYS
    )


def test_named_deny_list_covers_shipped_cost_dto_fields():
    missing = [key for key in _calc_compact_keys() if key not in PATIENT_FORBIDDEN_COST_KEYS]
    assert missing == []
    for key in RECEIPT_KEYS:
        assert _normalize_patient_key(key) in PATIENT_FORBIDDEN_COST_KEYS


def test_legacy_patient_snapshot_without_cost_keys_remains_valid():
    snapshot = patient_snapshot()
    validate_snapshot_payload('patient', snapshot)
    validate_snapshot_payload('patient', deepcopy(snapshot))


@pytest.mark.parametrize('key', (*_calc_compact_keys(), *RECEIPT_KEYS))
def test_calc_and_receipt_keys_are_rejected_on_patient_option(key):
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][key] = 1
    with pytest.raises(ValueError, match='Kostenschlüssel'):
        validate_snapshot_payload('patient', snapshot)


def test_staff_guest_keeps_sale_price_fields():
    snapshot = cafeteria_snapshot()
    option = snapshot['days'][0]['services'][0]['options'][0]
    assert {'internal_rappen', 'external_rappen'} <= set(option['prices'])
    validate_snapshot_payload('staff_guest', snapshot)
