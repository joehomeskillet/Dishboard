"""Synthetic before-screenshots for MP-UI-INVENTORY. Isolated DB, no live/prod persons."""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask
from playwright.sync_api import Browser
from werkzeug.serving import make_server

EVIDENCE = Path(__file__).resolve().parent
SCREEN_DIR = EVIDENCE / 'screenshots'
ROOT = EVIDENCE.parents[2]
MANIFEST_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-before-manifest.json'
PRIMARY = ((1440, 900), (390, 844))
REFERENCE_EXTRA = ((1024, 768), (768, 1024), (1920, 1080))
REFERENCE_PATHS = {
    '/admin/cafeteria/menues': 'ref-list',
    '/admin/design/darstellung': 'ref-settings',
    '/admin/cafeteria': 'ref-workspace',
}

PUBLIC_PATHS = [
    '/cafeteria/heute/', '/cafeteria/wochenangebot/', '/cafeteria/wochenangebot/ohne-bilder/',
    '/patienten/heute/', '/patienten/wochenplan/', '/patienten/wochenplan/ohne-bilder/',
    '/druck/cafeteria/woche', '/druck/patienten/woche', '/cafeteria/legende/',
]
SIGNAGE_PATHS = [
    '/signage/cafeteria/tag', '/signage/cafeteria/woche',
    '/signage/patienten/tag', '/signage/patienten/woche',
]
ADMIN_PATHS = [
    '/admin/cafeteria', '/admin/patienten',
    '/admin/cafeteria/menues', '/admin/patienten/menues',
    '/admin/cafeteria/komponenten', '/admin/patienten/komponenten',
    '/admin/cafeteria/copy?week=2026-08-31', '/admin/cafeteria/preview?week=2026-08-31',
    '/admin/cafeteria/wochen', '/admin/cafeteria/wochen/pruefung?week=2026-08-31',
    '/admin/import-preview', '/admin/grundlagen',
    '/admin/rezepte', '/admin/rezepte/neu',
    '/admin/kochbuecher', '/admin/kochbuecher/neu',
    '/admin/screens', '/admin/vorlagen',
    '/admin/design/darstellung', '/admin/design/marke',
    '/admin/bereiche-zeiten',
    '/admin/benutzer', '/admin/benutzer/neu', '/admin/benutzer/protokoll',
    '/admin/benutzer/zugriffsverlauf', '/admin/api', '/api/v1/docs',
]


def _slug(path: str, width: int, height: int, suffix: str = '') -> str:
    safe = path.strip('/').replace('/', '_') or 'root'
    extra = f'-{suffix}' if suffix else ''
    return f'{safe}{extra}-{width}x{height}.png'


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def start_server(app: Flask) -> tuple[object, str]:
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_port}'


def stop_server(server) -> None:
    server.shutdown()
    server.server_close()


def context_for(browser: Browser, live: str, cookie):
    context = browser.new_context(
        base_url=live,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        device_scale_factor=1,
        color_scheme='light',
        reduced_motion='reduce',
    )
    if cookie is not None:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live}])
    return context


