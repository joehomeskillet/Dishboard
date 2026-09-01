from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'csv'))

from demo_snapshots import cafeteria_snapshot, patient_snapshot  # noqa: E402
from validate_menu_csv import validate_file  # noqa: E402


def forbidden_patient_keys(value, path='$'):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            lower = key.lower()
            if lower in {'price', 'prices', 'preis', 'preise', 'internal_rappen', 'external_rappen', 'currency', 'chf', 'rappen'} or lower.endswith('_rappen') or re.search(r'(^|_)(price|preis)(_|$)', lower):
                found.append(f'{path}.{key}')
            found.extend(forbidden_patient_keys(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_patient_keys(child, f'{path}[{index}]'))
    return found


def test_demo_snapshots_are_separate():
    cafeteria = cafeteria_snapshot()
    patient = patient_snapshot()
    assert cafeteria['profile_code'] == 'staff_guest'
    assert patient['profile_code'] == 'patient'
    assert len([service for day in cafeteria['days'] for service in day['services']]) == 5
    assert len([service for day in patient['days'] for service in day['services']]) == 14
    assert not forbidden_patient_keys(patient)
    patient_text = json.dumps(patient, ensure_ascii=False)
    assert 'CHF' not in patient_text
    assert '0.00' not in patient_text
    assert 'Pastetli mit Brätkügeli' in patient_text


def test_profile_csv_examples_are_valid():
    cafeteria = validate_file(ROOT / 'csv' / 'menu_cafeteria_example.csv')
    patient = validate_file(ROOT / 'csv' / 'menu_patient_example.csv')
    assert cafeteria['valid'], cafeteria['errors']
    assert patient['valid'], patient['errors']
    assert len(cafeteria['headers']) == 19
    assert len(patient['headers']) == 17
    assert not any(re.search(r'(preis|chf|rappen)', header, re.I) for header in patient['headers'])


def test_templates_parse_and_patient_templates_have_no_cost_markup():
    template_root = ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'
    environment = Environment(loader=FileSystemLoader(str(template_root)))
    paths = sorted(template_root.rglob('*.html'))
    for path in paths:
        environment.parse(path.read_text(encoding='utf-8'))
    patient_paths = [
        template_root / 'public' / 'patient_today.html',
        template_root / 'public' / 'patient_week.html',
        template_root / 'public' / 'print_patient_week.html',
        template_root / 'signage' / 'patient_day.html',
        template_root / 'signage' / 'patient_week.html',
        template_root / 'admin' / 'patienten.html',
    ]
    forbidden = re.compile(r'\b(CHF|Rappen|Intern|Extern|0\.00)\b|prices|price-row|signage-price|admin-price', re.I)
    for path in patient_paths:
        assert not forbidden.search(path.read_text(encoding='utf-8')), path


def test_four_fixed_signage_routes_exist_without_date_query():
    routes = (ROOT / 'reference_scaffold' / 'cafeteria' / 'signage' / 'routes.py').read_text(encoding='utf-8')
    for route in (
        '/signage/cafeteria/tag', '/signage/cafeteria/woche',
        '/signage/patienten/tag', '/signage/patienten/woche',
    ):
        assert route in routes
    assert "request.args" in routes
    public_routes = (ROOT / 'reference_scaffold' / 'cafeteria' / 'public' / 'routes.py').read_text(encoding='utf-8')
    assert "request.args.get('date')" not in public_routes
