from __future__ import annotations

import io
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fpdf import FPDF, __version__ as fpdf_version
from pypdf import PdfReader

from test_country_select_template import render as render_countries

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / 'reference_scaffold/cafeteria/static/vendor/food-symbols'
SCRIPT = ROOT / 'tools/vendor_food_symbols.py'
MANIFEST = json.loads((VENDOR / 'manifest.json').read_text())


def run_vendor(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT,
                          capture_output=True, text=True, timeout=60, check=False)


def test_catalog_covers_existing_country_selection_and_allergen_semantics():
    choices = {row['attributes']['value']: row['label'] for row in render_countries('CH').options
               if row['attributes']['value']}
    assert {code: row['name'] for code, row in MANIFEST['countries'].items()} == choices
    assert len(choices) == 249
    assert {code: row['eu_number'] for code, row in MANIFEST['allergens'].items()} == {
        'GLUTEN': 1, 'CRUSTACEANS': 2, 'EGGS': 3, 'FISH': 4, 'PEANUTS': 5,
        'SOY': 6, 'MILK': 7, 'NUTS': 8, 'CELERY': 9, 'MUSTARD': 10,
        'SESAME': 11, 'SULPHITES': 12, 'LUPIN': 13, 'MOLLUSCS': 14,
    }
    assert MANIFEST['allergens']['NUTS']['file'] == 'allergens/nuts.svg'
    assert MANIFEST['allergens']['NUTS']['name'] == 'Schalenfrüchte'
    assert MANIFEST['allergens']['SOY']['file'] == 'allergens/soya.svg'
    assert MANIFEST['allergens']['SULPHITES']['file'] == 'allergens/so2.svg'
    assert all(row['text_fallback'] == row['name'] for row in MANIFEST['allergens'].values())
    assert all(row['text_fallback'] == code for code, row in MANIFEST['countries'].items())
    assert not any('free-from' in row['member'] or 'tabler' in row['member'] for row in MANIFEST['files'])


def test_real_offline_verifier_accepts_complete_pinned_sources():
    result = run_vendor('--verify')
    assert result.returncode == 0, result.stdout + result.stderr
    assert '14 allergens, 249 countries, 2 labels, 268 source artifacts + PDF audit; offline PASS.' in result.stdout


def test_dietary_symbols_are_the_exact_pinned_tabler_outline_members():
    lock = json.loads((VENDOR.parent / 'tabler.lock.json').read_text())
    source = next(row for row in lock['sources'] if row['id'] == 'icons')
    assert MANIFEST['sources']['tabler-icons']['version'] == lock['packages']['@tabler/icons'] == '3.46.0'
    assert MANIFEST['sources']['tabler-icons']['archive_sha256'] == source['sha256']
    assert MANIFEST['sources']['tabler-icons']['integrity'] == source['integrity']
    assert MANIFEST['labels'] == {
        'VEGETARIAN': {'name': 'Vegetarisch', 'text_fallback': 'Vegetarisch', 'file': 'labels/leaf.svg'},
        'VEGAN': {'name': 'Vegan', 'text_fallback': 'Vegan', 'file': 'labels/plant.svg'},
    }
    for name in ('leaf', 'plant'):
        row = next(row for row in MANIFEST['files'] if row['path'] == f'labels/{name}.svg')
        assert row['source'] == 'tabler-icons' and row['member'] == f'package/icons/outline/{name}.svg'
    assert (VENDOR / 'licenses/tabler-icons-LICENSE').read_bytes() == (VENDOR.parent / 'tabler-icons/LICENSE').read_bytes()


