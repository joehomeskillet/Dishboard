"""Own sync_playwright lifecycle; real HTTP/assets, no product test endpoint."""
from __future__ import annotations

import re
from threading import Thread

import pytest
from flask import Blueprint, Flask, render_template, render_template_string, request as flask_request
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui
from cafeteria.ui.semantics import ROOT, STATIC

PAGE = '''<!doctype html><html lang="{{ ui_locale }}"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
{% for file in ['tokens.css', 'vendor/tabler/tabler.min.css', 'admin-tabler.css', 'ui-semantic.css'] %}
<link rel="stylesheet" href="{{ url_for('static', filename=file) }}">{% endfor %}
</head><body class="admin-body dishboard-admin"><main class="container-fluid py-4">
{% from 'ui/_semantic.html' import icon_button, symbol_row, status_badge_sem, action_menu, empty_state_sem, status_bar, filter_bar_sem, confirm_dialog %}
{{ status_bar('navigation.menus', [{'key':'status.active', 'value':0}]) }}
{{ icon_button('actions.edit', href='#edit', icon_only=true, id='edit') }}
{{ icon_button('actions.save', type='button') }}
{{ symbol_row(['diet.vegan'], [{'key':'allergen.milk', 'presence':'contains', 'checked':true}], ['diet.regional'], ['review.approved']) }}
<section id="unknown">{{ symbol_row() }}</section>
<section id="unchecked">{{ symbol_row(allergens=[{'key':'allergen.gluten', 'presence':'contains'}]) }}</section>
<section id="may-contain">{{ symbol_row(allergens=[{'key':'allergen.eggs', 'presence':'may_contain', 'checked':true}]) }}</section>
{{ status_badge_sem('status.error') }}
{{ action_menu([{'key':'actions.preview', 'href':'#preview'}, {'key':'actions.copy', 'href':'#copy'}]) }}
{{ empty_state_sem('status.missing', 'ui.request_failed', 'actions.retry', '#retry') }}
{{ confirm_dialog('actions.delete', 'ui.request_failed', 'actions.delete') }}
<section id="filter-wrapper">{{ filter_bar_sem('/__semantic__', active=true, reset_url='/__semantic__') }}</section>
</main></body></html>'''

CONTEXT_PAGE = '''<!doctype html><html lang="de"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
{% for file in ['tokens.css', 'vendor/tabler/tabler.min.css', 'admin-tabler.css', 'ui-semantic.css'] %}
<link rel="stylesheet" href="{{ url_for('static', filename=file) }}">{% endfor %}
</head><body class="admin-body dishboard-admin"><main class="container-fluid py-4">
{% from 'ui/_semantic.html' import row_actions, filter_bar_sem %}
{{ row_actions([
  {'key':'actions.edit', 'href':'#template', 'icon_only':true, 'aria_label':'Vorlage X bearbeiten'},
  {'key':'actions.apply', 'text':'Übernehmen', 'title':'Wochenvorgaben übernehmen',
   'aria_label':'Übernehmen: Wochenvorgaben', 'class':'dropdown-item',
   'name':'intent', 'value':'apply', 'form':'week', 'attrs':{'formnovalidate':true}},
  {'key':'actions.history', 'text':'Zugriffsverlauf', 'href':'#history', 'class':'dropdown-item',
   'attrs':{'target':'_blank', 'rel':'noreferrer'}}]) }}
<p id="search-help">Zusatzfilter bleiben sichtbar.</p>
{{ filter_bar_sem('/__context__', search_name='text', search_value='Suppe',
    maxlength=200, describedby='search-help', loading=true, open=true,
    more_filters='<label for="category">Kategorie</label><input id="category" name="category" value="active">'|safe) }}
</main></body></html>'''

