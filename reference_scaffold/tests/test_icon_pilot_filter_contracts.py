"""Optional filter adapters keep existing defaults and native field contracts."""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from flask import render_template_string
from markupsafe import Markup

from cafeteria.ui.semantics import SemanticError
from test_ui_semantics import semantic_app  # noqa: F401


CALL = "{% import template as ui %}{{ ui[macro]('/search', **options) }}"
MACROS = [('admin/_macros.html', 'filter_bar'), ('ui/_semantic.html', 'filter_bar_sem')]


@pytest.mark.parametrize('template,macro', MACROS)
@pytest.mark.parametrize('locale', ['de', 'en', 'xx'])
def test_filter_trailing_defaults_keep_identical_html(semantic_app, template, macro, locale):  # noqa: F811
    semantic_app.config['UI_LOCALE'] = locale
    options = dict(id='catalog', search_name='text', search_value='Soup & herbs', maxlength=200,
                   describedby='search-hint', loading='Find recipes', active=True, reset_url='/reset',
                   filters=Markup('<select name="tag"><option value="">All</option></select>'))
    with semantic_app.test_request_context():
        default = render_template_string(CALL, template=template, macro=macro, options=options)
        explicit = render_template_string(CALL, template=template, macro=macro,
                                          options=options | {'search_id': None, 'search_emphasis': None})
    assert default == explicit
    document = BeautifulSoup(default, 'html.parser')
    form = document.select_one('form[role="search"]')
    assert form['method'] == 'get' and form['action'] == '/search'
    assert form['data-loading'] == 'Find recipes'
    field = form.select_one('input[name="text"]')
    assert field['id'] == 'catalog-search'
    assert field['value'] == 'Soup & herbs'
    assert field['maxlength'] == '200' and field['aria-describedby'] == 'search-hint'
    assert form.select_one('label[for="catalog-search"]') is not None
    assert len(form.select('[data-semantic="view.filter"]')) == 1
    assert len(form.select('button[data-semantic="view.search"]')) == 1
    assert len(form.select('button[data-semantic="actions.apply"]')) == 1
    assert not form.select('.btn-primary')


@pytest.mark.parametrize('template,macro', MACROS)
def test_filter_explicit_id_and_primary_search_preserve_get_fields(semantic_app, template, macro):  # noqa: F811
    with semantic_app.test_request_context():
        html = render_template_string(CALL, template=template, macro=macro, options={
            'search_name': 'text', 'search_id': 'text', 'search_emphasis': 'primary',
            'id': 'recipe', 'maxlength': 200, 'describedby': 'text-hint',
        })
    document = BeautifulSoup(html, 'html.parser')
    assert document.select_one('label')['for'] == 'text'
    field = document.select_one('input')
    assert field['id'] == 'text' and field['name'] == 'text'
    assert field['maxlength'] == '200' and field['aria-describedby'] == 'text-hint'
    primary = document.select('button.btn-primary')
    assert len(primary) == 1
    assert primary[0]['data-semantic'] == 'view.search'
    assert primary[0]['type'] == 'submit'
    assert primary[0].get_text(strip=True) == ''


@pytest.mark.parametrize('template,macro', MACROS)
def test_filter_id_is_escaped_and_emphasis_uses_existing_validation(semantic_app, template, macro):  # noqa: F811
    identifier = 'text" autofocus="true'
    with semantic_app.test_request_context():
        html = render_template_string(CALL, template=template, macro=macro, options={'search_id': identifier})
        with pytest.raises(SemanticError, match='invalid emphasis'):
            render_template_string(CALL, template=template, macro=macro, options={'search_emphasis': 'untrusted'})
    document = BeautifulSoup(html, 'html.parser')
    assert document.select_one('input')['id'] == identifier
    assert document.select_one('label')['for'] == identifier
    assert not document.select('[autofocus]')
