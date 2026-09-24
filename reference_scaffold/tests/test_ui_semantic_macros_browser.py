"""Own sync_playwright lifecycle; real HTTP/assets, no product test endpoint."""
from __future__ import annotations

from threading import Thread

import pytest
from flask import Blueprint, Flask, render_template, render_template_string
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
        expect(edit).to_have_attribute('title', messages['actions.edit.tooltip'])
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
        summary = page.locator('.ui-sem-actions summary')
        # Real Tab navigation from the preceding save button to native details.
        page.keyboard.press('Tab')
        page.keyboard.press('Tab')
        expect(summary).to_be_focused()
        assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.keyboard.press('Enter')
        expect(page.locator('.ui-sem-actions')).to_have_attribute('open', '')
        page.keyboard.press('Tab')
        expect(page.get_by_role('link', name=messages['actions.preview.label'], exact=True)).to_be_focused()
        page.keyboard.press('Shift+Tab')
        page.keyboard.press('Space')
        expect(page.locator('.ui-sem-actions')).not_to_have_attribute('open', '')
        for control in page.locator('.ui-sem-control:visible').all():
            size = control.bounding_box()
            assert size['width'] >= 48 and size['height'] >= 48, size
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
        expect(edit).to_have_attribute('title', 'Vorlage X bearbeiten')
        page.keyboard.press('Tab')
        expect(edit).to_be_focused()
        assert edit.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        page.keyboard.press('Tab')
        summary = page.locator('.ui-sem-actions summary')
        expect(summary).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('.ui-sem-actions')).to_have_attribute('open', '')
        page.keyboard.press('Tab')
        apply = page.get_by_role('button', name='Übernehmen: Wochenvorgaben', exact=True)
        expect(apply).to_be_focused()
        expect(apply).to_have_attribute('title', 'Wochenvorgaben übernehmen')
        expect(apply).to_have_attribute('form', 'week')
        expect(apply).to_have_attribute('formnovalidate', '')
        for control in page.locator('.dropdown-item').all():
            size = control.bounding_box()
            parent = control.locator('..').bounding_box()
            assert size['height'] >= 48 and abs(size['width'] - parent['width']) <= 1
            assert control.evaluate('el => getComputedStyle(el).justifyContent') == 'flex-start'
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
        link = page.get_by_role('link', name=messages['ui.templates_back.label'], exact=True)
        expect(link).to_have_attribute('href', '/templates')
        page.keyboard.press('Tab')
        expect(link).to_be_focused()
        assert link.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
        size = link.bounding_box()
        assert size['height'] >= 48 and size['width'] >= 48
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('h1, .alert, .ui-sem-control').evaluate_all('els => els.every(e => e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1)')
        page.screenshot(path=str(tmp_path / f'proof-{locale}-{width}.png'), full_page=True)
    finally:
        context.close()
