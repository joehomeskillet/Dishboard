"""Correction-wave proof for list-first master data pages and native forms."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from playwright.sync_api import expect

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


EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/ui-korrektur-0912/grundlagen'
VIEWPORTS = (
    (1366, 768, 'desktop'),
    (1920, 1080, 'wide'),
    (768, 1024, 'tablet'),
    (390, 844, 'mobile'),
    (720, 450, 'zoom-200'),
)


def _prepare_evidence() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    EVIDENCE.chmod(0o700)


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
        first = page.locator('.grundlagen-list .list-group-item').first
        expect(first).to_be_visible()
        box = first.bounding_box()
        assert box is not None
        if width in {1366, 1920}:
            assert box['y'] + box['height'] <= height
        expect(page.locator('details').filter(has_text='Liste filtern').first).not_to_have_attribute('open', '')
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
        expect(page.locator('details').filter(has_text='Liste filtern').first).to_have_attribute('open', '')
        _assert_no_horizontal_scroll(page)
        _screenshot(page, f'liste-leer-{state}-{width}x{height}.png')


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
        page.get_by_label('Name', exact=True).fill('<unzulässig>')
        storage = page.get_by_label('Testlager', exact=True)
        storage.check()
        storage_id = storage.input_value()

        with page.expect_request(lambda request: request.method == 'POST') as submitted:
            with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
                page.get_by_role('button', name='Zutat speichern', exact=True).click()

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

        status = page.locator('#food-status-title').locator('xpath=../..')
        expect(status.get_by_text('Aktiv', exact=True)).to_be_visible()
        expect(status.get_by_text('Lagerort fehlt', exact=True)).to_be_visible()
        expect(status.get_by_text('Allergenangaben nicht erfasst', exact=True)).to_be_visible()
        expect(status.get_by_text('Noch nicht bestätigt', exact=False)).to_be_visible()
        expect(page.get_by_role('button', name='Archivieren', exact=True)).not_to_be_visible()
        page.get_by_text('Weitere Aktionen', exact=True).click()
        expect(page.get_by_role('button', name='Archivieren', exact=True)).to_be_visible()
        _assert_no_horizontal_scroll(page)

        _prepare_evidence()
        _screenshot(page, 'zutat-status-mobile-390x844.png')
