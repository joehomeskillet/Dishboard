"""Synthetic before-screenshots for MP-UI-INVENTORY. Isolated DB, no live/prod persons."""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask
from playwright.sync_api import Browser
from werkzeug.serving import make_server

EVIDENCE = Path(__file__).resolve().parent
SCREEN_DIR = EVIDENCE / 'screenshots'
ROOT = EVIDENCE.parents[2]
MANIFEST_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-before-manifest.json'
READY_TIMEOUT_MS = 15000
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


@dataclass(frozen=True)
class Outputs:
    """Where one capture run writes. Defaults keep the versioned proposed baseline."""

    screen_dir: Path = SCREEN_DIR
    manifest_paths: tuple[Path, ...] = (MANIFEST_PATH, EVIDENCE / 'ui-before-manifest.json')

    @classmethod
    def into(cls, directory: Path) -> 'Outputs':
        """Send a run to a throwaway directory; versioned baselines stay untouched."""
        directory = Path(directory)
        return cls(directory / 'screenshots', (directory / 'ui-before-manifest.json',))


def _slug(path: str, width: int, height: int, suffix: str = '') -> str:
    safe = path.strip('/').replace('/', '_') or 'root'
    extra = f'-{suffix}' if suffix else ''
    return f'{safe}{extra}-{width}x{height}.png'


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def await_ready(page, timeout_ms: int = READY_TIMEOUT_MS) -> dict:
    """Wait for real readiness instead of a fixed delay. Never silently give up."""
    readiness = {'load': False, 'lazy_sweep': False, 'fonts': False, 'images': False,
                 'timeout_ms': timeout_ms, 'pending_images': [], 'error': None}
    try:
        page.wait_for_load_state('load', timeout=timeout_ms)
        readiness['load'] = True
        # A full-page screenshot shows content below the fold, so lazy images must be
        # brought into view first; otherwise they stay blank in the baseline.
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
        readiness['lazy_sweep'] = True
        page.wait_for_function('() => document.fonts && document.fonts.status === "loaded"',
                               timeout=timeout_ms)
        readiness['fonts'] = True
        page.wait_for_function(
            '''() => Array.from(document.images)
                 .every(img => img.complete && (img.naturalWidth > 0 || !img.currentSrc))''',
            timeout=timeout_ms,
        )
        readiness['images'] = True
    except Exception as error:  # noqa: BLE001 — record the bounded failure, never fake ready
        readiness['error'] = f'{type(error).__name__}: {error}'
        try:
            readiness['pending_images'] = page.evaluate(
                '''() => Array.from(document.images)
                     .filter(img => !img.complete)
                     .map(img => img.currentSrc || img.src).slice(0, 10)'''
            )
        except Exception as probe_error:  # noqa: BLE001
            readiness['pending_images'] = [f'probe failed: {probe_error}']
    return readiness


def rendered_fonts(page) -> dict:
    """Declared family plus the actually rendered platform font where CDP exposes it."""
    declared = page.evaluate(
        '''() => {
          const body = getComputedStyle(document.body).fontFamily;
          const h1 = document.querySelector('h1');
          return {body, h1: h1 ? getComputedStyle(h1).fontFamily : null};
        }'''
    )
    result = {**declared, 'platform': None, 'platform_source': 'unavailable'}
    try:
        session = page.context.new_cdp_session(page)
    except Exception as error:  # noqa: BLE001 — non-Chromium or CDP disabled
        result['platform_source'] = f'unavailable: {type(error).__name__}'
        return result
    try:
        session.send('DOM.enable')
        session.send('CSS.enable')
        root = session.send('DOM.getDocument')['root']['nodeId']
        node = session.send('DOM.querySelector', {'nodeId': root, 'selector': 'h1'})['nodeId']
        if not node:
            node = session.send('DOM.querySelector', {'nodeId': root, 'selector': 'body'})['nodeId']
        fonts = session.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']
        result['platform'] = [
            {'family': entry.get('familyName'), 'glyphs': entry.get('glyphCount')}
            for entry in fonts
        ]
        result['platform_source'] = 'cdp:CSS.getPlatformFontsForNode'
    except Exception as error:  # noqa: BLE001
        result['platform_source'] = f'unavailable: {type(error).__name__}: {error}'
    finally:
        try:
            session.detach()
        except Exception:  # noqa: BLE001 — detach failure must not hide the capture
            pass
    return result


