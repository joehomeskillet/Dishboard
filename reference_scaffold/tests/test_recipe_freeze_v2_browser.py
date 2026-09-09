"""Real preview, frozen dependency conflict and deliberate native reload at both widths."""
import base64
import json
import struct
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria import recipe_store as store, master_data_store as masters
from test_master_data_db import signed_in, STORAGE_PUBLIC_ID
from test_recipe_store_db import target, payload, line
from test_recipe_freeze_v2_db import full_state
from test_recipe_freeze_v2_routes import ready, revision_path, rename_food  # noqa: F401
from test_recipe_revision_routes import a3, b3, app_engine, pg16, installed_pg16, seeded_pg16  # noqa: F401
from test_recipe_images_browser import recipe_server  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


@pytest.fixture
def prepared_preview(ready):  # noqa: F811
    app, _, _, actor, public_id = ready
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        parent = store.get_recipe(engine, public_id)
        child = store.create_recipe(engine, actor, payload(title='Hausgemachte Gemüsebasis', servings='1000',
            servings_unit_code='G', ingredients=[line('Salz', food_public_id=parent.payload['ingredients'][1]['food_public_id'])]),
            expected_location_id=location)
        preview = store.get_dependency_preview(engine, target(child), expected_location_id=location)
        revision = store.freeze_revision(engine, actor, target(child), expected_location_id=location,
                                         expected_dependency_hash=preview.dependency_hash_sha256)
        food = masters.get_food(engine, parent.payload['ingredients'][0]['food_public_id'])
        masters.update_food(engine, actor, target(food), {'name': 'Gemüsebasis', 'base_unit_code': 'KG',
            'storage_location_public_ids': [STORAGE_PUBLIC_ID],
            'prepared_recipe_revision_public_id': revision.public_id,
            'prepared_recipe_content_hash_sha256': revision.content_hash_sha256}, original_location=location)
    return ready


def native_full_page_capture(page, destination):
    geometry = '''() => ({innerWidth,innerHeight,outerWidth,outerHeight,devicePixelRatio,scrollX,scrollY,
        documentWidth:document.documentElement.scrollWidth,
        documentHeight:document.documentElement.scrollHeight,
        rectangles:[...document.querySelectorAll('main,main .btn,main input,main select')].map(
            el => ({tag:el.tagName,rect:el.getBoundingClientRect().toJSON()}))})'''
    before = page.evaluate(geometry)
    cdp = page.context.new_cdp_session(page)
    try:
        metrics = cdp.send('Page.getLayoutMetrics')
        # Native browser zoom changes the CDP capture coordinate space. DOM CSS
        # dimensions would clip the enlarged image; use measured layout dimensions.
        arguments = {'format': 'png', 'captureBeyondViewport': True,
                     'clip': dict(metrics['contentSize'], scale=1)}
        png = base64.b64decode(cdp.send('Page.captureScreenshot', arguments)['data'], validate=True)
    finally:
        cdp.detach()
    after = page.evaluate(geometry)
    destination.write_bytes(png)
    assert png[:8] == b'\x89PNG\r\n\x1a\n' and png[12:16] == b'IHDR'
    width, height = struct.unpack('>II', png[16:24])
    capture = {'cdp_layout_metrics': metrics, 'capture_arguments': arguments,
               'png_dimensions': {'width': width, 'height': height},
               'layout_before': before, 'layout_after': after}
    destination.with_suffix('.capture.json').write_text(json.dumps(capture, indent=2))
    assert before == after
    assert width == metrics['contentSize']['width'] and height == metrics['contentSize']['height']
    return capture


def proof(page, destination, *, expected_status, requests, native_capture=False):
    page.evaluate('document.fonts.ready')
    assert page.evaluate('document.fonts.status') == 'loaded'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('main style,main [style]').count() == 0
    for control in page.locator('main .btn').all():
        if control.is_visible():
            box = control.bounding_box()
            assert box and box['height'] >= 48 and box['width'] >= 48
    capture = None
    if native_capture:
        capture = native_full_page_capture(page, destination)
    else:
        page.screenshot(path=str(destination), full_page=True)
    info = {'route': urlsplit(page.url).path, 'viewport': page.viewport_size,
            'measured_viewport': page.evaluate('({innerWidth,innerHeight,outerWidth,outerHeight})'),
            'device_pixel_ratio': page.evaluate('devicePixelRatio'), 'font_status': 'loaded',
            'lang': page.locator('html').get_attribute('lang'), 'timezone': page.evaluate(
                'Intl.DateTimeFormat().resolvedOptions().timeZone'),
            'status': expected_status, 'request_methods': requests}
    if capture is not None:
        info['native_capture'] = capture
    destination.with_suffix('.json').write_text(json.dumps(info, indent=2))


@pytest.mark.parametrize('width,height,javascript', [(1440, 900, True), (390, 844, False),
    (1024, 768, True), (768, 1024, True), (1920, 1080, True)])
