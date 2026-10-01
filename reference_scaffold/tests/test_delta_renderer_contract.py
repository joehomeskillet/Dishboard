"""DELTA-2: exclusive controls and semantic optional slots, without a database."""
from __future__ import annotations

from itertools import product
import json
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from flask import render_template_string
from jinja2 import nodes
from markupsafe import Markup

from cafeteria.ui.semantics import ROOT, SemanticError
from test_shared_macro_api import _action_context, _compile_call
from test_ui_semantics import semantic_app  # noqa: F401


def render(app, expression, **values):
    with app.test_request_context('/'):
        return BeautifulSoup(render_template_string(
            "{% from 'ui/_semantic.html' import icon_button, icon_summary, row_actions, "
            "read_detail_trigger, read_detail_dialog, filter_bar_sem, filter_trigger %}"
            "{% from 'admin/_macros.html' import list_row, empty_value %}" + expression,
            **values), 'html.parser')


@pytest.mark.parametrize('slot', ['status', 'meta', 'subtitle', 'markings'])
@pytest.mark.parametrize('value', [None, '', ' ', '\n\t', Markup('<span> </span>'),
                                  Markup('<span><b></b>&nbsp;</span>')])
def test_optional_empty_slots_have_no_wrapper_or_placeholder(semantic_app, slot, value):  # noqa: F811
    doc = render(semantic_app, "{{ list_row(primary='Apfel-Essig', **slots) }}",
                 slots={slot: value})
    assert not doc.select('.admin-list-status, .admin-list-meta, .admin-list-subtitle, '
                          '.admin-list-markings, .admin-empty-value')
    assert doc.get_text(strip=True) == 'Apfel-Essig'


@pytest.mark.parametrize('slot', ['status', 'meta', 'subtitle', 'markings'])
@pytest.mark.parametrize('value', [0, False, -3, 'Apfel-Essig', '−2', '<Gruppe>'])
def test_real_values_are_not_treated_as_empty(semantic_app, slot, value):  # noqa: F811
    doc = render(semantic_app, "{{ list_row(primary='Name', **slots) }}", slots={slot: value})
    node = doc.select_one('.admin-list-' + slot)
    assert node is not None and node.get_text(strip=True) == str(value)


def test_composed_slots_have_explicit_presence_and_state_fallback(semantic_app):  # noqa: F811
    doc = render(semantic_app, """{{ list_row(primary='Name',
        status=blank, meta=blank, subtitle=blank, markings=blank,
        status_present=false, meta_present=false, subtitle_present=false, markings_present=false) }}
        {{ list_row(primary='State', state='active') }}
        {{ list_row(primary='Symbol', markings=symbol, markings_present=true) }}""",
        blank=Markup('<span aria-hidden="true"></span>'),
        symbol=Markup('<svg aria-label="Vegetarisch"></svg>'))
    rows = doc.select('.admin-list-row')
    assert not rows[0].select('.admin-list-status, .admin-list-meta, .admin-list-subtitle, .admin-list-markings')
    assert rows[1].select_one('.admin-list-status').get_text(strip=True) == 'Aktiv'
    assert rows[2].select_one('.admin-list-markings svg') is not None


@pytest.mark.parametrize('primary', [None, '', ' ', Markup('<span></span>')])
def test_missing_required_name_is_a_component_error(semantic_app, primary):  # noqa: F811
    with pytest.raises(SemanticError, match='primary'):
        render(semantic_app, '{{ list_row(primary=value) }}', value=primary)


def test_empty_table_cell_keeps_column_and_meaningful_missing_value(semantic_app):  # noqa: F811
    doc = render(semantic_app, '''<table><thead><tr><th>Name</th><th>Meta</th><th>Preis</th>
        </tr></thead><tbody><tr><td>Essig</td><td></td><td>{{ empty_value() }}</td></tr></tbody></table>''')
    assert len(doc.select('th')) == len(doc.select('td')) == 3
    assert doc.select('td')[1].get_text(strip=True) == ''
    assert doc.select('td')[2].get_text(strip=True) == 'Nicht erfasst'


@pytest.mark.parametrize(('show_text', 'icon_only'), list(product([False, True], repeat=2)))
@pytest.mark.parametrize('mode', [None, 'icon', 'text'])
def test_button_modes_and_legacy_mapping(semantic_app, show_text, icon_only, mode):  # noqa: F811
    options = dict(show_text=show_text, icon_only=icon_only)
    if mode is not None:
        options['mode'] = mode
    doc = render(semantic_app, "{{ icon_button('actions.edit', text='Ändern', "
                 "aria_label='Suppe bearbeiten', **options) }}", options=options)
    button = doc.button
    text_mode = mode == 'text' or mode is None and show_text
    assert bool(button.select('svg')) is not text_mode
    assert button.get_text(strip=True) == ('Ändern' if text_mode else '')
    assert ('ui-sem-control--icon-only' in button['class']) is not text_mode
    assert ('ui-sem-control--text' in button['class']) is text_mode
    assert button['data-ui-tooltip'] == button['aria-label']
    if text_mode:
        assert 'Ändern' in button['aria-label']


