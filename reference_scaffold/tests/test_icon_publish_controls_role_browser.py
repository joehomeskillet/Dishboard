from __future__ import annotations

# ruff: noqa: F811

from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save_reviewed, _staff_values
from test_admin_workflow_routes import DAY, DATABASE_URL, _login

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize(('family', 'profile'), [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'])
@pytest.mark.parametrize('javascript', [True, False])
def test_publish_controls_follow_capability_and_preserve_post_contract(
    admin_app, admin_engine, live_server, browser, family, profile, role, javascript, tmp_path,
):
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    _save_reviewed(admin_engine, profile, values)
    client, _ = _login(admin_app, admin_engine, [role])
    cookie = client.get_cookie('session')
    assert cookie is not None
    overview = f'/admin/{family}?week={DAY}'
    publish_url = f'/admin/{family}/publish'
    can_publish = role != 'Cafeteria.Editor'
    with browser.new_context(
        base_url=live_server, java_script_enabled=javascript, reduced_motion='reduce',
        has_touch=not javascript,
        viewport={'width': 1440 if javascript else 390, 'height': 900 if javascript else 844},
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        response = page.goto(overview)
        assert response is not None and response.status == 200
        expect(page.locator('main')).to_have_attribute('data-status', 'ready')
        expect(page.locator('.page-header-subtitle')).to_contain_text('Noch nicht veröffentlicht · bereit')
        page.screenshot(path=str(tmp_path / 'ready.png'))
        trigger = page.locator('[data-bs-target="#week-publish-modal"]')
        form = page.locator('#week-publish-form')

        # Overview CSRF is still available from the native week-header form for editors.
        header = page.locator(f'form[action="/admin/{family}/header"]')
        payload = {
            name: header.locator(f'input[name="{name}"]').input_value()
            for name in ('_csrf', 'week', 'row_version')
        }
        assert payload['_csrf'] and payload['week'] == DAY
        with admin_engine.connect() as connection:
            before = {
                table: connection.execute(text(
                    f'SELECT to_jsonb(row) FROM cafeteria.{table} AS row ORDER BY id'
                )).scalars().all()
                for table in ('menu_weeks', 'menu_services', 'menu_items',
                              'publication_revisions', 'audit_events')
            }

        if not can_publish:
            refused = context.request.post(publish_url, form=payload, max_redirects=0)
            assert refused.status == 403
            with admin_engine.connect() as connection:
                after = {
                    table: connection.execute(text(
                        f'SELECT to_jsonb(row) FROM cafeteria.{table} AS row ORDER BY id'
                    )).scalars().all()
                    for table in before
                }
            assert after == before
            # Count across the full DOM, including hidden modal and overflow actions.
            expect(page.locator('[data-semantic="actions.publish"]')).to_have_count(0)
            expect(trigger).to_have_count(0)
            expect(form).to_have_count(0)
            expect(page.locator('#week-publish-modal, .admin-week-nojs-publish')).to_have_count(0)
            actions = page.get_by_role('link', name='CSV exportieren', exact=True).locator('..')
            expect(actions).to_be_visible()
            expect(actions.locator('[data-semantic="actions.publish"]')).to_have_count(0)
            expect(page.locator('[data-semantic="actions.more"]')).to_have_count(0)
            return

        expect(trigger).to_be_visible()
        expect(trigger).to_be_enabled()
        expect(form).to_have_attribute('action', publish_url)
        expect(form).to_have_attribute('method', 'post')
        expected = form.evaluate('form => Object.fromEntries(new FormData(form))')
        assert expected == payload
        if javascript:
            trigger.focus()
            page.keyboard.press('Enter')
            expect(page.locator('#week-publish-modal')).to_be_visible()
            confirm = form.get_by_role('button', name='Veröffentlichen', exact=True)
        else:
            expect(page.locator('.admin-week-nojs-publish summary')).to_have_count(0)
            confirm = page.locator('.admin-week-nojs-publish button')
        expect(confirm).to_be_visible()
        expect(confirm).to_be_enabled()
        page.screenshot(path=str(tmp_path / 'confirmation.png'))
        with page.expect_response(lambda result: result.request.method == 'POST') as published:
            confirm.click()
        assert published.value.status == 303
        assert published.value.headers['location'] == overview
        assert parse_qs(published.value.request.post_data or '') == {
            key: [value] for key, value in expected.items()
        }
        page.wait_for_url('**' + overview)
        expect(page.locator('main')).to_have_attribute('data-status', 'live')
        expect(trigger).to_have_attribute('aria-label', 'Erneut veröffentlichen')
        expect(trigger).to_be_enabled()
        with admin_engine.connect() as connection:
            assert connection.execute(text(
                'SELECT count(*) FROM cafeteria.publication_revisions'
            )).scalar_one() == len(before['publication_revisions']) + 1
