"""Recipe density evidence and native form interaction on synthetic PostgreSQL data."""
import json
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from cafeteria import roles
from cafeteria.admin import recipe_routes

from test_master_data_browser import master_server  # noqa: F401
from test_recipe_routes import app_engine, b3, fields, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_recipe_forms import form_values
from test_recipe_store_db import line, payload, snapshot
from test_rendered_ui import browser  # noqa: F401


EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/ui-density-0913/recipes'
VIEWPORTS = ((1440, 900), (390, 844), (1024, 768), (768, 1024), (1920, 1080), (2560, 1440), (320, 900))


def reference(client, count=4):
    original = fields(client, '/admin/rezepte/neu')
    data = form_values(payload(
        title='Gemüsesuppe', description='Gemüse vorbereiten und schonend garen.',
        ingredients=[line(name, quantity=str(index + 1)) for index, name in enumerate(
            (['Karotten', 'Kartoffeln', 'Zwiebeln', 'Gemüsebouillon'] * 5)[:count])],
        steps=[{'instruction': 'Gemüse waschen, schälen und klein schneiden.' if index == 0
                else f'Schritt {index + 1}: Gemüse garen und sorgfältig abschmecken.',
                'duration_minutes': None if index == 0 else 0, 'image_sha256': None}
               for index in range(2 if count == 4 else 10)],
    ))
    data['_csrf'], data['_form_context'] = original['_csrf'], original['_form_context']
    response = client.post('/admin/rezepte/neu', data=data)
    assert response.status_code == 303, response.text
    return response.location


@pytest.mark.parametrize('count', [4, 20])
def test_recipe_density_evidence(b3, master_server, browser, count):  # noqa: F811
    _, owner, client, _ = b3
    path = reference(client, count)
    base, cookie = master_server
    before = snapshot(owner)
    phase = os.environ.get('RECIPE_DENSITY_PHASE', 'after')
    destination = EVIDENCE / phase
    destination.mkdir(parents=True, exist_ok=True)
    metrics = []
    with browser.new_context(reduced_motion='reduce', locale='de-CH', timezone_id='Europe/Zurich') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            assert page.goto(base + path).status == 200
            page.evaluate('document.fonts.ready')
            metrics.append(page.evaluate('''() => ({
                width: innerWidth, height: innerHeight, totalHeight: document.documentElement.scrollHeight,
                overflow: document.documentElement.scrollWidth > innerWidth + 1,
                ingredientsTop: document.getElementById('ingredients-heading').getBoundingClientRect().top,
                preparationTop: document.getElementById('steps-heading').getBoundingClientRect().top,
                font: getComputedStyle(document.querySelector('input[name="title"]')).fontFamily,
                browser: navigator.userAgent
            })'''))
            page.screenshot(path=str(destination / f'{count}-ingredients-{width}x{height}.png'), full_page=True)
        (destination / f'{count}-ingredients.json').write_text(json.dumps(metrics, indent=2))
    assert snapshot(owner) == before


@pytest.mark.parametrize('state', ['readonly', 'archived'])
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('width', [390, 1440])
def test_readonly_preparation_reopens_after_escape(
    b3, master_server, browser, monkeypatch, state, javascript, width,  # noqa: F811
):
    _, owner, client, _ = b3
    original = fields(client, '/admin/rezepte/neu')
    instruction = ('Vollständige Anleitung mit allen Arbeitsschritten.\n' * 20).rstrip('\n')
    data = form_values(payload(steps=[{
        'instruction': instruction, 'duration_minutes': 7, 'image_sha256': None,
    }]))
    data['_csrf'], data['_form_context'] = original['_csrf'], original['_form_context']
    response = client.post('/admin/rezepte/neu', data=data)
    assert response.status_code == 303
    path = response.location
    if state == 'archived':
        assert client.post(path + '/status', data=fields(client, path + '/status')).status_code == 303
    else:
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    before = snapshot(owner)
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, posts = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        page.goto(base + path, wait_until='networkidle')
        detail = page.locator('#step-details-0')
        summary = detail.locator(':scope > summary')
        field = page.locator('[name="steps.0.instruction"]')
        expect(summary).to_have_accessible_name('Details für Schritt 1')
        expect(page.locator('[data-recipe-toggle="step-details-0"]')).to_be_hidden()
        expect(page.get_by_role('button', name='Speichern', exact=True)).to_have_count(0)
        for focus in (page.locator('a[href="#ingredients-heading"]'), summary):
            expect(detail).to_have_attribute('open', '')
            focus.focus()
            expect(focus).to_be_focused()
            if javascript and focus.get_attribute('data-ui-tooltip'):
                tooltip = page.get_by_role('tooltip', name=focus.get_attribute('data-ui-tooltip'), exact=True)
                expect(tooltip).to_be_visible()
                page.keyboard.press('Escape')
                expect(tooltip).to_be_hidden()
                expect(detail).to_have_attribute('open', '')
            page.keyboard.press('Escape')
            if javascript:
                expect(detail).not_to_have_attribute('open', '')
            else:
                expect(detail).to_have_attribute('open', '')
            expect(summary).to_be_visible()
            summary.focus()
            expect(summary).to_be_focused()
            if not javascript:
                page.keyboard.press('Enter')
                expect(detail).not_to_have_attribute('open', '')
            page.keyboard.press('Space')
            expect(detail).to_have_attribute('open', '')
            expect(field).to_be_visible()
            expect(field).to_be_disabled()
            expect(field).to_have_value(instruction)
            expect(page.locator('[name="steps.0.duration_minutes"]')).to_have_value('7')
            expect(page.locator('[name="steps.0.image_sha256"]')).to_be_visible()
        destination = EVIDENCE / 'after'
        destination.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(destination / f'preparation-{state}-{width}-js{javascript}.png'), full_page=True)
        assert not posts and not errors
    assert snapshot(owner) == before


