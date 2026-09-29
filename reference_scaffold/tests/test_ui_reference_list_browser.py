"""MP-UI-REF-LIST: real HTTP, scoped PostgreSQL data and proposed Chromium captures."""
from __future__ import annotations

import base64
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


def _measure(page: Page, count: int, contrast_failures: list, view: str) -> None:
    expect(page.locator('h1')).to_have_count(1)
    expect(page.locator('.admin-page-header h1')).to_have_text('Menüs')
    expect(page.locator('.page-header-subtitle')).to_contain_text('Gespeicherte Menüs')
    expect(page.locator('.admin-page-header .btn')).to_have_count(1)
    expect(page.locator('.admin-page-header .btn-primary')).to_have_accessible_name('Wochenplan')
    expect(page.locator('.admin-page-header .btn-primary')).to_have_text('')
    expect(page.locator('main')).to_have_attribute('data-layout', 'standard')
    record_selector = '[data-menu-id]' if view == 'cards' else '[data-menu-list-id]'
    expect(page.locator(record_selector)).to_have_count(count)
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
    for link in page.locator('[data-admin-icon-action]:visible, #menu-list [data-semantic="actions.edit"]:visible, #menu-cards [data-semantic="actions.edit"]:visible').all():
        semantic = link.get_attribute('data-semantic') == 'actions.edit'
        assert link.inner_text() == ('' if semantic else 'Bearbeiten')
        assert 'bearbeiten' in link.get_attribute('aria-label').lower()
        box = link.bounding_box()
        assert box is not None and box['height'] >= (36 if semantic else 48)
    geometry = page.locator('[data-menu-id]:visible').evaluate_all('''cards => cards.map(el => {
        const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return {width: r.width, height: r.height, top: r.top, radius: s.borderRadius, shadow: s.boxShadow,
                scroll: [el.scrollWidth, el.clientWidth, el.scrollHeight, el.clientHeight],
                overflowing: [...el.querySelectorAll('*')].filter(child =>
                    child.getClientRects().length && child.scrollWidth > child.clientWidth + 1
                ).map(child => [child.tagName, child.className, child.scrollWidth, child.clientWidth]),
                overflow: el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1};
    })''')
    if geometry:
        assert max(card['width'] for card in geometry) - min(card['width'] for card in geometry) <= 1
        for card in geometry:
            same_row = [other['height'] for other in geometry if abs(other['top'] - card['top']) <= 1]
            assert max(same_row) - min(same_row) <= 1
        assert all(card['radius'] == '12px' and card['shadow'] != 'none'
                   and not card['overflow'] for card in geometry), json.dumps(geometry)
    for heading in page.locator('.dishboard-menu-table thead th:visible').all():
        assert heading.evaluate('el => parseFloat(getComputedStyle(el).fontSize)') >= 12
    table = page.locator('.dishboard-menu-table')
    primary = table.locator('th[scope="row"]:visible, .admin-list-primary:visible')
    expect(primary).to_have_count(2 * table.locator('[data-menu-list-id]:visible').count())
    secondary = table.locator(
        'td[data-label="Tag"]:visible, td[data-label="Tag"] time:visible, '
        'td[data-label="Mahlzeit / Zuweisung"]:visible, td.admin-table-status:visible, '
        '[data-menu-list-id] .admin-list-secondary:visible, '
        '[data-menu-list-id] .text-secondary:visible',
    )
    for role, elements, size, weight in (
        ('primary', primary, 14, '600'), ('secondary', secondary, 13, '400'),
    ):
        for element in elements.all():
            typography = element.evaluate('''el => {
                const style = getComputedStyle(el);
                return {size: parseFloat(style.fontSize), weight: style.fontWeight};
            }''')
            assert typography == {'size': size, 'weight': weight}, (role, typography)
    assert page.locator('[data-menu-id]:visible :is(h2, p, li)').evaluate_all('''els => els.every(el => {
        const s = getComputedStyle(el);
        return s.webkitLineClamp === 'none' && el.scrollHeight <= el.clientHeight + 1 &&
            el.scrollWidth <= el.clientWidth + 1;
    })''')


