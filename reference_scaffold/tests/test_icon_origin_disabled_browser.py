"""Automatic origin actions expose their reason and follow native mode changes."""
import pytest
from playwright.sync_api import expect

from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_workflow_routes import DAY, WEEK, _payload
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401
from test_ui_menu_editor_browser import editor_page, family, javascript  # noqa: F401


@pytest.mark.parametrize('locale', ['de', 'en'])
def test_automatic_origin_removal_explains_lock_and_tracks_mode(editor_page, family, javascript, locale):  # noqa: F811
    page, engine, scope, profile, app, _ = editor_page
    app.config['UI_LOCALE'] = locale
    payload = _payload(staff=profile == 'staff_guest')
    payload.update(origin_mode='auto', origins=[])
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 1)
    reason = ('Automatische Herkunft wird aus den Bausteinen geerbt.' if locale == 'de'
              else 'Automatic origin is inherited from the components.')
    consequence = 'Löschen' if locale == 'de' else 'Delete'
    posts = []
    page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
    assert page.goto(f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1').status == 200
    section = page.locator('section[data-mode-section="origin"]')
    expect(section).to_be_visible()
    rows = page.locator('#origins-list > .origin-row')
    action = rows.first.locator('[data-remove-row]')
    wrapper = action.locator('..')
    expect(action).to_be_disabled()
    expect(wrapper).to_have_class('ui-sem-disabled')
    expect(wrapper).to_have_accessible_description(reason + ' ' + consequence)
    wrapper.focus()
    expect(wrapper).to_be_focused()
    wrapper.press('Enter')
    wrapper.press('Space')
    wrapper.click()
    expect(rows).to_have_count(1)
    assert not posts
    if javascript:
        for _ in range(2):
            page.locator('#origin-mode-manual').check()
            expect(action).to_be_enabled()
            expect(action).to_have_accessible_description(consequence)
            expect(wrapper).to_have_attribute('tabindex', '-1')
            page.locator('[name="origin_ingredient"]').first.fill('Rind')
            page.locator('[name="origin_country_code"]').first.select_option('CH')
            action.click()
            expect(page.locator('[name="origin_ingredient"]').first).to_have_value('')
            page.locator('#origin-mode-auto').check()
            expect(action).to_be_disabled()
            expect(wrapper).to_have_accessible_description(reason + ' ' + consequence)
            wrapper.focus()
            expect(wrapper).to_be_focused()
        assert not posts
