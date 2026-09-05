"""«Speichern und zurück»: same form data and CSRF, only the action carries return_to=week."""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, expect

from test_admin_ux_browser import (  # noqa: F401
    _submit_menu, admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import DAY


def _editor(family: str) -> str:
    return f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


def _submit_back(page: Page, family: str, status: int) -> dict[str, list[str]]:
    with page.expect_response(
        lambda response: response.request.method == 'POST' and f'/admin/{family}/menu' in response.url
    ) as submitted:
        page.get_by_role('button', name='Speichern und zurück', exact=True).click()
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
    back = page.get_by_role('button', name='Speichern und zurück', exact=True)
    expect(back).to_be_visible()
    assert back.evaluate('el => el.form === el.closest("form[data-menu-editor]")')
    assert back.get_attribute('formaction') == f'/admin/{family}/menu?return_to=week'
    box = back.bounding_box()
    assert box is not None and box['height'] >= 48 and box['x'] + box['width'] <= width + 1
    assert page.locator('form[data-menu-editor]').get_attribute('action') == f'/admin/{family}/menu'

    page.get_by_label('Titel', exact=True).fill('Zurück zur Woche')
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
    expect(page.get_by_label('Titel', exact=True)).to_have_value('Zurück zur Woche')
    expect(page.locator('form[data-menu-editor] [name="row_version"]')).to_have_value('1')


def test_save_and_back_error_keeps_editor_values_then_returns(page_context: Page) -> None:  # noqa: F811
    page = page_context
    page.set_viewport_size({'width': 820, 'height': 1180})
    page.goto(_editor('patienten'))
    page.get_by_label('Titel', exact=True).fill('Fehler dann zurück')
    for summary in page.locator('details.admin-accordion:not([open]) > summary').all():
        summary.click()
    page.locator('[name="origin_mode"][value="manual"]').check()
    page.locator('[name="origin_ingredient"]').fill('Rind')
    payload = _submit_back(page, 'patienten', 400)
    assert payload['origin_ingredient'] == ['Rind']
    assert payload['origin_country_code'] == ['']
    expect(page.locator('.error-region[role="alert"]')).to_be_visible()
    expect(page.get_by_label('Titel', exact=True)).to_have_value('Fehler dann zurück')
    expect(page.locator('[name="origin_ingredient"]')).to_have_value('Rind')
    expect(page.locator('[name="origin_country_code"]')).to_be_focused()
    assert page.locator('form[data-menu-editor]').get_attribute('action') == '/admin/patienten/menu'

    page.locator('[name="origin_country_code"]').select_option('CH')
    payload = _submit_back(page, 'patienten', 303)
    assert payload['origin_country_code'] == ['CH']
    assert urlsplit(page.url).path == '/admin/patienten'

    # The default submit still posts to the plain action and stays in the editor.
    page.goto(_editor('patienten'))
    page.get_by_label('Hinweis', exact=True).fill('Normal gespeichert')
    _submit_menu(page)
    assert urlsplit(page.url).path == '/admin/patienten/menu'
    expect(page.get_by_label('Hinweis', exact=True)).to_have_value('Normal gespeichert')
