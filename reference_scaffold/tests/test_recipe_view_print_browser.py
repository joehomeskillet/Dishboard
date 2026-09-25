"""Recipe view/print navigation, role boundaries and measured Tabler evidence."""
import re
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

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/recipe-reading-html-0913'
VIEWPORTS = ((1440, 900, True), (390, 844, False), (390, 844, True),
             (1440, 900, False), (1024, 768, True), (768, 1024, True),
             (1920, 1080, True), (2560, 1440, True), (320, 844, True), (320, 844, False))


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
            if label == 'print-template':
                expect(page.locator('#recipe-search')).to_have_attribute('maxlength', '200')
                expect(page.locator('#recipe-search')).to_have_attribute('name', 'q')
                page.locator('[data-recipe-selection] > summary').click()
                original_yield = page.get_by_role('link', name='Originalausbeute verwenden', exact=True)
                expect(original_yield).to_contain_text('Originalausbeute')
                assert 'Originalausbeute' in (original_yield.get_attribute('aria-label') or '')
            for glyph in page.locator('main use').all():
                if glyph.evaluate('el => el.closest("svg").getClientRects().length > 0'):
                    assert glyph.evaluate('el => el.getBBox().width > 0'), glyph.get_attribute('href')
            accessibility._accessible_capture(page, f'{label}-{width}x{height}-js{javascript}', methods=methods.copy())
        page.goto('/admin/rezepte')
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('main .btn-primary')).to_have_attribute('data-semantic', 'actions.add')
        card = page.locator('article.recipe-card').filter(
            has=page.locator('.admin-list-name strong', has_text=re.compile(r'^Suppe$')))
        edit = card.get_by_role('link', name='Suppe bearbeiten', exact=True)
        card.locator('.admin-compact-actions > summary').click()
        view = card.get_by_role('link', name='Suppe ansehen', exact=True)
        pdf = card.get_by_role('link', name='Drucken · Stand 1 · Suppe', exact=True)
        assert len({view.get_attribute('href'), edit.get_attribute('href'), pdf.get_attribute('href')}) == 3
        response = client.get(pdf.get_attribute('href'))
        assert response.status_code == 200 and response.data.startswith(b'%PDF-')
        assert response.headers['X-Recipe-Revision'] == revision.public_id
        view.focus()
        expect(view).to_be_focused()
        ring = view.evaluate(
            "el => getComputedStyle(el).outlineStyle + ' ' + getComputedStyle(el).boxShadow")
        assert ring != 'none none'
        with page.expect_navigation() as navigation:
            page.keyboard.press('Enter')
        assert navigation.value.status == 200
        expect(page.get_by_text('Entwurf · nicht festgeschrieben', exact=True)).to_be_visible()
        assert page.locator('main [name="_form_context"]').count() == 0
        assert page.locator('#recipe-document input, #recipe-document select, #recipe-document textarea').count() == 0
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('main .btn-primary')).to_have_attribute('data-semantic', 'actions.edit')
        page.locator('.page-header .admin-compact-actions > summary').click()
        quantity = page.get_by_role('link', name='Mengen berechnen', exact=True)
        expect(quantity).to_contain_text('Berechnen')
        quantity.click()
        page.get_by_label('Zielmenge · PORTION', exact=True).fill('8')
        scale = page.get_by_role('button', name='Mengen berechnen', exact=True)
        expect(scale).to_contain_text('Berechnen')
        scale.click()
        assert 'yield=8' in page.url
        expect(page.locator('main table tbody tr').first.locator('[data-label="Berechnet"]')).to_have_text('2')
        page.get_by_role('link', name='Rezept ansehen', exact=True).click()
        expect(page.locator('#recipe-document .recipe-amount').first).to_have_text('2 G')
        assert page.locator('#recipe-document table, #recipe-document input').count() == 0
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
            expect(page.locator('main .btn-primary')).to_have_count(1)
            if label == 'recipes':
                expect(page.locator('form[role="search"] .btn-primary')).to_have_attribute(
                    'data-semantic', 'view.filter')
            elif label == 'view':
                back = page.locator('main .btn-primary')
                expect(back).to_have_attribute('data-semantic', 'actions.back')
                expect(back).to_contain_text('Zurück')
                expect(back).to_have_attribute('aria-label', 'Zurück zur Rezeptliste')
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
        expect(page).to_have_title(re.compile(r'^Rezept-History'))
        expect(page.get_by_role('heading', name='Alle gespeicherten Stände', exact=True)).to_be_visible()
        expect(page.locator('#recipe-history')).to_be_visible()
        expect(page.locator('#recipe-history .admin-row-actions')).to_have_count(3)
        expect(page.locator('#recipe-history .ui-sem-actions')).to_have_count(3)
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
            summary = page.locator('#recipe-document')
            expect(summary.get_by_text('Erster Absatz' if number == 1 else f'Anleitung für gespeicherten Stand {number}', exact=False)).to_be_visible()
            expect(page.get_by_text('Aktueller Entwurf nach Stand 3', exact=True)).to_have_count(0)
            accessibility._accessible_capture(page, f'history-stand-{number}-{width}', methods=['GET'])
            page.get_by_role('link', name='Zur Rezept-History', exact=True).click()
        page.get_by_role('link', name='Aktuellen Entwurf ansehen', exact=True).click()
        expect(page.get_by_text('Aktueller Entwurf nach Stand 3', exact=True)).to_be_visible()
    assert state(owner) == before


