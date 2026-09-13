"""Korrekturwelle Bausteine: Layout, Verträge und Screenshotnachweise."""
from __future__ import annotations

from pathlib import Path
import json
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import render_template
from playwright.sync_api import Page, expect
from werkzeug.datastructures import MultiDict

from test_admin_workflow_routes import DATABASE_URL
from test_component_catalog_browser import _assert_component_controls_fit, catalog_page  # noqa: F401
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401
from test_recipe_freeze_v2_browser import native_full_page_capture

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'density-components-0913' / 'after'
VIEWPORTS = (
    (1440, 900),
    (1024, 768),
    (1920, 1080),
    (2560, 1440),
    (768, 1024),
    (390, 844),
    (320, 844),
)


def _form_payload(request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(request.post_data or '').items()}


def _shot(page: Page, route: str, state: str, width: int, height: int) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    family = page.locator('main').get_attribute('data-family') or 'template'
    name = f'{route}-{family}-{state}-{width}x{height}'
    metrics = page.evaluate('''() => {
        const main = document.querySelector('main');
        const core = document.querySelector('.component-row, #component-form [name="name"]');
        return {viewport: [innerWidth, innerHeight], dpr: devicePixelRatio,
            documentHeight: document.documentElement.scrollHeight,
            documentWidth: document.documentElement.scrollWidth,
            mainWidth: main.getBoundingClientRect().width,
            coreY: core?.getBoundingClientRect().y, scrollY,
            font: getComputedStyle(main).fontFamily, browser: navigator.userAgent};
    }''')
    (EVIDENCE / f'{name}.json').write_text(json.dumps(metrics, indent=2))
    destination = EVIDENCE / f'{name}.png'
    if state == 'native-zoom-200':
        native_full_page_capture(page, destination)
    else:
        page.screenshot(path=str(destination), full_page=True)