@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('width', [390, 1440])
def test_compact_rows_keep_native_post_values_and_focus(b3, master_server, browser, javascript, width):  # noqa: F811
    _, owner, client, _ = b3
    path = reference(client)
    original = fields(client, path)
    base, cookie = master_server
    before = snapshot(owner)
    with browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, posts = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        page.goto(base + path, wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        browser_context = page.locator('[name="_form_context"]').input_value()
        form = page.locator('#recipe-editor')
        expect(form).to_have_attribute('method', 'post')
        expect(page.locator('form#recipe-editor')).to_have_count(1)
        assert form.evaluate('f => [...new FormData(f).keys()].filter(k => k !== "tag_public_ids").length') == len(set(original) - {'tag_public_ids'})
        expect(page.locator('[name="ingredients.0.quantity"]')).to_have_count(1)
        page.locator('[name="ingredients.0.quantity"]').fill('2.5')
        page.locator('[name="ingredients.0.unit_code"]').select_option('KG')
        details = page.locator('#ingredient-details-0')
        toggle = page.locator('[data-recipe-toggle="ingredient-details-0"]') if javascript else details.locator('summary').first
        toggle.click()
        page.get_by_label('Gruppe', exact=True).first.fill('Suppe')
        page.get_by_label('Zutatennotiz', exact=True).first.fill('Fein würfeln')
        toggle.click()
        expect(page.locator('[name="ingredients.0.quantity"]')).to_have_value('2.5')
        assert not posts and snapshot(owner) == before
        if javascript:
            expect(page.locator('[data-recipe-ingredient-summary]').first).to_have_text('Gruppe: Suppe · Notiz: Fein würfeln')
        expect(page.get_by_label('Mehr: Weitere Aktionen Zutat 1', exact=True)).to_have_count(0)
        for operation, name in [('up', 'Zutat 1 nach oben verschieben'), ('down', 'Zutat 1 nach unten verschieben')]:
            control = page.locator(f'button[formaction*="row_action={operation}"]').first
            expect(control.locator('use')).to_have_attribute('href', f'/static/vendor/tabler-icons/tabler-icons.svg#tabler-arrow-{operation}')
            expect(control).to_have_class(re.compile(r'ui-sem-control--icon-only'))
            expect(control.locator('span')).to_have_count(0)
            expect(control).to_have_accessible_name(name)
        first_up = page.locator('[data-recipe-ingredient]').first.locator('button[formaction*="row_action=up"]')
        last_down = page.locator('[data-recipe-ingredient]').last.locator('button[formaction*="row_action=down"]')
        expect(first_up).to_have_count(1)
        expect(first_up).to_be_disabled()
        expect(page.locator('[data-recipe-ingredient]').first).to_contain_text('Bereits an erster Position.')
        expect(last_down).to_have_count(1)
        expect(last_down).to_be_disabled()
        expect(page.locator('[data-recipe-ingredient]').last).to_contain_text('Bereits an letzter Position.')
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Zutat 1 nach unten verschieben', exact=True).click()
        expect(page.locator('[name="ingredients.1.ingredient_text"]')).to_be_focused()
        expect(page.locator('[name="ingredients.1.quantity"]')).to_have_value('2.5')
        assert page.locator('[name="ingredients.1.line_public_id"]').input_value() == original['ingredients.0.line_public_id']
        assert page.locator('[name="_form_context"]').input_value() == browser_context
        assert page.locator('[name="row_version"]').input_value() == original['row_version']
        assert snapshot(owner) == before
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Zutat 2 davor einfügen', exact=True).click()
        expect(page.locator('[name="ingredients.1.ingredient_text"]')).to_be_focused()
        expect(page.locator('#ingredient-details-1')).to_have_attribute('open', '')
        page.locator('[name="ingredients.1.ingredient_text"]').fill('Neue Zutat')
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Zutat 2 entfernen', exact=True).click()
        expect(page.locator('[name="ingredients.1.ingredient_text"]')).to_be_focused()
        assert snapshot(owner) == before
        # A required, unchanged step may be collapsed; its exact text is still submitted.
        page.get_by_role('button', name='Speichern', exact=True).focus()
        with page.expect_navigation(wait_until='load'):
            page.keyboard.press('Enter')
        expect(page.get_by_role('heading', name='Rezepte', exact=True)).to_be_visible()
        expect(page.locator('.page-header-subtitle')).to_have_text('Gemüsesuppe')
        saved = fields(client, path)
        assert saved['ingredients.1.quantity'] == '2.5' and saved['ingredients.1.unit_code'] == 'KG'
        assert saved['ingredients.1.group_label'] == 'Suppe' and saved['ingredients.1.note'] == 'Fein würfeln'
        assert saved['steps.0.instruction'] == original['steps.0.instruction']
        assert saved['steps.0.duration_minutes'] == '' and saved['steps.1.duration_minutes'] == '0'
        assert len(posts) == 4 and not errors
        for request in posts[:-1]:
            assert '/admin/rezepte/formular?' in request.url
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


@pytest.mark.parametrize('javascript', [False, True])
def test_required_step_in_closed_details_opens_and_focuses(b3, master_server, browser, javascript):  # noqa: F811
    _, owner, client, _ = b3
    path = reference(client)
    base, cookie = master_server
    before = snapshot(owner)
    with browser.new_context(viewport={'width': 1440, 'height': 900}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors, posts = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        page.goto(base + path, wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        detail = page.locator('#step-details-0')
        toggle = page.locator('[data-recipe-toggle="step-details-0"]') if javascript else detail.locator('summary').first
        if javascript:
            toggle.click()
        field = page.locator('[name="steps.0.instruction"]')
        field.fill('')
        if javascript:
            toggle.click()
            expect(detail).not_to_have_attribute('open', '')
        else:
            expect(toggle).to_be_hidden()
        page.get_by_role('button', name='Speichern', exact=True).focus()
        page.keyboard.press('Enter')
        expect(detail).to_have_attribute('open', '')
        expect(field).to_be_focused()
        assert field.get_attribute('required') is not None
        assert not posts and not errors and snapshot(owner) == before
        destination = EVIDENCE / 'after'
        destination.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(destination / f'required-error-js{javascript}.png'), full_page=True)
        if javascript:
            expect(field).to_have_attribute('aria-invalid', 'true')
            toggle.click()
            expect(toggle).to_contain_text('Fehler')
            toggle.click()
            long_instruction = ('Vollständiger Text.\n' * 100).rstrip('\n')
            field.fill(long_instruction)
            page.keyboard.press('Escape')
            expect(toggle).to_be_focused()
            expect(detail).not_to_have_attribute('open', '')
            expect(page.locator('[data-recipe-step-summary]').first).to_contain_text('…')
            page.get_by_role('button', name='Speichern', exact=True).click()
            assert fields(client, path)['steps.0.instruction'] == long_instruction


def test_sticky_toolbar_clears_focus_and_virtual_keyboard(b3, master_server, browser):  # noqa: F811
    path = reference(b3[2])
    base, cookie = master_server
    with browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path)
        footer = page.locator('[data-sticky-form="recipe-editor"]')
        expect(footer).to_have_css('position', 'sticky')
        expect(footer.locator('[data-semantic="actions.save"]')).to_be_in_viewport()
        field = page.locator('[name="ingredients.2.quantity"]')
        field.evaluate('''e => {
            const bar = document.querySelector('[data-sticky-form="recipe-editor"]').getBoundingClientRect();
            window.scrollBy(0, e.getBoundingClientRect().bottom - bar.top + 8);
            e.focus({preventScroll: true});
        }''')
        page.wait_for_function('''() => {
            const active = document.activeElement;
            const field = active.getBoundingClientRect();
            const bar = document.querySelector('[data-sticky-form="recipe-editor"]').getBoundingClientRect();
            const hit = document.elementFromPoint(field.left + field.width / 2, field.top + field.height / 2);
            return active.name === 'ingredients.2.quantity'
                && field.bottom <= bar.top
                && field.top >= 0
                && !!hit && (hit === active || active.contains(hit));
        }''')
        expect(field).to_be_focused()
        page.evaluate('''() => {
            Object.defineProperty(visualViewport, 'height', {configurable: true, value: 430});
            visualViewport.dispatchEvent(new Event('resize'));
        }''')
        expect(footer).to_have_css('position', 'static')
        page.evaluate('''() => {
            delete visualViewport.height;
            visualViewport.dispatchEvent(new Event('resize'));
        }''')
        expect(footer).to_have_css('position', 'sticky')
        page.set_viewport_size({'width': 390, 'height': 600})
        expect(footer).to_have_css('position', 'static')


@pytest.mark.parametrize('touch', [False, True])
def test_reference_density_and_mobile_targets(b3, master_server, browser, touch):  # noqa: F811
    path = reference(b3[2])
    base, cookie = master_server
    with browser.new_context(viewport={'width': 1440, 'height': 900}, has_touch=touch,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path)
        assert page.evaluate('matchMedia("(pointer: coarse)").matches') == touch
        rows = page.locator('[data-recipe-ingredient]')
        expect(page.locator('.admin-compact-column-labels')).to_be_visible()
        expect(page.locator('.admin-compact-column-labels')).to_contain_text('Menge')
        expect(page.locator('.admin-compact-column-labels')).to_contain_text('Einheit')
        boxes = [row.bounding_box() for row in rows.all()]
        assert len(boxes) == 4 and all(box and box['height'] <= 72 and box['y'] + box['height'] < 900 for box in boxes)
        preparation = page.locator('[data-recipe-step]').first.bounding_box()
        assert preparation and preparation['y'] < 900
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            for element in page.locator('main :is(.btn, .form-control, .form-select, summary)').all():
                if element.is_visible():
                    box = element.bounding_box()
                    if 'ui-sem-control--icon-only' in (element.get_attribute('class') or '').split():
                        size = 44 if touch else 36
                        assert box and box['height'] == size and box['width'] == size
                        expect(element).to_have_accessible_name(re.compile(r'\S'))
                    else:
                        assert box and box['height'] >= (44 if touch else 36)
            if width < 992:
                for label in rows.first.locator('.admin-compact-line label').all():
                    box = label.bounding_box()
                    assert box and box['height'] >= 14
        page.set_viewport_size({'width': 1440, 'height': 900})
        for _ in range(5):
            page.keyboard.press('Control+Equal')
        zoom = page.evaluate('''() => ({innerWidth, devicePixelRatio,
            actual200Percent: innerWidth === 720 && devicePixelRatio === 2})''')
        destination = EVIDENCE / 'after'
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f'browser-zoom-probe-touch{touch}.json').write_text(json.dumps(zoom, indent=2))