DIRECT_PAGE = '''<!doctype html><html lang="{{ ui_locale }}"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
{% for file in ['tokens.css', 'vendor/tabler/tabler.min.css', 'admin-tabler.css', 'ui-semantic.css'] %}
<link rel="stylesheet" href="{{ url_for('static', filename=file) }}">{% endfor %}
<script defer src="{{ url_for('static', filename='vendor/tabler/tabler.min.js') }}"></script>
<script defer src="{{ url_for('static', filename='admin.js') }}"></script>
</head><body class="admin-body dishboard-admin"><main class="container-fluid">
{% from 'ui/_semantic.html' import row_actions, icon_button %}
{% from 'admin/_macros.html' import list_row, form_footer %}
<div id="card"><div class="admin-list-row"><div class="admin-list-name">{{ object }}</div>
{{ row_actions(items, object=object) }}</div></div>
<p id="existing-help">Existing help</p>
<form id="mutation" method="post"><input name="title" value="Untouched">
{{ row_actions([
  {'key':'actions.delete', 'id':'disabled-button', 'name':'intent', 'value':'delete',
   'consequence_key':'ui.request_failed', 'disabled_reason':reason,
   'attrs':{'data-confirm':'Delete?', 'aria-describedby':'existing-help'}},
  {'key':'actions.open', 'id':'disabled-link', 'href':'/__mutation__', 'disabled_reason':reason}
], object=object) }}</form>
{{ list_row(name=object, more_actions=icon_button('actions.open', href='#slot')) }}
{{ form_footer({'label':'Save', 'type':'button'}, '#cancel', rare=icon_button('actions.open', href='#rare')) }}
</main></body></html>'''


@pytest.fixture(params=['de', 'en', 'xx'])
def semantic_site(request):
    app = Flask('semantic-browser', template_folder=str(ROOT.parent / 'templates'),
                static_folder=str(STATIC))
    app.config.update(TESTING=True, UI_LOCALE=request.param)
    register_template_filters(app)
    register_ui(app)
    bp = Blueprint('admin', __name__)

    @bp.route('/templates')
    def vorlagen():
        return 'test target'

    app.register_blueprint(bp)

    @app.route('/__semantic__')
    def macro_page():
        return render_template_string(PAGE)

    @app.route('/__proof__')
    def proof_page():
        return render_template('admin/print_template_unavailable.html')

    @app.route('/__context__')
    def context_page():
        return render_template_string(CONTEXT_PAGE)

    @app.route('/__direct__', methods=['GET', 'POST'])
    def direct_page():
        assert flask_request.method == 'GET', 'Disabled action submitted the form'
        keys = ['actions.open', 'actions.edit', 'actions.print', 'actions.history',
                'actions.copy', 'actions.check', 'actions.export', 'actions.archive']
        items = [{'key': key, 'href': f'#action-{i}', 'id': f'action-{i}',
                  'consequence_key': 'ui.request_failed' if key == 'actions.archive' else None}
                 for i, key in enumerate(keys[:int(flask_request.args.get('count', '8'))])]
        return render_template_string(DIRECT_PAGE, items=items, object='Broccoli <&>',
                                      reason='Noch kein gespeicherter Stand vorhanden.')

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
            try:
                yield app, browser, f'http://127.0.0.1:{server.server_port}'
            finally:
                browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('width', [360, 768, 1024, 1440])
