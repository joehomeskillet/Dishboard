from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.test_csv_validation_followup import _example_rows, _validate


def weekend_rows(offsets: tuple[int, ...] = (5, 6)) -> tuple[list[str], list[dict[str, str]]]:
    headers, rows = _example_rows('menu_cafeteria_example.csv')
    monday = min(date.fromisoformat(row['datum']) for row in rows)
    for offset in offsets:
        for original in rows[:2]:
            row = dict(original)
            row.update(datum=(monday + timedelta(days=offset)).isoformat(),
                       wochentag={5: 'Samstag', 6: 'Sonntag'}[offset],
                       external_id=f"weekend-{offset}-{original['menueart']}")
            rows.append(row)
    return headers, rows


@pytest.mark.parametrize('offsets', [(5,), (6,), (5, 6)])
def test_csv_accepts_complete_optional_weekend_pairs(offsets: tuple[int, ...]) -> None:
    headers, rows = weekend_rows(offsets)
    result = _validate(headers, rows)
    assert result['valid'] is True, result['issues']
    values = result['values']
    assert isinstance(values, dict)
    assert len(values['days']) == 5 + len(offsets)
    assert [day['date'] for day in values['days']] == sorted({row['datum'] for row in rows})


@pytest.mark.parametrize('case', ['missing_pair', 'missing_weekday', 'duplicate', 'meal',
                                  'price', 'date', 'mixed_state', 'profile'])
def test_weekend_csv_retains_all_integrity_guards(case: str) -> None:
    headers, rows = weekend_rows()
    if case == 'missing_pair':
        rows.pop()
    elif case == 'missing_weekday':
        del rows[:2]
    elif case == 'duplicate':
        rows.append(dict(rows[-1]))
    elif case == 'meal':
        rows[-1]['mahlzeit'] = 'DINNER'
    elif case == 'price':
        rows[-1]['preis_externe_chf'] = '1.00'
    elif case == 'date':
        rows[-1]['datum'] = (date.fromisoformat(rows[-1]['datum']) + timedelta(days=7)).isoformat()
    elif case == 'mixed_state':
        rows[-1]['zustand'] = 'geschlossen'
    else:
        rows[-1]['profil'] = 'patient'
    assert _validate(headers, rows)['valid'] is False
