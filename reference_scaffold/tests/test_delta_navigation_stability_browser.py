"""DELTA-4: real navigation geometry, scrollbars and role/empty states (DX-T33–42)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from cafeteria import roles
from test_master_data_browser import master_server  # noqa: F401
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, create, installed_pg16, pg16, seeded_pg16,
)


ROOT = Path(__file__).resolve().parents[2]
NAV = 'nav[aria-label="Stammdatenbereiche"]'
TABS = ('Zutaten', 'Lagerorte', 'Einheiten', 'Kategorien', 'Kennzeichnungen', 'Zutaten')
HINT = 'Kein Bestand erfasst. Lagerorte ordnen Zutaten zu; Bestandsbuchungen sind hier nicht verfügbar.'
MEASURE = """() => {
    const rect = el => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {x:r.x, y:r.y, width:r.width, height:r.height};
    };
    const nav = document.querySelector('nav[aria-label="Stammdatenbereiche"]');
    const root = document.scrollingElement;
    const hint = document.querySelector('#storage-list-hint');
    const frame = document.querySelector('.page-body > .container-xl');
    return {
        nav:rect(nav), tabs:Object.fromEntries([...nav.querySelectorAll('a')].map(
            el => [el.textContent.trim(), rect(el)])),
        sidebar:rect(document.querySelector('aside.admin-sidebar')),
        frame:rect(frame), header:rect(document.querySelector('.page-header')),
        toolbar:rect(document.querySelector('.grundlagen-master')),
        row:rect(document.querySelector('.grundlagen-list .admin-list-row')),
        hint:rect(hint), hintText:hint?.textContent.trim(),
        hintInDisclosure:!!hint?.closest('details'),
        viewport:{width:innerWidth, height:innerHeight, zoom:visualViewport.scale},
        coarse:matchMedia('(pointer: coarse)').matches,
        scroll:{x:scrollX, y:scrollY, left:root.scrollLeft, top:root.scrollTop,
            height:root.scrollHeight, clientHeight:root.clientHeight,
            container:root.tagName, scrollbar:innerWidth-document.documentElement.clientWidth,
            gutter:getComputedStyle(root).scrollbarGutter,
            navLeft:nav.scrollLeft, sidebarTop:document.querySelector('#sidebar-menu').scrollTop},
        autofocus:[...document.querySelectorAll('[autofocus]')].map(el => el.id),
        hash:location.hash, focus:document.activeElement.tagName,
        horizontalOverflow:root.scrollWidth > innerWidth + 1
    };
}"""


def _measure(page, samples, event, kind):
    page.evaluate('document.fonts.ready')
    page.evaluate('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
    result = dict(event=event, kind=kind, **page.evaluate(MEASURE))
    samples.append(result)
    return result


def _differences(before, after):
    differences = []
    pairs = [('nav', before['nav'], after['nav']),
             ('sidebar', before['sidebar'], after['sidebar']),
             ('header', before['header'], after['header']),
             *[(f'tab:{name}', box, after['tabs'][name]) for name, box in before['tabs'].items()]]
    for name, left, right in pairs:
        for axis in ('x', 'y', 'width', 'height'):
            if abs(left[axis] - right[axis]) > 1:
                differences.append(f'{name}.{axis}: {left[axis]:.3f} -> {right[axis]:.3f}')
    # Content height intentionally changes with list length; frame origin/width must not.
    for axis in ('x', 'y', 'width'):
        left, right = before['frame'][axis], after['frame'][axis]
        if abs(left - right) > 1:
            differences.append(f'frame.{axis}: {left:.3f} -> {right:.3f}')
    for axis in ('x', 'y', 'left', 'top', 'navLeft', 'sidebarTop'):
        left, right = before['scroll'][axis], after['scroll'][axis]
        if abs(left - right) > 1:
            differences.append(f'scroll.{axis}: {left:.3f} -> {right:.3f}')
    return differences


def _save_evidence(samples, failures, state, scrollbars, revision, evidence):
    payload = dict(revision=revision, state=state, scrollbars=scrollbars,
                   tolerance_css_px=1, samples=samples, failures=failures)
    stem = evidence / f'{state}-{scrollbars}'
    stem.with_suffix('.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    lines = [f'# DELTA-4 — {state}, {scrollbars}', '', f'Revision: `{revision}`', '',
             'Tolerance: 1 CSS px. Full rectangles and internal/document scroll positions: adjacent JSON.', '',
             '| Viewport / pointer | Event / kind | Nav x/y/w/h | Scroll x/y | Scrollbar px |',
             '|---|---|---|---|---|']
    for item in samples:
        box = '/'.join(f'{item["nav"][axis]:.3f}' for axis in ('x', 'y', 'width', 'height'))
        lines.append(f'| {item["viewport"]["width"]} / {"coarse" if item["coarse"] else "fine"} '
                     f'| {item["event"]} / {item["kind"]} | {box} '
                     f'| {item["scroll"]["x"]}/{item["scroll"]["y"]} | {item["scroll"]["scrollbar"]} |')
    lines.extend(['', '## Violations', '', *(failures or ['None.'])])
    stem.with_suffix('.md').write_text('\n'.join(lines) + '\n')


@pytest.mark.parametrize('scrollbars', ['overlay', 'classic'])
@pytest.mark.parametrize('state', ['populated', 'empty', 'readonly'])
def test_delta_navigation_stability(b3, master_server, monkeypatch, state, scrollbars, tmp_path, request):  # noqa: F811
    """Moving hint above nav or changing active tab width must fail with measured deltas."""
    _, _, client, _ = b3
    if state != 'empty':
        for number in range(24):
            create(client, name=f'Geometriezutat {number:02d}')
        create(client, 'kategorien', name='Geometriekategorie', code='GEOMETRY', sort_order='1')
        create(client, 'tags', name='Geometriekennzeichnung', code='GEOMETRY')
    if state == 'readonly':
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    base, cookie = master_server
    # The gate's --basetemp places before/after evidence in the assigned audit directory.
    evidence = tmp_path
    revision = subprocess.check_output(['rtk', 'git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    revision += ' + working tree: ' + subprocess.check_output(
        ['rtk', 'git', 'diff', '--stat'], cwd=ROOT, text=True).strip()
    samples, failures = [], []
    request.addfinalizer(lambda: _save_evidence(samples, failures, state, scrollbars, revision, evidence))
    args = ['--no-sandbox', '--disable-dev-shm-usage']
    if scrollbars == 'overlay':
        args.append('--enable-features=OverlayScrollbar')
    with sync_playwright() as playwright:
        with playwright.chromium.launch(args=args, ignore_default_args=['--hide-scrollbars']) as browser:
            for width in (1440, 1024, 390):
                for coarse in (False, True):
                    with browser.new_context(viewport={'width': width, 'height': 900}, has_touch=coarse,
                                             reduced_motion='reduce') as context:
                        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
                        page = context.new_page()
                        response = page.goto(base + '/admin/grundlagen', wait_until='load')
                        assert response.status == 200
                        start = _measure(page, samples, 'start', TABS[0])
                        assert start['coarse'] == coarse, start
                        if state == 'readonly':
                            expect(page.locator('main [data-semantic="actions.add"]')).to_have_count(0)
                        if state == 'empty':
                            expect(page.get_by_text('Keine passenden Zutaten', exact=True)).to_be_visible()
                        previous = start
                        for label in TABS[1:]:
                            link = page.locator(NAV).get_by_role('link', name=label, exact=True)
                            link.hover()
                            hovered = _measure(page, samples, 'hover', previous['kind'])
                            link.focus()
                            focused = _measure(page, samples, 'focus', previous['kind'])
                            for current in (hovered, focused):
                                failures.extend(f'{width}/{coarse} {current["event"]}: {d}'
                                                for d in _differences(previous, current))
                            href = link.get_attribute('href')
                            link.press('Enter')
                            page.wait_for_url(base + href, wait_until='load')
                            selected = _measure(page, samples, 'selected', label)
                            expect(page.locator(NAV).locator('[aria-current="page"]')).to_have_text(label)
                            failures.extend(f'{width}/{coarse} {previous["kind"]} -> {label}: {d}'
                                            for d in _differences(start, selected))
                            if selected['autofocus'] or selected['hash'] or selected['horizontalOverflow']:
                                failures.append(f'{width}/{coarse} unexpected navigation state: {selected}')
                            if label == 'Lagerorte':
                                hint = page.locator('#storage-list-hint')
                                # Exercise existing tooltip/disclosure for the before measurement too.
                                trigger = page.locator('details.admin-hint summary')
                                if trigger.count():
                                    trigger.click()
                                expect(hint).to_have_text(HINT)
                                hint_state = _measure(page, samples, 'hint-visible', label)
                                if hint_state['hintInDisclosure']:
                                    failures.append(f'{width}/{coarse} Lagerorte hint is a disclosure')
                                if hint_state['hint']['y'] < selected['toolbar']['y'] + selected['toolbar']['height'] - 1:
                                    failures.append(f'{width}/{coarse} hint precedes toolbar: {hint_state["hint"]}, '
                                                    f'toolbar={selected["toolbar"]}')
                                failures.extend(f'{width}/{coarse} hint: {d}'
                                                for d in _differences(selected, hint_state))
                            page.screenshot(path=str(evidence / f'{state}-{scrollbars}-{width}-{coarse}-{label}.png'))
                            page.go_back(wait_until='load')
                            returned = _measure(page, samples, 'back', previous['kind'])
                            failures.extend(f'{width}/{coarse} back: {d}' for d in _differences(previous, returned))
                            page.go_forward(wait_until='load')
                            previous = _measure(page, samples, 'forward', label)
                            failures.extend(f'{width}/{coarse} forward: {d}' for d in _differences(selected, previous))
                        if state != 'empty':
                            heights = [x['scroll']['height'] > x['scroll']['clientHeight']
                                       for x in samples if x['viewport']['width'] == width and x['coarse'] == coarse
                                       and x['event'] == 'selected']
                            assert any(heights) and not all(heights), f'Need short AND long lists: {heights}'
                            long = next(x for x in samples if x['viewport']['width'] == width and x['coarse'] == coarse
                                        and x['kind'] == 'Zutaten' and x['event'] == 'selected')
                            assert (long['scroll']['scrollbar'] > 0) == (scrollbars == 'classic'), long['scroll']
                            page.evaluate('scrollTo(0, 200)')
                            assert page.evaluate('scrollY') > 0, 'Long list must remain scrollable'
    assert not failures, '\n'.join(failures)
