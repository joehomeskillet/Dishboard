"""Real PDFs prove active brand fields, isolated overrides, complete weeks and fit."""
from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import re
import subprocess
import xml.etree.ElementTree as ET

import pytest
from pypdf import PdfReader

from cafeteria.admin.week_pdf import ASSETS, WeekPdfFitError, render_week_pdf
from cafeteria.print_branding import PdfBranding
from cafeteria.print_template_config import PrintTemplateValidationError, default_config
from test_branding_store import _png
from test_week_pdf import WEEK, saved_week

BRAND = PdfBranding(2, (140, 28, 75), (53, 102, 111), (255, 255, 255), (32, 50, 51),
                    'carlito', 'fira', _png())
INHERIT = {**default_config(), 'palette': 'active_brand', 'font': 'active_brand', 'logo': 'active_brand'}


@pytest.mark.parametrize('profile', ['patient', 'staff_guest'])
def test_brand_pdf_keeps_all_menus_and_draws_real_fonts_logo_and_colors(profile, tmp_path):
    draft = saved_week(profile, False)
    options = [option for day in draft['days'] for service in day['services'] for option in service['options']]
    for index, option in enumerate(options):
        option['title'] = f'MENUNUMMER{index:02d}'
    options[1]['title'] += ' Gemüseauflauf mit Kartoffeln und saisonalem Gartengemüse'
    options[0]['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    payload = render_week_pdf(draft, profile, WEEK, INHERIT, branding=BRAND)
    reader = PdfReader(BytesIO(payload))
    assert len(reader.pages) == 1
    assert reader.metadata.subject == 'Dishboard Markenrevision 2'
    page = reader.pages[0]
    body = ' '.join(page.extract_text().split())
    assert 'Markenrevision' not in body
    assert all(body.count(f'MENUNUMMER{index:02d}') == 1 for index in range(28 if profile == 'patient' else 10))
    assert 'Legende der gedruckten Menüs' in body and 'Enthält: Milch' in body
    assert body.count('Allergenangaben nicht erfasst') == len(options)
    if profile == 'patient':
        assert re.search(r'\b(?:preise?|chf|rappen|kosten|prices?)\b', body, re.I) is None
    assert len(list(page.images)) == 1  # Native SVGs are vectors; no baked-in Südhang header remains.
    assert list(page.images)[0].image.size == (40, 20)
    fonts = [str(font.get_object()['/BaseFont']) for font in page['/Resources']['/Font'].values()]
    assert any('Carlito' in name for name in fonts) and any('FiraSans' in name for name in fonts)
    colors = [tuple(float(value) for value in values) for values, operation in page.get_contents().operations
              if operation == b'rg']
    assert any(color == pytest.approx(tuple(value / 255 for value in BRAND.primary), abs=0.001) for color in colors)
    assert any(color == pytest.approx(tuple(value / 255 for value in BRAND.text), abs=0.001) for color in colors)
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    assert (width > height) == (profile == 'patient')
    path = tmp_path / f'brand-{profile}.pdf'
    path.write_bytes(payload)
    result = subprocess.run(['pdftotext', '-bbox', str(path), '-'], check=True, capture_output=True, text=True)
    words = ET.fromstring(result.stdout).findall('.//{http://www.w3.org/1999/xhtml}word')
    boxes = [tuple(float(word.attrib[key]) for key in ('xMin', 'yMin', 'xMax', 'yMax')) for word in words]
    for x0, y0, x1, y1 in boxes:
        assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
    for index, (x0, y0, x1, y1) in enumerate(boxes):
        for a0, b0, a1, b1 in boxes[index + 1:]:
            assert min(x1, a1) - max(x0, a0) < 0.2 or min(y1, b1) - max(y0, b0) < 0.2
    sizes = []
    page.extract_text(visitor_text=lambda text, cm, tm, font, size: sizes.append(size) if text.strip() else None)
    assert min(sizes) >= 8.5
    subprocess.run(['pdftoppm', '-r', '120', '-png', '-singlefile', str(path), str(path.with_suffix(''))],
                   check=True, capture_output=True)


@pytest.mark.parametrize('profile', ['patient', 'staff_guest'])
def test_explicit_overrides_ignore_brand_changes_and_missing_brand_is_refused(profile):
    draft = saved_week(profile, False)
    for palette in ('reference', 'brand', 'teal'):
        config = {**default_config(), 'palette': palette}
        assert render_week_pdf(draft, profile, WEEK, config, branding=BRAND) == render_week_pdf(draft, profile, WEEK, config)
    with pytest.raises(PrintTemplateValidationError, match='geladen'):
        render_week_pdf(draft, profile, WEEK, INHERIT)
    # No custom brand asset means the standard logo, as in Web/Admin.
    payload = render_week_pdf(draft, profile, WEEK, INHERIT, branding=replace(BRAND, logo_png=None))
    page = PdfReader(BytesIO(payload)).pages[0]
    images = list(page.images)
    assert len(images) == 1
    embedded = [item.get_object().get_data() for item in page['/Resources']['/XObject'].values()
                if item.get_object().get('/Subtype') == '/Image']
    assert embedded == [(ASSETS / 'img/weekly-print-logo.jpg').read_bytes()]
    # Only the explicit print override omits the logo, even with an inherited brand.
    payload = render_week_pdf(draft, profile, WEEK, {**INHERIT, 'logo': 'none'}, branding=BRAND)
    assert len(list(PdfReader(BytesIO(payload)).pages[0].images)) == 0
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                option['note'] = 'Vollständige Deklaration. ' * 200
    with pytest.raises(WeekPdfFitError, match='A4-Seite'):
        render_week_pdf(draft, profile, WEEK, INHERIT, branding=BRAND)


def test_individual_brand_fields_leave_other_print_overrides_effective():
    draft = saved_week('staff_guest', False)
    for field in ('font', 'palette', 'logo'):
        config = {**default_config(), field: 'active_brand'}
        page = PdfReader(BytesIO(render_week_pdf(draft, 'staff_guest', WEEK, config, branding=BRAND))).pages[0]
        fonts = [str(font.get_object()['/BaseFont']) for font in page['/Resources']['/Font'].values()]
        assert any('FiraSans' in font for font in fonts) == (field == 'font')
        assert (list(page.images)[0].image.size == (40, 20)) == (field == 'logo')
    dark = replace(BRAND, primary=(255, 255, 255), accent=(220, 230, 240), surface=(20, 20, 20), text=(240, 240, 240))
    draft['days'][0]['services'][0]['options'][0]['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    page = PdfReader(BytesIO(render_week_pdf(draft, 'staff_guest', WEEK, INHERIT, branding=dark))).pages[0]
    # Existing black symbols get a white underlay in both the menu and the legend.
    white = [values for values, operator in page.get_contents().operations if operator == b'rg' and list(values) == [1, 1, 1]]
    assert len(white) >= 2
