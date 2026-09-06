"""Actual HTTP/CSP logo consumers, including closed, unavailable and print views."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine

from cafeteria.branding import change_branding
from cafeteria.branding_assets import normalize_logo
from cafeteria.branding_config import default_config
from test_admin_workflow_routes import app as workflow_app, database_engine as database_engine  # noqa: F401
from test_branding_browser import live_branding as live_branding
from test_branding_store import _png
from test_rendered_ui import browser as browser
from demo_snapshots import cafeteria_snapshot, patient_snapshot


@pytest.fixture
def logo_site(live_branding, monkeypatch: pytest.MonkeyPatch):
    origin, application, client, actor, authz = live_branding
    snapshots = {'staff_guest': cafeteria_snapshot(), 'patient': patient_snapshot()}
    application.config.update(LOCAL_AUTH_ENABLED=True, DEMO_TODAY='2026-08-31', TEST_SNAPSHOTS=snapshots)
    monkeypatch.setattr('cafeteria.public.routes.active_snapshot',
                        lambda _engine, profile, *_args, **_kwargs: deepcopy(snapshots[profile]))
    return origin, application, client, actor, authz


def _activate_logo(engine: Engine, actor: int, authz: int, size: tuple[int, int]) -> str:
    asset = normalize_logo(_png(size))
    change_branding(engine, actor, authz, 0, 'save', name='Testmarke',
                    config={**default_config(), 'logo_sha256': asset.sha256}, logo=asset)
    change_branding(engine, actor, authz, 1, 'activate', revision_id=2)
    return f'/branding/logos/{asset.sha256}.png'


def _assert_logo(page: Page, source: str) -> None:
    image = page.locator('img.brand-logo')
    expect(image).to_have_count(1)
    expect(image).to_have_attribute('src', source)
    expect(image).to_be_visible()
    assert page.locator('.wordmark-mark').count() == 0
    assert page.locator('img[src*="suedhang-logo"], img[src*="/branding/logos/"]').count() == 1
    if image.get_attribute('class') == 'brand-logo site-logo-img':
        assert image.evaluate('image => image.getBoundingClientRect().height <= 40')
    assert image.evaluate('''image => {
        const box = image.getBoundingClientRect();
        return image.complete && image.naturalWidth > 0 && image.naturalHeight > 0
            && getComputedStyle(image).objectFit === 'contain'
            && box.width > 0 && box.height > 0 && box.x >= 0 && box.y >= 0
            && box.right <= innerWidth + 1 && box.bottom <= innerHeight + 1;
    }''')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def _assert_signage_layout(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight + 1')
    assert page.locator('.food-legend:visible, [data-menu-metadata]:visible').evaluate_all('''nodes => nodes.every(node => {
        const box = node.getBoundingClientRect();
        return box.bottom <= innerHeight + 1 && box.right <= innerWidth + 1
            && node.scrollWidth <= node.clientWidth + 1 && node.scrollHeight <= node.clientHeight + 1;
    })''')


@pytest.mark.parametrize('size', [None, (100, 200), (640, 64)], ids=['standard', 'portrait', 'wide'])
def test_all_eleven_logo_consumers_use_the_active_brand(
    logo_site, database_engine: Engine, browser: Browser, tmp_path: Path, size: tuple[int, int] | None,
) -> None:
    origin, application, _, actor, authz = logo_site
    source = '/static/img/suedhang-logo.png' if size is None else _activate_logo(database_engine, actor, authz, size)
    snapshots = application.config['TEST_SNAPSHOTS']
    public_cases = [
        ('legend', '/cafeteria/legende/', 200, None),
        ('public-unavailable', '/cafeteria/heute/', 404, None),
        ('print-cafeteria', '/druck/cafeteria/woche', 200, 10),
        ('print-patient', '/druck/patienten/woche', 200, 28),
        ('login', '/auth/local', 200, None),
    ]
    signage_cases = [
        ('cafeteria-day', '/signage/cafeteria/tag', 200),
        ('cafeteria-week', '/signage/cafeteria/woche', 200),
        ('patient-day', '/signage/patienten/tag', 200),
        ('patient-week', '/signage/patienten/woche', 200),
        ('cafeteria-closed', '/signage/cafeteria/tag', 200),
        ('signage-unavailable', '/signage/patienten/woche', 404),
    ]
    with browser.new_context(java_script_enabled=False, reduced_motion='reduce') as context:
        # Each changed fixture state must reach HTTP, even for the same public URL.
        context.route('**/*', lambda route: route.continue_())
        page = context.new_page()
        failures = []
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.on('response', lambda response: failures.append(response.url)
                if response.status >= 400 and response.request.resource_type != 'document' else None)
        for name, path, status, count in public_cases:
            saved = snapshots['staff_guest']
            if status == 404:
                snapshots['staff_guest'] = None
            for width in (390, 1440):
                page.set_viewport_size({'width': width, 'height': 1100})
                response = page.goto(origin + path, wait_until='networkidle')
                assert response is not None and response.status == status
                assert "style-src 'self'" in response.headers['content-security-policy']
                page.evaluate('document.fonts.ready')
                _assert_logo(page, source)
                if count:
                    assert page.locator('[data-menu-metadata]').count() == count
                    expect(page.locator('.food-legend')).to_contain_text('Legende der gedruckten Menüs')
                    assert 'Enthält:' in page.locator('main').inner_text()
                    if name == 'print-patient':
                        assert 'CHF' not in page.locator('main').inner_text()
                if name == 'login':
                    expect(page.get_by_label('Benutzername')).to_be_visible()
                    expect(page.get_by_role('button', name='Anmelden', exact=True)).to_be_visible()
                page.screenshot(path=str(tmp_path / f'{name}-{width}.png'), full_page=True)
            if count:
                page.emulate_media(media='print')
                _assert_logo(page, source)
                expect(page.locator('.print-header')).to_be_visible()
                page.screenshot(path=str(tmp_path / f'{name}-print.png'), full_page=True)
                page.emulate_media(media='screen')
            snapshots['staff_guest'] = saved
        for name, path, status in signage_cases:
            application.config['DEMO_TODAY'] = '2026-09-06' if name == 'cafeteria-closed' else '2026-08-31'
            saved = snapshots['patient']
            if status == 404:
                snapshots['patient'] = None
            for width, height in ((1920, 1080), (3840, 2160)):
                page.set_viewport_size({'width': width, 'height': height})
                response = page.goto(origin + path, wait_until='networkidle')
                assert response is not None and response.status == status
                page.evaluate('document.fonts.ready')
                _assert_logo(page, source)
                _assert_signage_layout(page)
                if name == 'cafeteria-closed':
                    expect(page.get_by_role('heading', name='Cafeteria geschlossen')).to_be_visible()
                elif status == 404:
                    expect(page.locator('.food-legend')).to_have_count(0)
                else:
                    expect(page.locator('.food-legend:visible')).to_have_count(1)
                    assert page.locator('[data-menu-metadata]:visible').count() > 0
                page.screenshot(path=str(tmp_path / f'{name}-{width}.png'))
            snapshots['patient'] = saved
        assert failures == []


def test_running_signage_replaces_logo_and_reset_keeps_all_patient_pages(
    logo_site, database_engine: Engine, browser: Browser, tmp_path: Path,
) -> None:
    origin, application, _, actor, authz = logo_site
    with browser.new_context(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce') as context:
        page = context.new_page()
        page.clock.install()
        page.goto(origin + '/signage/patienten/woche', wait_until='load')
        revision = page.locator('html').get_attribute('data-signage-revision')
        source = _activate_logo(database_engine, actor, authz, (100, 200))
        page.clock.fast_forward(1000)
        expect(page.locator('html')).to_have_attribute('data-brand-revision', '2')
        _assert_logo(page, source)
        seen = page.locator('.patient-week-option:visible h3').all_text_contents()
        page.screenshot(path=str(tmp_path / 'patient-rotation-logo-first.png'))
        page.clock.fast_forward(30100)
        seen.extend(page.locator('.patient-week-option:visible h3').all_text_contents())
        assert len(seen) == 28
        expected = [option['title'] for day in application.config['TEST_SNAPSHOTS']['patient']['days']
                    for meal in day['services'] for option in meal['options']]
        assert seen == expected
        _assert_logo(page, source)
        page.screenshot(path=str(tmp_path / 'patient-rotation-logo-second.png'))
        change_branding(database_engine, actor, authz, 2, 'reset')
        change_branding(database_engine, actor, authz, 3, 'activate', revision_id=3)
        page.clock.fast_forward(1000)
        expect(page.locator('html')).to_have_attribute('data-brand-revision', '3')
        _assert_logo(page, '/static/img/suedhang-logo.png')
        assert page.locator('html').get_attribute('data-signage-revision') == revision
        page.screenshot(path=str(tmp_path / 'patient-reset-standard.png'))
