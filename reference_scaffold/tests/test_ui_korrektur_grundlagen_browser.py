"""Correction-wave proof for list-first master data pages and native forms."""
from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qsl, urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

from test_master_data_browser import master_server  # noqa: F401
from test_master_data_routes import (  # noqa: F401
    app_engine,
    b3,
    create,
    installed_pg16,
    pg16,
    seeded_pg16,
)
from test_rendered_ui import browser  # noqa: F401


EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/density-foundations-reviewfix-0913'
VIEWPORTS = (
    (360, 844, 'mobile-360'),
    (1440, 900, 'desktop-1440'),
    (2560, 1440, 'wide-2560'),
    (1920, 1080, 'wide'),
    (1366, 768, 'desktop'),
    (1024, 768, 'desktop-1024'),
    (768, 1024, 'tablet'),
    (390, 844, 'mobile'),
    (320, 844, 'reflow-320'),
)


def test_wp06_measured_layout_and_native_forms(b3, master_server, tmp_path):  # noqa: F811
    """Real browser measurements, including the native no-JS rendering."""
    _, _, client, _ = b3
    detail = urlsplit(create(client, name='Messzutat')).path
    base, cookie = master_server
    measurements = []
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for javascript in (False, True):
                for width in (360, 768, 1024, 1440):
                    with instance.new_context(viewport={'width': width, 'height': 900},
                                              java_script_enabled=javascript) as context:
                        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
                        page = context.new_page()
                        for state, path in [('list', '/admin/grundlagen'), ('editor', detail)]:
                            page.goto(base + path, wait_until='networkidle')
                            metric = page.evaluate('''() => ({
                                height: document.documentElement.scrollHeight,
                                row: document.querySelector('.list-group-item')?.getBoundingClientRect().height,
                                primary: document.querySelectorAll('main .btn-primary').length,
                                open: document.querySelectorAll('main details[open]').length,
                                overflow: document.documentElement.scrollWidth > innerWidth + 1
                            })''')
                            measurements.append(dict(width=width, javascript=javascript, state=state, **metric))
                            assert not metric['overflow']
                            assert metric['primary'] == 1
                            expect(page.locator('.admin-statusbar')).to_be_visible()
                            if state == 'list':
                                assert metric['row'] < 100
                                expect(page.locator('[aria-label="Stammdatenbereiche"] .active')).to_have_attribute('aria-current', 'true')
                            else:
                                assert metric['height'] < (3337 if width == 360 else 2747 if width == 768 else 2188 if width == 1024 else 2041)
                                name = page.get_by_label('Name', exact=True)
                                name.scroll_into_view_if_needed()
                                assert name.evaluate('''el => {
                                    const box = el.getBoundingClientRect();
                                    return document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2) === el;
                                }''')
                                page.evaluate('scrollTo(0, 0)')
                            page.screenshot(path=str(tmp_path / f'{state}-{width}-{javascript}.png'), full_page=True)
                        forms = page.locator('main form[method="post"]').evaluate_all('''forms => forms.map(form => ({
                            action: new URL(form.action).pathname,
                            fields: [...new FormData(form)].map(([name, value]) =>
                                [name, ['_csrf', '_form_context'].includes(name) ? '<token>' : value])
                        }))''')
                        metadata = next(form for form in forms if form['action'].endswith('/metadaten'))
                        allergen_fields = [(key, value) for key, value in metadata['fields'] if key.startswith('allergen_')]
                        assert len(allergen_fields) == 14
                        assert all(value == 'absent' for _, value in allergen_fields)
                        assert next(form for form in forms if form['action'].endswith('/allergenpruefung'))['fields'][-1] == ['checked', 'true']
                        if width == 360 and not javascript:
                            print('WP06_FIELDS', json.dumps(forms, ensure_ascii=False))
                        summary = page.locator('#food-core-form details summary').last
                        summary.focus()
                        page.keyboard.press('Enter')
                        expect(page.get_by_label('Notiz', exact=True)).to_be_visible()
                        page.keyboard.press('Tab')
                        expect(page.get_by_label('Dichte in g/ml (optional)', exact=True)).to_be_focused()
                        focus = page.locator(':focus').evaluate('el => {const s = getComputedStyle(el); return [s.outlineStyle, s.boxShadow]}')
                        assert focus[0] != 'none' or focus[1] != 'none'
                        price = page.locator('form[action$="/preis"]')
                        expect(price.get_by_label('CHF je Einheit', exact=True)).not_to_be_visible()
                        price.locator('xpath=ancestor::details[1]').locator('summary').click()
                        expect(price.get_by_label('CHF je Einheit', exact=True)).to_be_visible()
                        expect(price.get_by_role('button', name='Speichern', exact=True)).not_to_have_class(re.compile('btn-primary'))
                        for control in price.locator('.form-control, .btn').all():
                            assert control.bounding_box()['height'] >= 48
                        _assert_no_horizontal_scroll(page)
            print('WP06_MEASUREMENTS', json.dumps(measurements))
            (tmp_path / 'measurements.json').write_text(json.dumps(measurements, indent=2))
            print('WP06_SCREENSHOTS', str(tmp_path))
        finally:
            instance.close()


