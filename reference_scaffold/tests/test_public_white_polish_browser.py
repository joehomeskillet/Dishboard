"""White public layout: real HTTP, stable demo publications and native Chromium."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, ConsoleMessage, Page, Response

from test_public_mobile_ui import http_app as http_app
from test_public_mobile_ui import public_server as public_server
from test_rendered_ui import app as app
from test_rendered_ui import browser as browser

VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080))
WEB_ROUTES = (
    '/cafeteria/heute/', '/cafeteria/wochenangebot/',
    '/patienten/heute/', '/patienten/wochenplan/',
    '/cafeteria/wochenangebot/ohne-bilder/', '/patienten/wochenplan/ohne-bilder/',
)
TV_ROUTE = '/signage/cafeteria/tag'


def _capture(page: Page, output: Path) -> dict:
    page.evaluate('document.fonts.ready')
    page.screenshot(path=str(output.with_suffix('.png')), animations='disabled')
    metrics = page.evaluate('''() => {
      const box = el => { const r = el.getBoundingClientRect();
        return {x:r.x, y:r.y, width:r.width, height:r.height, bottom:r.bottom}; };
      const cards = [...document.querySelectorAll('.card:has(> .card-status-top)')];
      const nav = document.querySelector('.week-nav');
      return {
        viewport:[innerWidth,innerHeight], documentWidth:document.documentElement.scrollWidth,
        background:getComputedStyle(document.body).backgroundColor,
        backgroundImage:getComputedStyle(document.body).backgroundImage,
        font:getComputedStyle(document.body).fontFamily,
        cards:cards.map(el => ({...box(el), radius:getComputedStyle(el).borderTopLeftRadius,
          overflow:getComputedStyle(el).overflow, clipped:el.scrollHeight>el.clientHeight+1,
          titleFont:getComputedStyle(el.querySelector('.card-title')).fontSize,
          text:el.innerText})),
        navigation:nav ? {width:nav.clientWidth, scrollWidth:nav.scrollWidth,
          overflow:getComputedStyle(nav).overflowX,
          rows:[...new Set([...nav.children].map(el => Math.round(box(el).y)))],
          heights:[...nav.children].map(el => box(el).height)} : null,
        gaps:[...document.querySelectorAll('.hero-food')].map(el =>
          box(el.querySelector('footer')).y-box(el.querySelector('.hero-food-components')).bottom),
        images:[...document.images].filter(el => !el.loading || el.loading !== 'lazy').map(el =>
          ({loaded:el.complete&&el.naturalWidth>0, fit:getComputedStyle(el).objectFit})),
        content:document.querySelector('main').innerText
      };
    }''')
    first = page.locator('.card:has(> .card-status-top)').first
    first.scroll_into_view_if_needed()
    metrics['corner'] = first.evaluate('''el => {
      const r=el.getBoundingClientRect(), strip=el.querySelector('.card-status-top');
      const s=strip.getBoundingClientRect();
      return {radius:getComputedStyle(el).borderTopLeftRadius,
        overflow:getComputedStyle(el).overflow,
        stripeOutside:document.elementsFromPoint(r.left+.25,r.top+.25).includes(strip),
        stripeInside:document.elementsFromPoint(r.left+r.width/2,s.top+s.height/2).includes(strip),
        leftInset:s.left-r.left,rightInset:r.right-s.right,topInset:s.top-r.top};
    }''')
    rect = first.bounding_box()
    assert rect is not None
    page.screenshot(path=str(output.with_name(output.name + '-corner').with_suffix('.png')),
                    clip={'x': max(0, rect['x'] - 2), 'y': max(0, rect['y'] - 2),
                          'width': 100, 'height': 60}, animations='disabled')
    output.with_suffix('.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + '\n')
    return metrics


@pytest.mark.parametrize('route', (*WEB_ROUTES, TV_ROUTE))
def test_white_public_reference_matrix(
    http_app: Flask, public_server: str, browser: Browser, tmp_path: Path, route: str,
) -> None:
    """Record every viewport before evaluating geometry, so failures retain proof."""
    profile = 'patient' if 'patienten' in route else 'staff_guest'
    snapshot = http_app.config['TEST_SNAPSHOTS'][profile]
    fixture_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    collected = []
    for width, height in VIEWPORTS:
        errors: list[str] = []

        def console_error(message: ConsoleMessage) -> None:
            if message.type == 'error':
                errors.append(message.text)

        def http_error(response: Response) -> None:
            if response.status >= 400:
                errors.append(str(response.status))

        with browser.new_context(viewport={'width': width, 'height': height},
                                 java_script_enabled=False, locale='de-CH',
                                 timezone_id='Europe/Zurich', reduced_motion='reduce') as context:
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', console_error)
            page.on('requestfailed', lambda req: errors.append(req.url))
            page.on('response', http_error)
            response = page.goto(public_server + route, wait_until='networkidle')
            assert response is not None and response.status == 200
            assert 'set-cookie' not in response.headers
            assert "style-src 'self'" in response.headers['content-security-policy']
            metrics = _capture(page, tmp_path / f'{width}x{height}')
            metrics.update(route=route, browser=browser.version, fixture_sha256=fixture_hash, errors=errors)
            (tmp_path / f'{width}x{height}.json').write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2) + '\n')
            collected.append(metrics)
    for metrics in collected:
        width, _ = metrics['viewport']
        assert not metrics['errors']
        assert metrics['background'] == 'rgb(255, 255, 255)'
        assert metrics['backgroundImage'] == 'none'
        assert metrics['documentWidth'] <= width + 1
        assert all(image['loaded'] for image in metrics['images'])
        assert not any(card['clipped'] for card in metrics['cards'])
        corner = metrics['corner']
        assert float(corner['radius'].removesuffix('px')) > 0
        assert corner['overflow'] == 'hidden'
        assert not corner['stripeOutside'] and corner['stripeInside'], corner
        assert 0 <= corner['leftInset'] <= 1 and 0 <= corner['rightInset'] <= 1
        if metrics['navigation']:
            assert len(metrics['navigation']['rows']) == 1
            assert min(metrics['navigation']['heights']) >= 48
            if width == 390:
                assert metrics['cards'][0]['y'] < 520, metrics['cards'][0]['y']
        if route == TV_ROUTE and width == 1920:
            assert all(0 <= gap <= 24 for gap in metrics['gaps']), metrics['gaps']
        if profile == 'patient':
            assert 'CHF' not in metrics['content']
        else:
            assert 'CHF' in metrics['content']


@pytest.mark.parametrize('route', WEB_ROUTES[:4])
@pytest.mark.parametrize('javascript', (False, True))
def test_public_navigation_keyboard_and_zoom(
    http_app: Flask, public_server: str, browser: Browser, tmp_path: Path,
    route: str, javascript: bool,
) -> None:
    profile = 'patient' if 'patienten' in route else 'staff_guest'
    for day in http_app.config['TEST_SNAPSHOTS'][profile]['days']:
        for meal in day['services']:
            for option in meal['options']:
                option['note'] = 'Vollständiger Hinweis zur Rezeptur und Herkunft. ' * 8
    with browser.new_context(viewport={'width': 390, 'height': 844},
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        page = context.new_page()
        page.goto(public_server + route, wait_until='networkidle')
        page.locator('.site-logo').focus()
        page.keyboard.press('Shift+Tab')
        page.keyboard.press('Shift+Tab')
        skip = page.locator('a[href="#main-content"]')
        assert skip.is_visible()
        assert skip.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.keyboard.press('Enter')
        assert page.locator('main').evaluate('el => document.activeElement === el')
        if page.locator('.week-nav').count():
            nav = page.locator('.week-nav')
            nav.focus()
            if nav.evaluate('el => el.scrollWidth > el.clientWidth'):
                page.keyboard.press('ArrowRight')
                # Poll native keyboard scrolling without a script-page RAF/eval loop.
                for _ in range(20):
                    if nav.evaluate('el => el.scrollLeft > 0'):
                        break
                    page.wait_for_timeout(50)
                assert nav.evaluate('el => el.scrollLeft > 0')
            last = page.locator('.week-nav a').last
            last.focus()
            assert last.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
            page.keyboard.press('Enter')
            assert page.url.endswith(last.get_attribute('href') or 'missing')
        # Chromium CSS zoom exercises actual 200% layout/reflow, not a larger PNG DPR.
        page.evaluate("document.documentElement.style.zoom = '2'")
        page.evaluate('scrollTo(0,0)')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        cards = page.locator('.card:has(> .card-status-top)')
        assert cards.evaluate_all('els => els.every(el => el.scrollHeight <= el.clientHeight+1)')
        assert 'Vollständiger Hinweis zur Rezeptur und Herkunft. ' * 7 in cards.last.inner_text()
        cards.last.scroll_into_view_if_needed()
        assert cards.last.locator('[data-menu-metadata]').is_visible()
        page.screenshot(path=str(tmp_path / 'long-note-200percent.png'))


def test_tv_long_declarations_at_200percent_remain_reachable(
    http_app: Flask, public_server: str, browser: Browser, tmp_path: Path,
) -> None:
    options = http_app.config['TEST_SNAPSHOTS']['staff_guest']['days'][2]['services'][0]['options']
    note = 'Rezeptur, Herkunft und Produktdeklaration vollständig prüfen. ' * 8
    for option in options:
        option['note'] = note
    with browser.new_context(viewport={'width': 1920, 'height': 1080},
                             reduced_motion='reduce', java_script_enabled=False) as context:
        page = context.new_page()
        page.goto(public_server + TV_ROUTE, wait_until='networkidle')
        page.evaluate("document.documentElement.style.zoom = '2'")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        for card in page.locator('.hero-food').all():
            assert note.strip() in card.inner_text()
            assert card.evaluate('el => el.scrollHeight <= el.clientHeight+1')
            assert card.locator('.menu-photo img').evaluate('el => getComputedStyle(el).objectFit') == 'contain'
            card.locator('footer').scroll_into_view_if_needed()
            assert card.locator('.signage-price').is_visible()
        page.locator('.food-legend').scroll_into_view_if_needed()
        assert page.locator('.food-legend').is_visible()
        page.screenshot(path=str(tmp_path / 'tv-long-note-200percent.png'))


@pytest.mark.parametrize('route', ('/cafeteria/wochenangebot/', TV_ROUTE))
def test_upper_corner_at_native_triple_pixel_density(
    http_app: Flask, public_server: str, browser: Browser, tmp_path: Path, route: str,
) -> None:
    with browser.new_context(viewport={'width': 1920, 'height': 1080},
                             device_scale_factor=3, java_script_enabled=False) as context:
        page = context.new_page()
        page.goto(public_server + route, wait_until='networkidle')
        metrics = _capture(page, tmp_path / 'native-3x')
        assert not metrics['corner']['stripeOutside']
        assert metrics['corner']['stripeInside']
