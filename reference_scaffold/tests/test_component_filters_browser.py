from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

from cafeteria.component_catalog_store import AdminScope, archive_component, create_component
from test_component_catalog_browser import _assert_component_controls_fit, catalog_page  # noqa: F401
from test_component_catalog_db import CatalogDatabase, _link_component
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width', [390, 820, 1440])
def test_filter_controls_combine_reset_and_keep_exact_results(request, family, profile, width, tmp_path):
    page: Page = request.getfixturevalue('catalog_page')
    engine = request.getfixturevalue('admin_engine')
    with engine.connect() as connection:
        location = int(connection.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one())
        actor = connection.execute(text("SELECT id,authz_version FROM cafeteria.users "
            "WHERE public_id='00000000-0000-0000-0000-000000000002'")).one()
    scope = AdminScope(actor.id, location, profile, actor.authz_version)
    title = 'Filterprobe Karottengemüse mit langer Bezeichnung und Kräutersauce'
    match = create_component(engine, scope, 'side', title, 'CH', 'common', ['VEGAN'], [('GLUTEN', 'contains')])
    create_component(engine, scope, 'side', 'Filterprobe Unbekannt', None, 'current', [], [])
    archived = create_component(engine, scope, 'side', 'Filterprobe Archiviert', 'DE', 'current', [], [])
    archive_component(engine, scope, str(archived['public_id']), 1)
    _link_component(CatalogDatabase(engine, engine, location, 0, actor.id, actor.authz_version), str(match['public_id']))
    page.set_viewport_size({'width': width, 'height': 1000})
    path = f'/admin/{family}/komponenten'
    page.goto(path)
    form = page.get_by_role('form', name='Komponenten filtern')
    expect(form).to_be_visible()
    expect(page.locator('#component-result-count')).to_have_text('2 Treffer')
    _assert_component_controls_fit(page)
    params = {'q': 'Filterprobe', 'category': 'side', 'usage': 'used', 'allergen': 'GLUTEN',
              'presence': 'contains', 'label': 'VEGAN', 'origin': 'CH', 'status': 'active'}
    form.get_by_label('Suche', exact=True).fill(params['q'])
    for key, value in params.items():
        if key != 'q':
            form.locator(f'[name="{key}"]').select_option(value)
    form.get_by_role('button', name='Suchen', exact=True).click()
    expect(page.locator('#component-result-count')).to_have_text('1 Treffer')
    expect(page.locator('.component-row')).to_have_count(1)
    expect(page.locator('.component-row')).to_have_attribute('data-public-id', str(match['public_id']))
    expect(page.locator('.component-row')).to_contain_text(title)
    expect(page.locator('.component-row .usage')).to_contain_text('verwendet in 1 Gerichten')
    assert parse_qs(urlsplit(page.url).query) == {key: [value] for key, value in params.items()}
    for key, value in params.items():
        expect(form.locator(f'[name="{key}"]')).to_have_value(value)
    expect(form.locator('#f-origin option:checked')).to_have_text('Schweiz')
    _assert_component_controls_fit(page)
    page.screenshot(path=str(tmp_path / f'component-filters-{family}-{width}.png'), full_page=True)

    form.locator('#f-origin').select_option('DE')
    form.get_by_role('button', name='Suchen', exact=True).click()
    expect(page.locator('#component-result-count')).to_have_text('0 Treffer')
    expect(page.get_by_text('Keine Komponenten gefunden.', exact=True)).to_be_visible()
    form.get_by_role('link', name='Zurücksetzen', exact=True).click()
    assert urlsplit(page.url).query == ''
    expect(page.locator('#component-result-count')).to_have_text('2 Treffer')
    expect(form.locator('#f-q')).to_have_value('')
    expect(form.locator('#f-status')).to_have_value('active')

    form.locator('#f-allergen').select_option('unknown')
    form.locator('#f-origin').select_option('unknown')
    form.get_by_role('button', name='Suchen', exact=True).click()
    expect(page.locator('#component-result-count')).to_have_text('1 Treffer')
    expect(page.locator('.component-row')).to_contain_text('Filterprobe Unbekannt')
    expect(form.locator('#f-origin option:checked')).to_have_text('Nicht erfasst')
    expect(page.locator('#component-allergen-filter-hint')).to_contain_text('keine bestätigte Allergenfreiheit')
    form.get_by_role('link', name='Zurücksetzen', exact=True).click()
    form.locator('#f-status').select_option('archived')
    form.get_by_role('button', name='Suchen', exact=True).click()
    expect(page.locator('#component-result-count')).to_have_text('1 Treffer')
    expect(page.locator('.component-row')).to_have_attribute('data-active', '0')
    expect(page.locator('.component-row')).to_contain_text('Filterprobe Archiviert')
    _assert_component_controls_fit(page)