def _native_reference_zoom(chromium, origin, client, javascript, route, directory,
                           contrast_failures, errors) -> None:
    with chromium.browser_type.launch_persistent_context(
        str(directory / 'native-zoom-profile'), channel='chromium', headless=True,
        no_viewport=True, base_url=origin, locale='de-CH', timezone_id='Europe/Zurich',
        java_script_enabled=javascript, reduced_motion='reduce',
        args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
    ) as context:
        page = context.pages[0]
        page.goto('chrome://settings/appearance')
        page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
        assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
        context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value,
                             'url': origin}])
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('requestfailed', lambda request: errors.append(request.failure))
        _goto(page, route + '?q=Langtext')
        cdp = context.new_cdp_session(page)
        try:
            metrics = cdp.send('Page.getLayoutMetrics')
            geometry_script = '''() => ({url: location.href, innerWidth, innerHeight,
                outerWidth, outerHeight, devicePixelRatio, scrollX, scrollY,
                scrollWidth: document.documentElement.scrollWidth,
                rootZoom: getComputedStyle(document.documentElement).zoom,
                bodyZoom: getComputedStyle(document.body).zoom,
                rootTransform: getComputedStyle(document.documentElement).transform,
                bodyTransform: getComputedStyle(document.body).transform})'''
            geometry = page.evaluate(geometry_script)
            png = base64.b64decode(cdp.send('Page.captureScreenshot', {
                'format': 'png', 'captureBeyondViewport': False,
            })['data'], validate=True)
            (directory / 'zoom200-1440-viewport.png').write_bytes(png)
            image_size = [int.from_bytes(png[16:20], 'big'), int.from_bytes(png[20:24], 'big')]
            after_capture = page.evaluate(geometry_script)
            proof = {'cdp': metrics, 'geometry': geometry, 'after_capture': after_capture,
                     'viewport_image_size': image_size, 'requested_window': [1440, 900],
                     'javascript': javascript, 'captureBeyondViewport': False}
            (directory / 'zoom200-1440.json').write_text(json.dumps(proof, indent=2))
            assert urlsplit(geometry['url']).path == route
            assert parse_qs(urlsplit(geometry['url']).query) == {'q': ['Langtext']}
            assert metrics['cssVisualViewport']['zoom'] == 2, proof
            assert [geometry['innerWidth'], geometry['outerWidth'], geometry['devicePixelRatio']] == [720, 1440, 2], proof
            assert geometry['rootZoom'] == geometry['bodyZoom'] == '1', proof
            assert geometry['rootTransform'] == geometry['bodyTransform'] == 'none', proof
            assert geometry == after_capture, proof
            assert abs(image_size[0] - geometry['innerWidth'] * geometry['devicePixelRatio']) <= 2, proof
            assert abs(image_size[1] - geometry['innerHeight'] * geometry['devicePixelRatio']) <= 2, proof
            _measure(page, 1, contrast_failures, 'list')
            _capture(page, directory, 'zoom200-1440')
        finally:
            cdp.detach()


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
            _measure(page, count, contrast_failures, view)
            _capture(page, directory, f'{state}-{view}-{width}x{height}')


