#!/usr/bin/env python3
"""Reproduce or verify the pinned food symbols; no runtime downloads or new dependencies."""
from __future__ import annotations

import argparse
import ast
import io
import json
import logging
import re
import sys
import tarfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from vendor_tabler import check_hash, destination, member_bytes

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'reference_scaffold/cafeteria/static/vendor/food-symbols'
MANIFEST = VENDOR / 'manifest.json'
MAX_BYTES = 8 * 1024 * 1024
ALLERGEN_FILES = {
    'GLUTEN': 'gluten', 'CRUSTACEANS': 'crustaceans', 'EGGS': 'eggs', 'FISH': 'fish',
    'PEANUTS': 'peanuts', 'SOY': 'soya', 'MILK': 'milk', 'NUTS': 'nuts',
    'CELERY': 'celery', 'MUSTARD': 'mustard', 'SESAME': 'sesame',
    'SULPHITES': 'so2', 'LUPIN': 'lupin', 'MOLLUSCS': 'molluscs',
}


def application_catalogs() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    seed = (ROOT / 'database/seed.sql').read_text()
    section = seed.split('INSERT INTO allergens(code, display_name, eu_number)', 1)[1].split('ON CONFLICT', 1)[0]
    allergens = {
        code: {'name': name, 'eu_number': int(number)}
        for code, name, number in re.findall(r"\('([A-Z_]+)', '([^']+)', (\d+)\)", section)
    }
    template = (ROOT / 'reference_scaffold/cafeteria/templates/admin/_country_select.html').read_text()
    literal = template.split('{% set countries = ', 1)[1].split(' %}', 1)[0]
    countries = ast.literal_eval(literal)
    if set(allergens) != set(ALLERGEN_FILES) or not isinstance(countries, dict):
        raise ValueError('Application catalog changed; review the symbol mapping')
    if len(countries) != 249 or any(not re.fullmatch('[A-Z]{2}', code) for code in countries):
        raise ValueError('Country selection changed; review the flag mapping')
    return allergens, countries


def validate_svg(data: bytes, label: str) -> None:
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError(f'External XML definitions are not allowed: {label}')
    root = ET.fromstring(data)
    if root.tag != '{http://www.w3.org/2000/svg}svg' or 'viewBox' not in root.attrib:
        raise ValueError(f'Missing SVG viewBox: {label}')
    viewbox = [float(value) for value in root.attrib['viewBox'].split()]
    if len(viewbox) != 4 or viewbox[2] <= 0 or viewbox[3] <= 0:
        raise ValueError(f'Invalid SVG dimensions: {label}')
    for node in root.iter():
        tag = node.tag.rsplit('}', 1)[-1]
        if tag in {'script', 'foreignObject', 'image', 'animate', 'animateTransform', 'set'}:
            raise ValueError(f'Non-static SVG element: {label}: {tag}')
        for key, value in node.attrib.items():
            local = key.rsplit('}', 1)[-1].lower()
            if local.startswith('on') or (local == 'href' and not value.startswith('#')):
                raise ValueError(f'External/active SVG attribute: {label}: {key}')
        for value in [*node.attrib.values(), node.text or '']:
            references = re.findall(r'url\(([^)]*)\)', value)
            if '@import' in value or any(not ref.strip(' \"\'').startswith('#') for ref in references):
                raise ValueError(f'External SVG resource: {label}')


