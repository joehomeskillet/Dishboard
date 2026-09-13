"""Real PDF raster and text geometry receipts; synthetic recipes only."""
from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image
from pypdf import PdfReader
import pytest

from cafeteria.admin.recipe_document import build_recipe_document
from cafeteria.admin.recipe_pdf import render_recipe_pdf
from cafeteria.admin.recipe_pdf_layout import RecipeSheet
from cafeteria.print_template_config import default_config
from test_recipe_pdf import recipe, revision, prepared_revision

NS = '{http://www.w3.org/1999/xhtml}'


def fixture_recipe(case):
    source = recipe()
    if case == 'complete':
        source['title'] = 'Rezeptblatt mit vier Zutaten'
        source['ingredients'] = [dict(source['ingredients'][0], ingredient_text=f'Zutat{number}',
                                      quantity=str(number), unit_code='G', group_label=None)
                                 for number in range(1, 5)]
        source['steps'] = [dict(source['steps'][0], instruction=f'Arbeitsschritt{number} behutsam ausführen.')
                           for number in range(1, 3)]
        source['source'].update(kind='ai_assisted', reference='Synthetischer Küchenvorschlag',
                                note='Ungeprüfter Vorschlag. Ausbeute wurde nicht gemessen.',
                                fetched_at='2026-09-13T12:00:00Z')
        for row in source['ingredients']:
            row.update(source_kind='ai_assisted', source_reference='Synthetischer Küchenvorschlag',
                       fetched_at='2026-09-13T12:00:00Z')
    elif case == 'long':
        source['ingredients'] = [dict(source['ingredients'][0], ingredient_text=f'Langzutat{number:03d}',
                                      note='Zutatenhinweis sorgfältig berücksichtigen.') for number in range(60)]
        source['steps'] = [dict(source['steps'][0], instruction=f'Langschritt{number:03d} ' +
                                'Behutsam vorbereiten und vollständig weiterverarbeiten. ' * 8)
                           for number in range(40)]
    elif case == 'missing':
        source.update(steps=[], prep_minutes=None, cook_minutes=None)
        source['ingredients'] = [source['ingredients'][1]]
    elif case == 'provenance':
        source['ingredients'] = [dict(source['ingredients'][0], ingredient_text=f'Herkunftzutat{number}',
                                      source_kind='file_import', source_reference=f'Beleg {number}',
                                      fetched_at=f'2026-09-0{number}T12:00:00Z') for number in range(1, 4)]
    return source


def pdf_receipt(data, output, name):
    path = output / f'{name}.pdf'
    path.write_bytes(data)
    result = subprocess.run(['rtk', 'pdftotext', '-bbox', str(path), '-'],
                            capture_output=True, text=True, check=True)
    (output / f'{name}-bbox.html').write_text(result.stdout)
    pages = ET.fromstring(result.stdout).findall(f'.//{NS}page')
    for page in pages:
        words = page.findall(f'.//{NS}word')
        bounds = [tuple(float(node.attrib[key]) for key in ('xMin', 'yMin', 'xMax', 'yMax')) for node in words]
        assert all(47 <= x0 < x1 <= 548 and 12 <= y0 < y1 <= 830 for x0, y0, x1, y1 in bounds)
        ordered = sorted(bounds, key=lambda box: box[1])
        for index, box in enumerate(ordered):
            for other in ordered[index + 1:]:
                if other[1] >= box[3] - 0.5:
                    break
                assert min(box[2], other[2]) - max(box[0], other[0]) <= 0.5, (box, other)
    subprocess.run(['rtk', 'pdftoppm', '-scale-to', '1200', '-png', str(path), str(output / name)],
                   capture_output=True, text=True, check=True)
    for image_path in output.glob(f'{name}-*.png'):
        with Image.open(image_path) as image:
            assert image.width > 800 and image.height == 1200
            assert image.convert('L').getextrema()[0] < 100
    return pages


@pytest.mark.parametrize('case', ['complete', 'long', 'missing', 'provenance', 'prepared'])
def test_recipe_sheet_complete_content_and_real_page_geometry(case, tmp_path):
    output = Path(os.environ.get('RECIPE_DOCUMENT_EVIDENCE_DIR', str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    selected = prepared_revision() if case == 'prepared' else revision(fixture_recipe(case))
    before = json.dumps(selected.snapshot, default=dict, sort_keys=True)
    document = build_recipe_document(selected.snapshot['recipe'], revision=selected)
    data = render_recipe_pdf(selected, config=default_config(), images={})
    pages = pdf_receipt(data, output, case)
    reader = PdfReader(BytesIO(data))
    content = ' '.join(' '.join(page.extract_text() for page in reader.pages).split())
    assert json.dumps(selected.snapshot, default=dict, sort_keys=True) == before
    for row in document['ingredients']:
        assert row['text'] in content
    for step in document['steps']:
        assert step['instruction'].split()[0] in content
    assert document['title'] in content
    if case == 'complete':
        assert len(pages) == 1
        assert content.count('Synthetischer Küchenvorschlag') == 1
        assert content.count('Ausbeute wurde nicht gemessen.') == 1
        assert 'Zutaten 1–4' in content
        assert 'fachlich prüfen' in content
        words = pages[0].findall(f'.//{NS}word')
        left = [node for node in words if node.text == 'Zutaten' and float(node.attrib['xMin']) < 100]
        right = [node for node in words if node.text == 'Zubereitung' and float(node.attrib['xMin']) > 200]
        assert any(abs(float(a.attrib['yMin']) - float(b.attrib['yMin'])) < 1 for a in left for b in right)
    elif case == 'long':
        assert len(pages) > 3
        assert all('Fortsetzung' in page.extract_text() for page in reader.pages[1:])
        assert all(content.count(f'Langzutat{number:03d}') == 1 for number in range(60))
        assert all(content.count(f'Langschritt{number:03d}') == 1 for number in range(40))
        assert 'Zutaten 1–60' in content
    elif case == 'missing':
        assert document['empty_steps'] in content
        assert 'Menge nicht erfasst' in content and 'Einheit nicht erfasst' in content
        assert 'Vorbereitung:' not in content and 'Zubereitung:' not in content
    elif case == 'provenance':
        assert all(f'Beleg {number}' in content for number in range(1, 4))
        assert all(f'2026-09-0{number}T12:00:00Z' in content for number in range(1, 4))
    else:
        assert len(document['prepared']) == 2
        assert 'Arbeitsschritte, Bilder und Herkunft stehen bei der ersten Ausgabe' in content


def test_pinned_tabler_icons_paint_as_vectors_without_font_glyphs(tmp_path):
    pdf = RecipeSheet(default_config(), None)
    names = ('components', 'clipboard-check', 'history', 'tools-kitchen-2', 'alert-triangle', 'info-circle')
    for index, name in enumerate(names):
        pdf.icon(name, 60 + index * 70, 60, 24)
    data = bytes(pdf.output())
    pdf_receipt(data, tmp_path, 'icons')
    reader = PdfReader(BytesIO(data))
    assert not list(reader.pages[0].images), 'Tabler icons must be painted vectors, not raster replacements.'
    with Image.open(tmp_path / 'icons-1.png') as image:
        ratio = image.height / 841.89
        for index, name in enumerate(names):
            x = 60 + index * 70
            crop = image.crop((int(x * ratio), int(60 * ratio), int((x + 24) * ratio), int(84 * ratio)))
            dark = sum(crop.convert('L').histogram()[:160])
            assert dark >= 30, (name, dark)
