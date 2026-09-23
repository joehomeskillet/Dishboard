"""Real-browser acceptance for the shopping-list admin pages (MP-REC-SHOPPING-PERSIST, SP-UI).

Flask app on a real local HTTP server, real PostgreSQL fixtures shared with the
store's own ``test_shopping_list_db.py`` (real ``create_food_v27``/``freeze_recipe_v27``
flow, no hand-built snapshots). Screenshots are evidence only, never committed.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from werkzeug.serving import make_server

import cafeteria
from cafeteria.shopping_list_store import add_manual_item, compute_revision, create_shopping_list
from test_rendered_ui import browser  # noqa: F401
from test_shopping_list_db import (  # noqa: F401
    _bound_component, _ingredient, _item_public, _scope, app_engine, create_food,
    installed_pg16, pg16, seeded_pg16, store,
)

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/sp-ui-0914'
PDF_EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/spdf-route-0915'
ROUTE_VIEWPORTS = ((390, 844), (1440, 900))
SHARED_VIEWPORTS = ((1024, 768), (768, 1024), (1920, 1080))


@pytest.fixture
def app_client(store, monkeypatch, tmp_path):  # noqa: F811
    owner, engine, ids = store
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda app: None)
    application = cafeteria.create_app()
    application.config.update(TESTING=True, SECRET_KEY='sp-ui-browser-test', LAST_GOOD_DIR=str(tmp_path))
    application.extensions['cafeteria_db'] = engine
    application.extensions['cafeteria_auth_issuer_db'] = engine
    client = application.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': ids['actor'], 'name': 'Küche Browser'}
        session['authz_version'] = ids['authz']
        session['_csrf_token'] = 'sp-ui-browser-csrf'
    return application, owner, engine, client, ids


@pytest.fixture
def server(app_client):
    application, owner, engine, client, ids = app_client
    srv = make_server('127.0.0.1', 0, application, threaded=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    cookie = client.get_cookie(application.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    try:
        yield f'http://127.0.0.1:{srv.server_port}', cookie, owner, engine, ids
    finally:
        srv.shutdown()
        thread.join(timeout=5)
        srv.server_close()


def _week_public(owner, ids) -> str:
    with owner.connect() as connection:
        return str(connection.execute(text('SELECT public_id FROM cafeteria.menu_weeks WHERE id=:week'), ids).scalar_one())


def _seed_component(owner, engine, ids, *, target_quantity='8', food_name='Testmehl'):
    """500 G flour scaled by target_quantity/servings; PORTION servings=4 so 8 -> factor 2 (1000 G)."""
    ids['owner'] = owner
    flour = create_food(engine, ids, food_name)
    _bound_component(owner, engine, ids, [_ingredient(flour, '500', 'G')], servings='4', unit='PORTION',
                     target_quantity=target_quantity, target_unit_code='PORTION', label='Hauptgang')
    return flour


def _select_and_submit(page, selector, value, *, submit_label):
    """CSP (script-src 'self', no unsafe-inline) blocks inline onchange; the submit button is
    always visible and real (no <noscript> gate), so this works with and without JavaScript."""
    page.locator(selector).select_option(value)
    with page.expect_navigation(wait_until='load'):
        page.get_by_role('button', name=submit_label, exact=True).click()


EVIDENCE.mkdir(parents=True, exist_ok=True)
# Rendered controls below the 48px target of the page contract (hidden elements have no client rects).
SMALL_TARGETS = '''() => [...document.querySelectorAll('main :is(a.btn, button, input:not([type=hidden], .form-check-input), select, textarea, .form-check, summary)')]
    .filter(element => element.getClientRects().length && element.getBoundingClientRect().height < 48)
    .map(element => `${element.getBoundingClientRect().height}px ${element.outerHTML.slice(0, 100)}`)'''
# Selects whose selected option text does not fit between the padding (left text, right arrow).
CLIPPED_SELECTS = '''() => [...document.querySelectorAll('main select')].filter(select => select.getClientRects().length).filter(select => {
    const style = getComputedStyle(select), context = document.createElement('canvas').getContext('2d');
    context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    const width = context.measureText(select.options[select.selectedIndex]?.text ?? '').width;
    return width + parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) > select.clientWidth + 1;
}).map(select => `${select.name}: ${select.options[select.selectedIndex].text}`)'''


def _shot(page, name):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), name
    assert page.evaluate(SMALL_TARGETS) == [], name
    assert page.evaluate(CLIPPED_SELECTS) == [], name
    EVIDENCE.chmod(0o700)
    path = EVIDENCE / f'{name}.png'
    page.screenshot(path=str(path), full_page=True)
    path.chmod(0o600)


def _pdf_shot(page, name):
    """SPDF-ROUTE evidence lives in its own directory; never overwrites another WP's PNGs."""
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), name
    assert page.evaluate(SMALL_TARGETS) == [], name
    PDF_EVIDENCE.mkdir(parents=True, exist_ok=True)
    PDF_EVIDENCE.chmod(0o700)
    path = PDF_EVIDENCE / f'{name}.png'
    page.screenshot(path=str(path), full_page=True)
    path.chmod(0o600)


