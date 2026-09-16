"""CAL-MONTH: ISO month grid, default both profiles, no third meal."""
from __future__ import annotations

from datetime import date

from cafeteria.calendar_month import annotate_month, month_weeks


def test_september_2026_starts_on_monday_with_august_lead() -> None:
    weeks = month_weeks(2026, 9)
    assert weeks[0][0] == date(2026, 8, 31)
    assert weeks[0][1] == date(2026, 9, 1)
    assert all(len(week) == 7 for week in weeks)


def test_annotate_default_includes_both_profiles() -> None:
    services = (
        {'profile_code': 'patient', 'service_date': date(2026, 9, 1), 'meal_code': 'LUNCH', 'service_state': 'open'},
        {'profile_code': 'staff_guest', 'service_date': date(2026, 9, 1), 'meal_code': 'LUNCH', 'service_state': 'closed'},
        {'profile_code': 'patient', 'service_date': date(2026, 9, 2), 'meal_code': 'DINNER', 'service_state': 'open'},
    )
    cells = annotate_month(2026, 9, services)
    first_tuesday = cells[0][1]
    assert first_tuesday['date'] == date(2026, 9, 1)
    assert first_tuesday['in_month'] is True
    codes = {row['profile_code'] for row in first_tuesday['services']}
    assert codes == {'patient', 'staff_guest'}


def test_annotate_can_filter_to_cafeteria_only() -> None:
    services = (
        {'profile_code': 'patient', 'service_date': date(2026, 9, 1), 'meal_code': 'LUNCH', 'service_state': 'open'},
        {'profile_code': 'staff_guest', 'service_date': date(2026, 9, 1), 'meal_code': 'LUNCH', 'service_state': 'open'},
    )
    cells = annotate_month(2026, 9, services, profiles=('staff_guest',))
    codes = {row['profile_code'] for row in cells[0][1]['services']}
    assert codes == {'staff_guest'}