@pytest.mark.parametrize('mode', ['icon', 'text'])
def test_summary_and_row_actions_share_exclusive_contract(semantic_app, mode):  # noqa: F811
    doc = render(semantic_app, """<details>{{ icon_summary('actions.edit', mode=mode,
        aria_label='Suppe ändern') }}</details>
        {{ row_actions([{'key':'actions.edit', 'mode':mode, 'text':'Ändern',
            'aria_label':'Suppe bearbeiten', 'form':'editor', 'name':'intent', 'value':'save'}]) }}""",
        mode=mode)
    for node in doc.select('summary, button'):
        assert bool(node.select('svg')) == (mode == 'icon')
        assert bool(node.get_text(strip=True)) == (mode == 'text')
        assert node.get_text(strip=True) in node['aria-label']
    assert (doc.button['form'], doc.button['name'], doc.button['value']) == ('editor', 'intent', 'save')


@pytest.mark.parametrize('macro', ['icon_button', 'icon_summary'])
@pytest.mark.parametrize('mode', ['', 'both', False, 2])
def test_unknown_modes_are_errors(semantic_app, macro, mode):  # noqa: F811
    with pytest.raises(SemanticError, match='mode'):
        render(semantic_app, '{{ ' + macro + "('actions.edit', mode=mode) }}", mode=mode)


def test_blank_resolved_text_is_error(semantic_app):  # noqa: F811
    semantic_app.extensions['ui_translator'].locales['de']['actions.edit.label'] = ' '
    for macro in ['icon_button', 'icon_summary']:
        with pytest.raises(SemanticError, match='text'):
            render(semantic_app, '{{ ' + macro + "('actions.edit', mode='text') }}")


@pytest.mark.parametrize(('locale', 'close', 'purpose'), [
    ('de', 'Schliessen', 'Prüfhinweise'), ('en', 'Close', 'Review notes')])
def test_read_dialog_contract_and_escaping(semantic_app, locale, close, purpose):  # noqa: F811
    semantic_app.config['UI_LOCALE'] = locale
    doc = render(semantic_app, """{{ read_detail_trigger('review', 'ui.read_detail.review', object) }}
        {% call read_detail_dialog('review', title, object) %}<p>Vollständiger Hinweis</p>{% endcall %}""",
        object='Suppe <&>', title='Prüfung <script>bad()</script>')
    trigger = doc.select_one('[data-read-detail]')
    dialog = doc.dialog
    assert trigger['href'] == '#review' and purpose.lower() in trigger['aria-label'].lower()
    assert 'Suppe <&>' in trigger['aria-label']
    assert dialog['aria-labelledby'] == 'review-title'
    assert dialog['aria-describedby'] == 'review-context'
    assert doc.select_one('#review-title')['tabindex'] == '-1'
    assert doc.select_one('#review-context').get_text() == 'Suppe <&>'
    controls = dialog.select('a, button')
    assert len(controls) == 1 and controls[0].get_text(strip=True) == close
    assert controls[0]['href'] == '#review-trigger' and not controls[0].select('svg')
    assert not doc.select('script, details, form')