def test_preview_and_list_are_native_readonly_with_exact_prepared_selection(prepared_preview, recipe_server, browser,  # noqa: F811
                                                                          width, height, javascript, tmp_path):
    _, owner, _, _, public_id = prepared_preview
    base, cookie = recipe_server
    before = full_state(owner)
    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=javascript,
                             locale='de-CH', timezone_id='Europe/Zurich') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        methods, errors = [], []
        page.on('request', lambda request: methods.append(request.method))
        page.on('pageerror', lambda error: errors.append(str(error)))
        if width in (1440, 390):
            assert page.goto(base + '/admin/rezepte').status == 200
            proof(page, tmp_path / f'freeze-list-{width}.png', expected_status=200, requests=methods.copy())
            link = page.locator(f'main a[href="/admin/rezepte/{public_id}/revisionen"]')
            link.focus()
            expect(link).to_be_focused()
            with page.expect_navigation(wait_until='load'):
                page.keyboard.press('Enter')
        else:
            assert page.goto(base + revision_path(prepared_preview)).status == 200
        expect(page.get_by_role('heading', name='Zutatenstand prüfen', exact=True)).to_be_visible()
        child = page.get_by_role('link', name='Hausgemachte Gemüsebasis · gespeicherter Stand', exact=True)
        expect(child.locator('..')).to_contain_text('Originalausbeute: 1000 G')
        assert '/revisionen/' in child.get_attribute('href')
        expect(page.get_by_role('button', name='Revision festschreiben', exact=True)).to_be_visible()
        proof(page, tmp_path / f'freeze-preview-{width}.png', expected_status=200, requests=methods.copy())
        detail = page.get_by_text('Prüfnachweis anzeigen', exact=True)
        detail.focus()
        expect(detail).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('details[open]')).to_have_count(1)
        page.keyboard.press('Enter')
        expect(page.locator('details[open]')).to_have_count(0)
        assert all(method == 'GET' for method in methods) and errors == []
        assert full_state(owner) == before


@pytest.mark.parametrize('width,javascript', [(1440, True), (390, False)])
def test_native_freeze_conflict_keeps_original_until_explicit_reload(ready, recipe_server, browser, width, javascript, tmp_path):  # noqa: F811
    _, owner, _, _, _ = ready
    base, cookie = recipe_server
    with browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             java_script_enabled=javascript, locale='de-CH', timezone_id='Europe/Zurich') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        methods = []
        page.on('request', lambda request: methods.append(request.method))
        assert page.goto(base + revision_path(ready)).status == 200
        original = page.locator('input[name="_form_context"]').input_value()
        rename_food(ready)
        before = full_state(owner)
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Revision festschreiben', exact=True).click()
        assert outcome.value.status == 409
        expect(page.get_by_role('heading', name='Rezeptaktion nicht möglich', exact=True)).to_be_visible()
        assert page.locator('input[name="_form_context"]').input_value() == original
        assert page.locator('button[type="submit"]').count() == 0 and full_state(owner) == before
        proof(page, tmp_path / f'freeze-conflict-{width}.png', expected_status=409, requests=methods.copy())
        page.get_by_role('link', name='Aktuellen Stand bewusst neu laden', exact=True).click()
        link = page.locator(f'main a[href="{revision_path(ready)}"]')
        link.focus()
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        assert page.locator('input[name="_form_context"]').input_value() != original
        assert full_state(owner) == before
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Revision festschreiben', exact=True).click()
        assert outcome.value.status == 303
        expect(page.get_by_role('heading', name='Unveränderlicher Stand', exact=True)).to_be_visible()
        assert '/revisionen/' in urlsplit(page.url).path


@pytest.mark.parametrize('width,javascript', [(1440, True), (390, False)])
def test_incomplete_preview_is_visible_and_keyboard_editable(a3, recipe_server, browser, width, javascript, tmp_path):  # noqa: F811
    _, owner, _, _, _ = a3
    base, cookie = recipe_server
    before = full_state(owner)
    with browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             java_script_enabled=javascript, locale='de-CH', timezone_id='Europe/Zurich') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        methods = []
        page.on('request', lambda request: methods.append(request.method))
        assert page.goto(base + revision_path(a3)).status == 400
        expect(page.get_by_role('alert')).to_contain_text('noch unvollständig')
        assert page.locator('input[name="_form_context"]').count() == 0
        proof(page, tmp_path / f'freeze-incomplete-{width}.png', expected_status=400, requests=methods.copy())
        page.get_by_role('link', name='Rezept ergänzen', exact=True).focus()
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        expect(page.locator('#recipe-editor')).to_be_visible()
        assert all(method == 'GET' for method in methods)
        assert full_state(owner) == before


def test_both_routes_reflow_at_native_chromium_200_percent_zoom(prepared_preview, recipe_server, browser, tmp_path):  # noqa: F811
    _, owner, _, _, public_id = prepared_preview
    base, cookie = recipe_server
    before = full_state(owner)
    # Chromium's actual browser zoom, isolated from the shared browser fixture.
    # Temporary profile is removed after close; cookies never become evidence.
    with TemporaryDirectory(prefix='native-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(profile, channel='chromium', headless=True,
                no_viewport=True, locale='de-CH', timezone_id='Europe/Zurich',
                args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900']) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            methods = []
            page.on('request', lambda request: methods.append(request.method))
            assert page.goto(base + '/admin/rezepte').status == 200
            assert page.evaluate('devicePixelRatio') == 2
            assert page.evaluate('innerWidth') == 720
            proof(page, tmp_path / 'freeze-list-native-200-percent.png', expected_status=200,
                  requests=methods.copy(), native_capture=True)
            link = page.locator(f'main a[href="/admin/rezepte/{public_id}/revisionen"]')
            link.focus()
            with page.expect_navigation(wait_until='load'):
                page.keyboard.press('Enter')
            expect(page.get_by_role('heading', name='Zutatenstand prüfen', exact=True)).to_be_visible()
            proof(page, tmp_path / 'freeze-preview-native-200-percent.png', expected_status=200,
                  requests=methods.copy(), native_capture=True)
            assert all(method == 'GET' for method in methods)
            assert full_state(owner) == before
