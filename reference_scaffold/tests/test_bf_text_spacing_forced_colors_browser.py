"""BF-E3 T27/T28: text spacing, 320 CSS px, 400 percent, forced colors, reduced motion."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import pytest

from test_admin_workflow_routes import DATABASE_URL, DAY, _login, database_engine  # noqa: F401
from test_recipe_routes import create
from test_rendered_ui import browser  # noqa: F401
from test_ui_master_shell_browser import _cookie, _goto, _page, site  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

EVIDENCE = Path(
    '/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18'
    '/.claude/state/claude-session-2026-09-29/audit/BF/E3'
)
# WCAG 1.4.12 author stylesheet. The page must keep content and function with it applied.
SPACING_CSS = (
    '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}'
    'p{margin-bottom:2em!important}'
)
PROBE = """() => {
  const probe = document.createElement('p');
  probe.textContent = 'Abstand';
  probe.style.fontSize = '100px';
  document.body.append(probe);
  const style = getComputedStyle(probe);
  const reading = {
    line: parseFloat(style.lineHeight),
    letter: parseFloat(style.letterSpacing),
    word: parseFloat(style.wordSpacing),
    margin: parseFloat(style.marginBottom),
  };
  probe.remove();
  return reading;
}"""
REFLOW = """() => {
  const root = document.documentElement;
  const clipped = [];
  const offscreen = [];
  const selector = 'main h1, main h2, main label, main button, main a, main summary,'
    + ' main input, main select, main textarea, main .admin-statusbar-item';
  for (const el of document.querySelectorAll(selector)) {
    if (el.closest('[hidden], .visually-hidden')) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    const style = getComputedStyle(el);
    const clips = style.overflowX === 'hidden' || style.overflowX === 'clip';
    if (clips && el.clientWidth > 2 && el.scrollWidth > el.clientWidth + 2)
      clipped.push((el.id || el.getAttribute('aria-label') || el.tagName).slice(0, 60));
    if (rect.left < -1 || rect.right > root.clientWidth + 1)
      offscreen.push((el.id || el.getAttribute('aria-label') || el.innerText || el.tagName)
        .trim().slice(0, 60));
  }
  const unnamed = [...document.querySelectorAll('main .ui-sem-control--icon-only')].filter(el => {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && !(el.getAttribute('aria-label') || '').trim();
  }).length;
  return {
    docOverflow: root.scrollWidth > root.clientWidth + 1,
    clipped: clipped.slice(0, 8),
    offscreen: offscreen.slice(0, 8),
    unnamed,
    width: innerWidth,
  };
}"""


def _install_spacing(page) -> None:
    """Link a same-origin sheet. CSP style-src 'self' blocks an inline style element."""
    link = '<link id="bf-e3-text-spacing" rel="stylesheet" href="/bf-e3-text-spacing.css">'

    def _insert(route):
        if urlsplit(route.request.url).path == '/bf-e3-text-spacing.css':
            route.fulfill(status=200, content_type='text/css', body=SPACING_CSS)
            return
        if route.request.resource_type != 'document':
            route.continue_()
            return
        response = route.fetch()
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type:
            route.fulfill(response=response)
            return
        body = response.text()
        if '<head>' in body and 'bf-e3-text-spacing' not in body:
            body = body.replace('<head>', '<head>' + link, 1)
        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in {'content-length', 'content-encoding'}
        }
        route.fulfill(status=response.status, headers=headers, body=body)

    page.context.route('**/*', _insert)


def _record(name: str, failures: list) -> None:
    if not failures:
        return
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / name).write_text(repr(failures), encoding='utf-8')


def _shot(page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / f'{name}.png'))


def _paths(client) -> tuple[tuple[str, str], ...]:
    recipe = urlsplit(create(client, title='BF-E3 Abstand')).path
    menu = f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
    return (
        ('rezepte', '/admin/rezepte'),
        ('rezepteditor', recipe),
        ('cafeteria', '/admin/cafeteria'),
        ('menueditor', menu),
        ('zutat', '/admin/grundlagen/zutaten/neu'),
        ('einkauf', '/admin/einkaufslisten'),
        ('benutzer', '/admin/benutzer'),
    )


def _spacing_ok(reading: dict) -> bool:
    return (
        abs(reading['line'] - 150) <= 1
        and abs(reading['letter'] - 12) <= 1
        and abs(reading['word'] - 16) <= 1
        and abs(reading['margin'] - 200) <= 1
    )


def _reflow_ok(reading: dict) -> bool:
    return not reading['docOverflow'] and not reading['clipped'] and not reading['offscreen'] and reading['unnamed'] == 0


def _check_spacing_reflow(page, label: str, failures: list) -> None:
    present = page.evaluate("() => !!document.getElementById('bf-e3-text-spacing')")
    reading = page.evaluate(PROBE)
    if not present or not _spacing_ok(reading):
        _shot(page, f't27-spacing-{label}')
        failures.append((label, 'spacing', present, reading))
    reflow = page.evaluate(REFLOW)
    if not _reflow_ok(reflow):
        _shot(page, f't27-reflow-{label}')
        failures.append((label, 'reflow', reflow))


def test_t27_text_spacing_and_320_reflow(site) -> None:  # noqa: F811
    """Injected 1.4.12 spacing at 320 CSS px keeps text and controls on one axis."""
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    paths = _paths(client)
    failures: list = []
    for javascript in (True, False):
        page = _page(site, client, viewport={'width': 320, 'height': 844}, java_script_enabled=javascript)
        _install_spacing(page)
        try:
            for label, path in paths:
                _goto(page, path)
                width = page.evaluate('innerWidth')
                if width != 320:
                    failures.append((label, javascript, 'viewport', width))
                _check_spacing_reflow(page, f'{label}-320-js{int(javascript)}', failures)
        finally:
            page.context.close()
    _record('t27-320.txt', failures)
    assert not failures, failures


def test_t27_text_spacing_at_400_percent(site) -> None:  # noqa: F811
    """Native 400 percent zoom is the 320 CSS px reflow, with the same spacing sheet."""
    app, origin, engine, chromium = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    chosen = [item for item in _paths(client) if item[0] in {'rezepte', 'rezepteditor', 'cafeteria'}]
    failures: list = []
    with TemporaryDirectory(prefix='bf-e3-zoom-') as profile:
        context = chromium.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True, base_url=origin,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1280,2400'],
        )
        try:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(4, resolve))')
            zoom = page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))')
            context.add_cookies([_cookie(app, client, origin)])
            _install_spacing(page)
            # Chromium reports the 400 percent setting as a binary float just under 4.
            if abs(float(zoom) - 4) > 0.01:
                failures.append(('zoom', zoom))
            else:
                for label, path in chosen:
                    response = page.goto(path, wait_until='networkidle')
                    assert response is not None and response.status == 200
                    page.evaluate('document.fonts.ready')
                    metrics = page.evaluate('() => ({dpr: devicePixelRatio, width: innerWidth})')
                    if not (abs(metrics['dpr'] - 4) < 0.05 and 300 <= metrics['width'] <= 321):
                        _shot(page, f't27-400-zoom-{label}')
                        failures.append((label, 'zoom', metrics))
                    _check_spacing_reflow(page, f'{label}-400', failures)
        finally:
            context.close()
    _record('t27-400.txt', failures)
    assert not failures, failures


def _force_media(page) -> dict:
    try:
        page.emulate_media(forced_colors='active', reduced_motion='reduce')
    except TypeError:
        pass
    state = page.evaluate("""() => ({
      forced: matchMedia('(forced-colors: active)').matches,
      motion: matchMedia('(prefers-reduced-motion: reduce)').matches,
    })""")
    if state['forced'] and state['motion']:
        return state
    page.context.new_cdp_session(page).send('Emulation.setEmulatedMedia', {'features': [
        {'name': 'forced-colors', 'value': 'active'},
        {'name': 'prefers-reduced-motion', 'value': 'reduce'},
    ]})
    return page.evaluate("""() => ({
      forced: matchMedia('(forced-colors: active)').matches,
      motion: matchMedia('(prefers-reduced-motion: reduce)').matches,
    })""")


CUES = """() => {
  const active = document.activeElement;
  const focusStyle = active ? getComputedStyle(active) : null;
  const icons = [...document.querySelectorAll('main .ui-sem-control--icon-only')].filter(el => {
    if (el.closest('[hidden]')) return false;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden') return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return false;
    return !(el.getAttribute('aria-label') || '').trim();
  }).map(el => (el.getAttribute('data-semantic') || el.tagName).slice(0, 40));
  const chips = [...document.querySelectorAll('.admin-statusbar-item, .badge')].filter(el => {
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return false;
    const style = getComputedStyle(el);
    return !el.innerText.trim() || style.color === style.backgroundColor || style.display === 'none';
  }).map(el => (el.innerText || el.className).trim().slice(0, 40));
  const chipCount = [...document.querySelectorAll('.admin-statusbar-item, .badge')].filter(el => {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && el.innerText.trim();
  }).length;
  const disabled = [...document.querySelectorAll(
    'main button.btn:disabled, main button.btn[aria-disabled="true"], main a.btn[aria-disabled="true"]'
  )]
    .filter(el => el.getBoundingClientRect().width > 0)
    .slice(0, 4)
    .map(el => {
      const style = getComputedStyle(el);
      return {
        name: (el.getAttribute('aria-label') || '').trim(),
        border: style.borderTopStyle,
        hidden: style.visibility === 'hidden' || style.display === 'none',
      };
    });
  const motion = document.querySelector('main button, main a');
  const motionStyle = motion ? getComputedStyle(motion) : null;
  return {
    focus: active && {
      tag: active.tagName,
      style: focusStyle.outlineStyle,
      width: parseFloat(focusStyle.outlineWidth) || 0,
    },
    icons, chips: chips.slice(0, 6), chipCount, disabled,
    motion: motionStyle && {
      duration: motionStyle.transitionDuration,
      animation: motionStyle.animationName,
    },
  };
}"""


def test_t28_forced_colors_and_reduced_motion_keep_cues(site) -> None:  # noqa: F811
    """Forced colors and reduced motion keep focus, names, chips and disabled actions."""
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    paths = _paths(client)
    failures: list = []
    saw_chip = False
    saw_disabled = False
    for javascript in (True, False):
        page = _page(site, client, viewport={'width': 1280, 'height': 720}, java_script_enabled=javascript)
        try:
            for label, path in paths:
                _goto(page, path)
                media = _force_media(page)
                if media != {'forced': True, 'motion': True}:
                    _shot(page, f't28-media-{label}-js{int(javascript)}')
                    failures.append((label, javascript, 'media', media))
                    continue
                page.keyboard.press('Tab')
                cues = page.evaluate(CUES)
                focus = cues['focus'] or {}
                bad_focus = focus.get('style') in (None, 'none', 'hidden') or focus.get('width', 0) <= 0
                bad_motion = (
                    not cues['motion']
                    or not str(cues['motion']['duration']).startswith('0s')
                    or cues['motion']['animation'] not in ('none', 'none, none')
                )
                bad_disabled = [
                    item for item in cues['disabled']
                    if item['hidden'] or not item['name'] or item['border'] != 'dashed'
                ]
                if cues['chipCount']:
                    saw_chip = True
                if cues['disabled']:
                    saw_disabled = True
                if bad_focus or cues['icons'] or cues['chips'] or bad_motion or bad_disabled:
                    _shot(page, f't28-{label}-js{int(javascript)}')
                    failures.append((label, javascript, {
                        'focus': focus, 'icons': cues['icons'], 'chips': cues['chips'],
                        'motion': cues['motion'], 'disabled': bad_disabled,
                    }))
        finally:
            page.context.close()
    if not saw_chip or not saw_disabled:
        failures.append(('coverage', saw_chip, saw_disabled))
    _record('t28.txt', failures)
    assert not failures, failures
