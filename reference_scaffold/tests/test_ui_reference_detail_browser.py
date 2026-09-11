"""Browser and contract verification for MP-UI-REF-DETAIL (admin.recipe_revision)."""
from __future__ import annotations

from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from cafeteria import recipe_store as store, roles
from test_master_data_db import make_actor, signed_in
from test_recipe_revision_routes import (  # noqa: F401
    a3, app_engine, b3, edit, installed_pg16, pg16, png, seeded_pg16, snapshot,
)
from test_recipe_store_db import line, mutable, payload, target
from test_rendered_ui import browser  # noqa: F401

VIEWPORTS = [
    (1440, 900),
    (1024, 768),
    (768, 1024),
    (390, 844),
    (1920, 1080),
]

ZOOM_VIEWPORTS = [(1440, 900), (390, 844)]
FOCUS_COLOR = 'rgb(163, 22, 77)'


@pytest.fixture
def detail_revisions(a3):  # noqa: F811
    app, owner, client, actor, recipe_id = a3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        loc = store.get_location(engine)

        # 1. Normal recipe revision with image, step duration and step image
        row_norm = store.get_recipe(engine, recipe_id)
        row_norm = store.add_recipe_image(engine, actor, target(row_norm), data=png(), content_type='image/png',
                                          caption='Normales Rezeptbild', expected_location_id=loc)
        data_norm = mutable(store.get_recipe(engine, recipe_id).payload)
        digest = data_norm['images'][0]['sha256']
        data_norm['steps'][0]['image_sha256'] = digest
        data_norm['steps'][0]['duration_minutes'] = 25
        data_norm['description'] = 'Klassisches Menürezept mit Bild und Zubereitungsschritten.'
        row_norm = store.update_recipe(engine, actor, target(row_norm), data_norm, expected_location_id=loc)
        rev_normal = store.freeze_revision(engine, actor, target(row_norm), expected_location_id=loc)

        # 2. Recipe revision without images
        p_no_img = payload(
            title='Gemüsebouillon ohne Bilder',
            description='Leichte klare Brühe ohne beigefügte Bilddokumente.',
            ingredients=[
                line('Karotten', quantity='0.5', unit_code='KG'),
                line('Lauch', quantity='0.25', unit_code='KG'),
                line('Wasser', quantity='2.0', unit_code='L'),
            ],
            steps=[
                {'instruction': 'Gemüse waschen und klein schneiden.', 'duration_minutes': 10, 'image_sha256': None},
                {'instruction': 'In kochendem Wasser 45 Minuten sieden lassen.', 'duration_minutes': 45, 'image_sha256': None},
            ],
        )
        row_no_img = store.create_recipe(engine, actor, p_no_img, expected_location_id=loc)
        rev_no_img = store.freeze_revision(engine, actor, target(row_no_img), expected_location_id=loc)

        # 3. Long text recipe revision
        long_title = 'Traditioneller geschmorter Rindsbraten mit Wurzelgemüse und Rotweinsauce nach Landgasthof-Art'
        long_desc = 'Ausführliches Festtagsrezept mit detaillierten Angaben.\nStreng handwerkliche Zubereitung.\nMehrere Stunden Garzeit.'
        long_instruction = 'Das Fleisch gründlich trocken tupfen, rundherum kräftig würzen und im schweren Bräter von allen Seiten scharf anbraten bis eine Kruste entsteht.'
        p_long = payload(
            title=long_title,
            description=long_desc,
            ingredients=[
                line('Rindsschulter gut gelagert und pariert vom regionalen Metzger', quantity='1.8', unit_code='KG',
                     note='Zimmertemperatur annehmen lassen vor dem Anbraten'),
                line('Fein gewürfeltes Röstgemüse bestehend aus Sellerie, Karotten und Lauch', quantity='0.6', unit_code='KG',
                     note='Gleichmässig in 1 cm grosse Würfel schneiden'),
            ],
            steps=[
                {'instruction': long_instruction, 'duration_minutes': 120, 'image_sha256': None},
                {'instruction': 'Mit kräftigem Rotwein ablöschen und langsam einkochen lassen.', 'duration_minutes': 30, 'image_sha256': None},
            ],
        )
        row_long = store.create_recipe(engine, actor, p_long, expected_location_id=loc)
        rev_long = store.freeze_revision(engine, actor, target(row_long), expected_location_id=loc)

        # 4. Empty recipe revision without ingredients or preparation steps
        p_empty = payload(
            title='Leeres Rezept ohne Inhalt',
            description='Revision ohne Zutaten und Zubereitungsschritte.',
            ingredients=[],
            steps=[],
        )
        row_empty = store.create_recipe(engine, actor, p_empty, expected_location_id=loc)
        rev_empty = store.freeze_revision(engine, actor, target(row_empty), expected_location_id=loc)

    return {
        'normal': (row_norm.public_id, rev_normal.public_id, rev_normal.revision_number, rev_normal.content_hash_sha256),
        'no_images': (row_no_img.public_id, rev_no_img.public_id, rev_no_img.revision_number, rev_no_img.content_hash_sha256),
        'long_text': (row_long.public_id, rev_long.public_id, rev_long.revision_number, rev_long.content_hash_sha256),
        'empty': (row_empty.public_id, rev_empty.public_id, rev_empty.revision_number, rev_empty.content_hash_sha256),
    }


