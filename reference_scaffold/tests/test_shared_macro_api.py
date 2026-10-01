"""DB-free UC-G0d compatibility and attribute trust-boundary contracts."""
from __future__ import annotations

from itertools import product

import pytest
from bs4 import BeautifulSoup
from flask import render_template_string
from jinja2 import nodes
from markupsafe import Markup

from cafeteria.ui.semantics import ROOT, SemanticError
from test_ui_semantics import semantic_app  # noqa: F401


# Frozen verbatim from base 2e9ab299; never regenerate from the implementation.
LEGACY = '''{% from 'admin/_macros.html' import actions, icon %}
{%- macro form_footer(primary, cancel_url, rare=none, sticky=false, form_id=none, secondary=none, danger=none) -%}
{% from 'ui/_semantic.html' import icon_button %}
<div class="admin-form-footer"{% if sticky %} data-sticky{% if form_id %} data-sticky-form="{{ form_id }}"{% endif %}{% endif %}>
  {% if danger %}<div class="admin-form-danger">{{ danger }}</div>{% endif %}
  {% if rare and rare|trim %}<div class="admin-form-rare admin-row-actions" role="group" aria-label="{{ t('ui.action_group.aria') }}">{{ rare }}</div>{% endif %}
  <div class="admin-form-main">
    {% if secondary %}{{ actions(secondary=secondary) }}{% endif %}
    {{ icon_button('actions.cancel', href=cancel_url) }}
    {{ actions(primary=primary) }}
  </div>
</div>
{%- endmacro %}

{%- macro disclosure_section(title=none, id=none, open=false, has_content=false, has_error=false, variant='plain') -%}
<details class="admin-compact-details admin-disclosure{% if variant == 'card' %} card admin-disclosure--card{% endif %}"{% if id %} id="{{ id }}"{% endif %}{% if open or has_content or has_error %} open{% endif %}>
  <summary>{{ icon(sem('ui.disclosure.more_options').resolved_icon) }}{{ t(sem('ui.disclosure.more_options').label_key) if title is none else title }}{% if has_content %}<span class="text-secondary"> · {{ t(sem('ui.disclosure.has_content').label_key) }}</span>{% endif %}</summary>
  <div class="admin-compact-detail-body">{{ caller() if caller else '' }}</div>
</details>
{%- endmacro %}'''


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('populated', [False, True])
def test_every_existing_footer_call_renders_byte_identically(semantic_app, family, populated):  # noqa: F811
    """Render actual call ASTs, including their expressions, with synthetic data."""
    env = semantic_app.jinja_env
    calls = []
    for path in sorted((ROOT.parent / 'templates').rglob('*.html')):
        for call in env.parse(path.read_text()).find_all(nodes.Call):
            if isinstance(call.node, nodes.Name) and call.node.name == 'form_footer':
                calls.append((path, call))
    assert len(calls) == 11, 'Review compatibility inventory when consumers change'
    with semantic_app.test_request_context('/'):
        before = env.from_string(LEGACY).module.form_footer
        after = env.get_template('admin/_macros.html').module.form_footer
        icon_button = env.get_template('ui/_semantic.html').module.icon_button
        save = icon_button('actions.save', name='intent', value='save', form='editor')
        data = dict(
            family=family, error=populated, error_purpose='core', core='core',
            kind='food', query_kinds={'food': 'food'}, recipe_editor=populated,
            week='2026-W40', public_id='synthetic-template', book=populated, row=populated,
            list_args={'q': 'Reis & Suppe', 'archived': '1'},
            save_action=save, save_primary=save, add_primary=save, continue_primary=save,
            archive_rare=icon_button('actions.open', href='#archive'),
            g={key: '/filtered?q=Reis&archived=1' for key in (
                'food_list_return', 'cookbook_list_return', 'recipe_list_return',
                'component_list_return')} if populated else {},
            url_for=lambda endpoint, **values: '/' + endpoint + '?' + repr(sorted(values.items())),
            icon_button=icon_button,
        )
        for path, call in calls:
            ast = nodes.Template([nodes.Output([call])]).set_environment(env)
            template = env.template_class.from_code(env, env.compile(ast), env.globals, None)
            assert template.render(form_footer=after, **data) == template.render(
                form_footer=before, **data), f'{path}:{call.lineno}'