def shot(page, path: str, width: int, height: int, suffix: str = '',
         out: Outputs | None = None, after_load=None) -> dict:
    out = out or Outputs()
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
        readiness = await_ready(page)
        if after_load is not None:
            after_load(page)
        overflow = page.evaluate(
            'document.documentElement.scrollWidth > document.documentElement.clientWidth + 1'
        )
        fonts = rendered_fonts(page)
        out.screen_dir.mkdir(parents=True, exist_ok=True)
        target = out.screen_dir / _slug(path, width, height, suffix)
        page.screenshot(path=str(target), full_page=True)
    finally:
        # Listeners stay attached through readiness, measurement and screenshot,
        # so a failure after DOMContentLoaded is still recorded.
        page.remove_listener('console', on_console)
        page.remove_listener('pageerror', on_pageerror)
        page.remove_listener('requestfailed', on_requestfailed)
    status = response.status if response is not None else None
    return {
        'path': path,
        'viewport': {'width': width, 'height': height},
        'suffix': suffix,
        'status': status,
        'final_url': page.url,
        'screenshot': _relative(target),
        'screenshot_sha256': _sha(target),
        'overflow_horizontal': bool(overflow),
        'console': console[:20],
        'request_failures': failed[:20],
        'computed_fonts': fonts,
        'readiness': readiness,
        'rendered': readiness['error'] is None,
        'source_discovered_only': False,
    }


def capture_paths(page, paths: list[str], extra_for: set[str] | None = None,
                  out: Outputs | None = None) -> list[dict]:
    rows = []
    extra_for = extra_for or set()
    for path in paths:
        for width, height in PRIMARY:
            rows.append(shot(page, path, width, height, out=out))
        if path in extra_for or path in REFERENCE_PATHS:
            for width, height in REFERENCE_EXTRA:
                rows.append(shot(page, path, width, height, suffix='reference', out=out))
    return rows


def capture_publish_dialog(page, out: Outputs | None = None) -> tuple[list[dict], list[dict]]:
    """Record the publish modal with the ordinary recorder; never invent a success row."""

    def open_modal(current) -> None:
        trigger = current.locator('[data-bs-target="#week-publish-modal"]')
        if not trigger.count():
            raise LookupError('publish trigger absent')
        if not trigger.first.is_enabled():
            raise LookupError('publish trigger disabled')
        trigger.first.click()
        modal = current.locator('#week-publish-modal')
        modal.wait_for(state='visible', timeout=5000)
        current.wait_for_function(
            '''() => {
              const modal = document.querySelector('#week-publish-modal');
              return Boolean(modal) && modal.classList.contains('show');
            }''',
            timeout=5000,
        )

    try:
        row = shot(page, '/admin/cafeteria', 1440, 900, suffix='dialog-publish',
                   out=out, after_load=open_modal)
    except Exception as error:  # noqa: BLE001 — blocked record, never a fake pass
        return [], [{'id': 'publish_dialog', 'error': f'{type(error).__name__}: {error}',
                     'status': 'blocked_modal_not_open'}]
    return [row], []


def capture_provenance(identity: Mapping[str, str] | None = None) -> dict[str, object]:
    """Keep the recorded source author separate from caller-declared capture identity."""
    supplied = dict(identity or {})
    if set(supplied) - {'wp_id', 'lane', 'model'} or any(
        not isinstance(value, str) or not value.strip() for value in supplied.values()
    ):
        raise ValueError('Capture identity accepts nonempty wp_id, lane and model strings only.')
    return {
        'wp_id': supplied.get('wp_id'),
        'lane': supplied.get('lane'),
        'model': supplied.get('model'),
        'identity_status': 'caller_supplied' if supplied else 'not_supplied',
        'source_provenance': {
            'inventory_commit': 'f136490f7b2c19805c8f6436ebdbb657c3549dd7',
            'wp_id': 'wp-fc6f91338ad3',
            'lane': 'grok-build',
            'model': 'grok-4.6',
        },
    }