def _prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    EVIDENCE.chmod(0o700)


@pytest.mark.parametrize('javascript', [False, True])
def test_wp06_allergen_payload_and_review_are_independent(b3, master_server, javascript):  # noqa: F811
    _, _, client, _ = b3
    path = urlsplit(create(client, name='Allergenvertrag')).path
    base, cookie = master_server
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            with instance.new_context(viewport={'width': 360, 'height': 900}, java_script_enabled=javascript) as context:
                context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
                page = context.new_page()
                page.goto(base + path)
                form = page.locator('form[action$="/metadaten"]')
                page.get_by_text('Allergene und Kostformen', exact=True).click()
                before = form.evaluate('form => [...new FormData(form)]')
                milk = form.locator('select[name="allergen_MILK"]')
                if javascript:
                    expect(milk).not_to_be_visible()
                    checkbox = form.locator('#allergen-milk')
                    checkbox.focus()
                    page.keyboard.press('Space')
                expect(milk).to_be_visible()
                milk.select_option('may_contain')
                with page.expect_request(lambda request: request.method == 'POST') as request:
                    with page.expect_response(lambda response: response.request.method == 'POST', timeout=60000) as outcome:
                        form.get_by_role('button').click(no_wait_after=True)
                assert outcome.value.status == 303
                fields = parse_qsl(request.value.post_data or '', keep_blank_values=True)
                assert fields == [(key, 'may_contain' if key == 'allergen_MILK' else value) for key, value in before]
                page.wait_for_load_state('networkidle')
                expect(page.locator('.admin-statusbar')).to_contain_text('Noch nicht bestätigt')
                expect(milk).to_be_visible()
                expect(milk).to_have_value('may_contain')
                milk.select_option('absent')
                with page.expect_response(lambda response: response.request.method == 'POST', timeout=60000) as outcome:
                    form.get_by_role('button').click(no_wait_after=True)
                assert outcome.value.status == 303
                page.wait_for_load_state('networkidle')
                expect(page.locator('.admin-statusbar')).to_contain_text('Allergenangaben nicht erfasst')
                expect(page.locator('.admin-statusbar')).to_contain_text('Noch nicht bestätigt')
                assert page.locator('.admin-statusbar-item--success').count() == 0
                _assert_no_horizontal_scroll(page)
        finally:
            instance.close()


def _screenshot(page, name: str) -> None:
    target = EVIDENCE / name
    page.screenshot(path=str(target), full_page=True)
    target.chmod(0o600)