@pytest.mark.parametrize('profile', ['staff_guest', 'patients'])
@pytest.mark.parametrize('populated', [False, True])
def test_every_existing_disclosure_call_renders_byte_identically(semantic_app, profile, populated):  # noqa: F811
    env = semantic_app.jinja_env
    calls = []
    for path in sorted((ROOT.parent / 'templates').rglob('*.html')):
        for call in env.parse(path.read_text()).find_all(nodes.Call):
            if isinstance(call.node, nodes.Name) and call.node.name == 'disclosure_section':
                calls.append((path, call))
    assert len(calls) == 64, 'Review compatibility inventory when consumers change'
    text = 'Suppe <&>' if populated else ''
    values = dict.fromkeys([
        'note', 'shared_note', 'menu_week_public_id', 'prepared_recipe_choice', 'label',
        'scopes_preview', 'channel_cafeteria', 'channel_patienten', 'density_g_per_ml',
        'piece_weight_g', 'tag_public_ids', 'labels', 'food_public_id', 'description',
        'internal_chf', 'external_chf'], text)
    values.update(action='save_schedule', profile=profile)
    source = dict.fromkeys(['reference', 'url', 'note', 'fetched_at'], text)
    data = dict(
        profile=profile, code=profile, form_id='course', exceptions=[text] if populated else [],
        course_open=populated, expanded=populated, error=populated, error_message=text,
        create_title='Anlegen', roles_title='Rollen', state_title='Status',
        password_title='Passwort',  # noqa: S106 -- UI section title, not a credential.
        group='heading', group_label='Überschrift', singular='Einheit', recipe_query=text,
        recipe_page=2 if populated else 1, values=values, submitted=values, errors=values,
        field_errors=values, component={'food_public_id': text}, detail={'note': text},
        row={'allergens': [text], 'fetched_at': text} if populated else {},
        payload={'source': source}, display_errors=text, invalid=populated, result=text,
        error_field='layout_heading_size' if populated else '', error_purpose='tags',
        error_action='restore', error_form='demand', optional_content=text, optional_errors=text,
        area_names={'staff_guest': 'Cafeteria', 'patients': 'Patienten'},
        schedule_error={'found': populated}, exception_error={'found': populated}, preview=populated,
        suppliers=[text] if populated else [], baskets=[], request={'args': {'open': 'korb'}},
        menu_revision_public_ids=[text] if populated else [],
        body=lambda: Markup('<input name="draft" value="un saved">'),
    )
    with semantic_app.test_request_context('/'):
        before = env.from_string(LEGACY).module.disclosure_section
        after = env.get_template('admin/_macros.html').module.disclosure_section
        for path, call in calls:
            call.kwargs.append(nodes.Keyword('caller', nodes.Name('body', 'load')))
            ast = nodes.Template([nodes.Output([call])]).set_environment(env)
            template = env.template_class.from_code(env, env.compile(ast), env.globals, None)
            assert template.render(disclosure_section=after, **data) == template.render(
                disclosure_section=before, **data), f'{path}:{call.lineno}'


def test_existing_disclosure_and_footer_options_are_byte_identical(semantic_app):  # noqa: F811
    with semantic_app.test_request_context('/'):
        old = semantic_app.jinja_env.from_string(LEGACY).module
        new = semantic_app.jinja_env.get_template('admin/_macros.html').module
        for title, variant, opened, content, error in product(
                [None, 'Weitere <Angaben>'], ['plain', 'card'], [False, True],
                [False, True], [False, True]):
            options = dict(title=title, id='details', variant=variant, open=opened,
                           has_content=content, has_error=error,
                           caller=lambda: Markup('<input name="draft" value="un saved">'))
            assert new.disclosure_section(**options) == old.disclosure_section(**options)
        for sticky, secondary, danger, rare in product(
                [False, True], [None, [{'label': 'Vorschau', 'href': '#preview'}]],
                [None, Markup('<span>Gefahr</span>')], [None, Markup('<span>Zusatz</span>')]):
            options = dict(primary={'label': 'Speichern'}, cancel_url='#cancel', sticky=sticky,
                           form_id='editor', secondary=secondary, danger=danger, rare=rare)
            assert new.form_footer(**options) == old.form_footer(**options)