def test_semantic_macros_keyboard_names_reflow(semantic_site, width, tmp_path):
    app, browser, origin = semantic_site
    context = browser.new_context(java_script_enabled=False, viewport={'width': width, 'height': 1000})
    page = context.new_page()
    try:
        response = page.goto(origin + '/__semantic__')
        assert response.status == 200
        locale = app.config['UI_LOCALE']
        messages = app.extensions['ui_translator'].locales[locale]
        expect(page.locator('html')).to_have_attribute('lang', locale)
        edit = page.get_by_role('link', name=messages['actions.edit.aria'], exact=True)
        expect(edit).to_have_attribute('data-ui-tooltip', messages['actions.edit.tooltip'])
        page.keyboard.press('Tab')
        expect(edit).to_be_focused()
        assert edit.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        first = page.locator('.ui-sem-symbol-row').first
        assert first.locator(':scope > div').evaluate_all("els => els.map(el => el.dataset.symbolGroup)") == ['diet', 'allergens', 'properties', 'status']
        expect(first).to_contain_text(messages['diet.vegan.label'])
        expect(first).to_contain_text(messages['allergen.contains.label'].format(name=messages['allergen.milk.label']))
        expect(page.locator('#unknown')).to_contain_text(messages['allergen.unknown.label'])
        expect(page.locator('#unchecked')).to_contain_text(messages['allergen.unchecked.label'].format(name=messages['allergen.gluten.label']))
        expect(page.locator('#may-contain')).to_contain_text(messages['allergen.may_contain.label'].format(name=messages['allergen.eggs.label']))
        for image in page.locator('img').all():
            assert image.evaluate('el => el.complete && el.naturalWidth > 0')
            expect(image).to_have_attribute('aria-hidden', 'true')
        for glyph in page.locator('svg use').all():
            if glyph.is_visible():
                assert glyph.evaluate('el => el.getBBox().width > 0')
        expect(page.locator('.badge[data-semantic="status.error"]')).to_contain_text(messages['status.error.label'])
        # Native Tab order reaches each action directly, without opening a menu.
        page.keyboard.press('Tab')
        page.keyboard.press('Tab')
        expect(page.get_by_role('link', name=messages['actions.preview.label'], exact=True)).to_be_focused()
        assert page.locator('.admin-row-actions a').first.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.keyboard.press('Tab')
        expect(page.get_by_role('link', name=messages['actions.copy.label'], exact=True)).to_be_focused()
        expect(page.locator('.admin-row-actions details, .admin-row-actions summary')).to_have_count(0)
        for control in page.locator('.ui-sem-control:visible').all():
            size = control.bounding_box()
            assert size['width'] >= 36 and size['height'] >= 36, size
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('.ui-sem-label, .ui-sem-control').evaluate_all('''els => els.filter(e => e.getClientRects().length).every(e => e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1)''')
        expect(page.locator('.admin-statusbar-value')).to_have_text('0')
        expect(page.locator('.admin-filter-bar')).to_have_attribute('method', 'get')
        page.screenshot(path=str(tmp_path / f'semantic-{locale}-{width}.png'), full_page=True)
    finally:
        context.close()


@pytest.mark.parametrize('width', [360, 390, 768, 1024, 1440, 1920])
def test_p2c_context_actions_dropdown_and_active_filters(semantic_site, width, tmp_path):
    app, browser, origin = semantic_site
    context = browser.new_context(java_script_enabled=False, viewport={'width': width, 'height': 1000})
    page = context.new_page()
    try:
        assert page.goto(origin + '/__context__').status == 200
        edit = page.get_by_role('link', name='Vorlage X bearbeiten', exact=True)
        expect(edit).to_have_accessible_name('Vorlage X bearbeiten')
        expect(edit).to_have_attribute('data-ui-tooltip', 'Vorlage X bearbeiten')
        page.keyboard.press('Tab')
        expect(edit).to_be_focused()
        assert edit.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.keyboard.press('Tab')
        apply = page.get_by_role('button', name='Übernehmen: Wochenvorgaben', exact=True)
        expect(apply).to_be_focused()
        expect(apply).to_have_attribute('data-ui-tooltip', 'Wochenvorgaben übernehmen')
        expect(apply).to_have_attribute('form', 'week')
        expect(apply).to_have_attribute('formnovalidate', '')
        for control in page.locator('.dropdown-item').all():
            size = control.bounding_box()
            assert size['height'] == 36 and size['width'] == 36
            assert control.evaluate('el => getComputedStyle(el).justifyContent') == 'center'
            assert control.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
        history = page.get_by_role('link', name='Zugriffsverlauf', exact=True)
        page.keyboard.press('Tab')
        expect(history).to_be_focused()
        expect(history).to_have_attribute('rel', 'noreferrer noopener')
        expect(history).to_have_attribute('target', '_blank')
        expect(page.locator('.admin-filter-more')).to_have_attribute('open', '')
        expect(page.get_by_label('Kategorie')).to_be_visible()
        search = page.get_by_role('searchbox')
        expect(search).to_have_value('Suppe')
        expect(search).to_have_attribute('maxlength', '200')
        expect(search).to_have_attribute('aria-describedby', 'search-help')
        expect(page.get_by_role('search')).to_have_attribute('data-loading', 'true')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(tmp_path / f'p2c-context-{app.config["UI_LOCALE"]}-{width}.png'), full_page=True)
    finally:
        context.close()


