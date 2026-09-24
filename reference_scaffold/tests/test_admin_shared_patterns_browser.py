"""M21–M25 contracts rendered through the real admin shell, on test-only routes."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import render_template_string, request
from playwright.sync_api import expect
from werkzeug.datastructures import MultiDict
from werkzeug.serving import make_server

from cafeteria.workflow_partial_form import _allergens
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import _factory
from flask import Flask
from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui
from cafeteria.ui.semantics import ROOT, STATIC, load_registry


@pytest.fixture
def shared_site(monkeypatch, tmp_path, database_engine, browser):  # noqa: F811
    app = _factory(monkeypatch, tmp_path, database_engine)
    client, _ = _login(app, database_engine, ['Cafeteria.Admin'])

    @app.route('/__shared_patterns__', methods=['GET', 'POST'])
    def shared_patterns():
        if request.method == 'POST':
            return {key: request.form.getlist(key) for key in request.form}
        return render_template_string('''{% extends 'admin/base_tabler.html' %}
        {% from 'admin/_macros.html' import page_header, option_detail_group, filter_bar, list_row, form_footer, disclosure_section, field, select, icon %}
        {% block page_header %}{{ page_header('Gemeinsame Muster') }}{% endblock %}
        {% block content %}
        {% set visible %}{{ select('category', 'Kategorie', [('all', 'Alle'), ('soup', 'Suppe')], 'soup') }}{% endset %}
        {% set more %}{{ field('source', 'Quelle', 'Küche') }}{% endset %}
        {{ filter_bar('/__shared_patterns__', search_name='query', search_value='Reis', filters=visible, more_filters=more, active=active, reset_url='/__shared_patterns__') }}
        {% set markings %}<span class="badge">Vegetarisch</span>{% endset %}
        {% set other %}<a class="btn" href="#archive">{{ icon('archive') }}Archivieren</a>{% endset %}
        {{ list_row('Kartoffelstock mit einer langen Bezeichnung', 'Beilage, in zwei Menüs verwendet', 'active', {'label': 'Bearbeiten', 'href': '#edit', 'icon': 'pencil'}, markings=markings, overflow=3, more_actions=other) }}
        <form id="pattern-form" method="post" action="/__shared_patterns__"{% if kind == 'menu' %} data-menu-editor{% endif %}>
          {% if kind == 'menu' %}
          <label class="form-check"><input type="radio" name="allergen_mode" value="manual" checked>Manuell</label>
          <label class="form-check"><input type="radio" name="allergen_mode" value="auto">Automatisch</label>
          {% endif %}
          {{ option_detail_group(options, submitted=values, errors=errors, field_prefix='allergen_' if kind == 'keyed' else none, code_name='choice' if kind == 'generic' else 'allergen_code', detail_name='detail' if kind == 'generic' else 'allergen_presence', mode='choice' if kind == 'generic' else 'allergen', manual=manual) }}
          {% call disclosure_section('Weitere Optionen', id='optional', has_content=content, has_error=error) %}
            {{ field('note', 'Notiz', 'Angabe' if content else '', error='Bitte prüfen' if error else none) }}
          {% endcall %}
          {% call disclosure_section('Offener Abschnitt', id='explicit', open=true) %}<p>Offen</p>{% endcall %}
          {{ form_footer({'label': 'Speichern', 'icon': 'device-floppy', 'name': 'intent', 'value': 'save'}, '#cancel', rare=other, sticky=true, form_id='pattern-form') }}
        </form>
        {% endblock %}''', options=[{'code': 'MILK', 'name': 'Milch'}, {'code': 'GLUTEN', 'name': 'Gluten'},
                                   {'code': 'LUPIN', 'name': 'Lupinen'}, {'code': 'EGG', 'name': 'Eier'}],
            values=MultiDict([('allergen_code', 'MILK'), ('allergen_presence', 'invalid' if 'invalid' in request.args else 'may_contain'),
                              ('allergen_code', 'EGG'), ('allergen_presence', 'contains'),
                              ('allergen_MILK', 'may_contain'), ('allergen_GLUTEN', 'absent'),
                              ('allergen_LUPIN', 'absent'), ('allergen_EGG', 'contains')]),
            kind=request.args.get('kind', 'paired'), content='content' in request.args,
            error='error' in request.args, errors={'allergen_presence': 'Bitte prüfen'} if 'invalid' in request.args else {},
            active=request.args.get('active', '1') == '1', manual='auto' not in request.args,
            family='cafeteria', profile='staff_guest')

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    try:
        yield browser, origin, {'name': cookie.key, 'value': cookie.value, 'url': origin}
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _run_polish_check(markup, check, width=390, javascript=True):
    # Own Playwright lifecycle on a separate thread from the module browser fixture.
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(_polish_check, markup, check, width, javascript).result(timeout=120)


def _polish_check(markup, check, width, javascript):
    from playwright.sync_api import sync_playwright

    app = Flask('polish-patterns', template_folder=str(ROOT.parent / 'templates'), static_folder=str(STATIC))
    app.config.update(TESTING=True, UI_LOCALE='de')
    register_template_filters(app)
    register_ui(app)

    @app.route('/__polish__', methods=['GET', 'POST'])
    def polish_page():
        if request.method == 'POST':
            return {key: request.form.getlist(key) for key in request.form}
        return render_template_string('''<!doctype html><html lang="de"><head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            {% for file in ['tokens.css', 'vendor/tabler/tabler.min.css', 'admin-tabler.css', 'ui-semantic.css'] %}
            <link rel="stylesheet" href="{{ url_for('static', filename=file) }}">{% endfor %}
            </head><body class="dishboard-admin"><main class="container-fluid">
            ''' + markup + '''</main><script src="{{ url_for('static', filename='admin.js') }}"></script></body></html>''')

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            chromium = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
            try:
                page = chromium.new_page(java_script_enabled=javascript, reduced_motion='reduce',
                                         viewport={'width': width, 'height': 900})
                assert page.goto(f'http://127.0.0.1:{server.server_port}/__polish__').status == 200
                page.evaluate('document.fonts.ready')
                check(page)
            finally:
                chromium.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('width,columns', [(360, 1), (768, 2), (1024, 2), (1440, 3), (1920, 3)])
def test_polish_field_grid_targets_and_adjacent_error(width, columns):
    markup = '''{% from 'admin/_macros.html' import field, select, check %}
        <div class="admin-option-grid">
          <div>{{ field('name', 'Name', error='Name fehlt') }}</div>
          <div>{{ select('kind', 'Art', [('a', 'Standard')]) }}</div>
          <div>{{ field('note', 'Notiz') }}</div>
        </div>{{ check('choice', 'Auswahl') }}{{ check('radio', 'Option', type='radio') }}'''

    def verify(page):
        grid = page.locator('.admin-option-grid')
        assert grid.evaluate('el => getComputedStyle(el).gridTemplateColumns.split(" ").length') == columns
        for control in page.locator('.form-control, .form-select').all():
            assert control.bounding_box()['height'] >= 48
        for label in page.locator('.form-label').all():
            expect(label).to_have_css('margin-bottom', '4px')
        for row in page.locator('.form-check').all():
            assert row.bounding_box()['height'] >= 44
        expect(page.locator('#name')).to_have_attribute('aria-invalid', 'true')
        expect(page.locator('#name')).to_have_attribute('aria-describedby', 'name-error')
        expect(page.locator('#name + .invalid-feedback')).to_have_text('Name fehlt')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')

    _run_polish_check(markup, verify, width, javascript=False)


@pytest.mark.parametrize('width', [360, 390, 767, 768, 1440])
def test_polish_stack_table_reflows_without_losing_labels(width, tmp_path):
    markup = '''<table class="table admin-table--stack">
        <caption>Bestand</caption><thead><tr><th scope="col">Name</th><th scope="col">Aktion</th></tr></thead>
        <tbody><tr><td data-label="Name">Reis</td><td data-label="Aktion"><button class="btn">Öffnen</button></td></tr>
        <tr><td data-label="Name">EinLangerUngetrennterNameMitVielenZeichenFürDenMobilenUmbruch</td>
        <td data-label="Aktion"><a class="btn" href="#detail">Details</a></td></tr></tbody></table>'''

    def verify(page):
        table = page.locator('table')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert table.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
        expect(page.get_by_role('button', name='Öffnen')).to_be_visible()
        if width < 768:
            expect(table.locator('tbody tr').first).to_have_css('display', 'grid')
            expect(table.locator('td').first).to_have_css('display', 'block')
            assert table.locator('td').first.evaluate('el => getComputedStyle(el, "::before").content') == '"Name"'
        else:
            expect(table).to_have_css('display', 'table')
            # 48px control + shared 8px block padding + one row separator.
            assert table.locator('tbody tr').first.bounding_box()['height'] <= 65
        page.screenshot(path=str(tmp_path / f'polish-table-{width}.png'), full_page=True)

    _run_polish_check(markup, verify, width, javascript=False)


def test_polish_loading_preserves_native_submitter_and_resets_on_pageshow():
    markup = '''<iframe name="result" title="Ergebnis"></iframe>
        <form id="editor" method="post" action="/__polish__" target="result" data-loading>
          <input name="note" value="Behalten">
          <button id="already-disabled" disabled>Gesperrt</button>
        </form><button id="save" class="btn btn-primary" type="submit" form="editor"
          name="intent" value="save" aria-busy="false"><span>Speichern</span></button>'''

    def verify(page):
        button = page.locator('#save')
        button.click()
        expect(button).to_be_disabled()
        expect(button).to_have_attribute('aria-busy', 'true')
        assert 'admin-btn-loading' in button.get_attribute('class').split()
        expect(button.locator('span')).to_be_visible()
        expect(button).to_have_text('Speichern')
        expect(button).not_to_have_css('color', 'rgba(0, 0, 0, 0)')
        assert button.evaluate('el => getComputedStyle(el, "::after").animationName') == 'none'
        body = page.frame_locator('iframe').locator('body')
        expect(body).to_contain_text('intent')
        assert json.loads(body.inner_text()) == {'intent': ['save'], 'note': ['Behalten']}
        page.evaluate('window.dispatchEvent(new PageTransitionEvent("pageshow", {persisted: true}))')
        expect(button).to_be_enabled()
        expect(button).to_have_attribute('aria-busy', 'false')
        assert 'admin-btn-loading' not in button.get_attribute('class').split()
        expect(page.locator('#already-disabled')).to_be_disabled()

    _run_polish_check(markup, verify)


def test_polish_loading_ignores_invalid_and_cancelled_submits():
    markup = '''<form data-loading><input id="required" required name="name">
        <button class="btn btn-primary">Speichern</button></form>'''

    def verify(page):
        button = page.get_by_role('button', name='Speichern')
        button.click()
        expect(button).to_be_enabled()
        expect(button).not_to_have_attribute('aria-busy', 'true')
        page.locator('#required').fill('Name')
        page.evaluate('document.querySelector("form").addEventListener("submit", e => e.preventDefault())')
        button.click()
        # Wait past the deferred native-submit hook without an arbitrary sleep.
        page.evaluate('new Promise(resolve => setTimeout(resolve, 0))')
        expect(button).to_be_enabled()
        expect(button).not_to_have_attribute('aria-busy', 'true')

    _run_polish_check(markup, verify)


@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('width', [360, 1440])
def test_polish_hint_modes_are_keyboard_reachable_and_keep_safety_inline(javascript, width):
    markup = '''{% from 'admin/_macros.html' import hint, option_detail_group %}
        {{ hint('Zusatzinformation', 'tip') }}
        {{ hint('Sicherheitsinformation', 'safety', mode='inline') }}
        {{ hint('Längere Erklärung', 'explanation', mode='dialog') }}
        {{ option_detail_group([]) }}'''

    def verify(page):
        tip = page.locator('[aria-describedby="tip"]')
        expect(tip).to_have_attribute('title', 'Zusatzinformation')
        expect(page.locator('#tip')).to_be_hidden()
        page.keyboard.press('Tab')
        expect(tip).to_be_focused()
        assert tip.evaluate('el => parseFloat(getComputedStyle(el).outlineWidth)') >= 2
        page.keyboard.press('Enter')
        expect(page.locator('#tip')).to_be_visible()
        expect(page.locator('#safety')).to_be_visible()
        expect(page.get_by_text('Nicht ausgewählt bedeutet nicht: allergenfrei bestätigt.', exact=True)).to_be_visible()
        page.keyboard.press('Tab')
        expect(page.locator('summary[aria-describedby="explanation"]')).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('#explanation')).to_be_visible()
        if javascript:
            expect(page.locator('dialog')).to_have_attribute('open', '')
            assert page.locator('dialog').evaluate('el => el.matches(":modal")')
            page.keyboard.press('Escape')
            expect(page.locator('#explanation')).to_be_hidden()
            expect(page.locator('summary[aria-describedby="explanation"]')).to_be_focused()
        else:
            page.keyboard.press('Enter')
            expect(page.locator('#explanation')).to_be_hidden()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')

    _run_polish_check(markup, verify, width, javascript)


def _page(shared_site, javascript=True, width=390, query=''):
    chromium, origin, cookie = shared_site
    context = chromium.new_context(java_script_enabled=javascript, viewport={'width': width, 'height': 900},
                                  reduced_motion='reduce', locale='de-CH')
    context.add_cookies([cookie])
    page = context.new_page()
    response = page.goto(origin + '/__shared_patterns__' + query)
    assert response.status == 200
    return page


def _pairs(page, codes='allergen_code', details='allergen_presence'):
    # Capture successful controls at a real submit event, without leaving the test page.
    page.evaluate('''() => document.querySelector('#pattern-form').addEventListener('submit', e => {
        e.preventDefault(); window.submitted = [...new FormData(e.target).entries()];
    }, {once: true})''')
    page.get_by_role('button', name='Speichern', exact=True).click()
    entries = page.evaluate('window.submitted')
    left = [value for key, value in entries if key == codes]
    right = [dict(entries)[f'{details}__{code}'] for code in left]
    assert len(left) == len(right)
    return list(zip(left, right, strict=True))


def test_option_detail_pairing_survives_non_sorted_toggles(shared_site):
    page = _page(shared_site)
    try:
        assert _pairs(page) == [('MILK', 'may_contain'), ('EGG', 'contains')]
        for code, checked in [('LUPIN', True), ('MILK', False), ('GLUTEN', True), ('EGG', False)]:
            page.locator(f'[name="allergen_code"][value="{code}"]').set_checked(checked)
        page.locator('#allergen-lupin-presence').select_option('may_contain')
        assert _pairs(page) == [('GLUTEN', 'contains'), ('LUPIN', 'may_contain')]
        expect(page.locator('#allergen-milk-presence')).to_be_enabled()
        expect(page.locator('#allergen-milk-presence')).to_be_hidden()
        expect(page.locator('#allergen-egg-presence')).to_be_enabled()
        page.locator('[name="allergen_code"][value="MILK"]').check()
        page.locator('[name="allergen_code"][value="LUPIN"]').uncheck()
        assert _pairs(page) == [('MILK', 'may_contain'), ('GLUTEN', 'contains')]
        expect(page.locator('[data-option-count]')).to_have_text('2 ausgewählt')
        expect(page.locator('[data-option-count]')).to_have_attribute('aria-live', 'polite')
        for row in page.locator('[data-option-detail]').all():
            expect(row.locator('label .icon')).to_have_count(1)
        selected = page.locator('[data-option-detail]').filter(has=page.locator('input:checked')).first
        assert selected.evaluate('el => parseFloat(getComputedStyle(el).borderTopWidth)') >= 2
        expect(page.get_by_text('Nicht ausgewählt bedeutet nicht: allergenfrei bestätigt.', exact=True)).to_be_visible()
        option_text = ' '.join(page.locator('[data-option-detail]').all_inner_texts()).lower()
        assert 'allergenfrei' not in option_text and 'frei von' not in option_text
    finally:
        page.context.close()


@pytest.mark.parametrize('kind', ['paired', 'keyed'])
def test_option_detail_nojs_preserves_initial_successful_controls(shared_site, kind):
    page = _page(shared_site, javascript=False, query='?kind=' + kind)
    try:
        expect(page.locator('[data-option-detail] select')).to_have_count(4)
        if kind == 'paired':
            expect(page.locator('#allergen-gluten-presence')).to_be_enabled()
            expect(page.locator('#allergen-milk-presence')).to_be_enabled()
        else:
            page.locator('select[name="allergen_GLUTEN"]').select_option('contains')
        with page.expect_navigation():
            page.get_by_role('button', name='Speichern', exact=True).click()
        result = page.locator('body').inner_text()
        data = json.loads(result)
        if kind == 'paired':
            assert [(code, data[f'allergen_presence__{code}'][0]) for code in data['allergen_code']] == [
                ('MILK', 'may_contain'), ('EGG', 'contains')]
        else:
            assert data['allergen_MILK'] == ['may_contain']
            assert data['allergen_GLUTEN'] == ['contains']
            assert data['allergen_LUPIN'] == ['absent']
            assert data['allergen_EGG'] == ['contains']
    finally:
        page.context.close()


def test_option_detail_generic_container_and_menu_modes(shared_site):
    for kind in ('generic', 'menu'):
        page = _page(shared_site, query='?kind=' + kind)
        try:
            if kind == 'generic':
                expect(page.locator('.allergen-row')).to_have_count(0)
                page.locator('[value="LUPIN"][type="checkbox"]').check()
                page.locator('#allergen-lupin-presence').select_option('may_contain')
                assert _pairs(page, 'choice', 'detail') == [('LUPIN', 'may_contain')]
            else:
                page.get_by_label('Automatisch', exact=True).check()
                assert _pairs(page) == []
                expect(page.locator('[name="allergen_code"]').first).to_be_disabled()
                page.get_by_label('Manuell', exact=True).check()
                assert _pairs(page) == [('MILK', 'may_contain'), ('EGG', 'contains')]
        finally:
            page.context.close()


def test_option_detail_keyed_sends_absent_explicitly(shared_site):
    page = _page(shared_site, query='?kind=keyed')
    try:
        page.locator('#allergen-egg-presence').select_option('absent')
        expect(page.locator('#allergen-egg')).to_be_focused()
        expect(page.locator('#allergen-egg')).not_to_be_checked()
        page.locator('#allergen-egg').check()
        page.locator('#allergen-milk').uncheck()
        page.locator('#allergen-lupin').check()
        page.locator('#allergen-lupin-presence').select_option('may_contain')
        with page.expect_navigation():
            page.get_by_role('button', name='Speichern', exact=True).click()
        data = json.loads(page.locator('body').inner_text())
        assert {key: value for key, value in data.items() if key.startswith('allergen_')} == {
            'allergen_MILK': ['absent'], 'allergen_GLUTEN': ['absent'],
            'allergen_LUPIN': ['may_contain'], 'allergen_EGG': ['contains']}
    finally:
        page.context.close()


@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('width', [360, 768, 1024, 1440])
def test_shared_patterns_semantics_reflow_focus_and_targets(shared_site, javascript, width, tmp_path):
    page = _page(shared_site, javascript=javascript, width=width, query='?error=1')
    try:
        expect(page.locator('#optional')).to_have_attribute('open', '')
        expect(page.locator('#explicit')).to_have_attribute('open', '')
        expect(page.locator('.admin-form-footer .btn-primary')).to_have_count(1)
        expect(page.locator('.admin-list-actions a:visible')).to_have_count(1)
        expect(page.locator('.admin-list-row [data-status="active"]')).to_have_text('Aktiv')
        expect(page.locator('.admin-list-row')).to_contain_text('+3')
        expect(page.locator('.admin-filter-bar')).to_have_attribute('method', 'get')
        expect(page.locator('.admin-filter-bar input').first).to_have_attribute('name', 'query')
        for summary in page.locator('main summary').all():
            summary.focus()
            expect(summary).to_be_focused()
            assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
            if summary.locator('..').get_attribute('open') is None:
                page.keyboard.press('Enter')
        targets = page.locator('main :is(button, a.btn, select, input:not([type="hidden"]), summary)').all()
        for target in targets:
            if not target.is_visible():
                continue
            measured = target.evaluate('''el => {
                const target = el.type === 'checkbox' || el.type === 'radio' ? el.closest('label') : el;
                const r = target.getBoundingClientRect(); return [r.width, r.height];
            }''')
            assert measured[0] >= 48 and measured[1] >= 48, measured
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        for glyph in page.locator('main svg use').all():
            assert glyph.evaluate('el => el.getBBox().width > 0'), glyph.get_attribute('href')
        page.screenshot(path=str(tmp_path / f'shared-{width}-{javascript}.png'), full_page=True)
        page.set_viewport_size({'width': width, 'height': 450})
        expect(page.locator('.admin-form-footer')).to_have_css('position', 'static')
        page.get_by_label('Notiz', exact=True).focus()
        expect(page.get_by_label('Notiz', exact=True)).to_be_focused()
    finally:
        page.context.close()


def test_filter_get_parameters_and_disclosure_content(shared_site):
    page = _page(shared_site, javascript=False, query='?content=1&active=0')
    try:
        expect(page.locator('#optional')).to_have_attribute('open', '')
        expect(page.locator('#optional summary')).to_contain_text('enthält Angaben')
        expect(page.get_by_role('link', name='Filter zurücksetzen')).to_have_count(0)
        with page.expect_navigation():
            page.get_by_role('button', name='Filtern', exact=True).click()
        assert parse_qs(urlsplit(page.url).query) == {'query': ['Reis'], 'category': ['soup'], 'source': ['Küche']}
        expect(page.locator('#optional')).not_to_have_attribute('open', '')
    finally:
        page.context.close()


@pytest.mark.parametrize('javascript', [False, True])
def test_option_detail_server_disabled_and_error_links(shared_site, javascript):
    page = _page(shared_site, javascript=javascript, query='?auto=1')
    try:
        for control in page.locator('[data-option-check], [data-option-presence]').all():
            expect(control).to_be_disabled()
        page.goto(page.url.replace('auto=1', 'invalid=1'))
        presence = page.locator('#allergen-milk-presence')
        expect(presence).to_have_attribute('aria-invalid', 'true')
        expect(presence).to_have_attribute('aria-describedby', 'allergen-milk-error')
        expect(page.locator('#allergen-milk-error.field-error')).to_have_text('Bitte prüfen')
        assert 'is-invalid' in presence.get_attribute('class').split()
    finally:
        page.context.close()


def test_option_detail_nojs_new_selection_preserves_identity(shared_site):
    page = _page(shared_site, javascript=False)
    try:
        page.locator('#allergen-lupin').check()
        expect(page.locator('#allergen-lupin-presence')).to_be_enabled()
        page.locator('#allergen-lupin-presence').select_option('may_contain')
        with page.expect_navigation():
            page.get_by_role('button', name='Speichern', exact=True).click()
        data = json.loads(page.locator('body').inner_text())
        submitted = MultiDict((key, value) for key, values in data.items() for value in values)
        assert {row['code']: row['presence'] for row in _allergens(submitted, 'Makro-Test')} == {
            'MILK': 'may_contain', 'EGG': 'contains', 'LUPIN': 'may_contain',
        }
    finally:
        page.context.close()


def test_form_footer_sticky_yields_to_focus_errors_and_short_viewport(shared_site):
    page = _page(shared_site, width=1440, query='?content=1')
    try:
        footer = page.locator('.admin-form-footer')
        expect(footer).to_have_attribute('data-sticky-ready', 'true')
        expect(footer).to_have_css('position', 'sticky')
        page.get_by_label('Notiz', exact=True).focus()
        expect(footer).to_have_css('position', 'static')
        page.locator('#optional summary').focus()
        expect(footer).to_have_css('position', 'sticky')
        page.set_viewport_size({'width': 1440, 'height': 450})
        expect(footer).to_have_css('position', 'static')
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(page.url.replace('content=1', 'error=1'))
        expect(footer).to_have_css('position', 'static')
    finally:
        page.context.close()


PAGE = '''<!doctype html><html lang="de"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
{% for file in ['vendor/tabler/tabler.min.css', 'admin-tabler.css', 'ui-semantic.css'] %}
<link rel="stylesheet" href="{{ url_for('static', filename=file) }}">{% endfor %}
</head><body class="admin-body dishboard-admin"><main class="container-fluid py-4">
{% from 'admin/_macros.html' import icon %}
{% for ic in icons %}
    {{ icon(ic) }}
{% endfor %}
</main></body></html>'''


@pytest.mark.parametrize('width', [360, 768, 1024, 1440])
def test_statusbar_link_keyboard_focus_and_navigation(width):
    # The module-scoped browser fixture owns the main thread's sync event loop.
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(_assert_statusbar_link_keyboard_focus_and_navigation, width).result(timeout=120)


def _assert_statusbar_link_keyboard_focus_and_navigation(width):
    from playwright.sync_api import sync_playwright

    app = Flask('statusbar-links', template_folder=str(ROOT.parent / 'templates'),
                static_folder=str(STATIC))
    register_template_filters(app)
    register_ui(app)

    @app.route('/__statusbar__')
    def statusbar_page():
        return render_template_string('''<!doctype html><html lang="de"><head>
        {% for file in ['tokens.css', 'vendor/tabler/tabler.min.css', 'admin-tabler.css'] %}
        <link rel="stylesheet" href="{{ url_for('static', filename=file) }}">{% endfor %}
        </head><body class="dishboard-admin">
        {% from 'admin/_macros.html' import page_header %}
        {{ page_header('Status', status_items=[
            {'label': 'Prüfstand', 'value': 'Offen', 'variant': 'warning', 'href': '#existing'},
            {'label': 'Menüs', 'value': 0}]) }}
        <section id="existing">Vorhandenes Ziel</section></body></html>''')

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            chromium = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
            try:
                page = chromium.new_page(java_script_enabled=False,
                                         viewport={'width': width, 'height': 900})
                origin = f'http://127.0.0.1:{server.server_port}'
                assert page.goto(origin + '/__statusbar__').status == 200
                link = page.get_by_role('link', name='Offen', exact=True)
                expect(link).to_have_attribute('href', '#existing')
                expect(page.locator('dd').nth(1).locator('a')).to_have_count(0)
                expect(link).to_have_css('text-decoration-line', 'none')
                assert link.evaluate('el => getComputedStyle(el).color === getComputedStyle(el.parentElement).color')
                assert link.bounding_box()['height'] >= 48
                page.keyboard.press('Tab')
                expect(link).to_be_focused()
                expect(link).to_have_css('text-decoration-line', 'underline')
                assert link.evaluate('el => el.matches(":focus-visible")')
                assert link.evaluate('el => parseFloat(getComputedStyle(el).outlineWidth)') >= 2
                expect(link).to_have_css('outline-style', 'solid')
                link.click()
                expect(page).to_have_url(origin + '/__statusbar__#existing')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            finally:
                chromium.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('width', [360, 390, 768, 1024, 1440, 1920])
def test_p2b_labels_rows_actions_and_sorting_without_js(width, tmp_path):
    markup = '''{% from 'admin/_macros.html' import label, list_row, empty_value, sort_header %}
        {% from 'ui/_semantic.html' import row_actions, icon_button %}
        <section id="labels">
        {% for variant in ['neutral', 'info', 'active', 'success', 'warning', 'danger', 'category'] %}
          {{ label('Prüfung offen', variant, icon='alert-triangle', detail='Allergenangaben fehlen') }}
        {% endfor %}</section>
        {% set controls = row_actions([{'key': 'actions.edit', 'href': '#edit', 'icon_only': true},
          {'key': 'actions.preview', 'href': '#preview'}, {'key': 'actions.copy', 'href': '#copy'}]) %}
        <section id="row">{{ list_row(primary='Reis', meta=empty_value(),
          status=label('Aktiv', 'active'), actions=controls) }}</section>
        <table class="table admin-table admin-table--stack"><thead><tr>
          {{ sort_header('Name', 'name', 'name', 'asc', '?sort=name&direction=desc') }}
          <th>Info</th><th>Status</th><th>Aktionen</th></tr></thead><tbody><tr>
          <td data-label="Name"><strong>Reis</strong></td><td data-label="Info">{{ empty_value() }}</td>
          <td data-label="Status" class="admin-table-status">{{ label('Aktiv', 'active') }}</td>
          <td data-label="Aktionen" class="admin-table-actions">{{ controls }}</td>
        </tr></tbody></table>
        <section id="sizes">{{ icon_button('actions.edit', href='#edit') }}
          {{ icon_button('actions.edit', href='#edit', icon_only=true) }}
          {{ icon_button('actions.edit', href='#edit', icon_only=true, size='large') }}
          {{ icon_button('actions.edit', href='#edit', size='large') }}</section>'''

    def verify(page):
        import json
        import re

        def luminance(color):
            channels = [int(x) / 255 for x in re.findall(r'\d+', color)[:3]]
            linear = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in channels]
            return sum(x * weight for x, weight in zip(linear, (.2126, .7152, .0722), strict=True))

        labels = page.locator('#labels .admin-label')
        heights = [node.bounding_box()['height'] for node in labels.all()]
        contrasts = []
        assert len(heights) == 7 and max(heights) - min(heights) <= 1
        for node in labels.all():
            expect(node).to_have_attribute('title', 'Allergenangaben fehlen')
            expect(node.locator('.visually-hidden')).to_contain_text('Allergenangaben fehlen')
            colors = node.evaluate('e => [getComputedStyle(e).color, getComputedStyle(e).backgroundColor]')
            foreground, background = sorted(map(luminance, colors))
            contrasts.append((background + .05) / (foreground + .05))
            assert contrasts[-1] >= 4.5, colors
        group = page.locator('#row .admin-row-actions')
        expect(group.locator(':scope > a:visible')).to_have_count(1)
        expect(group.locator('details a:visible')).to_have_count(0)
        direct = group.locator(':scope > a')
        expect(direct).to_have_attribute('aria-label', 'Bearbeiten')
        expect(direct).to_have_attribute('title', 'Bearbeiten')
        size = direct.bounding_box()
        assert size['height'] >= 48 and abs(size['width'] - size['height']) <= 1
        page.keyboard.press('Tab')
        expect(direct).to_be_focused()
        assert direct.evaluate('e => parseFloat(getComputedStyle(e).outlineWidth)') >= 2
        page.keyboard.press('Tab')
        expect(group.locator('summary')).to_be_focused()
        page.keyboard.press('Enter')
        expect(group.locator('details')).to_have_attribute('open', '')
        expect(group.locator('details a:visible')).to_have_count(2)
        page.keyboard.press('Tab')
        expect(group.get_by_role('link', name='Vorschau', exact=True)).to_be_focused()
        page.keyboard.press('Shift+Tab')
        page.keyboard.press('Space')
        expect(group.locator('details')).not_to_have_attribute('open', '')
        expect(page.locator('th[aria-sort]')).to_have_attribute('aria-sort', 'ascending')
        expect(page.locator('th[aria-sort] a')).to_have_attribute('href', '?sort=name&direction=desc')
        assert page.locator('.admin-empty-value').all_text_contents() == ['—', '—']
        row = page.locator('#row .admin-list-row')
        table_row = page.locator('tbody tr')
        if width >= 768:
            assert abs(row.bounding_box()['height'] - table_row.bounding_box()['height']) <= 1
            for side in ['Top', 'Right', 'Bottom', 'Left']:
                assert row.evaluate(f'e => getComputedStyle(e).padding{side}') == page.locator('tbody td').first.evaluate(f'e => getComputedStyle(e).padding{side}')
        else:
            assert row.evaluate('e => getComputedStyle(e).padding') == table_row.evaluate('e => getComputedStyle(e).padding')
            for cell in table_row.locator('td').all():
                assert cell.bounding_box()['width'] >= table_row.bounding_box()['width'] - 25
        assert abs(row.locator('.admin-label').bounding_box()['height'] - table_row.locator('.admin-label').bounding_box()['height']) <= 1
        for control in table_row.locator('a:visible, summary').all():
            box = control.bounding_box()
            assert box['x'] >= 0 and box['width'] >= 48 and box['height'] >= 48
        sizes = page.locator('#sizes a').all()
        assert abs(sizes[0].bounding_box()['height'] - sizes[1].bounding_box()['height']) <= 1
        assert sizes[2].bounding_box()['height'] == sizes[2].bounding_box()['width'] == 56
        assert sizes[3].bounding_box()['height'] == sizes[2].bounding_box()['height']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        (tmp_path / f'p2b-{width}.json').write_text(json.dumps({
            'width': width, 'label_heights': heights, 'contrast_ratios': contrasts,
            'list_height': row.bounding_box()['height'],
            'table_height': table_row.bounding_box()['height'],
            'icon_button': size,
        }, indent=2))
        page.screenshot(path=str(tmp_path / f'p2b-{width}.png'), full_page=True)
        page.locator('body').evaluate("e => e.style.zoom = '2'")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')

    _run_polish_check(markup, verify, width, javascript=False)


def test_admin_icons_exist_and_render(browser):  # noqa: F811
    # Every registry icon resolves to a sprite symbol that renders with a real bounding box.
    app = Flask('semantic-browser2', template_folder=str(ROOT.parent / 'templates'),
                static_folder=str(STATIC))
    app.config.update(TESTING=True, UI_LOCALE='de')
    register_template_filters(app)
    register_ui(app)
    # Render the resolved icon: entries without a sprite symbol fall back centrally.
    # food:* icons render through the food symbol map, not the Tabler sprite.
    icons = sorted({entry.resolved_icon for entry in load_registry().values()
                    if not entry.resolved_icon.startswith('food:')})
    assert icons

    @app.route('/__test__')
    def test_page():
        return render_template_string(PAGE, icons=icons)

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with browser.new_context(java_script_enabled=False) as context:
            page = context.new_page()
            response = page.goto(f'http://127.0.0.1:{server.server_port}/__test__')
            assert response is not None and response.status == 200
            glyphs = page.locator('main svg use').all()
            assert len(glyphs) == len(icons)
            for glyph in glyphs:
                assert glyph.evaluate('el => el.getBBox().width > 0'), glyph.get_attribute('href')
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
