"""«Speichern und zum Wochenplan»: same data and CSRF; action carries return_to=week."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, expect

from test_admin_ux_browser import (  # noqa: F401
    _submit_menu, admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import DAY
from test_rendered_ui import _login


def _editor(family: str) -> str:
    return f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


def _submit_back(
    page: Page, family: str, status: int, name: str = 'Speichern und zum Wochenplan',
) -> dict[str, list[str]]:
    with page.expect_response(
        lambda response: response.request.method == 'POST' and f'/admin/{family}/menu' in response.url
    ) as submitted:
        page.get_by_role('button', name=name, exact=True).click()
    response = submitted.value
    request_url = urlsplit(response.url)
    assert request_url.path == f'/admin/{family}/menu'
    assert parse_qs(request_url.query) == {'return_to': ['week']}
    assert response.status == status
    page.wait_for_load_state()
    data = response.request.post_data
    assert data is not None
    return parse_qs(data, keep_blank_values=True)


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize(('width', 'height'), ((360, 780), (1280, 800)))
def test_save_and_back_posts_same_form_and_returns_to_week(
    page_context: Page, family: str, width: int, height: int,  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(_editor(family))
    back = page.get_by_role('button', name='Speichern und zum Wochenplan', exact=True)
    expect(back).to_be_visible()
    assert back.evaluate('el => el.form === el.closest("form[data-menu-editor]")')
    assert back.get_attribute('formaction') == f'/admin/{family}/menu?return_to=week'
    assert page.evaluate("matchMedia('(pointer: fine)').matches && navigator.maxTouchPoints === 0")
    box = back.bounding_box()
    assert box is not None and box['height'] == box['width'] == 36
    assert box['x'] + box['width'] <= width + 1
    assert page.locator('form[data-menu-editor]').get_attribute('action') == f'/admin/{family}/menu'

    page.get_by_label('Menüname', exact=True).fill('Zurück zur Woche')
    if family == 'cafeteria':
        page.locator('[name="internal_chf"]').fill('9.50')
        page.locator('[name="external_chf"]').fill('14.50')
    for mode in ('allergen', 'origin', 'label'):
        page.locator(f'[name="{mode}_mode"][value="auto"]').check()
    csrf = page.locator('form[data-menu-editor] [name="_csrf"]').input_value()
    payload = _submit_back(page, family, 303)
    assert payload['_csrf'] == [csrf]
    assert {key: payload[key] for key in ('week', 'day', 'meal', 'option', 'row_version', 'title')} == {
        'week': [DAY], 'day': [DAY], 'meal': ['LUNCH'], 'option': ['MENU_1'], 'row_version': ['0'],
        'title': ['Zurück zur Woche'],
    }
    assert 'return_to' not in payload
    landed = urlsplit(page.url)
    assert landed.path == f'/admin/{family}'
    assert parse_qs(landed.query) == {'week': [DAY]}
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')

    page.goto(_editor(family))
    expect(page.get_by_label('Menüname', exact=True)).to_have_value('Zurück zur Woche')
    expect(page.locator('form[data-menu-editor] [name="row_version"]')).to_have_value('1')


def test_save_and_back_error_keeps_editor_values_then_returns(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 820, 'height': 1180})
    page.goto(_editor('patienten'))
    page.get_by_label('Menüname', exact=True).fill('Fehler dann zurück')
    for summary in page.locator('details.admin-accordion:not([open]) > summary').all():
        summary.click()
    page.locator('[name="origin_mode"][value="manual"]').check()
    page.locator('[name="origin_ingredient"]').fill('Rind')
    payload = _submit_back(page, 'patienten', 400)
    assert payload['origin_ingredient'] == ['Rind']
    assert payload['origin_country_code'] == ['']
    expect(page.locator('.error-region[role="alert"]')).to_be_visible()
    expect(page.locator('.error-region[role="alert"]')).to_be_focused()
    expect(page.get_by_label('Menüname', exact=True)).to_have_value('Fehler dann zurück')
    expect(page.locator('[name="origin_ingredient"]')).to_have_value('Rind')
    assert page.locator('form[data-menu-editor]').get_attribute('action') == '/admin/patienten/menu'

    page.locator('[name="origin_country_code"]').select_option('CH')
    payload = _submit_back(page, 'patienten', 303)
    assert payload['origin_country_code'] == ['CH']
    assert urlsplit(page.url).path == '/admin/patienten'

    # The default submit still posts to the plain action and stays in the editor.
    page.goto(_editor('patienten'))
    output_texts = page.locator('#sec-output-texts')
    expect(output_texts).not_to_have_attribute('open', '')
    summary = output_texts.locator(':scope > summary')
    summary.focus()
    summary.press('Enter')
    expect(output_texts).to_have_attribute('open', '')
    note = page.get_by_label('Hinweis (auf dem Speiseplan sichtbar)', exact=True)
    expect(note).to_be_visible()
    note.fill('Normal gespeichert')
    _submit_menu(page)
    assert urlsplit(page.url).path == '/admin/patienten/menu'
    expect(output_texts).to_have_attribute('open', '')
    expect(note).to_be_visible()
    expect(note).to_have_value('Normal gespeichert')


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize('locale', ('de', 'en'))
@pytest.mark.parametrize('javascript', (True, False))
@pytest.mark.parametrize('width', (390, 1440))
def test_save_return_icon_locales_pointer_and_native_payload(
    browser, live_server, admin_app, admin_engine, family, locale, javascript, width, tmp_path: Path,  # noqa: F811
) -> None:
    admin_app.config['UI_LOCALE'] = locale
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    coarse = width == 390
    name = 'Speichern und zum Wochenplan' if locale == 'de' else 'Save and return to week'
    context = browser.new_context(
        base_url=live_server, java_script_enabled=javascript, has_touch=coarse,
        viewport={'width': width, 'height': 844 if coarse else 900}, reduced_motion='reduce',
    )
    cookie = client.get_cookie('session')
    assert cookie is not None
    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True}])
    try:
        page = context.new_page()
        errors, posts, measurements = [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        assert page.goto(_editor(family)).status == 200
        form = page.locator('form[data-menu-editor]')
        primary = form.locator('[data-sticky] .btn-primary')
        back = form.locator(f'[formaction="/admin/{family}/menu?return_to=week"]')
        cancel = form.locator('[data-semantic="actions.cancel"]')

        def capture(stage):
            back.scroll_into_view_if_needed()
            for moment in ('before', 'after'):
                state = page.evaluate('''() => ({
                    coarse: matchMedia('(pointer: coarse)').matches,
                    anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                    fine: matchMedia('(pointer: fine)').matches,
                    maxTouchPoints: navigator.maxTouchPoints,
                    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                    controls: [...document.querySelectorAll(
                        'form[data-menu-editor] [data-sticky] [type="submit"]'
                    )].map(el => {const r = el.getBoundingClientRect();
                        return {width: r.width, height: r.height, x: r.x};})
                })''')
                measurements.append({'stage': stage, 'moment': moment, 'state': state})
                (tmp_path / 'save-return-measurements.json').write_text(json.dumps(measurements, indent=2))
                assert state['coarse'] == state['anyCoarse'] == coarse
                assert state['fine'] is not coarse and state['maxTouchPoints'] == int(coarse)
                assert state['scrollWidth'] <= width + 1
                if moment == 'before':
                    page.screenshot(path=str(tmp_path / f'{family}-{locale}-{width}-{javascript}-{stage}.png'),
                                    full_page=False)
            return state

        state = capture('before-save')
        assert back.evaluate('el => el.tagName') == 'BUTTON'
        assert back.inner_text().strip() == ''
        expect(back).to_have_attribute('aria-label', name)
        expect(back).to_have_attribute('data-ui-tooltip', name)
        expect(back).to_have_attribute('data-semantic', 'actions.save')
        assert 'btn-primary' not in back.get_attribute('class').split()
        assert back.get_attribute('name') is None and back.get_attribute('value') is None
        expect(primary).to_have_attribute('aria-label', 'Menü speichern')
        assert primary.get_attribute('formaction') is None
        expect(form).to_have_attribute('action', f'/admin/{family}/menu')
        expect(cancel).to_have_attribute('href', f'/admin/{family}?week={DAY}')
        assert back.evaluate('el => el.form === el.closest("form[data-menu-editor]")')
        assert len(state['controls']) == 2
        primary_box, return_box = state['controls']
        assert primary_box['width'] == primary_box['height'] == (44 if coarse else 36)
        assert return_box['width'] == return_box['height'] == (44 if coarse else 36)
        for control in state['controls']:
            assert control['x'] + control['width'] <= width + 1

        page.mouse.move(0, 0)
        page.keyboard.press('Tab')
        back.focus()
        expect(back).to_be_focused()
        assert back.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        if javascript:
            tip = page.get_by_role('tooltip', name=name, exact=True)
            expect(tip).to_be_visible()
            back.press('Escape')
            expect(tip).to_be_hidden()
            expect(back).to_be_focused()
        else:
            expect(page.get_by_role('tooltip')).to_have_count(0)
        assert posts == []

        title = page.get_by_label('Menüname', exact=True)
        title.fill(f'{locale} <Menü> & Woche')
        for mode in ('allergen', 'origin', 'label'):
            value = 'auto' if javascript else 'manual'
            page.locator(f'[name="{mode}_mode"][value="{value}"]').check()
        if not javascript:
            # Native manual rows remain successful controls without JS mode synchronization.
            page.locator('[name="component_text"]').fill('Gemüse')
            page.locator('[name="origin_ingredient"]').fill('Gemüse')
            page.locator('[name="origin_country_code"]').select_option('CH')
        if family == 'cafeteria':
            page.locator('[name="internal_chf"]').fill('9.50')
            page.locator('[name="external_chf"]').fill('14.50')
        expected = form.evaluate('''el => {
            const result = {};
            for (const [key, value] of new FormData(el)) (result[key] ||= []).push(value);
            return result;
        }''')
        payload = _submit_back(page, family, 303, name)
        assert payload == expected
        assert payload['_csrf'] and payload['row_version'] == ['0']
        assert 'return_to' not in payload
        assert len(posts) == 1
        landed = urlsplit(page.url)
        assert landed.path == f'/admin/{family}' and parse_qs(landed.query) == {'week': [DAY]}

        assert page.goto(_editor(family)).status == 200
        expect(title).to_have_value(f'{locale} <Menü> & Woche')
        expect(form.locator('[name="row_version"]')).to_have_value('1')
        if family == 'cafeteria':
            expect(form.locator('[name="internal_chf"]')).to_have_value('9.50')
            expect(form.locator('[name="external_chf"]')).to_have_value('14.50')
        state = capture('saved')
        primary_box, return_box = state['controls']
        assert primary_box['width'] == primary_box['height'] == (44 if coarse else 36)
        assert return_box['width'] == return_box['height'] == (44 if coarse else 36)

        # Implicit Enter still selects the first, primary submit and stays in the editor.
        title.fill('Default speichern')
        with page.expect_response(lambda response: response.request.method == 'POST') as submitted:
            title.press('Enter')
        assert submitted.value.status == 303
        assert submitted.value.url == live_server + f'/admin/{family}/menu'
        page.wait_for_load_state()
        assert urlsplit(page.url).path == f'/admin/{family}/menu'
        expect(title).to_have_value('Default speichern')
        expect(form.locator('[name="row_version"]')).to_have_value('2')
        assert len(posts) == 2 and not errors
    finally:
        context.close()
