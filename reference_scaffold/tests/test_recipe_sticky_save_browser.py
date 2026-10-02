"""UC-P1-B2: shared recipe footer reachability on long native forms."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_bf_dialog_low_height_browser import REACH
from test_master_data_browser import master_server  # noqa: F401
from test_recipe_density_browser import reference
from test_recipe_routes import app_engine, b3, fields, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/delta3/DELTA-3-09/sticky-save'


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('coarse', [False, True], ids=['mouse', 'touch'])
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844), (1024, 600)],
                         ids=['wide', 'narrow', 'short'])
def test_long_recipe_save_reach_and_native_submit(
    b3, master_server, browser, width, height, coarse, javascript,  # noqa: F811
):
    path = reference(b3[2], count=20)
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': height}, has_touch=coarse,
                             java_script_enabled=javascript, reduced_motion='reduce',
                             service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + path, wait_until='networkidle').status == 200
        assert page.evaluate('matchMedia("(pointer: coarse)").matches') is coarse
        footer = page.locator('.admin-form-footer[data-sticky-form="recipe-editor"]')
        save = footer.locator('[data-semantic="actions.save"]')
        expect(save).to_have_count(1)
        expect(save).to_have_attribute('form', 'recipe-editor')
        expect(page.locator('.admin-compact-toolbar[data-sticky-form]')).to_have_count(0)
        sticky = javascript and height >= 700
        expect(footer).to_have_css('position', 'sticky' if sticky else 'static')
        assert page.evaluate('document.documentElement.scrollHeight > innerHeight * 2')
        if sticky:
            # Check before any locator action can scroll the footer into view.
            for position in ('top', 'middle'):
                if position == 'middle':
                    page.evaluate('scrollTo(0, document.documentElement.scrollHeight / 2)')
                expect(save).to_be_in_viewport(ratio=1)
                reach = save.evaluate(REACH)
                assert reach['inView'] and reach['hitOk'] and not reach['covered'], reach
        title = page.locator('[name="title"]')
        title.fill('UC-P1-B2 Langformular gespeichert')
        # Low-height/no-JS fallback keeps the native keyboard save path reachable.
        save.focus()
        expect(save).to_be_focused()
        expect(save).to_be_in_viewport(ratio=1)
        reach = save.evaluate(REACH)
        assert reach['inView'] and reach['hitOk'] and not reach['covered'], reach
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        box = save.bounding_box()
        assert box and box['width'] >= (44 if coarse else 36) and box['height'] >= (44 if coarse else 36)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f'save-{width}x{height}-coarse{int(coarse)}-js{int(javascript)}.png'))
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        assert fields(b3[2], path)['title'] == 'UC-P1-B2 Langformular gespeichert'
