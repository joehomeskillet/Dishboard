"""Menu editor on the Tabler admin base: geometry matrix, sticky save bar, dynamic rows, errors, modes."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from test_admin_ux_browser import (  # noqa: F401
    _submit_menu, admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import DAY
from test_rendered_ui import PATIENT_FORBIDDEN

MATRIX = ((360, 780), (768, 1024), (820, 1180), (1024, 768), (1199, 800), (1200, 800), (1280, 800))
CONTROLS = 'input:not([type="hidden"]), select, textarea, button, a.btn, summary'


def _editor(family: str) -> str:
    return f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


def _open_sections(page: Page) -> None:
    for summary in page.locator('details.admin-accordion:not([open]) > summary').all():
        summary.click()


def _box(locator) -> dict[str, float]:
    box = locator.bounding_box()
    assert box is not None
    return box


def _settle(page: Page) -> None:
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_editor_viewport_matrix_split_touch_and_sticky_bar(page_context: Page, family: str) -> None:  # noqa: F811
    page = page_context
    for width, height in MATRIX:
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(_editor(family))
        assert response is not None and response.status == 200
        assert page.locator('link[href$="admin-menu-editor.css"]').count() == 1
        assert page.locator('[style], script:not([src])').count() == 0
        main = page.locator('main#main-content')
        expect(main).to_have_attribute('data-family', family)
        expect(main).to_have_attribute('data-week', DAY)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width

        toggle = page.get_by_role('button', name='Menü', exact=True)
        if width < 1200:
            expect(toggle).to_be_visible()
        else:
            expect(toggle).to_be_hidden()

        form = page.locator('form[data-menu-editor]')
        review = page.locator('#review')
        form_box, review_box = _box(form), _box(review)
        if width >= 1200:
            assert review_box['x'] >= form_box['x'] + form_box['width'] - 1, width
            assert abs(review_box['y'] - form_box['y']) < 8, width
        else:
            assert review_box['y'] >= form_box['y'] + form_box['height'] - 1, width
            assert review_box['width'] >= form_box['width'] - 1

        _open_sections(page)
        for control in main.locator(CONTROLS).all():
            if control.evaluate('el => el.matches("input[type=checkbox], input[type=radio]")'):
                control = control.locator('xpath=ancestor::label[1]')
            box = control.bounding_box()
            if box is None or not box['width']:
                continue
            assert box['height'] >= 48, (width, control.evaluate('el => el.outerHTML'))
            assert box['x'] + box['width'] <= width + 1, (width, control.evaluate('el => el.outerHTML'))

        bar = form.locator('[data-sticky]')
        page.evaluate('window.scrollTo(0, 0)')
        bar_box = _box(bar)
        assert 0 <= bar_box['y'] and bar_box['y'] + bar_box['height'] <= height + 1, (width, bar_box)
        assert bar.evaluate('el => getComputedStyle(el).position') == 'sticky'
        primary = bar.get_by_role('button', name='Speichern', exact=True)
        expect(primary).to_have_class(re.compile(r'\bbtn-primary\b'))
        for button in bar.locator('.btn').all():
            button_box = _box(button)
            assert button_box['x'] >= bar_box['x'] - 1 and button_box['x'] + button_box['width'] <= width + 1
        if width == 360:
            assert bar_box['height'] >= 2 * 48, 'Save bar must wrap at 360 px instead of overflowing.'
        dense = bar.get_by_label('Kompakte Ansicht', exact=True)
        dense_label = dense.locator('xpath=ancestor::label[1]')
        expect(dense_label).to_have_class(re.compile(r'\bform-check\b'))
        assert _box(dense_label)['height'] >= 48

        page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
        _settle(page)
        bar_box = _box(bar)
        last_section = form.locator('details.admin-accordion').last
        last_box = _box(last_section)
        assert last_box['y'] + last_box['height'] <= bar_box['y'] + 1, 'Save bar covers the last section.'
        if width < 1200:
            review_box = _box(review)
            assert review_box['y'] >= bar_box['y'] + bar_box['height'] - 1, 'Save bar covers the review panel.'

        output = os.environ.get('TABLER_PROOF_DIR')
        if output:
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(directory / f'{family}-menu-editor-{width}x{height}.png'), full_page=True)


def test_editor_keyboard_focus_stays_clear_of_save_bar(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 360, 'height': 780})
    page.goto(_editor('patienten'))
    _open_sections(page)
    for mode in ('allergen', 'origin', 'label'):
        page.locator(f'[name="{mode}_mode"][value="manual"]').check()
    page.get_by_label('Titel', exact=True).focus()
    seen = 0
    for _ in range(120):
        page.keyboard.press('Tab')
        _settle(page)
        clear = page.evaluate('''() => {
            const active = document.activeElement;
            const form = document.querySelector('form[data-menu-editor]');
            const bar = form.querySelector('[data-sticky]');
            if (!form.contains(active)) return 'outside';
            if (bar.contains(active)) return 'bar';
            const field = active.getBoundingClientRect();
            const box = bar.getBoundingClientRect();
            if (getComputedStyle(bar).position !== 'sticky' || box.top >= innerHeight) return 'clear';
            return field.bottom <= box.top + 1 && field.top >= 0 ? 'clear' : `covered:${active.outerHTML}`;
        }''')
        if clear == 'outside':
            break
        seen += 1
        assert clear in ('clear', 'bar'), clear
    assert seen > 20, 'Keyboard walk did not traverse the editor form.'

    # Small visual viewports (landscape phone, resized layout viewport with keyboard) drop sticky.
    page.set_viewport_size({'width': 360, 'height': 400})
    assert page.locator('form[data-menu-editor] [data-sticky]').evaluate('el => getComputedStyle(el).position') == 'static'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def test_dynamic_rows_have_unique_ids_labeled_controls_and_ordered_payload(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 360, 'height': 780})
    page.goto(_editor('patienten'))
    page.get_by_label('Titel', exact=True).fill('Reihenfolge')
    add = page.get_by_role('button', name='Komponente hinzufügen')
    for index, text in enumerate(('Erste', 'Zweite', 'Dritte')):
        if index:
            add.click()
        page.locator('[name="component_text"]').nth(index).fill(text)
    rows = page.locator('#components-list .component-row')
    expect(rows).to_have_count(3)
    expect(rows.nth(2).locator('legend')).to_have_text('Komponente 3')
    rows.nth(2).get_by_role('button', name='Nach oben').click()
    expect(page.locator('[name="component_text"]').nth(1)).to_have_value('Dritte')
    expect(rows.nth(1).get_by_role('button', name='Nach oben')).to_be_focused()
    rows.nth(0).get_by_role('button', name='Komponente entfernen').click()
    expect(rows).to_have_count(2)
    expect(rows.nth(0).locator('legend')).to_have_text('Komponente 1')
    expect(rows.nth(1).locator('legend')).to_have_text('Komponente 2')

    _open_sections(page)
    page.locator('[name="origin_mode"][value="manual"]').check()
    page.get_by_role('button', name='Herkunft hinzufügen').click()
    origin_rows = page.locator('#origins-list .origin-row')
    expect(origin_rows).to_have_count(2)
    for index, (ingredient, country) in enumerate((('Rind', 'CH'), ('Reis', 'IT'))):
        page.locator('[name="origin_ingredient"]').nth(index).fill(ingredient)
        page.locator('[name="origin_country_code"]').nth(index).select_option(country)
    country = page.locator('[name="origin_country_code"]').first
    expect(country).to_have_class(re.compile(r'\bform-select\b'))
    assert country.locator('option[value="CH"]').inner_text().strip() not in ('', 'CH')
    assert country.locator('option').first.get_attribute('value') == ''

    ids = page.locator('form[data-menu-editor] [id]').evaluate_all('els => els.map(el => el.id)')
    assert len(ids) == len(set(ids)), sorted(id_ for id_ in ids if ids.count(id_) > 1)
    assert {'component-0-id', 'component-1-text', 'origin-1-ingredient', 'origin-1-country'} <= set(ids)
    dangling = page.locator('form[data-menu-editor] label[for]').evaluate_all(
        'els => els.map(el => el.htmlFor).filter(id => !document.getElementById(id))',
    )
    assert dangling == []
    for name in ('Komponente hinzufügen', 'Komponente entfernen', 'Nach oben', 'Nach unten', 'Herkunft hinzufügen', 'Herkunft entfernen'):
        assert page.get_by_role('button', name=name).count() >= 1, name

    payload = _submit_menu(page)
    assert payload['component_text'] == ['Dritte', 'Zweite']
    assert payload['component_public_id'] == ['', '']
    assert payload['origin_ingredient'] == ['Rind', 'Reis']
    assert payload['origin_country_code'] == ['CH', 'IT']
    assert not any(name.endswith('[]') for name in payload)
    page.reload()
    expect(page.locator('[name="component_text"]').nth(0)).to_have_value('Dritte')
    expect(page.locator('[name="component_text"]').nth(1)).to_have_value('Zweite')


def test_field_error_opens_only_affected_accordion_and_summary_links_to_field(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 1024, 'height': 768})
    page.goto(_editor('patienten'))
    page.get_by_label('Titel', exact=True).fill('Fehlerfall')
    origin = page.locator('details[data-mode-section="origin"]')
    _open_sections(page)
    # Unsaved cells prefill every mode as manual; only origin stays manual for this error case.
    page.locator('[name="allergen_mode"][value="auto"]').check()
    page.locator('[name="label_mode"][value="auto"]').check()
    page.locator('[name="origin_mode"][value="manual"]').check()
    expect(origin.locator('[data-mode-badge]')).to_have_text('manuell festgelegt')
    page.locator('[name="origin_ingredient"]').fill('Rind')
    payload = _submit_menu(page, 400)
    assert payload['origin_country_code'] == ['']

    assert origin.get_attribute('open') is not None
    assert page.locator('details[data-mode-section="allergen"]').get_attribute('open') is None
    assert page.locator('details[data-mode-section="label"]').get_attribute('open') is None
    field = page.locator('[name="origin_country_code"]')
    expect(field).to_be_focused()
    expect(field).to_have_attribute('aria-invalid', 'true')
    expect(field).to_have_class(re.compile(r'\bis-invalid\b'))
    expect(field).to_have_attribute('aria-describedby', 'origin-0-country-error')
    expect(page.locator('#origin-0-country-error')).to_be_visible()
    expect(page.locator('[name="origin_mode"][value="manual"]')).to_be_checked()
    expect(page.get_by_label('Titel', exact=True)).to_have_value('Fehlerfall')

    summary = page.locator('.error-region[role="alert"]')
    expect(summary).to_have_class(re.compile(r'\balert-danger\b'))
    link = summary.locator('a[data-error-link]')
    expect(link).to_have_attribute('href', '#origin-0-country')
    origin.evaluate('el => el.removeAttribute("open")')
    link.click()
    assert origin.get_attribute('open') is not None
    expect(field).to_be_focused()
    expect(summary.locator('button', has_text='Erneut versuchen')).to_be_visible()


def test_modes_and_accordion_state_survive_save_and_reload(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 820, 'height': 1180})
    page.goto(_editor('patienten'))
    page.get_by_label('Titel', exact=True).fill('Modus')
    # Unsaved cells prefill every mode as manual, so all accordions start open.
    for key in ('allergen', 'origin', 'label'):
        assert page.locator(f'details[data-mode-section="{key}"]').get_attribute('open') is not None
        expect(page.locator(f'details[data-mode-section="{key}"] [data-mode-badge]')).to_have_text('manuell festgelegt')
        page.locator(f'[name="{key}_mode"][value="auto"]').check()
        expect(page.locator(f'details[data-mode-section="{key}"] [data-mode-badge]')).to_have_text('automatisch geerbt')
    _submit_menu(page)
    page.reload()
    for key in ('allergen', 'origin', 'label'):
        assert page.locator(f'details[data-mode-section="{key}"]').get_attribute('open') is None
        expect(page.locator(f'[name="{key}_mode"][value="auto"]')).to_be_checked()
    allergen = page.locator('details[data-mode-section="allergen"]')
    allergen.locator('summary').click()
    page.locator('[name="allergen_mode"][value="manual"]').check()
    page.locator('[name="allergen_code"][value="MILK"]').check()
    payload = _submit_menu(page)
    assert payload['allergen_mode'] == ['manual']
    assert payload['origin_mode'] == ['auto']
    assert payload['label_mode'] == ['auto']
    assert payload['allergen_code'] == ['MILK']

    page.reload()
    assert allergen.get_attribute('open') is not None
    expect(allergen.locator('[data-mode-badge]')).to_have_text('manuell festgelegt')
    expect(page.locator('[name="allergen_mode"][value="manual"]')).to_be_checked()
    expect(page.locator('[name="allergen_code"][value="MILK"]')).to_be_checked()
    for key in ('origin', 'label'):
        assert page.locator(f'details[data-mode-section="{key}"]').get_attribute('open') is None
        expect(page.locator(f'[name="{key}_mode"][value="auto"]')).to_be_checked()

    page.locator('[name="allergen_mode"][value="auto"]').check()
    expect(allergen.locator('[data-mode-badge]')).to_have_text('automatisch geerbt')
    expect(page.locator('[name="allergen_code"][value="MILK"]')).to_be_disabled()
    payload = _submit_menu(page)
    assert 'allergen_code' not in payload
    page.reload()
    assert allergen.get_attribute('open') is None


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_prices_only_for_staff_and_compact_view_keeps_targets(page_context: Page, family: str) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 360, 'height': 780})
    page.goto(_editor(family))
    prices = page.locator('[name="internal_chf"], [name="external_chf"]')
    if family == 'cafeteria':
        expect(prices).to_have_count(2)
        expect(page.get_by_label('Mitarbeitende CHF', exact=True)).to_be_visible()
        expect(page.get_by_label('Externe CHF', exact=True)).to_be_visible()
    else:
        expect(prices).to_have_count(0)
        assert PATIENT_FORBIDDEN.search(page.content()) is None

    dense = page.get_by_label('Kompakte Ansicht', exact=True)
    dense.check()
    expect(page.locator('main#main-content')).to_have_attribute('data-state', 'dense')
    _open_sections(page)
    for control in page.locator(f'main#main-content :is({CONTROLS})').all():
        if control.evaluate('el => el.matches("input[type=checkbox], input[type=radio]")'):
            control = control.locator('xpath=ancestor::label[1]')
        box = control.bounding_box()
        if box and box['width']:
            assert box['height'] >= 48, control.evaluate('el => el.outerHTML')
    page.reload()
    expect(page.locator('main#main-content')).to_have_attribute('data-state', 'dense')
    page.get_by_label('Kompakte Ansicht', exact=True).uncheck()
    expect(page.locator('main#main-content')).not_to_have_attribute('data-state', 'dense')


def test_primary_button_states_keep_brand_colours(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 1280, 'height': 800})
    page.goto(_editor('cafeteria'))
    save = page.locator('form[data-menu-editor] [data-sticky] button.btn-primary')
    resolve = '''([name]) => {
        const probe = document.createElement('span');
        probe.style.color = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        document.body.appendChild(probe);
        const value = getComputedStyle(probe).color;
        probe.remove();
        return value;
    }'''
    brand = page.evaluate(resolve, ['--sh-primary'])
    brand_hover = page.evaluate(resolve, ['--sh-primary-2'])
    assert brand != brand_hover
    style = 'el => [getComputedStyle(el).backgroundColor, getComputedStyle(el).borderColor, getComputedStyle(el).color]'
    background, _, colour = save.evaluate(style)
    assert background == brand
    assert colour == 'rgb(255, 255, 255)'
    save.hover()
    background, border, colour = save.evaluate(style)
    assert background == brand_hover, background
    assert border == brand_hover, border
    assert colour == 'rgb(255, 255, 255)'
    page.mouse.move(0, 0)
    page.get_by_label('Titel', exact=True).focus()
    for _ in range(80):
        page.keyboard.press('Tab')
        if page.evaluate('() => document.activeElement.matches("[data-sticky] button.btn-primary")'):
            break
    expect(save).to_be_focused()
    focus = save.evaluate('el => ({outline: getComputedStyle(el).outlineStyle, width: getComputedStyle(el).outlineWidth, colour: getComputedStyle(el).outlineColor, shadow: getComputedStyle(el).boxShadow, bg: getComputedStyle(el).backgroundColor})')
    assert focus['outline'] != 'none' and float(focus['width'].rstrip('px')) >= 2
    assert focus['colour'] == brand
    assert brand in focus['shadow'] or brand_hover in focus['shadow'] or focus['bg'] in (brand, brand_hover)
    assert 'rgb(5, 100, 188)' not in focus['shadow']
    # Active: mouse down keeps the bordeaux scale.
    box = save.bounding_box()
    assert box is not None
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.mouse.down()
    active = save.evaluate('el => getComputedStyle(el).backgroundColor')
    page.mouse.move(0, 0)  # release outside the button so no click submits the form
    page.mouse.up()
    assert active in (brand, brand_hover), active
    assert page.locator('form[data-menu-editor]').count() == 1
