"""Acceptance coverage for U04/U05 menu-editor correction."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import Page, expect

from cafeteria.component_catalog_store import create_component, update_component
from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_ux_browser import _submit_menu
from test_admin_workflow_routes import DAY, WEEK, _payload
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401
from test_ui_menu_editor_browser import (  # noqa: F401
    editor_page,
    family,
    javascript,
)

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/ui-korrektur-0912/editor'


def _menu_url(family_name: str) -> str:
    return f'/admin/{family_name}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


def _pairs(page: Page) -> dict[str, list[str]]:
    entries = page.locator('form[data-menu-editor]').evaluate(
        'form => [...new FormData(form).entries()].map(([name, value]) => [name, String(value)])'
    )
    result: dict[str, list[str]] = {}
    for name, value in entries:
        result.setdefault(name, []).append(value)
    return result


def _assert_component_pairs(payload: dict[str, list[str]]) -> None:
    ids = payload['component_public_id']
    texts = payload['component_text']
    assert len(ids) == len(texts)
    assert all(not (public_id and text) for public_id, text in zip(ids, texts, strict=True))


def _capture(page: Page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.screenshot(path=str(EVIDENCE / name), full_page=True)


def test_a08_unchanged_catalog_and_text_pairs_use_native_save(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.goto(_menu_url(family))
    assert page.locator('[data-component-kind-option][name]').count() == 0
    if javascript:
        expect(page.get_by_role('button', name='Ändern')).to_have_count(2)
        expect(page.locator('[data-component-summary]')).to_have_text(['Kartoffelstock', 'Blattsalat'])
    else:
        for row in page.locator('#components-list .component-row').all():
            expect(row.locator('[name="component_public_id"]')).to_be_visible()
            expect(row.locator('[name="component_text"]')).to_be_visible()

    with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/menu')) as saved:
        page.get_by_role('button', name='Menü speichern', exact=True).click()
    assert saved.value.status == 303
    data = saved.value.request.post_data
    assert data is not None
    payload = parse_qs(data, keep_blank_values=True)
    assert payload['component_public_id'][0] and payload['component_public_id'][1] == ''
    assert payload['component_text'] == ['', 'Blattsalat']
    _assert_component_pairs(payload)
    page.wait_for_load_state()
    expect(page.get_by_text('Menü gespeichert.', exact=True)).to_be_visible()


def test_a08_switching_input_kind_clears_other_value(editor_page, family: str, javascript: bool) -> None:  # noqa: F811
    if not javascript:
        pytest.skip('Eingabeart-Schalter ist progressive Enhancement.')
    page, *_ = editor_page
    page.goto(_menu_url(family))
    rows = page.locator('#components-list .component-row')

    rows.first.get_by_role('button', name='Ändern').click()
    rows.first.locator('[data-component-kind-option][value="text"]').check()
    expect(rows.first.locator('[name="component_public_id"]')).to_have_value('')
    expect(rows.first.locator('[name="component_public_id"]')).to_be_hidden()
    expect(rows.first.locator('[name="component_text"]')).to_be_visible()
    rows.first.locator('[name="component_text"]').fill('Knöpfli')

    rows.nth(1).get_by_role('button', name='Ändern').click()
    rows.nth(1).locator('[data-component-kind-option][value="catalog"]').check()
    expect(rows.nth(1).locator('[name="component_text"]')).to_have_value('')
    expect(rows.nth(1).locator('[name="component_text"]')).to_be_hidden()
    rows.nth(1).locator('[name="component_public_id"]').select_option(index=1)

    payload = _pairs(page)
    _assert_component_pairs(payload)
    assert payload['component_text'] == ['Knöpfli', '']
    assert payload['component_public_id'][0] == '' and payload['component_public_id'][1]


def test_a09_add_move_remove_keeps_visual_payload_order(editor_page, family: str, javascript: bool) -> None:  # noqa: F811
    if not javascript:
        pytest.skip('Zeilenaktionen benötigen progressive Enhancement.')
    page, *_ = editor_page
    page.goto(_menu_url(family))
    page.get_by_role('button', name='Baustein hinzufügen').click()
    rows = page.locator('#components-list .component-row')
    expect(rows).to_have_count(3)
    expect(rows.last.locator('[name="component_public_id"]')).to_be_focused()
    rows.last.locator('[data-component-kind-option][value="text"]').check()
    rows.last.locator('[name="component_text"]').fill('Dritte Beilage')
    rows.last.get_by_role('button', name='Fertig').click()
    rows.last.get_by_role('button', name='Nach oben').click()
    rows.first.get_by_role('button', name='Entfernen').click()

    expect(rows).to_have_count(2)
    expect(rows.nth(0).locator('legend').first).to_have_text('Baustein 1')
    expect(rows.nth(1).locator('legend').first).to_have_text('Baustein 2')
    payload = _pairs(page)
    assert payload['component_public_id'] == ['', '']
    assert payload['component_text'] == ['Dritte Beilage', 'Blattsalat']
    _assert_component_pairs(payload)


def test_a10_a13_dirty_review_links_width_and_focus_order(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    if not javascript:
        pytest.skip('Dirty-Hervorhebung und Fokusöffnung benötigen JavaScript.')
    page, *_ = editor_page
    page.set_viewport_size({'width': 1366, 'height': 768})
    page.goto(_menu_url(family))
    expect(page.locator('main')).to_have_attribute('data-layout', 'standard')
    note = page.locator('[data-menu-editor-dirty-note]')
    expect(note).to_be_visible()
    expect(note).not_to_have_class('is-dirty')
    page.get_by_label('Menüname', exact=True).fill('Geänderter Herbstteller')
    expect(note).to_have_class(re.compile(r'\bis-dirty\b'))

    ordered = page.evaluate('''() => {
        const nodes = [
            document.querySelector('#f-title'),
            document.querySelector('[data-edit-row]'),
            document.querySelector('#sec-markings + details summary, #sec-markings ~ details summary'),
            document.querySelector('[data-sticky] .btn-primary'),
            document.querySelector('#review a[data-error-link]'),
        ];
        return nodes.every(Boolean) && nodes.slice(1).every((node, index) =>
            Boolean(nodes[index].compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING));
    }''')
    assert ordered
    link = page.locator('#review a[href="#allergen-mode-manual"]')
    link.click()
    expect(page.locator('details[data-mode-section="allergen"]')).to_have_attribute('open', '')
    expect(page.locator('#allergen-mode-manual')).to_be_focused()

    container_ratio = page.locator('.page-body > .container-xl').evaluate('''element => {
        const main = document.querySelector('main.admin-main');
        return element.getBoundingClientRect().width / main.getBoundingClientRect().width;
    }''')
    assert container_ratio >= 0.95
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def test_a11_a12_editor_evidence_states(editor_page, family: str, javascript: bool) -> None:  # noqa: F811
    if family != 'patienten':
        pytest.skip('Ein Familienprofil genügt für viewportbezogene Bildbelege.')
    page, engine, scope, profile, _, base_url = editor_page
    page.goto(_menu_url(family))
    if not javascript:
        page.set_viewport_size({'width': 1366, 'height': 768})
        _capture(page, 'menu-editor-ohne-js-1366x768.png')
        return

    page.get_by_role('button', name='Baustein hinzufügen').click()
    page.locator('[data-component-kind-option][value="text"]').last.check()
    page.locator('[name="component_text"]').last.fill('Dritte Beilage')
    page.get_by_role('button', name='Fertig').last.click()
    for width, height in ((1366, 768), (1920, 1080), (768, 1024), (390, 844)):
        page.set_viewport_size({'width': width, 'height': height})
        _capture(page, f'menu-editor-regulaer-{width}x{height}.png')

    with page.context.browser.new_context(
        base_url=base_url, viewport={'width': 720, 'height': 450}, device_scale_factor=2,
        reduced_motion='reduce',
    ) as zoom:
        zoom.add_cookies(page.context.cookies())
        zoom_page = zoom.new_page()
        zoom_page.goto(_menu_url(family))
        _capture(zoom_page, 'menu-editor-regulaer-200-prozent-720x450.png')

    for summary in page.locator('details.admin-accordion:not([open]) > summary').all():
        summary.click()
    page.locator('[name="origin_mode"][value="manual"]').check()
    page.locator('[name="origin_ingredient"]').fill('Rind')
    page.locator('[name="origin_country_code"]').select_option('')
    _submit_menu(page, 400)
    page.set_viewport_size({'width': 390, 'height': 844})
    _capture(page, 'menu-editor-fehler-390x844.png')

    potato = create_component(engine, scope, 'side', 'Kartoffel', 'CH', 'common', (), ())
    rice = create_component(engine, scope, 'side', 'Reis', 'DE', 'current', (), ())
    payload = _payload(staff=profile == 'staff_guest')
    payload.update(origin_mode='auto', origins=[], assignments=[
        {'component_public_id': str(potato['public_id']), 'component_text': None},
        {'component_public_id': str(rice['public_id']), 'component_text': None},
    ])
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 1)
    update_component(engine, scope, str(rice['public_id']), {
        'category': 'side', 'name': 'Kartoffel', 'origin_country_code': 'DE',
        'label_codes': [], 'allergens': [],
    }, int(rice['row_version']))
    response = page.goto(_menu_url(family))
    assert response is not None and response.status == 409
    _capture(page, 'menu-editor-konflikt-390x844.png')
