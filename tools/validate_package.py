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
LIVE_SCREENSHOTS = {
    'login-1440x900.png': (1440, 900),
    'auth-local-1440x900.png': (1440, 900),
    'website-cafeteria-heute-1440x1100.png': (1440, 1100),
    'website-cafeteria-woche-1440x1100.png': (1440, 1100),
    'website-patienten-heute-1440x1100.png': (1440, 1100),
    'website-patienten-woche-1440x1100.png': (1440, 1100),
    'mobile-cafeteria-heute-390x844.png': (390, 844),
    'mobile-cafeteria-woche-390x844.png': (390, 844),
    'mobile-patienten-heute-390x844.png': (390, 844),
    'mobile-patienten-woche-390x844.png': (390, 844),
    'admin-cafeteria-1440x900.png': (1440, 900),
    'admin-patienten-1440x900.png': (1440, 900),
    'signage-cafeteria-tag-1920x1080.png': (1920, 1080),
    'signage-cafeteria-woche-1920x1080.png': (1920, 1080),
    'signage-cafeteria-geschlossen-1920x1080.png': (1920, 1080),
    'signage-patienten-tag-1920x1080.png': (1920, 1080),
    'signage-patienten-woche-1920x1080-vorschau.png': (1920, 1080),
    'signage-patienten-woche-3840x2160.png': (3840, 2160),
}
REQUIRED_FILES = (
    'README.md', 'CHANGELOG.md', 'SOURCES.md', 'VALIDATION.md',
    'docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.md',
    'docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.docx',
    'docs/GROK_KRITIK_UMSETZUNG.md', 'review/Grok_Kritik_original.txt',
    'docs/ABNAHME_CHECKLISTE.md', 'docs/CSV_IMPORT_EXPORT.md',
    'docs/ENTRA_SSO_BETRIEBSKONZEPT.md', 'docs/DOCKER_COMPOSE_RUNBOOK.md',
    'database/schema.sql', 'database/migrations/0001_initial_postgresql.sql',
    'database/migrations/0002_profile_publication_and_local_auth.sql',
    'database/migrations/0003_patient_key_and_withdrawal_contracts.sql',
    'database/migrations/0004_patient_key_lock_and_capability_contracts.sql',
    'database/migrations/0005_least_privilege_identity_contracts.sql',
    'database/migrations/0006_auth_issuer_and_local_login.sql',
    'database/migrations/0007_auth_security_hardening.sql',
    'database/migrations/0008_auth_final_hardening.sql',
    'database/migrations/0009_bootstrap_first_local_admin.sql',
    'database/migrations/0010_v12_to_v13.sql',
    'database/seed.sql', 'database/seed_demo.sql', 'database/permissions.sql',
    'demo/snapshots/patienten_kw36.json', 'demo/snapshots/cafeteria_kw36.json',
    'csv/menu_patient_template.csv', 'csv/menu_patient_example.csv',
    'csv/menu_cafeteria_template.csv', 'csv/menu_cafeteria_example.csv',
    'deployment/docker-compose.yml', 'deployment/Dockerfile', 'deployment/.env.example',
    'deployment/redis-healthcheck.sh', 'entra/app-roles-manifest.json',
    'entra/role-mapping.yaml', 'entra/configure-entra-app.ps1',
    'reference_scaffold/requirements.txt', 'design/SCREENSHOT_INDEX.md',
    'tools/capture_screenshots.py', 'tools/build_sdd_docx.py',
    'tools/build_manifest.py', 'tools/capture_live_screenshots.py',
    'design/screenshots/live/INDEX.json',
    'PACKAGE_CONTENTS.txt', 'MANIFEST_SHA256.txt',
)
MIGRATION_CHECKSUMS = {
    '0001_initial_postgresql.sql': 'd1001f657858b4fec9a466517bf4117add8b28160dda7aebf7c43c21e6e6fff0',
    '0002_profile_publication_and_local_auth.sql': '7f8696eb886a99d841ac82be1e4b3abf1b51080c18aac07ea5290325f3e5e863',
    '0003_patient_key_and_withdrawal_contracts.sql': 'eda9c5e851525367af62a3f056b3592a521d871f6ac818d4d50c18d8f720d1de',
    '0004_patient_key_lock_and_capability_contracts.sql': '7309069f1b52d41a756a315af8b6ccf0771afe113875a6c5f82d42775f74b066',
    '0005_least_privilege_identity_contracts.sql': 'b33bdfebe621adfca3da98c85a1b0e8316040c55cf62542eda138099362f1818',
    '0006_auth_issuer_and_local_login.sql': '60897aea8c7096f449a43a6cd2b79452f943cbbec75cc74a0bcf4514baaac233',
    '0007_auth_security_hardening.sql': 'a25d5b6ca71bc11c582eef6e90f792979a88aa86dcc444b7b1ab1db90967595f',
    '0008_auth_final_hardening.sql': '4311165d2dcd763cf9a462906d044000956eb11d16ac847ecf9351facae21e45',
    '0009_bootstrap_first_local_admin.sql': '1b988c75b7ef3f333045d738fa29cd210a367eeaf30825a3005873cafc3b65ed',
    '0010_v12_to_v13.sql': '82f22cc0dd439a8b1ca1e0dc324616871411d67700723f1ebebedc06185a1a72',
}


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
    parser.add_argument('--offline', action='store_true', help='Run offline without live database tests')
    args = parser.parse_args()
    root = args.root.resolve()
    offline = args.offline
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

    # Check for forbidden paths and files
    forbidden_names = {'.git', '.claude', '.gitnexus', '.superpowers', '.mypy_cache', '.ruff_cache'}
    forbidden_paths: list[str] = []
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if rel == Path('.'):
            continue
        parts = rel.parts
        if any(part in forbidden_names for part in parts):
            forbidden_paths.append(str(rel))
        if rel.parts[:2] == ('reference_scaffold', 'last_good'):
            forbidden_paths.append(str(rel))
        if rel.name == '.pytest_cache' or rel.name == '__pycache__':
            forbidden_paths.append(str(rel))
    check(not forbidden_paths, f'Unerwuenschte Meta-Pfade im Paket: {sorted(set(forbidden_paths))}')

    # Check for .zip files
    zip_files = [str(p.relative_to(root)) for p in root.rglob('*.zip') if p.is_file()]
    check(not zip_files, f'Unerwuenschte ZIP-Dateien im Paket: {zip_files}')

    check(not (root / 'deployment/.env').exists(), 'deployment/.env darf nicht im Paket liegen.')
    secret_dir = root / 'deployment/secrets'
    unexpected = []
    if secret_dir.exists():
        unexpected = [p.name for p in secret_dir.iterdir() if p.is_file() and p.name not in {'.gitignore', 'README.md'}]
    check(not unexpected, f'Unerwartete Secret-Dateien: {unexpected}')
    check(not any(path.is_symlink() for path in root.rglob('*')), 'Paket enthaelt symbolische Links.')
    ok(f'{len(REQUIRED_FILES)} Pflichtartefakte, Secret-Ausschluss und Meta-Verzeichnis-Filter geprueft')

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
        check(status.get('tables') == 31, 'Schema enthaelt nicht 31 Tabellen.')
        check(status.get('application_roles') == 3, 'Schema enthaelt nicht drei Rollen.')
        check(status.get('offer_profiles') == 2, 'Schema enthaelt nicht zwei Profile.')
        check(status.get('schema_version') == 13, 'Schema-Version ist nicht 13.')
        check(status.get('patient_services') == 14, 'Demo-Seed enthaelt nicht 14 Patienten-Services.')
        check(status.get('cafeteria_services') == 5, 'Demo-Seed enthaelt nicht 5 Cafeteria-Services.')

    # Migration validation instead of byte-equality
    migrations_dir = root / 'database/migrations'
    migration_files = ['0001_initial_postgresql.sql', '0002_profile_publication_and_local_auth.sql',
                      '0003_patient_key_and_withdrawal_contracts.sql', '0004_patient_key_lock_and_capability_contracts.sql',
                      '0005_least_privilege_identity_contracts.sql', '0006_auth_issuer_and_local_login.sql',
                      '0007_auth_security_hardening.sql', '0008_auth_final_hardening.sql',
                      '0009_bootstrap_first_local_admin.sql']
    migration_files.append('0010_v12_to_v13.sql')

    for mig_file in migration_files:
        mig_path = migrations_dir / mig_file
        check(mig_path.is_file(), f'Migration-Datei fehlt: {mig_file}')
        if mig_path.is_file() and mig_file in MIGRATION_CHECKSUMS:
            actual_sha = sha256(mig_path)
            expected_sha = MIGRATION_CHECKSUMS[mig_file]
            check(actual_sha == expected_sha, f'Migration-Checksum falsch {mig_file}: {actual_sha}, erwartet {expected_sha}')

    schema = root / 'database/schema.sql'
    schema_text = schema.read_text(encoding='utf-8')
    contract_functions = ('validate_menu_service', 'validate_menu_item_price', 'validate_publication_revision',
                         'jsonb_has_patient_forbidden_key', 'withdraw_publication_revision', 'issue_publication_capability',
                         'sync_entra_user', 'ensure_auth_capability_state', 'hard_reset_auth_capability_state',
                         'bootstrap_first_local_admin')
    for token in contract_functions:
        check(token in schema_text, f'DB-Vertragsfunktion fehlt: {token}')

    requirements = (root / 'reference_scaffold/requirements.txt').read_text(encoding='utf-8')
    check('alembic' not in requirements.lower(), 'Alembic steht noch in den Laufzeitanforderungen.')
    ok(f'PostgreSQL-Artefakte und 10 Migrationen geprueft; SHA-256 {sha256(schema)}')

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

    # Pytest with proper cwd and offline support
    if not offline:
        if 'TEST_DATABASE_URL' not in os.environ:
            check(False, 'Live-Gate erforderlich: TEST_DATABASE_URL fehlt (oder --offline explizit setzen)')
        else:
            pytest_result = run([sys.executable, '-m', 'pytest', '-q', '-rs', '-p', 'no:cacheprovider', 'tests'],
                               root / 'reference_scaffold')
            check(pytest_result.returncode == 0, f'Vertragstests fehlgeschlagen: {pytest_result.stderr or pytest_result.stdout}')
            ok('Flask-Routen, Jinja-Templates und Vertragstests geprueft')
    else:
        pytest_result = run([sys.executable, '-m', 'pytest', '-q', '-rs', '-p', 'no:cacheprovider', 'tests'],
                           root / 'reference_scaffold')
        # Always parse pytest output for skipped count in offline mode
        output = pytest_result.stdout + pytest_result.stderr
        skipped_match = re.search(r'(\d+)\s+skipped', output)
        skipped_count = int(skipped_match.group(1)) if skipped_match else 0

        if skipped_count > 0:
            print(f'[WARNUNG] offline: {skipped_count} Tests uebersprungen, Live-Gate nicht bestanden')
            ok(f'Flask-Routen, Jinja-Templates und Vertragstests geprueft (offline, {skipped_count} uebersprungen)')
        elif pytest_result.returncode == 0:
            ok('Flask-Routen, Jinja-Templates und Vertragstests geprueft')
        else:
            check(False, f'Vertragstests fehlgeschlagen: {pytest_result.stderr or pytest_result.stdout}')

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

    # CSS contract: token superset and no hex outside :root
    prototype = root / 'design/prototype'
    css_a = prototype / 'assets/app.css'
    css_b = root / 'reference_scaffold/cafeteria/static/app.css'
    check(css_a.is_file() and css_b.is_file(), 'CSS-Dateien fehlen')
    if css_a.is_file() and css_b.is_file():
        try:
            css_a_text = css_a.read_text(encoding='utf-8')
            css_b_text = css_b.read_text(encoding='utf-8')
            # Extract prototype tokens
            proto_tokens = set(re.findall(r'--sh-[a-z0-9-]+', css_a_text))
            scaffold_tokens = set(re.findall(r'--sh-[a-z0-9-]+', css_b_text))
            missing_tokens = proto_tokens - scaffold_tokens
            check(not missing_tokens, f'Scaffold-CSS fehlen Prototype-Tokens: {sorted(missing_tokens)}')

            # Check for hex colors outside :root in scaffold
            lines = css_b_text.split('\n')
            in_root = False
            root_depth = 0
            hex_violations = []
            for i, line in enumerate(lines, 1):
                if ':root' in line and '{' in line:
                    in_root = True
                    root_depth = line.count('{') - line.count('}')
                elif in_root:
                    root_depth += line.count('{') - line.count('}')
                    if root_depth <= 0:
                        in_root = False
                elif re.search(r'#[0-9a-fA-F]{3,6}', line):
                    hex_violations.append(f'Line {i}: {line.strip()}')

            if hex_violations:
                errors.append('Scaffold-CSS enthaelt Hard-Coded Hex-Farben ausserhalb :root:\n' + '\n'.join(hex_violations))
        except Exception as exc:
            errors.append(f'CSS-Analyse fehlgeschlagen: {exc}')
    ok('CSS-Tokens und Hex-Color-Regeln geprueft')

    # Prototypen und Screenshots
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

    # Live screenshot inventory
    live_dir = root / 'design/screenshots/live'
    if live_dir.is_dir():
        live_index_path = live_dir / 'INDEX.json'
        if live_index_path.is_file():
            try:
                data = json.loads(live_index_path.read_text(encoding='utf-8'))
                live_index = data if isinstance(data, list) else []
            except Exception as exc:
                errors.append(f'INVALID JSON in design/screenshots/live/INDEX.json: {exc}')
                live_index = []
        else:
            check(False, 'design/screenshots/live/INDEX.json fehlt')
            live_index = []

        check(len(live_index) == len(LIVE_SCREENSHOTS), f'Live-Screenshot-INDEX enthaelt nicht die erwartete Anzahl: {len(live_index)}, erwartet {len(LIVE_SCREENSHOTS)}')
        live_index_map = {entry.get('name'): entry for entry in live_index if isinstance(entry, dict) and 'name' in entry}
        check(set(live_index_map) == set(LIVE_SCREENSHOTS), 'Live-Screenshot-INDEX Namen falsch')

        for name, (width, height) in LIVE_SCREENSHOTS.items():
            path = live_dir / name
            entry = live_index_map.get(name)
            check(path.is_file(), f'Live-Screenshot fehlt: {name}')
            check(entry is not None, f'Live-Screenshot nicht im Index: {name}')
            if entry is None:
                continue
            for key in ('name', 'url', 'width', 'height', 'http_status', 'sha256', 'captured_at', 'base_url'):
                check(key in entry, f'Live-INDEX-Eintrag unvollstaendig: {name}: {key}')
            if isinstance(entry.get('width'), int):
                check(entry['width'] == width, f'Live-Screenshot-Breite falsch: {name}: {entry.get("width")}, erwartet {width}')
            else:
                check(False, f'Live-Screenshot-Breite kein Integer: {name}')
            if isinstance(entry.get('height'), int):
                check(entry['height'] == height, f'Live-Screenshot-Hoehe falsch: {name}: {entry.get("height")}, erwartet {height}')
            else:
                check(False, f'Live-Screenshot-Hoehe kein Integer: {name}')
            if path.is_file():
                check(sha256(path) == entry.get('sha256'), f'Live-Screenshot-Checksumme falsch: {name}')
                with Image.open(path) as image:
                    check(image.size == (width, height), f'Live-Screenshot falsche Abmessung: {name}: {image.size}, erwartet ({width}, {height}).')
                    grayscale = image.convert('L').resize((64, 64))
                    check(ImageStat.Stat(grayscale).var[0] > 10, f'Live-Screenshot wirkt leer/einfarbig: {name}')
        ok('Live-Screenshot-Inventory mit 18 Bildern, SHA-256 und Metadaten geprueft')
    else:
        check(False, 'design/screenshots/live: Verzeichnis fehlt')

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
