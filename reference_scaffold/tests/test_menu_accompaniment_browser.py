"""Browser coverage for REC-008 accompaniment controls and week cards."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

from test_admin_ux_browser import _submit_menu, live_server  # noqa: F401
from test_admin_workflow_routes import DAY, _login
from test_menu_template_binding_db import make_template
from test_menu_template_binding_routes import proposal
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401
from test_ui_menu_editor_browser import (  # noqa: F401
    editor_page,
    family,
    javascript,
)

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/acc-editor-ui-0913'


def _menu_url(family_name: str) -> str:
    return f'/admin/{family_name}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


def _assert_no_overflow(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def test_editor_radio_roundtrip_and_week_card_in_both_grids(
    editor_page, family: str, javascript: bool,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.set_viewport_size({'width': 1440, 'height': 900})
    response = page.goto(_menu_url(family))
    assert response is not None and response.status == 200

    group = page.get_by_role('group', name='Suppe oder Salat dazu')
    expect(group).to_have_count(1)
    none = page.locator('#accompaniment-none')
    soup = page.locator('#accompaniment-soup')
    salad = page.locator('#accompaniment-salad')
    expect(none).to_be_checked()
    expect(soup).not_to_be_checked()
    expect(salad).not_to_be_checked()
    expect(page.get_by_text('Aus Vorlage vorgeschlagen', exact=True)).to_have_count(0)
    sizes = group.locator('label.form-check').evaluate_all(
        'labels => labels.map(label => label.getBoundingClientRect().height)'
    )
    assert len(sizes) == 3 and all(size >= 48 for size in sizes), sizes

    salad.check()
    submitted = _submit_menu(page, 303)
    assert submitted['accompaniment'] == ['salad']
    expect(page.locator('#accompaniment-salad')).to_be_checked()
    review = page.locator('[data-review-field="accompaniment"]')
    expect(review).to_have_text('Dazu: Salat (gemischt und grün)')
    assert 'bestätigt' not in review.inner_text().lower()

    response = page.goto(f'/admin/{family}?week={DAY}')
    assert response is not None and response.status == 200
    card = page.locator(
        f'.menu-slot[data-day="{DAY}"][data-meal="LUNCH"][data-option="MENU_1"]'
    )
    expect(card.locator('.menu-accompaniment')).to_have_text(
        'Dazu: Salat (gemischt und grün)'
    )
    expect(card.locator('.menu-accompaniment use[href$="#tabler-salad"]')).to_have_count(1)
    expect(page.locator('.menu-accompaniment')).to_have_count(1)

    # Soup roundtrip
    page.goto(_menu_url(family))
    soup = page.locator('#accompaniment-soup')
    soup.check()
    submitted = _submit_menu(page, 303)
    assert submitted['accompaniment'] == ['soup']
    expect(page.locator('#accompaniment-soup')).to_be_checked()
    expect(page.locator('[data-review-field="accompaniment"]')).to_have_text('Dazu: Suppe')

    page.goto(f'/admin/{family}?week={DAY}')
    expect(card.locator('.menu-accompaniment')).to_have_text('Dazu: Suppe')
    expect(card.locator('.menu-accompaniment use[href$="#tabler-soup"]')).to_have_count(1)


@pytest.mark.parametrize('family', ['patienten'])
@pytest.mark.parametrize('javascript', [True], indirect=True, ids=['js'])
def test_invalid_value_links_error_to_radio_group_and_retains_other_values(
    editor_page, family: str,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.goto(_menu_url(family))
    
    soup = page.locator('#accompaniment-soup')
    soup.check()
    page.get_by_label('Menüname', exact=True).fill('')
    
    _submit_menu(page, 400)
    
    expect(page.locator('#accompaniment-soup')).to_be_checked()
    expect(page.locator('.error-region a[href="#f-title"]')).to_have_count(1)
    
    review = page.locator('[data-review-field="accompaniment"]')
    expect(review).to_have_text('Keine Beilage')

    # Also test invalid accompaniment value explicitly
    page.evaluate("document.getElementById('accompaniment-none').value = 'both';")
    page.locator('#accompaniment-none').check()
    page.get_by_label('Menüname', exact=True).fill('Valid Title')
    _submit_menu(page, 400)
    
    expect(page.locator('.error-region a[href="#accompaniment-none"]')).to_have_count(1)
    expect(page.locator('#err-accompaniment')).to_be_visible()
    expect(page.locator('[name="accompaniment"][aria-invalid="true"]')).to_have_count(3)


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_template_proposal_prefills_salad_and_shows_proposal_hint(
    browser, live_server, admin_app, admin_engine, javascript,  # noqa: F811
) -> None:
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    with admin_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE cafeteria.dish_templates SET accompaniment_default='salad' "
                'WHERE id=:id'
            ),
            template,
        )
    _, _, url = proposal(admin_app, admin_engine, actor, template)
    context = browser.new_context(
        base_url=live_server,
        java_script_enabled=javascript,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        reduced_motion='reduce',
    )
    cookie = client.get_cookie('session')
    assert cookie is not None
    context.add_cookies([{
        'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True,
    }])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        page = context.new_page()
        response = page.goto(url)
        assert response is not None and response.status == 200
        expect(page.locator('#accompaniment-salad')).to_be_checked()
        expect(page.get_by_text('Aus Vorlage vorgeschlagen', exact=True)).to_be_visible()
        for width, height in ((1440, 900), (390, 844)):
            page.set_viewport_size({'width': width, 'height': height})
            _assert_no_overflow(page)
            page.screenshot(
                path=str(EVIDENCE / f'proposal-{width}x{height}-{"js" if javascript else "nojs"}.png'),
                full_page=True,
            )
        page.locator('#accompaniment-none').check()
        with page.expect_navigation():
            page.locator('form[data-menu-editor] button[type="submit"]').click()
        card = page.locator('#menu-LUNCH-MENU_1')
        expect(card.locator('.menu-accompaniment')).to_have_count(0)
    finally:
        context.close()


@pytest.mark.parametrize('family', ['patienten'])
@pytest.mark.parametrize('javascript', [True], indirect=True, ids=['js'])
def test_radio_keyboard_mobile_reflow_and_200_percent_zoom(
    editor_page, family: str,  # noqa: F811
) -> None:
    page, *_ = editor_page
    page.set_viewport_size({'width': 1440, 'height': 900})
    page.goto(_menu_url(family))
    none = page.locator('#accompaniment-none')
    none.focus()
    expect(none).to_be_focused()
    none.press('ArrowRight')
    expect(page.locator('#accompaniment-soup')).to_be_checked()

    page.set_viewport_size({'width': 390, 'height': 844})
    labels = page.locator('.menu-accompaniment-options label.form-check')
    tops = labels.evaluate_all(
        'items => items.map(item => Math.round(item.getBoundingClientRect().top))'
    )
    assert len(tops) == len(set(tops)) == 3, tops
    _assert_no_overflow(page)

    session = page.context.new_cdp_session(page)
    session.send('Emulation.setPageScaleFactor', {'pageScaleFactor': 2})
    _assert_no_overflow(page)
    expect(page.get_by_role('group', name='Suppe oder Salat dazu')).to_be_visible()