@pytest.mark.parametrize('icon', [False, True])
def test_disclosure_classes_and_attributes_escape_even_trusted_markup(semantic_app, icon):  # noqa: F811
    hostile = Markup('\" autofocus onfocus=\"alert(1)\"><script>bad()</script>')
    with semantic_app.test_request_context('/'):
        html = render_template_string('''{% from 'admin/_macros.html' import disclosure_section %}
            {{ disclosure_section(title=title, id='extra', details_class=value,
                details_attrs={'data-note': value, 'hidden': false, 'aria-busy': false},
                summary_class=value, summary_attrs={'data-note': value, 'aria-controls':'body'},
                summary_key='ui.disclosure.details' if icon else none, summary_object='Suppe') }}''',
            value=hostile, title='Details <&>', icon=icon)
    soup = BeautifulSoup(html, 'html.parser')
    assert not soup.select('script, [onfocus], [autofocus], [hidden]')
    for element in [soup.details, soup.summary]:
        assert element['data-note'] == hostile
        assert '\"' in ' '.join(element['class'])
    assert soup.details['aria-busy'] == 'false'
    assert soup.summary['aria-controls'] == 'body'
    if icon:
        assert soup.summary['aria-label'] == soup.summary['data-ui-tooltip'] == 'Details <&>'


@pytest.mark.parametrize('target', ['details_attrs', 'summary_attrs'])
@pytest.mark.parametrize('attrs', [
    {'onclick': 'alert(1)'}, {'data-x\" onfocus': 'bad'}, {'class': 'replacement'},
    {'hidden': 'false'}, '<b>raw</b>',
])
def test_disclosure_rejects_unsafe_attributes(semantic_app, target, attrs):  # noqa: F811
    with semantic_app.test_request_context('/'), pytest.raises(SemanticError):
        render_template_string("{% from 'admin/_macros.html' import disclosure_section %}"
                               '{{ disclosure_section(**options) }}', options={target: attrs})


@pytest.mark.parametrize('order', [[], ['primary'], ['primary', 'primary', 'cancel'],
                                  ['secondary', 'cancel', 'unknown'], 'primary'])
def test_footer_rejects_orders_that_drop_or_duplicate_actions(semantic_app, order):  # noqa: F811
    with semantic_app.test_request_context('/'), pytest.raises(SemanticError):
        render_template_string("{% from 'admin/_macros.html' import form_footer %}"
                               "{{ form_footer('Speichern', action_order=order) }}", order=order)


def test_save_only_and_ordered_footer_keep_native_form_contracts(semantic_app):  # noqa: F811
    with semantic_app.test_request_context('/'):
        html = render_template_string('''{% from 'admin/_macros.html' import form_footer %}
            {{ form_footer({'label':'Speichern', 'name':'intent', 'value':'save', 'form':'editor'}) }}
            {{ form_footer({'label':'Speichern', 'name':'intent', 'value':'save'}, '/back',
                secondary=[{'label':'Speichern und zurück', 'name':'intent', 'value':'back',
                            'type':'submit', 'form':'editor', 'formaction':'/save-back',
                            'formnovalidate':true},
                           {'label':'Vorschau', 'href':'/preview'}],
                action_order=['primary', 'secondary', 'cancel']) }}''')
    footers = BeautifulSoup(html, 'html.parser').select('.admin-form-footer')
    assert len(footers[0].select('button')) == 1
    assert not footers[0].select('[data-semantic="actions.cancel"]')
    assert footers[0].button['form'] == 'editor'
    controls = footers[1].select('button, a')
    assert [control['aria-label'] for control in controls] == [
        'Speichern', 'Speichern und zurück', 'Vorschau', 'Abbrechen']
    assert controls[1]['formaction'] == '/save-back'
    assert controls[1]['form'] == 'editor'
    assert controls[1]['type'] == 'submit'
    assert 'formnovalidate' in controls[1].attrs
    assert controls[-1]['href'] == '/back'
