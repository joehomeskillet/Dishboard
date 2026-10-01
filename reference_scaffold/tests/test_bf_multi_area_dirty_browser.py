"""BF-03/04: independent forms, value-based leave guards and retained price errors."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from test_master_data_browser import master_server  # noqa: F401
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, create, installed_pg16, pg16, seeded_pg16, snapshot,
)
from test_rendered_ui import browser  # noqa: F401


def _open(page, selector):
    for details in page.locator(f'details:has({selector})').all():
        if not details.evaluate('element => element.open'):
            details.locator('> summary').click()
    return page.locator(selector)


@pytest.fixture
def food_page(b3, master_server, browser):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, name='BF getrennte Bereiche')
    base, cookie = master_server
    with browser.new_context(base_url=base, viewport={'width': 1440, 'height': 900},
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(path).status == 200
        yield page, owner, path


@pytest.mark.parametrize('width', (390, 1440))
def test_t04_other_area_warns_before_submit_and_cancel_keeps_both(food_page, width):
    page, owner, path = food_page
    page.set_viewport_size({'width': width, 'height': 900})
    before = snapshot(owner)
    page.locator('#name').fill('BF neuer Name')
    _open(page, '#unit_price').fill('12.34')
    page.locator('#valid_from').fill('2026-09-30')
    core = page.locator('#food-core-form')
    price = page.locator('form:has(#unit_price)')
    expect(core.locator('[data-dirty-status]')).to_have_text('Nicht gespeichert')
    expect(core.locator('[data-dirty-status]')).to_be_visible()
    expect(price.locator('[data-dirty-status]')).to_be_visible()
    decisions = []

    def stay(dialog):
        decisions.append(dialog.type)
        dialog.dismiss()

    page.on('dialog', stay)
    core.get_by_role('button', name='Speichern', exact=True).click()
    expect(page.locator('#name')).to_have_value('BF neuer Name')
    expect(page.locator('#unit_price')).to_have_value('12.34')
    assert decisions == ['beforeunload']
    assert snapshot(owner) == before
    expect(core.locator('[data-dirty-status]')).to_be_visible()
    expect(price.locator('[data-dirty-status]')).to_be_visible()
    page.locator('main a[data-semantic="actions.back"]').click()
    assert decisions == ['beforeunload', 'beforeunload']
    expect(page).to_have_url(re.compile(re.escape(path) + '$'))
    # Explicitly accept losing the other area; only the submitted core may persist.
    page.remove_listener('dialog', stay)
    page.on('dialog', lambda dialog: (decisions.append(dialog.type), dialog.accept()))
    core.get_by_role('button', name='Speichern', exact=True).click()
    expect(page.locator('.flash-region')).to_contain_text('gespeichert')
    expect(page.locator('#name')).to_have_value('BF neuer Name')
    expect(page.locator('#unit_price')).to_have_value('')
    assert decisions == ['beforeunload'] * 3
    with owner.connect() as connection:
        assert connection.execute(text('SELECT name FROM cafeteria.foods')).scalar_one() == 'BF neuer Name'
        assert connection.execute(text('SELECT count(*) FROM cafeteria.food_purchase_price_revisions')).scalar_one() == 0


@pytest.mark.parametrize('field,changed', (('#name', 'Anderer Name'),
                                         ('#base_unit_code', 'KG'),
                                         ('#storage_location_public_ids input[type="checkbox"]', False)))
def test_value_reversal_and_native_reset_remove_unsaved_warning(food_page, field, changed):
    page, owner, _ = food_page
    before = snapshot(owner)
    control = page.locator(field)
    core = page.locator('#food-core-form')
    status = core.locator('[data-dirty-status]')
    checkbox = control.get_attribute('type') == 'checkbox'
    original = control.is_checked() if checkbox else control.input_value()
    control.focus()
    expect(status).to_be_hidden()

    def set_value(value):
        if checkbox:
            control.set_checked(value)
        elif field == '#base_unit_code':
            control.select_option(value)
        else:
            control.fill(value)

    set_value(changed)
    expect(status).to_be_visible()
    set_value(original)
    expect(status).to_be_hidden()
    set_value(changed)
    expect(status).to_be_visible()
    core.evaluate('form => form.reset()')
    expect(status).to_be_hidden()
    dialogs = []
    page.on('dialog', lambda dialog: (dialogs.append(dialog.type), dialog.dismiss()))
    page.locator('main a[data-semantic="actions.back"]').click()
    expect(page).to_have_url(re.compile('/admin/grundlagen\\?kind=foods$'))
    assert dialogs == []
    assert snapshot(owner) == before


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize('navigation', ('profile', 'week'))
def test_t06_cancel_context_change_and_restore_radio_value(food_page, family, navigation):
    page, owner, _ = food_page
    path = f'/admin/{family}/menu?week=2026-08-31&day=2026-08-31&meal=LUNCH&option=MENU_1'
    assert page.goto(path).status == 200
    before = snapshot(owner)
    note = page.locator('[data-menu-editor-dirty-note]')
    _open(page, '[name="allergen_mode"]')
    initial_mode = page.locator('[name="allergen_mode"]:checked').input_value()
    changed_mode = 'manual' if initial_mode == 'auto' else 'auto'
    page.locator(f'[name="allergen_mode"][value="{changed_mode}"]').check()
    expect(note).to_have_class(re.compile(r'\bis-dirty\b'))
    page.locator(f'[name="allergen_mode"][value="{initial_mode}"]').check()
    expect(note).not_to_have_class(re.compile(r'\bis-dirty\b'))
    page.get_by_label('Menüname', exact=True).fill('BF Kontext bleibt')
    dialogs = []
    page.on('dialog', lambda dialog: (dialogs.append(dialog.type), dialog.dismiss()))
    other = 'patienten' if family == 'cafeteria' else 'cafeteria'
    if navigation == 'profile':
        page.get_by_role('button', name='Navigation einklappen', exact=True).click()
        page.locator('#sidebar-menu').get_by_role('button', name='Wochenplan', exact=True).click()
        target = page.locator(f'#admin-nav-flyout a[href^="/admin/{other}"]')
    else:
        target = page.locator('[data-semantic="navigation.weekplan"]')
    target.click()
    assert dialogs == ['beforeunload']
    expect(page).to_have_url(re.compile(re.escape(path) + '$'))
    expect(page.get_by_label('Menüname', exact=True)).to_have_value('BF Kontext bleibt')
    assert snapshot(owner) == before


@pytest.mark.parametrize('javascript', (True, False), ids=('js', 'no-js'))
@pytest.mark.parametrize('entry', ('pointer', 'keyboard'))
def test_price_error_retains_inputs_opens_section_and_does_not_write(b3, master_server, browser, javascript, entry, tmp_path):  # noqa: F811
    _, owner, client, _ = b3
    path = create(client, name='BF Preisfehler')
    before = snapshot(owner)
    base, cookie = master_server
    with browser.new_context(base_url=base, java_script_enabled=javascript,
                             viewport={'width': 390, 'height': 844}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(path).status == 200
        price_input = page.locator('#unit_price')
        if entry == 'pointer':
            price_input.click()
        else:
            page.locator('#unit_code').press('Shift+Tab')
        expect(price_input).to_be_focused()
        price_input.fill('ungueltiger-preis')
        page.locator('#valid_from').fill('2026-09-30')
        page.locator('#valid_to').fill('2026-10-31')
        page.locator('#unit_code').fill('KG')
        with page.expect_response(lambda response: response.request.method == 'POST') as submitted:
            page.get_by_role('button', name='Preis speichern', exact=True).click()
        assert submitted.value.status == 400
        expect(page.locator('#unit_price')).to_have_value('ungueltiger-preis')
        expect(page.locator('#valid_from')).to_have_value('2026-09-30')
        expect(page.locator('#valid_to')).to_have_value('2026-10-31')
        expect(page.locator('#unit_code')).to_have_value('KG')
        expect(page.locator('#unit_price')).to_have_attribute('aria-invalid', 'true')
        expect(page.locator('#food-core-form [aria-invalid="true"]')).to_have_count(0)
        expect(page.locator('#food-core-form [aria-describedby~="master-error"]')).to_have_count(0)
        expect(page.locator('#price-error')).to_be_visible()
        expect(page.locator('#unit_price' if javascript else '#price-error')).to_be_focused()
        expect(page.locator('a[data-error-link][href="#unit_price"]')).to_be_visible()
        page.screenshot(path=str(tmp_path / f'price-error-js{int(javascript)}.png'), full_page=True)
        assert snapshot(owner) == before
        with owner.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.food_purchase_price_revisions')).scalar_one() == 0


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_restoring_week_values_keeps_action_permissions_and_live_descriptions(food_page, family):
    page, owner, _ = food_page
    assert page.goto(f'/admin/{family}?week=2026-08-31').status == 200
    before = snapshot(owner)
    title = _open(page, 'input[name="title"]')
    original = title.input_value()
    preview = page.locator('main a[href*="/preview"]').first
    publish = page.locator('form[action*="/publish"] button[type="submit"]')
    original_disabled = publish.is_disabled()
    original_aria = preview.get_attribute('aria-disabled')
    preview.hover()
    tooltip = page.locator('.tooltip.show').last
    expect(tooltip).to_be_visible()
    tooltip_id = tooltip.get_attribute('id')
    title.fill('BF vorübergehender Titel')
    expect(preview).to_have_attribute('aria-disabled', 'true')
    expect(publish).to_be_disabled()
    page.mouse.move(0, 0)
    expect(page.locator(f'#{tooltip_id}')).to_have_count(0)
    title.fill(original)
    expect(page.locator('#admin-dirty-action-reason')).to_be_hidden()
    assert publish.is_disabled() == original_disabled
    assert preview.get_attribute('aria-disabled') == original_aria
    assert preview.evaluate('''el => (el.getAttribute('aria-describedby') || '').split(/\\s+/)
        .filter(id => id && !document.getElementById(id))''') == []
    assert snapshot(owner) == before


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_publish_shows_save_first_while_dirty_and_restores_label(food_page, family):
    page, owner, _ = food_page
    assert page.goto(f'/admin/{family}?week=2026-08-31').status == 200
    before = snapshot(owner)
    title = _open(page, 'input[name="title"]')
    original = title.input_value()
    publish = page.locator('form[action*="/publish"] button[type="submit"]')
    reason = page.locator('#admin-dirty-action-reason')
    week_status = page.locator('main').get_attribute('data-status')
    expect(publish).to_have_text('Veröffentlichen')
    was_enabled = publish.is_enabled()
    original_describedby = publish.get_attribute('aria-describedby')
    title.fill('BF vorübergehender Titel')
    expect(publish).to_be_disabled()
    expect(publish).to_have_text('Zuerst speichern')
    expect(reason).to_be_visible()
    expect(reason).to_have_text('Zuerst speichern')
    expect(publish).to_have_attribute(
        'aria-describedby', re.compile(r'(^|\s)admin-dirty-action-reason(\s|$)'))
    title.fill(original)
    expect(reason).to_be_hidden()
    expect(publish).to_have_text('Veröffentlichen')
    assert publish.is_enabled() is was_enabled
    assert publish.get_attribute('aria-describedby') == original_describedby
    described = publish.get_attribute('aria-describedby') or ''
    assert 'admin-dirty-action-reason' not in described.split()
    # An empty week keeps its publication guard. A publishable week is active and undescribed.
    if week_status in {'ready', 'live', 'changed'}:
        expect(publish).to_be_enabled()
        expect(publish).not_to_have_attribute('aria-describedby')
    assert snapshot(owner) == before