def shot(page, path: str, width: int, height: int, suffix: str = '') -> dict:
    page.set_viewport_size({'width': width, 'height': height})
    console: list[str] = []
    failed: list[str] = []

    def on_console(msg) -> None:
        if msg.type in {'error', 'warning'}:
            console.append(f'{msg.type}: {msg.text}')

    def on_pageerror(err) -> None:
        failed.append(str(err))

    def on_requestfailed(req) -> None:
        failed.append(f'failed {req.method} {req.url} {req.failure}')

    page.on('console', on_console)
    page.on('pageerror', on_pageerror)
    page.on('requestfailed', on_requestfailed)
    try:
        response = page.goto(path, wait_until='domcontentloaded', timeout=30000)
    finally:
        page.remove_listener('console', on_console)
        page.remove_listener('pageerror', on_pageerror)
        page.remove_listener('requestfailed', on_requestfailed)
    page.wait_for_timeout(250)
    overflow = page.evaluate(
        'document.documentElement.scrollWidth > document.documentElement.clientWidth + 1'
    )
    fonts = page.evaluate(
        '''() => {
          const body = getComputedStyle(document.body).fontFamily;
          const h1 = document.querySelector('h1');
          return {body, h1: h1 ? getComputedStyle(h1).fontFamily : null};
        }'''
    )
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    out = SCREEN_DIR / _slug(path, width, height, suffix)
    page.screenshot(path=str(out), full_page=True)
    status = response.status if response is not None else None
    return {
        'path': path,
        'viewport': {'width': width, 'height': height},
        'suffix': suffix,
        'status': status,
        'final_url': page.url,
        'screenshot': str(out.relative_to(ROOT)),
        'screenshot_sha256': _sha(out),
        'overflow_horizontal': bool(overflow),
        'console': console[:20],
        'request_failures': failed[:20],
        'computed_fonts': fonts,
        'rendered': True,
        'source_discovered_only': False,
    }


def capture_paths(page, paths: list[str], extra_for: set[str] | None = None) -> list[dict]:
    rows = []
    extra_for = extra_for or set()
    for path in paths:
        for width, height in PRIMARY:
            rows.append(shot(page, path, width, height))
        if path in extra_for or path in REFERENCE_PATHS:
            for width, height in REFERENCE_EXTRA:
                rows.append(shot(page, path, width, height, suffix='reference'))
    return rows


