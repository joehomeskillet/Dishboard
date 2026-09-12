"""Real native upload/revision/scaling flows on local PostgreSQL at all requested widths."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from test_recipe_revision_routes import (  # noqa: F401
    a3, app_engine, b3, pg16, installed_pg16, seeded_pg16, png, edit, snapshot, complete_a3,
)
from test_rendered_ui import browser  # noqa: F401


@pytest.fixture
def recipe_server(a3):  # noqa: F811
    app, _, client, _, _ = a3
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    try:
        yield f'http://127.0.0.1:{server.server_port}', cookie
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def geometry(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('main style, main [style]').count() == 0
    for element in page.locator('main :is(.btn, .form-control)').all():
        if element.is_visible():
            box = element.bounding_box()
            assert box is not None and box['height'] >= 48 and box['width'] >= 48
            element.focus()
            expect(element).to_be_focused()
    for svg in page.locator('main svg use').all():
        assert 'tabler-' in svg.get_attribute('href')


def capture(page, tmp_path, name):
    root = Path(os.environ.get('RECIPE_A3_EVIDENCE_DIR', str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    destination = root / (name + '.png')
    page.screenshot(path=str(destination), full_page=True)
    destination.chmod(0o600)


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_native_upload_freeze_history_scaling_and_assets(a3, recipe_server, browser, width, javascript, tmp_path):  # noqa: F811
    complete_a3(a3)
    _, owner, _, _, public_id = a3
    base, cookie = recipe_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, posts, responses = [], [], {}
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request.method) if request.method == 'POST' else None)
        page.on('response', lambda response: responses.setdefault(urlsplit(response.url).path, []).append(response.status))
        path = f'/admin/rezepte/{public_id}'
        assert page.goto(base + path + '/bilder').status == 200
        expect(page.get_by_role('heading', name='Rezeptbilder', exact=True)).to_be_visible()
        before = snapshot(owner)
        page.get_by_role('button', name='Bild hochladen', exact=True).click()
        assert posts == [] and snapshot(owner) == before
        expect(page.locator('#image-file')).to_be_focused()
        page.get_by_label('Bilddatei', exact=True).set_input_files({'name': 'recipe.png', 'mimeType': 'image/png', 'buffer': png()})
        page.get_by_label('Bildunterschrift · optional', exact=True).fill('Bild aus dem Browser')
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Bild hochladen', exact=True).click()
        assert outcome.value.status == 303 and len(posts) == 1
        expect(page.locator('td[data-label="Bildunterschrift"]')).to_have_text('Bild aus dem Browser')
        expect(page.locator('td[data-label="Bildunterschrift"]')).to_be_visible()
        expect(page.locator('main img')).to_have_count(1)
        page.locator('main img').scroll_into_view_if_needed()
        deadline = time.monotonic() + 15
        while not page.locator('main img').evaluate('el => el.complete && el.naturalWidth === 24'):
            assert time.monotonic() < deadline, 'Uploaded image did not decode to width24'
            page.wait_for_timeout(50)
        assert page.locator('main img').evaluate('el => el.complete && el.naturalWidth === 24')
        geometry(page)
        capture(page, tmp_path, f'images-{width}-js{javascript}')
        page.goto(base + path + '/revisionen')
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Gespeicherten Stand festhalten', exact=True).click()
        assert outcome.value.status == 303 and len(posts) == 2
        expect(page.get_by_role('heading', name='Gespeicherter Stand 1', exact=True)).to_be_visible()
        revision_path = urlsplit(page.url).path
        before = snapshot(owner)
        page.get_by_label('Zielmenge · PORTION', exact=True).fill('6')
        page.get_by_role('button', name='Mengen berechnen', exact=True).click()
        expect(page.locator('td').get_by_text('0.1875', exact=True)).to_be_visible()
        assert len(posts) == 2 and snapshot(owner) == before
        page.locator('details.card > summary').filter(has_text='Technische Details').click()
        expect(page.get_by_text('quantity_places', exact=True)).to_be_visible()
        geometry(page)
        capture(page, tmp_path, f'revision-{width}-js{javascript}')
        page.goto(base + path + '/skalierung')
        page.get_by_label('Zielmenge · PORTION', exact=True).fill('NaN')
        with page.expect_response(lambda response: '/skalierung?' in response.url) as invalid:
            page.get_by_role('button', name='Mengen berechnen', exact=True).click()
        assert invalid.value.status == 400
        expect(page.get_by_label('Zielmenge · PORTION', exact=True)).to_have_value('NaN')
        expect(page.get_by_label('Zielmenge · PORTION', exact=True)).to_be_focused()
        assert snapshot(owner) == before
        assert page.goto(base + revision_path).status == 200
        assets = page.locator('link[rel="stylesheet"],script[src]').evaluate_all('els => els.map(el => new URL(el.href || el.src).pathname)')
        assert all(any(code in (200, 304) for code in responses.get(asset, []))
                   for asset in assets if javascript or asset.endswith('.css'))
        assert any('tabler.min.css' in asset for asset in assets) and not any(asset.endswith('/app.css') for asset in assets)
        assert errors == []


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_upload_stale_cas_retains_original_copyable_text_and_focus(a3, recipe_server, browser, width, javascript, tmp_path):  # noqa: F811
    _, owner, _, _, public_id = a3
    base, cookie = recipe_server
    with browser.new_context(viewport={'width': width, 'height': 1100}, java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + f'/admin/rezepte/{public_id}/bilder')
        original = page.locator('input[name="_form_context"]').input_value()
        version = page.locator('input[name="row_version"]').input_value()
        page.get_by_label('Bildunterschrift · optional', exact=True).fill('Meine erhaltene Bildunterschrift')
        page.get_by_label('Bilddatei', exact=True).set_input_files({'name': 'recipe.png', 'mimeType': 'image/png', 'buffer': png()})
        edit(a3, title='Anderer Tab')
        before = snapshot(owner)
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Bild hochladen', exact=True).click()
        assert outcome.value.status == 409 and snapshot(owner) == before
        expect(page.locator('#recipe-error')).to_be_focused()
        expect(page.get_by_label('Bildunterschrift', exact=True)).to_have_value('Meine erhaltene Bildunterschrift')
        assert page.locator('input[name="_form_context"]').input_value() == original
        assert page.locator('input[name="row_version"]').input_value() == version
        field = page.get_by_label('Bildunterschrift', exact=True)
        field.focus()
        page.keyboard.press('Control+A')
        assert field.evaluate('el => el.value.slice(el.selectionStart, el.selectionEnd)') == 'Meine erhaltene Bildunterschrift'
        assert page.locator('button[type="submit"]').count() == 0
        geometry(page)
        capture(page, tmp_path, f'upload-conflict-{width}-js{javascript}')