def _open_editor(page: Page, family: str) -> None:
    list_path = f'/admin/{family}/komponenten'
    page.goto(list_path)
    if page.locator('.component-row').count() == 0:
        page.locator('#create-component summary').click()
        form = page.locator(f'form[action="{list_path}"][method="post"]')
        form.locator('[name="name"]').fill('Editor-Screenshot-Baustein')
        form.locator('[name="category"]').select_option('side')
        form.get_by_role('button', name='Baustein erstellen', exact=True).click()
        page.wait_for_url(f'**{list_path}/*')
    else:
        page.locator('.component-edit-link').first.click()
        page.wait_for_load_state()


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
def test_list_first_row_visible_without_scroll(catalog_page: Page, family: str) -> None:  # noqa: F811
    page = catalog_page
    page.set_viewport_size({'width': 1366, 'height': 768})
    list_path = f'/admin/{family}/komponenten'
    page.goto(list_path)
    if page.locator('.component-row').count() == 0:
        page.locator('#create-component summary').click()
        form = page.locator(f'form[action="{list_path}"][method="post"]')
        form.locator('[name="name"]').fill('Sichtbarkeits-Baustein')
        form.locator('[name="category"]').select_option('side')
        form.get_by_role('button', name='Baustein erstellen', exact=True).click()
        page.wait_for_url(f'**{list_path}/*')
        page.goto(list_path)
    expect(page.locator('#create-component')).not_to_have_attribute('open', '')
    first_row = page.locator('.component-list-container .component-row').first
    expect(first_row).to_be_visible()
    box = first_row.bounding_box()
    assert box is not None
    assert box['y'] + box['height'] <= 768


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_components_list_layout_and_overflow(catalog_page: Page, family: str, width: int, height: int) -> None:  # noqa: F811
    page = catalog_page
    page.set_viewport_size({'width': width, 'height': height})
    list_path = f'/admin/{family}/komponenten'
    _open_editor(page, family)
    page.goto(list_path)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    expect(page.get_by_role('heading', level=1, name='Bausteine')).to_be_visible()
    expect(page.get_by_role('form', name='Bausteine filtern')).to_be_visible()
    expect(page.locator('.component-row').first).to_be_visible()
    _assert_component_controls_fit(page)
    _shot(page, 'komponenten', 'normal', width, height)

    page.goto(f'{list_path}?q=kein-treffer-fuer-screenshot')
    expect(page.get_by_text('Keine Bausteine passen zu diesen Filtern.', exact=True)).to_be_visible()
    expect(page.get_by_text('Baustein anlegen', exact=True)).to_have_count(1)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    _shot(page, 'komponenten', 'leer', width, height)


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_component_editor_layout_and_overflow(catalog_page: Page, family: str, width: int, height: int) -> None:  # noqa: F811
    page = catalog_page
    page.set_viewport_size({'width': width, 'height': height})
    _open_editor(page, family)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    expect(page.get_by_role('button', name='Baustein speichern', exact=True)).to_be_visible()
    expect(page.get_by_role('link', name='Abbrechen', exact=True)).to_be_visible()
    _assert_component_controls_fit(page)
    _shot(page, 'komponente', 'normal', width, height)


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
def test_components_zoom_200_percent_without_horizontal_scroll(catalog_page: Page, family: str, tmp_path) -> None:  # noqa: F811
    _open_editor(catalog_page, family)
    editor_url = catalog_page.url
    parsed = urlsplit(editor_url)
    base_url = f'{parsed.scheme}://{parsed.netloc}'
    browser_instance = catalog_page.context.browser
    with TemporaryDirectory(prefix='components-zoom-', dir=tmp_path) as profile:
        with browser_instance.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True,
            reduced_motion='reduce', locale='de-CH', timezone_id='Europe/Zurich',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies(catalog_page.context.cookies())
            for route, url in [('komponenten', base_url + f'/admin/{family}/komponenten'), ('komponente', editor_url)]:
                assert page.goto(url).status == 200
                assert page.evaluate('devicePixelRatio === 2 && innerWidth === 720')
                _assert_component_controls_fit(page)
                if route == 'komponente':
                    expect(page.locator('[data-sticky-form]')).to_have_class('card-header admin-compact-toolbar is-static')
                _shot(page, route, 'native-zoom-200', 720, 450)


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_create_edit_archive_payloads_unchanged(
    catalog_page: Page, family: str, javascript: bool,  # noqa: F811
) -> None:
    bootstrap_page = catalog_page
    list_path = f'/admin/{family}/komponenten'
    bootstrap_page.goto(list_path)
    page = bootstrap_page
    context = None
    if not javascript:
        browser = bootstrap_page.context.browser
        assert browser is not None
        parsed = urlsplit(bootstrap_page.url)
        context = browser.new_context(
            base_url=f'{parsed.scheme}://{parsed.netloc}',
            java_script_enabled=False,
            reduced_motion='reduce',
            storage_state=bootstrap_page.context.storage_state(),
        )
        page = context.new_page()
    try:
        page.goto(list_path)
        page.locator('#create-component summary').click()
        create = page.locator(f'form[action="{list_path}"][method="post"]')
        create.locator('[name="name"]').fill('Korrektur-Payload-Test')
        create.locator('[name="category"]').select_option('side')
        create.locator('[name="origin_country_code"]').select_option('CH')
        create.locator('[name="target_scope"][value="current"]').check()
        with page.expect_request(lambda request: request.method == 'POST' and request.url.endswith(list_path)) as created:
            create.get_by_role('button', name='Baustein erstellen', exact=True).click()
        payload = _form_payload(created.value)
        assert set(payload) == {'_csrf', 'name', 'category', 'origin_country_code', 'target_scope'}
        assert payload['name'] == 'Korrektur-Payload-Test'
        assert payload['category'] == 'side'
        assert payload['origin_country_code'] == 'CH'
        assert payload['target_scope'] == 'current'
        assert payload['_csrf']
        page.wait_for_url(f'**{list_path}/*')
        detail_path = page.url.split(page.url.split('/admin/')[0], 1)[1]
        detail = page.locator(f'form[action="{detail_path}"]')
        detail.locator('[name="name"]').fill('Korrektur-Payload-Test bearbeitet')
        with page.expect_request(lambda request: request.method == 'POST' and detail_path in request.url) as saved:
            detail.get_by_role('button', name='Baustein speichern', exact=True).click()
        saved_payload = _form_payload(saved.value)
        assert set(saved_payload) == {'_csrf', 'row_version', 'name', 'category', 'origin_country_code'}
        assert saved_payload['_csrf']
        assert saved_payload['row_version']

        page.goto(list_path)
        page.locator('.component-filter-advanced summary').click()
        page.locator('#f-status').select_option('all')
        with page.expect_request(lambda request: request.method == 'GET' and 'status=all' in request.url) as filtered:
            page.get_by_role('button', name='Suchen', exact=True).click()
        query = parse_qs(urlsplit(filtered.value.url).query, keep_blank_values=True)
        assert set(query) == {'q', 'category', 'status', 'usage', 'allergen', 'presence', 'label', 'origin'}
        assert query['status'] == ['all']

        page.goto(detail_path)
        archive = page.get_by_role('button', name='Archivieren', exact=True)
        if javascript:
            page.once('dialog', lambda dialog: dialog.accept())
        with page.expect_request(lambda request: request.method == 'POST' and request.url.endswith('/archive')) as archived:
            archive.click()
        archive_payload = _form_payload(archived.value)
        assert set(archive_payload) == {'_csrf', 'row_version'}
        assert archive_payload['_csrf']
        assert archive_payload['row_version']
    finally:
        if context is not None:
            context.close()


