"""Calculation receipts keep patient cost keys forbidden."""
from cafeteria.calculation_receipts import patient_forbidden_keys
from cafeteria.patient_payload import PATIENT_FORBIDDEN_COST_KEYS


def test_patient_guard_unchanged() -> None:
    keys = patient_forbidden_keys()
    assert keys is PATIENT_FORBIDDEN_COST_KEYS
    assert 'costtotal' in keys
