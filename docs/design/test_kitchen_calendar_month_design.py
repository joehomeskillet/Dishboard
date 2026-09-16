"""CAL-DESIGN: month-grid decision names R11 and layout_variant=calendar."""
from pathlib import Path

DOC = Path(__file__).with_name('2026-09-16-kitchen-calendar-month.md')


def test_design_decision_records_r11_and_calendar_variant() -> None:
    text = DOC.read_text(encoding='utf-8')
    assert 'layout_variant=calendar' in text
    assert '390×844' in text
    assert '1440×900' in text
    assert '1024×768' in text
    assert '768×1024' in text
    assert '1920×1080' in text
    assert 'Anlässe als Marker' in text or 'Anlass-Marker' in text
    assert 'Keine vendored Kalenderbibliothek' in text
    assert 'Standard beide' in text
    assert 'Werkzeugleiste' in text
    assert 'Mittagessen' in text
    assert 'Tagesliste' in text
