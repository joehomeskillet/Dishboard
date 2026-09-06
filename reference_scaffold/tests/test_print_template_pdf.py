"""Actual PDF structure and text prove each offered property has a renderer consumer."""
from __future__ import annotations

import re
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from fontTools.ttLib import TTFont

from cafeteria.admin.week_pdf import WeekPdfFitError, render_week_pdf
from cafeteria.print_template_config import PrintTemplateValidationError, default_config, validate_config
from test_week_pdf import WEEK, saved_week


def _page(profile: str, config: dict[str, str]):
    return PdfReader(BytesIO(render_week_pdf(saved_week(profile, False), profile, WEEK, config))).pages[0]


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
@pytest.mark.parametrize('field,value', [
    ('header_text', 'Guten Appetit'), ('footer_text', 'Wir wünschen eine gute Woche'),
    ('palette', 'brand'), ('palette', 'teal'), ('font', 'fira'),
    ('text_size', 'large'), ('logo', 'wordmark'), ('logo', 'none'),
    ('margin', 'wide'), ('margin', 'wider'), ('spacing', 'roomy'),
])
def test_every_control_changes_real_pdf_without_losing_week(profile: str, field: str, value: str, tmp_path: Path) -> None:
    config = {**default_config(), field: value}
    base, changed = _page(profile, default_config()), _page(profile, config)
    if field == 'font':
        fonts = [str(font.get_object().get('/BaseFont')) for font in changed['/Resources']['/Font'].values()]
        assert any('FiraSans' in font for font in fonts)
    elif field == 'logo' and value == 'wordmark':
        assert list(base.images)[-1].image.tobytes() != list(changed.images)[-1].image.tobytes()
    else:
        assert base.get_contents().get_data() != changed.get_contents().get_data()
    body = ' '.join(changed.extract_text().split())
    if field.endswith('_text'):
        assert value in body
    draft = saved_week(profile, False)
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                assert option['title'] in body
                assert all(component in body for component in option['components'])
    # Every menu retains its warning; the additional occurrence belongs to the legend.
    assert body.count('Allergenangaben nicht erfasst') == (29 if profile == 'patient' else 11)
    if profile == 'patient':
        assert re.search(r'preis|chf|rappen|kosten|price', body, re.I) is None
        assert 'SONNTAG' in body
    payload = render_week_pdf(draft, profile, WEEK, config)
    reader = PdfReader(BytesIO(payload))
    assert len(reader.pages) == 1
    assert (float(changed.mediabox.width) > float(changed.mediabox.height)) == (profile == 'patient')
    sizes: list[float] = []
    changed.extract_text(visitor_text=lambda text, cm, tm, font, size: sizes.append(size) if text.strip() else None)
    assert min(sizes) >= 8.5
    path = tmp_path / f'{profile}-{field}-{value.replace(" ", "_")}.pdf'
    path.write_bytes(payload)
    result = subprocess.run(['pdftotext', '-bbox', str(path), '-'], capture_output=True, check=True, text=True)
    words = ET.fromstring(result.stdout).findall('.//{http://www.w3.org/1999/xhtml}word')
    for word in words:
        x0, y0, x1, y1 = (float(word.attrib[key]) for key in ('xMin', 'yMin', 'xMax', 'yMax'))
        assert 0 <= x0 < x1 <= float(changed.mediabox.width)
        assert 0 <= y0 < y1 <= float(changed.mediabox.height)


@pytest.mark.parametrize('field,value', [
    ('font', '../fonts/custom'), ('palette', 'https://example.invalid'), ('logo', '/tmp/private.jpg'),
    ('spacing', '0'), ('margin', []), ('text_size', '1'), ('footer_text', '<script>'),
    ('header_text', 'hidden\u202ehint'), ('header_text', 'x' * 73), ('footer_text', 'x' * 161),
])
def test_unbounded_or_non_allowlisted_properties_rejected(field: str, value: object) -> None:
    with pytest.raises(PrintTemplateValidationError):
        validate_config({**default_config(), field: value}, 'staff_guest')


@pytest.mark.parametrize('value', ['CHF 10', 'Preise auf Anfrage', 'Kosten', 'c\u200bhf', 'Ｐｒｅｉｓ'])
def test_patient_custom_text_cannot_introduce_price_information(value: str) -> None:
    with pytest.raises(PrintTemplateValidationError):
        validate_config({**default_config(), 'header_text': value}, 'patient')


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_custom_fonts_keep_glyph_and_overflow_refusal(profile: str) -> None:
    draft = saved_week(profile)
    config = {**default_config(), 'font': 'fira', 'text_size': 'large', 'spacing': 'roomy', 'margin': 'wider'}
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                option['note'] = 'Vollständige Deklaration. ' * 100
    with pytest.raises(WeekPdfFitError, match='A4-Seite'):
        render_week_pdf(draft, profile, WEEK, config)
    with pytest.raises(WeekPdfFitError, match='Druckschrift'):
        render_week_pdf(saved_week(profile, False), profile, WEEK, {**default_config(), 'header_text': '🥜'})


def test_existing_fira_fonts_have_verified_lossless_print_copies() -> None:
    assets = Path(__file__).parents[1] / 'cafeteria/static/fonts'
    provenance = json.loads((assets / 'weekly-print-fira-provenance.json').read_text())
    assert (assets / provenance['license']).is_file()
    for record in provenance['files']:
        source, target = assets / record['source'], assets / record['destination']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
        assert hashlib.sha256(target.read_bytes()).hexdigest() == record['sha256']
        with TTFont(source) as original, TTFont(target) as copied:
            assert original.getBestCmap() == copied.getBestCmap()
            assert original['hmtx'].metrics == copied['hmtx'].metrics
