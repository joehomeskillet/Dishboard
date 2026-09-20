#!/usr/bin/env python3
"""Full-page UI/UX wave captures at acceptance viewports against the test database."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from flask import Flask
from playwright.sync_api import Browser, Page, sync_playwright
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))

from cafeteria import create_app  # noqa: E402
from cafeteria.auth.local_users import create_local_user, load_local_command_context  # noqa: E402
from cafeteria.db import init_database, upsert_entra_user  # noqa: E402

APP_PASSWORD = 'Test-App-Role-2026-7VgJ9wL4pQ2xR8mK'
BACKUP_PASSWORD = 'Test-Backup-Role-2026-5ZtN8cR3yH6qW1pL'
ISSUER_PASSWORD = 'Test-Issuer-Role-2026-9QmK4xV7pR2wL8sN'
LOCAL_USERNAME = 'capture.admin'
LOCAL_PASSWORD = 'MysteryKeeper2026!@Xyz'
LOCAL_ACTOR_ID = 'capture.admin@example.invalid'

VIEWPORTS: tuple[tuple[int, int], ...] = (
    (360, 800),
    (768, 1024),
    (1024, 768),
    (1440, 900),
)

_SLUG_RE = re.compile(r'[^a-z0-9]+')


@dataclass(frozen=True)
class WavePage:
    """One admin surface in the UI/UX wave inventory."""

    slug: str
    title: str
    endpoint: str
    values: Mapping[str, object] = field(default_factory=dict)


def wave_pages() -> tuple[WavePage, ...]:
    """All cafeteria admin surfaces required for before/after evidence."""
    return (
        WavePage('wochenplan-cafeteria', 'Wochenplan Cafeteria', 'admin.cafeteria'),
        WavePage('menues', 'Menüs', 'admin.menu_collection', {'family': 'cafeteria'}),
        WavePage('bausteine', 'Bausteine', 'admin.components_get', {'family': 'cafeteria'}),
        WavePage('zutaten-grundlagen', 'Zutaten / Grundlagen', 'admin.master_data_list'),
        WavePage('rezepte', 'Rezepte', 'admin.recipes_list'),
        WavePage('kochbuecher', 'Kochbücher', 'admin.cookbooks_list'),
        WavePage('gerichtvorlagen', 'Gerichtvorlagen', 'admin.dish_templates_list'),
        WavePage('einkaufslisten', 'Einkaufslisten', 'admin.shopping_lists_index'),
        WavePage('bestellung', 'Bestellung', 'admin.order_home'),
        WavePage('lager', 'Lager', 'admin.inventory_home'),
        WavePage('kalkulation', 'Kalkulation', 'admin.cost_home'),
        WavePage('bereiche-oeffnungszeiten', 'Bereiche & Öffnungszeiten', 'admin.operations_settings'),
        WavePage('erscheinungsbild', 'Erscheinungsbild', 'admin.branding_editor'),
        WavePage('darstellung', 'Darstellung', 'admin.display_settings'),
        WavePage('daten-importieren', 'Daten importieren', 'admin.import_preview'),
        WavePage('schnittstellen', 'Schnittstellen', 'admin.api_overview'),
        WavePage('benutzer-zugriff', 'Benutzer & Zugriff', 'admin.local_users_list'),
    )


def slugify(value: str) -> str:
    """Normalize a human label into a filesystem-safe slug."""
    normalized = (
        value.strip()
        .lower()
        .replace('ä', 'ae')
        .replace('ö', 'oe')
        .replace('ü', 'ue')
        .replace('ß', 'ss')
    )
    cleaned = _SLUG_RE.sub('-', normalized)
    return cleaned.strip('-') or 'page'


def filename_for(module_slug: str, width: int) -> str:
    """PNG filename for one module viewport."""
    return f'{module_slug}-{width}.png'


def resolve_routes(application: Flask) -> dict[str, str]:
    """Resolve registered admin routes via url_for."""
    routes: dict[str, str] = {}
    with application.test_request_context('/'):
        for page in wave_pages():
            routes[page.slug] = application.url_for(page.endpoint, **page.values)
    return routes


def manifest_row(
    *,
    path: str,
    route: str,
    viewport: Mapping[str, int],
    http_status: int | None,
    sha256: str | None,
    horizontal_overflow: bool | None,
    console_errors: Sequence[str],
    error: str | None = None,
) -> dict[str, Any]:
    """One manifest capture row."""
    row: dict[str, Any] = {
        'path': path,
        'route': route,
        'viewport': {'width': viewport['width'], 'height': viewport['height']},
        'http_status': http_status,
        'sha256': sha256,
        'horizontal_overflow': horizontal_overflow,
        'console_errors': list(console_errors),
    }
    if error is not None:
        row['error'] = error
    return row


def exit_code_from_rows(rows: Sequence[Mapping[str, Any]]) -> int:
    """Exit 1 when any capture row recorded an error or non-200 status."""
    for row in rows:
        if row.get('error'):
            return 1
        status = row.get('http_status')
        if status is None or status != 200:
            return 1
    return 0


def _role_database_url(database_url: str, role: str, password: str) -> str:
    return make_url(database_url).set(username=role, password=password).render_as_string(hide_password=False)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.getsockname()[1]


def _drop_schema(database_url: str) -> None:
    engine = create_engine(database_url, poolclass=NullPool, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
    finally:
        engine.dispose()


def _prepare_database(database_url: str) -> None:
    init_database(
        database_url,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        demo_seed_path=str(ROOT / 'database' / 'seed_demo.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
        seed_demo=True,
    )


def _configure_process_env(database_url: str, redis_url: str) -> None:
    app_url = _role_database_url(database_url, 'cafeteria_app', APP_PASSWORD)
    os.environ['DATABASE_URL'] = app_url
    os.environ['POSTGRES_AUTH_ISSUER_PASSWORD'] = ISSUER_PASSWORD
    os.environ['SESSION_REDIS_URL'] = redis_url
    os.environ['LOCAL_AUTH_ENABLED'] = 'true'
    os.environ['SESSION_COOKIE_SECURE'] = 'false'
    os.environ.setdefault('FLASK_SECRET_KEY', 'uiux-capture-secret')
    os.environ.setdefault('APP_ENV', 'test')
    os.environ.setdefault('DEMO_MODE', 'true')
    os.environ.setdefault('SEED_DEMO', 'true')
    os.environ.setdefault('DEMO_TODAY', '2026-09-01')


def _provision_admin_user(application: Flask) -> None:
    issuer_engine = application.extensions['cafeteria_auth_issuer_db']
    upsert_entra_user(
        issuer_engine,
        {
            'tid': '00000000-0000-0000-0000-000000000711',
            'oid': '00000000-0000-0000-0000-000000000722',
            'sub': 'capture-admin-actor',
            'name': 'Capture Admin',
            'preferred_username': LOCAL_ACTOR_ID,
        },
        ['Cafeteria.Admin'],
    )
    create_local_user(
        issuer_engine,
        actor=load_local_command_context(issuer_engine, actor_identifier=LOCAL_ACTOR_ID).actor,
        username=LOCAL_USERNAME,
        display_name='Capture Admin',
        password=LOCAL_PASSWORD,
        roles=('Cafeteria.Admin',),
    )


def _start_server(application: Flask) -> tuple[object, str]:
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_port}'


def _stop_server(server: object) -> None:
    server.shutdown()
    server.server_close()


def _perform_local_login(page: Page, base_url: str) -> None:
    response = page.goto(urljoin(base_url, '/auth/local'), wait_until='load')
    if response is None or response.status not in (200, 204):
        raise RuntimeError(f'login form unavailable ({response.status if response else None})')
    csrf_input = page.query_selector('input[name="csrf_token"]')
    if csrf_input is None:
        raise RuntimeError('csrf token missing on login form')
    csrf_token = csrf_input.get_attribute('value')
    if not csrf_token:
        raise RuntimeError('csrf token empty on login form')
    page.fill('input[name="username"]', LOCAL_USERNAME)
    page.fill('input[name="password"]', LOCAL_PASSWORD)
    with page.expect_navigation():
        page.click('button[type="submit"]')
    page.wait_for_load_state('load')
    if '/admin/' not in page.url:
        raise RuntimeError(f'login did not reach admin area ({page.url})')


def _await_ready(page: Page, timeout_ms: int = 15000) -> None:
    page.wait_for_load_state('load', timeout=timeout_ms)
    page.evaluate(
        '''async () => {
          const step = Math.max(window.innerHeight, 200);
          const total = document.documentElement.scrollHeight;
          for (let y = 0; y <= total; y += step) {
            window.scrollTo(0, y);
            await new Promise(resolve => requestAnimationFrame(resolve));
          }
          window.scrollTo(0, 0);
          await new Promise(resolve => requestAnimationFrame(resolve));
        }'''
    )
    page.wait_for_function('() => document.fonts && document.fonts.status === "loaded"', timeout=timeout_ms)
    page.wait_for_function(
        '''() => Array.from(document.images)
             .every(img => img.complete && (img.naturalWidth > 0 || !img.currentSrc))''',
        timeout=timeout_ms,
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_viewport(
    page: Page,
    base_url: str,
    route: str,
    output_path: Path,
    width: int,
    height: int,
) -> dict[str, Any]:
    console_errors: list[str] = []
    http_status: int | None = None

    def on_console(message) -> None:
        if message.type == 'error':
            console_errors.append(message.text)

    def on_pageerror(error) -> None:
        console_errors.append(str(error))

    page.on('console', on_console)
    page.on('pageerror', on_pageerror)
    try:
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(urljoin(base_url, route), wait_until='domcontentloaded', timeout=30000)
        http_status = response.status if response is not None else None
        _await_ready(page)
        if http_status != 200:
            raise RuntimeError(f'HTTP {http_status}')
        horizontal_overflow = page.evaluate(
            'document.documentElement.scrollWidth > document.documentElement.clientWidth + 1'
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output_path), full_page=True)
        return manifest_row(
            path=str(output_path),
            route=route,
            viewport={'width': width, 'height': height},
            http_status=http_status,
            sha256=_sha256_file(output_path),
            horizontal_overflow=bool(horizontal_overflow),
            console_errors=console_errors,
        )
    except Exception as error:
        return manifest_row(
            path=str(output_path),
            route=route,
            viewport={'width': width, 'height': height},
            http_status=http_status,
            sha256=None,
            horizontal_overflow=None,
            console_errors=console_errors,
            error=f'{type(error).__name__}: {error}',
        )
    finally:
        page.remove_listener('console', on_console)
        page.remove_listener('pageerror', on_pageerror)


def run_capture(
    application: Flask,
    browser: Browser,
    base_url: str,
    out_dir: Path,
    label: str,
) -> list[dict[str, Any]]:
    """Capture all wave pages for one label directory."""
    label_dir = out_dir / label
    label_dir.mkdir(parents=True, exist_ok=True)
    routes = resolve_routes(application)
    rows: list[dict[str, Any]] = []

    with browser.new_context(
        base_url=base_url,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        device_scale_factor=1,
        color_scheme='light',
        reduced_motion='reduce',
    ) as context:
        page = context.new_page()
        _perform_local_login(page, base_url)

        for wave_page in wave_pages():
            route = routes[wave_page.slug]
            page_failed = False
            for width, height in VIEWPORTS:
                if page_failed:
                    break
                png_path = label_dir / filename_for(wave_page.slug, width)
                row = _capture_viewport(page, base_url, route, png_path, width, height)
                rows.append(row)
                if row.get('error') or row.get('http_status') != 200:
                    page_failed = True
    return rows


def write_manifest(out_dir: Path, label: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    manifest_path = out_dir / label / 'manifest.json'
    payload = {
        'label': label,
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'viewports': [{'width': w, 'height': h} for w, h in VIEWPORTS],
        'pages': [
            {
                'slug': page.slug,
                'title': page.title,
                'endpoint': page.endpoint,
                'values': dict(page.values),
            }
            for page in wave_pages()
        ],
        'captures': [dict(row) for row in rows],
        'exit_code': exit_code_from_rows(rows),
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return manifest_path


def build_application(database_url: str, redis_url: str) -> Flask:
    _configure_process_env(database_url, redis_url)
    _drop_schema(database_url)
    _prepare_database(database_url)
    application = create_app()
    application.config.update(TESTING=False, DEMO_TODAY='2026-09-01')
    _provision_admin_user(application)
    return application


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Capture UI/UX wave before/after evidence.')
    parser.add_argument('--out', type=Path, required=True, help='Output directory root')
    parser.add_argument('--label', choices=('before', 'after'), required=True, help='Capture label')
    args = parser.parse_args(argv)

    database_url = os.getenv('TEST_DATABASE_URL')
    redis_url = os.getenv('TEST_REDIS_URL')
    if not database_url or not redis_url:
        print('TEST_DATABASE_URL and TEST_REDIS_URL are required.', file=sys.stderr)
        return 1
    # The capture drops and rebuilds the cafeteria schema: only a disposable local test database.
    target = make_url(database_url)
    if target.host not in ('127.0.0.1', 'localhost', '::1') or 'test' not in (target.database or ''):
        print('Refusing: TEST_DATABASE_URL must be a loopback database whose name contains "test".',
              file=sys.stderr)
        return 1

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    application = build_application(database_url, redis_url)
    server, base_url = _start_server(application)
    time.sleep(0.5)
    rows: list[dict[str, Any]] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage'],
            )
            try:
                rows = run_capture(application, browser, base_url, out_dir, args.label)
            finally:
                browser.close()
    finally:
        _stop_server(server)
        application.extensions['cafeteria_db'].dispose()
        issuer = application.extensions.get('cafeteria_auth_issuer_db')
        if issuer is not None:
            issuer.dispose()

    write_manifest(out_dir, args.label, rows)
    return exit_code_from_rows(rows)


if __name__ == '__main__':
    raise SystemExit(main())