@pytest.mark.parametrize('locale', ['de', 'en'])
def test_delta2b_filter_dialog_keeps_form_and_server_chips(semantic_app, locale):  # noqa: F811
    semantic_app.config['UI_LOCALE'] = locale
    doc = render(semantic_app, """{{ filter_bar_sem('/search', id='catalog',
        search_name='text', search_value='Soup & herbs', filters=filters,
        more_filters=more, profile=profile, active=true, open=true, reset_url='/reset') }}""",
        filters=Markup('''<input type="hidden" name="scope" value="patienten">
            <label for="tag">Kategorie</label><select id="tag" name="tag">
            <option value="">Alle</option><option value="soup" selected>Suppe &amp; Brot</option></select>
            <label><input name="archived" type="checkbox" value="1" checked>Archivierte</label>'''),
        more=Markup('<label for="ingredient">Zutat</label><input id="ingredient" name="ingredient" value="&lt;Kraut&gt;">'),
        profile=Markup('<nav><a href="/profile">Patienten</a></nav>'))
    assert not doc.select('details.admin-filter-more')
    dialog = doc.select_one('dialog.admin-filter-dialog')
    assert dialog is not None and not dialog.has_attr('open')
    assert dialog.find_parent('form') is doc.form
    assert len(doc.select('form')) == 1
    assert doc.form['action'] == '/search' and doc.form['method'] == 'get'
    assert not doc.select_one('[name="text"]').find_parent('dialog')
    assert not doc.select_one('nav').find_parent('dialog')
    assert dialog.select_one('[name="scope"]')['value'] == 'patienten'
    assert dialog.select_one('[name="ingredient"]')['value'] == '<Kraut>'
    assert dialog.select_one('[name="archived"]').has_attr('checked')
    assert dialog.h2.get_text(strip=True) == 'Filter'
    assert len(dialog.select('[data-read-detail-close]')) == 1
    assert not dialog.select_one('[data-read-detail-close]').select('svg')
    assert doc.select_one('[data-semantic="view.reset"]')['href'] == '/reset'
    trigger = doc.select_one('[data-semantic="view.filter"]')
    count = doc.select_one('.admin-filter-count')
    assert not trigger.get_text(strip=True) and trigger.select_one('svg')
    assert count.get_text(strip=True) == '3' and count not in trigger.descendants
    assert count['id'] in trigger['aria-describedby'].split()
    chips = doc.select('.admin-filter-chip')
    assert [chip.get_text(strip=True) for chip in chips] == ['Suppe & Brot', 'Archivierte', '<Kraut>']
    assert all(not chip.find_parent('dialog') for chip in chips)
    remove = chips[0].a
    assert not remove.get_text(strip=True) and remove.svg
    assert 'text=Soup+%26+herbs' in remove['href'] and 'scope=patienten' in remove['href']
    assert 'tag=' in remove['href'] and 'tag=soup' not in remove['href']
    assert 'archived=1' in remove['href']
    ids = [node['id'] for node in doc.select('[id]')]
    assert len(ids) == len(set(ids))


def test_delta2b_two_read_triggers_have_unique_ids_and_canonical_nojs_return(semantic_app):  # noqa: F811
    doc = render(semantic_app, """{{ read_detail_trigger('review', 'ui.read_detail.review', 'Suppe') }}
        {{ read_detail_trigger('review', 'ui.read_detail.review', 'Suppe', trigger_id='review-second') }}
        {% call read_detail_dialog('review', 'Hinweise', 'Suppe') %}Inhalt{% endcall %}""")
    triggers = doc.select('[data-read-detail]')
    assert [node['id'] for node in triggers] == ['review-trigger', 'review-second']
    assert all(node['href'] == '#review' for node in triggers)
    assert len(doc.select('#review-trigger')) == 1
    assert doc.select_one('[data-read-detail-close]')['href'] == '#review-trigger'


@pytest.mark.parametrize('label,expected', [('Suppe bearbeiten', 'Ändern: Suppe bearbeiten'),
                                         ('Ändern: Suppe', 'Ändern: Suppe')])
def test_delta2b_text_name_contains_visible_label_once(semantic_app, label, expected):  # noqa: F811
    doc = render(semantic_app, "{{ icon_button('actions.edit', mode='text', text='Ändern', aria_label=label) }}",
                 label=label)
    assert doc.button['aria-label'] == expected
    assert doc.button.get_text(strip=True) == 'Ändern' and not doc.button.svg


def test_delta2b_server_chips_respect_successful_fields_and_select_defaults(semantic_app):  # noqa: F811
    from urllib.parse import parse_qs, urlsplit

    doc = render(semantic_app, "{{ filter_bar_sem('/search', filters=filters, profile=profile) }}",
        profile=Markup('<input type="hidden" name="scope" value="patienten">'),
        filters=Markup('''<label><input name="ignored" value="bad" disabled>Disabled</label>
            <label><input type="checkbox" name="unchecked" value="bad">Unchecked</label>
            <select name="status"><option value="active">Aktiv</option>
                <option value="archived" selected>Archiviert</option></select>
            <input type="hidden" name="keep" value="yes">
            <select name="default"><option value="first">Erstes</option></select>
            <input type="text" name="empty" value="">
            <label for="note">Text</label><input id="note" name="note" value="A &amp; B">'''))
    chips = doc.select('.admin-filter-chip')
    assert len(chips) == 2
    values = parse_qs(urlsplit(chips[0].a['href']).query, keep_blank_values=True)
    assert values == {'q': [''], 'scope': ['patienten'], 'status': ['active'],
                      'keep': ['yes'], 'default': ['first'], 'empty': [''], 'note': ['A & B']}


