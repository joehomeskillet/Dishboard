"""Wave-0 receipts bundle for MP-REC-SNAPSHOT-V2."""
from __future__ import annotations

from pathlib import Path

RECEIPTS = Path(__file__).resolve().parent / 'snapshot-v2-receipts-0915.md'
LIVE = 'e0da7ab'
CRITERIA = (
    'v1-PDFbytes und v1-Snapshot-/Hashbelege bleiben bytegleich',
    'zwei Geschwister mit gemeinsamen Enkeln',
    'fehlende/zusätzliche/falsche IDs',
    'v2-PDF und Skalierungsdarstellung',
    'exakte Recipe/Revision/Assetauswahl',
)


def test_receipts_file_maps_every_acceptance_criterion() -> None:
    text = RECEIPTS.read_text(encoding='utf-8')
    assert LIVE in text
    assert 'GATE_EXIT=' in text
    assert 'PG18' in text
    for criterion in CRITERIA:
        assert criterion in text, criterion
        block_start = text.index(criterion)
        block = text[block_start:block_start + 900]
        assert 'test_anchor:' in block, criterion
        assert 'coverage:' in block, criterion