@pytest.mark.parametrize('width,height', ROUTE_VIEWPORTS)
@pytest.mark.parametrize('javascript', [False, True])
def test_full_lifecycle_create_compute_check_recompute_and_manual_item(
    server, browser, width, height, javascript,  # noqa: F811
):
    base, cookie, owner, engine, ids = server
    _seed_component(owner, engine, ids)
    week_public = _week_public(owner, ids)
    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=javascript,
                             reduced_motion='reduce', locale='de-CH', timezone_id='Europe/Zurich') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        assert page.goto(base + '/admin/einkaufslisten').status == 200
        expect(page.get_by_role('heading', level=1)).to_have_text('Einkaufslisten')
        expect(page.get_by_text('Noch keine Einkaufslisten', exact=True)).to_be_visible()
        expect(page.get_by_label('Titel', exact=True)).to_be_visible()
        page.locator('.empty-action').get_by_role('link', name='Anlegen', exact=True).click()
        expect(page.get_by_label('Titel', exact=True)).to_be_focused()
        page.get_by_label('Titel', exact=True).fill('Browser Einkaufsliste')
        with page.expect_navigation(wait_until='load'):
            page.locator('.shopping-create-form').get_by_role('button', name='Anlegen', exact=True).click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Einkaufslisten')
        expect(page.locator('.page-header')).to_contain_text('Browser Einkaufsliste')
        page.locator('.shopping-manual').get_by_role('link', name='Anlegen', exact=True).click()
        expect(page.locator('#new-item-text')).to_be_focused()
        expect(page.locator('.empty-title', has_text='Noch keine Berechnung')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        _shot(page, f'detail-empty-{width}x{height}-js-{javascript}')

        # Woche waehlen: no bound week yet, real navigation via the always-visible submit button.
        _select_and_submit(page, '#compute_week', week_public, submit_label='Woche laden')
        checkbox = page.locator('input[name="component_ids"]').first
        expect(checkbox).to_be_visible()
        checkbox.check()
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Neu berechnen', exact=True).click()
        assert '1000 Gramm' in page.inner_text('main')
        _shot(page, f'detail-computed-{width}x{height}-js-{javascript}')

        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Abhaken', exact=True).first.click()
        assert 'Abgehakt' in page.inner_text('main')

        with owner.begin() as connection:
            connection.execute(
                text("UPDATE cafeteria.menu_item_components SET target_quantity='16' WHERE menu_item_id=:item"), ids,
            )
        page.goto(base + page.url.replace(base, ''))
        _select_and_submit(page, '#compute_week', week_public, submit_label='Woche laden')
        page.locator('input[name="component_ids"]').first.check()
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Neu berechnen', exact=True).click()
        assert '2000 Gramm' in page.inner_text('main')
        assert 'Geändert, erneut offen' in page.inner_text('main')
        expect(page.locator('.shopping-result-table .badge:visible', has_text='Geändert, erneut offen')).to_have_count(1)
        _shot(page, f'detail-recomputed-{width}x{height}-js-{javascript}')

        page.get_by_label('Text', exact=True).fill('Servietten')
        page.get_by_label('Menge (optional)', exact=True).fill('2')
        new_unit_value = page.locator('#new-item-unit option').nth(1).get_attribute('value')
        page.locator('#new-item-unit').select_option(new_unit_value)
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Anlegen', exact=True).click()
        expect(page.locator('input[value="Servietten"]')).to_be_visible()
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Abhaken', exact=True).last.click()
        expect(page.get_by_role('button', name='Wieder öffnen', exact=True).last).to_be_visible()

        page.locator('select[name="revision"]').select_option(index=1)
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Öffnen', exact=True).click()
        expect(page.get_by_text('Beleg vom', exact=False)).to_contain_text('nicht aktuell')
        main = page.inner_text('main')
        assert 'Testmehl' in main and '1000 Gramm' in main and '2000 Gramm' not in main and 'Servietten' in main
        assert main.count('nicht aktuell') == 2, main  # notice + the visible status of the single line
        expect(page.locator('.shopping-result-table .badge:visible', has_text='nicht aktuell')).to_have_count(1)
        for label in ('Abhaken', 'Wieder öffnen', 'Neu berechnen', 'Anlegen', 'Speichern', 'Löschen'):
            expect(page.get_by_role('button', name=label)).to_have_count(0)
        _shot(page, f'detail-older-revision-{width}x{height}-js-{javascript}')
        assert not errors


@pytest.mark.parametrize('width,height', SHARED_VIEWPORTS)
def test_detail_shared_viewports_no_overflow_and_48px_targets(server, browser, width, height):  # noqa: F811
    base, cookie, owner, engine, ids = server
    _seed_component(owner, engine, ids)
    week_public = _week_public(owner, ids)
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Geteilte Ansicht', menu_week_public_id=week_public)
    compute_revision(engine, scope, list_id, component_ids=[f'{_item_public(owner, ids["item"])}:1'], policy='leaf',
                     expected_row_version=1)
    add_manual_item(engine, scope, list_id, item_text='Servietten', quantity='2', unit_code='TL')
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce',
                             locale='de-CH', timezone_id='Europe/Zurich') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(f'{base}/admin/einkaufslisten/{list_id}').status == 200
        expect(page.locator('#compute_week')).to_have_value(week_public)
        expect(page.locator('input[name="component_ids"]').first).to_be_visible()
        expect(page.get_by_role('button', name='Abhaken', exact=True)).to_have_count(2)
        page.evaluate('window.scrollTo(0, 0)')  # full-page capture of the fixed sidebar starts at the top
        _shot(page, f'detail-shared-{width}x{height}')


