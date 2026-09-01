#!/usr/bin/env python3
"""Offline-Vertragspruefung des Pakets mit zwei Publikationsprofilen.

Kein Docker- oder PostgreSQL-Start. Die Ausgabe unterscheidet bewusst zwischen
Artefaktpruefung und noch offenen Live-Nachweisen.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageStat

EXPECTED_ROLES = {'Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'}
PRIMARY_SCREENSHOTS = {
    'signage-cafeteria-tag-1920x1080.png': (1920, 1080),
    'signage-cafeteria-woche-1920x1080.png': (1920, 1080),
    'signage-cafeteria-geschlossen-1920x1080.png': (1920, 1080),
    'signage-patienten-tag-1920x1080.png': (1920, 1080),
    'signage-patienten-woche-1920x1080-vorschau.png': (1920, 1080),
    'signage-patienten-woche-3840x2160.png': (3840, 2160),
    'mobile-cafeteria-heute-390x844.png': (390, 844),
    'mobile-cafeteria-woche-390x844.png': (390, 844),
    'mobile-patienten-heute-390x844.png': (390, 844),
    'mobile-patienten-woche-390x844.png': (390, 844),
    'website-cafeteria-woche-1440x1100.png': (1440, 1100),
    'website-patienten-woche-1440x1100.png': (1440, 1100),
    'admin-cafeteria-1440x900.png': (1440, 900),
    'admin-patienten-1440x900.png': (1440, 900),
}
REQUIRED_FILES = (
    'README.md', 'CHANGELOG.md', 'SOURCES.md', 'VALIDATION.md',
    'docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.md',
    'docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.docx',
    'docs/GROK_KRITIK_UMSETZUNG.md', 'review/Grok_Kritik_original.txt',
    'docs/ABNAHME_CHECKLISTE.md', 'docs/CSV_IMPORT_EXPORT.md',
    'docs/ENTRA_SSO_BETRIEBSKONZEPT.md', 'docs/DOCKER_COMPOSE_RUNBOOK.md',
    'database/schema.sql', 'database/migrations/0001_initial_postgresql.sql',
    'database/seed.sql', 'database/seed_demo.sql', 'database/permissions.sql',
    'demo/snapshots/patienten_kw36.json', 'demo/snapshots/cafeteria_kw36.json',
    'csv/menu_patient_template.csv', 'csv/menu_patient_example.csv',
    'csv/menu_cafeteria_template.csv', 'csv/menu_cafeteria_example.csv',
    'deployment/docker-compose.yml', 'deployment/Dockerfile', 'deployment/.env.example',
    'deployment/redis-healthcheck.sh', 'entra/app-roles-manifest.json',
    'entra/role-mapping.yaml', 'entra/configure-entra-app.ps1',
    'reference_scaffold/requirements.txt', 'design/SCREENSHOT_INDEX.md',
    'tools/capture_screenshots.py', 'tools/build_sdd_docx.py',
    'tools/build_manifest.py', 'PACKAGE_CONTENTS.txt', 'MANIFEST_SHA256.txt',
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forbidden_patient_keys(value: Any, path: str = '$') -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lower = key.lower()
            if (
                lower in {'price', 'prices', 'preis', 'preise', 'internal_rappen', 'external_rappen', 'currency', 'chf', 'rappen'}
                or lower.endswith('_rappen')
                or re.search(r'(^|_)(price|preis)(_|$)', lower)
            ):
                found.append(f'{path}.{key}')
            found.extend(forbidden_patient_keys(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_patient_keys(child, f'{path}[{index}]'))
    return found


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    successes: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def ok(message: str) -> None:
        successes.append(message)

    # Paket und Geheimnisse
    for relative in REQUIRED_FILES:
        check((root / relative).is_file(), f'Pflichtdatei fehlt: {relative}')
    check(not (root / 'deployment/.env').exists(), 'deployment/.env darf nicht im Paket liegen.')
    secret_dir = root / 'deployment/secrets'
    unexpected = []
    if secret_dir.exists():
        unexpected = [p.name for p in secret_dir.iterdir() if p.is_file() and p.name not in {'.gitignore', 'README.md'}]
    check(not unexpected, f'Unerwartete Secret-Dateien: {unexpected}')
    check(not any(path.is_symlink() for path in root.rglob('*')), 'Paket enthaelt symbolische Links.')
    check(not any('__pycache__' in path.parts or '.pytest_cache' in path.parts for path in root.rglob('*')), 'Cache-Verzeichnisse muessen vor dem Paketbau entfernt werden.')
    ok(f'{len(REQUIRED_FILES)} Pflichtartefakte und Secret-Ausschluss geprueft')

    # SDD und Reviewgrundlage
    sdd = (root / 'docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.md').read_text(encoding='utf-8')
    for token in (
        'Entwurf, intern technisch geprüft; nicht fachlich abgenommen',
        'Montag bis Sonntag', 'Mittag und Abend', 'Menü 1 und Vegetarisch',
        '/signage/cafeteria/tag', '/signage/cafeteria/woche',
        '/signage/patienten/tag', '/signage/patienten/woche',
        '3840 × 2160', 'keine Kosteninformation',
    ):
        check(token in sdd, f'SDD-Pflichtinhalt fehlt: {token}')
    check('Verbindliche Zielarchitektur und Implementierungsgrundlage' not in sdd, 'SDD behauptet weiterhin ungerechtfertigte Reife.')
    check('SQL-Baseline' in sdd and 'Alembic' in sdd and 'Anspruch entfernt' in sdd, 'Migrationsehrlichkeit fehlt im SDD.')
    headings = re.findall(r'^(#{1,6})\s+(.+)$', sdd, re.M)
    check(sum(1 for line in sdd.splitlines() if line.strip().startswith('```')) % 2 == 0, 'Ungerade Zahl Markdown-Codefences.')
    review = (root / 'review/Grok_Kritik_original.txt').read_text(encoding='utf-8')
    check('Zwei Profile, zwei Publikationsstränge' in review, 'Reviewgrundlage wirkt unvollstaendig.')
    check('Vier Player-Flächen' in review, 'Reviewgrundlage enthaelt die vier Player nicht.')
    ok(f'SDD mit {len(headings)} Ueberschriften und unveraenderte Reviewgrundlage geprueft')

    # Rollen
    manifest = json.loads((root / 'entra/app-roles-manifest.json').read_text(encoding='utf-8'))
    role_values = {role['value'] for role in manifest['appRoles']}
    check(role_values == EXPECTED_ROLES, f'Entra-Rollen abweichend: {sorted(role_values)}')
    check(len({role['id'] for role in manifest['appRoles']}) == 3, 'App-Rollen-IDs nicht eindeutig.')
    mapping = yaml.safe_load((root / 'entra/role-mapping.yaml').read_text(encoding='utf-8'))
    check(set(mapping.get('roles', {})) == EXPECTED_ROLES, 'Rollenmapping weicht vom Manifest ab.')
    publisher = set(mapping['roles']['Cafeteria.Publisher']['capabilities'])
    check({'draft.write', 'publication.publish'} <= publisher, 'Publisher braucht Korrektur- und Publikationsrecht.')
    code_roles = (root / 'reference_scaffold/cafeteria/roles.py').read_text(encoding='utf-8')
    for role in EXPECTED_ROLES:
        check(role in code_roles and role in sdd, f'Rolle nicht durchgaengig dokumentiert: {role}')
    for obsolete in ('Cafeteria.MasterData', 'Cafeteria.Auditor'):
        check(obsolete not in code_roles and obsolete not in json.dumps(manifest), f'Alte Rolle noch aktiv: {obsolete}')
    ok('Drei Entra-Rollen konsistent; Publisher darf korrigieren')

    # Snapshots
    patient = json.loads((root / 'demo/snapshots/patienten_kw36.json').read_text(encoding='utf-8'))
    cafeteria = json.loads((root / 'demo/snapshots/cafeteria_kw36.json').read_text(encoding='utf-8'))
    check(patient.get('profile_code') == 'patient', 'Patienten-Snapshot hat falsches Profil.')
    check(cafeteria.get('profile_code') == 'staff_guest', 'Cafeteria-Snapshot hat falsches Profil.')
    patient_services = [service for day in patient.get('days', []) for service in day.get('services', [])]
    cafeteria_services = [service for day in cafeteria.get('days', []) for service in day.get('services', [])]
    check(len(patient.get('days', [])) == 7 and len(patient_services) == 14, 'Patienten-Snapshot ist nicht 7 Tage x 2 Mahlzeiten.')
    cafeteria_service_days = [day for day in cafeteria.get('days', []) if day.get('services')]
    cafeteria_weekend_days = [day for day in cafeteria.get('days', []) if day.get('date') and date.fromisoformat(day['date']).weekday() >= 5]
    check(
        len(cafeteria_services) == 5
        and len(cafeteria_service_days) == 5
        and all(date.fromisoformat(day['date']).weekday() < 5 for day in cafeteria_service_days)
        and all(service.get('meal_code') == 'LUNCH' for service in cafeteria_services)
        and all(not day.get('services') for day in cafeteria_weekend_days),
        'Cafeteria-Snapshot ist nicht Mo-Fr x Mittag beziehungsweise enthält Wochenendservices.',
    )
    check(all(len(service.get('options', [])) == 2 for service in patient_services + cafeteria_services), 'Nicht jeder offene Service hat zwei Menuearten.')
    check({o.get('type_code') for s in patient_services for o in s.get('options', [])} == {'MENU_1', 'VEGGIE'}, 'Patienten-Menuearten unvollstaendig.')
    check(not forbidden_patient_keys(patient), f'Patienten-Snapshot enthaelt Kostenschluessel: {forbidden_patient_keys(patient)}')
    patient_text = json.dumps(patient, ensure_ascii=False)
    check(not re.search(r'\b(CHF|Rappen|0\.00)\b', patient_text, re.I), 'Patienten-Snapshot enthaelt Kostenwerte/-begriffe.')
    check(all('prices' in option for service in cafeteria_services for option in service['options']), 'Cafeteria-Snapshot ohne Preise.')
    check(any(day.get('date') == '2026-09-06' and any(s.get('meal_code') == 'DINNER' for s in day.get('services', [])) for day in patient['days']), 'Patienten-Sonntagabend fehlt.')
    ok('Getrennte Demo-Snapshots: 14 Patienten- und 5 Cafeteria-Services, je zwei Menuearten')

    # CSV
    csv_dir = root / 'csv'
    formats = {
        'patient': ('menu_patient_template.csv', 'menu_patient_example.csv', 17, 28),
        'staff_guest': ('menu_cafeteria_template.csv', 'menu_cafeteria_example.csv', 19, 10),
    }
    for profile, (template_name, example_name, header_count, row_count) in formats.items():
        with (csv_dir / template_name).open(encoding='utf-8-sig', newline='') as handle:
            template_headers = next(csv.reader(handle, delimiter=';'))
        with (csv_dir / example_name).open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle, delimiter=';')
            example_headers = reader.fieldnames or []
            rows = list(reader)
        check(template_headers == example_headers, f'{profile}: Vorlage und Beispiel haben andere Header.')
        check(len(example_headers) == header_count, f'{profile}: falsche Headerzahl {len(example_headers)}.')
        check(len(rows) == row_count, f'{profile}: falsche Beispielzeilenzahl {len(rows)}.')
        result = run([sys.executable, 'validate_menu_csv.py', example_name, '--json'], csv_dir)
        check(result.returncode == 0, f'{profile}: CSV-Validator fehlgeschlagen: {result.stderr or result.stdout}')
        if profile == 'patient':
            check(not any(re.search(r'(preis|chf|rappen|cost|price)', h, re.I) for h in example_headers), 'Patienten-CSV enthaelt Kostenspalte.')
        else:
            check({'preis_mitarbeitende_chf', 'preis_externe_chf'} <= set(example_headers), 'Cafeteria-Kostenspalten fehlen.')
    ok('Zwei profilbezogene CSV-Formate mit 28 beziehungsweise 10 Datenzeilen validiert')

    # Datenbank
    db_result = run([sys.executable, 'database/validate_schema.py'], root)
    check(db_result.returncode == 0, f'Schema-Validator fehlgeschlagen: {db_result.stderr or db_result.stdout}')
    if db_result.returncode == 0:
        status = json.loads(db_result.stdout)
        check(status.get('tables') == 24, 'Schema enthaelt nicht 24 Tabellen.')
        check(status.get('application_roles') == 3, 'Schema enthaelt nicht drei Rollen.')
        check(status.get('offer_profiles') == 2, 'Schema enthaelt nicht zwei Profile.')
        check(status.get('patient_services') == 14, 'Demo-Seed enthaelt nicht 14 Patienten-Services.')
        check(status.get('cafeteria_services') == 5, 'Demo-Seed enthaelt nicht 5 Cafeteria-Services.')
    schema = root / 'database/schema.sql'
    migration = root / 'database/migrations/0001_initial_postgresql.sql'
    check(schema.read_bytes() == migration.read_bytes(), 'SQL-Baseline ist nicht byteidentisch zu schema.sql.')
    schema_text = schema.read_text(encoding='utf-8')
    for token in ('validate_menu_service', 'validate_menu_item_price', 'validate_publication_revision', 'jsonb_has_patient_forbidden_key'):
        check(token in schema_text, f'DB-Vertragsfunktion fehlt: {token}')
    requirements = (root / 'reference_scaffold/requirements.txt').read_text(encoding='utf-8')
    check('alembic' not in requirements.lower(), 'Alembic steht noch in den Laufzeitanforderungen.')
    ok(f'PostgreSQL-Artefakte statisch geprueft; SHA-256 {sha256(schema)}')

    # Routen, Jinja und Patientenkostenverbot
    route_text = (root / 'reference_scaffold/cafeteria/signage/routes.py').read_text(encoding='utf-8')
    for route in ('/signage/cafeteria/tag', '/signage/cafeteria/woche', '/signage/patienten/tag', '/signage/patienten/woche'):
        check(route in route_text, f'Signage-Route fehlt: {route}')
    check('request.args' in route_text, 'Signage sperrt Query-Parameter nicht.')
    public_routes = (root / 'reference_scaffold/cafeteria/public/routes.py').read_text(encoding='utf-8')
    check("request.args.get('date')" not in public_routes, 'Oeffentliche Datumssteuerung ist noch vorhanden.')
    template_root = root / 'reference_scaffold/cafeteria/templates'
    environment = Environment(loader=FileSystemLoader(str(template_root)))
    for path in sorted(template_root.rglob('*.html')):
        try:
            environment.parse(path.read_text(encoding='utf-8'))
        except Exception as exc:
            errors.append(f'Jinja-Fehler in {path.relative_to(root)}: {exc}')
    patient_templates = list((template_root / 'public').glob('patient*.html')) + [template_root / 'public/print_patient_week.html'] + list((template_root / 'signage').glob('patient*.html')) + [template_root / 'admin/patienten.html']
    forbidden_markup = re.compile(r'\b(CHF|Rappen|Intern|Extern|0\.00)\b|prices|price-row|signage-price|admin-price', re.I)
    for path in patient_templates:
        check(not forbidden_markup.search(path.read_text(encoding='utf-8')), f'Patienten-Template enthaelt Kostenmarkup: {path.relative_to(root)}')
    pytest_result = run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'reference_scaffold/tests'], root)
    check(pytest_result.returncode == 0, f'Vertragstests fehlgeschlagen: {pytest_result.stderr or pytest_result.stdout}')
    ok('Flask-Routen, Jinja-Templates und Offline-Vertragstests geprueft')

    # Compose, Shell und Python
    compose_result = run([sys.executable, 'deployment/validate_compose.py'], root)
    check(compose_result.returncode == 0, f'Compose-Validator fehlgeschlagen: {compose_result.stderr or compose_result.stdout}')
    compose_text = (root / 'deployment/docker-compose.yml').read_text(encoding='utf-8')
    check('redis-cli -a' not in compose_text, 'Redis-Passwort steht weiterhin im Healthcheck-Kommando.')
    config_text = (root / 'reference_scaffold/cafeteria/config.py').read_text(encoding='utf-8')
    check("self.APP_ENV == 'production'" in config_text and 'DEMO_MODE, SEED_DEMO und DEMO_TODAY' in config_text, 'Produktionssperre fuer Demo fehlt.')
    shell_files = sorted(root.glob('deployment/**/*.sh'))
    for path in shell_files:
        result = run(['sh', '-n', str(path)], root)
        check(result.returncode == 0, f'Shell-Syntaxfehler in {path.relative_to(root)}: {result.stderr}')
    py_files = [path for path in root.rglob('*.py') if '__pycache__' not in path.parts]
    for path in py_files:
        try:
            source = path.read_text(encoding='utf-8-sig')
            compile(source, str(path), 'exec')
        except Exception as exc:
            errors.append(f'Python-Syntaxfehler in {path.relative_to(root)}: {exc}')
    ok(f'Compose statisch, {len(shell_files)} Shell- und {len(py_files)} Python-Dateien geprueft')

    # Prototypen und Screenshots
    prototype = root / 'design/prototype'
    css_a = prototype / 'assets/app.css'
    css_b = root / 'reference_scaffold/cafeteria/static/app.css'
    check(css_a.read_bytes() == css_b.read_bytes(), 'Prototype- und Scaffold-CSS weichen ab.')
    patient_proto = list(prototype.glob('patienten-*.html')) + list(prototype.glob('signage-patienten-*.html')) + [prototype / 'admin-patienten.html']
    cafeteria_proto = list(prototype.glob('cafeteria-*.html')) + list(prototype.glob('signage-cafeteria-*.html')) + [prototype / 'admin-cafeteria.html']
    for path in patient_proto:
        text_value = path.read_text(encoding='utf-8')
        check('Menü 1' in text_value and 'Vegetarisch' in text_value, f'Zwei Menuearten fehlen in {path.name}.')
        check(not re.search(r'\b(CHF|Rappen|Intern|Extern|0\.00)\b|class="[^"]*(price|preis)', text_value, re.I), f'Patienten-Prototyp enthaelt Kosteninformation: {path.name}')
    for path in cafeteria_proto:
        text_value = path.read_text(encoding='utf-8')
        if 'geschlossen' not in path.name:
            check('Menü 1' in text_value and 'Vegetarisch' in text_value, f'Zwei Menuearten fehlen in {path.name}.')
            check('Mitarbeitende' in text_value and 'Externe' in text_value, f'Cafeteria-Kostenadressaten fehlen in {path.name}.')
    for name, expected in PRIMARY_SCREENSHOTS.items():
        path = root / 'design/screenshots' / name
        check(path.is_file(), f'Screenshot fehlt: {name}')
        if path.is_file():
            with Image.open(path) as image:
                check(image.size == expected, f'Falsche Abmessung {name}: {image.size}, erwartet {expected}.')
                grayscale = image.convert('L').resize((64, 64))
                check(ImageStat.Stat(grayscale).var[0] > 10, f'Screenshot wirkt leer/einfarbig: {name}')
    check(len(list((root / 'design/screenshots').glob('*.png'))) >= 17, 'Weniger als 14 Primaer- plus 3 Kompatibilitaetsbilder.')
    ok(f'{len(PRIMARY_SCREENSHOTS)} primaere Screenshots mit Zielmassen und sichtbarem Inhalt geprueft')

    # Diagramme und DOCX-Struktur
    for stem in ('system_architecture', 'erd', 'auth_flow', 'csv_flow'):
        for suffix in ('.dot', '.png', '.svg'):
            check((root / 'architecture' / f'{stem}{suffix}').is_file(), f'Diagramm fehlt: {stem}{suffix}')
    docx = root / 'docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.docx'
    try:
        with zipfile.ZipFile(docx) as archive:
            names = set(archive.namelist())
            check('word/document.xml' in names, 'DOCX enthaelt kein document.xml.')
            check(any(name.startswith('word/media/') for name in names), 'DOCX enthaelt keine eingebetteten Bilder.')
    except zipfile.BadZipFile as exc:
        errors.append(f'DOCX ist ungueltig: {exc}')
    ok('Diagrammquellen/-renderings und DOCX-Paketstruktur geprueft')

    # JSON/YAML allgemein
    for path in root.rglob('*.json'):
        try:
            json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            errors.append(f'Ungueltiges JSON in {path.relative_to(root)}: {exc}')
    for path in root.rglob('*.yaml'):
        try:
            yaml.safe_load(path.read_text(encoding='utf-8'))
        except Exception as exc:
            errors.append(f'Ungueltiges YAML in {path.relative_to(root)}: {exc}')

    print('OFFLINE-PAKETPRUEFUNG')
    for message in successes:
        print(f'[OK] {message}')
    if errors:
        print('\nFEHLER:')
        for error in errors:
            print(f'[FEHLER] {error}')
        return 1
    print('\nPaketpruefung erfolgreich. Live-PostgreSQL, Docker, Entra, Backup/Restore und Fachabnahme sind separat auszufuehren.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
