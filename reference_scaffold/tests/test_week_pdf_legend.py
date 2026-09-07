from copy import deepcopy
from datetime import timedelta
from io import BytesIO
import re
import subprocess
import xml.etree.ElementTree as ET

import pytest
from pypdf import PdfReader

from cafeteria.admin.week_pdf import WeekPdfFitError, render_week_pdf
from test_week_pdf import WEEK, saved_week


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_printed_week_has_complete_deduplicated_legend_without_hidden_options(profile, tmp_path):
    draft = saved_week(profile, False)
    options = [option for day in draft['days'] for service in day['services'] for option in service['options']]
    for index, option in enumerate(options):
        option['title'] = f'MENUNUMMER{index:02d}'
        option['components'] = ['Kartoffeln']
    for option, presence, country in zip(options, ['contains', 'may_contain', 'contains'], ['CH', 'US', 'CH']):
        option.update(
            allergens=[{'code': 'MILK', 'name': 'Milch', 'presence': presence}],
            origins=[{'country_code': country, 'text': f'Kartoffeln: {country}'}],
            labels=[{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
            allergen_review_status='not_checked',
        )
    hidden = {**deepcopy(options[0]), 'title': 'NICHTGEDRUCKT',
              'labels': [{'code': 'CUSTOM', 'name': 'UNSICHTBAREDEKLARATION'}]}
    options[2]['labels'] = [{'code': 'VEGAN', 'name': 'Vegan'}]
    draft['days'].append({'date': (WEEK + timedelta(days=14)).isoformat(), 'services': [
        {'meal_code': 'LUNCH', 'service_state': 'open', 'options': [hidden]},
    ]})
    original = deepcopy(draft)
    payload = render_week_pdf(draft, profile, WEEK)
    assert draft == original
    reader = PdfReader(BytesIO(payload))
    assert len(reader.pages) == 1
    page = reader.pages[0]
    body = ' '.join(page.extract_text().split())
    assert all(body.count(f'MENUNUMMER{index:02d}') == 1 for index in range(len(options)))
    assert 'NICHTGEDRUCKT' not in body and 'UNSICHTBAREDEKLARATION' not in body
    menu_text, legend = body.split('Legende der gedruckten Menüs', 1)
    assert 'Kartoffeln: US (Vereinigte Staaten)' in menu_text
    for label in ('Enthält: Milch', 'Kann enthalten: Milch', 'Herkunft: Schweiz',
                  'Herkunft: Vereinigte Staaten', 'Vegetarisch', 'Vegan',
                  'Allergenangaben nicht erfasst', 'Allergenprüfung offen'):
        assert legend.count(label) == 1
    if profile == 'patient':
        assert re.search(r'\b(?:preise?|chf|rappen|kosten|prices?)\b', body, re.I) is None
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    assert (width > height) == (profile == 'patient')
    path = tmp_path / f'legend-{profile}.pdf'
    path.write_bytes(payload)
    result = subprocess.run(['pdftotext', '-bbox', str(path), '-'], check=True, capture_output=True, text=True)
    words = ET.fromstring(result.stdout).findall('.//{http://www.w3.org/1999/xhtml}word')
    boxes = [tuple(float(word.attrib[key]) for key in ('xMin', 'yMin', 'xMax', 'yMax')) for word in words]
    for x0, y0, x1, y1 in boxes:
        assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
    for index, (x0, y0, x1, y1) in enumerate(boxes):
        for a0, b0, a1, b1 in boxes[index + 1:]:
            assert min(x1, a1) - max(x0, a0) < 0.2 or min(y1, b1) - max(y0, b0) < 0.2
    subprocess.run(['pdftoppm', '-r', '120', '-png', '-singlefile', str(path), str(path.with_suffix(''))],
                   check=True, capture_output=True)


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_legend_overflow_is_rejected_during_real_measurement(profile, monkeypatch):
    draft = saved_week(profile, False)
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                option['origins'] = [{'country_code': 'UNKNOWNCOUNTRY' * 300, 'text': ''}]
    # Real text measurement must fail before header images, cell symbols or text draw.
    def unexpected_draw(*args, **kwargs):
        pytest.fail('Oversized legend reached drawing')
    monkeypatch.setattr('cafeteria.admin.week_pdf._draw', unexpected_draw)
    with pytest.raises(WeekPdfFitError, match='A4-Seite'):
        render_week_pdf(draft, profile, WEEK)
