from __future__ import annotations

import threading
from collections.abc import Iterator
from wsgiref.simple_server import make_server

import pytest
from flask import render_template
from playwright.sync_api import Page, expect
from sqlalchemy import text
from werkzeug.datastructures import MultiDict

from test_admin_workflow_routes import DATABASE_URL
from test_rendered_ui import _login, admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)


@pytest.fixture
def catalog_page(request: pytest.FixtureRequest) -> Iterator[Page]:
    application = request.getfixturevalue('admin_app')
    engine = request.getfixturevalue('admin_engine')
    client, _ = _login(application, engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    server = make_server('127.0.0.1', 0, application)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with request.getfixturevalue('browser').new_context(
            base_url=f'http://127.0.0.1:{server.server_port}',
            reduced_motion='reduce',
        ) as context:
            context.add_cookies([{
                'name': 'session', 'value': cookie.value,
                'domain': '127.0.0.1', 'path': '/', 'httpOnly': True,
            }])
            yield context.new_page()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('viewport', [(360, 800), (1280, 900)])
def test_catalog_native_forms_preserve_and_remove_metadata(
    catalog_page: Page, request: pytest.FixtureRequest,
    family: str, profile: str, viewport: tuple[int, int],
) -> None:
    page = catalog_page
    engine = request.getfixturevalue('admin_engine')
    page.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
    list_path = f'/admin/{family}/komponenten'
    page.goto(list_path)
    page.locator('#create-component summary').click()
    form = page.locator(f'form[action="{list_path}"][method="post"]')
    form.locator('[name="name"]').fill('Katalog-Browsertest')
    form.locator('[name="category"]').select_option('side')
    form.locator('[name="origin_country_code"]').select_option('CH')
    form.locator('[name="target_scope"][value="current"]').check()
    form.locator('[name="label_code"][value="VEGAN"]').check()
    gluten = form.locator('.allergen-row').filter(has=page.locator('[value="GLUTEN"]'))
    milk = form.locator('.allergen-row').filter(has=page.locator('[value="MILK"]'))
    expect(gluten.locator('select')).to_be_disabled()
    gluten.locator('[name="allergen_code"]').check()
    gluten.locator('select').select_option('may_contain')
    milk.locator('[name="allergen_code"]').check()
    expect(milk.locator('select')).to_be_enabled()
    with page.expect_response(lambda response: response.request.method == 'POST') as created:
        form.get_by_role('button', name='Komponente erstellen', exact=True).click()
    assert created.value.status == 303
    page.wait_for_url(f'**{list_path}/*')
    expect(page.locator('main')).to_have_attribute('data-profile-scope', profile)

    # Existing inactive master links must survive an ordinary scalar edit.
    with engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.allergens SET active=false WHERE code='GLUTEN'"))
        connection.execute(text("UPDATE cafeteria.dietary_labels SET active=false WHERE code='VEGAN'"))
    page.reload()
    detail_path = f"{list_path}/{page.locator('main').get_attribute('data-public-id')}"
    detail = page.locator(f'form[action="{detail_path}"]')
    gluten = detail.locator('.allergen-row').filter(has=page.locator('[value="GLUTEN"]'))
    milk = detail.locator('.allergen-row').filter(has=page.locator('[value="MILK"]'))
    expect(detail.locator('[name="label_code"][value="VEGAN"]')).to_be_checked()
    expect(gluten.locator('[name="allergen_code"]')).to_be_checked()
    expect(gluten.locator('select')).to_have_value('may_contain')
    expect(milk.locator('[name="allergen_code"]')).to_be_checked()
    detail.locator('[name="name"]').fill('Katalog-Browsertest bearbeitet')
    milk.locator('[name="allergen_code"]').uncheck()
    expect(milk.locator('select')).to_be_disabled()
    with page.expect_response(lambda response: response.request.method == 'POST') as saved:
        detail.get_by_role('button', name='Speichern', exact=True).click()
    assert saved.value.status == 303
    expect(page.locator('h1')).to_have_text('Katalog-Browsertest bearbeitet')
    expect(detail.locator('[name="label_code"][value="VEGAN"]')).to_be_checked()
    expect(gluten.locator('select')).to_have_value('may_contain')
    expect(milk.locator('[name="allergen_code"]')).not_to_be_checked()

    # Clearing native checkboxes intentionally removes the complete metadata set.
    detail.locator('[name="label_code"][value="VEGAN"]').uncheck()
    gluten.locator('[name="allergen_code"]').uncheck()
    expect(gluten.locator('select')).to_be_disabled()
    with page.expect_response(lambda response: response.request.method == 'POST') as cleared:
        detail.get_by_role('button', name='Speichern', exact=True).click()
    assert cleared.value.status == 303
    page.wait_for_load_state()
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.component_labels')).scalar_one() == 0
        assert connection.execute(text('SELECT count(*) FROM cafeteria.component_allergens')).scalar_one() == 0

def _assert_component_controls_fit(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    dimensions = page.locator(
        'main .btn, main .form-control, main .form-select, main .form-check, '
        'main summary, main .dishboard-component-link'
    ).evaluate_all('''elements => elements.filter(e => e.getClientRects().length).map(e => ({
        height: e.getBoundingClientRect().height,
        width: e.getBoundingClientRect().width,
        label: e.textContent.trim().slice(0, 40)
    }))''')
    assert dimensions
    assert all(item['height'] >= 48 for item in dimensions), dimensions


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
def test_catalog_table_cards_country_errors_and_archive_across_breakpoints(
    catalog_page: Page, family: str, tmp_path,
) -> None:
    page = catalog_page
    list_path = f'/admin/{family}/komponenten'
    long_name = 'Saisonales Ofengemüse mit Karotten, Zucchetti und einer langen Komponentenbezeichnung'
    page.goto(list_path)
    page.locator('#create-component summary').click()
    form = page.locator(f'form[action="{list_path}"][method="post"]')
    form.locator('[name="name"]').fill(long_name)
    form.locator('[name="category"]').select_option('side')
    form.locator('[name="origin_country_code"]').select_option('CH')
    form.get_by_role('button', name='Komponente erstellen', exact=True).click()
    page.wait_for_url(f'**{list_path}/*')
    detail_path = page.url.split(page.url.split('/admin/')[0], 1)[1]
    public_id = page.locator('main').get_attribute('data-public-id')
    assert public_id

    for width, height in [(360, 800), (768, 1024), (820, 1180), (1024, 768),
                          (1199, 900), (1200, 900), (1280, 900)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.goto(list_path)
        expect(page.locator('body')).to_have_class('admin-body dishboard-admin')
        assert page.locator('link[href$="/app.css"]').count() == 0
        assert page.locator('script[src$="/vendor/tabler/tabler.min.js"]').count() == 1
        row = page.locator(f'.component-row[data-public-id="{public_id}"]')
        expect(row).to_contain_text(long_name)
        expect(row).to_contain_text('verwendet in 0 Gerichten')
        if width < 1200:
            expect(page.locator('.dishboard-component-table thead')).to_be_hidden()
            assert row.evaluate('e => getComputedStyle(e).display') == 'grid'
            assert row.evaluate('''e => e.querySelector('th').getBoundingClientRect().width
                >= e.getBoundingClientRect().width - 36''')
        else:
            expect(page.locator('.dishboard-component-table thead')).to_be_visible()
            assert row.evaluate('e => getComputedStyle(e).display') == 'table-row'
        _assert_component_controls_fit(page)
        if width in (360, 1200):
            page.screenshot(path=str(tmp_path / f'{family}-components-{width}.png'), full_page=True)
        page.goto(detail_path)
        expect(page.locator('h1')).to_have_text(long_name)
        expect(page.locator('#c-origin option:checked')).to_have_text('Schweiz')
        expect(page.locator('main')).to_have_attribute('data-family', family)
        _assert_component_controls_fit(page)
        if width in (360, 1200):
            page.screenshot(path=str(tmp_path / f'{family}-component-editor-{width}.png'), full_page=True)

    archive = page.get_by_role('button', name='Archivieren', exact=True)
    page.once('dialog', lambda dialog: dialog.dismiss())
    archive.click()
    expect(page.locator('main')).to_have_attribute('data-active', '1')
    page.once('dialog', lambda dialog: dialog.accept())
    archive.click()
    page.wait_for_load_state()
    expect(page.get_by_role('button', name='Reaktivieren', exact=True)).to_be_visible()
    expect(page.locator('main')).to_have_attribute('data-active', '0')
    page.goto(list_path)
    assert page.locator(f'.component-row[data-public-id="{public_id}"]').count() == 0
    page.locator('#f-archived').check()
    page.get_by_role('button', name='Suchen', exact=True).click()
    expect(page.locator(f'.component-row[data-public-id="{public_id}"]')).to_contain_text('archiviert')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('template', ['components.html', 'component_editor.html'])
def test_component_error_template_retains_submitted_state(
    catalog_page: Page, request: pytest.FixtureRequest, family: str, profile: str,
    template: str,
) -> None:
    # Presentation contract only: existing POST routes still abort on validation errors.
    page = catalog_page
    page.goto(f'/admin/{family}/komponenten')
    page.set_viewport_size({'width': 360, 'height': 800})
    application = request.getfixturevalue('admin_app')
    component = {
        'public_id': 'template-example', 'name': 'Gespeicherter Name', 'category': 'side',
        'origin_country_code': 'CH', 'active': True, 'row_version': 7,
        'profile_scope': 'common', 'usage_count': 2,
        'labels': [{'code': 'VEGAN'}], 'allergens': [{'code': 'MILK', 'presence': 'contains'}],
    }
    values = MultiDict([
        ('name', 'Noch nicht gespeicherte Eingabe'), ('category', 'side'),
        ('origin_country_code', 'ZZ'), ('target_scope', 'current'),
        ('allergen_code', 'GLUTEN'), ('allergen_presence', 'may_contain'),
    ])
    with application.test_request_context():
        html = render_template(
            f'admin/{template}', family=family, profile=profile, component=component,
            rows=[], categories={'side': 'Beilage'}, query='', category=None,
            include_archived=False, csrf='template-only-csrf', form_values=values,
            form_errors={'name': 'Name prüfen', 'category': 'Kategorie prüfen',
                         'origin_country_code': 'Herkunft prüfen'},
            labels=[{'code': 'VEGAN', 'name': 'Vegan'}],
            allergens=[{'code': 'MILK', 'name': 'Milch'}, {'code': 'GLUTEN', 'name': 'Gluten'}],
        )
    page.set_content(html, wait_until='networkidle')
    form = page.locator('#component-form')
    expect(form.locator('[name="name"]')).to_have_value('Noch nicht gespeicherte Eingabe')
    expect(form.locator('[name="category"]')).to_have_value('side')
    expect(form.locator('[name="origin_country_code"]')).to_have_value('ZZ')
    for field_id in ['c-name', 'c-cat', 'c-origin']:
        expect(page.locator(f'#{field_id}')).to_have_attribute('aria-invalid', 'true')
        expect(page.locator(f'#{field_id}')).to_have_attribute('aria-describedby', f'{field_id}-error')
        expect(page.locator(f'#{field_id}-error')).to_be_visible()
        expect(page.locator(f'.error-region a[href="#{field_id}"]')).to_be_visible()
    expect(form.locator('[name="label_code"]')).not_to_be_checked()
    expect(form.locator('[name="allergen_code"][value="MILK"]')).not_to_be_checked()
    expect(form.locator('[name="allergen_code"][value="GLUTEN"]')).to_be_checked()
    expect(form.locator('select[name="allergen_presence"]:enabled')).to_have_value('may_contain')
    expect(form.locator('[name="_csrf"]')).to_have_value('template-only-csrf')
    if template == 'components.html':
        expect(page.locator('#create-component')).to_have_attribute('open', '')
        expect(form.locator('[name="target_scope"][value="current"]')).to_be_checked()
    else:
        expect(form.locator('[name="row_version"]')).to_have_value('7')
    _assert_component_controls_fit(page)
