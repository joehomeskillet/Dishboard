"""BF-E3-F1: a blocked icon sprite stays named and operable.

Visible labels need the deferred probe. Without JavaScript the accessible name
stays in the markup; the sprite class is never set.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Browser, Page, expect

from test_admin_ux_browser import live_server, page_context
from test_admin_workflow_routes import DAY
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server', 'page_context']

SHOTS = Path(
    '/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18'
    '/.claude/state/claude-session-2026-09-29/audit/BF/E3-F1'
)
SCAFFOLD = Path(__file__).resolve().parents[1]
PAGES = (
    ('rezepte', '/admin/rezepte', 'a.ui-sem-control--icon-only[href$="/rezepte/neu"]'),
    ('menueditor', f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1',
     'a[data-semantic="navigation.weekplan"]'),
    ('wochenplan', f'/admin/cafeteria?week={DAY}', 'main a.ui-sem-control--icon-only[href*="/menu?"]'),
    ('bausteine', '/admin/cafeteria/komponenten', 'a[data-semantic="actions.add"][href="#c-name"]'),
)
MEASURE = '''() => {
  const coarse = matchMedia('(pointer: coarse), (any-pointer: coarse)').matches;
  const min = coarse ? 44 : 36;
  const fallback = document.documentElement.classList.contains('ui-asset-sprite-missing');
  const offenders = [];
  let seen = 0;
  for (const el of document.querySelectorAll('.ui-sem-control--icon-only')) {
    if (el.closest('[hidden]')) continue;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    if (!el.getClientRects().length) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    seen += 1;
    const label = (el.getAttribute('aria-label') || el.getAttribute('data-ui-tooltip') || '').trim();
    const semantic = el.getAttribute('data-semantic') || el.tagName;
    if (!label) {
      offenders.push({reason: 'unnamed', semantic});
      continue;
    }
    if (el.tabIndex < 0 && !el.matches(':disabled') && el.getAttribute('aria-disabled') !== 'true') {
      offenders.push({reason: 'tabindex', semantic, tabIndex: el.tabIndex});
    }
    if (!fallback) continue;
    if (rect.width + 0.6 < min || rect.height + 0.6 < min) {
      offenders.push({reason: 'size', semantic, label, w: rect.width, h: rect.height, min});
    }
    const icon = el.querySelector(':scope > .icon');
    if (icon) {
      const box = icon.getBoundingClientRect();
      if (box.width > 8 || box.height > 8) offenders.push({reason: 'icon', semantic, w: box.width, h: box.height});
    }
    const after = getComputedStyle(el, '::after');
    let text = after.content;
    try { text = JSON.parse(after.content); } catch (error) { /* CSS escapes stay raw. */ }
    if (text !== label) offenders.push({reason: 'label', semantic, label, text});
    if (parseFloat(after.fontSize) < 8) offenders.push({reason: 'font', semantic, font: after.fontSize});
    if (el.scrollWidth > el.clientWidth + 1) {
      offenders.push({reason: 'clip', semantic, label, sw: el.scrollWidth, cw: el.clientWidth});
    }
  }
  return {
    offenders, seen, fallback,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    styled: document.querySelectorAll('main [style]').length,
    flag: document.documentElement.dataset.adminAssetFallback || '',
  };
}'''


def _arm(context, *, images: bool) -> None:
    def handle(route):
        request = route.request
        url = request.url
        blocked = 'tabler-icons.svg' in url
        if images and request.resource_type == 'image':
            blocked = blocked or 'suedhang-logo' in url or ('/rezepte/' in url and '/bilder/' in url)
        if blocked:
            route.abort()
        else:
            route.continue_()
    context.route('**/*', handle)


def _open(browser, live_server, storage, width, height, coarse, javascript, *, images=False):
    context = browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        has_touch=coarse, java_script_enabled=javascript, reduced_motion='reduce',
        storage_state=storage,
    )
    _arm(context, images=images and javascript)
    return context


def _shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name))


def _ready(page: Page, javascript: bool) -> None:
    if not javascript:
        assert 'ui-asset-sprite-missing' not in (page.locator('html').get_attribute('class') or '')
        return
    page.wait_for_function("() => document.documentElement.classList.contains('ui-asset-sprite-missing')")
    page.evaluate('() => document.fonts.ready')


def _visible_icons(page: Page):
    return [control for control in page.locator('.ui-sem-control--icon-only').all() if control.is_visible()]


def _assert_nojs(page: Page) -> None:
    _ready(page, False)
    icons = _visible_icons(page)
    assert icons
    for control in icons:
        expect(control).to_have_accessible_name(re.compile(r'\S'))
        assert (control.get_attribute('aria-label') or control.get_attribute('data-ui-tooltip') or '').strip()
    assert page.locator('main [style]').count() == 0


def _focus_icon(page: Page, javascript: bool) -> None:
    page.locator('.skip-link').focus()
    for _ in range(80):
        page.keyboard.press('Tab')
        if page.locator('.ui-sem-control--icon-only:focus').count():
            break
    else:
        raise AssertionError('no icon-only control in tab order')
    if not javascript:
        return
    assert page.evaluate('() => getComputedStyle(document.activeElement).outlineStyle') != 'none'
    assert page.evaluate('() => document.activeElement.tabIndex') >= 0


def _click(page: Page, key: str, selector: str, javascript: bool) -> None:
    target = page.locator(selector).first
    expect(target).to_be_visible()
    target.scroll_into_view_if_needed()
    if key == 'bausteine':
        target.click()
        if javascript:
            expect(page.locator('#c-name')).to_be_focused()
        else:
            assert urlsplit(page.url).fragment == 'c-name'
        return
    with page.expect_navigation():
        target.click()
    if key == 'rezepte':
        assert urlsplit(page.url).path.rstrip('/').endswith('/rezepte/neu')
    elif key == 'menueditor':
        assert f'/admin/cafeteria?week={DAY}' in page.url
    else:
        assert '/menu?' in page.url


def _tab_names(page: Page) -> list[str]:
    page.locator('.skip-link').focus()
    names = []
    for _ in range(40):
        page.keyboard.press('Tab')
        names.append(page.evaluate('''() => {
          const el = document.activeElement;
          if (!el || el === document.body) return '';
          return (el.getAttribute('data-semantic') || el.tagName) + '|' + (el.getAttribute('aria-label') || '');
        }'''))
    return names


def test_asset_fallback_is_external_and_csp_safe() -> None:
    base = (SCAFFOLD / 'cafeteria/templates/admin/base_tabler.html').read_text()
    matches = [line.strip() for line in base.splitlines() if 'admin-asset-fallback.js' in line]
    assert matches == ["<script src=\"{{ url_for('static', filename='admin-asset-fallback.js') }}\" defer></script>"]
    script = (SCAFFOLD / 'cafeteria/static/admin-asset-fallback.js').read_text()
    for banned in ('onerror=', 'eval(', 'innerHTML', 'document.write', 'unsafe-inline'):
        assert banned not in script
    css = (SCAFFOLD / 'cafeteria/static/ui-semantic.css').read_text()
    fallback = css.split('html.ui-asset-sprite-missing', 1)[1]
    assert 'content: attr(aria-label)' in fallback and '#' not in fallback


@pytest.mark.parametrize('width,height', [(1440, 1100)], ids=['1440'])
def test_sprite_present_keeps_icon_geometry(browser, live_server, page_context, width, height) -> None:
    storage = page_context.context.storage_state()
    context = browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': height},
        reduced_motion='reduce', storage_state=storage,
    )
    page = context.new_page()
    try:
        assert page.goto('/admin/rezepte', wait_until='networkidle').status == 200
        state = page.evaluate(MEASURE)
        assert state['flag'] == '1'
        assert state['fallback'] is False
        assert state['offenders'] == [] and state['seen'] > 0 and state['styled'] == 0
        box = page.locator('header a.ui-sem-control--icon-only[href$="/rezepte/neu"]').bounding_box()
        assert box is not None and abs(box['width'] - 36) < 0.6 and abs(box['height'] - 36) < 0.6
    finally:
        context.close()


def test_sprite_block_keeps_tab_order(browser, live_server, page_context) -> None:
    storage = page_context.context.storage_state()
    plain = browser.new_context(
        base_url=live_server, viewport={'width': 1440, 'height': 1100},
        reduced_motion='reduce', storage_state=storage,
    )
    blocked = _open(browser, live_server, storage, 1440, 1100, False, True, images=True)
    try:
        first, second = plain.new_page(), blocked.new_page()
        assert first.goto('/admin/rezepte', wait_until='load').status == 200
        assert second.goto('/admin/rezepte', wait_until='load').status == 200
        _ready(second, True)
        assert _tab_names(first) == _tab_names(second)
    finally:
        plain.close()
        blocked.close()


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('width,height', [(1440, 1100), (390, 844)], ids=['1440', '390'])
@pytest.mark.parametrize('coarse', [False, True], ids=['fine', 'coarse'])
def test_blocked_sprite_keeps_actions_named(
    browser: Browser, live_server: str, page_context: Page,
    javascript: bool, width: int, height: int, coarse: bool,
) -> None:
    storage = page_context.context.storage_state()
    context = _open(browser, live_server, storage, width, height, coarse, javascript, images=True)
    page = context.new_page()
    try:
        for key, path, selector in PAGES:
            assert page.goto(path, wait_until='load').status == 200
            _ready(page, javascript)
            if javascript:
                assert page.evaluate("() => matchMedia('(pointer: coarse)').matches") is coarse
                state = page.evaluate(MEASURE)
                assert state['offenders'] == [], state['offenders']
                assert state['seen'] > 0 and state['overflow'] is False and state['styled'] == 0
                assert state['flag'] == '1'
            else:
                _assert_nojs(page)
            shot = {
                ('rezepte', 1440, False, True): 'sprite-rezepte-1440-fine-js.png',
                ('wochenplan', 390, True, True): 'sprite-wochenplan-390-coarse-js.png',
                ('bausteine', 1440, False, False): 'sprite-bausteine-1440-fine-nojs.png',
                ('menueditor', 1440, True, True): 'sprite-menueditor-1440-coarse-js.png',
            }.get((key, width, coarse, javascript))
            if shot:
                _shot(page, shot)
            _focus_icon(page, javascript)
            _click(page, key, selector, javascript)
    finally:
        context.close()


def test_sprite_fallback_initializes_once(browser, live_server, page_context) -> None:
    storage = page_context.context.storage_state()
    context = _open(browser, live_server, storage, 1440, 1100, False, True, images=True)
    page = context.new_page()
    hits = {'n': 0}

    def count_probe(request) -> None:
        if 'tabler-icons.svg' in request.url and request.resource_type in {'fetch', 'xhr'}:
            hits['n'] += 1

    page.on('request', count_probe)
    try:
        assert page.goto('/admin/rezepte', wait_until='load').status == 200
        _ready(page, True)
        before = hits['n']
        assert before >= 1
        page.evaluate('''() => {
          for (let i = 0; i < 20; i += 1) {
            window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));
          }
        }''')
        loaded = page.evaluate('''() => new Promise(resolve => {
          const script = document.createElement('script');
          script.src = '/static/admin-asset-fallback.js?reentry=1';
          script.onload = () => resolve(true);
          script.onerror = () => resolve(false);
          document.body.appendChild(script);
        })''')
        assert loaded is True
        assert hits['n'] == before
        assert page.evaluate('''() => {
          const names = document.documentElement.className.split(' ').filter(name => name === 'ui-asset-sprite-missing');
          return document.documentElement.dataset.adminAssetFallback === '1' && names.length === 1;
        }''')
    finally:
        context.close()
