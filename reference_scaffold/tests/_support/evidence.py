"""Opt-in fixture for owned evidence writers; no effect on unmodified modules."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_evidence(request: pytest.FixtureRequest, tmp_path: Path,
                     monkeypatch: pytest.MonkeyPatch) -> None:
    if os.getenv('UI_EVIDENCE') == '1':
        return
    for name in ('EVIDENCE', 'EVIDENCE_DIR', 'API_EVIDENCE'):
        if isinstance(getattr(request.module, name, None), Path):
            target = tmp_path / ('evidence-' + name.lower())
            target.mkdir(parents=True, exist_ok=True)
            # Only output-path constants change. No assertion, validator or app is patched.
            monkeypatch.setattr(request.module, name, target)