def _assert_no_horizontal_scroll(page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


@pytest.mark.parametrize(('width', 'height', 'state'), VIEWPORTS)
def test_ingredient_list_is_first_full_width_and_visible(
    b3, master_server, browser, width, height, state,  # noqa: F811
):
    _, _, client, _ = b3
    create(client, name='Erste sichtbare Zutat')
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + '/admin/grundlagen', wait_until='networkidle')

        assert page.locator('nav[aria-label="Stammdatenbereiche"]').count() == 1
        assert page.locator('main .btn-primary').count() == 1
        expect(page.locator('main .btn-primary').first).to_contain_text('Anlegen')
        expect(page.locator('nav[aria-label="Stammdatenbereiche"] .icon use').first).to_have_attribute(
            'href', re.compile(r'tabler-')
        )
        first = page.locator('.grundlagen-list .list-group-item').first
        expect(first).to_be_visible()
        box = first.bounding_box()
        assert box is not None
        if width in {1366, 1440, 1920, 2560}:
            assert box['y'] + box['height'] <= height
        expect(page.locator('details').filter(has_text='Filter').first).not_to_have_attribute('open', '')
        _assert_no_horizontal_scroll(page)

        if width >= 1024:
            ratio = page.evaluate('''() => {
                const box = document.querySelector('.page-body > .container-xl');
                const list = document.querySelector('.grundlagen-list');
                const style = getComputedStyle(box);
                const inner = box.getBoundingClientRect().width
                    - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
                return list.getBoundingClientRect().width / inner;
            }''')
            assert ratio >= 0.95

        _prepare_evidence()
        _screenshot(page, f'liste-regulaer-{state}-{width}x{height}.png')

        page.goto(base + '/admin/grundlagen?q=zzzz-kein-treffer', wait_until='networkidle')
        expect(page.get_by_text('Keine passenden Zutaten', exact=True)).to_be_visible()
        expect(page.locator('details').filter(has_text='Filter').first).to_have_attribute('open', '')
        _assert_no_horizontal_scroll(page)
        _screenshot(page, f'liste-leer-{state}-{width}x{height}.png')


