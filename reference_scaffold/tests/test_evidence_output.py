"""Evidence opt-in changes output locations, never test validation."""
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('flag', [None, '0', 'yes', '1'])
def test_evidence_redirect_requires_explicit_one(tmp_path, monkeypatch, flag):
    from _support.evidence import isolate_evidence
    if flag is None:
        monkeypatch.delenv('UI_EVIDENCE', raising=False)
    else:
        monkeypatch.setenv('UI_EVIDENCE', flag)
    original = tmp_path / 'baseline'
    module = SimpleNamespace(EVIDENCE=original, API_EVIDENCE=original / 'api', OTHER=Path('/unrelated'))
    isolate_evidence.__wrapped__(SimpleNamespace(module=module), tmp_path / 'temporary', monkeypatch)
    if flag == '1':
        assert module.EVIDENCE == original
        assert not original.exists()
    else:
        assert module.EVIDENCE.is_relative_to(tmp_path / 'temporary')
        assert module.EVIDENCE.is_dir()
        assert module.API_EVIDENCE != module.EVIDENCE
        assert not original.exists()
    assert module.OTHER == Path('/unrelated')
