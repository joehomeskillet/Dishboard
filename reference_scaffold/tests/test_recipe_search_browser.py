"""Real native full-text search field on `/admin/rezepte` at mobile/desktop sizes,
without JavaScript (NoJS GET submit)."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qsl

import pytest
from flask import template_rendered
from playwright.sync_api import expect, sync_playwright

from test_master_data_browser import master_server  # noqa: F401
from test_recipe_filter_reads import recipe_ids
from test_recipe_search_db import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, search_lab, seeded_pg16, step,
)
from test_rendered_ui import browser  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/fts-ui-0915'


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_native_text_search_is_keyboard_operable_ranked_and_no_overflow(
        b3, search_lab, master_server, browser, width, height):  # noqa: F811
    lab = search_lab
    title_hit = lab['recipe']('Zauberwort Auflauf')
    lab['recipe']('Andere Suppe', steps=[step('Sauce langsam passieren')])
    base, cookie = master_server
    evidence = EVIDENCE
    evidence.mkdir(parents=True, exist_ok=True)
    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=False,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, writes = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('request', lambda request: writes.append(request.method) if request.method != 'GET' else None)
        response = page.goto(base + '/admin/rezepte')
        assert response.status == 200 and response.headers['cache-control'] == 'no-store'
        form = page.locator('form[action="/admin/rezepte"]')
        assert form.get_attribute('method') == 'get'
        assert form.get_attribute('data-loading') == 'Rezepte suchen'
        control = page.get_by_label('Suche', exact=True)
        assert control.get_attribute('id') == 'text'
        assert control.get_attribute('maxlength') == '200'
        assert 'text-hint' in (control.get_attribute('aria-describedby') or '')
        control.focus()
        expect(control).to_be_focused()
        assert control.bounding_box()['height'] >= 44
        control.fill('zauberwort')
        page.get_by_role('button', name='Filtern', exact=True).focus()
        expect(page.get_by_role('button', name='Filtern', exact=True)).to_be_focused()
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        assert 'text=zauberwort' in page.url
        expect(page.locator('.recipe-card')).to_have_count(1)
        expect(page.locator('.admin-list-row')).to_have_count(1)
        expect(page.locator('.recipe-card .admin-list-name strong')).to_have_text('Zauberwort Auflauf')
        expect(page.locator('.recipe-card .admin-status--info').first).to_be_visible()
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('form[role="search"] button[type="submit"] use')).to_have_attribute(
            'href', re.compile(r'#tabler-filter$'))
        assert recipe_ids(page.content()) == [title_hit.public_id]
        expect(page.get_by_text('Sortiert nach Relevanz.', exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.get_by_role('heading', level=1).scroll_into_view_if_needed()
        page.screenshot(path=str(evidence / f'recipes-search-{width}x{height}.png'), caret='initial')
        assert not errors and not writes


@pytest.mark.parametrize('javascript', [False, True])
def test_recipe_frame_measurements(search_lab, master_server, tmp_path, javascript):  # noqa: F811
    """Measure real layout with an independent browser, including native disclosures."""
    search_lab['recipe']('Dichteprobe Suppe')
    search_lab['recipe']('Dichteprobe Gemüse')
    base, cookie = master_server
    def inspect():
        with sync_playwright() as playwright:
            instance = playwright.chromium.launch(
                headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            try:
                with instance.new_context(java_script_enabled=javascript, reduced_motion='reduce') as context:
                    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
                    page = context.new_page()
                    for width, height in [(360, 844), (768, 1024), (1024, 768), (1440, 900)]:
                        page.set_viewport_size({'width': width, 'height': height})
                        assert page.goto(base + '/admin/rezepte').status == 200
                        page.evaluate('document.fonts.ready')
                        measurements = page.evaluate('''() => {
                            const box = selector => document.querySelector(selector).getBoundingClientRect();
                            return {width: innerWidth, height: document.documentElement.scrollHeight,
                                filter: box('form[action="/admin/rezepte"]').height,
                                first: box('.recipe-card').top, row: box('.recipe-card').height,
                                overflow: document.documentElement.scrollWidth > innerWidth + 1};
                        }''')
                        shot = tmp_path / f'frame-{width}-js-{javascript}.png'
                        page.screenshot(path=str(shot), full_page=True)
                        print('WP07_METRICS ' + json.dumps(measurements | {'javascript': javascript, 'shot': str(shot)}))
                        assert not measurements['overflow']
                        expect(page.locator('dl.admin-statusbar')).to_contain_text('Aktiv')
                        expect(page.locator('main .btn-primary')).to_have_count(1)
                        assert measurements['filter'] < (330 if width == 360 else 210)
                        assert measurements['row'] < (230 if width == 360 else 180)
                        summary = page.locator('form[role="search"] .admin-filter-more > summary')
                        summary.focus()
                        expect(summary).to_be_focused()
                        assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
                        page.keyboard.press('Enter')
                        expect(page.get_by_label('Nach Rezepttitel suchen', exact=True)).to_be_visible()
                        page.keyboard.press('Enter')
                        assert page.get_by_role('button', name='Filtern', exact=True).bounding_box()['height'] >= 48
                        expect(page.locator('.admin-list-row')).to_have_count(2)
                        expect(page.locator('.admin-list-row .admin-status--info')).to_have_count(2)
            finally:
                instance.close()

    with ThreadPoolExecutor(max_workers=1) as worker:
        worker.submit(inspect).result()


@pytest.mark.parametrize('javascript', [False, True])
def test_editor_disclosures_preserve_complete_native_post(
        b3, search_lab, master_server, tmp_path, javascript):  # noqa: F811
    from cafeteria import recipe_store, master_data_store as masters
    from test_recipe_store_db import line

    tag = masters.create_vocabulary(search_lab['engine'], 'tag', search_lab['actor'],
                                    code='WP07', name='Formularvertrag Kennzeichnung')
    recipe = search_lab['recipe']('Formularvertrag', tag_public_ids=[tag.public_id],
        ingredients=[line(f'Zutat {index}') for index in range(4)],
        steps=[step('Waschen und vorbereiten'), step('Kochen und abschmecken')])
    app = b3[0]
    original_payload = recipe_store.get_recipe(search_lab['engine'], recipe.public_id).payload
    rendered = {}

    def capture(sender, template, context, **extra):
        if template.name == 'admin/rezepte_editor.html':
            rendered['fields'] = sorted(context['data'].items(multi=True))

    base, cookie = master_server
    def inspect():
        with sync_playwright() as playwright:
            instance = playwright.chromium.launch(
                headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            try:
                with instance.new_context(java_script_enabled=javascript, reduced_motion='reduce') as context:
                    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
                    page = context.new_page()
                    with template_rendered.connected_to(capture, app):
                        assert page.goto(base + f'/admin/rezepte/{recipe.public_id}').status == 200
                    expected = rendered['fields']
                    form = page.locator('#recipe-editor')
                    for width, height in [(360, 844), (768, 1024), (1024, 768), (1440, 900)]:
                        page.set_viewport_size({'width': width, 'height': height})
                        page.evaluate('document.fonts.ready')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                        expect(page.locator('main .btn-primary')).to_have_count(1)
                        expect(page.locator('.admin-statusbar')).to_contain_text('Entwurf')
                        assert sorted(map(tuple, form.evaluate('f => [...new FormData(f)]'))) == expected
                        page.screenshot(path=str(tmp_path / f'editor-{width}-js-{javascript}.png'), full_page=True)
                    page.get_by_label('Aktionen für Zutat 1', exact=True).click()
                    remove = page.locator('button[formaction*="row_action=remove"]').first
                    assert 'btn-danger' in (remove.get_attribute('class') or '').split()
                    expect(remove.locator('span')).to_have_text('Entfernen')
                    assert remove.get_attribute('formnovalidate') is not None
                    assert '/admin/rezepte/formular?' in (remove.get_attribute('formaction') or '')
                    expect(page.locator('.ui-sem-consequence').first).to_be_visible()
                    source = page.locator('#recipe-source > summary')
                    source.focus()
                    page.keyboard.press('Enter')
                    expect(page.get_by_label('Quellennotiz', exact=True)).to_be_visible()
                    page.keyboard.press('Enter')
                    assert sorted(map(tuple, form.evaluate('f => [...new FormData(f)]'))) == expected
                    with page.expect_request(lambda request: request.method == 'POST') as submitted:
                        page.get_by_role('button', name='Speichern', exact=True).click()
                    # Native URL-encoded submission uses CRLF, unlike DOM FormData.
                    wire_expected = [(name, value.replace('\n', '\r\n')) for name, value in expected]
                    assert sorted(parse_qsl(submitted.value.post_data, keep_blank_values=True)) == wire_expected
                    page.wait_for_load_state()
                    print(f'WP07_POST fields={len(expected)} javascript={javascript} unchanged=True')
            finally:
                instance.close()

    with ThreadPoolExecutor(max_workers=1) as worker:
        worker.submit(inspect).result()
    current = recipe_store.get_recipe(search_lab['engine'], recipe.public_id)
    assert current.payload == original_payload


def test_unfiltered_empty_list_keeps_single_primary_add(master_server, browser):  # noqa: F811
    base, cookie = master_server
    with browser.new_context(viewport={'width': 1440, 'height': 900}, java_script_enabled=False,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + '/admin/rezepte').status == 200
        expect(page.locator('[data-empty-kind="none"] .empty-title')).to_have_text('Noch keine Rezepte')
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('.page-header .btn-primary')).to_have_attribute('data-semantic', 'actions.add')
        expect(page.locator('[data-empty-kind="none"] .btn-primary')).to_have_count(0)
        expect(page.locator('[data-empty-kind="none"] [data-semantic="actions.add"]')).to_be_visible()
