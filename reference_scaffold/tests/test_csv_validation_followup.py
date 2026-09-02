from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pytest

from cafeteria.csvio import validate_upload

ROOT = Path(__file__).resolve().parents[2]
SENSITIVE_PATIENT_TEXT = re.compile(
    r'CHF|Intern|Extern|0\.00|Preis|price|rappen|kosten|cost|titel',
    re.I,
)
MENU_VALUE_FIELDS = (
    'external_id',
    'titel',
    'beschreibung',
    'beilagen',
    'labels',
    'allergene_enthaelt',
    'allergene_spuren',
    'herkunft',
    'hinweis',
    'preis_mitarbeitende_chf',
    'preis_externe_chf',
)


def _example_rows(name: str) -> tuple[list[str], list[dict[str, str]]]:
    text_value = (ROOT / 'csv' / name).read_text(encoding='utf-8-sig')
    reader = csv.DictReader(io.StringIO(text_value), delimiter=';')
    return list(reader.fieldnames or []), list(reader)


def _validate(headers: list[str], rows: list[dict[str, str]]) -> dict[str, object]:
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return validate_upload(io.BytesIO(buffer.getvalue().encode()))


def _close(row: dict[str, str], notice: str) -> None:
    row['zustand'] = 'geschlossen'
    row['zustand_text'] = notice
    for field in MENU_VALUE_FIELDS:
        if field in row:
            row[field] = ''


def _positions(result: dict[str, object]) -> set[tuple[int, int]]:
    return {
        (int(issue['line']), int(issue['column']))
        for issue in result['issues']  # type: ignore[union-attr]
    }


def test_service_rows_reject_mixed_open_and_closed_state_at_both_rows() -> None:
    """Picking matching[0] hides the second row's conflicting service state."""
    headers, rows = _example_rows('menu_patient_example.csv')
    _close(rows[0], 'Mittagsservice geschlossen')

    result = _validate(headers, rows)

    assert result['valid'] is False
    assert {(2, 16), (3, 16)} <= _positions(result)


def test_service_rows_reject_different_normalized_notices_at_both_rows() -> None:
    """Two closure rows with different notices cannot silently use the first notice."""
    headers, rows = _example_rows('menu_patient_example.csv')
    _close(rows[0], 'Mittagsservice geschlossen')
    _close(rows[1], 'Anderer Hinweis')

    result = _validate(headers, rows)

    assert result['valid'] is False
    assert {(2, 17), (3, 17)} <= _positions(result)


def test_service_rows_compare_notices_after_whitespace_normalization() -> None:
    """Equivalent closure notices remain a valid fixed-grid service."""
    headers, rows = _example_rows('menu_patient_example.csv')
    _close(rows[0], '  Mittagsservice geschlossen  ')
    _close(rows[1], 'Mittagsservice geschlossen')

    result = _validate(headers, rows)

    assert result['valid'] is True
    service = result['values']['days'][0]['services'][0]  # type: ignore[index]
    assert service['service_state'] == 'closed'
    assert service['notice'] == 'Mittagsservice geschlossen'


@pytest.mark.parametrize(
    ('field', 'value', 'column'),
    (
        ('labels', 'UNKNOWN_LABEL', 11),
        ('allergene_enthaelt', 'UNKNOWN_ALLERGEN', 12),
        ('allergene_spuren', 'UNKNOWN_ALLERGEN', 13),
    ),
)
def test_unknown_reference_code_is_positioned_before_preview(
    field: str,
    value: str,
    column: int,
) -> None:
    """Unknown SELECT codes used to disappear silently during persistence."""
    headers, rows = _example_rows('menu_patient_example.csv')
    rows[5][field] = value

    result = _validate(headers, rows)

    assert result['valid'] is False
    assert (7, column) in _positions(result)


@pytest.mark.parametrize(
    ('contains', 'traces', 'labels', 'origins', 'columns'),
    (
        ('', '', 'VEGAN|VEGAN', '', {11}),
        ('MILK|MILK', '', '', '', {12}),
        ('MILK', 'MILK', '', '', {12, 13}),
        ('', '', '', 'Poulet=CH|Poulet=CH', {14}),
        ('', '', '', 'Poulet=CH|Poulet=DE', {14}),
    ),
)
def test_duplicate_pipe_values_are_positioned_validation_issues(
    contains: str,
    traces: str,
    labels: str,
    origins: str,
    columns: set[int],
) -> None:
    """Duplicate relation keys must fail before a database uniqueness error."""
    headers, rows = _example_rows('menu_patient_example.csv')
    row = rows[5]
    row['allergene_enthaelt'] = contains
    row['allergene_spuren'] = traces
    row['labels'] = labels
    row['herkunft'] = origins

    result = _validate(headers, rows)

    assert result['valid'] is False
    assert {(7, column) for column in columns} <= _positions(result)


def test_patient_semantic_policy_reports_real_row_and_field_without_reflection() -> None:
    """Snapshot preflight used to collapse a row-seven title error to line 1, column 1."""
    headers, rows = _example_rows('menu_patient_example.csv')
    rows[5]['titel'] = 'CHF Intern Extern 0.00 Rappen'

    result = _validate(headers, rows)

    assert result['valid'] is False
    matching = [
        issue
        for issue in result['issues']  # type: ignore[union-attr]
        if issue['line'] == 7 and issue['column'] == 8
    ]
    assert matching
    assert all(SENSITIVE_PATIENT_TEXT.search(str(issue['message'])) is None for issue in matching)


@pytest.mark.parametrize(
    ('field', 'column'),
    (
        ('preis_mitarbeitende_chf', 18),
        ('preis_externe_chf', 19),
    ),
)
def test_staff_price_parse_error_uses_exact_header_column(field: str, column: int) -> None:
    """A shared Kostenfeld error used to misreport every price failure as column 18."""
    headers, rows = _example_rows('menu_cafeteria_example.csv')
    rows[3][field] = 'ungueltig'

    result = _validate(headers, rows)

    assert result['valid'] is False
    assert (5, column) in _positions(result)