@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_error_state_opens_create_details_and_focuses_error_region(
    catalog_page: Page, request: pytest.FixtureRequest, width: int, height: int,  # noqa: F811
) -> None:
    page = catalog_page
    application = request.getfixturevalue('admin_app')
    values = MultiDict([
        ('name', 'Noch nicht gespeicherte Eingabe'), ('category', 'side'),
        ('origin_country_code', 'ZZ'), ('target_scope', 'current'),
    ])
    with application.test_request_context():
        html = render_template(
            'admin/components.html', family='patienten', profile='patient', component={},
            rows=[], categories={'side': 'Beilage'}, query='', category=None,
            include_archived=False, csrf='template-only-csrf', form_values=values,
            form_errors={'name': 'Name prüfen', 'category': 'Kategorie prüfen',
                         'origin_country_code': 'Herkunft prüfen'},
            labels=[{'code': 'VEGAN', 'name': 'Vegan'}],
            allergens=[{'code': 'MILK', 'name': 'Milch'}],
        )
    page.set_viewport_size({'width': width, 'height': height})
    page.goto('/admin/patienten/komponenten')
    page.set_content(html, wait_until='networkidle')
    expect(page.locator('#create-component')).to_have_attribute('open', '')
    expect(page.locator('.error-region')).to_be_visible()
    expect(page.locator('.error-region')).to_be_focused()
    expect(page.locator('[name="name"]')).to_have_value('Noch nicht gespeicherte Eingabe')
    expect(page.locator('.error-region a[href="#c-name"]')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    _shot(page, 'komponenten', 'fehler', width, height)


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_allergen_display_preserves_native_values_and_single_save(
    catalog_page: Page, family: str, width: int, height: int, javascript: bool,  # noqa: F811
) -> None:
    page = catalog_page
    path = f'/admin/{family}/komponenten'
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(path)
    expect(page.get_by_text('Noch keine aktiven Bausteine.', exact=True)).to_be_visible()
    page.locator('#create-component summary').press('Enter')
    form = page.locator('#component-form')
    form.locator('#c-name').fill('Allergen-Roundtrip')
    form.locator('#c-cat').select_option('side')
    gluten = form.locator('.allergen-row').filter(has=page.locator('[value="GLUTEN"]'))
    expect(gluten.locator('select')).to_be_disabled()
    expect(gluten.locator('select')).to_be_hidden()
    expect(gluten.get_by_text('Nicht ausgewählt', exact=True)).to_be_visible()
    gluten.locator('[name="allergen_code"]').check()
    expect(gluten.locator('select')).to_be_visible()
    gluten.locator('select').select_option('may_contain')
    form.get_by_role('button', name='Baustein erstellen', exact=True).click()
    page.wait_for_url(f'**{path}/*')
    editor_url = page.url
    browser_instance = page.context.browser
    with browser_instance.new_context(
        java_script_enabled=javascript, storage_state=page.context.storage_state(),
        reduced_motion='reduce', viewport={'width': width, 'height': height},
    ) as context:
        page = context.new_page()
        page.goto(editor_url)
        form = page.locator('#component-form')
        save = form.get_by_role('button', name='Baustein speichern', exact=True)
        expect(save).to_have_count(1)
        assert save.bounding_box()['y'] + save.bounding_box()['height'] <= height
        gluten = form.locator('.allergen-row').filter(has=page.locator('[value="GLUTEN"]'))
        expect(gluten.locator('select')).to_have_value('may_contain')
        expect(gluten.locator('select')).to_be_visible()
        if javascript:
            gluten.locator('[name="allergen_code"]').uncheck()
            expect(gluten.locator('select')).to_be_disabled()
            expect(gluten.locator('select')).to_be_hidden()
            gluten.locator('[name="allergen_code"]').check()
            expect(gluten.locator('select')).to_have_value('may_contain')
        # A disclosure is never a submit or reset, including without JavaScript.
        version = form.locator('[name="row_version"]').input_value()
        page.get_by_text('Wirkung zentraler Änderungen', exact=True).press('Enter')
        page.get_by_text('Wirkung zentraler Änderungen', exact=True).press('Enter')
        expect(form.locator('[name="row_version"]')).to_have_value(version)
        expect(gluten.locator('select')).to_have_value('may_contain')
        form.locator('#c-name').fill('Allergen-Roundtrip bearbeitet')
        with page.expect_request(lambda request: request.method == 'POST') as saved:
            save.click()
        payload = parse_qs(saved.value.post_data or '')
        assert payload['allergen_code'] == ['GLUTEN']
        assert payload['allergen_presence'] == ['may_contain']
        assert payload['_csrf'] and payload['row_version'] == [version]
        expect(page.locator('h1')).to_have_text('Allergen-Roundtrip bearbeitet')
        expect(page.locator('#edit-presence-GLUTEN')).to_have_value('may_contain')
        assert page.locator('.component-allergens .allergen-row').evaluate_all('''rows => rows.every(row => {
            const name = row.querySelector('.form-check').getBoundingClientRect();
            const input = row.querySelector('.component-allergen-presence').getBoundingClientRect();
            return name.right <= input.left + 1 || name.bottom <= input.top + 1;
        })''')
        if width < 768:
            selection = page.locator('#edit-presence-GLUTEN').bounding_box()
            assert selection['width'] >= form.bounding_box()['width'] - 96
        page.evaluate('scrollTo(0, 0)')
        _assert_component_controls_fit(page)
        _shot(page, 'komponente', f'allergen-js{javascript}', width, height)
