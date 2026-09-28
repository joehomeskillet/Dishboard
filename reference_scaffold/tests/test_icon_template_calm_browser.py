"""Template hub density without losing active/draft or saved/public meaning."""
from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

from cafeteria.admin import output_routes
from cafeteria.print_template_config import default_config
from cafeteria.print_templates import PrintTemplateStateError, change_template
from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_ui_list_family_browser import _mount_public_targets
from test_ui_route_inventory import _prepare_inventory_entities


def test_template_calm_roles_revisions_native_week_and_errors(
    admin_app, admin_engine, live_server, monkeypatch, tmp_path,  # noqa: F811
):
    _mount_public_targets(admin_app)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _prepare_inventory_entities(admin_app, admin_engine, actor)
    with client.session_transaction() as state:
        authz_version = state['authz_version']
    for profile in ('staff_guest', 'patient', 'recipe'):
        change_template(admin_engine, profile, actor, authz_version, 0, 'standard', 'save',
                        name=f'Neuer Entwurf {profile}', config=default_config())
    failures, measurements = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for role in ('Cafeteria.Admin', 'Cafeteria.Editor'):
                client, _ = _login(admin_app, admin_engine, [role])
                cookie = client.get_cookie('session')
                assert cookie is not None
                for javascript in (True, False):
                    for width, height in ((1440, 900), (390, 844)):
                        with browser.new_context(base_url=live_server, java_script_enabled=javascript,
                                                 viewport={'width': width, 'height': height}) as context:
                            context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                            page = context.new_page()
                            response = page.goto('/admin/vorlagen?week=2026-08-31', wait_until='networkidle')
                            assert response.status == 200 and response.headers['cache-control'] == 'no-store'
                            label = f'{role}-{width}-js{javascript}'
                            metrics = page.evaluate("""() => ({
                                first: document.querySelector('[data-current-template]').getBoundingClientRect().top
                                    - document.querySelector('main').getBoundingClientRect().top,
                                statusCards: document.querySelectorAll('.admin-statusbar-item').length,
                                overflow: document.documentElement.scrollWidth > innerWidth + 1
                            })""")
                            measurements.append(dict(case=label, **metrics))
                            if metrics['statusCards'] or metrics['overflow'] or (width == 1440 and metrics['first'] > 220):
                                failures.append((label, metrics))
                            page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True)
                            for family, profile in (('cafeteria', 'staff_guest'), ('patienten', 'patient')):
                                page.locator(f'[aria-controls="output-{family}"]').click()
                                pane = page.locator(f'#output-{family}')
                                if not pane.is_visible():
                                    failures.append((label, family, 'profile unreachable'))
                                    continue
                                current = pane.locator('[data-current-template]')
                                assert current.is_visible()
                                assert current.locator('h3').inner_text() == 'Standard'
                                assert 'Version 1' in current.inner_text()
                                assert f'Neuer Entwurf: Neuer Entwurf {profile} · Version 2' in current.inner_text()
                                assert pane.locator('[data-semantic="status.active"]').count() == 1
                                saved = page.locator(f'a[href="/admin/{family}/preview/print?week=2026-08-31"]')
                                public = page.locator(f'a[href="/druck/{family}/woche"]')
                                assert saved.count() == 1 and public.count() == 1
                                assert 'gespeicherten Woche' in saved.get_attribute('aria-label')
                                assert 'veröffentlichten' in public.get_attribute('aria-label')
                                editors = pane.locator(f'a[href^="/admin/vorlagen/{family}?"]')
                                assert (editors.count() > 0) == (role == 'Cafeteria.Admin')
                                assert pane.locator('summary').evaluate_all(
                                    'els => els.every(el => el.textContent.trim() === "" && el.getAttribute("aria-label"))')
                                page.screenshot(path=str(tmp_path / f'{label}-{family}.png'), full_page=True)
                            recipe = page.locator('[aria-labelledby="recipe-templates-heading"]')
                            assert recipe.locator('h3').inner_text() == 'Standard'
                            assert 'Neuer Entwurf: Neuer Entwurf recipe · Revision 2' in recipe.inner_text()
                            page.get_by_label('Woche ab Montag').fill('2026-09-07')
                            page.get_by_role('button', name='Woche öffnen', exact=True).click()
                            page.wait_for_url('**/admin/vorlagen?week=2026-09-07')
                            assert page.locator('a[href="/druck/patienten/woche"]').count() == 1
            def unavailable(*_args, **_kwargs):
                raise PrintTemplateStateError('Vorlagenkatalog derzeit nicht verfügbar.')

            monkeypatch.setattr(output_routes, 'read_templates', unavailable)
            with browser.new_context(base_url=live_server, viewport={'width': 390, 'height': 844}) as context:
                context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                page = context.new_page()
                response = page.goto('/admin/vorlagen', wait_until='networkidle')
                assert response.status == 503 and response.headers['cache-control'] == 'no-store'
                assert page.locator('.alert-danger').count() == 1
                assert page.get_by_role('link', name='Erneut laden').is_visible()
                assert page.locator('.print-tpl-row').count() == 0
                page.screenshot(path=str(tmp_path / 'catalog-error-390.png'))
        finally:
            browser.close()
    (tmp_path / 'template-calm-measurements.json').write_text(
        json.dumps(measurements, indent=2), encoding='utf-8')
    assert not failures, failures