@pytest.mark.parametrize('populated', [False, True])
def test_post_g0d_consumers_keep_extended_footer_and_disclosure_contracts(semantic_app, populated):  # noqa: F811
    """UC-P2 additions have no equivalent in the frozen pre-G0d fixture."""
    env = semantic_app.jinja_env
    data = dict(family='cafeteria', g={}, back_url='/filtered?q=soup',
                cell={'template_proposal': populated}, form_id='course',
                course_open=populated, service_open=populated, week_settings_open=populated,
                settings_summary='Wochenvorgaben', kind_label='Suppe', option_label='Menü 1',
                course={'state': 'planned' if populated else 'unplanned'},
                override={'state': 'planned' if populated else 'unplanned'},
                recipe_page={'query': {'search': 'Suppe' if populated else ''},
                             'previous_offset': 1 if populated else None},
                body=lambda: Markup('<input name="draft" value="un saved">'))
    counts = {'form_footer': 0, 'disclosure_section': 0}
    with semantic_app.test_request_context('/'):
        macros = env.get_template('admin/_macros.html').module
        data.update(form_footer=macros.form_footer, disclosure_section=macros.disclosure_section,
                    icon_button=env.get_template('ui/_semantic.html').module.icon_button)
        for path in sorted((ROOT.parent / 'templates/admin').rglob('*.html')):
            for call in env.parse(path.read_text(encoding='utf-8')).find_all(nodes.Call):
                if not isinstance(call.node, nodes.Name) or call.node.name not in counts:
                    continue
                name = call.node.name
                if name == 'form_footer':
                    extended = any(kw.key == 'action_order' or kw.key == 'cancel_url'
                                   and isinstance(kw.value, nodes.Const) and kw.value.value is None
                                   for kw in call.kwargs)
                else:
                    extended = any(kw.key in {'details_class', 'details_attrs', 'summary_class',
                                             'summary_attrs', 'summary_key', 'summary_object'}
                                   for kw in call.kwargs)
                if not extended:
                    continue
                counts[name] += 1
                if name == 'disclosure_section':
                    call.kwargs.append(nodes.Keyword('caller', nodes.Name('body', 'load')))
                doc = BeautifulSoup(_compile_call(env, call).render(**data), 'html.parser')
                if name == 'disclosure_section':
                    assert doc.details and doc.summary
                    assert doc.select_one('input[name=draft]')['value'] == 'un saved'
                else:
                    assert doc.select('.admin-form-footer button[type=submit]')
                    cancel = doc.select_one('[data-semantic="actions.cancel"]')
                    assert bool(cancel) == (path.name == 'menu_editor.html')
                    if cancel:
                        assert cancel['href'] == '/filtered?q=soup'
                        assert len(doc.select('button')) == (1 if populated else 2)
    assert counts == {'form_footer': 4, 'disclosure_section': 10}


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('active', [False, True])
def test_all_existing_show_text_calls_render_only_text(semantic_app, tmp_path, locale, active):  # noqa: F811
    """Render real call expressions; synthetic values cover both conditional arms."""
    semantic_app.config['UI_LOCALE'] = locale
    env = semantic_app.jinja_env
    data = _action_context(True)
    data.update(
        item=SimpleNamespace(key='actions.edit', href='/target', text='Bearbeiten',
                             aria_label='Suppe bearbeiten'),
        component=SimpleNamespace(active=active, name='Suppe'), active=active,
        account=SimpleNamespace(disabled_at=active), can_mutate=True, reactivating=active,
        recipe_id='recipe-1', revision=SimpleNamespace(id=1, name='Vorlage'),
        key=SimpleNamespace(label='Testzugang'), publish_label='Veröffentlichen',
        publish_blocked=False, g={}, request=SimpleNamespace(path='/source'),
    )
    rendered = []
    with semantic_app.test_request_context('/'):
        data['icon_button'] = env.get_template('ui/_semantic.html').module.icon_button
        for path in sorted((ROOT.parent / 'templates/admin').rglob('*.html')):
            for call in env.parse(path.read_text(encoding='utf-8')).find_all(nodes.Call):
                if not isinstance(call.node, nodes.Name) or call.node.name != 'icon_button':
                    continue
                if not any(kw.key == 'show_text' and isinstance(kw.value, nodes.Const)
                           and kw.value.value is True for kw in call.kwargs):
                    continue
                doc = BeautifulSoup(_compile_call(env, call).render(**data), 'html.parser')
                control = doc.select_one('a, button')
                where = f'{path.name}:{call.lineno}'
                assert control and control.get_text(strip=True), where
                assert not control.select('svg, img'), where
                assert control.get_text(strip=True).lower() in control['aria-label'].lower(), where
                rendered.append({'source': where, 'text': control.get_text(strip=True)})
    assert len(rendered) >= 35, 'Consumer inventory unexpectedly shrank'
    (tmp_path / 'show-text-consumers.json').write_text(json.dumps(rendered, ensure_ascii=False,
                                                               indent=2), encoding='utf-8')
