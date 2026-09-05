from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

from cafeteria.admin.week_pdf import WeekPdfFitError, render_week_pdf

WEEK = date(2026, 8, 31)
FIXTURE = Path(__file__).parent / 'fixtures' / 'weekly_print_notes.json'


def saved_week(profile: str, notes: bool = True) -> dict[str, Any]:
    days: dict[str, dict[str, Any]] = {}
    for item in json.loads(FIXTURE.read_text()):
        if item['profile'] != profile:
            continue
        day = days.setdefault(item['date'], {'date': item['date'], 'services': []})
        service = next((s for s in day['services'] if s['meal_code'] == item['meal']), None)
        if service is None:
            service = {'meal_code': item['meal'], 'service_state': 'open', 'options': []}
            day['services'].append(service)
        service['options'].append({
            'type_code': item['code'], 'title': item['title'], 'components': item['components'],
            'description': '', 'note': item['note'] if notes else '',
            'labels': [], 'origins': [], 'allergens': [], 'allergen_review_status': 'not_checked',
            'internal_rappen': 1100, 'external_rappen': 1660,
        })
    return {'days': list(days.values()), 'title': 'Herbstküche', 'shared_note': '', 'workflow_state': 'draft'}


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
@pytest.mark.parametrize('notes', [False, True])
def test_complete_week_is_one_readable_page(profile: str, notes: bool, tmp_path: Path) -> None:
    draft = saved_week(profile, notes)
    payload = render_week_pdf(draft, profile, WEEK)
    reader = PdfReader(BytesIO(payload))
    assert len(reader.pages) == 1
    page = reader.pages[0]
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    assert (width > height) == (profile == 'patient')
    assert sorted((width, height)) == pytest.approx([595.28, 841.89], abs=0.02)
    body = ' '.join(page.extract_text().split())
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                assert option['title'] in body
                for component in option['components']:
                    assert component in body
                if notes:
                    assert option['note'] in body
    assert body.count('Allergenangaben nicht erfasst') == (28 if profile == 'patient' else 10)
    if profile == 'patient':
        assert all(label in body for label in ('Mittag · Menü 1', 'Mittag · Vegetarisch', 'Abend · Menü 1', 'Abend · Vegetarisch', 'SONNTAG'))
        assert re.search(r'\b(?:preise?|chf|rappen|kosten|prices?|cafeteria)\b', body, re.I) is None
    else:
        assert 'Intern: 11.00 CHF' in body and 'Extern: 16.60 CHF' in body
    font_sizes: list[float] = []
    page.extract_text(visitor_text=lambda text, cm, tm, font, size: font_sizes.append(size) if text.strip() else None)
    assert min(font_sizes) >= 8.5
    path = tmp_path / 'week.pdf'
    path.write_bytes(payload)
    result = subprocess.run(['pdftotext', '-bbox', str(path), '-'], capture_output=True, check=True, text=True)
    words = ET.fromstring(result.stdout).findall('.//{http://www.w3.org/1999/xhtml}word')
    assert words
    boxes = [tuple(float(word.attrib[key]) for key in ('xMin', 'yMin', 'xMax', 'yMax')) for word in words]
    for x1, y1, x2, y2 in boxes:
        assert 0 <= x1 < x2 <= width
        assert 0 <= y1 < y2 <= height
    for index, (x1, y1, x2, y2) in enumerate(boxes):
        for a1, b1, a2, b2 in boxes[index + 1:]:
            assert min(x2, a2) - max(x1, a1) < 0.2 or min(y2, b2) - max(y1, b1) < 0.2


def test_patient_all_28_unique_menu_sentinels_survive() -> None:
    draft = saved_week('patient')
    markers = []
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                marker = f'MENUNUMMER{len(markers):02d}'
                markers.append(marker)
                option['title'] = marker
    page = PdfReader(BytesIO(render_week_pdf(draft, 'patient', WEEK))).pages[0]
    body = page.extract_text()
    assert all(body.count(marker) == 1 for marker in markers)