def test_ingredient_list_genuine_browser_zoom_200(
    b3, master_server, browser, tmp_path,  # noqa: F811
):
    _, _, client, _ = b3
    create(client, name='Erste sichtbare Zutat')
    base, cookie = master_server
    with TemporaryDirectory(prefix='grundlagen-native-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(
            profile,
            channel='chromium',
            headless=True,
            no_viewport=True,
            locale='de-CH',
            timezone_id='Europe/Zurich',
            reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            page.goto(base + '/admin/grundlagen', wait_until='networkidle')
            cdp = context.new_cdp_session(page)
            zoom = cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom']
            assert zoom == 2
            assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
            assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'

            assert page.locator('nav[aria-label="Stammdatenbereiche"]').count() == 1
            assert page.locator('main .btn-primary').count() == 1
            expect(page.locator('main .btn-primary').first).to_contain_text('Anlegen')
            expect(page.locator('nav[aria-label="Stammdatenbereiche"] .icon use').first).to_have_attribute(
                'href', re.compile(r'tabler-')
            )
            first = page.locator('.grundlagen-list .list-group-item').first
            expect(first).to_be_visible()
            expect(page.locator('details').filter(has_text='Filter').first).not_to_have_attribute('open', '')
            _assert_no_horizontal_scroll(page)
            _prepare_evidence()
            _screenshot(page, 'liste-regulaer-zoom-200-1440x900.png')
            proof = cdp.send('Page.getLayoutMetrics')
            proof['zoom'] = zoom
            proof['devicePixelRatio'] = 2
            (EVIDENCE / 'liste-regulaer-zoom-200-1440x900.cdp.json').write_text(json.dumps(proof, indent=2))

            # Verify zoom persists across page.goto for empty state too
            page.goto(base + '/admin/grundlagen?q=zzzz-kein-treffer', wait_until='networkidle')
            empty_zoom = cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom']
            assert empty_zoom == 2
            assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
            assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
            expect(page.get_by_text('Keine passenden Zutaten', exact=True)).to_be_visible()
            expect(page.locator('details').filter(has_text='Filter').first).to_have_attribute('open', '')
            _assert_no_horizontal_scroll(page)
            _screenshot(page, 'liste-leer-zoom-200-1440x900.png')
            empty_proof = cdp.send('Page.getLayoutMetrics')
            empty_proof['zoom'] = empty_zoom
            empty_proof['devicePixelRatio'] = 2
            (EVIDENCE / 'liste-leer-zoom-200-1440x900.cdp.json').write_text(json.dumps(empty_proof, indent=2))
            cdp.detach()


@pytest.mark.parametrize('javascript', [False, True])
def test_ingredient_form_keeps_native_payload_and_opens_on_error(
    b3, master_server, browser, javascript,  # noqa: F811
):
    base, cookie = master_server
    with browser.new_context(
        viewport={'width': 1366, 'height': 768},
        java_script_enabled=javascript,
        reduced_motion='reduce',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + '/admin/grundlagen/zutaten/neu')
        form_details = page.locator('main details').filter(has_text='Zutat anlegen').first
        expect(form_details).to_have_attribute('open', '')
        assert page.locator('main .btn-primary').count() == 1
        expect(page.locator('#food-core-form').get_by_role('button', name='Speichern', exact=True).locator('.icon use')).to_have_attribute(
            'href', re.compile(r'tabler-device-floppy')
        )
        page.get_by_label('Name', exact=True).fill('<unzulässig>')
        storage = page.get_by_label('Testlager', exact=True)
        storage.check()
        storage_id = storage.input_value()

        with page.expect_request(lambda request: request.method == 'POST') as submitted:
            with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
                page.locator('#food-core-form').get_by_role('button', name='Speichern', exact=True).click()

        assert outcome.value.status == 400
        request = submitted.value
        assert urlsplit(request.url).path == '/admin/grundlagen/zutaten/neu'
        payload = dict(parse_qsl(request.post_data or '', keep_blank_values=True))
        assert set(payload) == {
            '_csrf', '_form_context', 'name', 'base_unit_code', 'category_public_id',
            'density_g_per_ml', 'piece_weight_g', 'note', 'storage_location_public_ids',
            'prepared_recipe_choice',
        }
        assert payload['storage_location_public_ids'] == storage_id
        assert payload['prepared_recipe_choice'] == ''
        assert payload['name'] == '<unzulässig>'
        expect(form_details).to_have_attribute('open', '')
        expect(page.get_by_label('Name', exact=True)).to_have_value('<unzulässig>')
        expect(page.get_by_label('Name', exact=True) if javascript else page.locator('.error-region')).to_be_focused()
        _assert_no_horizontal_scroll(page)

        _prepare_evidence()
        _screenshot(page, f'zutat-fehler-js-{str(javascript).lower()}-1366x768.png')


def test_ingredient_statuses_and_secondary_actions_stay_separate(
    b3, master_server, browser,  # noqa: F811
):
    _, _, client, _ = b3
    path = urlsplit(create(client, name='Status Zutat')).path
    base, cookie = master_server
    with browser.new_context(viewport={'width': 390, 'height': 844}, java_script_enabled=False) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path)

        status = page.locator('.admin-statusbar')
        expect(status.get_by_text('Aktiv', exact=True)).to_be_visible()
        lagerort_line = status.locator('.admin-statusbar-item').filter(has_text='Lagerort')
        expect(lagerort_line).to_be_visible()
        assert 'Testlager' in lagerort_line.inner_text() or 'Lagerort fehlt' in lagerort_line.inner_text()
        expect(status.get_by_text('Allergenangaben nicht erfasst', exact=True)).to_be_visible()
        expect(status.get_by_text('Noch nicht bestätigt', exact=False)).to_be_visible()
        allergen_status = status.locator('.admin-statusbar-item').filter(has_text='Allergenprüfung')
        expect(allergen_status).to_have_class(re.compile(r'admin-statusbar-item--warning'))
        assert 'Version' not in status.inner_text()
        expect(page.get_by_role('button', name='Archivieren', exact=True)).not_to_be_visible()
        page.locator('main details').filter(has=page.locator('form[action$="/archivieren"], form[action$="/reaktivieren"]')).locator('summary').first.click()
        expect(page.get_by_role('button', name='Archivieren', exact=True)).to_be_visible()
        _assert_no_horizontal_scroll(page)

        _prepare_evidence()
        _screenshot(page, 'zutat-status-mobile-390x844.png')