@pytest.fixture
def detail_server(a3):  # noqa: F811
    app, _, client, _, _ = a3
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    try:
        yield f'http://127.0.0.1:{server.server_port}', cookie, app
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def assert_geometry(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('main style, main [style]').count() == 0
    for element in page.locator('main :is(.btn, .form-control)').all():
        if element.is_visible():
            box = element.bounding_box()
            assert box is not None and box['height'] >= 48 and box['width'] >= 48
    for svg in page.locator('main svg use').all():
        assert 'tabler-' in svg.get_attribute('href')
    tables = page.locator('main table')
    if tables.count() > 0:
        table_fs = tables.first.evaluate('el => parseFloat(getComputedStyle(el).fontSize)')
        assert table_fs >= 14


def capture_screenshot(page, tmp_path: Path, name: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    destination = tmp_path / f'{name}.png'
    page.screenshot(path=str(destination), full_page=True)


def assert_zoom_geometry(page):
    page.evaluate('scrollTo(0, 0)')
    # CSS zoom can introduce a few subpixel rounding pixels on narrow viewports.
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 4')
    assert page.locator('main style, main [style]').count() == 0
    for element in page.locator('main :is(.btn, .form-control)').all():
        if element.is_visible():
            box = element.bounding_box()
            assert box is not None and box['height'] >= 44 and box['width'] >= 44


def assert_focus_ring(element):
    styles = element.evaluate('''el => {
        const style = getComputedStyle(el);
        return {
            outlineStyle: style.outlineStyle,
            outlineWidth: parseFloat(style.outlineWidth),
            outlineColor: style.outlineColor,
        };
    }''')
    assert styles['outlineStyle'] == 'solid'
    assert styles['outlineWidth'] >= 2
    assert styles['outlineColor'] == FOCUS_COLOR


@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_detail_reference_normal_all_viewports(detail_revisions, detail_server, browser, width, height, tmp_path):  # noqa: F811
    recipe_id, rev_id, rev_num, sha256 = detail_revisions['normal']
    base, cookie, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        response = page.goto(url)
        assert response.status == 200

        # Layout variant attribute
        expect(page.locator('main.admin-main')).to_have_attribute('data-layout', 'standard')

        # Breadcrumbs
        breadcrumbs = page.locator('nav[aria-label="Breadcrumb"] .breadcrumb-item')
        expect(breadcrumbs.first).to_contain_text('Rezepte')
        expect(breadcrumbs.nth(1)).to_be_visible()
        expect(breadcrumbs.last).to_contain_text('Revisionen')

        # H1 & Subtitle
        expect(page.locator('h1.page-title')).to_be_visible()
        expect(page.locator('.page-header-subtitle')).to_contain_text(f'Unveränderlicher Revisionsstand {rev_num}')
        expect(page.locator('.page-header-subtitle')).to_contain_text('Erstellt:')

        # Header Actions
        back_btn = page.get_by_role('link', name='Alle Revisionen')
        expect(back_btn).to_be_visible()
        expect(back_btn).to_have_attribute('href', f'/admin/rezepte/{recipe_id}/revisionen')

        pdf_btn = page.get_by_role('link', name='PDF öffnen')
        expect(pdf_btn).to_be_visible()
        assert f'/admin/rezepte/{recipe_id}/revisionen/{rev_id}/druck.pdf' in pdf_btn.get_attribute('href')

        # Status badge & Immutable card
        expect(page.get_by_role('heading', name='Unveränderlicher Stand')).to_be_visible()
        status_badge = page.locator('[data-status="archived"]')
        expect(status_badge).to_have_text('Unveränderlich')
        expect(page.get_by_text(sha256)).to_be_visible()
        expect(page.get_by_text(rev_id)).to_be_visible()

        # Scaling and Ingredients table
        table = page.locator('main table.card-table')
        expect(table).to_be_visible()
        table_fs = table.evaluate('el => parseFloat(getComputedStyle(el).fontSize)')
        assert table_fs >= 14

        # Preparation steps and images
        expect(page.get_by_role('heading', name='Zubereitung')).to_be_visible()
        step_img = page.locator('main ol img')
        if step_img.count() > 0:
            expect(step_img.first).to_have_attribute('width', '320')
            expect(step_img.first).to_have_attribute('height', '240')

        # Gallery images
        expect(page.get_by_role('heading', name='Bilder und Herkunft')).to_be_visible()
        gallery_img = page.locator('main figure img')
        expect(gallery_img.first).to_have_attribute('width', '480')
        expect(gallery_img.first).to_have_attribute('height', '360')

        # Snapshot details
        summary = page.locator('summary').filter(has_text='Vollständiger gespeicherter Revisionsstand')
        expect(summary).to_be_visible()
        summary.click()
        expect(page.locator('details[open]')).to_be_visible()

        # Geometry and accessibility checks
        assert_geometry(page)
        capture_screenshot(page, tmp_path, f'detail-normal-{width}x{height}')


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_detail_reference_no_images_state(detail_revisions, detail_server, browser, width, height, tmp_path):  # noqa: F811
    recipe_id, rev_id, rev_num, _ = detail_revisions['no_images']
    base, cookie, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(url).status == 200

        # Verify no images section
        expect(page.get_by_role('heading', name='Bilder und Herkunft')).to_have_count(0)
        expect(page.locator('main img')).to_have_count(0)

        # Core sections present
        expect(page.get_by_role('heading', name='Unveränderlicher Stand')).to_be_visible()
        expect(page.get_by_role('heading', name='Zutaten und Mengen')).to_be_visible()
        expect(page.get_by_role('heading', name='Zubereitung')).to_be_visible()

        assert_geometry(page)
        capture_screenshot(page, tmp_path, f'detail-no-images-{width}x{height}')


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_detail_reference_long_text_state(detail_revisions, detail_server, browser, width, height, tmp_path):  # noqa: F811
    recipe_id, rev_id, _, _ = detail_revisions['long_text']
    base, cookie, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(url).status == 200

        # Verify long texts are present and wrapped
        expect(page.locator('h1.page-title')).to_contain_text('Traditioneller geschmorter Rindsbraten')
        expect(page.locator('main')).to_contain_text('Zimmertemperatur annehmen lassen')
        expect(page.locator('main')).to_contain_text('Streng handwerkliche Zubereitung')

        assert_geometry(page)
        capture_screenshot(page, tmp_path, f'detail-longtext-{width}x{height}')


@pytest.mark.parametrize('width,height', ZOOM_VIEWPORTS)
def test_detail_reference_empty_state(detail_revisions, detail_server, browser, width, height, tmp_path):  # noqa: F811
    recipe_id, rev_id, rev_num, _ = detail_revisions['empty']
    base, cookie, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(url).status == 200

        expect(page.locator('h1.page-title')).to_contain_text('Leeres Rezept ohne Inhalt')
        expect(page.locator('.page-header-subtitle')).to_contain_text(f'Unveränderlicher Revisionsstand {rev_num}')
        expect(page.get_by_text('Keine Zutaten gespeichert.')).to_be_visible()
        expect(page.get_by_text('Keine Schritte gespeichert.')).to_be_visible()

        assert_geometry(page)
        capture_screenshot(page, tmp_path, f'detail-empty-{width}x{height}')


@pytest.mark.parametrize('width,height', ZOOM_VIEWPORTS)
def test_detail_reference_zoom_200_percent(detail_revisions, detail_server, browser, width, height, tmp_path):  # noqa: F811
    recipe_id, rev_id, rev_num, _ = detail_revisions['normal']
    base, cookie, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(url).status == 200

        page.evaluate("document.documentElement.style.zoom = '2'")

        expect(page.locator('h1.page-title')).to_be_visible()
        expect(page.locator('.page-header-subtitle')).to_contain_text(f'Unveränderlicher Revisionsstand {rev_num}')
        expect(page.get_by_role('link', name='Alle Revisionen')).to_be_visible()
        expect(page.get_by_role('link', name='PDF öffnen')).to_be_visible()
        expect(page.get_by_role('heading', name='Unveränderlicher Stand')).to_be_visible()

        assert_zoom_geometry(page)
        capture_screenshot(page, tmp_path, f'detail-zoom200-{width}x{height}')
        page.evaluate("document.documentElement.style.zoom = ''")


def test_detail_reference_scaling_and_pdf_query(detail_revisions, detail_server, browser, tmp_path):  # noqa: F811
    recipe_id, rev_id, _, _ = detail_revisions['normal']
    base, cookie, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': 1440, 'height': 900}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(url).status == 200

        # Perform scaling calculation
        yield_input = page.locator('#target-yield')
        expect(yield_input).to_be_visible()
        yield_input.fill('8')
        page.get_by_role('button', name='Mengen berechnen').click()
        page.wait_for_load_state('load')

        # Check scaled values and PDF query sync
        assert 'yield=8' in page.url
        pdf_btn = page.get_by_role('link', name='PDF öffnen')
        parsed = urlparse(pdf_btn.get_attribute('href'))
        assert parse_qs(parsed.query).get('yield') == ['8']

        # Invalid scaling input
        yield_input = page.locator('#target-yield')
        yield_input.fill('invalid-amount')
        page.get_by_role('button', name='Mengen berechnen').click()
        page.wait_for_load_state('load')
        expect(page.locator('#yield-error')).to_be_visible()

        capture_screenshot(page, tmp_path, 'detail-scaling-interaction')


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_detail_reference_no_js_and_keyboard(detail_revisions, detail_server, browser, width, height, tmp_path):  # noqa: F811
    recipe_id, rev_id, _, _ = detail_revisions['normal']
    base, cookie, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=False,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(url).status == 200

        # Keyboard tab through action links and form inputs
        back_btn = page.get_by_role('link', name='Alle Revisionen')
        back_btn.focus()
        expect(back_btn).to_be_focused()

        pdf_btn = page.get_by_role('link', name='PDF öffnen')
        pdf_btn.focus()
        expect(pdf_btn).to_be_focused()

        yield_input = page.locator('#target-yield')
        yield_input.focus()
        expect(yield_input).to_be_focused()

        assert_geometry(page)
        capture_screenshot(page, tmp_path, f'detail-no-js-{width}x{height}')


@pytest.mark.parametrize('width,height', ZOOM_VIEWPORTS)
def test_detail_reference_focus_ring(detail_revisions, detail_server, browser, width, height, tmp_path):  # noqa: F811
    recipe_id, rev_id, _, _ = detail_revisions['normal']
    base, cookie, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(url).status == 200

        back_btn = page.get_by_role('link', name='Alle Revisionen')
        back_btn.focus()
        expect(back_btn).to_be_focused()
        assert_focus_ring(back_btn)

        pdf_btn = page.get_by_role('link', name='PDF öffnen')
        pdf_btn.focus()
        expect(pdf_btn).to_be_focused()
        assert_focus_ring(pdf_btn)

        yield_input = page.locator('#target-yield')
        yield_input.focus()
        expect(yield_input).to_be_focused()
        assert_focus_ring(yield_input)

        capture_screenshot(page, tmp_path, f'detail-focus-ring-{width}x{height}')


def test_detail_reference_unauthenticated_gets_401(detail_revisions, detail_server, browser, tmp_path):  # noqa: F811
    recipe_id, rev_id, _, _ = detail_revisions['normal']
    base, _, _ = detail_server
    url = f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}'

    with browser.new_context(viewport={'width': 1440, 'height': 900}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        page = context.new_page()
        for width, height in ZOOM_VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto(url)
            assert response.status == 401
            assert 'Unveränderlicher Stand' not in page.locator('body').inner_text()
            capture_screenshot(page, tmp_path, f'detail-401-unauthenticated-{width}x{height}')


def test_detail_reference_errors_404_and_403(detail_revisions, detail_server, browser, a3, monkeypatch, tmp_path):  # noqa: F811
    recipe_id, rev_id, _, _ = detail_revisions['normal']
    base, cookie, app = detail_server
    _, owner, _, _, _ = a3

    with browser.new_context(viewport={'width': 1440, 'height': 900}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()

        # 404: Unknown revision ID
        resp_unknown_rev = page.goto(f'{base}/admin/rezepte/{recipe_id}/revisionen/{uuid4()}')
        assert resp_unknown_rev.status == 404
        capture_screenshot(page, tmp_path, 'detail-404-unknown-revision')

        # 404: Unknown recipe ID
        resp_unknown_recipe = page.goto(f'{base}/admin/rezepte/{uuid4()}/revisionen/{rev_id}')
        assert resp_unknown_recipe.status == 404

    # 403: Role without draft.read capability
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'csv.export'})
    unprivileged_actor = make_actor(owner, role='Cafeteria.Publisher')

    client_unprivileged = app.test_client()
    with client_unprivileged.session_transaction() as sess:
        sess['user'] = {'id': unprivileged_actor.user_id, 'name': 'Publisher Without Draft Read'}
        sess['authz_version'] = unprivileged_actor.authz_version
    unprivileged_cookie = client_unprivileged.get_cookie(app.config['SESSION_COOKIE_NAME'])

    with browser.new_context(viewport={'width': 1440, 'height': 900}, java_script_enabled=True,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': unprivileged_cookie.key, 'value': unprivileged_cookie.value, 'url': base}])
        page = context.new_page()
        resp_forbidden = page.goto(f'{base}/admin/rezepte/{recipe_id}/revisionen/{rev_id}')
        assert resp_forbidden.status == 403
        capture_screenshot(page, tmp_path, 'detail-403-forbidden')