@pytest.mark.parametrize('javascript', [False, True])
def test_warning_unavailable_selection_and_readonly_remain_accessible(
    b3, master_server, browser, monkeypatch, javascript,  # noqa: F811
):
    _, owner, client, _ = b3
    original = fields(client, '/admin/rezepte/neu')
    data = form_values(payload(source={
        'kind': 'ai_assisted', 'reference': 'Synthetischer Testimport', 'url': None,
        'note': 'Angaben vor Verwendung prüfen', 'fetched_at': '2026-09-13T08:00:00+00:00',
    }))
    data['_csrf'], data['_form_context'] = original['_csrf'], original['_form_context']
    response = client.post('/admin/rezepte/neu', data=data)
    assert response.status_code == 303
    path = response.location
    choices = recipe_routes._choices
    monkeypatch.setattr(recipe_routes, '_choices', lambda values: choices(values) | {'units': []})
    base, cookie = master_server
    before = snapshot(owner)
    with browser.new_context(viewport={'width': 390, 'height': 844}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path)
        expect(page.locator('.alert-warning')).to_contain_text('vor der Verwendung prüfen')
        expect(page.locator('.alert-warning')).to_be_visible()
        expect(page.locator('[name="ingredients.0.unit_code"]')).to_have_value('G')
        expect(page.locator('[name="ingredients.0.unit_code"] option:checked')).to_have_text('Ursprüngliche Auswahl · nicht mehr verfügbar')
        assert page.locator('[name="source.note"]').get_attribute('readonly') is not None
        assert page.locator('#recipe-editor').evaluate('f => new FormData(f).get("ingredients.0.unit_code")') == 'G'
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
        page.reload()
        expect(page.locator('[name="ingredients.0.quantity"]')).to_be_disabled()
        expect(page.locator('[name="steps.0.instruction"]')).to_be_visible()
        expect(page.locator('[name="steps.0.instruction"]')).to_be_disabled()
        page.locator('#ingredient-details-0 > summary').click()
        expect(page.locator('[name="ingredients.0.food_public_id"]')).to_be_visible()
        expect(page.get_by_role('button', name='Speichern', exact=True)).to_have_count(0)
        expect(page.locator('.alert-warning')).to_be_visible()
    assert snapshot(owner) == before