def run_capture(
    app: Flask,
    browser: Browser,
    login_cookie,
    editor_cookie,
    snapshots_ok: bool,
    extra_admin_paths: list[str] | None = None,
    out: Outputs | None = None,
    reference_paths: list[str] | None = None,
    *,
    capture_identity: Mapping[str, str] | None = None,
) -> dict:
    provenance = capture_provenance(capture_identity)
    out = out or Outputs()
    out.screen_dir.mkdir(parents=True, exist_ok=True)
    server, live = start_server(app)
    captures: list[dict] = []
    blocks: list[dict] = []
    try:
        with context_for(browser, live, None) as anonymous:
            page = anonymous.new_page()
            page.emulate_media(reduced_motion='reduce')
            captures.extend(capture_paths(
                page, PUBLIC_PATHS + SIGNAGE_PATHS + ['/auth/local'], out=out))
            captures.append(shot(page, '/admin/cafeteria', 1440, 900, suffix='anonymous-401', out=out))
            try:
                captures.append(shot(page, '/auth/login', 1440, 900, suffix='auth-login', out=out))
            except Exception as error:  # noqa: BLE001 — record, do not fake pass
                blocks.append({'id': 'auth_login_render', 'error': str(error), 'status': 'blocked'})
        with context_for(browser, live, login_cookie) as admin:
            page = admin.new_page()
            page.emulate_media(reduced_motion='reduce')
            admin_paths = ADMIN_PATHS + list(extra_admin_paths or [])
            extra = set(REFERENCE_PATHS) | set(reference_paths or [])
            captures.extend(capture_paths(page, admin_paths, extra_for=extra, out=out))
            menu = '/admin/cafeteria/menu?week=2026-08-31&day=2026-08-31&meal=LUNCH&option=MENU_1'
            captures.extend(capture_paths(page, [menu], extra_for={menu}, out=out))
            captures.append(shot(page, '/admin/cafeteria/copy', 1440, 900,
                                 suffix='missing-week-404', out=out))
            captures.append(shot(page, '/admin/cafeteria/wochen/pruefung', 1440, 900,
                                 suffix='missing-week-400', out=out))
            dialog_rows, dialog_blocks = capture_publish_dialog(page, out=out)
            captures.extend(dialog_rows)
            blocks.extend(dialog_blocks)
        with context_for(browser, live, editor_cookie) as editor:
            page = editor.new_page()
            page.emulate_media(reduced_motion='reduce')
            captures.append(shot(page, '/admin/cafeteria', 1440, 900, suffix='editor-nav', out=out))
            captures.append(shot(page, '/admin/benutzer', 1440, 900, suffix='editor-403', out=out))
            captures.append(shot(page, '/admin/design/darstellung', 1440, 900,
                                 suffix='editor-settings', out=out))
        previous_today = app.config.get('DEMO_TODAY')
        app.config['DEMO_TODAY'] = '2026-09-06'
        try:
            with context_for(browser, live, None) as closed:
                page = closed.new_page()
                page.emulate_media(reduced_motion='reduce')
                captures.append(shot(page, '/signage/cafeteria/tag', 1920, 1080,
                                     suffix='closed-sunday', out=out))
                captures.append(shot(page, '/signage/cafeteria/tag', 390, 844,
                                     suffix='closed-sunday', out=out))
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
            **provenance,
            'mp_id': 'MP-UI-INVENTORY',
            'source_commit': '5f5f6cb535922db8453c68d871279d6b2e203391',
            'schema': 25,
            'baseline_status': 'proposed_never_user_approved',
            'captured_at': datetime.now(timezone.utc).isoformat(),
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
                    'Seed has no recipes, so the caller creates a synthetic same-site recipe and '
                    'freezes one immutable v1 revision through the existing recipe store before '
                    'the run. The detail row is captured whenever that entity is supplied.'
                ),
                'status': 'resolved_by_synthetic_entity',
            },
            {
                'id': 'native_pdf_bytes',
                'reason': 'PDF downloads classified non-visual; HTML print routes captured separately.',
                'status': 'classified_download',
            },
        ],
        'visual_inspection': str((EVIDENCE / 'visual-inspection.md').relative_to(ROOT)),
    }
    rendered_manifest = json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'
    for target in out.manifest_paths:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered_manifest, encoding='utf-8')
    return manifest
