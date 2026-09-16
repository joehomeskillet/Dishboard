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


def test_month_weeks_covers_four_five_and_six_week_months() -> None:
    assert len(month_weeks(2021, 2)) == 4
    assert len(month_weeks(2026, 9)) == 5
    assert len(month_weeks(2022, 1)) == 6
    assert all(len(week) == 7 for week in month_weeks(2022, 1))


def test_present_month_uses_german_labels_today_and_overflow() -> None:
    from cafeteria.calendar_month import present_month

    services = (
        {
            'profile_code': 'staff_guest', 'service_date': date(2026, 9, 16),
            'meal_code': 'LUNCH', 'service_state': 'open', 'week_start': date(2026, 9, 14),
            'menus': (
                {'title': 'Risotto', 'type_code': 'MENU_1'},
                {'title': 'Gemüseplatte', 'type_code': 'VEGGIE'},
                {'title': 'Suppe extra', 'type_code': 'MENU_1'},
                {'title': 'Nachtisch extra', 'type_code': 'VEGGIE'},
            ),
        },
        {
            'profile_code': 'patient', 'service_date': date(2026, 9, 16),
            'meal_code': 'DINNER', 'service_state': 'closed', 'notice': 'Küche geschlossen',
            'week_start': date(2026, 9, 14), 'menus': (),
        },
    )
    weeks = present_month(annotate_month(2026, 9, services), date(2026, 9, 16), extra_limit=2)
    cell = weeks[2][2]
    assert cell['date'] == date(2026, 9, 16)
    assert cell['is_today'] is True
    assert cell['list_label'] == 'Mi, 16. September'
    labels = [group['profile_label'] for group in cell['groups']]
    assert labels == ['Cafeteria', 'Patienten']
    cafeteria = cell['groups'][0]['meals'][0]
    assert cafeteria['meal_label'] == 'Mittagessen'
    assert [item['title'] for item in cafeteria['visible']] == ['Risotto', 'Gemüseplatte']
    assert [item['title'] for item in cafeteria['extra']] == ['Suppe extra', 'Nachtisch extra']
    dinner = cell['groups'][1]['meals'][0]
    assert dinner['meal_label'] == 'Abendessen'
    assert dinner['state_label'] == 'Geschlossen'
    empty = weeks[0][0]
    assert empty['groups'] == []
    assert empty['is_today'] is False