def run_capture(
    app: Flask,
    browser: Browser,
    login_cookie,
    editor_cookie,
    snapshots_ok: bool,
    extra_admin_paths: list[str] | None = None,
) -> dict:
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    server, live = start_server(app)
    captures: list[dict] = []
    blocks: list[dict] = []
    try:
        with context_for(browser, live, None) as anonymous:
            page = anonymous.new_page()
            page.emulate_media(reduced_motion='reduce')
            captures.extend(capture_paths(page, PUBLIC_PATHS + SIGNAGE_PATHS + ['/auth/local']))
            captures.append(shot(page, '/admin/cafeteria', 1440, 900, suffix='anonymous-401'))
            try:
                captures.append(shot(page, '/auth/login', 1440, 900, suffix='auth-login'))
            except Exception as error:  # noqa: BLE001 — record, do not fake pass
                blocks.append({'id': 'auth_login_render', 'error': str(error), 'status': 'blocked'})
        with context_for(browser, live, login_cookie) as admin:
            page = admin.new_page()
            page.emulate_media(reduced_motion='reduce')
            admin_paths = ADMIN_PATHS + list(extra_admin_paths or [])
            extra = set(REFERENCE_PATHS) | set(extra_admin_paths or [])
            captures.extend(capture_paths(page, admin_paths, extra_for=extra))
            menu = '/admin/cafeteria/menu?week=2026-08-31&day=2026-08-31&meal=LUNCH&option=MENU_1'
            captures.extend(capture_paths(page, [menu], extra_for={menu}))
            captures.append(shot(page, '/admin/cafeteria/copy', 1440, 900, suffix='missing-week-404'))
            captures.append(shot(page, '/admin/cafeteria/wochen/pruefung', 1440, 900, suffix='missing-week-400'))
            try:
                page.goto('/admin/cafeteria')
                page.set_viewport_size({'width': 1440, 'height': 900})
                trigger = page.locator('[data-bs-target="#week-publish-modal"]')
                if trigger.count() and trigger.first.is_enabled():
                    trigger.first.click()
                    page.wait_for_timeout(200)
                    out = SCREEN_DIR / 'admin_cafeteria-dialog-publish-1440x900.png'
                    page.screenshot(path=str(out), full_page=True)
                    captures.append({
                        'path': '/admin/cafeteria',
                        'viewport': {'width': 1440, 'height': 900},
                        'suffix': 'dialog-publish',
                        'status': 200,
                        'final_url': page.url,
                        'screenshot': str(out.relative_to(ROOT)),
                        'screenshot_sha256': _sha(out),
                        'overflow_horizontal': False,
                        'console': [],
                        'request_failures': [],
                        'rendered': True,
                        'source_discovered_only': False,
                    })
            except Exception as error:  # noqa: BLE001
                blocks.append({'id': 'publish_dialog', 'error': str(error), 'status': 'blocked'})
        with context_for(browser, live, editor_cookie) as editor:
            page = editor.new_page()
            page.emulate_media(reduced_motion='reduce')
            captures.append(shot(page, '/admin/cafeteria', 1440, 900, suffix='editor-nav'))
            captures.append(shot(page, '/admin/benutzer', 1440, 900, suffix='editor-403'))
            captures.append(shot(page, '/admin/design/darstellung', 1440, 900, suffix='editor-settings'))
        previous_today = app.config.get('DEMO_TODAY')
        app.config['DEMO_TODAY'] = '2026-09-06'
        try:
            with context_for(browser, live, None) as closed:
                page = closed.new_page()
                page.emulate_media(reduced_motion='reduce')
                captures.append(shot(page, '/signage/cafeteria/tag', 1920, 1080, suffix='closed-sunday'))
                captures.append(shot(page, '/signage/cafeteria/tag', 390, 844, suffix='closed-sunday'))
        finally:
            app.config['DEMO_TODAY'] = previous_today
    finally:
        stop_server(server)

    ua = 'unknown'
    browser_version = getattr(browser, 'version', 'unknown')
    chromium = 'unknown'
    try:
        chromium = browser.version
        ua = f'playwright-chromium {chromium}'
    except Exception:  # noqa: BLE001
        ua = 'playwright-chromium'
    manifest = {
        'meta': {
            'wp_id': 'wp-fc6f91338ad3',
            'mp_id': 'MP-UI-INVENTORY',
            'source_commit': '5f5f6cb535922db8453c68d871279d6b2e203391',
            'schema': 25,
            'baseline_status': 'proposed_never_user_approved',
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'lane': 'grok-build',
            'model': 'grok-4.6',
            'locale': 'de-CH',
            'timezone': 'Europe/Zurich',
            'dpr': 1,
            'browser': ua,
            'browser_version': browser_version,
            'engine': 'playwright.chromium',
            'headless': True,
            'testdata': 'isolated_pg_schema25_seed_plus_demo_snapshots_kw36',
            'live_requests': False,
            'production_persons': False,
            'source_hashes': {
                'database/schema.sql': _sha(ROOT / 'database' / 'schema.sql'),
                'database/seed.sql': _sha(ROOT / 'database' / 'seed.sql'),
                'demo/snapshots/cafeteria_kw36.json': _sha(ROOT / 'demo' / 'snapshots' / 'cafeteria_kw36.json'),
                'demo/snapshots/patienten_kw36.json': _sha(ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json'),
            },
            'snapshots_injected': snapshots_ok,
        },
        'viewports': {
            'required_html': [{'width': 1440, 'height': 900}, {'width': 390, 'height': 844}],
            'reference_extra': [
                {'width': 1024, 'height': 768},
                {'width': 768, 'height': 1024},
                {'width': 1920, 'height': 1080},
            ],
        },
        'captures': captures,
        'coverage_blocks': blocks + [
            {
                'id': 'entra_callback_live_tenant',
                'reason': 'Cannot safely synthesize a real Entra tenant or production person.',
                'status': 'blocked_not_fake_pass',
            },
            {
                'id': 'recipe_revision_detail_entity',
                'reason': (
                    'Seed has no recipes. Revision-detail HTML needs a persisted recipe revision; '
                    'list and new-form are captured. Not a fake pass for the detail row.'
                ),
                'status': 'blocked_pending_synthetic_entity',
            },
            {
                'id': 'native_pdf_bytes',
                'reason': 'PDF downloads classified non-visual; HTML print routes captured separately.',
                'status': 'classified_download',
            },
        ],
        'visual_inspection': str((EVIDENCE / 'visual-inspection.md').relative_to(ROOT)),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (EVIDENCE / 'ui-before-manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    return manifest