@pytest.fixture
def readable_recipe(recipe_editor):  # noqa: F811
    from test_recipe_store_db import payload, complete_line
    app, _, _, actor = recipe_editor
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        ingredients = [complete_line(engine, actor, name, quantity=amount, unit_code='G')
                       for name, amount in [('Karotte', '800'), ('Wasser', '200'), ('Salz', '8'), ('Kräuter', '4')]]
        ingredients[0].update(group_label='Gemüse', note='Gleichmässig schneiden')
        values = payload(title='Gemüsesuppe · Leseprüfung', servings='4', ingredients=ingredients,
                         description='Synthetisches Rezeptblatt mit vier Zutaten und zwei Schritten.',
                         prep_minutes=0, cook_minutes=20,
                         steps=[{'instruction': 'Gemüse waschen und schneiden.\nMit Wasser aufkochen.',
                                 'duration_minutes': 0, 'image_sha256': None},
                                {'instruction': 'Salz und Kräuter zugeben. Vollständig abschmecken.',
                                 'duration_minutes': None, 'image_sha256': None}])
        values['source'].update(kind='ai_assisted', reference='Synthetische Testquelle', fetched_at='2026-09-13T08:00:00Z',
                               note='Ungeprüft. Ausbeute nicht gemessen; vor Verwendung prüfen.')
        row = store.create_recipe(engine, actor, values, expected_location_id=location)
        preview = store.get_dependency_preview(engine, target(row), expected_location_id=location)
        revision = store.freeze_revision(engine, actor, target(row), expected_location_id=location,
                                         expected_dependency_hash=preview.dependency_hash_sha256)
    return row.public_id, revision.public_id


@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844), (320, 844), (2560, 1440)])
@pytest.mark.parametrize('javascript', [False, True])
def test_readable_recipe_content_and_explicit_mode(readable_recipe, recipe_editor, recipe_server, browser,  # noqa: F811
                                                  monkeypatch, width, height, javascript):
    recipe, revision = readable_recipe
    root = f'/admin/rezepte/{recipe}'
    before = state(recipe_editor[1])
    monkeypatch.setattr(accessibility, 'EVIDENCE', EVIDENCE)
    with _context(browser, recipe_server, recipe_editor[2], width, javascript=javascript) as context:
        page = context.new_page()
        page.set_viewport_size({'width': width, 'height': height})
        for label, path in [('draft', root + '/ansicht'), ('saved', root + '/revisionen/' + revision)]:
            assert page.goto(path).status == 200
            document = page.locator('#recipe-document')
            expect(document.locator('input, select, textarea, form, table')).to_have_count(0)
            expect(document.locator('.recipe-ingredient')).to_have_count(4)
            expect(document.locator('.recipe-steps > li')).to_have_count(2)
            expect(document.get_by_text('Vorbereitung: 0 Minuten', exact=True)).to_be_visible()
            expect(document.get_by_text('Kochzeit: 20 Minuten', exact=True)).to_be_visible()
            expect(document.locator('.recipe-source-note')).to_have_text('Ungeprüft. Ausbeute nicht gemessen; vor Verwendung prüfen.')
            expect(document.locator('[data-warning="ai_source"]')).to_be_visible()
            warning_boxes = [item.bounding_box() for item in document.locator('.recipe-warnings p').all()]
            assert len(warning_boxes) == 3 and all(warning_boxes)
            assert all(later['y'] >= earlier['y'] + earlier['height']
                       for earlier, later in zip(warning_boxes, warning_boxes[1:]))
            expect(document.locator('.recipe-steps')).to_contain_text('Vollständig abschmecken.')
            ingredients, steps = document.locator('.recipe-columns > section').all()
            left, right = ingredients.bounding_box(), steps.bounding_box()
            assert left and right
            if width >= 768:
                assert abs(left['y'] - right['y']) <= 1 and right['width'] >= 1.9 * left['width']
            else:
                assert right['y'] >= left['y'] + left['height']
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            for glyph in document.locator('use').all():
                assert glyph.evaluate('el => el.getBBox().width > 0 && el.getBBox().height > 0')
            originals = document.locator('.recipe-originals > summary')
            expect(originals).to_contain_text('Originalmengen')
            expect(originals).to_have_attribute('title', 'Originalmengen ansehen')
            expect(originals).to_have_attribute('aria-label', 'Originalmengen ansehen')
            provenance = document.locator('.recipe-provenance > summary')
            expect(provenance).to_contain_text('Herkunft')
            expect(provenance).to_have_attribute('aria-label', 'Herkunft ansehen')
            assert 'Verlauf' not in (provenance.inner_text() or '')
            originals.focus()
            expect(originals).to_be_focused()
            page.keyboard.press('Enter')
            expect(document.get_by_text('Originalausbeute: 4 PORTION', exact=True)).to_be_visible()
            page.keyboard.press('Enter')
            accessibility._accessible_capture(page, f'complete-{label}-{width}-js{javascript}', methods=['GET'])
            more = page.locator('.page-header .admin-compact-actions > summary')
            if more.count():
                more.click()
            page.get_by_role('link', name='Mengen berechnen', exact=True).click()
            page.get_by_label('Zielmenge · PORTION', exact=True).fill('6')
            page.get_by_role('button', name='Mengen berechnen', exact=True).click()
            if label == 'saved':
                assert 'mode=scale' in page.url and revision in page.url
                assert 'yield=6' in page.get_by_role('link', name='PDF öffnen').get_attribute('href')
            page.get_by_role('link', name='Rezept ansehen', exact=True).click()
            expect(page.locator('.recipe-amount').first).to_have_text('1200 G')
            expect(page.locator('#recipe-document input, #recipe-document table')).to_have_count(0)
    assert state(recipe_editor[1]) == before
