"""Real PostgreSQL/Chromium A04 forms, with and without application JavaScript."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_routes import DATABASE_URL, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401
from test_week_form_rerender import DAY, WEEK, _form, _snapshot

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/week-form-rerender-0912'
VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080), (720, 450)]


@pytest.fixture
def week_page(browser, live_server, admin_app, admin_engine, javascript):  # noqa: F811
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    context = browser.new_context(base_url=live_server, java_script_enabled=javascript)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context.add_cookies([{'name': 'session', 'value': cookie.value,
                         'domain': '127.0.0.1', 'path': '/', 'httpOnly': True}])
    page = context.new_page()
    page.emulate_media(reduced_motion='reduce')
    try:
        yield page, client
    finally:
        context.close()


def _locator(page, family, kind):
    form = page.locator(f'form[action="/admin/{family}/{kind}"]')
    if kind == 'service':
        meal = 'LUNCH' if family == 'cafeteria' else 'DINNER'
        form = form.filter(has=page.locator(f'input[name="day"][value="{DAY}"]'))
        form = form.filter(has=page.locator(f'input[name="meal"][value="{meal}"]'))
    return form


def _submit(page, form, expected):
    with page.expect_response(lambda response: response.request.method == 'POST') as response:
        form.locator('button[type="submit"]').click()
    assert response.value.status == expected
    page.wait_for_load_state('load')


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('kind', ['header', 'service'])
@pytest.mark.parametrize('javascript', [True, False])
def test_week_form_errors_save_and_stale_resubmit(week_page, admin_engine, family, kind, javascript):  # noqa: F811
    page, client = week_page
    page.goto(f'/admin/{family}?week={WEEK}')
    form = _locator(page, family, kind)
    assert form.locator('xpath=..').get_attribute('open') is None
    form.locator('xpath=..').locator('summary').click()
    if kind == 'header':
        field, entered = 'title', '   '
        form.locator('[name="title"]').fill(entered)
        form.locator('[name="shared_note"]').fill('  Mein unverlorener Hinweis  ')
    else:
        field, entered = 'service_end', '11:00'
        form.locator('[name="service_state"]').select_option('holiday')
        form.locator('[name="notice"]').fill('  Mein unverlorener Hinweis  ')
        form.locator('[name="service_start"]').fill('12:00')
        form.locator('[name="service_end"]').fill(entered)
    before = _snapshot(admin_engine)
    _submit(page, form, 400)
    assert _snapshot(admin_engine) == before
    form = _locator(page, family, kind)
    expect(form).to_be_visible()
    expect(form.locator(f'[name="{field}"]')).to_have_value(entered)
    expect(form.locator(f'[name="{field}"]')).to_have_attribute('aria-invalid', 'true')
    expect(form.locator('[name="row_version"]')).to_have_value('0')
    other_field = 'shared_note' if kind == 'header' else 'notice'
    expect(form.locator(f'[name="{other_field}"]')).to_have_value('  Mein unverlorener Hinweis  ')
    expect(page.locator('details.admin-week-settings[open], details.admin-week-service[open]')).to_have_count(1)
    if javascript:
        expect(form.locator('.error-region')).to_be_focused()
    else:
        expect(form.locator(f'[name="{field}"]')).to_be_focused()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for width, height in VIEWPORTS:
        page.set_viewport_size({'width': width, 'height': height})
        form.locator('.error-region').scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(EVIDENCE / f'{family}-{kind}-{javascript}-{width}x{height}.png'))
    page.set_viewport_size({'width': 1440, 'height': 900})
    if kind == 'service':
        form.locator('[name="service_start"]').fill('kein Beginn')
        form.locator('[name="service_end"]').fill('kein Ende')
        _submit(page, form, 400)
        form = _locator(page, family, kind)
        expect(form.locator('[name="service_start"]')).to_have_value('kein Beginn')
        expect(form.locator('[name="service_end"]')).to_have_value('kein Ende')
        form.locator('[name="service_start"]').fill('12:00')
    form.locator(f'[name="{field}"]').fill('Meine Woche' if kind == 'header' else '13:00')
    _submit(page, form, 303)
    assert page.url.endswith(f'/admin/{family}?week={WEEK}')
    # Keep the browser's original version while another writer saves a newer one.
    page.goto(f'/admin/{family}?week={WEEK}')
    form = _locator(page, family, kind)
    form.locator('xpath=..').locator('summary').click()
    old_version = form.locator('[name="row_version"]').input_value()
    competing = _form(client.get(f'/admin/{family}?week={WEEK}'), family, kind)['fields']
    target = 'title' if kind == 'header' else 'notice'
    competing[target] = 'Parallel gespeichert'
    assert client.post(f'/admin/{family}/{kind}', data=competing).status_code == 303
    before = _snapshot(admin_engine)
    form.locator(f'[name="{target}"]').fill('Mein Konflikttext')
    for _ in range(2):
        _submit(page, form, 409)
        form = _locator(page, family, kind)
        expect(form).to_be_visible()
        expect(form.locator('[name="row_version"]')).to_have_value(old_version)
        expect(form.locator(f'[name="{target}"]')).to_have_value('Mein Konflikttext')
        expect(form.get_by_role('link', name='Aktuellen Wochenplan öffnen')).to_be_visible()
        assert _snapshot(admin_engine) == before
    page.route(f'**/admin/{family}/{kind}', lambda route: route.continue_(
        post_data=route.request.post_data + '&row_version=0',
    ))
    _submit(page, form, 400)
    expect(page.locator('.admin-week-settings, .admin-week-service')).to_have_count(0)
    assert _snapshot(admin_engine) == before
