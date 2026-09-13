"""Recipe view/print navigation, role boundaries and measured Tabler evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from playwright.sync_api import expect

from cafeteria import recipe_store as store, roles
from test_master_data_db import signed_in
from test_recipe_store_db import mutable, target
from test_dish_template_routes import create as create_template
import test_dish_template_browser as accessibility
from test_recipe_template_editor_browser import recipe_server  # noqa: F401
from test_recipe_template_editor_routes import (  # noqa: F401
    recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine, example, path, state,
)
from test_print_template_browser import browser, _context  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/recipe-view-print-0913'
VIEWPORTS = ((1440, 900, True), (390, 844, False), (390, 844, True),
             (1440, 900, False), (1024, 768, True), (768, 1024, True),
             (1920, 1080, True), (2560, 1440, True))


@pytest.fixture
def view_print(recipe_editor, monkeypatch):
    recipe, revision, _ = example(recipe_editor)
    template = create_template(recipe_editor[2], title='Gericht zur Suppe', recipe_public_id=recipe)
    monkeypatch.setattr(accessibility, 'EVIDENCE', EVIDENCE)
    return recipe, revision, template


def routes(recipe, revision):
    root = f'/admin/rezepte/{recipe}'
    return [('recipes', '/admin/rezepte'), ('view', root + '/ansicht'),
            ('revisions', root + '/revisionen'), ('revision', root + '/revisionen/' + revision.public_id),
            ('dish-templates', '/admin/gerichtvorlagen'), ('print-template', path(recipe, revision.public_id))]


@pytest.mark.parametrize('width,height,javascript', VIEWPORTS)
def test_view_print_route_matrix_and_native_links(view_print, recipe_editor, recipe_server, browser,
                                                width, height, javascript):
    recipe, revision, template = view_print
    _, owner, client, _ = recipe_editor
    before = state(owner)
    with _context(browser, recipe_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': height})
        methods, errors = [], []
        page.on('request', lambda request: methods.append(request.method))
        page.on('pageerror', lambda error: errors.append(str(error)))
        for label, route in routes(recipe, revision):
            assert page.goto(route).status == 200
            for glyph in page.locator('main use').all():
                if glyph.evaluate('el => el.closest("svg").getClientRects().length > 0'):
                    assert glyph.evaluate('el => el.getBBox().width > 0'), glyph.get_attribute('href')
            accessibility._accessible_capture(page, f'{label}-{width}x{height}-js{javascript}', methods=methods.copy())
        page.goto('/admin/rezepte')
        card = page.locator('article').filter(has=page.get_by_role('heading', name='Suppe', exact=True))
        view = card.get_by_role('link', name='Suppe ansehen', exact=True)
        edit = card.get_by_role('link', name='Suppe bearbeiten', exact=True)
        pdf = card.get_by_role('link', name='Drucken · Stand 1 · Suppe', exact=True)
        assert len({view.get_attribute('href'), edit.get_attribute('href'), pdf.get_attribute('href')}) == 3
        response = client.get(pdf.get_attribute('href'))
        assert response.status_code == 200 and response.data.startswith(b'%PDF-')
        assert response.headers['X-Recipe-Revision'] == revision.public_id
        view.focus()
        expect(view).to_be_focused()
        assert view.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        with page.expect_navigation() as navigation:
            page.keyboard.press('Enter')
        assert navigation.value.status == 200
        expect(page.get_by_text('Entwurf · nicht festgeschrieben', exact=True)).to_be_visible()
        assert page.locator('main [name="_form_context"]').count() == 0
        page.get_by_label('Zielmenge · PORTION', exact=True).fill('8')
        page.get_by_role('button', name='Mengen berechnen', exact=True).click()
        assert 'yield=8' in page.url
        expect(page.locator('main table tbody tr').first.locator('[data-label="Berechnet"]')).to_have_text('2')
        page.get_by_role('link', name='Gericht zur Suppe', exact=True).click()
        assert page.url.endswith(template)
        page.goto('/admin/gerichtvorlagen')
        page.get_by_role('link', name='Rezept: Suppe', exact=True).click()
        assert page.url.endswith(f'/admin/rezepte/{recipe}/ansicht')
        expect(page.get_by_role('link', name='Standard · Revision 1 (aktiv)', exact=True)).to_be_visible()
        page.get_by_role('link', name='Standard · Revision 1 (aktiv)', exact=True).click()
        assert page.url.endswith(f'template=standard&revision=1&recipe={recipe}')
        page.get_by_role('link', name='Zurück zum Rezept «Suppe»', exact=True).click()
        assert page.url.endswith(f'/admin/rezepte/{recipe}/ansicht')
        assert not errors and set(methods) == {'GET'}
    assert state(owner) == before


@pytest.mark.parametrize('width,javascript', [(390, False), (1440, True)])
def test_reader_view_print_without_write_actions(view_print, recipe_editor, recipe_server, browser,
                                               monkeypatch, width, javascript):
    recipe, revision, _ = view_print
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Admin', {'draft.read'})
    before = state(recipe_editor[1])
    with _context(browser, recipe_server, recipe_editor[2], width, javascript=javascript) as context:
        page = context.new_page()
        for label, route in routes(recipe, revision)[:4]:
            assert page.goto(route).status == 200
            assert page.locator('main a[href="/admin/rezepte/' + recipe + '"]').count() == 0
            assert page.locator('main [name="_form_context"]').count() == 0
            assert page.locator('main a[href*="/vorlagen/rezepte?"]').count() == 0
            assert page.get_by_role('button', name='Gespeicherten Stand festhalten', exact=True).count() == 0
            assert page.get_by_role('link', name='Vorlage anlegen', exact=True).count() == 0
            accessibility._accessible_capture(page, f'{label}-reader-{width}-js{javascript}', methods=['GET'])
    assert state(recipe_editor[1]) == before


def test_real_browser_zoom_and_320_reflow(view_print, recipe_editor, recipe_server, browser, tmp_path):
    recipe, revision, _ = view_print
    cookie = recipe_editor[2].get_cookie(recipe_editor[0].config['SESSION_COOKIE_NAME'])
    before = state(recipe_editor[1])
    with TemporaryDirectory(prefix='recipe-view-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(profile, channel='chromium', headless=True,
                no_viewport=True, locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
                args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900']) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': recipe_server}])
            for label, route in routes(recipe, revision):
                assert page.goto(recipe_server + route).status == 200
                assert page.evaluate('devicePixelRatio') == 2 and page.evaluate('innerWidth') == 720
                accessibility._accessible_capture(page, f'{label}-native-200-percent', methods=['GET'], native=True)
    with _context(browser, recipe_server, recipe_editor[2], 320) as context:
        page = context.new_page()
        for label, route in routes(recipe, revision):
            assert page.goto(route).status == 200
            accessibility._accessible_capture(page, f'{label}-reflow-320', methods=['GET'])
    assert state(recipe_editor[1]) == before


@pytest.mark.parametrize('width,height,javascript', [(390, 844, False), (1440, 900, True)])
def test_history_opens_each_of_three_archived_stands(view_print, recipe_editor, recipe_server, browser,
                                                 monkeypatch, width, height, javascript):
    recipe, first, _ = view_print
    app, owner, client, actor = recipe_editor
    engine = app.extensions['cafeteria_db']
    revisions = [first]
    with signed_in(engine, actor):
        location = store.get_location(engine)
        for number in (2, 3):
            row = store.get_recipe(engine, recipe)
            data = mutable(row.payload)
            data['description'] = f'Anleitung für gespeicherten Stand {number}'
            row = store.update_recipe(engine, actor, target(row), data, expected_location_id=location)
            preview = store.get_dependency_preview(engine, target(row), expected_location_id=location)
            revisions.append(store.freeze_revision(engine, actor, target(row), expected_location_id=location,
                             expected_dependency_hash=preview.dependency_hash_sha256))
        row = store.get_recipe(engine, recipe)
        data = mutable(row.payload)
        data['description'] = 'Aktueller Entwurf nach Stand 3'
        row = store.update_recipe(engine, actor, target(row), data, expected_location_id=location)
        store.set_recipe_active(engine, actor, target(row), active=False, expected_location_id=location)
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Admin', {'draft.read'})
    before = state(owner)
    with _context(browser, recipe_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': height})
        root = f'/admin/rezepte/{recipe}'
        assert page.goto(root + '/revisionen').status == 200
        expect(page.get_by_role('heading', name='Rezept-History', exact=True)).to_be_visible()
        expect(page.locator('#recipe-history time')).to_have_count(3)
        accessibility._accessible_capture(page, f'history-three-{width}', methods=['GET'])
        for number, revision in enumerate(revisions, 1):
            link = page.get_by_role('link', name=f'Gespeicherten Stand {number} ansehen', exact=True)
            link.focus()
            expect(link).to_be_focused()
            with page.expect_navigation() as navigation:
                page.keyboard.press('Enter')
            assert navigation.value.status == 200
            assert page.url.endswith(root + '/revisionen/' + revision.public_id)
            expect(page.get_by_role('heading', name=f'Gespeicherter Stand {number}', exact=True)).to_be_visible()
            summary = page.locator('main section.card').first
            expect(summary.get_by_text('Erster Absatz' if number == 1 else f'Anleitung für gespeicherten Stand {number}', exact=False)).to_be_visible()
            expect(page.get_by_text('Aktueller Entwurf nach Stand 3', exact=True)).to_have_count(0)
            accessibility._accessible_capture(page, f'history-stand-{number}-{width}', methods=['GET'])
            page.get_by_role('link', name='Zur Rezept-History', exact=True).click()
        page.get_by_role('link', name='Aktuellen Entwurf ansehen', exact=True).click()
        expect(page.get_by_text('Aktueller Entwurf nach Stand 3', exact=True)).to_be_visible()
    assert state(owner) == before
