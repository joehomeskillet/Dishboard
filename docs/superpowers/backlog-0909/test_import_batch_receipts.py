"""Wave-0 receipts bundle for MP-REC-IMPORT-BATCH."""
from __future__ import annotations

from pathlib import Path

RECEIPTS = Path(__file__).resolve().parent / 'import-batch-receipts-0915.md'
LIVE = 'e0da7ab'
CRITERIA = (
    'Quelldokument/hash/Originalrow bleiben bei Kandidatenedit unverändert',
    'neuer Kandidatenhash/Batchversion invalidiert vorherige Bestätigung',
    'unaufgelöste Food-/Unitzeilen können als Import-draft gespeichert werden',
    'keine automatische Veröffentlichung',
    'GET no-store',
)


def test_receipts_file_maps_every_acceptance_criterion() -> None:
    text = RECEIPTS.read_text(encoding='utf-8')
    assert LIVE in text
    assert 'GATE_EXIT=' in text
    assert 'keine neue Migration' in text
    for criterion in CRITERIA:
        assert criterion in text, criterion
        block_start = text.index(criterion)
        block = text[block_start:block_start + 900]
        assert 'test_anchor:' in block, criterion
        assert 'coverage:' in block, criterion
