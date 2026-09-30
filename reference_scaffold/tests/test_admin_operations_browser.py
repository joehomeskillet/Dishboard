"""Native Tabler operations forms work with and without JavaScript."""
from __future__ import annotations

from pathlib import Path
import json
import re

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from test_admin_display_browser import _assert_controls, _context
from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server,
)
from test_admin_workflow_routes import _login

PATH = '/admin/bereiche-zeiten'


def _open_details(page, editor_id: str) -> None:
    details = page.locator(f'#{editor_id}')
    expect(details).to_have_count(1)
    if details.get_attribute('open') is None:
        page.locator(f'#{editor_id} > summary').click()
    expect(details).to_have_attribute('open', '')


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_native_operations_controls_save_focus_and_original_exception(
    browser, live_server, admin_app, admin_engine, width, javascript, tmp_path: Path,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with _context(browser, live_server, client, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': 1100})
        page.goto(PATH)
        current_links = page.get_by_role('link', name='Bereiche & Öffnungszeiten', exact=True, include_hidden=True)
        expect(current_links).to_have_count(1 if javascript else 2)
        for current_link in current_links.all():
            expect(current_link).to_have_attribute('aria-current', 'page')
        _assert_controls(page)
        assert page.locator('[style], [onclick], script:not([src])').count() == 0
        page.screenshot(path=str(tmp_path / f'operations-{width}-js-{javascript}.png'), full_page=True)
        _open_details(page, 'weekend-editor')
        page.locator('#allows_weekend').check()
        page.locator('#weekend-form').get_by_role('button', name=re.compile(r'.+ speichern$')).click()
        _open_details(page, 'weekend-editor')
        expect(page.locator('#allows_weekend')).to_be_checked()
        _open_details(page, 'schedule-editor-staff_guest')
        page.locator('#staff_guest-slot_6_LUNCH_state').select_option('open')
        page.locator('#staff_guest-slot_6_LUNCH_start').fill('11:30')
        page.locator('#staff_guest-slot_6_LUNCH_end').fill('13:30')
        page.locator('#schedule-staff_guest button[type="submit"]').click()
        _open_details(page, 'schedule-editor-staff_guest')
        expect(page.locator('#staff_guest-slot_6_LUNCH_start')).to_have_value('11:30')
        page.locator('#staff_guest-slot_6_LUNCH_end').fill('10:00')
        page.locator('#schedule-staff_guest button[type="submit"]').click()
        page.wait_for_load_state()
        expect(page.locator('#schedule-editor-staff_guest')).to_have_attribute('open', '')
        invalid = page.locator('#staff_guest-slot_6_LUNCH_end')
        expect(invalid).to_have_attribute('aria-invalid', 'true')
        expect(invalid).to_have_attribute('autofocus', '')
        focused = page.locator('.error-region[role="alert"]') if javascript else invalid
        expect(focused).to_be_focused()
        expect(page.locator('#staff_guest-slot_6_LUNCH_start')).to_have_value('11:30')
        assert focused.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.screenshot(path=str(tmp_path / f'operations-error-{width}-js-{javascript}.png'), full_page=True)
        page.goto(PATH)
        _open_details(page, 'exception-editor')
        page.locator('#exception-load-date').fill('2026-09-05')
        page.locator('#exception-load-meal').select_option('LUNCH')
        page.locator('#exception-load').get_by_role('button', name=re.compile(r'.+ öffnen$')).click()
        expect(page.locator('#exception-editor')).to_have_attribute('open', '')
        expect(page.locator('#exception-save input[name="row_version"]')).to_have_value('0')
        expect(page.locator('#service_start')).to_have_value('11:30')
        page.locator('#service_end').fill('14:00')
        _assert_controls(page)
        page.locator('#exception-save').get_by_role('button', name=re.compile(r'.+ speichern$')).click()
        _open_details(page, 'saved-exceptions')
        expect(page.locator('[data-kind="time"]')).to_be_visible()
        page.screenshot(path=str(tmp_path / f'operations-saved-{width}-js-{javascript}.png'), full_page=True)


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('width', [390, 1440])
def test_operations_overview_icons_preserve_context_and_native_forms(
    browser, live_server, admin_app, admin_engine, width, javascript, locale, tmp_path, monkeypatch,  # noqa: F811
):
    monkeypatch.setitem(admin_app.config, 'UI_LOCALE', locale)
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    with admin_engine.connect() as connection:
        timezone = connection.execute(text('SELECT timezone FROM cafeteria.locations WHERE active')).scalar_one()
    with browser.new_context(
        base_url=live_server, java_script_enabled=javascript, has_touch=width == 390,
        viewport={'width': width, 'height': 844 if width == 390 else 900}, reduced_motion='reduce',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        posts, errors, failures, measurements = [], [], [], []
        page.on('request', lambda req: posts.append(req) if req.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        assert page.goto(PATH).status == 200
        expect(page.locator('html')).to_have_attribute('lang', locale)
        page.evaluate('document.fonts.ready')
        rows = page.locator('#operations-overview tbody > tr')
        expect(rows).to_have_count(2)
        names = rows.locator('th[scope="row"] a').all_text_contents()
        expect(page.locator('.admin-statusbar-item').filter(
            has=page.get_by_text('Zeitzone', exact=True),
        )).to_contain_text(timezone)
        area_label = 'Bereich' if locale == 'de' else 'Area'
        if page.locator('.admin-statusbar-label').filter(has_text=re.compile(r'^\s*' + area_label + r'\s*$')).count():
            failures.append('redundant area header card')
        for code in ('staff_guest', 'patient'):
            form = page.locator(f'#schedule-{code}')
            missing = form.evaluate('''form => [...form.querySelectorAll('select[name$="_state"]')]
                .filter(field => field.value === 'open' &&
                    (!form.elements.namedItem(field.name.replace(/state$/, 'start')).value ||
                     !form.elements.namedItem(field.name.replace(/state$/, 'end')).value)).length''')
            warning = page.locator(f'.admin-statusbar-item:has(a[href="#schedule-{code}"])')
            expect(warning).to_have_count(1 if missing else 0)
            if missing:
                expect(warning.locator('a')).to_have_text(str(missing))
                expect(warning).to_contain_text('Zeiten nicht eingetragen')
            expect(form.locator('input[name="_csrf"]')).not_to_have_value('')
            expect(form.locator('input[name="revision"]')).to_have_value(re.compile(r'^\d+$'))
        forms = page.locator('main form')
        form_state = '''forms => forms.map(f => ({action: f.getAttribute('action'),
            method: f.getAttribute('method'), fields: [...new FormData(f)]}))'''
        before = forms.evaluate_all(form_state)
        section_titles = page.locator('.admin-disclosure--card > summary').all_text_contents()

        def capture(stage):
            for moment in ('before', 'after'):
                if moment == 'after':
                    page.screenshot(path=str(tmp_path / f'operations-{stage}.png'), full_page=False)
                state = page.evaluate('''() => ({coarse: matchMedia('(pointer: coarse)').matches,
                    anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                    fine: matchMedia('(pointer: fine)').matches, maxTouchPoints: navigator.maxTouchPoints,
                    innerWidth, scrollWidth: document.documentElement.scrollWidth,
                    summaries: [...document.querySelectorAll('.operations-overview-details > summary')]
                        .map(el => ({name: el.getAttribute('aria-label'), text: el.textContent.trim(),
                            width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height,
                            minHeight: getComputedStyle(el).minHeight, padding: getComputedStyle(el).padding}))})''')
                measurements.append({'stage': stage, 'moment': moment, 'state': state})
                (tmp_path / 'operations-measurements.json').write_text(json.dumps(measurements, ensure_ascii=False, indent=2))
                coarse = width == 390
                assert (state['coarse'], state['anyCoarse'], state['fine']) == (coarse, coarse, not coarse), state
                assert (state['maxTouchPoints'] > 0) is coarse and state['innerWidth'] == width, state
                assert state['scrollWidth'] <= width + 1, state
                size = 44 if coarse else 36
                for actual in state['summaries']:
                    if (actual['width'], actual['height']) != (size, size):
                        failures.append({'stage': stage, 'moment': moment, 'expected': size, 'actual': actual})

        capture('initial')
        for index, name in enumerate(names):
            details = rows.nth(index).locator('.operations-overview-details')
            summary = details.locator(':scope > summary')
            expected = (f'{name}: Details ein- oder ausklappen' if locale == 'de'
                        else f'Expand or collapse details: {name}')
            actual = {'text': summary.inner_text().strip(), 'name': summary.get_attribute('aria-label'),
                      'tooltip': summary.get_attribute('data-ui-tooltip')}
            if actual != {'text': '', 'name': expected, 'tooltip': expected}:
                failures.append({'expected_name': expected, 'actual': actual})
            if summary.get_attribute('data-semantic') != 'ui.disclosure.details':
                failures.append('missing shared disclosure semantic')
            expect(summary.locator('a, button, input')).to_have_count(0)
            expect(details).not_to_have_attribute('open', '')
            summary.scroll_into_view_if_needed()
            summary.focus()
            expect(summary).to_be_focused()
            assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
            if javascript and summary.get_attribute('data-ui-tooltip'):
                tooltip = page.get_by_role('tooltip', name=expected, exact=True)
                expect(tooltip).to_be_visible()
                summary.press('Escape')
                expect(tooltip).to_be_hidden()
                expect(details).not_to_have_attribute('open', '')
            summary.press('Enter')
            expect(details).to_have_attribute('open', '')
            expect(details.locator('ul')).to_be_visible()
            capture(f'{index}-opened')
            summary.press('Space')
            expect(details).not_to_have_attribute('open', '')
            capture(f'{index}-closed')
            assert forms.evaluate_all(form_state) == before
            assert page.locator('.admin-disclosure--card > summary').all_text_contents() == section_titles
            assert not posts and not errors
        assert not failures, failures


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('width', [390, 1440])
def test_operations_notice_icons_keep_context_labels_and_native_forms(
    browser, live_server, admin_app, admin_engine, width, javascript, locale, tmp_path, monkeypatch,  # noqa: F811
):
    """Notice disclosures identify their slot and retain native closed form values."""
    from urllib.parse import parse_qs

    monkeypatch.setitem(admin_app.config, 'UI_LOCALE', locale)
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    with admin_engine.connect() as connection:
        services_before = connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one()
    with browser.new_context(
        base_url=live_server, java_script_enabled=javascript, has_touch=width == 390,
        viewport={'width': width, 'height': 844 if width == 390 else 900}, reduced_motion='reduce',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        posts, errors, failures, measurements, names = [], [], [], [], []
        page.on('request', lambda req: posts.append(req) if req.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        form_state = '''form => ({action: form.getAttribute('action'), method: form.getAttribute('method'),
            fields: Object.fromEntries(new FormData(form))})'''

        def capture(stage, summary):
            summary.scroll_into_view_if_needed()
            for moment in ('before', 'after'):
                if moment == 'after':
                    page.screenshot(path=str(tmp_path / f'notice-{stage}.png'), full_page=False)
                state = summary.evaluate('''el => ({coarse: matchMedia('(pointer: coarse)').matches,
                    anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                    fine: matchMedia('(pointer: fine)').matches, maxTouchPoints: navigator.maxTouchPoints,
                    innerWidth, scrollWidth: document.documentElement.scrollWidth,
                    width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height})''')
                measurements.append({'stage': stage, 'moment': moment, 'state': state})
                (tmp_path / 'notice-measurements.json').write_text(json.dumps(measurements, indent=2))
                coarse = width == 390
                assert (state['coarse'], state['anyCoarse'], state['fine']) == (coarse, coarse, not coarse), state
                assert (state['maxTouchPoints'] > 0) is coarse and state['innerWidth'] == width, state
                assert state['scrollWidth'] <= width + 1, state
                size = 44 if coarse else 36
                if (state['width'], state['height']) != (size, size):
                    failures.append({'stage': stage, 'expected_size': size, 'actual': state})

        def exercise(details, object_name, stage):
            summary = details.locator(':scope > summary')
            field = details.locator('input')
            form = details.locator('xpath=ancestor::form')
            expected = (f'{object_name}: Weitere Optionen ein- oder ausklappen' if locale == 'de'
                        else f'Expand or collapse more options: {object_name}')
            names.append(expected)
            actual = {'text': summary.inner_text().strip(), 'name': summary.get_attribute('aria-label'),
                      'tooltip': summary.get_attribute('data-ui-tooltip'),
                      'semantic': summary.get_attribute('data-semantic')}
            if actual != {'text': '', 'name': expected, 'tooltip': expected,
                          'semantic': 'ui.disclosure.more_options'}:
                failures.append({'stage': stage, 'expected_name': expected, 'actual': actual})
            expect(summary.locator('use')).to_have_attribute('href', re.compile(r'#tabler-chevron-right$'))
            expect(summary.locator('a, button, input')).to_have_count(0)
            expect(details).not_to_have_attribute('open', '')
            before, post_count = form.evaluate(form_state), len(posts)
            capture(stage + '-closed', summary)
            page.keyboard.press('Tab')
            summary.focus()
            expect(summary).to_be_focused()
            assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
            if javascript and summary.get_attribute('data-ui-tooltip'):
                tooltip = page.get_by_role('tooltip', name=expected, exact=True)
                expect(tooltip).to_be_visible()
                summary.press('Escape')
                expect(tooltip).to_be_hidden()
                expect(details).not_to_have_attribute('open', '')
            summary.press('Enter')
            expect(details).to_have_attribute('open', '')
            expect(field).to_be_visible()
            label = details.locator(f'label[for="{field.get_attribute("id")}"]')
            expect(label).to_have_text('Hinweis')
            if width == 390 or stage.startswith('exception'):
                if not label.is_visible():
                    failures.append({'stage': stage, 'missing_visible_notice_label': True})
            if width == 390 and stage.startswith('schedule'):
                for cell in details.locator('xpath=ancestor::tr').locator('td[data-label]').all():
                    if cell.evaluate("el => getComputedStyle(el, '::before').display") != 'none':
                        failures.append({'stage': stage, 'duplicate_mobile_label': cell.get_attribute('data-label')})
            capture(stage + '-open', summary)
            assert form.evaluate(form_state) == before
            field.fill('Notiz "A&B" bleibt erhalten')
            entered = form.evaluate(form_state)
            summary.focus()
            summary.press('Space')
            expect(details).not_to_have_attribute('open', '')
            assert form.evaluate(form_state) == entered
            expect(field).to_have_value('Notiz "A&B" bleibt erhalten')
            assert len(posts) == post_count
            return summary, field

        for profile in ('staff_guest', 'patient'):
            assert page.goto(PATH).status == 200
            expect(page.locator('html')).to_have_attribute('lang', locale)
            page.evaluate('document.fonts.ready')
            section_titles = page.locator('.admin-disclosure--card > summary').all_text_contents()
            area = page.locator(f'#operations-overview th a[href="#schedule-{profile}"]').inner_text()
            _open_details(page, f'schedule-editor-{profile}')
            form = page.locator(f'#schedule-{profile}')
            details = form.locator('tr').filter(has=page.locator(f'#{profile}-slot_1_LUNCH_notice')).locator('.operations-notice')
            summary, field = exercise(details, f'{area} · Montag · Mittag · Hinweis', 'schedule-' + profile)
            assert page.locator('.admin-disclosure--card > summary').all_text_contents() == section_titles
            summary.press('Enter')
            invalid_note = 'x' * 201
            field.fill(invalid_note)
            summary.focus()
            summary.press('Space')
            submitted = form.evaluate(form_state)
            with page.expect_response(lambda response: response.request.method == 'POST'
                                      and response.url == live_server + PATH) as response:
                form.locator('button[type="submit"]').click()
            assert response.value.status == 400
            payload = parse_qs(response.value.request.post_data, keep_blank_values=True)
            assert payload == {key: [value] for key, value in submitted['fields'].items()}
            expect(page.locator(f'#schedule-editor-{profile}')).to_have_attribute('open', '')
            expect(details).to_have_attribute('open', '')
            expect(field).to_have_value(invalid_note)
            expect(field).to_have_attribute('aria-invalid', 'true')
            expect(page.locator(f'#{profile}-slot_1_LUNCH_notice-error')).to_be_visible()
            expect(form.locator('[name=revision]')).to_have_value(submitted['fields']['revision'])
            capture('schedule-' + profile + '-error', summary)

            assert page.goto(PATH).status == 200
            _open_details(page, 'exception-editor')
            load_id = 'exception-load' if profile == 'staff_guest' else 'exception-load-patient'
            load_form = page.locator('#' + load_id)
            load_form.locator('[name=date]').fill('2026-09-28')
            load_form.locator('[name=meal]').select_option('LUNCH')
            with page.expect_response(lambda response: response.request.method == 'POST'
                                      and response.url == live_server + PATH) as response:
                load_form.locator('button[type="submit"]').click()
            assert response.value.status == 200
            exception = page.locator('#exception-save')
            expect(exception.locator('[name=profile]')).to_have_value(profile)
            expect(exception.locator('[name=date]')).to_have_value('2026-09-28')
            expect(exception.locator('[name=meal]')).to_have_value('LUNCH')
            expect(exception.locator('[name=row_version]')).to_have_value('0')
            for name in ('_csrf', 'loaded'):
                expect(exception.locator(f'[name={name}]')).not_to_have_value('')
            exercise(exception.locator('.operations-notice'),
                     f'{area} · 2026-09-28 · Mittag · Hinweis', 'exception-' + profile)
            expect(exception.get_by_role('heading', name=f'{area} · 2026-09-28 · Mittag', exact=True)).to_be_visible()
        assert len(names) == len(set(names)) == 4
        assert len(posts) == 4 and not errors
        with admin_engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_services')).scalar_one() == services_before
        assert not failures, failures