def _keyboard(page: Page, javascript: bool) -> None:
    page.locator('main').focus()
    page.keyboard.press('Tab')
    expect(page.locator('main .btn-primary')).to_be_focused()
    expect(page.locator('main .btn-primary')).to_have_accessible_name('Wochenplan')
    expect(page.locator('main .btn-primary')).to_have_text('')
    expect(page.locator('.admin-area-tabs')).to_have_count(0)
    page.keyboard.press('Tab')
    expect(page.locator('details.admin-hint')).to_have_count(0)
    expect(page.locator('#menu-query-search')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('button', name='Suchen', exact=True)).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('navigation', name='Profil').get_by_role('link').first).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('navigation', name='Profil').get_by_role('link').last).to_be_focused()
    page.keyboard.press('Tab')
    if javascript:
        cards = page.get_by_role('tab', name='Karten', exact=True)
        listing = page.get_by_role('tab', name='Liste', exact=True)
        expect(listing).to_be_focused()
        expect(listing).to_have_attribute('aria-selected', 'true')
        expect(cards).to_have_attribute('tabindex', '-1')
        page.keyboard.press('ArrowRight')
        expect(cards).to_be_focused()
        expect(cards).to_have_attribute('aria-selected', 'true')
        page.keyboard.press('ArrowLeft')
        expect(listing).to_be_focused()
        expect(listing).to_have_attribute('aria-selected', 'true')
        page.keyboard.press('End')
        expect(cards).to_be_focused()
        page.keyboard.press('Home')
        expect(listing).to_be_focused()
        page.keyboard.press('Tab')
        expect(page.locator('#menu-list')).to_be_focused()
    else:
        listing = page.get_by_role('navigation', name='Menüansicht ohne JavaScript').get_by_role(
            'link', name='Liste', exact=True,
        )
        expect(listing).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('#menu-list')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('region', name='Menüliste', exact=True)).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('#menu-list a.admin-list-primary')).to_have_count(0)
    action = page.locator('#menu-list [data-semantic="actions.edit"]').first
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
        expect(page.locator('#menu-list')).to_be_visible()
        if javascript:
            expect(page.get_by_role('tab', name='Liste', exact=True)).to_have_attribute(
                'aria-selected', 'true',
            )
            expect(page.locator('#menu-cards')).to_be_hidden()
        else:
            expect(page.get_by_role('navigation', name='Menüansicht ohne JavaScript').get_by_role(
                'link', name='Liste', exact=True,
            )).to_have_attribute('href', '#menu-list')
        expect(page.locator('[data-empty-kind="none"]')).to_have_count(2)
        expect(page.get_by_role('navigation', name='Ergebnisseiten')).to_have_count(0)
        _views(page, javascript, tmp_path, 'empty', 0, contrast_failures)
        _save(database_engine, scope, title='Pouletbrust an Kräutersauce', payload=_photo_payload(profile))
        reviewed_payload = _payload(staff=profile == 'staff_guest')
        reviewed_payload['allergens'] = [{'code': 'GLUTEN', 'presence': 'contains'}]
        _save(database_engine, scope, week=WEEK + timedelta(weeks=1), title='Tomatensuppe', payload=reviewed_payload)
        with database_engine.begin() as connection:
            connection.execute(text("UPDATE cafeteria.menu_items SET allergen_review_status='checked'"))
            row = connection.execute(text("SELECT id,row_version FROM cafeteria.menu_items WHERE title='Tomatensuppe'")).one()
        review_component(database_engine, scope, row.id,
                         get_component_review_token(database_engine, scope, row.id), row.row_version)
        before = _versions(database_engine)
        _goto(page, route)
        _keyboard(page, javascript)
        expect(page.locator('#menu-cards [data-status="success"]')).to_have_count(1)
        expect(page.locator('#menu-cards [data-review="open"] [data-status="warning"]')).to_have_count(1)
        expect(page.locator('#menu-cards [data-review="open"]')).to_contain_text('Allergenangaben nicht erfasst')
        _views(page, javascript, tmp_path, 'normal', 2, contrast_failures)
        assert _versions(database_engine) == before
        page.locator('#menu-query-search').fill('KeinTreffer')
        page.get_by_role('button', name='Suchen', exact=True).click()
        expect(page.locator('#menu-query-search')).to_have_value('KeinTreffer')
        expect(page.locator('[data-empty-kind="no_match"]')).to_have_count(2)
        _views(page, javascript, tmp_path, 'no-match', 0, contrast_failures)
        page.get_by_role('search').get_by_role('link', name='Zurücksetzen', exact=True).click()
        expect(page.locator('#menu-query-search')).to_have_value('')
        payload = _payload(staff=profile == 'staff_guest')
        payload.update(description='Saisonales Gemüse schonend zubereiten. ' * 8, note=LONG_NOTE,
                       assignments=[{'component_public_id': None, 'component_text': 'Gemüse' * 30}])
        _save(database_engine, scope, week=WEEK + timedelta(weeks=2), title=LONG_TITLE, payload=payload)
        _goto(page, route)
        long_card = page.locator('#menu-cards [data-menu-id]', has_text=LONG_TITLE)
        expect(long_card.locator('.menu-note-details .shared-note')).to_contain_text(
            LONG_NOTE.strip()
        )
        if javascript:
            page.get_by_role('tab', name='Liste', exact=True).click()
        else:
            page.get_by_role('navigation', name='Menüansicht ohne JavaScript').get_by_role(
                'link', name='Liste', exact=True,
            ).click()
        note = page.locator('#menu-list details.menu-note-details').filter(has_text='Wichtiger Zubereitungshinweis')
        expect(note).to_have_count(1)
        note.locator('summary').focus()
        expect(note.locator('summary')).to_be_focused()
        page.keyboard.press('Enter')
        expect(note).to_have_attribute('open', '')
        page.keyboard.press('Enter')
        expect(note).not_to_have_attribute('open', '')
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
            expect(page.locator('#menu-list').get_by_role(
                'columnheader', name='Gespeicherter Prüfstand', exact=True,
            )).to_be_visible()
            expect(page.locator('#menu-list .admin-table-status').get_by_text(
                'Allergenangaben nicht erfasst').first).to_be_visible()
            region = page.get_by_role('region', name='Menüliste', exact=True)
            region.focus()
            page.keyboard.press('Shift+Tab')
            page.keyboard.press('Tab')
            expect(region).to_be_focused()
            assert region.evaluate('el => getComputedStyle(el).outlineStyle') == 'solid'
            if width == 390:
                assert region.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
            _capture(page, tmp_path, f'keyboard-scroll-{width}')
        page.get_by_role('navigation', name='Ergebnisseiten').get_by_role('link', name='Weiter').click()
        expect(page.locator('[data-menu-list-id]')).to_have_count(2)
        expect(page.get_by_role('navigation', name='Ergebnisseiten').get_by_role('link', name='Weiter')).to_have_count(0)
        assert parse_qs(urlsplit(page.url).query) == {'page': ['2']}
        _views(page, javascript, tmp_path, 'last-page', 2, contrast_failures, ((1440, 900), (390, 844)))
        _goto(page, route + '?q=Gemüse')
        expect(page.locator('[data-menu-list-id]')).to_have_count(24)
        for link in page.get_by_role('navigation', name='Profil').get_by_role('link').all():
            assert parse_qs(urlsplit(link.get_attribute('href')).query) == {'q': ['Gemüse']}
        _goto(page, route + '?q=Langtext')
        expect(page.locator('[data-menu-list-id]')).to_have_count(1)
        # Narrow CSS viewports and actual browser zoom are separate contracts.
        for width, height in ((320, 844), (390, 844)):
            page.set_viewport_size({'width': width, 'height': height})
            _measure(page, 1, contrast_failures, 'list')
            _capture(page, tmp_path, f'long-text-reflow-{width}')
        _native_reference_zoom(browser, origin, client, javascript, route, tmp_path,
                               contrast_failures, errors)
        assert _versions(database_engine) == before
        _goto(page, route + '?q=Pouletbrust')
        if javascript:
            page.get_by_role('tab', name='Karten', exact=True).click()
        else:
            page.get_by_role('navigation', name='Menüansicht ohne JavaScript').get_by_role(
                'link', name='Karten', exact=True,
            ).click()
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
        destination = page.locator('#menu-cards [data-semantic="actions.edit"]').get_attribute('href')
        assert urlsplit(destination).path == f'/admin/{family}/menu'
        assert set(parse_qs(urlsplit(destination).query)) == {'week', 'day', 'meal', 'option'}
        page.locator('#menu-cards [data-semantic="actions.edit"]').click()
        expect(page.locator('input[name="title"]')).to_have_value('Pouletbrust an Kräutersauce')
        assert not errors, errors
        evidence = {'family': family, 'javascript': javascript, 'viewports': VIEWPORTS,
                    'long_text_reflow_viewports': ((320, 844), (390, 844)),
                    'native_zoom_evidence': 'zoom200-1440.json',
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