def load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text())
    if manifest['schema_version'] != 1:
        raise ValueError('Unsupported food-symbol manifest')
    allergens, countries = application_catalogs()
    if set(manifest['allergens']) != set(allergens) or set(manifest['countries']) != set(countries):
        raise ValueError('Manifest does not cover the application catalogs exactly')
    paths = [row['path'] for row in manifest['files']]
    if len(paths) != len(set(paths)) or len(paths) != 265:
        raise ValueError('Expected exactly 14 allergen SVGs, 249 flags and two licenses')
    for code, expected in allergens.items():
        row = manifest['allergens'][code]
        if (row['name'] != expected['name'] or row['eu_number'] != expected['eu_number']
                or row['text_fallback'] != expected['name']
                or row['file'] != f'allergens/{ALLERGEN_FILES[code]}.svg'):
            raise ValueError(f'Allergen mapping differs from seed: {code}')
    for code, name in countries.items():
        row = manifest['countries'][code]
        if row != {'name': name, 'text_fallback': code, 'file': f'flags/{code.lower()}.svg'}:
            raise ValueError(f'Country mapping differs from existing selection: {code}')
    expected_paths = {row['file'] for key in ('allergens', 'countries') for row in manifest[key].values()}
    expected_paths.update(row['license_file'] for row in manifest['sources'].values())
    if set(paths) != expected_paths or any('free-from' in row['member'] for row in manifest['files']):
        raise ValueError('Unmapped file or forbidden free-from symbol')
    for row in manifest['files']:
        path = row['path']
        source_key = 'erudus' if path.startswith('allergens/') or path == 'licenses/erudus-LICENSE' else 'flag-icons'
        source = manifest['sources'][source_key]
        repository = {'erudus': 'Erudus/erudus-icons', 'flag-icons': 'lipis/flag-icons'}[source_key]
        member_path = ('src/svg/' + Path(path).name if path.startswith('allergens/')
                       else 'flags/4x3/' + Path(path).name if path.startswith('flags/') else 'LICENSE')
        expected_member = f"{repository.split('/')[1]}-{source['commit']}/{member_path}"
        if (row['source'] != source_key or row['member'] != expected_member
                or source['repository'] != repository or source['license'] != 'MIT'):
            raise ValueError(f'Incorrect source-to-code mapping: {path}')
    return manifest


def source_bytes(source: dict[str, Any], cache: Path | None) -> bytes:
    url = urllib.parse.urlsplit(source['archive_url'])
    expected = f"/{source['repository']}/tar.gz/{source['commit']}"
    if (url.scheme != 'https' or url.netloc != 'codeload.github.com' or url.path != expected
            or url.query or url.fragment or not re.fullmatch('[0-9a-f]{40}', source['commit'])):
        raise ValueError('Source must be the commit-pinned official GitHub archive')
    cached = cache / source['cache_file'] if cache else None
    if cached and cached.is_file():
        data = cached.read_bytes()
    else:
        with urllib.request.urlopen(source['archive_url'], timeout=45) as response:
            data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Archive exceeds size limit')
    check_hash(data, source['archive_sha256'], source['repository'])
    return data


def build(manifest: dict[str, Any], output: Path, cache: Path | None) -> None:
    sources = {key: source_bytes(row, cache) for key, row in manifest['sources'].items()}
    pending = []
    for row in manifest['files']:
        with tarfile.open(fileobj=io.BytesIO(sources[row['source']]), mode='r:gz') as archive:
            data = member_bytes(archive, row['member'])
        check_hash(data, row['sha256'], row['path'])
        if row['path'].endswith('.svg'):
            validate_svg(data, row['path'])
        pending.append((destination(output, row['path']), data))
    audit = manifest['pdf_compatibility']
    audit_data = destination(VENDOR, audit['file']).read_bytes()
    check_hash(audit_data, audit['sha256'], audit['file'])
    pending.append((destination(output, audit['file']), audit_data))
    changed = 0
    for path, data in pending:
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
        changed += 1
    print(f'FOOD SYMBOL BUILD: {len(pending)} verified artifacts; {changed} changed.')


def verify(manifest: dict[str, Any], output: Path) -> None:
    expected_svgs = set()
    for row in manifest['files']:
        path = destination(output, row['path'])
        data = path.read_bytes()
        check_hash(data, row['sha256'], row['path'])
        if path.suffix == '.svg':
            validate_svg(data, row['path'])
            expected_svgs.add(path.resolve())
    if {path.resolve() for path in output.rglob('*.svg')} != expected_svgs:
        raise ValueError('Unmapped SVG files in output directory')
    audit = manifest['pdf_compatibility']
    data = destination(output, audit['file']).read_bytes()
    check_hash(data, audit['sha256'], audit['file'])
    report = json.loads(data)
    expected = {f'{group}/{code}' for group in ('allergens', 'countries') for code in manifest[group]}
    if (report['renderer'] != audit['renderer'] or report['version'] != audit['version']
            or set(report['results']) != expected):
        raise ValueError('PDF compatibility audit does not cover all symbols')
    print('FOOD SYMBOL VERIFY: 14 allergens, 249 countries, 265 source artifacts + PDF audit; offline PASS.')


