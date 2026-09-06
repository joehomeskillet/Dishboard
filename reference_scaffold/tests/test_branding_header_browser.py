"""Header logo geometry, full image visibility and navigation over real HTTP/CSP."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine

from test_admin_workflow_routes import app as workflow_app, database_engine as database_engine  # noqa: F401
from test_branding_browser import live_branding as live_branding  # noqa: F401
from test_branding_logo_browser import _activate_logo, logo_site as logo_site
from test_rendered_ui import browser as browser

PUBLIC_PAGES = (
    ('/cafeteria/heute/', 2), ('/cafeteria/wochenangebot/', 10),
    ('/patienten/heute/', 4), ('/patienten/wochenplan/', 28),
)


def _assert_logo_box(page: Page, selector: str, height: int, size: tuple[int, int] | None) -> None:
    logo = page.locator(selector)
    expect(logo).to_be_visible()
    expect(logo).to_have_js_property('complete', True)
    metrics = logo.evaluate('''image => {
        const box = image.getBoundingClientRect();
        const parent = image.parentElement.getBoundingClientRect();
        return {width: box.width, height: box.height, naturalWidth: image.naturalWidth,
            naturalHeight: image.naturalHeight, fit: getComputedStyle(image).objectFit,
            contained: box.left >= parent.left && box.right <= parent.right + 1
                && box.top >= parent.top && box.bottom <= parent.bottom + 1,
            visible: box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight};
    }''')
    assert metrics['height'] == height, metrics
    assert metrics['width'] > 0 and metrics['naturalWidth'] > 0 and metrics['naturalHeight'] > 0
    assert metrics['fit'] == 'contain' and metrics['contained'] and metrics['visible'], metrics
    if size is not None:
        assert (metrics['naturalWidth'], metrics['naturalHeight']) == size
        # The actual painted pixels must retain the complete uploaded rectangle's aspect ratio.
        with Image.open(BytesIO(logo.screenshot())) as screenshot:
            rgb = screenshot.convert('RGB')
            mask = Image.new('L', rgb.size)
            mask.putdata([255 if rgb.getpixel((x, y)) == (120, 20, 60) else 0
                          for y in range(rgb.height) for x in range(rgb.width)])
            bounds = mask.getbbox()
        assert bounds is not None
        scale = min(metrics['width'] / size[0], height / size[1])
        assert abs(bounds[2] - bounds[0] - size[0] * scale) <= 2, (bounds, metrics)
        assert abs(bounds[3] - bounds[1] - size[1] * scale) <= 2, (bounds, metrics)


def _assert_equal_cards(page: Page, selector: str, count: int) -> None:
    cards = page.locator(selector)
    expect(cards).to_have_count(count)
    dimensions = cards.evaluate_all('''cards => cards.map(card => {
        const box = card.getBoundingClientRect();
        return {width: box.width, height: box.height,
            clipped: card.scrollWidth > card.clientWidth + 1 || card.scrollHeight > card.clientHeight + 1};
    })''')
    for axis in ('width', 'height'):
        values = [box[axis] for box in dimensions]
        assert max(values) - min(values) <= 1, dimensions
    assert not any(box['clipped'] for box in dimensions)


@pytest.mark.parametrize('width', (390, 820, 1440))
@pytest.mark.parametrize('size', (None, (100, 100), (100, 200), (640, 64)),
                         ids=('standard', 'square', 'portrait', 'wide'))
def test_header_logos_keep_fixed_boxes_and_full_images(
    logo_site, database_engine: Engine, browser: Browser, tmp_path: Path,
    width: int, size: tuple[int, int] | None,
) -> None:
    origin, _, client, actor, authz = logo_site
    tmp_path = tmp_path / ('standard' if size is None else f'{size[0]}x{size[1]}')
    tmp_path.mkdir()
    if size is not None:
        _activate_logo(database_engine, actor, authz, size)
    cookie = client.get_cookie('session')
    assert cookie is not None
    with browser.new_context(viewport={'width': width, 'height': 1100}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': origin}])
        page = context.new_page()
        failures = []
        navigation_aborts = []
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('console', lambda message: failures.append(message.text) if message.type == 'error' else None)
        # Leaving Screens cancels its lazy iframe loads/polling; retain those separately.
        page.on('requestfailed', lambda request: (
            navigation_aborts if request.failure == 'net::ERR_ABORTED' else failures
        ).append(f'{request.url}: {request.failure}'))
        page.on('response', lambda response: failures.append(f'{response.status}: {response.url}')
                if response.status >= 400 else None)
        response = page.goto(origin + '/admin/vorlagen', wait_until='load')
        assert response is not None and response.status == 200
        assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
        page.evaluate('document.fonts.ready')
        _assert_logo_box(page, '.admin-logo', 32, size)
        if width < 1200:
            toggle = page.get_by_role('button', name='Menü', exact=True)
            box = toggle.bounding_box()
            assert box is not None and box['width'] >= 48 and box['height'] >= 48
            page.screenshot(path=str(tmp_path / f'admin-header-{width}.png'))
            toggle.click()
            expect(toggle).to_have_attribute('aria-expanded', 'true')
        navigation = page.get_by_role('navigation', name='Backend')
        expect(navigation).to_be_visible()
        for link in navigation.locator('a:visible').all():
            box = link.bounding_box()
            assert box is not None and box['height'] >= 48, box
        page.screenshot(path=str(tmp_path / f'admin-navigation-{width}.png'))
        navigation.get_by_role('link', name='Screens', exact=True).click()
        expect(page).to_have_url(origin + '/admin/screens')
        page.evaluate('document.fonts.ready')
        _assert_equal_cards(page, '.screen-card', 4)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')

        for path, count in PUBLIC_PAGES:
            response = page.goto(origin + path, wait_until='load')
            assert response is not None and response.status == 200
            assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
            page.evaluate('document.fonts.ready')
            _assert_logo_box(page, '.site-logo-img', 40, size)
            _assert_equal_cards(page, '.card:has(> .card-status-top)', count)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            logo_link = page.locator('.site-logo')
            box = logo_link.bounding_box()
            assert box is not None and box['width'] >= 48 and box['height'] >= 48
            assert logo_link.get_attribute('href') in {route for route, _ in PUBLIC_PAGES}
            page.screenshot(path=str(tmp_path / f'{path.strip("/").replace("/", "-")}-{width}.png'))

        page.goto(origin + '/auth/local', wait_until='load')
        page.evaluate('document.fonts.ready')
        _assert_logo_box(page, '.site-logo-img', 40, size)
        login_logo = page.locator('.site-logo')
        box = login_logo.bounding_box()
        assert box is not None and box['width'] >= 48 and box['height'] >= 48
        page.screenshot(path=str(tmp_path / f'login-header-{width}.png'))
        login_logo.click()
        expect(page).to_have_url(origin + '/cafeteria/heute/')
        (tmp_path / 'requests.json').write_text(json.dumps({
            'navigation_aborts': navigation_aborts, 'errors': failures,
        }, indent=2), encoding='utf-8')
        assert failures == []
