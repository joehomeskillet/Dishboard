"""Native detail actions retain form values, readable content and printed labels."""
from __future__ import annotations

import json

from playwright.sync_api import expect, sync_playwright

from cafeteria import roles
from cafeteria.component_catalog_store import create_component
from cafeteria.ui import register_ui
from cafeteria.ui.i18n import translate
from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login, _scope
from test_ui_route_inventory import _recipe_revision


def _check_action(page, summary, javascript):
    expect(summary.locator('svg')).to_have_count(1)
    assert summary.evaluate('el => el.getBoundingClientRect().width >= 32')
    assert summary.evaluate('el => el.getBoundingClientRect().height >= 32')
    summary.focus()
    expect(summary).to_be_focused()
    page.keyboard.press('Shift')
    assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
    if javascript:
        tooltip = page.get_by_role('tooltip', name=summary.get_attribute('aria-label'), exact=True)
        expect(tooltip).to_be_visible()
        page.keyboard.press('Escape')
        expect(tooltip).to_be_hidden()


def test_detail_actions_native_roles_profiles_and_print(
    admin_app, admin_engine, live_server, monkeypatch, tmp_path,  # noqa: F811
):
    admin_app.config['TESTING'] = True
    register_ui(admin_app)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    component = create_component(admin_engine, _scope(admin_engine, actor), 'side',
                                 'Detail-Prüfung', 'CH', 'common', (), ())
    recipe, revision = _recipe_revision(admin_app, admin_engine, actor)
    root = f'/admin/rezepte/{recipe}'
    failures, measurements = [], []
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'draft.read'})
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
                            label = f'{role}-{width}-js{javascript}'
                            posts = []
                            page.on('request', lambda request: posts.append(request.url)
                                    if request.method == 'POST' else None)
                            for family in ('cafeteria', 'patienten'):
                                route = f'/admin/{family}/komponenten/{component["public_id"]}'
                                assert page.goto(route).status == 200
                                page.locator('#c-name').fill('Ungespeicherter Name')
                                form = page.locator('#component-form')
                                values = form.evaluate('el => Array.from(new FormData(el))')
                                more = page.locator('.component-secondary-actions > summary')
                                if more.inner_text().strip() or not more.get_attribute('aria-label'):
                                    failures.append((label, family, 'More is not an accessible icon action'))
                                _check_action(page, more, javascript)
                                more.focus()
                                expect(more).to_be_focused()
                                page.keyboard.press('Enter')
                                expect(page.locator('.component-secondary-actions h2')).to_have_text('Archivieren')
                                expect(page.locator('.component-secondary-actions .ui-sem-consequence')).to_be_visible()
                                assert page.locator('form[action$="/archive"]').get_attribute('data-confirm')
                                page.keyboard.press('Enter')
                                assert form.evaluate('el => Array.from(new FormData(el))') == values
                                expect(page.get_by_text('Wirkung zentraler Änderungen', exact=True)).to_be_visible()
                                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                                page.screenshot(path=str(tmp_path / f'{label}-{family}.png'), full_page=True)
                            for state, route in (('draft', root + '/ansicht'),
                                                 ('saved', root + '/revisionen/' + revision)):
                                assert page.goto(route).status == 200
                                document = page.locator('#recipe-document')
                                if role == 'Cafeteria.Editor':
                                    assert page.locator(f'main a[href="{root}"]').count() == 0
                                expect(document.locator('.recipe-amount').first).to_have_text('800 G')
                                for selector, name, content in (
                                    ('.recipe-originals', 'Originalmengen ansehen', 'Originalausbeute: 4 PORTION'),
                                    ('.recipe-provenance', 'Herkunft ansehen', 'Gilt für:'),
                                ):
                                    summary = document.locator(selector + ' > summary')
                                    expect(summary).to_have_attribute('aria-label', name)
                                    if summary.inner_text().strip():
                                        failures.append((label, state, selector, 'visible action text'))
                                    _check_action(page, summary, javascript)
                                    summary.focus()
                                    page.keyboard.press('Enter')
                                    expect(document.locator(selector)).to_contain_text(content)
                                    assert document.locator(selector).get_attribute('open') is not None
                                    metrics = summary.evaluate('''el => ({
                                        text: el.textContent.trim(), width: el.getBoundingClientRect().width,
                                        height: el.getBoundingClientRect().height,
                                        after: getComputedStyle(el, '::after').content
                                    })''')
                                    measurements.append(dict(case=label, state=state, selector=selector, **metrics))
                                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                                page.screenshot(path=str(tmp_path / f'{label}-{state}.png'), full_page=True)
                                if role == 'Cafeteria.Admin' and javascript and state == 'saved':
                                    page.emulate_media(media='print')
                                    for selector, text in (('.recipe-originals', 'Originalmengen'),
                                                           ('.recipe-provenance', 'Herkunft')):
                                        summary = document.locator(selector + ' > summary')
                                        printed = summary.evaluate('''el => ({
                                            text: el.textContent.trim(),
                                            after: getComputedStyle(el, '::after').content,
                                            width: el.getBoundingClientRect().width
                                        })''')
                                        assert text in printed['text'] or text in printed['after']
                                        measurements.append(dict(case=label, media='print', selector=selector, **printed))
                                    page.screenshot(path=str(tmp_path / f'{label}-print.png'), full_page=True)
                                    page.emulate_media(media='screen')
                            assert not posts
                if role == 'Cafeteria.Editor':
                    assert client.post(f'/admin/cafeteria/komponenten/{component["public_id"]}',
                                       data={'_csrf': 'workflow-csrf'}).status_code == 403
            with browser.new_context(base_url=live_server, viewport={'width': 390, 'height': 844}) as context:
                context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                page = context.new_page()
                for locale in ('de', 'en', 'xx'):
                    admin_app.config['UI_LOCALE'] = locale
                    assert page.goto(root + '/revisionen/' + revision).status == 200
                    for selector, key, english in (
                        ('.recipe-originals', 'recipe.original_quantities', 'View original quantities'),
                        ('.recipe-provenance', 'recipe.provenance', 'View provenance'),
                    ):
                        with admin_app.app_context():
                            name, printed = translate(key + '.aria'), translate(key + '.label')
                        summary = page.locator(selector + ' > summary')
                        expect(summary).to_have_accessible_name(name)
                        expect(summary).to_have_attribute('data-ui-tooltip', name)
                        expect(summary).to_have_attribute('data-print-label', printed)
                        if locale == 'en':
                            assert name == english
                        if locale == 'xx':
                            assert name.startswith('[!! ') and printed.startswith('[!! ')
                        _check_action(page, summary, True)
                    page.screenshot(path=str(tmp_path / f'locale-{locale}-390.png'), full_page=True)
            admin_app.config['UI_LOCALE'] = 'de'
            with playwright.chromium.launch_persistent_context(
                str(tmp_path / 'zoom-profile'), channel='chromium', headless=True, no_viewport=True,
                locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
                args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
            ) as context:
                page = context.pages[0]
                page.goto('chrome://settings/appearance')
                page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
                assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
                context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                for name, route, selector in (
                    ('cafeteria', f'/admin/cafeteria/komponenten/{component["public_id"]}', '.component-secondary-actions'),
                    ('patienten', f'/admin/patienten/komponenten/{component["public_id"]}', '.component-secondary-actions'),
                    ('recipe', root + '/revisionen/' + revision, '.recipe-originals'),
                ):
                    assert page.goto(live_server + route).status == 200
                    assert page.evaluate('devicePixelRatio') == 2
                    assert page.evaluate('innerWidth') == 720
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    summary = page.locator(selector + ' > summary')
                    _check_action(page, summary, True)
                    page.keyboard.press('Enter')
                    assert page.locator(selector).get_attribute('open') is not None
                    page.screenshot(path=str(tmp_path / f'{name}-native-zoom200.png'), full_page=True)
        finally:
            browser.close()
    (tmp_path / 'detail-measurements.json').write_text(json.dumps(measurements, indent=2), encoding='utf-8')
    assert not failures, failures