@pytest.mark.parametrize('width', [320, 390, 768, 1024, 1280, 1440])
@pytest.mark.parametrize('touch', [False, True])
def test_direct_actions_visibility_geometry_and_reflow(semantic_site, width, touch, tmp_path):
    app, browser, origin = semantic_site
    context = browser.new_context(viewport={'width': width, 'height': 1000}, has_touch=touch)
    page = context.new_page()
    try:
        for count in (0, 1, 2, 5, 8):
            assert page.goto(f'{origin}/__direct__?count={count}').status == 200
            row = page.locator('#card .admin-list-row')
            group = row.locator('.admin-row-actions')
            expect(group).to_have_count(1 if count else 0)
            expect(row.locator('details, [data-semantic="actions.more"]')).to_have_count(0)
            controls = group.locator('.ui-sem-control')
            expect(controls).to_have_count(count)
            if not count:
                continue
            expect(group).to_have_attribute('role', 'group')
            assert 'Broccoli <&>' in group.get_attribute('aria-label')
            size = 44 if touch else 36
            assert float(group.evaluate('el => getComputedStyle(el).gap').removesuffix('px')) == (6 if touch else 4)
            for i, control in enumerate(controls.all()):
                expect(control).to_be_visible()
                expect(control).to_have_attribute('href', f'#action-{i}')
                assert 'Broccoli <&>' in control.get_attribute('aria-label')
                assert not control.inner_text().strip()
                box = control.bounding_box()
                assert box['width'] == size and box['height'] == size, box
                icon = control.locator('svg').bounding_box()
                assert 18 <= icon['width'] <= 20
                height = row.bounding_box()['height']
                control.hover()
                tooltip = page.get_by_role('tooltip', name=control.get_attribute('data-ui-tooltip'), exact=True)
                expect(tooltip).to_be_visible()
                control.focus()
                assert abs(row.bounding_box()['height'] - height) <= 1
                page.keyboard.press('Escape')
                expect(page.locator('.ui-sem-tooltip.show')).to_have_count(0)
                control.click()
                assert page.url.endswith(f'#action-{i}')
                assert abs(row.bounding_box()['height'] - height) <= 1
                page.keyboard.press('Escape')
            expect(group.locator('p.ui-sem-consequence')).to_have_count(0)
            if count == 8:
                archive = controls.last
                ids = archive.get_attribute('aria-describedby').split()
                assert any(page.locator(f'[id="{ref}"]').inner_text() for ref in ids)
                assert all(page.locator(f'[id="{ref}"]').evaluate(
                    'el => el.classList.contains("visually-hidden")') for ref in ids)
                # Component width, independent of viewport width; normal flex row reflows.
                page.locator('#card').evaluate("el => el.style.width = '240px'")
                positions = controls.evaluate_all('els => els.map(el => el.getBoundingClientRect().top)')
                assert len(set(positions)) > 1
                assert min(positions) >= row.locator('.admin-list-name').bounding_box()['y'] + row.locator('.admin-list-name').bounding_box()['height']
                bounds = page.locator('#card').bounding_box()
                for control in controls.all():
                    box = control.bounding_box()
                    assert box['x'] >= bounds['x'] and box['x'] + box['width'] <= bounds['x'] + bounds['width'] + 1
                page.screenshot(path=str(tmp_path / f'direct-{app.config["UI_LOCALE"]}-{width}-{touch}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    finally:
        context.close()


@pytest.mark.parametrize('width', [768, 1440])
@pytest.mark.parametrize('touch', [False, True])
def test_direct_actions_at_double_layout_zoom(semantic_site, width, touch, tmp_path):
    app, browser, origin = semantic_site
    context = browser.new_context(viewport={'width': width, 'height': 1200}, has_touch=touch)
    page = context.new_page()
    try:
        assert page.goto(origin + '/__direct__?count=8').status == 200
        # CSS layout zoom exercises reflow as well as doubled physical target sizes.
        page.locator('html').evaluate("el => el.style.zoom = '2'")
        page.locator('#card').evaluate("el => el.style.width = '240px'")
        row = page.locator('#card .admin-list-row')
        controls = row.locator('.ui-sem-control')
        boxes = [control.bounding_box() for control in controls.all()]
        assert len({box['y'] for box in boxes}) > 1
        for control in controls.all():
            expect(control).to_be_visible()
            size = 88 if touch else 72
            box = control.bounding_box()
            assert box['width'] == size and box['height'] == size
            height = row.bounding_box()['height']
            control.focus()
            expect(control).to_be_focused()
            control.hover()
            assert abs(row.bounding_box()['height'] - height) <= 1
            page.keyboard.press('Escape')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(tmp_path / f'direct-zoom200-{app.config["UI_LOCALE"]}-{width}-{touch}.png'), full_page=True)
    finally:
        context.close()


@pytest.mark.parametrize('javascript', [False, True])
def test_disabled_actions_cannot_navigate_or_submit(semantic_site, javascript):
    _app, browser, origin = semantic_site
    context = browser.new_context(java_script_enabled=javascript)
    page = context.new_page()
    mutations = []
    page.on('request', lambda req: mutations.append(req.url) if req.method == 'POST' or '__mutation__' in req.url else None)
    try:
        assert page.goto(origin + '/__direct__').status == 200
        button = page.locator('#disabled-button')
        link = page.locator('#disabled-link')
        expect(button).to_be_disabled()
        assert link.get_attribute('href') is None
        expect(link).to_have_attribute('aria-disabled', 'true')
        expect(link).to_have_attribute('tabindex', '0')
        reason = 'Noch kein gespeicherter Stand vorhanden.'
        for control in (button, link):
            expect(control).to_have_accessible_description(re.compile(reason))
        assert 'existing-help' in button.get_attribute('aria-describedby').split()
        link.focus()
        expect(link).to_be_focused()
        for key in ('Enter', 'Space'):
            page.keyboard.press(key)
        link.click(force=True)
        button.evaluate('el => el.click()')
        page.locator('#mutation input').press('Enter')
        if javascript:
            page.locator('#mutation').evaluate('form => form.requestSubmit(document.getElementById("disabled-button"))')
            link.focus()
            expect(page.locator('.ui-sem-tooltip.show')).to_contain_text(reason)
        assert page.url == origin + '/__direct__'
        assert not mutations
        expect(page.locator('#mutation input')).to_have_value('Untouched')
        expect(page.locator('.admin-form-rare a, .admin-list-actions a[href="#slot"]')).to_have_count(2)
        for action in page.locator('.admin-form-rare a, .admin-list-actions a[href="#slot"]').all():
            expect(action).to_be_visible()
    finally:
        context.close()


@pytest.mark.parametrize('width', [360, 768, 1024, 1440])
def test_proof_page_locales_and_layout(semantic_site, width, tmp_path):
    app, browser, origin = semantic_site
    context = browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=False)
    page = context.new_page()
    try:
        assert page.goto(origin + '/__proof__').status == 200
        locale = app.config['UI_LOCALE']
        messages = app.extensions['ui_translator'].locales[locale]
        expect(page.get_by_role('heading', level=1)).to_have_text(messages['ui.print_unavailable.label'])
        expect(page.get_by_role('alert')).to_contain_text(messages['ui.request_failed.label'])
        link = page.get_by_role('link', name=messages['ui.templates_back.aria'], exact=True)
        expect(link).to_have_attribute('href', '/templates')
        page.keyboard.press('Tab')
        expect(link).to_be_focused()
        assert link.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        size = link.bounding_box()
        assert size['height'] >= 36 and size['width'] >= 36
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('h1, .alert, .ui-sem-control').evaluate_all('els => els.every(e => e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1)')
        page.screenshot(path=str(tmp_path / f'proof-{locale}-{width}.png'), full_page=True)
    finally:
        context.close()
