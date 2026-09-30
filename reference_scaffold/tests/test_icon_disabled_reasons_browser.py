"""Localized disabled reasons remain reachable without activating native commands."""
import pytest
from playwright.sync_api import expect

from test_master_data_browser import master_server  # noqa: F401
from test_recipe_density_browser import reference
from test_recipe_routes import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import snapshot
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('javascript', [True, False])
def test_recipe_move_reasons_are_localized(b3, master_server, browser, locale, javascript):  # noqa: F811
    app, owner, client, _ = b3
    app.config['UI_LOCALE'] = locale
    path = reference(client)
    before = snapshot(owner)
    base, cookie = master_server
    with browser.new_context(java_script_enabled=javascript) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + path).status == 200
        for direction, reason in (
            ('up', 'Bereits an erster Position.' if locale == 'de' else 'Already at the first position.'),
            ('down', 'Bereits an letzter Position.' if locale == 'de' else 'Already at the last position.'),
        ):
            action = page.locator(f'[data-semantic="actions.move_{direction}"]:disabled').first
            expect(action).to_have_accessible_description(reason)
            wrapper = action.locator('..')
            expect(wrapper).to_have_accessible_description(reason)
            wrapper.focus()
            expect(wrapper).to_be_focused()
            expect(wrapper).to_have_attribute('data-ui-tooltip', action.get_attribute('aria-label') + ': ' + reason)
            wrapper.press('Enter')
            wrapper.press('Space')
            assert page.url == base + path
        assert snapshot(owner) == before
