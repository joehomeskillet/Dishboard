"""UC-P3-a: real HTTP evidence for cookbook density and recipe screen/print content."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect

from cafeteria import recipe_store as store
from test_cookbooks_browser import cookbook_server  # noqa: F401
from test_master_data_db import signed_in
from test_recipe_view_print_browser import (  # noqa: F401
    readable_recipe, recipe_editor, recipe_server, browser,
    b3, pg16, installed_pg16, seeded_pg16, app_engine,
)


DESCRIPTION = 'Saisonale Rezepte für die Gemeinschaftsküche, sortiert nach Aufwand. ' * 6
VIEWPORTS = [(1440, 900), (390, 844)]


def _page(context, coarse):
    page = context.new_page()
    cdp = context.new_cdp_session(page)
    cdp.send('Emulation.setEmulatedMedia', {'features': [
        {'name': 'pointer', 'value': 'coarse' if coarse else 'fine'},
        {'name': 'any-pointer', 'value': 'coarse' if coarse else 'fine'},
    ]})
    assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
    return page, cdp


def _destination(tmp_path):
    destination = Path(os.environ.get('UC_P3A_EVIDENCE', tmp_path))
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def test_cookbook_density_and_complete_description(cookbook_server, browser, tmp_path):  # noqa: F811
    server = cookbook_server
    with signed_in(server['engine'], server['actor']):
        location = store.get_location(server['engine'])
        store.create_cookbook(server['engine'], server['actor'], name='Alltagsküche',
                              description=DESCRIPTION, expected_location_id=location)
    destination, measurements = _destination(tmp_path), {}
    for width, height in VIEWPORTS:
        for coarse in (False, True):
            label = f'{width}-{"coarse" if coarse else "fine"}'
            with browser.new_context(viewport={'width': width, 'height': height},
                                     has_touch=coarse, reduced_motion='reduce') as context:
                cookie = server['cookie']
                context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server['base']}])
                page, cdp = _page(context, coarse)
                assert page.goto(server['base'] + '/admin/kochbuecher').status == 200
                page.evaluate('document.fonts.ready')
                row = page.locator('.cookbook-list tbody tr')
                expect(row).to_have_count(1)
                measurements[label] = row.evaluate('''row => {
                    const rect = element => {
                        const {x, y, width, height} = element.getBoundingClientRect();
                        return {x, y, width, height};
                    };
                    const description = row.querySelector('.admin-list-subtitle');
                    return {row: rect(row), description: rect(description),
                        title: description.title, text: description.textContent,
                        ellipsis: getComputedStyle(description).textOverflow,
                        scrollWidth: document.documentElement.scrollWidth, innerWidth,
                        actions: [...row.querySelectorAll('.btn')].map(rect)};
                }''')
                page.screenshot(path=str(destination / f'cookbooks-{label}.png'), full_page=True)
                for action in row.locator('.btn').all():
                    action.focus()
                    expect(action).to_be_focused()
                cdp.detach()
    (destination / 'cookbooks-density.json').write_text(json.dumps(measurements, indent=2))
    for label, values in measurements.items():
        assert values['scrollWidth'] <= values['innerWidth']
        minimum = 44 if 'coarse' in label else 36
        assert all(a['width'] >= minimum and a['height'] >= minimum for a in values['actions'])
        assert values['title'] == DESCRIPTION.strip()
        assert values['text'] == DESCRIPTION.strip()
        assert values['ellipsis'] == 'ellipsis'
        if label.startswith('390'):
            assert values['row']['height'] <= 155
            assert values['description']['height'] <= 21


def test_recipe_document_screen_and_print(readable_recipe, recipe_editor, recipe_server, browser, tmp_path):  # noqa: F811
    recipe, revision = readable_recipe
    app, _, client, _ = recipe_editor
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    destination, measurements = _destination(tmp_path), {}
    for width, height in VIEWPORTS:
        for coarse in (False, True):
            label = f'{width}-{"coarse" if coarse else "fine"}'
            with browser.new_context(viewport={'width': width, 'height': height},
                                     has_touch=coarse, reduced_motion='reduce') as context:
                context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': recipe_server}])
                page, cdp = _page(context, coarse)
                assert page.goto(f'{recipe_server}/admin/rezepte/{recipe}/revisionen/{revision}').status == 200
                page.evaluate('document.fonts.ready')
                document = page.locator('#recipe-document')
                expect(document.locator('.recipe-ingredient')).to_have_count(4)
                expect(document.locator('.recipe-steps > li')).to_have_count(2)
                expect(document).to_contain_text('Vorbereitung: 0 Minuten')
                expect(document).to_contain_text('Kochzeit: 20 Minuten')
                page.screenshot(path=str(destination / f'recipe-{label}.png'), full_page=True)
                expect(page.locator('.recipe-originals > h2')).to_have_text('Originalmengen')
                expect(page.locator('.recipe-provenance > h2')).to_have_text('Herkunft')
                expect(document.locator('details, summary')).to_have_count(0)
                expect(document.locator('.recipe-original-quantities > div')).to_have_text([
                    'Karotte: 800 G', 'Wasser: 200 G', 'Salz: 8 G', 'Kräuter: 4 G',
                ])
                page.emulate_media(media='print')
                measurements[label] = document.evaluate('''element => ({
                    text: element.innerText,
                    parts: [...element.querySelectorAll('.recipe-metadata, .recipe-ingredient, .recipe-steps, .recipe-originals')]
                        .map(el => {const {x,y,width,height} = el.getBoundingClientRect();
                            return {text: el.innerText, x,y,width,height};}),
                    scrollWidth: document.documentElement.scrollWidth, innerWidth
                })''')
                document.screenshot(path=str(destination / f'recipe-print-{label}.png'))
                assert measurements[label]['scrollWidth'] <= width
                cdp.detach()
    (destination / 'recipe-print-density.json').write_text(json.dumps(measurements, indent=2))
