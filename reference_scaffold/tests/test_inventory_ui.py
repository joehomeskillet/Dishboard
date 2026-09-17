"""Inventory UI never shows a fake zero stock."""
from pathlib import Path


def test_lager_template_unknown_label() -> None:
    text = (Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin' / 'lager.html').read_text(encoding='utf-8')
    assert 'Kein Bestand erfasst' in text
    assert 'BESTELLEN' not in text