@pytest.mark.parametrize('fault', ['modified', 'missing', 'extra_svg', 'pdf_audit', 'modified_label', 'missing_label'])
def test_offline_verifier_rejects_changed_missing_and_unmapped_assets(tmp_path, fault):
    copied = tmp_path / 'symbols'
    shutil.copytree(VENDOR, copied)
    target = copied / 'allergens/nuts.svg'
    if fault.endswith('_label'):
        target = copied / 'labels/leaf.svg'
        fault = fault.removesuffix('_label')
    if fault == 'modified':
        target.write_bytes(target.read_bytes() + b'\n')
    elif fault == 'missing':
        target.unlink()
    elif fault == 'extra_svg':
        (copied / 'free-from-nuts.svg').write_bytes(target.read_bytes())
    else:
        (copied / 'pdf-compatibility.json').write_text('{}')
    result = run_vendor('--verify', '--output-dir', str(copied))
    assert result.returncode == 1
    assert 'ERROR:' in result.stderr
    assert 'offline PASS' not in result.stdout


def test_bad_cached_source_fails_before_any_destination_is_written(tmp_path):
    cache = tmp_path / 'cache'
    cache.mkdir()
    (cache / 'erudus.tar.gz').write_bytes(b'not the pinned archive')
    output = tmp_path / 'output'
    result = run_vendor('--build', '--cache-dir', str(cache), '--output-dir', str(output))
    assert result.returncode == 1
    assert 'SHA256 mismatch' in result.stderr
    assert not output.exists()


@pytest.mark.parametrize('group,codes', [
    ('allergens', tuple(MANIFEST['allergens'])),
    ('countries', ('CH', 'DE', 'AT', 'FR', 'IT', 'GB', 'JP', 'BR', 'NP')),
])
def test_real_fpdf2_renders_all_allergens_and_representative_flags_without_warnings(group, codes, caplog):
    assert fpdf_version == '2.8.8'
    caplog.set_level(logging.WARNING, logger='fpdf')
    pdf = FPDF()
    pdf.add_page()
    for index, code in enumerate(codes):
        row = MANIFEST[group][code]
        pdf.image(str(VENDOR / row['file']), x=10+(index % 5)*35, y=10+(index // 5)*35,
                  w=25, h=25, keep_aspect_ratio=True)
    reader = PdfReader(io.BytesIO(bytes(pdf.output())))
    assert len(reader.pages) == 1
    assert len(reader.pages[0].get_contents().get_data()) > 1000
    assert not caplog.records, [record.message for record in caplog.records]


@pytest.mark.parametrize('code', ['VEGETARIAN', 'VEGAN'])
def test_declared_dietary_svg_renders_native_strokes_without_warnings(code, caplog):
    assert fpdf_version == '2.8.8'
    caplog.set_level(logging.WARNING, logger='fpdf')
    pdf = FPDF()
    pdf.add_page()
    pdf.image(str(VENDOR / MANIFEST['labels'][code]['file']), x=10, y=10, w=25, h=25)
    reader = PdfReader(io.BytesIO(bytes(pdf.output())))
    assert len(reader.pages) == 1
    operations = reader.pages[0].get_contents().operations
    assert any(operator == b'S' for _, operator in operations)
    assert any(operator == b'c' for _, operator in operations)
    assert not caplog.records, [record.message for record in caplog.records]


def test_complete_pdf_audit_keeps_problematic_flags_explicit_and_sources_available():
    audit = json.loads((VENDOR / 'pdf-compatibility.json').read_text())
    assert (audit['renderer'], audit['version']) == ('fpdf2', '2.8.8')
    assert set(audit['results']) == {f'{group}/{code}' for group in ('allergens', 'countries', 'labels') for code in MANIFEST[group]}
    problems = {key.split('/')[1] for key, row in audit['results'].items() if row['status'] == 'requires_conversion'}
    assert problems == {'AI', 'AR', 'BZ', 'BI', 'KY', 'FK', 'GD', 'GT', 'HT', 'KG', 'HR',
                        'MX', 'NI', 'RS', 'GS', 'LK', 'TW', 'TN', 'TC', 'UM', 'US'}
    for key, row in audit['results'].items():
        assert (VENDOR / row['file']).is_file()
        group, code = key.split('/')
        assert row['file'] == MANIFEST[group][code]['file']
        assert MANIFEST[group][code]['text_fallback']
        if row['status'] == 'requires_conversion':
            assert row['error'] or row['warnings']
        else:
            assert row['status'] == 'renders_without_warning'
            assert not row['error'] and not row['warnings']
