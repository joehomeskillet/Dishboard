"""MP-UI-REF-LIST: real HTTP, scoped PostgreSQL data and proposed Chromium captures."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

from cafeteria.branding_config import contrast
from cafeteria.display_settings import DEFAULT_ADMIN_DISPLAY, set_admin_display
from cafeteria.workflow_review import get_component_review_token, review_component
from test_admin_workflow_routes import (
    WEEK, _login, _payload, app as workflow_app, database_engine,  # noqa: F401
)
from test_branding_browser import live_branding  # noqa: F401
from test_menu_collection import _save, _scope
from test_rendered_ui import browser  # noqa: F401

VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080))
FAMILIES = (('cafeteria', 'staff_guest'), ('patienten', 'patient'))
DESCRIPTION = ('Gespeicherte Menüs aus allen Wochen. Öffnen führt direkt zum jeweiligen '
               'Menü im Wochenplan.')
LONG_TITLE = 'Langtext ' + 'Sommergemüse mit Kräutern ' * 7
LONG_NOTE = 'Wichtiger Zubereitungshinweis bleibt vollständig lesbar. ' * 6


def _photo_payload(profile: str) -> dict:
    values = _payload(staff=profile == 'staff_guest')
    values['assignments'] = [{'component_public_id': None, 'component_text': name}
                             for name in ('Kartoffelstock', 'Zucchetti')]
    return values


def _context(chromium, origin, client, javascript):
    context = chromium.new_context(
        base_url=origin, viewport={'width': 1440, 'height': 900},
        locale='de-CH', timezone_id='Europe/Zurich', device_scale_factor=1,
        java_script_enabled=javascript, reduced_motion='reduce',
    )
    context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value,
                         'url': origin}])
    return context


def _goto(page: Page, path: str, status: int = 200) -> None:
    response = page.goto(path, wait_until='networkidle')
    assert response is not None and response.status == status
    assert "style-src 'self'; script-src 'self'" in response.headers['content-security-policy']
    page.evaluate('document.fonts.ready')


def _versions(engine) -> list:
    with engine.connect() as connection:
        return [connection.execute(text(query)).all() for query in (
            'SELECT id,row_version,workflow_state FROM cafeteria.menu_weeks ORDER BY id',
            'SELECT id,row_version,allergen_review_status FROM cafeteria.menu_items ORDER BY id',
        )]


def _capture(page: Page, directory: Path, name: str) -> None:
    page.evaluate('document.fonts.ready')
    for image in page.locator('.menu-photo img:visible').all():
        image.scroll_into_view_if_needed()
        expect(image).to_have_js_property('complete', True)
        assert image.evaluate('el => el.naturalWidth > 0')
    page.evaluate('window.scrollTo(0, 0)')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), name
    screenshot = directory / f'{name}.png'
    page.screenshot(path=str(screenshot), full_page=True, animations='disabled')


def _measure(page: Page, count: int, contrast_failures: list) -> None:
    expect(page.locator('h1')).to_have_count(1)
    expect(page.locator('.admin-page-header h1')).to_have_text('Menüs')
    expect(page.locator('.page-header-subtitle')).to_have_text(DESCRIPTION)
    expect(page.locator('.admin-page-header .btn')).to_have_count(0)
    expect(page.locator('main')).to_have_attribute('data-layout', 'standard')
    expect(page.locator('[data-menu-id]')).to_have_count(count)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    text_pairs = page.locator(
        'main .badge:visible, main h1, main h2:visible, main p:visible, '
        'main .form-label, main .page-header-subtitle, main .nav-link:visible, '
        'main .btn:visible, main th:visible, main td:visible',
    ).evaluate_all('''elements => elements.map(el => {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 1;
        const ctx = canvas.getContext('2d', {willReadFrequently: true});
        const hex = () => '#' + Array.from(ctx.getImageData(0, 0, 1, 1).data).slice(0, 3)
            .map(value => value.toString(16).padStart(2, '0')).join('');
        ctx.fillStyle = 'white'; ctx.fillRect(0, 0, 1, 1);
        const parents = [];
        for (let parent = el; parent; parent = parent.parentElement) parents.unshift(parent);
        for (const parent of parents) {
            ctx.fillStyle = getComputedStyle(parent).backgroundColor; ctx.fillRect(0, 0, 1, 1);
        }
        const bg = hex();
        ctx.fillStyle = getComputedStyle(el).color; ctx.fillRect(0, 0, 1, 1);
        return {text: hex(), bg, label: el.textContent};
    })''')
    assert text_pairs
    for pair in text_pairs:
        ratio = contrast(pair['text'], pair['bg'])
        if ratio < 4.5:
            finding = {**pair, 'ratio': ratio}
            if finding not in contrast_failures:
                contrast_failures.append(finding)
    for link in page.locator('[data-admin-icon-action]:visible').all():
        assert link.inner_text() == 'Öffnen'
        box = link.bounding_box()
        assert box is not None and box['height'] >= 48
    geometry = page.locator('[data-menu-id]:visible').evaluate_all('''cards => cards.map(el => {
        const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return {width: r.width, height: r.height, radius: s.borderRadius, shadow: s.boxShadow,
                overflow: el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1};
    })''')
    if geometry:
        for axis in ('width', 'height'):
            assert max(card[axis] for card in geometry) - min(card[axis] for card in geometry) <= 1
        assert all(card['radius'] == '12px' and card['shadow'] != 'none'
                   and not card['overflow'] for card in geometry), geometry
    for cell in page.locator('.dishboard-menu-table :is(th, td):visible').all():
        assert cell.evaluate('el => parseFloat(getComputedStyle(el).fontSize)') >= 14
    assert page.locator('[data-menu-id]:visible :is(h2, p, li)').evaluate_all('''els => els.every(el => {
        const s = getComputedStyle(el);
        return s.webkitLineClamp === 'none' && el.scrollHeight <= el.clientHeight + 1 &&
            el.scrollWidth <= el.clientWidth + 1;
    })''')


def _views(page: Page, javascript: bool, directory: Path, state: str, count: int,
           contrast_failures: list, viewports=VIEWPORTS) -> None:
    for width, height in viewports:
        page.set_viewport_size({'width': width, 'height': height})
        for view in ('cards', 'list'):
            if javascript:
                page.get_by_role('tab', name='Karten' if view == 'cards' else 'Liste', exact=True).click()
            else:
                page.get_by_role('navigation', name='Menüansicht ohne JavaScript').get_by_role(
                    'link', name='Karten' if view == 'cards' else 'Liste', exact=True,
                ).click()
            expect(page.locator(f'#menu-{view}')).to_be_visible()
            _measure(page, count, contrast_failures)
            _capture(page, directory, f'{state}-{view}-{width}x{height}')


def _keyboard(page: Page, javascript: bool) -> None:
    page.locator('main').focus()
    page.keyboard.press('Tab')
    expect(page.get_by_role('navigation', name='Profil').get_by_role('link').first).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('navigation', name='Profil').get_by_role('link').last).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('#menu-query')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('button', name='Suchen', exact=True)).to_be_focused()
    page.keyboard.press('Tab')
    if javascript:
        cards = page.get_by_role('tab', name='Karten', exact=True)
        expect(cards).to_be_focused()
        page.keyboard.press('ArrowRight')
        expect(page.get_by_role('tab', name='Liste', exact=True)).to_be_focused()
        page.keyboard.press('ArrowLeft')
        expect(cards).to_be_focused()
        page.keyboard.press('Tab')
        expect(page.locator('#menu-cards')).to_be_focused()
    else:
        expect(page.get_by_role('navigation', name='Menüansicht ohne JavaScript').get_by_role('link').first).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('#menu-cards')).to_be_focused()
    page.keyboard.press('Tab')
    action = page.locator('#menu-cards [data-admin-icon-action]').first
    expect(action).to_be_focused()
    assert action.evaluate('el => getComputedStyle(el).outlineStyle') == 'solid'
    assert action.evaluate('el => parseFloat(getComputedStyle(el).outlineWidth)') >= 2
    page.keyboard.press('Escape')


@pytest.mark.parametrize('family,profile', FAMILIES)
@pytest.mark.parametrize('javascript', (True, False))
def test_reference_states_and_viewports(
    live_branding, database_engine, browser, family, profile, javascript, tmp_path,  # noqa: F811
):
    origin, app, client, _, _ = live_branding
    app.config['DEMO_TODAY'] = '2026-09-02'
    scope = _scope(client, database_engine, profile)
    route = f'/admin/{family}/menues'
    with _context(browser, origin, client, javascript) as context:
        page = context.new_page()
        errors = []
        contrast_failures = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('requestfailed', lambda request: errors.append(request.failure))
        _goto(page, route)
        expect(page.locator('[data-empty-kind="none"]')).to_have_count(2)
        expect(page.get_by_role('navigation', name='Ergebnisseiten')).to_have_count(0)
        _views(page, javascript, tmp_path, 'empty', 0, contrast_failures)
        _save(database_engine, scope, title='Pouletbrust an Kräutersauce', payload=_photo_payload(profile))
        _save(database_engine, scope, week=WEEK + timedelta(weeks=1), title='Tomatensuppe')
        with database_engine.begin() as connection:
            connection.execute(text("UPDATE cafeteria.menu_items SET allergen_review_status='checked'"))
            row = connection.execute(text("SELECT id,row_version FROM cafeteria.menu_items WHERE title='Tomatensuppe'")).one()
        review_component(database_engine, scope, row.id,
                         get_component_review_token(database_engine, scope, row.id), row.row_version)
        before = _versions(database_engine)
        _goto(page, route)
        _keyboard(page, javascript)
        expect(page.locator('#menu-cards [data-status="success"]')).to_have_count(1)
        expect(page.locator('#menu-cards [data-status="review_open"]')).to_have_count(1)
        _views(page, javascript, tmp_path, 'normal', 2, contrast_failures)
        assert _versions(database_engine) == before
        page.get_by_label('Menü oder Komponente suchen').fill('KeinTreffer')
        page.get_by_role('button', name='Suchen', exact=True).click()
        expect(page.locator('#menu-query')).to_have_value('KeinTreffer')
        expect(page.locator('[data-empty-kind="no_match"]')).to_have_count(2)
        _views(page, javascript, tmp_path, 'no-match', 0, contrast_failures)
        page.get_by_role('link', name='Suche zurücksetzen', exact=True).click()
        expect(page.locator('#menu-query')).to_have_value('')
        payload = _payload(staff=profile == 'staff_guest')
        payload.update(description='Saisonales Gemüse schonend zubereiten. ' * 8, note=LONG_NOTE,
                       assignments=[{'component_public_id': None, 'component_text': 'Gemüse' * 30}])
        _save(database_engine, scope, week=WEEK + timedelta(weeks=2), title=LONG_TITLE, payload=payload)
        _goto(page, route)
        expect(page.locator('#menu-cards .shared-note')).to_contain_text(LONG_NOTE.strip())
        _views(page, javascript, tmp_path, 'long-text', 3, contrast_failures)
        for offset in range(3, 26):
            _save(database_engine, scope, week=WEEK + timedelta(weeks=offset), title=f'Gemüsemenü {offset}')
        before = _versions(database_engine)
        _goto(page, route)
        _views(page, javascript, tmp_path, 'dense', 24, contrast_failures)
        for width, height in ((1440, 900), (390, 844)):
            page.set_viewport_size({'width': width, 'height': height})
            if javascript:
                page.get_by_role('tab', name='Liste', exact=True).click()
            expect(page.locator('#menu-list').get_by_text('Gespeicherter Prüfvermerk:').first).to_be_visible()
            expect(page.locator('#menu-list').get_by_text('Allergenangaben nicht erfasst').first).to_be_visible()
            region = page.get_by_role('region', name='Menüliste', exact=True)
            region.focus()
            page.keyboard.press('Shift+Tab')
            page.keyboard.press('Tab')
            expect(region).to_be_focused()
            assert region.evaluate('el => getComputedStyle(el).outlineStyle') == 'solid'
            if width == 390:
                page.keyboard.press('ArrowRight')
                expect(region).not_to_have_js_property('scrollLeft', 0)
            _capture(page, tmp_path, f'keyboard-scroll-{width}')
        page.get_by_role('navigation', name='Ergebnisseiten').get_by_role('link', name='Weiter').click()
        expect(page.locator('[data-menu-id]')).to_have_count(2)
        expect(page.get_by_role('navigation', name='Ergebnisseiten').get_by_role('link', name='Weiter')).to_have_count(0)
        assert parse_qs(urlsplit(page.url).query) == {'page': ['2']}
        _views(page, javascript, tmp_path, 'last-page', 2, contrast_failures, ((1440, 900), (390, 844)))
        _goto(page, route + '?q=Gemüse')
        expect(page.locator('[data-menu-id]')).to_have_count(24)
        for link in page.get_by_role('navigation', name='Profil').get_by_role('link').all():
            assert parse_qs(urlsplit(link.get_attribute('href')).query) == {'q': ['Gemüse']}
        _goto(page, route + '?q=Langtext')
        expect(page.locator('[data-menu-id]')).to_have_count(1)
        # CSS zoom exercises layout magnification; DPR is deliberately unchanged.
        for width, height in ((1440, 900), (390, 844)):
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate("document.documentElement.style.zoom = '2'")
            _measure(page, 1, contrast_failures)
            _capture(page, tmp_path, f'zoom200-{width}')
            page.evaluate("document.documentElement.style.zoom = ''")
        assert _versions(database_engine) == before
        _goto(page, route + '?q=Pouletbrust')
        photo = page.locator('#menu-cards .menu-photo img')
        expect(photo).to_have_count(1)
        photo.scroll_into_view_if_needed()
        expect(photo).to_have_js_property('naturalWidth', 1200)
        cdp = context.new_cdp_session(page)
        cdp.send('DOM.enable')
        cdp.send('CSS.enable')
        root = cdp.send('DOM.getDocument')['root']['nodeId']
        node = cdp.send('DOM.querySelector', {'nodeId': root, 'selector': 'h1'})['nodeId']
        fonts = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']
        cdp.detach()
        destination = page.locator('#menu-cards [data-admin-icon-action]').get_attribute('href')
        assert urlsplit(destination).path == f'/admin/{family}/menu'
        assert set(parse_qs(urlsplit(destination).query)) == {'week', 'day', 'meal', 'option'}
        page.locator('#menu-cards [data-admin-icon-action]').click()
        expect(page.locator('input[name="title"]')).to_have_value('Pouletbrust an Kräutersauce')
        assert not errors, errors
        evidence = {'family': family, 'javascript': javascript, 'viewports': VIEWPORTS,
                    'browser': browser.version, 'platform': platform.platform(),
                    'locale': 'de-CH', 'timezone': 'Europe/Zurich', 'dpr': 1,
                    'demo_today': app.config['DEMO_TODAY'], 'reduced_motion': 'reduce',
                    'fixture_sha256': hashlib.sha256(json.dumps({
                        'family': family, 'week_start': WEEK.isoformat(), 'weeks': 26,
                        'photo': {**_photo_payload(profile), 'title': 'Pouletbrust an Kräutersauce'},
                        'reviewed': {**_payload(staff=profile == 'staff_guest'), 'title': 'Tomatensuppe'},
                        'long_text': payload, 'dense': _payload(staff=profile == 'staff_guest'),
                        'dense_titles': [f'Gemüsemenü {offset}' for offset in range(3, 26)],
                    }, sort_keys=True).encode()).hexdigest(),
                    'screenshots': sorted(path.name for path in tmp_path.glob('*.png')),
                    'platform_fonts': fonts,
                    'contrast_failures': contrast_failures,
                    'font': page.locator('h1').evaluate('el => getComputedStyle(el).fontFamily')}
        (tmp_path / 'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        assert not contrast_failures, contrast_failures


@pytest.mark.parametrize('family,profile', FAMILIES)
@pytest.mark.parametrize('javascript', (True, False))
def test_reference_access_and_error_responses_do_not_write(
    live_branding, database_engine, browser, family, profile, javascript, monkeypatch, tmp_path,  # noqa: F811
):
    origin, app, client, _, _ = live_branding
    _save(database_engine, _scope(client, database_engine, profile), title='Geschütztes Menü')
    before = _versions(database_engine)
    route = f'/admin/{family}/menues'
    with _context(browser, origin, client, javascript) as context:
        page = context.new_page()
        for width, height in ((1440, 900), (390, 844)):
            page.set_viewport_size({'width': width, 'height': height})
            _goto(page, route + '?page=0&q=ungültig', 400)
            _capture(page, tmp_path, f'invalid-400-{width}')
            # Every shipped role has draft.read. Simulate its absence at the real guard.
            with monkeypatch.context() as denied:
                denied.setattr('cafeteria.roles.capabilities', lambda: set())
                _goto(page, route, 403)
                assert 'Geschütztes Menü' not in page.locator('body').inner_text()
                _capture(page, tmp_path, f'capability-denied-403-{width}')
        with database_engine.begin() as connection:
            connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        for width, height in ((1440, 900), (390, 844)):
            page.set_viewport_size({'width': width, 'height': height})
            _goto(page, route, 503)
            _capture(page, tmp_path, f'unavailable-503-{width}')
        assert _versions(database_engine) == before
    denied, _ = _login(app, database_engine, [])
    with _context(browser, origin, denied, javascript) as context:
        page = context.new_page()
        for width, height in ((1440, 900), (390, 844)):
            page.set_viewport_size({'width': width, 'height': height})
            _goto(page, route, 401)
            assert 'Geschütztes Menü' not in page.locator('body').inner_text()
            _capture(page, tmp_path, f'no-role-401-{width}')
    assert _versions(database_engine) == before


@pytest.mark.parametrize('javascript', (True, False))
def test_reference_roles_and_persisted_image_option(
    live_branding, database_engine, browser, javascript, tmp_path,  # noqa: F811
):
    origin, app, admin, actor, authz = live_branding
    for _, profile in FAMILIES:
        _save(database_engine, _scope(admin, database_engine, profile),
              title='Pouletbrust an Kräutersauce', payload=_photo_payload(profile))
    with _context(browser, origin, admin, javascript) as context:
        page = context.new_page()
        for family, _ in FAMILIES:
            _goto(page, f'/admin/{family}/menues')
            expect(page.locator('.menu-photo')).to_have_count(1)
    set_admin_display(database_engine, actor, authz,
                      {**DEFAULT_ADMIN_DISPLAY, 'admin_menu_images': 'hide'})
    before = _versions(database_engine)
    for role in ('Cafeteria.Admin', 'Cafeteria.Editor', 'Cafeteria.Publisher'):
        client, _ = _login(app, database_engine, [role])
        with _context(browser, origin, client, javascript) as context:
            page = context.new_page()
            for family, _ in FAMILIES:
                for width, height in ((1440, 900), (390, 844)):
                    page.set_viewport_size({'width': width, 'height': height})
                    _goto(page, f'/admin/{family}/menues')
                    expect(page.locator('main')).to_have_attribute('data-menu-images', 'hide')
                    expect(page.locator('.menu-photo')).to_have_count(0)
                    expect(page.locator('[data-menu-id]')).to_have_count(1)
                    _capture(page, tmp_path, f'{role}-{family}-images-hidden-{width}')
    assert _versions(database_engine) == before
