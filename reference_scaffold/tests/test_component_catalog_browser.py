from __future__ import annotations

import threading
from collections.abc import Iterator
from wsgiref.simple_server import make_server

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

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
@pytest.mark.parametrize('viewport', [(390, 844), (1440, 1100)])
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
    form.locator('[name="origin_country_code"]').fill('CH')
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