def test_all_metadata_is_preserved_and_empty_slots_stay_empty() -> None:
    draft = saved_week('patient', False)
    option = draft['days'][0]['services'][0]['options'][0]
    option.update(description='Sorgfältig zubereitet', note='Hinweis: getrennte Zubereitung',
                  labels=[{'name': 'Vegetarisch'}], origins=[{'text': 'Kartoffeln: Schweiz'}],
                  allergens=[{'name': 'Milch', 'presence': 'contains'}, {'name': 'Eier', 'presence': 'may_contain'}])
    draft['days'][0]['services'][0]['options'][1]['title'] = ''
    body = ' '.join(PdfReader(BytesIO(render_week_pdf(draft, 'patient', WEEK))).pages[0].extract_text().split())
    for expected in ['Sorgfältig zubereitet', 'Hinweis: getrennte Zubereitung', 'Vegetarisch', 'Kartoffeln: Schweiz', 'Enthält: Milch', 'Kann enthalten: Eier', 'Allergenprüfung offen', 'Menü noch nicht erfasst']:
        assert expected in body


@pytest.mark.parametrize('profile', ['patient', 'staff_guest'])
def test_unbounded_content_rejected_without_truncation(profile: str) -> None:
    draft = saved_week(profile)
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                option['note'] = 'Lange vollständige Rezepturangaben. ' * 100
    with pytest.raises(WeekPdfFitError, match='A4-Seite'):
        render_week_pdf(draft, profile, WEEK)


def test_individual_prices_do_not_leak_into_patient_output() -> None:
    draft = saved_week('staff_guest', False)
    draft['days'][0]['services'][0]['options'][0]['internal_rappen'] = 1200
    body = ' '.join(PdfReader(BytesIO(render_week_pdf(draft, 'staff_guest', WEEK))).pages[0].extract_text().split())
    assert 'Intern: 12.00 CHF' in body and 'Intern: 11.00 CHF' in body
    assert 'Preise beim Menü in CHF' in body


def test_unsupported_glyph_is_rejected_instead_of_silently_dropped() -> None:
    draft = saved_week('patient', False)
    draft['days'][0]['services'][0]['options'][0]['note'] = 'Hinweis 🥜'
    with pytest.raises(WeekPdfFitError, match='Druckschrift'):
        render_week_pdf(draft, 'patient', WEEK)


@pytest.mark.parametrize('week', [date(2026, 9, 7), WEEK])
def test_cafeteria_header_matches_reference_geometry(week: date, tmp_path: Path) -> None:
    draft = saved_week('staff_guest', False)
    for offset, day in enumerate(draft['days']):
        day['date'] = (week + timedelta(days=offset)).isoformat()
    payload = render_week_pdf(draft, 'staff_guest', week)
    page = PdfReader(BytesIO(payload)).pages[0]
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    operations = page.get_contents().operations
    first_image = next(i for i, (_, operator) in enumerate(operations) if operator == b'Do')
    image_matrix = next(args for args, operator in reversed(operations[:first_image]) if operator == b'cm')
    # Measured from the supplied reference: full-bleed photo ending at y=201.96pt.
    assert [float(value) for value in image_matrix] == pytest.approx(
        [width, 0, 0, 201.96, 0, height - 201.96], abs=0.02,
    )
    first_text = next(i for i, (_, operator) in enumerate(operations) if operator == b'Tj')
    date_color = next(args for args, operator in reversed(operations[:first_text]) if operator == b'rg')
    assert [float(value) for value in date_color] == pytest.approx([0, 112 / 255, 136 / 255], abs=0.001)
    strips = [
        args for i, (args, operator) in enumerate(operations)
        if operator == b're' and operations[i + 1][1] == b'f'
    ]
    strip = next(args for args in strips if abs(height - float(args[1]) - 145.56) < 0.02)
    x, bottom, strip_width, negative_height = (float(value) for value in strip)
    assert x + strip_width == pytest.approx(572.28, abs=0.02)
    assert negative_height == pytest.approx(-26.28, abs=0.02)
    assert strip_width >= 250.43
    if week.month == (week + timedelta(days=4)).month:
        assert x == pytest.approx(321.84, abs=0.02)
    path = tmp_path / 'reference-header.pdf'
    path.write_bytes(payload)
    result = subprocess.run(['pdftotext', '-bbox', str(path), '-'], capture_output=True, check=True, text=True)
    words = ET.fromstring(result.stdout).findall('.//{http://www.w3.org/1999/xhtml}word')
    date_words = [word for word in words if float(word.attrib['yMax']) < 203]
    assert date_words
    for word in date_words:
        assert x <= float(word.attrib['xMin']) < float(word.attrib['xMax']) <= x + strip_width
        assert height - bottom <= float(word.attrib['yMin']) < float(word.attrib['yMax']) <= height - bottom - negative_height
