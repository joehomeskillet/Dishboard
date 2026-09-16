"""Wave-0 receipts bundle for MP-REC-BINDINGS (no product schema)."""
from __future__ import annotations

from pathlib import Path

RECEIPTS = Path(__file__).resolve().parent / 'bindings-receipts-0915.md'
LIVE = 'e0da7ab'
CRITERIA = (
    'Nicht-NULL-Roundtrip fuer menu_item_components.recipe_revision_id',
    'Legacy-Zweifeldersatz verliert keine vorhandene Rezeptreferenz',
    'Standortfremde Revision wird mit 23514',
    'Akteurs- und Positions-CAS greifen',
    'Textgleicher Revisionswechsel und Wechsel zurueck verwerfen alte Reviewtokens',
    'Vorwochenkopie erhaelt die exakte Revision',
    'Vollstaendiger Menue-CSV-Ersatz loescht eine reine Rezeptbindung nicht still',
    'Bereits veroeffentlichte Wochen behalten ihren Publikationshash',
)


def test_receipts_file_maps_every_acceptance_criterion() -> None:
    text = RECEIPTS.read_text(encoding='utf-8')
    assert LIVE in text
    assert 'GATE_EXIT=' in text
    for criterion in CRITERIA:
        assert criterion in text, criterion
        block_start = text.index(criterion)
        block = text[block_start:block_start + 900]
        assert 'test_anchor:' in block, criterion
        assert 'coverage:' in block, criterion
