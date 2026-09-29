"""UI22: real browser zoom throughout the native menu form journey."""
from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urljoin, urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_ux_browser import live_server as live_server  # noqa: F401
from test_admin_workflow_routes import DAY, WEEK, _login, _payload, _scope
from test_menu_template_binding_db import stored_state
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('javascript', [True, False])
def test_menu_editor_native_zoom_form_journey(
    browser, live_server, admin_app, admin_engine, family, profile, javascript, tmp_path,  # noqa: F811
):
    """200% keeps real errors, both submitters and clean cancellation usable."""
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, actor, profile)
    title = 'Saisonales Gemüse mit Kräutern, Kartoffeln und einer milden Sauce'
    description = 'Gedünstetes Herbstgemüse mit frischen Kräutern. Dazu Kartoffeln und eine milde Sauce.'
    note = 'Für die Ausgabe warm halten. Die Kräuter erst kurz vor dem Servieren dazugeben.'
    components = ['Gedünstetes Herbstgemüse mit frischen Kräutern', 'Kartoffeln mit milder Sauce']
    seed = {**_payload(staff=family == 'cafeteria'), 'title': title,
            'description': description, 'note': note,
            'assignments': [{'component_public_id': None, 'component_text': value} for value in components],
            'origins': [{'ingredient': 'Gemüse', 'country_code': 'CH', 'text': 'Gemüse: CH'},
                        {'ingredient': 'Kartoffeln', 'country_code': 'DE', 'text': 'Kartoffeln: DE'}]}
    assert persist_menu_item(admin_engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', seed, 0) == 1
    original = stored_state(admin_engine)
    editor_url = f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
    week_url = f'/admin/{family}?week={DAY}'
    measurements, posts, errors = [], [], []
    with browser.browser_type.launch_persistent_context(
        str(tmp_path / 'chromium-profile'), channel='chromium', headless=True,
        no_viewport=True, base_url=live_server, locale='de-CH', timezone_id='Europe/Zurich',
        java_script_enabled=javascript, reduced_motion='reduce',
        args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
    ) as context:
        page = context.pages[0]
        page.goto('chrome://settings/appearance')
        page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
        assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
        cookie = client.get_cookie('session')
        assert cookie is not None
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        assert page.goto(editor_url).status == 200
        cdp = context.new_cdp_session(page)
        form = page.locator('form[data-menu-editor]')
        primary = form.get_by_role('button', name='Menü speichern', exact=True)
        back = form.get_by_role('button', name='Speichern und zum Wochenplan', exact=True)
        cancel = form.get_by_role('link', name='Abbrechen', exact=True)
        title_field = page.get_by_label('Menüname', exact=True)
        note_field = page.get_by_label('Hinweis (auf dem Speiseplan sichtbar)', exact=True)

        def capture(stage, footer=False):
            page.evaluate('document.fonts.ready')
            script = '''() => {
                const box = el => el ? {x: el.getBoundingClientRect().x,
                    y: el.getBoundingClientRect().y, width: el.getBoundingClientRect().width,
                    height: el.getBoundingClientRect().height} : null;
                const root = document.documentElement, body = document.body;
                return {url: location.href, innerWidth, innerHeight, outerWidth, outerHeight,
                    dpr: devicePixelRatio, scrollX, scrollY, scrollWidth: root.scrollWidth,
                    rootZoom: getComputedStyle(root).zoom, bodyZoom: getComputedStyle(body).zoom,
                    rootTransform: getComputedStyle(root).transform,
                    bodyTransform: getComputedStyle(body).transform,
                    fine: matchMedia('(pointer: fine)').matches,
                    coarse: matchMedia('(pointer: coarse)').matches,
                    anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                    touch: navigator.maxTouchPoints, focus: box(document.activeElement),
                    tooltips: [...document.querySelectorAll('[role="tooltip"]')].map(el => el.textContent),
                    footer: box(document.querySelector('form[data-menu-editor] [data-sticky]')),
                    actions: [...document.querySelectorAll('form[data-menu-editor] [data-sticky] .btn')].map(box)};
            }'''
            before = page.evaluate(script)
            zoom = cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom']
            png = base64.b64decode(cdp.send('Page.captureScreenshot', {
                'format': 'png', 'captureBeyondViewport': False,
            })['data'], validate=True)
            (tmp_path / f'{stage}.png').write_bytes(png)
            after = page.evaluate(script)
            size = [int.from_bytes(png[16:20], 'big'), int.from_bytes(png[20:24], 'big')]
            proof = {'stage': stage, 'cdpZoom': zoom, 'before': before, 'after': after, 'pngSize': size}
            measurements.append(proof)
            (tmp_path / 'native-zoom.json').write_text(json.dumps(measurements, indent=2) + '\n')
            assert png[:8] == b'\x89PNG\r\n\x1a\n' and png[12:16] == b'IHDR'
            assert zoom == 2 and [before['innerWidth'], before['outerWidth'], before['dpr']] == [720, 1440, 2]
            assert before['rootZoom'] == before['bodyZoom'] == '1'
            assert before['rootTransform'] == before['bodyTransform'] == 'none'
            assert before['fine'] and not before['coarse'] and not before['anyCoarse'] and before['touch'] == 0
            assert before == after, proof
            assert abs(size[0] - before['innerWidth'] * before['dpr']) <= 2
            assert abs(size[1] - before['innerHeight'] * before['dpr']) <= 2
            assert before['scrollWidth'] <= before['innerWidth'] + 1
            if footer:
                bar = before['footer']
                assert len(before['actions']) == 3
                for index, box in enumerate(before['actions']):
                    assert box['width'] == box['height'] == 36
                    assert box['x'] >= bar['x'] - 1 and box['y'] >= bar['y'] - 1
                    assert box['x'] + box['width'] <= bar['x'] + bar['width'] + 1
                    assert box['y'] + box['height'] <= bar['y'] + bar['height'] + 1
                    for other in before['actions'][:index]:
                        assert (box['x'] + box['width'] <= other['x'] + 1 or
                                other['x'] + other['width'] <= box['x'] + 1 or
                                box['y'] + box['height'] <= other['y'] + 1 or
                                other['y'] + other['height'] <= box['y'] + 1)
            return before

        def tab_to(control):
            page.mouse.move(0, 0)
            expect(control).to_have_count(1)
            for _ in range(160):
                if control.evaluate('el => el === document.activeElement'):
                    break
                page.keyboard.press('Tab')
            else:
                pytest.fail('Target was not reachable within 160 native Tab presses')
            expect(control).to_be_focused()
            expect(control).to_be_visible()
            assert control.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
            geometry = control.bounding_box()
            viewport = page.evaluate('[innerWidth, innerHeight]')
            assert geometry['x'] >= -1 and geometry['y'] >= -1
            assert geometry['x'] + geometry['width'] <= viewport[0] + 1
            assert geometry['y'] + geometry['height'] <= viewport[1] + 1
            assert control.evaluate('''el => {
                const r = el.getBoundingClientRect();
                const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                return hit === el || el.contains(hit);
            }'''), 'Focused control is covered'
            tooltip_text = control.get_attribute('data-ui-tooltip')
            if javascript and tooltip_text:
                tooltip = page.get_by_role('tooltip')
                expect(tooltip).to_have_text([tooltip_text])
                expect(tooltip).to_be_visible()

        def fields():
            return form.evaluate('''el => {
                const values = {};
                for (const [key, value] of new FormData(el)) (values[key] ||= []).push(value);
                return values;
            }''')

        def submit(control, status, returning=False):
            expected = fields()
            assert expected['_csrf'] and expected['week'] == expected['day'] == [DAY]
            assert expected['meal'] == ['LUNCH'] and expected['option'] == ['MENU_1']
            assert expected['component_text'] == components
            assert expected['origin_ingredient'] == ['Gemüse', 'Kartoffeln']
            assert expected['origin_country_code'] == ['CH', 'DE']
            assert 'return_to' not in expected
            tab_to(control)
            capture(f'footer-before-{len(posts)}', footer=True)
            endpoint = live_server + f'/admin/{family}/menu' + ('?return_to=week' if returning else '')
            count = len(posts)
            with page.expect_navigation(wait_until='load') as navigation, page.expect_response(
                lambda response: response.request.method == 'POST' and response.url == endpoint
            ) as sent:
                page.keyboard.press('Enter')
            response = sent.value
            assert response.status == status and len(posts) == count + 1
            assert parse_qs(response.request.post_data, keep_blank_values=True) == expected
            assert navigation.value.status == (400 if status == 400 else 200)
            if status == 303:
                assert navigation.value.url == urljoin(live_server, response.headers['location'])
                if returning:
                    assert response.headers['location'] == week_url
                else:
                    assert urlsplit(page.url).path == f'/admin/{family}/menu'
            return expected

        try:
            capture('initial')
            assert stored_state(admin_engine) == original and not posts
            expect(title_field).to_have_value(title)
            for details in form.locator('details.admin-accordion, #sec-output-texts').all():
                if details.get_attribute('open') is None:
                    tab_to(details.locator(':scope > summary'))
                    page.keyboard.press('Enter')
                    expect(details).to_have_attribute('open', '')
            # Native text controls may scroll internally; labels/content must not be clipped.
            assert form.locator('.form-label:visible, .form-hint:visible, .card-title:visible').evaluate_all('''els =>
                els.every(el => {const style = getComputedStyle(el);
                    return style.webkitLineClamp === 'none' && el.scrollHeight <= el.clientHeight + 1 &&
                        el.scrollWidth <= el.clientWidth + 1;})''')
            for control, name in [(primary, 'Menü speichern'), (back, 'Speichern und zum Wochenplan'),
                                  (cancel, 'Abbrechen')]:
                expect(control).to_have_text('')
                expect(control).to_have_attribute('aria-label', name)
                expect(control).to_have_attribute('data-ui-tooltip', name)
            expect(primary).not_to_have_attribute('formaction', '')
            assert primary.get_attribute('formaction') is None
            expect(back).to_have_attribute('formaction', f'/admin/{family}/menu?return_to=week')
            expect(cancel).to_have_attribute('href', week_url)
            expect(note_field).to_have_value(note)
            expect(form.locator('[name="row_version"]')).to_have_value('1')
            title_field.fill('')
            invalid = submit(primary, 400)
            assert stored_state(admin_engine) == original
            assert fields() == invalid
            error = page.locator('.error-region[role="alert"]')
            expect(error).to_be_visible()
            expect(page.locator('#err-title')).to_be_visible()
            expect(title_field).to_have_attribute('aria-invalid', 'true')
            if javascript:
                expect(error).to_be_focused()
            else:
                tab_to(error.locator('a[href="#f-title"]'))
                page.keyboard.press('Enter')
                expect(title_field).to_be_in_viewport()
            capture('native400')
            title_field.fill(title + ' – korrigiert')
            valid = submit(primary, 303)
            assert valid['row_version'] == ['1']
            saved = stored_state(admin_engine)
            item = json.loads(saved['menu_items'][0])
            assert item['title'] == title + ' – korrigiert' and item['row_version'] == 2
            assert item['description'] == description and item['note'] == note
            expect(title_field).to_have_value(item['title'])
            expect(form.locator('[name="row_version"]')).to_have_value('2')
            capture('saved-editor')
            assert page.goto(editor_url).status == 200
            output = page.locator('#sec-output-texts')
            if output.get_attribute('open') is None:
                tab_to(output.locator(':scope > summary'))
                page.keyboard.press('Enter')
            note_field.fill(note + ' Ausgabe um zwölf Uhr.')
            returned = submit(back, 303, returning=True)
            assert returned['row_version'] == ['2']
            final = stored_state(admin_engine)
            item = json.loads(final['menu_items'][0])
            assert item['row_version'] == 3 and item['title'] == valid['title'][0]
            assert item['note'] == returned['note'][0] and final != saved
            assert page.url == live_server + week_url
            capture('saved-week')
            assert page.goto(editor_url).status == 200
            expect(note_field).to_have_value(item['note'])
            expect(form.locator('[name="row_version"]')).to_have_value('3')
            tab_to(cancel)
            capture('clean-cancel', footer=True)
            count = len(posts)
            with page.expect_navigation(wait_until='load') as cancelled:
                page.keyboard.press('Enter')
            assert cancelled.value.status == 200 and page.url == live_server + week_url
            assert len(posts) == count == 3 and stored_state(admin_engine) == final
            capture('cancelled-week')
            assert not errors
        finally:
            cdp.detach()
