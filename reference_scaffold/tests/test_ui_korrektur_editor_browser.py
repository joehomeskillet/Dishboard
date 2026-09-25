"""Acceptance coverage for U04/U05 menu-editor correction."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import Page, expect

from cafeteria.component_catalog_store import create_component, update_component
from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_workflow_routes import DAY, WEEK, _payload
from test_rendered_ui import PATIENT_FORBIDDEN, admin_app, admin_engine, browser  # noqa: F401
from test_ui_menu_editor_browser import (  # noqa: F401
    editor_page,
    family,
    javascript,
)

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/density-menu-0913/editor'
DENSITY_VIEWPORTS = (
    (1440, 900),
    (1024, 768),
    (768, 1024),
    (390, 844),
    (1920, 1080),
    (2560, 1440),
)


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


def _submit_menu_form(page: Page, status: int) -> dict[str, list[str]]:
    with page.expect_response(
        lambda response: response.request.method == 'POST' and response.url.endswith('/menu')
    ) as submitted:
        page.get_by_role('button', name='Menü speichern', exact=True).click()
    response = submitted.value
    assert response.status == status
    data = response.request.post_data
    assert data is not None
    page.wait_for_load_state()
    return parse_qs(data, keep_blank_values=True)


def _tab_to(page: Page, selector: str, limit: int = 80) -> None:
    target = page.locator(selector).first
    expect(target).to_have_count(1)
    for _ in range(limit):
        page.keyboard.press('Tab')
        if target.evaluate('element => element === document.activeElement'):
            return
    raise AssertionError(f'Focus did not reach {selector!r} after {limit} Tab presses')


def _assert_component_pairs(payload: dict[str, list[str]]) -> None:
    ids = payload['component_public_id']
    texts = payload['component_text']
    assert len(ids) == len(texts)
    assert all(not (public_id and text) for public_id, text in zip(ids, texts, strict=True))


def _capture(page: Page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    _assert_no_overflow(page)
    page.screenshot(path=str(EVIDENCE / name), full_page=True)


def _assert_no_overflow(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def _assert_one_primary_save(page: Page) -> None:
    form = page.locator('form[data-menu-editor]')
    expect(form.locator('.btn-primary')).to_have_count(1)
    expect(form.locator('.btn-primary [data-semantic="actions.save"] use')).to_have_attribute(
        'href', '/static/vendor/tabler-icons/tabler-icons.svg#tabler-device-floppy')
    expect(page.locator('#review .admin-list-row')).to_have_count(2)
    expect(form.get_by_role('button', name='Menü speichern', exact=True)).to_have_count(1)
    expect(form.get_by_role('button', name='Speichern und zum Wochenplan', exact=True)).to_have_count(1)
    secondary = form.locator('input[type="submit"][formaction*="return_to=week"]')
    expect(secondary).to_have_count(1)
    assert secondary.evaluate('el => !el.classList.contains("btn-primary")')


def test_a08_unchanged_catalog_and_text_pairs_use_native_save(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.goto(_menu_url(family))
    assert page.locator('[data-component-kind-option][name]').count() == 0
    if javascript:
        expect(page.get_by_role('button', name='Bearbeiten')).to_have_count(2)
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

    rows.first.get_by_role('button', name='Bearbeiten').click()
    rows.first.locator('[data-component-kind-option][value="text"]').check()
    expect(rows.first.locator('[name="component_public_id"]')).to_have_value('')
    expect(rows.first.locator('[name="component_public_id"]')).to_be_hidden()
    expect(rows.first.locator('[name="component_text"]')).to_be_visible()
    rows.first.locator('[name="component_text"]').fill('Knöpfli')

    rows.nth(1).get_by_role('button', name='Bearbeiten').click()
    rows.nth(1).locator('[data-component-kind-option][value="catalog"]').check()
    expect(rows.nth(1).locator('[name="component_text"]')).to_have_value('')
    expect(rows.nth(1).locator('[name="component_text"]')).to_be_hidden()
    rows.nth(1).locator('[name="component_public_id"]').select_option(index=1)

    payload = _pairs(page)
    _assert_component_pairs(payload)
    assert payload['component_text'] == ['Knöpfli', '']
    assert payload['component_public_id'][0] == '' and payload['component_public_id'][1]


@pytest.mark.parametrize('javascript', [True], indirect=True, ids=['js'])
def test_a08_reopening_empty_input_kind_focuses_selected_control(editor_page, family: str) -> None:  # noqa: F811
    page, *_ = editor_page
    page.goto(_menu_url(family))
    row = page.locator('#components-list .component-row').first
    for kind, name, other_name in (
        ('text', 'component_text', 'component_public_id'),
        ('catalog', 'component_public_id', 'component_text'),
    ):
        row.get_by_role('button', name='Bearbeiten').click()
        option = row.locator(f'[data-component-kind-option][value="{kind}"]')
        option.check()
        expect(row.locator(f'[name="{name}"]')).to_have_value('')
        expect(row.locator(f'[name="{other_name}"]')).to_have_value('')
        row.get_by_role('button', name='Bestätigen').click()
        edit = row.get_by_role('button', name='Bearbeiten')
        expect(edit).to_be_focused()
        edit.press('Enter')
        expect(option).to_be_checked()
        expect(row.locator(f'[name="{name}"]')).to_be_focused()
        expect(row.locator(f'[name="{other_name}"]')).to_be_hidden()
        row.get_by_role('button', name='Bestätigen').click()


def test_a09_add_move_remove_keeps_visual_payload_order(editor_page, family: str, javascript: bool) -> None:  # noqa: F811
    if not javascript:
        pytest.skip('Zeilenaktionen benötigen progressive Enhancement.')
    page, *_ = editor_page
    page.goto(_menu_url(family))
    page.locator('[data-add-row="components-list"]').click()
    rows = page.locator('#components-list .component-row')
    expect(rows).to_have_count(3)
    expect(rows.last.locator('[name="component_public_id"]')).to_be_focused()
    rows.last.locator('[data-component-kind-option][value="text"]').check()
    rows.last.locator('[name="component_text"]').fill('Dritte Beilage')
    rows.last.get_by_role('button', name='Bestätigen').click()
    expect(rows.last.locator('[data-move-row="up"]')).not_to_be_visible()
    rows.last.locator('summary').click()
    rows.last.get_by_role('button', name='Nach oben').click()
    rows.first.locator('summary').click()
    rows.first.get_by_role('button', name='Löschen').click()

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
    page, *_ = editor_page
    page.set_viewport_size({'width': 1366, 'height': 768})
    page.goto(_menu_url(family))
    expect(page.locator('main')).to_have_attribute('data-layout', 'standard')
    note = page.locator('[data-menu-editor-dirty-note]')
    expect(note).to_be_visible()
    expect(note).not_to_have_class('is-dirty')
    if javascript:
        page.get_by_label('Menüname', exact=True).fill('Geänderter Herbstteller')
        expect(note).to_have_class(re.compile(r'\bis-dirty\b'))

    page.locator('#f-title').focus()
    page.keyboard.press('Tab')
    expect(page.locator('#accompaniment-none')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('summary[aria-describedby="accompaniment-hint"]')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('summary[aria-describedby="components-hint"]')).to_be_focused()
    page.keyboard.press('Tab')
    assert page.evaluate('document.activeElement.closest("#components-list") !== null')
    _tab_to(page, '#sec-markings ~ details summary')
    _tab_to(page, '[data-sticky] .btn-primary')
    _tab_to(page, '#review a[data-error-link]')

    if javascript:
        link = page.locator('#review a[href="#allergen-mode-manual"]')
        link.click()
        expect(page.locator('details[data-mode-section="allergen"]')).to_have_attribute('open', '')
        expect(page.locator('#allergen-mode-manual')).to_be_focused()

    container_ratio = page.locator('.page-body > .container-xl').evaluate('''element => {
        const main = document.querySelector('main.admin-main');
        return element.getBoundingClientRect().width / main.getBoundingClientRect().width;
    }''')
    assert container_ratio >= 0.95
    _assert_no_overflow(page)
    _assert_one_primary_save(page)
    layout = page.evaluate('''() => {
        const main = document.querySelector('.menu-editor-main');
        const review = document.querySelector('.menu-editor-review');
        const form = document.querySelector('form[data-menu-editor]');
        if (!main || !review || !form) return null;
        const mainBox = main.getBoundingClientRect();
        const reviewBox = review.getBoundingClientRect();
        return {
            mainWidth: mainBox.width,
            reviewWidth: reviewBox.width,
            stacked: reviewBox.top >= mainBox.bottom - 1,
            reviewInForm: form.contains(review),
        };
    }''')
    assert layout is not None
    assert layout['mainWidth'] > layout['reviewWidth']
    assert not layout['reviewInForm']
    expect(page.locator('[data-review-scope="persisted"]')).to_contain_text('Zuletzt gespeicherter Stand')
    expect(page.locator('#review')).to_have_attribute('data-saved-review', '')


def test_a11_a12_editor_evidence_states(editor_page, family: str, javascript: bool) -> None:  # noqa: F811
    if family != 'patienten':
        pytest.skip('Ein Familienprofil genügt für viewportbezogene Bildbelege.')
    page, engine, scope, profile, _, base_url = editor_page
    page.goto(_menu_url(family))
    if not javascript:
        page.set_viewport_size({'width': 1366, 'height': 768})
        _capture(page, 'menu-editor-ohne-js-1366x768.png')
        return

    page.locator('[data-add-row="components-list"]').click()
    page.locator('[data-component-kind-option][value="text"]').last.check()
    page.locator('[name="component_text"]').last.fill('Dritte Beilage')
    page.locator('[data-finish-row]').last.click()
    for width, height in DENSITY_VIEWPORTS:
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
    _submit_menu_form(page, 400)
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


def test_a11_review_keeps_persisted_state_when_draft_changes(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.goto(_menu_url(family))
    review = page.locator('#review')
    expect(review).to_have_attribute('data-saved-review', '')
    expect(page.locator('[data-review-scope="persisted"]')).to_contain_text(
        'Zuletzt gespeicherter Stand — nicht der ungespeicherte Entwurf.',
    )
    saved_allergens = page.locator('[data-review-field="allergens"]').inner_text()
    saved_labels = page.locator('[data-review-field="labels"]').inner_text()
    saved_origins = page.locator('[data-review-field="origins"]').inner_text()
    assert saved_allergens.strip()
    assert saved_labels.strip()
    draft_title = 'Entwurf der nicht geprüft ist'
    page.get_by_label('Menüname', exact=True).fill(draft_title)
    allergen = page.locator('details[data-mode-section="allergen"]')
    if allergen.get_attribute('open') is None:
        allergen.locator('summary').click()
    milk = page.locator('[name="allergen_code"][value="MILK"]')
    if milk.count() and milk.is_enabled():
        milk.uncheck()
    expect(review).not_to_contain_text(draft_title)
    expect(page.locator('[data-review-field="allergens"]')).to_have_text(saved_allergens)
    expect(page.locator('[data-review-field="labels"]')).to_have_text(saved_labels)
    expect(page.locator('[data-review-field="origins"]')).to_have_text(saved_origins)
    expect(page.locator('.menu-editor-review-actions')).to_contain_text('gespeicherten Stand')
    if javascript:
        expect(page.locator('[data-menu-editor-dirty-note]')).to_have_class(re.compile(r'\bis-dirty\b'))


def test_cafeteria_has_both_prices_patient_has_none(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.goto(_menu_url(family))
    prices = page.locator('[name="internal_chf"], [name="external_chf"]')
    if family == 'cafeteria':
        expect(prices).to_have_count(2)
        expect(page.get_by_label('Mitarbeitende CHF', exact=True)).to_be_visible()
        expect(page.get_by_label('Preis für externe Gäste CHF', exact=True)).to_be_visible()
        return
    expect(prices).to_have_count(0)
    assert PATIENT_FORBIDDEN.search(page.content()) is None


def test_compact_assignments_and_native_kind_contract(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.goto(_menu_url(family))
    expect(page.locator('[data-add-row="components-list"]')).to_have_count(1)
    _assert_one_primary_save(page)
    rows = page.locator('#components-list .component-row')
    expect(rows).to_have_count(2)
    if javascript:
        expect(rows.first.locator('[data-component-summary-view]')).to_be_visible()
        expect(rows.first.locator('[data-component-edit-view]')).to_be_hidden()
        height = rows.first.evaluate('el => el.getBoundingClientRect().height')
        assert height >= 44
        expect(rows.get_by_role('button', name='Bearbeiten')).to_have_count(2)
        expect(rows.locator('[data-move-row="up"]')).to_have_count(2)
        expect(rows.locator('[data-remove-row]')).to_have_count(2)
    else:
        for row in rows.all():
            expect(row.locator('[name="component_public_id"]')).to_be_visible()
            expect(row.locator('[name="component_text"]')).to_be_visible()
    assert page.locator('[data-component-kind-option][name]').count() == 0


def test_a09_origin_error_opens_closed_details(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.goto(_menu_url(family))
    origin = page.locator('details[data-mode-section="origin"]')
    if origin.get_attribute('open') is None:
        origin.locator('summary').click()
    page.locator('[name="origin_mode"][value="manual"]').check()
    page.locator('[name="origin_ingredient"]').first.fill('Rind')
    page.locator('[name="origin_country_code"]').first.select_option('')
    if origin.get_attribute('open') is not None:
        origin.locator('summary').click()
    _submit_menu_form(page, 400)
    expect(page.locator('.error-region[role="alert"]')).to_be_visible()
    expect(page.locator('details[data-mode-section="origin"]')).to_have_attribute('open', '')
    expect(page.locator('[name="origin_ingredient"]').first).to_have_value('Rind')
    expect(page.get_by_label('Menüname', exact=True)).to_have_value('Herbstteller')
    _assert_one_primary_save(page)


def test_density_viewports_reflow_and_zoom_probe(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    if family != 'patienten':
        pytest.skip('Ein Familienprofil genügt für die Viewportmatrix.')
    page, *_rest, base_url = editor_page
    page.goto(_menu_url(family))
    for width, height in (*DENSITY_VIEWPORTS, (320, 844)):
        page.set_viewport_size({'width': width, 'height': height})
        _assert_no_overflow(page)
        _assert_one_primary_save(page)
        expect(page.locator('#review')).to_be_visible()
        if width >= 992:
            layout = page.evaluate('''() => {
                const main = document.querySelector('.menu-editor-main').getBoundingClientRect();
                const review = document.querySelector('.menu-editor-review').getBoundingClientRect();
                return {main: main.width, review: review.width, stacked: review.top >= main.bottom - 1};
            }''')
            assert layout['main'] > layout['review']
            assert not layout['stacked']
            if (width, height) == (1440, 900):
                for summary in page.locator('details.admin-accordion:not([open]) > summary').all():
                    summary.click()
                metrics = page.evaluate('''() => {
                    const main = document.querySelector('.menu-editor-main');
                    const aside = document.querySelector('.menu-editor-review');
                    const review = document.querySelector('#review');
                    const mainBox = main.getBoundingClientRect();
                    const asideBox = aside.getBoundingClientRect();
                    const reviewBox = review.getBoundingClientRect();
                    return {
                        mainHeight: mainBox.height,
                        asideHeight: asideBox.height,
                        mainBottom: mainBox.bottom,
                        asideBottom: asideBox.bottom,
                        reviewTop: reviewBox.top,
                        initialReviewY: window.scrollY + reviewBox.top,
                    };
                }''')
                assert abs(metrics['asideBottom'] - metrics['mainBottom']) <= 2
                scroll_target = metrics['initialReviewY'] + 150
                page.evaluate('(y) => window.scrollTo(0, y)', scroll_target)
                scrolled = page.evaluate('''() => {
                    const main = document.querySelector('.menu-editor-main').getBoundingClientRect();
                    const aside = document.querySelector('.menu-editor-review').getBoundingClientRect();
                    const review = document.querySelector('#review').getBoundingClientRect();
                    return {
                        scrollY: window.scrollY,
                        mainTop: main.top,
                        reviewTop: review.top,
                        asideBottom: aside.bottom,
                    };
                }''')
                assert scrolled['scrollY'] >= scroll_target - 1  # Chromium rounds CSS scroll pixels.
                assert scrolled['mainTop'] < 0
                assert 0 <= scrolled['reviewTop'] <= 30
                expect(page.locator('#review')).to_be_visible()
                expect(page.locator('#review')).to_have_attribute('data-saved-review', '')
                expect(page.locator('[data-review-scope="persisted"]')).to_be_visible()
                page.evaluate('() => window.scrollTo(0, 0)')
        else:
            layout = page.evaluate('''() => {
                const main = document.querySelector('.menu-editor-main').getBoundingClientRect();
                const review = document.querySelector('.menu-editor-review').getBoundingClientRect();
                const reviewBlock = document.querySelector('#review');
                return {
                    stacked: review.top >= main.bottom - 1,
                    position: window.getComputedStyle(reviewBlock).position,
                };
            }''')
            assert layout['stacked']
            assert layout['position'] == 'static'
    zoom_kind = 'css-viewport-dpr2-surrogate'
    try:
        session = page.context.new_cdp_session(page)
        session.send('Emulation.setPageScaleFactor', {'pageScaleFactor': 2})
        zoom_kind = 'cdp-page-scale-factor-2'
        _assert_no_overflow(page)
    except Exception as error:
        zoom_kind = f'css-viewport-dpr2-surrogate ({type(error).__name__})'
        with page.context.browser.new_context(
            base_url=base_url, viewport={'width': 720, 'height': 450},
            device_scale_factor=2, java_script_enabled=javascript, reduced_motion='reduce',
        ) as zoom:
            zoom.add_cookies(page.context.cookies())
            zoom_page = zoom.new_page()
            zoom_page.goto(_menu_url(family))
            _assert_no_overflow(zoom_page)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'zoom-probe.txt').write_text(f'{zoom_kind}\n', encoding='utf-8')
