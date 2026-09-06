"""OPS-001: the week PDFs carry the area name, serving times and open weekend days."""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Any

import pytest
from pypdf import PdfReader

from cafeteria.admin.week_pdf import render_week_pdf

WEEK = date(2026, 8, 31)
CAFETERIA_AREA = 'Team-Restaurant'
PATIENT_AREA = 'Schülerinnen und Schüler'


def _option(index: int, day_index: int, meal: str) -> dict[str, Any]:
    return {
        'type_code': 'MENU_1' if index == 1 else 'VEGGIE',
        'title': f'Gericht {day_index}{meal[0]}{index}',
        'components': ['Kartoffeln', 'Gemüse'],
        'description': '', 'note': '', 'labels': [], 'origins': [], 'allergens': [],
        'allergen_review_status': 'checked',
        'internal_rappen': 1100, 'external_rappen': 1660,
    }


def _service(meal: str, day_index: int, start: str | None, end: str | None) -> dict[str, Any]:
    service: dict[str, Any] = {
        'meal_code': meal, 'service_state': 'open', 'notice': '',
        'options': [_option(1, day_index, meal), _option(2, day_index, meal)],
    }
    if start:
        service['service_start'] = start
    if end:
        service['service_end'] = end
    return service


def draft(*, patient: bool, area: bool, times: bool, open_days: int = 5) -> dict[str, Any]:
    """Saved week for the PDF; `open_days` counts the cafeteria rows (5 to 7)."""
    meals = ('LUNCH', 'DINNER') if patient else ('LUNCH',)
    total = 7 if patient else open_days
    days = []
    for index in range(total):
        services = [
            _service(meal, index,
                     ('11:30' if meal == 'LUNCH' else '17:30') if times else None,
                     ('13:30' if meal == 'LUNCH' else '19:00') if times else None)
            for meal in meals
        ]
        days.append({'date': (WEEK + timedelta(days=index)).isoformat(), 'services': services})
    week: dict[str, Any] = {
        'days': days, 'title': 'Herbstküche', 'shared_note': '', 'workflow_state': 'draft',
    }
    if area:
        week['area_name'] = PATIENT_AREA if patient else CAFETERIA_AREA
    return week


def _render(**kwargs: Any) -> tuple[PdfReader, str]:
    payload = render_week_pdf(draft(**kwargs), 'patient' if kwargs['patient'] else 'staff_guest', WEEK)
    reader = PdfReader(BytesIO(payload))
    return reader, ' '.join(reader.pages[0].extract_text().split())


@pytest.mark.parametrize('open_days', (5, 6, 7))
def test_cafeteria_pdf_stays_one_page_for_five_to_seven_open_days(open_days: int) -> None:
    reader, body = _render(patient=False, area=True, times=True, open_days=open_days)
    assert len(reader.pages) == 1
    for index in range(open_days):
        assert f'Gericht {index}L1' in body
        assert f'Gericht {index}L2' in body
    assert 'Kartoffeln' in body
    assert 'Intern: 11.00 CHF' in body and 'Extern: 16.60 CHF' in body
    sizes: list[float] = []
    reader.pages[0].extract_text(
        visitor_text=lambda text, cm, tm, font, size: sizes.append(size) if text.strip() else None,
    )
    assert min(sizes) >= 8.5


@pytest.mark.parametrize('open_days', (5, 6, 7))
def test_cafeteria_pdf_names_every_shown_day_and_its_time(open_days: int) -> None:
    _, body = _render(patient=False, area=True, times=True, open_days=open_days)
    names = ('MONTAG', 'DIENSTAG', 'MITTWOCH', 'DONNERSTAG', 'FREITAG', 'SAMSTAG', 'SONNTAG')
    for name in names[:open_days]:
        assert name in body
    for name in names[open_days:]:
        assert name not in body
    assert body.count('Mittag 11:30–13:30 Uhr') == open_days


def test_cafeteria_pdf_carries_the_area_name_in_title_and_band() -> None:
    reader, body = _render(patient=False, area=True, times=True)
    assert reader.metadata.title == f'Wochenangebot {CAFETERIA_AREA}'
    assert f'WOCHENANGEBOT {CAFETERIA_AREA.upper()}' in body


def test_cafeteria_pdf_without_area_keeps_its_previous_title_and_band() -> None:
    reader, body = _render(patient=False, area=False, times=False)
    assert reader.metadata.title == 'Wochenangebot Cafeteria'
    assert 'WOCHENANGEBOT CAFETERIA' in body
    assert 'Uhr' not in body


def test_patient_pdf_shows_the_area_name_and_times_without_any_price() -> None:
    reader, body = _render(patient=True, area=True, times=True)
    assert len(reader.pages) == 1
    assert reader.metadata.title == f'Wochenangebot {PATIENT_AREA}'
    assert PATIENT_AREA in body
    assert 'Ausgabe 11:30–13:30 Uhr' in body
    assert 'Ausgabe 17:30–19:00 Uhr' in body
    for forbidden in ('CHF', 'Rappen', 'Intern', 'Extern', 'Preis'):
        assert forbidden not in body


def test_patient_pdf_without_area_keeps_its_previous_title() -> None:
    reader, body = _render(patient=True, area=False, times=False)
    assert reader.metadata.title == 'Wochenangebot Patienten'
    assert 'Wochenangebot Patienten' in body
    assert 'Uhr' not in body


def test_open_saturday_next_to_a_closed_sunday_prints_six_rows_on_one_page() -> None:
    """The Saturday release of SDD §1a: six full rows, Sunday closed and therefore absent."""
    week = draft(patient=False, area=True, times=True, open_days=7)
    week['days'][6]['services'][0].update(
        service_state='closed', notice='Am Sonntag geschlossen.', options=[])
    reader = PdfReader(BytesIO(render_week_pdf(week, 'staff_guest', WEEK)))
    body = ' '.join(reader.pages[0].extract_text().split())
    assert len(reader.pages) == 1
    assert 'SAMSTAG' in body and 'SONNTAG' not in body
    assert 'Am Sonntag geschlossen.' not in body
    for index in range(6):
        assert f'Gericht {index}L1' in body and f'Gericht {index}L2' in body
    assert body.count('Mittag 11:30–13:30 Uhr') == 6
    assert 'Intern: 11.00 CHF' in body and 'Extern: 16.60 CHF' in body


def test_day_column_shows_a_lone_start_time() -> None:
    week = draft(patient=False, area=True, times=True)
    for day in week['days']:
        day['services'][0].pop('service_end')
    body = ' '.join(
        PdfReader(BytesIO(render_week_pdf(week, 'staff_guest', WEEK))).pages[0].extract_text().split()
    )
    assert body.count('Mittag ab 11:30 Uhr') == 5
    assert '13:30' not in body


def test_closed_weekend_service_keeps_the_cafeteria_at_five_rows() -> None:
    week = draft(patient=False, area=True, times=True, open_days=7)
    for day in week['days'][5:]:
        day['services'][0].update(service_state='closed', notice='Am Wochenende geschlossen.', options=[])
    body = ' '.join(
        PdfReader(BytesIO(render_week_pdf(week, 'staff_guest', WEEK))).pages[0].extract_text().split()
    )
    assert 'SAMSTAG' not in body and 'SONNTAG' not in body
    assert 'Am Wochenende geschlossen.' not in body
    assert body.count('Mittag 11:30–13:30 Uhr') == 5