def test_keyboard_and_200_percent_zoom(server, browser, tmp_path):  # noqa: F811
    from tempfile import TemporaryDirectory

    base, cookie, owner, engine, ids = server
    _seed_component(owner, engine, ids)
    with owner.begin() as connection:
        list_id = connection.execute(text('''INSERT INTO cafeteria.shopping_lists(
                location_id, menu_week_id, title, created_by, updated_by)
            VALUES (:location, :week, 'Tastatur und Zoom', :actor, :actor) RETURNING public_id'''), ids).scalar_one()
    with browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce',
                             locale='de-CH', timezone_id='Europe/Zurich') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(f'{base}/admin/einkaufslisten/{list_id}').status == 200
        title = page.get_by_role('heading', level=1)
        title.focus()
        page.keyboard.press('Tab')
        focused = page.evaluate('document.activeElement.tagName')
        assert focused in ('A', 'BUTTON', 'SELECT', 'INPUT')
    with TemporaryDirectory(prefix='sp-ui-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True, locale='de-CH',
            timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            assert page.goto(f'{base}/admin/einkaufslisten/{list_id}').status == 200
            assert page.evaluate('devicePixelRatio') == 2 and page.evaluate('innerWidth') == 720
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            _shot(page, 'detail-native-200-percent')


@pytest.mark.parametrize('width,height', ((1440, 900), (390, 844)))
def test_pdf_link_visible_focusable_and_serves_pdf(server, browser, width, height):  # noqa: F811
    base, cookie, owner, engine, ids = server
    _seed_component(owner, engine, ids)
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='PDF-Link')
    revision = compute_revision(
        engine, scope, list_id, component_ids=[f'{_item_public(owner, ids["item"])}:1'],
        policy='leaf', expected_row_version=1,
    )
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce',
                             locale='de-CH', timezone_id='Europe/Zurich') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(f'{base}/admin/einkaufslisten/{list_id}').status == 200
        link = page.get_by_role('link', name='Drucken', exact=True)
        expect(link).to_be_visible()
        href = link.get_attribute('href')
        assert href == f'/admin/einkaufslisten/{list_id}/druck.pdf?revision={revision}'
        link.focus()
        expect(link).to_be_focused()
        response = page.request.get(base + href)
        assert response.status == 200
        assert response.headers['content-type'] == 'application/pdf'
        page.evaluate('window.scrollTo(0, 0)')
        _pdf_shot(page, f'pdf-link-{width}x{height}')


