"""Own native/JS proposal evidence, real browser zoom and clear conflict navigation."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import expect
from cafeteria.branding_config import contrast

from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_routes import DAY, _login
from test_menu_recipe_selection_browser import _insert_revision
from test_menu_template_binding_db import make_template, stored_state
from test_menu_proposal_routes import editor_form, planning
from test_recipe_freeze_v2_browser import native_full_page_capture
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/menu-proposal-0913'
VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844),
             (1920, 1080), (2560, 1440), (320, 900))


def shot(page, name):
    page.evaluate('document.fonts.ready')
    assert page.evaluate('document.fonts.status') == 'loaded'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('h1').count() == 1
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE / f'{name}.png'
    if name.endswith('native-zoom-200'):
        native_full_page_capture(page, destination)
    else:
        page.screenshot(path=str(destination), full_page=True)
    metrics = page.evaluate('''() => {
        const main = document.querySelector('main'), body = document.querySelector('.page-body');
        const primary = document.querySelector('.page-body .btn-primary');
        const style = primary && getComputedStyle(primary);
        const hex = value => '#' + value.match(/[\\d.]+/g).slice(0, 3)
            .map(n => Math.round(Number(n)).toString(16).padStart(2, '0')).join('');
        const contrasts = [...document.querySelectorAll('main .btn, main .form-label, main .form-hint, main .form-control, main .form-select, main [role=alert]')]
            .filter(e => e.getClientRects().length && !e.disabled).map(e => {
                let parent = e;
                while (parent.parentElement && ['transparent', 'rgba(0, 0, 0, 0)'].includes(getComputedStyle(parent).backgroundColor)) parent = parent.parentElement;
                return {color:hex(getComputedStyle(e).color), background:hex(getComputedStyle(parent).backgroundColor)};
            });
        return {width:innerWidth,height:innerHeight,dpr:devicePixelRatio,
            mainWidth:main.getBoundingClientRect().width,bodyWidth:body.getBoundingClientRect().width,
            font:getComputedStyle(document.body).fontFamily,loaded:document.fonts.status,
            color:style?.color,background:style?.backgroundColor,contrasts};
    }''')
    for pair in metrics['contrasts']:
        pair['ratio'] = contrast(pair['color'], pair['background'])
        assert pair['ratio'] >= 4.5, pair
    (EVIDENCE / f'{name}.json').write_text(json.dumps(metrics, indent=2))


def submit(page, label, status):
    with page.expect_navigation(wait_until='load'), page.expect_response(
        lambda response: response.request.method == 'POST'
    ) as result:
        button = page.get_by_role('button', name=label, exact=True)
        button.focus()
        expect(button).to_be_focused()
        assert button.evaluate('(el) => getComputedStyle(el).outlineStyle') != 'none'
        page.keyboard.press('Enter')
    assert result.value.status == status
    page.wait_for_load_state()
    return parse_qs(result.value.request.post_data, keep_blank_values=True)


@pytest.mark.parametrize('javascript', (True, False))
@pytest.mark.parametrize('family', ('patienten', 'cafeteria'))
def test_native_proposal_forms_save_and_keep_accessible_layout(
    browser, live_server, admin_app, admin_engine, javascript, family,  # noqa: F811
):
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    revision = _insert_revision(admin_engine, actor, 'Rösti aus dem gespeicherten Stand')
    template = make_template(admin_engine, recipe=int(revision['recipe_id']))
    context = browser.new_context(base_url=live_server, java_script_enabled=javascript,
        locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce')
    context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': live_server}])
    failures = []
    try:
        page = context.new_page()
        page.on('pageerror', lambda error: failures.append(str(error)))
        for route, name in (('/admin/gerichtvorlagen', 'list'),
                (f'/admin/gerichtvorlagen/{template["public_id"]}', 'template')):
            assert page.goto(route).status == 200
            for width, height in ((1440, 900), (390, 844)):
                page.set_viewport_size({'width': width, 'height': height})
                shot(page, f'{name}-{family}-{width}-{javascript}')
            link = page.get_by_role('link', name='Als Menü einplanen', exact=True)
            expect(link).to_be_visible()
            assert link.bounding_box()['height'] >= 48
        page.get_by_role('link', name='Als Menü einplanen', exact=True).click()
        page.get_by_label('Woche ab Montag', exact=True).fill(DAY)
        page.get_by_label('Bereich', exact=True).select_option('patient' if family == 'patienten' else 'staff_guest')
        original = page.locator('[name="template_context"]').input_value()
        submit(page, 'Ziel aktualisieren', 200)
        assert page.locator('[name="template_context"]').input_value() == original
        assert page.locator('#planning-meal option').count() == (2 if family == 'patienten' else 1)
        assert page.locator('#planning-day option').count() == 7
        assert page.locator('#planning-day option[disabled]').count() == (0 if family == 'patienten' else 2)
        page.get_by_label('Wochentag', exact=True).select_option('1')
        if not javascript:
            submit(page, 'Ziel aktualisieren', 200)
        expect(page.locator('#planning-summary')).to_contain_text('Dienstag, 1. September 2026')
        expect(page.locator('.flash-region')).not_to_contain_text('Zuerst speichern')
        page.get_by_label('Wochentag', exact=True).select_option('0')
        if not javascript:
            submit(page, 'Ziel aktualisieren', 200)
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            shot(page, f'planning-{family}-{width}-{javascript}')
            for label in ('Bereich', 'Woche ab Montag', 'Wochentag', 'Mahlzeit', 'Menüart'):
                assert page.get_by_label(label, exact=True).bounding_box()['height'] >= 48
        before = stored_state(admin_engine)
        submit(page, 'Weiter zum Menü', 303)
        assert 'template_context=' in page.url and '_csrf=' not in page.url
        expect(page.get_by_role('heading', name='Neues Menü aus Vorlage «Rösti»', exact=True)).to_be_visible()
        expect(page.get_by_label('Menüname', exact=True)).to_have_value('Rösti')
        expect(page.locator('[name="recipe_revision_public_id"]')).to_have_value(revision['public_id'])
        expect(page.get_by_text('Vorgeschlagen: Stand 1', exact=False)).to_be_visible()
        assert page.locator('[name="row_version"]').input_value() == '0'
        assert stored_state(admin_engine) == before
        for width, height in ((1440, 900), (390, 844), (320, 900)):
            page.set_viewport_size({'width': width, 'height': height})
            shot(page, f'editor-{family}-{width}-{javascript}')
        if family == 'cafeteria':
            page.locator('[name="internal_chf"]').fill('9.50')
            page.locator('[name="external_chf"]').fill('14.50')
        else:
            expect(page.locator('[name="internal_chf"], [name="external_chf"]')).to_have_count(0)
        page.get_by_label('Menüname', exact=True).fill('Rösti für den Wochenplan')
        if javascript:
            expect(page.locator('.flash-region')).to_contain_text('Zuerst speichern')
        saved = submit(page, 'Menü speichern', 303)
        assert saved['row_version'] == ['0']
        assert saved['recipe_revision_public_id'] == [revision['public_id']]
        expect(page.get_by_text('Menü «Rösti für den Wochenplan» aus Vorlage «Rösti»', exact=False)).to_be_visible()
        expect(page.get_by_text('Aus Vorlage «Rösti»', exact=True)).to_be_visible()
        assert failures == []
    finally:
        context.close()


@pytest.mark.parametrize('javascript', (True, False))
def test_occupied_conflict_opens_current_menu_only_after_explicit_action(
    browser, live_server, admin_app, admin_engine, javascript,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    path, form, _ = planning(client, template, area='patient')
    menu, _ = editor_form(client, client.post(path, data=form).location)
    assert client.post('/admin/patienten/menu', data=menu).status_code == 303
    before = stored_state(admin_engine)
    with browser.new_context(base_url=live_server, java_script_enabled=javascript,
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': live_server}])
        page = context.new_page()
        assert page.goto(path + f'?week={DAY}').status == 200
        page.get_by_label('Bereich', exact=True).select_option('patient')
        submit(page, 'Weiter zum Menü', 409)
        expect(page.get_by_role('alert')).to_contain_text('Bereits belegt mit «Rösti»')
        expect(page.get_by_role('link', name='Anderes Ziel wählen', exact=True)).to_be_visible()
        assert page.locator('[data-menu-editor]').count() == 0
        for width, height in ((1440, 900), (390, 844), (320, 900)):
            page.set_viewport_size({'width': width, 'height': height})
            shot(page, f'occupied-{width}-{javascript}')
        assert stored_state(admin_engine) == before
        link = page.get_by_role('link', name='Bestehendes Menü öffnen', exact=True)
        link.focus()
        page.keyboard.press('Enter')
        expect(page.get_by_label('Menüname', exact=True)).to_have_value('Rösti')
        expect(page.locator('form[data-menu-editor] [name="row_version"]')).to_have_value('1')
        assert 'template_context=' not in page.url
        assert stored_state(admin_engine) == before


def test_real_browser_200_percent_zoom(browser, live_server, admin_app, admin_engine, tmp_path):  # noqa: F811
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    with TemporaryDirectory(prefix='proposal-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(profile, channel='chromium',
                headless=True, no_viewport=True, locale='de-CH', reduced_motion='reduce',
                args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900']) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': live_server}])
            assert page.goto(live_server + f'/admin/gerichtvorlagen/{template["public_id"]}/einplanen?week={DAY}').status == 200
            cdp = context.new_cdp_session(page)
            assert cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom'] == 2
            assert page.evaluate('[innerWidth,outerWidth,devicePixelRatio]') == [720, 1440, 2]
            assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
            shot(page, 'planning-native-zoom-200')
            submit(page, 'Weiter zum Menü', 303)
            assert cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom'] == 2
            shot(page, 'editor-native-zoom-200')
            cdp.detach()


@pytest.mark.parametrize('javascript', (True, False))
def test_invalid_week_keeps_native_values_and_focuses_error(
    browser, live_server, admin_app, admin_engine, javascript,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    with browser.new_context(base_url=live_server, java_script_enabled=javascript,
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': live_server}])
        page = context.new_page()
        assert page.goto(f'/admin/gerichtvorlagen/{template["public_id"]}/einplanen?week={DAY}').status == 200
        original = page.locator('[name="template_context"]').input_value()
        csrf = page.locator('#planning-target [name="_csrf"]').input_value()
        before = stored_state(admin_engine)
        page.get_by_label('Woche ab Montag', exact=True).fill('2026-09-01')
        submit(page, 'Weiter zum Menü', 400)
        expect(page.get_by_role('alert')).to_be_focused()
        expect(page.get_by_label('Woche ab Montag', exact=True)).to_have_value('2026-09-01')
        assert page.locator('[name="template_context"]').input_value() == original
        assert page.locator('#planning-target [name="_csrf"]').input_value() == csrf
        for width, height in ((1440, 900), (390, 844), (320, 900)):
            page.set_viewport_size({'width': width, 'height': height})
            shot(page, f'invalid-week-{width}-{javascript}')
        page.get_by_label('Woche ab Montag', exact=True).fill(DAY)
        submit(page, 'Weiter zum Menü', 303)
        assert stored_state(admin_engine) == before
