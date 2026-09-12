"""Korrekturwelle Bausteine: Layout, Verträge und Screenshotnachweise."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import render_template
from playwright.sync_api import Page, expect
from werkzeug.datastructures import MultiDict

from test_admin_workflow_routes import DATABASE_URL
from test_component_catalog_browser import _assert_component_controls_fit, catalog_page  # noqa: F401
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'ui-korrektur-0912' / 'components'
VIEWPORTS = (
    (1366, 768),
    (1920, 1080),
    (768, 1024),
    (390, 844),
)


def _form_payload(request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(request.post_data or '').items()}


def _shot(page: Page, route: str, state: str, width: int, height: int) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(EVIDENCE / f'{route}-{state}-{width}x{height}.png'),
        full_page=True,
    )


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
    expect(page.get_by_text('Keine Bausteine gefunden.', exact=True)).to_be_visible()
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
def test_components_zoom_200_percent_without_horizontal_scroll(catalog_page: Page, family: str) -> None:  # noqa: F811
    page = catalog_page
    page.set_viewport_size({'width': 720, 'height': 450})
    _open_editor(page, family)
    page.goto(f'/admin/{family}/komponenten')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    expect(page.locator('.component-row').first).to_be_visible()
    _shot(page, 'komponenten', 'zoom-200', 720, 450)


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
