"""Synthetic before-screenshots for MP-UI-INVENTORY. Isolated DB, no live/prod persons."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import threading
from collections.abc import Callable, Mapping, Sequence
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
REQUIRED = ((1440, 900), (1024, 768), (768, 1024), (390, 844))
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

    @classmethod
    def promoting(cls, directory: Path) -> 'Outputs':
        """Send a run to a directory while updating versioned MANIFEST_PATH too."""
        directory = Path(directory)
        return cls(directory / 'screenshots', (MANIFEST_PATH, directory / 'ui-before-manifest.json'))


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


def capture_viewports(default=PRIMARY) -> tuple[tuple[int, int], ...]:
    """Opt into all required sizes, retaining any existing special viewport."""
    if os.environ.get('UI_CAPTURE_VIEWPORTS') == 'required':
        return tuple(dict.fromkeys((*REQUIRED, *default)))
    return default


def context_for(browser: Browser, live: str, cookie):
    touch = True if os.environ.get('UI_CAPTURE_POINTER') == 'coarse' else None
    context = browser.new_context(
        base_url=live,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        device_scale_factor=1,
        color_scheme='light',
        reduced_motion='reduce',
        has_touch=touch,
        is_mobile=touch,
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


def interactive_target_metrics(page) -> dict:
    """Measure full-page DOM target boxes; findings need route/state classification."""
    return page.evaluate(r'''() => {
      const pointer_coarse = matchMedia('(pointer: coarse)').matches;
      const minimum_target_size = pointer_coarse ? 44 : 36;
      const text = el => {
        if (el.nodeType === Node.TEXT_NODE) return el.textContent;
        if (el.nodeType !== Node.ELEMENT_NODE || el.getAttribute('aria-hidden') === 'true'
            || ['SCRIPT', 'STYLE'].includes(el.tagName)) return '';
        const css = getComputedStyle(el);
        if (css.display === 'none' || ['hidden', 'collapse'].includes(css.visibility)) return '';
        return el.tagName === 'IMG' ? (el.getAttribute('alt') || '')
          : [...el.childNodes].map(text).join(' ');
      };
      const name = el => {
        const labelled = (el.getAttribute('aria-labelledby') || '').trim().split(/\s+/)
          .map(id => document.getElementById(id)?.textContent || '').join(' ').trim();
        const labels = [...(el.labels || [])].map(text).join(' ').trim();
        const content = el.matches('input')
          ? (['submit', 'reset', 'button'].includes(el.type) ? el.value : el.getAttribute('alt') || '')
          : (el.matches('select') ? '' : text(el).trim());
        return (labelled || (el.getAttribute('aria-label') || '').trim() || labels || content
          || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 80);
      };
      const visibleRect = el => {
        if (!el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return null;
        let {left, top, right, bottom} = el.getBoundingClientRect();
        for (let node = el; node && node !== document.body; node = node.parentElement) {
          const css = getComputedStyle(node), box = node.getBoundingClientRect();
          if (css.clipPath === 'inset(50%)') return null;
          const clip = (css.clip.match(/-?[\d.]+px/g) || []).map(parseFloat);
          if (clip.length === 4) {
            top = Math.max(top, box.top + clip[0]);
            right = Math.min(right, box.left + clip[1]);
            bottom = Math.min(bottom, box.top + clip[2]);
            left = Math.max(left, box.left + clip[3]);
          }
          if (node !== el) {
            if (/^(auto|scroll|hidden|clip)$/.test(css.overflowX)) {
              left = Math.max(left, box.left + node.clientLeft);
              right = Math.min(right, box.left + node.clientLeft + node.clientWidth);
            }
            if (/^(auto|scroll|hidden|clip)$/.test(css.overflowY)) {
              top = Math.max(top, box.top + node.clientTop);
              bottom = Math.min(bottom, box.top + node.clientTop + node.clientHeight);
            }
          }
          if (css.position === 'fixed') {
            left = Math.max(left, 0); top = Math.max(top, 0);
            right = Math.min(right, innerWidth); bottom = Math.min(bottom, innerHeight);
          }
        }
        return right > left && bottom > top
          ? new DOMRect(left, top, right - left, bottom - top) : null;
      };
      const targets = [...document.querySelectorAll(
        'a, button, input:not([type=hidden]), select, summary, [role=button]')]
        .map((el, index) => ({el, index, rect: visibleRect(el)})).filter(({rect}) => rect);
      const record = ({el, index, rect}) => ({
        index, id: el.id, tag: el.tagName.toLowerCase(), name: name(el),
        width: rect.width, height: rect.height, x: rect.x, y: rect.y
      });
      const records = targets.map(record);
      const overlapping_targets = [];
      for (let i = 0; i < targets.length; i++) {
        for (let j = i + 1; j < targets.length; j++) {
          const a = targets[i], b = targets[j];
          if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
          const width = Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left);
          const height = Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top);
          if (width > 0 && height > 0 && width * height > 1) {
            overlapping_targets.push({first: records[i], second: records[j], intersection_area: width * height});
          }
        }
      }
      return {
        pointer_coarse, max_touch_points: navigator.maxTouchPoints, minimum_target_size,
        target_too_small: records.filter(r => r.width < minimum_target_size || r.height < minimum_target_size),
        overlapping_targets
      };
    }''')


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
    touch_session = None
    try:
        if os.environ.get('UI_CAPTURE_POINTER') == 'coarse':
            # Chromium can clear touch after full-page screenshots or CDP detach.
            # Reapply real input emulation, keeping this session through the shot.
            touch_session = page.context.new_cdp_session(page)
            touch_session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        response = page.goto(path, wait_until='domcontentloaded', timeout=30000)
        readiness = await_ready(page)
        if after_load is not None:
            after_load(page)
        fonts = rendered_fonts(page)
        if touch_session is not None:
            touch_session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
            page.evaluate('() => new Promise(requestAnimationFrame)')
        metrics = page.evaluate(r'''() => {
          const root = document.documentElement;
          const visible = el => [...el.getClientRects()].some(r => r.width && r.height)
            && !['hidden', 'collapse'].includes(getComputedStyle(el).visibility);
          const text = el => {
            if (el.nodeType === Node.TEXT_NODE) return el.textContent;
            if (el.nodeType !== Node.ELEMENT_NODE || el.getAttribute('aria-hidden') === 'true'
                || ['SCRIPT', 'STYLE'].includes(el.tagName)) return '';
            const css = getComputedStyle(el);
            if (css.display === 'none' || ['hidden', 'collapse'].includes(css.visibility)) return '';
            return [...el.childNodes].map(text).join(' ');
          };
          const named = el => {
            const labelled = (el.getAttribute('aria-labelledby') || '').trim().split(/\s+/)
              .map(id => document.getElementById(id)?.textContent || '').join(' ').trim();
            return labelled || (el.getAttribute('aria-label') || '').trim() || text(el).trim();
          };
          return {
            innerWidth: window.innerWidth, scrollWidth: root.scrollWidth,
            clientWidth: root.clientWidth, h1_count: document.querySelectorAll('h1').length,
            unnamed_controls: [...document.querySelectorAll('.ui-sem-control, button, a.btn')]
              .map((el, index) => ({el, index})).filter(({el}) => visible(el) && !named(el))
              .map(({el, index}) => ({index, tag: el.tagName.toLowerCase()}))
          };
        }''')
        metrics.update(interactive_target_metrics(page))
        out.screen_dir.mkdir(parents=True, exist_ok=True)
        target = out.screen_dir / _slug(path, width, height, suffix)
        # ponytail: coarse screenshots stay viewport-only until Chromium's
        # captureBeyondViewport preserves touch; DOM metrics cover the full page.
        screenshot_full_page = touch_session is None
        page.screenshot(path=str(target), full_page=screenshot_full_page)
    finally:
        # Listeners stay attached through readiness, measurement and screenshot,
        # so a failure after DOMContentLoaded is still recorded.
        page.remove_listener('console', on_console)
        page.remove_listener('pageerror', on_pageerror)
        page.remove_listener('requestfailed', on_requestfailed)
        if touch_session is not None:
            touch_session.detach()
    status = response.status if response is not None else None
    return {
        'path': path,
        'viewport': {'width': width, 'height': height},
        'suffix': suffix,
        'status': status,
        'final_url': page.url,
        'screenshot': _relative(target),
        'screenshot_sha256': _sha(target),
        'screenshot_full_page': screenshot_full_page,
        **metrics,
        'overflow_horizontal': metrics['scrollWidth'] > metrics['clientWidth'] + 1,
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
        for width, height in capture_viewports():
            rows.append(shot(page, path, width, height, out=out))
        if path in extra_for or path in REFERENCE_PATHS:
            for width, height in REFERENCE_EXTRA:
                if (width, height) in capture_viewports():
                    continue
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

    rows, blocks = [], []
    for width, height in capture_viewports(((1440, 900),)):
        try:
            rows.append(shot(page, '/admin/cafeteria', width, height, suffix='dialog-publish',
                             out=out, after_load=open_modal))
        except Exception as error:  # noqa: BLE001 — blocked record, never a fake pass
            blocks.append({'id': 'publish_dialog', 'error': f'{type(error).__name__}: {error}',
                           'path': '/admin/cafeteria', 'viewport': {'width': width, 'height': height},
                           'status': 'blocked_modal_not_open'})
    return rows, blocks


def _json_copy(value: object, *, error: str, **dumps_kwargs) -> tuple[str, object]:
    try:
        raw = json.dumps(value, **dumps_kwargs)
        return raw, json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(error) from exc


def fixture_record(descriptor: Mapping[str, object] | None) -> dict[str, object]:
    """Record fixture metadata and canonical hash."""
    if descriptor is None:
        return {'status': 'not_supplied', 'sha256': None, 'descriptor': None}
    raw_json, deep_copy = _json_copy(
        descriptor, error='Fixture descriptor must be JSON-serializable',
        sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return {
        'status': 'caller_supplied',
        'sha256': hashlib.sha256(raw_json.encode('utf-8')).hexdigest(),
        'descriptor': deep_copy,
    }


def font_file_hashes() -> dict[str, str]:
    """Map ROOT-relative font file paths to their SHA256 hashes."""
    fonts_dir = ROOT / 'reference_scaffold' / 'cafeteria' / 'static' / 'fonts'
    suffixes = {'.woff2', '.woff', '.ttf', '.otf'}
    result: dict[str, str] = {}
    if fonts_dir.is_dir():
        for path in fonts_dir.rglob('*'):
            if path.is_file() and path.suffix.lower() in suffixes:
                rel = path.relative_to(ROOT).as_posix()
                result[rel] = _sha(path)
    return dict(sorted(result.items()))


def runtime_record() -> dict[str, str]:
    """Capture environment version details."""
    try:
        pw_version = importlib.metadata.version('playwright')
    except importlib.metadata.PackageNotFoundError:
        pw_version = 'unknown'
    return {
        'platform': platform.platform(),
        'python': platform.python_version(),
        'playwright': pw_version,
    }


ROLE_NAV_PATH = '/admin/cafeteria'


def role_suffix(role: str) -> str:
    """Derive role-nav screenshot suffix from role name."""
    prefix = 'Cafeteria.'
    name = role[len(prefix):] if role.startswith(prefix) else role
    cleaned = re.sub(r'[^a-z0-9]', '-', name.lower())
    return f'role-nav-{cleaned}'


def capture_role_navigation(browser: Browser, live: str, role_cookies: Mapping[str, object],
                            out: Outputs | None = None) -> list[dict]:
    """Capture navigation sidebar per role context across primary viewports."""
    rows: list[dict] = []
    sidebar_selector = 'aside.admin-sidebar nav.admin-nav a'
    for role, cookie in role_cookies.items():
        with context_for(browser, live, cookie) as ctx:
            page = ctx.new_page()
            page.emulate_media(reduced_motion='reduce')
            for width, height in capture_viewports():
                row = shot(page, ROLE_NAV_PATH, width, height, suffix=role_suffix(role), out=out)
                row['role'] = role
                probe = page.evaluate(f'''() => {{ const selector = {json.dumps(sidebar_selector)};
                  const links = Array.from(document.querySelectorAll(selector));
                  if (links.length === 0) return {{nav_items: [], nav_probe_error: `no sidebar links matched ${{selector}}`}};
                  return {{nav_items: links.map(el => ((el.querySelector('.nav-link-title') || el).textContent || '').replace(/\\s+/g, ' ').trim())}}; }}''')
                row['nav_items'] = probe['nav_items']
                if 'nav_probe_error' in probe:
                    row['nav_probe_error'] = probe['nav_probe_error']
                rows.append(row)
    return rows


def capture_states(page, state_captures: Sequence[tuple[str, str, Callable]],
                   out: Outputs | None = None) -> tuple[list[dict], list[dict]]:
    """Capture UI states with specific actions per path/suffix/action tuple."""
    rows: list[dict] = []
    blocks: list[dict] = []
    for path, suffix, action in state_captures:
        for width, height in capture_viewports():
            try:
                rows.append(shot(page, path, width, height, suffix=suffix, out=out, after_load=action))
            except Exception as error:  # noqa: BLE001 — state capture failure produces block record
                blocks.append({
                    'id': f'state_{suffix}', 'path': path, 'viewport': {'width': width, 'height': height},
                    'status': 'blocked_state_not_reached', 'error': f'{type(error).__name__}: {error}',
                })
    return rows, blocks


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


def _prepared_additions(result: object) -> tuple[list[str], list[str], list[tuple[str, str, Callable]]]:
    if result is None:
        return [], [], []
    if not isinstance(result, Mapping):
        raise TypeError(f'prepare_entities must return a mapping or None, not {type(result).__name__}')
    allowed = ('extra_admin_paths', 'reference_paths', 'state_captures')
    unknown = [key for key in result if key not in allowed]
    if unknown:
        raise TypeError(f'prepare_entities returned unknown key(s): {unknown}')
    parsed: list = []
    for key in allowed:
        value = result[key] if key in result else []
        if not isinstance(value, (list, tuple)):
            raise TypeError(f'prepare_entities[{key!r}] must be a list or tuple, not {type(value).__name__}')
        parsed.append(list(value))
    return parsed[0], parsed[1], parsed[2]


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
    role_cookies: Mapping[str, object] | None = None,
    fixture_descriptor: Mapping[str, object] | None = None,
    supersedes: Mapping[str, object] | None = None,
    empty_paths: list[str] | None = None,
    prepare_entities: Callable[[], Mapping[str, object] | None] | None = None,
    state_captures: Sequence[tuple[str, str, Callable]] | None = None,
) -> dict:
    provenance = capture_provenance(capture_identity)
    fixture_rec = fixture_record(fixture_descriptor)
    superseded = None if supersedes is None else _json_copy(
        supersedes, error='Supersedes must be JSON-serializable')[1]
    demo_today = app.config.get('DEMO_TODAY')

    out = out or Outputs()
    out.screen_dir.mkdir(parents=True, exist_ok=True)
    server, live = start_server(app)
    captures: list[dict] = []
    blocks: list[dict] = []
    try:
        with context_for(browser, live, None) as anonymous:
            page = anonymous.new_page()
            page.emulate_media(reduced_motion='reduce')
            captures.extend(capture_paths(page, PUBLIC_PATHS + SIGNAGE_PATHS + ['/auth/local'], out=out))
            for width, height in capture_viewports(((1440, 900),)):
                captures.append(shot(page, '/admin/cafeteria', width, height, suffix='anonymous-401', out=out))
            for width, height in capture_viewports():
                try:
                    captures.append(shot(page, '/auth/login', width, height, suffix='auth-login', out=out))
                except Exception as error:  # noqa: BLE001 — record, do not fake pass
                    blocks.append({'id': f'auth_login_render_{width}x{height}', 'error': str(error), 'status': 'blocked'})
        with context_for(browser, live, login_cookie) as admin:
            page = admin.new_page()
            page.emulate_media(reduced_motion='reduce')

            if empty_paths:
                for path in empty_paths:
                    for width, height in capture_viewports():
                        captures.append(shot(page, path, width, height, suffix='empty', out=out))

            added_admin, added_refs, added_states = _prepared_additions(
                prepare_entities() if prepare_entities is not None else None)
            active_extra_admin = list(extra_admin_paths or []) + added_admin
            active_ref_paths = list(reference_paths or []) + added_refs
            active_state_captures = list(state_captures or []) + added_states

            admin_paths = ADMIN_PATHS + active_extra_admin
            extra = set(REFERENCE_PATHS) | set(active_ref_paths)
            captures.extend(capture_paths(page, admin_paths, extra_for=extra, out=out))
            menu = '/admin/cafeteria/menu?week=2026-08-31&day=2026-08-31&meal=LUNCH&option=MENU_1'
            captures.extend(capture_paths(page, [menu], extra_for={menu}, out=out))
            for width, height in capture_viewports(((1440, 900),)):
                captures.append(shot(page, '/admin/cafeteria/copy', width, height, suffix='missing-week-404', out=out))
                captures.append(shot(page, '/admin/cafeteria/wochen/pruefung', width, height, suffix='missing-week-400', out=out))
            dialog_rows, dialog_blocks = capture_publish_dialog(page, out=out)
            captures.extend(dialog_rows)
            blocks.extend(dialog_blocks)

            if active_state_captures:
                st_rows, st_blocks = capture_states(page, active_state_captures, out=out)
                captures.extend(st_rows)
                blocks.extend(st_blocks)
        with context_for(browser, live, editor_cookie) as editor:
            page = editor.new_page()
            page.emulate_media(reduced_motion='reduce')
            for width, height in capture_viewports(((1440, 900),)):
                captures.append(shot(page, '/admin/cafeteria', width, height, suffix='editor-nav', out=out))
                captures.append(shot(page, '/admin/benutzer', width, height, suffix='editor-403', out=out))
                captures.append(shot(page, '/admin/design/darstellung', width, height, suffix='editor-settings', out=out))
        if role_cookies:
            role_rows = capture_role_navigation(browser, live, role_cookies, out=out)
            captures.extend(role_rows)
        previous_today = app.config.get('DEMO_TODAY')
        app.config['DEMO_TODAY'] = '2026-09-06'
        try:
            with context_for(browser, live, None) as closed:
                page = closed.new_page()
                page.emulate_media(reduced_motion='reduce')
                for width, height in capture_viewports(((1920, 1080), (390, 844))):
                    captures.append(shot(page, '/signage/cafeteria/tag', width, height, suffix='closed-sunday', out=out))
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
    manifest: dict[str, object] = {
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
            'fixture': fixture_rec,
            'font_files': font_file_hashes(),
            'demo_today': demo_today,
            'runtime': runtime_record(),
        },
        'viewports': {
            'required_html': [{'width': width, 'height': height} for width, height in capture_viewports()],
            'reference_extra': [{'width': 1024, 'height': 768}, {'width': 768, 'height': 1024},
                                {'width': 1920, 'height': 1080}],
        },
        'captures': captures,
        'coverage_blocks': blocks + [
            {'id': 'entra_callback_live_tenant',
             'reason': 'Cannot safely synthesize a real Entra tenant or production person.',
             'status': 'blocked_not_fake_pass'},
            {'id': 'recipe_revision_detail_entity',
             'reason': ('Seed has no recipes, so the caller creates a synthetic same-site recipe and '
                        'freezes one immutable v1 revision through the existing recipe store before '
                        'the run. The detail row is captured whenever that entity is supplied.'),
             'status': 'resolved_by_synthetic_entity'},
            {'id': 'native_pdf_bytes',
             'reason': 'PDF downloads classified non-visual; HTML print routes captured separately.',
             'status': 'classified_download'},
        ],
        'visual_inspection': str((EVIDENCE / 'visual-inspection.md').relative_to(ROOT)),
    }
    if superseded is not None:
        manifest['superseded_evidence'] = superseded

    rendered_manifest = json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'
    for target in out.manifest_paths:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered_manifest, encoding='utf-8')
    return manifest