FRAME_VIEWPORTS = ((360, 844), (768, 1024), (1024, 768), (1440, 900))


def _assert_shopping_frame(browser_instance, base, cookie, list_id):
    for javascript in (False, True):
        context = browser_instance.new_context(
            viewport={'width': 1440, 'height': 900}, java_script_enabled=javascript,
            reduced_motion='reduce', locale='de-CH', timezone_id='Europe/Zurich',
        )
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        try:
            for width, height in FRAME_VIEWPORTS:
                page.set_viewport_size({'width': width, 'height': height})
                assert page.goto(base + '/admin/einkaufslisten').status == 200
                list_metrics = page.evaluate('''() => ({
                    width: innerWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    primaryCount: document.querySelectorAll('main .btn-primary').length,
                    rowHeights: [...document.querySelectorAll('.shopping-list .admin-list-row')]
                        .map(e => e.getBoundingClientRect().height),
                    createFields: [...document.querySelectorAll('.shopping-create-form [name]')].map(e => e.name),
                })''')
                assert list_metrics['scrollWidth'] <= width + 1, (javascript, width, list_metrics)
                assert list_metrics['primaryCount'] == 1, (javascript, width, list_metrics)
                assert sorted(list_metrics['createFields']) == ['_csrf', 'menu_week_public_id', 'note', 'title']
                if width == 1440:
                    assert list_metrics['rowHeights'] and max(list_metrics['rowHeights']) <= 72, list_metrics
                statusbar = page.locator('dl.admin-statusbar')
                expect(statusbar).to_be_visible()
                expect(statusbar.locator('.admin-statusbar-item').filter(
                    has=page.get_by_text('Positionen', exact=True)
                )).to_contain_text('offen')
                expect(page.locator('.shopping-filter .active')).to_have_attribute('aria-current', 'true')
                expect(page.get_by_role('link', name='Öffnen', exact=True).first).to_be_visible()
                page.locator('#einkaufsliste-neu-title').click()
                expect(page.get_by_label('Titel', exact=True)).to_be_focused()
                expect(page.locator('.shopping-create-form').get_by_role('button', name='Anlegen', exact=True)).to_be_visible()
                if width in (360, 1440):
                    page.evaluate('window.scrollTo(0, 0)')
                    _shot(page, f'rework-list-{width}-js-{javascript}')

                assert page.goto(f'{base}/admin/einkaufslisten/{list_id}').status == 200
                detail_metrics = page.evaluate('''() => ({
                    width: innerWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    primaryCount: document.querySelectorAll('main .btn-primary').length,
                    lineToggle: [...new Set([...document.querySelectorAll('form[action$="/zeilen"] [name]')]
                        .map(e => e.name))].sort(),
                    resultHeights: [...document.querySelectorAll('.shopping-result-table tbody tr')]
                        .map(e => e.getBoundingClientRect().height),
                    manualHeights: [...document.querySelectorAll('.shopping-manual-table tbody tr')]
                        .map(e => e.getBoundingClientRect().height),
                })''')
                assert detail_metrics['scrollWidth'] <= width + 1, (javascript, width, detail_metrics)
                assert detail_metrics['primaryCount'] == 1, (javascript, width, detail_metrics)
                assert detail_metrics['lineToggle'] == ['_csrf', 'checked', 'line_key', 'revision_public_id']
                if width == 1440:
                    for key in ('resultHeights', 'manualHeights'):
                        assert detail_metrics[key] and max(detail_metrics[key]) <= 96, detail_metrics
                if width in (360, 1440):
                    print(f'SHOPPING_METRICS js={javascript} list={list_metrics} detail={detail_metrics}')
                    _shot(page, f'rework-detail-{width}-js-{javascript}')
                expect(page.locator('#shopping-delete-hint')).to_have_count(1)
                expect(page.get_by_role('button', name='Löschen', exact=True)).to_have_class('btn btn-danger ms-3')
                expect(page.get_by_role('button', name='Löschen', exact=True)).to_have_attribute(
                    'aria-describedby', 'shopping-delete-hint',
                )
                detail_bar = page.locator('dl.admin-statusbar')
                expect(detail_bar).to_be_visible()
                for label in ('Woche', 'Liste', 'Berechnung', 'Positionen'):
                    expect(detail_bar.locator('.admin-statusbar-item').filter(
                        has=page.get_by_text(label, exact=True)
                    )).to_have_count(1)
                expect(page.get_by_role('button', name='Abhaken', exact=True)).to_have_count(2)
                expect(page.get_by_role('button', name='Neu berechnen', exact=True)).to_have_count(1)
            if javascript:
                page.set_viewport_size({'width': 1440, 'height': 900})
                assert page.goto(f'{base}/admin/einkaufslisten/{list_id}').status == 200
                page.get_by_role('heading', level=1).focus()
                page.keyboard.press('Tab')
                focused = page.evaluate('document.activeElement.tagName')
                assert focused in ('A', 'BUTTON', 'SELECT', 'INPUT', 'SUMMARY')
                outline = page.evaluate(
                    'getComputedStyle(document.activeElement).outlineStyle'
                )
                assert outline == 'solid'
        finally:
            context.close()


def test_frame_statusbar_viewports_keyboard_and_no_js(server, browser):  # noqa: F811
    """Use the session browser so fixture teardown owns every browser process."""
    base, cookie, owner, engine, ids = server
    _seed_component(
        owner, engine, ids,
        food_name='Bio Vollkornweizenmehl aus regionalem Anbau für Brot und feines Gebäck',
    )
    week_public = _week_public(owner, ids)
    scope = _scope(ids)
    list_id = create_shopping_list(engine, scope, title='Rahmen Einkaufsliste', menu_week_public_id=week_public)
    compute_revision(engine, scope, list_id, component_ids=[f'{_item_public(owner, ids["item"])}:1'], policy='leaf',
                     expected_row_version=1)
    add_manual_item(
        engine, scope, list_id,
        item_text='Ungebleichte Servietten für Mittagessen und Abendservice im grossen Speisesaal',
        quantity='2000', unit_code='TL',
    )
    _assert_shopping_frame(browser, base, cookie, list_id)