def check_pdf(manifest: dict[str, Any], output: Path, artifacts: Path) -> None:
    from fpdf import FPDF, __version__

    if __version__ != '2.8.8':
        raise ValueError(f'Expected project renderer fpdf2 2.8.8, got {__version__}')
    messages: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    handler = Capture()
    logger = logging.getLogger('fpdf')
    logger.addHandler(handler)
    records = {}
    try:
        for group in ('allergens', 'countries'):
            for code, row in manifest[group].items():
                messages.clear()
                error_message = None
                try:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.image(str(output / row['file']), x=10, y=10, w=20, h=20, keep_aspect_ratio=True)
                    if not bytes(pdf.output()).startswith(b'%PDF'):
                        raise ValueError('Renderer did not produce PDF')
                except (ValueError, TypeError, NotImplementedError, AssertionError) as error:
                    error_message = str(error)
                records[f'{group}/{code}'] = {
                    'file': row['file'],
                    'status': 'requires_conversion' if error_message or messages else 'renders_without_warning',
                    'error': error_message, 'warnings': sorted(set(messages)),
                }
    finally:
        logger.removeHandler(handler)
    artifacts.mkdir(parents=True, exist_ok=True)
    report = {'renderer': 'fpdf2', 'version': __version__, 'results': records}
    (artifacts / 'pdf-compatibility.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    contact = FPDF()
    contact.set_auto_page_break(False)
    contact.add_font('Carlito', fname=ROOT / 'reference_scaffold/cafeteria/static/fonts/weekly-print-carlito.ttf')
    for group, columns, rows_per_page in [('allergens', 4, 5), ('countries', 7, 13)]:
        cell_width, cell_height = 190 / columns, 245 / rows_per_page
        for index, (code, row) in enumerate(manifest[group].items()):
            position = index % (columns * rows_per_page)
            if position == 0:
                contact.add_page()
                contact.set_font('Carlito', size=15)
                contact.text(10, 13, 'Kontaktbogen: Allergene' if group == 'allergens' else 'Kontaktbogen: Herkunft')
                contact.set_font('Carlito', size=9)
                contact.text(10, 20, 'fpdf2 2.8.8 · Technische Vorschau, keine Geräte- oder Druckabnahme')
            x, y = 10 + (position % columns) * cell_width, 26 + (position // columns) * cell_height
            record = records[f'{group}/{code}']
            if record['status'] == 'renders_without_warning':
                contact.image(str(output / row['file']), x=x+3, y=y, w=cell_width-8,
                              h=cell_height-12, keep_aspect_ratio=True)
            else:
                contact.set_font('Carlito', size=7)
                contact.set_xy(x, y+2)
                contact.multi_cell(cell_width-2, 3, 'SVG-Konvertierung\nnötig; Textfallback')
            contact.set_font('Carlito', size=8 if group == 'allergens' else 6.5)
            contact.set_xy(x, y+cell_height-10)
            contact.multi_cell(cell_width-2, 3.2, f"{code}\n{row['name']}")
    contact.output(artifacts / 'contact-sheet.pdf')
    ready = sum(row['status'] == 'renders_without_warning' for row in records.values())
    failures = sum(row['error'] is not None for row in records.values())
    print(f'FOOD SYMBOL PDF: {ready}/263 render without warning; {263-ready} require conversion '
          f'({failures} errors); all source SVGs retained. Contact sheet: {contact.pages_count} pages.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify', action='store_true', help='Offline hash/catalog/SVG verification')
    action.add_argument('--build', action='store_true', help='Copy only verified pinned source members')
    action.add_argument('--pdf-check', action='store_true', help='Audit all SVGs with existing fpdf2; emit report/contact sheet')
    parser.add_argument('--output-dir', type=Path, default=VENDOR)
    parser.add_argument('--cache-dir', type=Path, help='Optional source archives, verified before use')
    parser.add_argument('--artifact-dir', type=Path, default=ROOT / '.claude/artifacts/food-symbols')
    args = parser.parse_args()
    try:
        manifest = load_manifest()
        if args.build:
            build(manifest, args.output_dir, args.cache_dir)
        verify(manifest, args.output_dir)
        if args.pdf_check:
            check_pdf(manifest, args.output_dir, args.artifact_dir)
    except (OSError, ValueError, KeyError, IndexError, SyntaxError, tarfile.TarError, ET.ParseError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
