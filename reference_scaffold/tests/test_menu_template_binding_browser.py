"""Native and JS form flows; screenshots are evidence, never replacement baselines."""
from pathlib import Path

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from test_admin_ux_browser import _submit_menu, live_server  # noqa: F401
from test_admin_workflow_routes import DAY, _hidden, _login, _menu_form
from test_menu_template_binding_db import make_template, stored_state
from test_menu_template_binding_routes import proposal, proposal_form
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/menu-template-binding-0913'
VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080), (2560, 1440), (320, 900))


@pytest.mark.parametrize('family', ('patienten', 'cafeteria'))
@pytest.mark.parametrize('javascript', (True, False))
def test_archived_provenance_native_roundtrip_and_viewports(
    browser, live_server, admin_app, admin_engine, family, javascript,  # noqa: F811
):
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    action = f'/admin/{family}/menu'
    editor = f'{action}?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
    initial = client.get(editor)
    csrf = _hidden(initial.text, '_csrf', form_action=action)
    prices = {'internal_chf': '9.50', 'external_chf': '14.50'} if family == 'cafeteria' else {}
    assert client.post(action, data=_menu_form(_csrf=csrf, title='Rösti mit Gemüse',
        dish_template_public_id=template['public_id'], component_public_id='', component_text='Rösti',
        recipe_revision_public_id='', origin_ingredient='Kartoffel', origin_country_code='CH', **prices)).status_code == 303
    with admin_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.dish_templates SET active=false WHERE id=:id'), template)
    context = browser.new_context(base_url=live_server, java_script_enabled=javascript,
                                  reduced_motion='reduce')
    context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value,
                         'url': live_server, 'httpOnly': True}])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        page = context.new_page()
        assert page.goto(editor).status == 200
        link = page.get_by_role('link', name='Aus Vorlage «Rösti» (archiviert)', exact=True)
        expect(link).to_be_visible()
        expect(page.get_by_label('Vorlagenbezug lösen', exact=True)).not_to_be_checked()
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate('document.fonts.ready')
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
            box = link.bounding_box()
            assert box and box['height'] >= 48
            assert page.evaluate('document.fonts.status') == 'loaded'
            link.focus()
            assert link.evaluate('(el) => getComputedStyle(el).outlineStyle') != 'none'
            page.screenshot(path=str(EVIDENCE / f'editor-{family}-{width}-{javascript}.png'))
        page.set_viewport_size({'width': 390, 'height': 844})
        page.get_by_label('Menüname', exact=True).fill('Rösti – eigener Titel')
        submitted = _submit_menu(page, 303)
        assert submitted['dish_template_public_id'] == [template['public_id']]
        expect(link).to_be_visible()
        checkbox = page.get_by_label('Vorlagenbezug lösen', exact=True)
        checkbox.focus()
        page.keyboard.press('Space')
        expect(checkbox).to_be_checked()
        submitted = _submit_menu(page, 303)
        assert submitted['dish_template_detach'] == ['1']
        expect(page.get_by_role('link', name='Aus Vorlage «Rösti» (archiviert)', exact=True)).to_have_count(0)
        with admin_engine.connect() as connection:
            assert connection.execute(text('SELECT title,dish_template_id FROM cafeteria.menu_items')).one() == ('Rösti – eigener Titel', None)
    finally:
        context.close()


@pytest.mark.parametrize('javascript', (True, False))
def test_proposal_conflict_resubmit_preserves_original_hidden_authority(
    browser, live_server, admin_app, admin_engine, javascript,  # noqa: F811
):
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    template = make_template(admin_engine)
    _, token, url = proposal(admin_app, admin_engine, actor, template)
    form = proposal_form(client, url, token, template)
    context = browser.new_context(base_url=live_server, java_script_enabled=javascript,
                                  viewport={'width': 390, 'height': 844})
    context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value,
                         'url': live_server, 'httpOnly': True}])
    try:
        page = context.new_page()
        assert page.goto(url).status == 200
        page.get_by_label('Menüname', exact=True).fill('Mein Vorschlag')
        if javascript:
            page.locator('[data-edit-row]').first.click()
            page.locator('[data-component-kind-option][value="text"]').first.check()
        page.locator('[name="component_text"]').first.fill('Rösti')
        assert client.post('/admin/patienten/menu', data=form).status_code == 303
        before = stored_state(admin_engine)
        first = _submit_menu(page, 409)
        second = _submit_menu(page, 409)
        assert first['template_context'] == second['template_context'] == [token]
        assert first['_csrf'] == second['_csrf']
        assert first['row_version'] == second['row_version'] == ['0']
        expect(page.get_by_label('Menüname', exact=True)).to_have_value('Mein Vorschlag')
        expect(page.get_by_role('link', name='Bestehendes Menü öffnen', exact=True)).to_be_visible()
        assert stored_state(admin_engine) == before
        page.screenshot(path=str(EVIDENCE / f'proposal-conflict-{javascript}.png'), full_page=True)
    finally:
        context.close()
