"""M21–M25 contracts rendered through the real admin shell, on test-only routes."""
from __future__ import annotations

import json
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import render_template_string, request
from playwright.sync_api import expect
from werkzeug.datastructures import MultiDict
from werkzeug.serving import make_server

from cafeteria.workflow import WorkflowValidationError
from cafeteria.workflow_partial_form import _allergens
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_route_inventory import _factory


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
    right = [value for key, value in entries if key == details]
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
        expect(page.locator('#allergen-milk-presence')).to_be_disabled()
        expect(page.locator('#allergen-egg-presence')).to_be_disabled()
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
            expect(page.locator('#allergen-gluten-presence')).to_be_disabled()
            expect(page.locator('#allergen-milk-presence')).to_be_enabled()
        else:
            page.locator('select[name="allergen_GLUTEN"]').select_option('contains')
        with page.expect_navigation():
            page.get_by_role('button', name='Speichern', exact=True).click()
        result = page.locator('body').inner_text()
        data = json.loads(result)
        if kind == 'paired':
            assert list(zip(data['allergen_code'], data['allergen_presence'], strict=True)) == [
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
        expect(presence).to_have_attribute('aria-describedby', 'err-allergen-presence')
        expect(page.locator('#err-allergen-presence.field-error')).to_have_text('Bitte prüfen')
        assert 'is-invalid' in presence.get_attribute('class').split()
    finally:
        page.context.close()


def test_option_detail_nojs_new_selection_is_rejected_by_existing_parser(shared_site):
    page = _page(shared_site, javascript=False)
    try:
        page.locator('#allergen-lupin').check()
        expect(page.locator('#allergen-lupin-presence')).to_be_disabled()
        with page.expect_navigation():
            page.get_by_role('button', name='Speichern', exact=True).click()
        data = json.loads(page.locator('body').inner_text())
        submitted = MultiDict((key, value) for key, values in data.items() for value in values)
        with pytest.raises(WorkflowValidationError, match='Zusammengehörige Felder sind unvollständig'):
            _allergens(submitted, 'Makro-Test')
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
