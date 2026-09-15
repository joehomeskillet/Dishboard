"""Wave-0 receipts bundle for MP-BAS-FOUNDATIONS (no product schema)."""
from __future__ import annotations

from pathlib import Path

RECEIPTS = Path(__file__).resolve().parent / 'foundations-receipts-0915.md'
LIVE = 'e0da7ab'
CRITERIA = (
    'Ein Lebensmittel ohne Lagerauswahl kann nicht gespeichert werden',
    'Ein Lebensmittel mit genau einem Lagerort verliert diesen bei reiner Namensaenderung nicht',
    'Eine wirksame Aenderung erhoeht die Version genau um 1',
    'Das Entfernen des letzten Lagerorts wird abgelehnt',
    'Der vorbereitete Pin zeigt Revisions-UUID und 64-stelligen Hash',
    'Kein Bestand erfasst',
    'Es entsteht kein zweiter Lagerdienst',
    'UI-Master vollständig gelesen',
    'keyboard/NoJS/200%Zoom',
)


def test_receipts_file_maps_every_acceptance_criterion() -> None:
    text = RECEIPTS.read_text(encoding='utf-8')
    assert LIVE in text
    assert 'GATE_EXIT=' in text
    for criterion in CRITERIA:
        assert criterion in text, criterion
        block_start = text.index(criterion)
        block = text[block_start:block_start + 800]
        assert 'test_anchor:' in block, criterion
        assert 'coverage:' in block, criterion
