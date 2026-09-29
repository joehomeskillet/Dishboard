"""DB-free presentation contracts, including failure paths and trust boundaries."""
from __future__ import annotations

import json
import hashlib
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from flask import Flask, render_template_string
from markupsafe import Markup

from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui, sem
from cafeteria.ui.i18n import Translator, load_locales, translate
from cafeteria.ui.semantics import (
    FOOD, ROOT, STATIC, SemanticError, load_registry, read_json, sprite_icons, validate_locales,
)
from cafeteria.food_symbols import food_symbol


# Written out independently of the code under test: a wrong mapping must fail here.
EXPECTED_FOOD = {
    'diet.vegetarian': ('labels', 'VEGETARIAN'), 'diet.vegan': ('labels', 'VEGAN'),
    'allergen.gluten': ('allergens', 'GLUTEN'), 'allergen.crustaceans': ('allergens', 'CRUSTACEANS'),
    'allergen.eggs': ('allergens', 'EGGS'), 'allergen.fish': ('allergens', 'FISH'),
    'allergen.peanuts': ('allergens', 'PEANUTS'), 'allergen.soy': ('allergens', 'SOY'),
    'allergen.milk': ('allergens', 'MILK'), 'allergen.nuts': ('allergens', 'NUTS'),
    'allergen.celery': ('allergens', 'CELERY'), 'allergen.mustard': ('allergens', 'MUSTARD'),
    'allergen.sesame': ('allergens', 'SESAME'), 'allergen.sulfites': ('allergens', 'SULPHITES'),
    'allergen.lupin': ('allergens', 'LUPIN'), 'allergen.molluscs': ('allergens', 'MOLLUSCS'),
}


@pytest.fixture
def semantic_app():
    app = Flask('semantic-tests', template_folder=str(ROOT.parent / 'templates'),
                static_folder=str(STATIC))
    app.config.update(TESTING=True, UI_LOCALE='de')
    register_template_filters(app)
    register_ui(app)
    return app


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize(('status', 'blocked', 'publish_label'), (
    ('empty', True, 'Veröffentlichen'),
    ('incomplete', True, 'Veröffentlichen'),
    ('review_open', True, 'Veröffentlichen'),
    ('ready', False, 'Veröffentlichen'),
    ('live', False, 'Erneut veröffentlichen'),
    ('changed', False, 'Änderungen veröffentlichen'),
))
def test_week_actions_keep_publish_labels_and_native_contracts(
    semantic_app, family, status, blocked, publish_label,
):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context('/'):
        html = render_template_string(
            "{% from 'admin/_macros.html' import page_header %}"
            "{% include 'admin/_week_controls.html' %}"
            "{% from 'admin/_week_controls.html' import overview_header with context %}"
            "{{ overview_header('Wochenplan', '') }}",
            family=family, status=status, status_label=status, publish_blocked=blocked,
            can_publish=True,
            week_value='2026-08-31', week_csrf='test-publish',
            schedule_defaults_csrf='test-defaults', week_row_version=3,
            iso_week=36, title='', date_range='', cells=[], filled_slots=0, open_checks=0,
            url_for=lambda endpoint, **kwargs: '/test/' + endpoint,
        )
    doc = BeautifulSoup(html, 'html.parser')
    trigger = doc.select_one('[data-bs-target="#week-publish-modal"]')
    submit = doc.select_one('#week-publish-form button[type="submit"]')
    nojs = doc.select_one('noscript button')
    for button in (trigger, submit, nojs):
        assert button.get('aria-label', button.get_text(strip=True)) == publish_label
        assert button.has_attr('disabled') is blocked
    assert trigger['data-bs-toggle'] == 'modal'
    assert nojs['form'] == 'week-publish-form'
    for button in (trigger, nojs):
        assert button.get('aria-describedby') == ('week-publish-guidance' if blocked else None)
    primary = doc.select('.btn-primary')
    assert len(primary) == 1
    assert primary[0].get('aria-label', primary[0].get_text(strip=True)) == (
        'Offene Punkte prüfen' if status == 'review_open' else publish_label
    )
    form = doc.select_one('#week-publish-form')
    assert form['method'] == 'post'
    assert form['action'] == f'/admin/{family}/publish'
    assert [(field['name'], field['value']) for field in form.select('input')] == [
        ('_csrf', 'test-publish'), ('week', '2026-08-31'), ('row_version', '3'),
    ]
    defaults = doc.select_one('#schedule-defaults')
    assert [(field['name'], field['value']) for field in defaults.select('input')] == [
        ('_csrf', 'test-defaults'), ('week', '2026-08-31'), ('row_version', '3'),
    ]
    assert defaults.select_one('button')['data-semantic'] == 'actions.apply'
    assert [item['aria-label'] for item in doc.select('.admin-week-more-menu .dropdown-item')] == [
        'CSV exportieren', 'Vorwoche kopieren', 'Wochenvorgaben übernehmen',
    ]


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize('status', ('ready', 'review_open'))
def test_week_actions_hide_publish_without_capability(semantic_app, family, status):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context('/'):
        html = render_template_string(
            "{% from 'admin/_macros.html' import page_header %}"
            "{% include 'admin/_week_controls.html' %}"
            "{% from 'admin/_week_controls.html' import overview_header with context %}"
            "{{ overview_header('Wochenplan', '') }}",
            family=family, status=status, status_label=status,
            publish_blocked=status == 'review_open', can_publish=False,
            week_value='2026-08-31', week_csrf='test-publish',
            schedule_defaults_csrf='test-defaults', week_row_version=3,
            iso_week=36, title='', date_range='', cells=[], filled_slots=0, open_checks=0,
            url_for=lambda endpoint, **kwargs: '/test/' + endpoint,
        )
    doc = BeautifulSoup(html, 'html.parser')
    assert doc.select_one('[data-bs-target="#week-publish-modal"]') is None
    assert doc.select_one('#week-publish-form') is None
    assert doc.select_one('noscript .admin-week-nojs-publish') is None
    assert doc.select_one('noscript button') is None
    primary = doc.select('.btn-primary')
    assert [button.get('aria-label', button.get_text(strip=True)) for button in primary] == (
        ['Offene Punkte prüfen'] if status == 'review_open' else []
    )


def test_registry_source_schema_and_frozen_resolution():
    registry = load_registry()
    source = Path(__file__).resolve().parents[2] / 'docs/design/semantic-ui-language-2026-09-20'
    seeds = json.loads((source / '05_SEMANTIC_REGISTRY.json').read_text())
    # P2c adds activate/apply/history; no aliases for different business actions.
    assert len(seeds) == 187
    assert len(registry) == 213
    for key, icon in {'recipe.original_quantities': 'scale', 'recipe.provenance': 'history'}.items():
        assert registry[key].resolved_icon == icon
        assert registry[key].icon_only_allowed
        assert registry[key].label_key == key + '.label'
        assert registry[key].tooltip_key == key + '.tooltip'
        assert registry[key].aria_key == key + '.aria'
    assert {r['semantic_key'] for r in seeds} <= registry.keys()
    assert len(read_json(ROOT / 'icon_fallbacks.json')) == 6
    available = sprite_icons()
    assert len(available) == 147
    assert FOOD == EXPECTED_FOOD
    for key, item in registry.items():
        if key in EXPECTED_FOOD:
            kind, code = EXPECTED_FOOD[key]
            assert item.resolved_icon == f'food:{kind}:{code}'
            asset = food_symbol(code, kind)
            assert asset and (STATIC / asset.filename).is_file()
        else:
            assert item.resolved_icon in available
        assert not item.icon_only_allowed or (item.tooltip_key and item.aria_key)
    assert registry['admin.user'].resolved_icon == 'user'
    
    assert registry['admin.user'].icon_only_allowed
    
    with pytest.raises(FrozenInstanceError):
        registry['actions.save'].role = 'danger'
    for row in read_json(ROOT / 'semantic_registry.json'):
        assert not {'label_de', 'label_en', 'label', 'tooltip', 'aria'} & row.keys()


@pytest.mark.parametrize('mutation,match', [
    ('duplicate', 'actions.add'), ('missing', 'actions.add'),
    ('icon', 'actions.add'), ('boolean', 'actions.add'), ('role', 'actions.add'),
])
def test_bad_registry_fails_with_key(tmp_path, mutation, match):
    rows = read_json(ROOT / 'semantic_registry.json')
    rows.sort(key=lambda row: row['key'] != 'actions.add')
    if mutation == 'duplicate':
        rows.append(rows[0])
    elif mutation == 'missing':
        del rows[0]['aria_key']
    elif mutation == 'icon':
        rows[0]['icon'] = '../untrusted'
    elif mutation == 'boolean':
        rows[0]['icon_only_allowed'] = 'yes'
    else:
        rows[0]['role'] = 'invalid'
    path = tmp_path / 'registry.json'
    path.write_text(json.dumps(rows))
    with pytest.raises(SemanticError, match=match):
        load_registry(path)


def test_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path / 'duplicate.json'
    path.write_text('{"actions.save.label":"one","actions.save.label":"two"}')
    with pytest.raises(SemanticError, match='actions.save.label'):
        read_json(path)


def test_locale_symmetry_orphans_missing_and_pseudo():
    registry, locales = load_registry(), load_locales(testing=True)
    validate_locales(registry, locales)
    assert set(locales) == {'de', 'en', 'xx'}
    assert 'xx' not in load_locales()
    for key, value in locales['de'].items():
        assert len(locales['xx'][key]) >= 1.3 * len(value)
        assert locales['xx'][key].startswith('[!! ')
    locales['en'].pop('actions.save.aria')
    with pytest.raises(SemanticError, match='actions.save.aria'):
        validate_locales(registry, locales)
    locales = load_locales()
    locales['en']['orphan.label'] = 'Orphan'
    with pytest.raises(SemanticError, match='orphan.label'):
        validate_locales(registry, locales)


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('key', ['recipe.import.row_details',
                                'print_template.reactivate.label', 'print_template.reactivate.aria',
                                'api_key.revoke.label', 'api_key.revoke.aria',
                                'api_key.revoke.confirm', 'api_key.revoke.consequence',
                                'menu.save_return.aria',
                                'recipe.pdf_open.label', 'recipe.pdf_open.aria'])
@pytest.mark.parametrize('mutation', ['missing', 'empty', 'unknown'])
def test_context_message_allowlist_stays_strict(locale, key, mutation):
    locales = load_locales()
    if mutation == 'missing':
        locales[locale].pop(key)
        message = 'translation missing'
    elif mutation == 'empty':
        locales[locale][key] = ' '
        message = 'empty or invalid translation'
    else:
        locales[locale][key + '.extra'] = 'Not allowed'
        message = 'orphan translation'
    with pytest.raises(SemanticError, match=message):
        validate_locales(load_registry(), locales)


@pytest.mark.parametrize('locale,label,row,aria', [
    ('de', 'Reaktivieren', 'Details für Zeile 7', 'Druckvorlage &lt;b&gt;&amp; reaktivieren'),
    ('en', 'Reactivate', 'Details for row 7', 'Reactivate print template &lt;b&gt;&amp;'),
])
def test_import_and_print_context_messages_translate_and_escape(locale, label, row, aria):
    translator = Translator(load_locales(testing=True))
    assert translator.translate('print_template.reactivate.label', locale) == label
    assert translator.translate('recipe.import.row_details', locale, row=7) == row
    assert translator.translate('print_template.reactivate.aria', locale, name=Markup('<b>&')) == aria
    for key in ('recipe.import.row_details', 'print_template.reactivate.aria'):
        with pytest.raises(SemanticError, match='missing parameters'):
            translator.translate(key, locale)


def test_fallback_missing_markers_and_warning_deduplication(caplog):
    locales = {'de': {'known': 'Speichern'}, 'en': {}}
    production = Translator(locales, production=True)
    assert production.translate('known', 'en') == 'Speichern'
    assert production.translate('known', 'en') == 'Speichern'
    assert len(caplog.records) == 1
    assert production.translate('unknown', 'en') == '⟦unknown⟧'
    development = Translator(locales)
    assert development.translate('known', 'en') == '⟦known⟧'
    assert 'Missing UI translation known in en' in caplog.text


def test_parameters_escape_even_markup_and_named_fields_reorder():
    resolver = Translator({'de': {'message': '{first} vor {second}'},
                           'en': {'message': '{second} after {first}'}})
    assert resolver.translate('message', 'en', first='A', second='B') == 'B after A'
    result = resolver.translate('message', 'de', first=Markup('<script>bad</script>'), second='"&')
    assert '<script>' not in result and '&lt;script&gt;' in result
    assert '&#34;&amp;' in result
    with pytest.raises(SemanticError, match='message'):
        resolver.translate('message', 'en', first='A')
    with pytest.raises(SemanticError, match='unsupported UI_LOCALE'):
        resolver.translate('message', '../../en')


def test_production_keeps_the_page_when_a_parameter_is_missing(caplog):
    production = Translator({'de': {'message': '{first} vor {second}'}}, production=True)
    result = production.translate('message', 'de', first=Markup('<b>A</b>'))
    assert result == '&lt;b&gt;A&lt;/b&gt; vor {second}'
    assert "Missing UI translation parameters ['second'] for message" in caplog.text


def test_globals_allowlist_and_icon_only_policy(semantic_app):
    with semantic_app.test_request_context():
        assert translate('actions.save.label') == 'Speichern'
        assert translate('actions.save.label', locale='en') == 'Save'
        assert sem('allergen.milk').resolved_icon == 'food:allergens:MILK'
        with pytest.raises(SemanticError, match='unknown semantic key'):
            sem('../../secrets')
        for key in ('actions.save', 'actions.delete'):
            html = render_template_string(
                "{% from 'ui/_semantic.html' import icon_button %}"
                "{{ icon_button(key, consequence_key='ui.request_failed') }}", key=key)
            assert 'ui-sem-control--icon-only' in html
        html = render_template_string("{% from 'ui/_semantic.html' import icon_button %}{{ icon_button('actions.edit', icon_only=true) }}")
        assert 'data-ui-tooltip="Bearbeiten"' in html and 'aria-label="Bearbeiten"' in html
        with pytest.raises(SemanticError, match='consequence_key'):
            render_template_string("{% from 'ui/_semantic.html' import icon_button %}{{ icon_button('actions.delete') }}")
    app = Flask('unsupported')
    app.config['UI_LOCALE'] = 'fr'
    with pytest.raises(SemanticError, match='fr'):
        register_ui(app)


def test_app_start_rejects_pseudo_outside_testing():
    app = Flask('production-pseudo')
    app.config.update(APP_ENV='production', UI_LOCALE='xx')
    with pytest.raises(SemanticError, match='xx'):
        register_ui(app)


@pytest.mark.parametrize('call', [
    "confirm_dialog('actions.delete', confirm_key='actions.delete')",
    "confirm_dialog('actions.delete', none, 'actions.delete')",
    "confirm_dialog('actions.confirm', '', 'actions.delete')",
])
def test_danger_confirmation_requires_consequence_before_render(semantic_app, call):
    with semantic_app.test_request_context(), pytest.raises(SemanticError, match='consequence_key'):
        render_template_string("{% from 'ui/_semantic.html' import confirm_dialog %}{{ " + call + " }}")


def test_footer_action_levels_keep_form_contract(semantic_app):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        html = render_template_string('''
            {% from 'admin/_macros.html' import form_footer %}
            {% from 'ui/_semantic.html' import icon_button %}
            {{ form_footer({'label': 'Speichern', 'name': 'intent', 'value': 'save', 'form': 'editor',
                'formaction': '/save', 'formmethod': 'post', 'formenctype': 'multipart/form-data',
                'formtarget': 'result', 'formnovalidate': true},
                '/cancel', rare=icon_button('actions.edit', href='#edit'),
                secondary=[{'label': 'Vorschau', 'href': '#preview'}],
                danger=icon_button('actions.delete', consequence_key='ui.request_failed')) }}
        ''')
    document = BeautifulSoup(html, 'html.parser')
    primary = document.select('.btn-primary')
    assert len(primary) == 1
    assert (primary[0]['name'], primary[0]['value'], primary[0]['form']) == ('intent', 'save', 'editor')
    assert {key: primary[0][key] for key in ('formaction', 'formmethod', 'formenctype', 'formtarget')} == {
        'formaction': '/save', 'formmethod': 'post', 'formenctype': 'multipart/form-data', 'formtarget': 'result'}
    assert primary[0].has_attr('formnovalidate')
    for control in document.select('.admin-form-main .btn'):
        assert control['aria-label']
        assert control['data-ui-tooltip'] == control['aria-label']
        assert not control.get_text(strip=True)
    assert primary[0].select_one('use')['href'].endswith('#tabler-device-floppy')
    assert document.select_one('.admin-form-main a[href="#preview"]')
    assert document.select_one('.admin-form-main a[href="/cancel"]')
    rare = document.select_one('details.admin-form-rare')
    assert not rare.has_attr('open')
    assert rare.select_one('summary.btn-ghost')
    assert rare.select_one('a[href="#edit"]')
    danger = document.select_one('.admin-form-danger')
    assert danger.select_one('.btn-danger svg')
    assert danger.select_one('.btn-danger')['aria-label'] == 'Löschen'
    assert danger.select_one('.btn-danger span') is None
    assert danger.select_one('.ui-sem-consequence').get_text(strip=True)


@pytest.mark.parametrize('text', [None, '', '  \n '])
@pytest.mark.parametrize('mode', ['inline', 'tooltip', 'dialog'])
def test_c3_empty_hint_has_no_icon_or_spacing(semantic_app, text, mode):
    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from 'admin/_macros.html' import hint %}{{ hint(text, 'help', mode=mode) }}",
            text=text, mode=mode)
    assert not html.strip()


def test_c3_nonempty_hint_keeps_help_and_relationship(semantic_app):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from 'admin/_macros.html' import hint %}{{ hint('CSV ändert keinen Status.', 'help') }}")
    document = BeautifulSoup(html, 'html.parser')
    assert document.select_one('summary')['aria-describedby'] == 'help'
    assert document.select_one('#help').get_text() == 'CSV ändert keinen Status.'

def test_c3_legacy_actions_use_canonical_icons_and_keep_secondary_weight(semantic_app):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        html = render_template_string('''{% from 'admin/_macros.html' import actions %}
            {{ actions(primary='Anlegen', secondary=[
                {'label':'Entwurf sichern', 'icon':'device-floppy', 'type':'submit', 'name':'intent', 'value':'draft', 'formnovalidate':1},
                {'label':'Record bearbeiten', 'icon':'pencil', 'href':'/edit', 'disabled':true}]) }}''')
    document = BeautifulSoup(html, 'html.parser')
    assert document.select_one('.btn-primary')['data-semantic'] == 'actions.add'
    save = document.select_one('[name="intent"]')
    assert save['data-semantic'] == 'actions.save' and save['value'] == 'draft'
    assert save.has_attr('formnovalidate')
    assert 'btn-primary' not in save['class']
    edit = document.select_one('a[href="/edit"]')
    assert edit['data-semantic'] == 'actions.edit'
    assert edit['aria-disabled'] == 'true' and edit['tabindex'] == '-1'
    assert not document.get_text(strip=True)


@pytest.mark.parametrize('count', [0, 2])
def test_c3_shared_filter_trigger_is_named_icon_with_optional_count(semantic_app, count):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from 'ui/_semantic.html' import filter_trigger %}{{ filter_trigger('test-filter', count, true) }}",
            count=count)
    summary = BeautifulSoup(html, 'html.parser').summary
    assert summary['aria-label'] == 'Filter'
    assert summary['data-ui-tooltip'] == 'Filter'
    assert summary.select_one('use')['href'].endswith('#tabler-filter')
    assert summary.select_one('.admin-filter-count').has_attr('hidden') == (count == 0)
    assert summary.has_attr('aria-describedby') == bool(count)
    assert summary.get_text(strip=True) == str(count)


def test_registry_icons_in_sprite():
    from cafeteria.ui.semantics import load_registry, sprite_icons
    
    registry = load_registry()
    sprite = sprite_icons()
    
    missing = []
    for item in registry.values():
        if not item.resolved_icon.startswith('food:'):
            if item.resolved_icon not in sprite:
                missing.append(item.resolved_icon)
            
    assert not missing, f"Missing icons in sprite: {missing}"


def test_c3_categories_and_overflow_have_distinct_icons():
    registry = load_registry()
    assert registry['navigation.categories'].resolved_icon == 'grid-dots'
    assert {item.key for item in registry.values() if item.resolved_icon == 'dots'} == {'actions.more'}


def test_row_actions_keep_one_direct_action_and_native_form_fields(semantic_app):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        html = render_template_string('''{% from 'ui/_semantic.html' import row_actions %}
            {{ row_actions([{'key': 'actions.edit', 'href': '#edit', 'icon_only': true},
                {'key': 'actions.copy', 'name': 'intent', 'value': 'copy', 'form': 'editor'},
                {'key': 'actions.delete', 'name': 'intent', 'value': 'delete', 'form': 'editor',
                 'consequence_key': 'ui.request_failed'}]) }}''')
    document = BeautifulSoup(html, 'html.parser')
    assert len(document.select('.admin-row-actions > a')) == 1
    assert not document.details.has_attr('open')
    assert document.summary.get_text(strip=True) == ''
    assert document.summary['aria-label'] == 'Weitere Aktionen'
    buttons = document.select('details button')
    assert [(b['name'], b['value'], b['form']) for b in buttons] == [
        ('intent', 'copy', 'editor'), ('intent', 'delete', 'editor')]
    assert buttons[1].get_text(strip=True) == 'Löschen'
    assert document.select_one('.ui-sem-consequence')


def test_statusbar_without_href_preserves_markup(semantic_app):
    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from 'admin/_macros.html' import page_header %}"
            "{{ page_header('Status', status_items=[{'label': 'Prüfstand', "
            "'value': 'Offen', 'variant': 'warning', 'detail': '2 Angaben fehlen'}]) }}"
        )
    statusbar = html[html.index('<dl '):html.index('</dl>') + len('</dl>')]
    print('STATUSBAR_NO_HREF=' + repr(statusbar))
    assert statusbar == (
        '<dl class="admin-statusbar" aria-label="Status">'
        '<div class="admin-statusbar-item admin-statusbar-item--warning">\n'
        '        <dt class="admin-statusbar-label">Prüfstand</dt>\n'
        '        <dd class="admin-statusbar-value">\n'
        '          <span class="admin-statusbar-value-text">Offen</span>'
        '<span class="admin-statusbar-detail">2 Angaben fehlen</span></dd>\n'
        '      </div></dl>'
    )


@pytest.mark.parametrize('locale', ['de', 'en'])
def test_admin_shell_locale_and_single_semantic_stylesheet(semantic_app, locale):
    from bs4 import BeautifulSoup

    semantic_app.config['UI_LOCALE'] = locale
    with semantic_app.test_request_context():
        html = render_template_string(
            "{% extends 'admin/base_tabler.html' %}{% block sidebar %}{% endblock %}"
            "{% block content %}Admin{% endblock %}"
        )
    document = BeautifulSoup(html, 'html.parser')
    assert document.html['lang'] == locale
    styles = [node['href'] for node in document.select('link[rel="stylesheet"]')]
    assert styles.count('/static/ui-semantic.css') == 1
    assert styles.index('/static/ui-semantic.css') == styles.index('/static/admin-tabler.css') + 1
    assert styles.index('/static/admin-nav.css') == styles.index('/static/ui-semantic.css') + 1


@pytest.mark.parametrize('locale,options,more', [
    ('de', 'Weitere Optionen', 'Weitere Aktionen'),
    ('en', 'More options', 'More actions'),
])
def test_disclosure_project_keys_and_shared_labels(semantic_app, locale, options, more):
    from bs4 import BeautifulSoup

    semantic_app.config['UI_LOCALE'] = locale
    with semantic_app.test_request_context():
        for key in ('ui.disclosure.details', 'ui.disclosure.more_options'):
            item = sem(key)
            assert item.resolved_icon == 'chevron-right'
            assert not item.icon_only_allowed
            for suffix in ('label', 'aria', 'tooltip'):
                assert '⟦' not in translate(getattr(item, suffix + '_key'))
        html = render_template_string('''
            {% from 'admin/_macros.html' import disclosure_section, list_row %}
            {% call disclosure_section(id='default') %}Optional{% endcall %}
            {% call disclosure_section(title=t(sem('ui.disclosure.details').label_key), id='details', has_error=true) %}Error{% endcall %}
            {% call disclosure_section(title='Custom', id='custom', has_content=true) %}Value{% endcall %}
            {{ list_row('Name', 'Subtitle', 'active', {'label': 'Edit', 'href': '#edit'}, more_actions='Archive') }}
        ''')
    document = BeautifulSoup(html, 'html.parser')
    assert document.select_one('#default summary').get_text(strip=True) == options
    assert not document.select_one('#default').has_attr('open')
    assert document.select_one('#details summary').get_text(strip=True) == 'Details'
    assert document.select_one('#details').has_attr('open')
    assert document.select_one('#custom summary').get_text(strip=True).startswith('Custom')
    assert document.select_one('#custom').has_attr('open')
    overflow = document.select_one('.admin-compact-actions summary')
    assert overflow['aria-label'] == more
    assert overflow['data-ui-tooltip'] == more
    assert overflow.get_text(strip=True) == ''
    assert overflow.select_one('svg use') is not None


@pytest.mark.parametrize('mode', ['tooltip', 'inline', 'dialog'])
def test_hint_escapes_text_and_uses_caller_owned_description_id(semantic_app, mode):
    from bs4 import BeautifulSoup

    text = '<img src=x onerror=alert(1)>'
    with semantic_app.test_request_context():
        html = render_template_string("{% from 'admin/_macros.html' import hint %}{{ hint(text, 'help-name', mode) }}",
                                      text=text, mode=mode)
    document = BeautifulSoup(html, 'html.parser')
    assert not document.select('img, script')
    assert document.select_one('#help-name').get_text() == text
    if mode != 'inline':
        assert document.summary['aria-describedby'] == 'help-name'
        assert document.summary['title'] == text


def test_p2b_slots_escape_details_and_preserve_zero_and_sort_states(semantic_app):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        html = render_template_string('''
            {% from 'admin/_macros.html' import label, list_row, sort_header %}
            {{ label('Warning', 'danger', detail=detail) }}
            {{ list_row(primary=0, secondary=detail, meta=0) }}
            <table><tr>{{ sort_header('Name', 'name', 'other', 'asc', '#name') }}
            {{ sort_header('Date', 'date', 'date', 'desc', '#date') }}</tr></table>
        ''', detail='<img src=x onerror=alert(1)>')
    document = BeautifulSoup(html, 'html.parser')
    assert not document.select('img, script')
    assert document.select_one('.admin-label')['title'] == '<img src=x onerror=alert(1)>'
    assert document.select_one('.admin-list-name strong').text == '0'
    assert document.select_one('.admin-list-meta').text == '0'
    assert [n['aria-sort'] for n in document.select('th')] == ['none', 'descending']


@pytest.mark.parametrize('locale', ['de', 'en'])
def test_p2b_action_labels_are_short_and_registry_is_single_source(locale):
    messages = load_locales()[locale]
    for key, entry in load_registry().items():
        if key.startswith(('actions.', 'view.')) or key in {'admin.settings', 'ui.templates_back'}:
            label = messages[entry.label_key]
            assert len(label) <= 18 and len(label.split()) <= 2, (key, label)


def test_p2b_legacy_icon_link_and_status_mapping_contract(semantic_app):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        html = render_template_string('''{% from 'admin/_macros.html' import icon_link, status_badge %}
            {{ icon_link('#edit', 'Bearbeiten') }}
            {{ status_badge('active', mapping={'active': ('Konflikt', 'danger')}) }}''')
    document = BeautifulSoup(html, 'html.parser')
    assert document.select_one('use')['href'].endswith('#tabler-' + load_registry()['actions.edit'].resolved_icon)
    assert document.a['title'] == document.a['aria-label'] == 'Bearbeiten'
    assert document.select_one('.admin-status--danger').get_text(strip=True) == 'Konflikt'


# Unchanged renderers retain byte snapshots; WP2c composites use DOM contracts below.
# Hash raw UTF-8 HTML, including whitespace; no normalized DOM comparison.
@pytest.mark.parametrize('template,macro,call,digest', [
    ('ui/_semantic.html', 'icon_button',
     "icon_button('actions.edit', href='/edit', icon_only=true, id='edit')",
     '4684e5173caa81cddea3c7c9f7eef8e3e9969166ae336768e872a86ee8396170'),
    ('admin/_macros.html', 'field',
     "field('q', 'Suche', 'Soup', type='search', hint='Help', error='Error')",
     '9bbf6ded90cc791728d0add549697446ca1ac979266596a6ba2d0afa30d4d84f'),
])
def test_p2c_legacy_bytes(semantic_app, template, macro, call, digest):
    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from '" + template + "' import " + macro + ' %}{{ ' + call + ' }}')
    assert hashlib.sha256(html.encode()).hexdigest() == digest


@pytest.mark.parametrize('locale,expected', [('de', 'Broccoli bearbeiten'), ('en', 'Edit Broccoli')])
@pytest.mark.parametrize('href', [None, '/edit'])
def test_icon_first_name_precedence_and_object_locale(semantic_app, locale, expected, href):
    semantic_app.config['UI_LOCALE'] = locale
    options = {'href': href, 'object': 'Broccoli', 'text': 'Custom label'}
    control = _p2c_action(semantic_app, **options).select_one('.ui-sem-control')
    assert control['aria-label'] == control['data-ui-tooltip'] == expected
    explicit = _p2c_action(semantic_app, **options, aria_label='Explicit').select_one('.ui-sem-control')
    assert explicit['aria-label'] == explicit['data-ui-tooltip'] == 'Explicit'
    text_only = _p2c_action(semantic_app, text='A longer contextual action name').button
    assert text_only['aria-label'] == text_only['data-ui-tooltip'] == 'A longer contextual action name'
    assert text_only.get_text(strip=True) == ''
    for node in (control, explicit, text_only):
        assert 'title' not in node.attrs
        assert node.svg['aria-hidden'] == 'true'
        assert 'ui-sem-control--icon-only' in node['class']


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('key', ['actions.edit', 'actions.more', 'data.revision'])
def test_icon_first_object_is_text_even_for_markup(semantic_app, locale, key):
    semantic_app.config['UI_LOCALE'] = locale
    hostile = Markup('\"<img src=x onerror=alert(1)>&')
    doc = _p2c_action(semantic_app, key, object=hostile)
    assert str(hostile) in doc.button['aria-label']
    assert doc.button['data-ui-tooltip'] == doc.button['aria-label']
    assert not doc.select('img, script')


@pytest.mark.parametrize('options', [{'object': ''}, {'object': 42}, {'text': 42}, {'icon_only': 'false'}])
def test_icon_first_invalid_names_and_switches(semantic_app, options):
    with pytest.raises(SemanticError):
        _p2c_action(semantic_app, **options)


@pytest.mark.parametrize('key', ['actions.save', 'actions.edit', 'actions.delete'])
def test_icon_first_all_roles_and_explicit_text_exception(semantic_app, key):
    options = {'consequence_key': 'ui.request_failed'}
    control = _p2c_action(semantic_app, key, **options).button
    assert control.span is None
    assert control['aria-label'] == load_locales()['de'][key + '.aria']
    exception = _p2c_action(semantic_app, key, show_text=True, **options).button
    assert exception.span.text == load_locales()['de'][key + '.label']
    assert exception.span.text in exception['aria-label']
    assert 'ui-sem-control--icon-only' not in exception['class']


def test_icon_first_menu_empty_and_confirmation_text(semantic_app):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        empty = render_template_string("{% from 'ui/_semantic.html' import action_menu %}{{ action_menu([]) }}")
        html = render_template_string("{% from 'ui/_semantic.html' import confirm_dialog %}"
                                      "{{ confirm_dialog('actions.delete', 'ui.request_failed', 'actions.delete') }}")
    assert not empty.strip()
    dialog = BeautifulSoup(html, 'html.parser').dialog
    assert [button.get_text(strip=True) for button in dialog.select('button')] == ['Löschen', 'Abbrechen']
    assert dialog.select_one('form')['method'] == 'dialog'


def test_icon_first_distinct_action_meanings():
    registry = load_registry()
    expected = {'save': 'device-floppy', 'check': 'list-check', 'publish': 'send',
                'confirm': 'check', 'open': 'arrow-right', 'more': 'dots',
                'import': 'upload', 'export': 'download', 'next': 'chevron-right'}
    for action, icon in expected.items():
        assert registry['actions.' + action].resolved_icon == icon
    assert len({registry['actions.' + key].resolved_icon for key in ('save', 'check', 'publish', 'confirm')}) == 4


def _p2c_action(app, key='actions.edit', **kwargs):
    from bs4 import BeautifulSoup

    with app.test_request_context():
        html = render_template_string(
            "{% from 'ui/_semantic.html' import icon_button %}{{ icon_button(key, **options) }}",
            key=key, options=kwargs)
    return BeautifulSoup(html, 'html.parser')


def test_p2c_context_text_escape_and_symbol(semantic_app):
    hostile = '\"<>&'
    doc = _p2c_action(semantic_app, text=hostile, aria_label=hostile + ' Kontext',
                      title=hostile, **{'class': 'dropdown-item'})
    assert doc.button.span is None
    assert doc.button['aria-label'] == hostile + ' Kontext'
    assert doc.button['data-ui-tooltip'] == hostile
    assert set(doc.button['class']) >= {'btn', 'ui-sem-control', 'dropdown-item'}
    assert doc.select_one('use')['href'].endswith('#tabler-edit')
    assert not doc.select('script, img')
    icon = _p2c_action(semantic_app, icon_only=True, aria_label='Vorlage X bearbeiten')
    assert icon.button['data-ui-tooltip'] == icon.button['aria-label'] == 'Vorlage X bearbeiten'
    assert icon.button.span is None
    custom = _p2c_action(semantic_app, icon_only=True, aria_label=hostile, title='Eigener Tooltip')
    assert custom.button['aria-label'] == hostile
    assert custom.button['data-ui-tooltip'] == 'Eigener Tooltip'


@pytest.mark.parametrize('key,emphasis,expected', [
    ('actions.add', None, 'btn-primary'), ('actions.add', 'secondary', None),
    ('actions.edit', 'primary', 'btn-primary'), ('actions.edit', 'secondary', None),
    ('actions.edit', 'danger', 'btn-danger'), ('actions.delete', 'danger', 'btn-danger'),
    ('actions.delete', None, 'btn-danger'),
])
def test_p2c_emphasis(semantic_app, key, emphasis, expected):
    doc = _p2c_action(semantic_app, key, emphasis=emphasis, consequence_key='ui.request_failed')
    assert set(doc.button['class']) & {'btn-primary', 'btn-danger'} == ({expected} if expected else set())


@pytest.mark.parametrize('options,match', [
    ({'emphasis': 'quiet'}, 'invalid emphasis'),
    ({'key': 'actions.delete', 'emphasis': 'secondary', 'consequence_key': 'ui.request_failed'}, 'downgraded'),
    ({'key': 'actions.delete', 'emphasis': 'primary', 'consequence_key': 'ui.request_failed'}, 'downgraded'),
    ({'show_text': 'true'}, 'boolean'),
    ({'emphasis': 'danger'}, 'consequence_key'),
    ({'emphasis': 'danger', 'icon_only': True}, 'consequence_key'),
    ({'text': 'one two three', 'show_text': True}, 'text must'),
    ({'text': 'x' * 19, 'show_text': True}, 'text must'), ({'text': ''}, 'text must'),
    ({'aria_label': ''}, 'nonempty'), ({'title': ''}, 'nonempty'),
    ({'attrs': []}, 'mapping'), ({'attrs': {'disabled': 'false'}}, 'boolean'),
])
def test_p2c_invalid_contract_fails(semantic_app, options, match):
    with pytest.raises(SemanticError, match=match):
        _p2c_action(semantic_app, **options)


@pytest.mark.parametrize('locale,key,text,aria_label,visible', [
    ('de', 'actions.edit', None, 'Unrelated', 'Bearbeiten'),
    ('en', 'actions.edit', None, 'Vorlage X bearbeiten', 'Edit'),
    ('en', 'actions.activate', None, 'Vorlage X aktivieren', 'Activate'),
    ('en', 'actions.apply', None, 'Vorlage X übernehmen', 'Apply'),
    ('de', 'actions.edit', 'Edit', 'Vorlage X bearbeiten', 'Edit'),
    ('en', 'actions.edit', None, '\"<img src=x>&', 'Edit'),
])
@pytest.mark.parametrize('href', [None, '/edit'])
def test_p2d_explicit_context_name_has_precedence(semantic_app, locale, key, text, aria_label, visible, href):
    semantic_app.config['UI_LOCALE'] = locale
    doc = _p2c_action(semantic_app, key, text=text, aria_label=aria_label, href=href)
    control = doc.select_one('.ui-sem-control')
    assert control.span is None
    assert visible == (text or load_locales()[locale][key + '.label'])
    assert control['aria-label'] == control['data-ui-tooltip'] == aria_label
    assert not doc.select('img, script')


@pytest.mark.parametrize('icon_only', [False, True])
@pytest.mark.parametrize('title', [None, 'Eigener Tooltip'])
def test_p2d_composed_name_respects_icon_only_and_explicit_title(semantic_app, icon_only, title):
    semantic_app.config['UI_LOCALE'] = 'en'
    doc = _p2c_action(semantic_app, aria_label='Vorlage X bearbeiten', icon_only=icon_only, title=title)
    expected = 'Vorlage X bearbeiten'
    assert doc.button['aria-label'] == expected
    assert doc.button['data-ui-tooltip'] == (title if title is not None else expected)
    assert doc.button.span is None
    assert 'ui-sem-control--icon-only' in doc.button['class']


@pytest.mark.parametrize('aria_label', [None, 'Vorlage X BEARBEITEN'])
def test_p2d_matching_or_absent_name_keeps_exact_markup(semantic_app, aria_label):
    with semantic_app.test_request_context():
        template = "{% from 'ui/_semantic.html' import icon_button %}{{ icon_button('actions.edit', **options) }}"
        baseline = render_template_string(template, options={})
        actual = render_template_string(template, options={'aria_label': aria_label})
    expected = baseline if aria_label is None else baseline.replace(
        'Bearbeiten"', 'Vorlage X BEARBEITEN"')
    assert actual == expected


@pytest.mark.parametrize('attribute', [
    'onclick', 'style', 'href', 'type', 'name', 'value', 'class', 'aria-label',
    'aria-live', 'data-', 'data-X', 'data-x_y', 'data-x\n', 'data-x" onclick', 42,
])
def test_p2c_attribute_allowlist_rejects(semantic_app, attribute):
    with pytest.raises(SemanticError, match='attribute'):
        _p2c_action(semantic_app, attrs={attribute: 'value'})


def test_p2c_attributes_escape_boolean_and_native_submission(semantic_app):
    attrs = {'data-confirm': '\"<>&', 'data-x-9': 'x', 'aria-describedby': 'help',
             'aria-controls': 'panel', 'aria-expanded': False, 'aria-current': 'page',
             'formaction': '/apply?x=1&y=2', 'formmethod': 'post',
             'formnovalidate': True, 'disabled': True, 'hidden': False, 'tabindex': -1}
    doc = _p2c_action(semantic_app, name='intent', value='apply', form='week', attrs=attrs)
    for key, value in attrs.items():
        if key == 'hidden':
            assert key not in doc.button.attrs
        else:
            assert doc.button[key] == ('' if value is True else 'false' if value is False else str(value))
    assert (doc.button['name'], doc.button['value'], doc.button['form']) == ('intent', 'apply', 'week')
    assert set(doc.button.attrs) == set(attrs) - {'hidden'} | {'class', 'data-semantic', 'data-ui-tooltip', 'aria-label', 'type', 'name', 'value', 'form'}
    assert 'disabled' not in _p2c_action(semantic_app, attrs={'disabled': False}).button.attrs
    assert _p2c_action(semantic_app, attrs={'hidden': True}).button['hidden'] == ''


@pytest.mark.parametrize('rel', [None, '', 'noreferrer', 'noopener', 'noreferrer noopener'])
def test_p2c_blank_target_keeps_rel_and_enforces_noopener(semantic_app, rel):
    attrs = {'target': '_blank'}
    if rel is not None:
        attrs['rel'] = rel
    doc = _p2c_action(semantic_app, href='/docs', attrs=attrs)
    assert doc.a['target'] == '_blank'
    assert doc.a['rel'].count('noopener') == 1
    assert set((rel or '').split()) <= set(doc.a['rel'])


@pytest.mark.parametrize('macro', ['row_actions', 'action_menu'])
def test_p2c_wrappers_forward_context_and_native_attrs(semantic_app, macro):
    from bs4 import BeautifulSoup

    item = {'key': 'actions.edit', 'text': 'Ändern', 'aria_label': 'Ändern Vorlage X',
            'title': 'Vorlage X ändern', 'class': 'dropdown-item', 'emphasis': 'secondary',
            'attrs': {'data-confirm': 'Weiter?', 'formaction': '/edit', 'formnovalidate': True},
            'name': 'intent', 'value': 'edit', 'form': 'editor', 'id': 'context', 'icon_only': True}
    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from 'ui/_semantic.html' import " + macro + ' %}{{ ' + macro + '(items) }}',
            items=[item, dict(item, id='second', icon_only=False)])
    doc = BeautifulSoup(html, 'html.parser')
    for control in doc.select('button'):
        assert control['aria-label'] == item['aria_label']
        assert control['data-ui-tooltip'] == item['title']
        assert 'dropdown-item' in control['class'] and 'btn-primary' not in control['class']
        assert control['data-confirm'] == 'Weiter?'
        assert control['formaction'] == '/edit' and control['formnovalidate'] == ''
        assert (control['name'], control['value'], control['form']) == ('intent', 'edit', 'editor')
    assert (doc.select_one('#context').span is None) == (macro == 'row_actions')
    assert doc.select_one('#second').span.text == 'Ändern'
    assert not doc.details.has_attr('open')
    assert len(doc.select('.admin-row-actions > button')) == (1 if macro == 'row_actions' else 0)


@pytest.mark.parametrize('macro,template', [('filter_bar_sem', 'ui/_semantic.html'), ('filter_bar', 'admin/_macros.html')])
@pytest.mark.parametrize('opened', [False, True])
def test_p2c_filter_contract(semantic_app, macro, template, opened):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from '" + template + "' import " + macro + ' %}{{ ' + macro +
            "('/search', search_name='text', search_value=value, maxlength=200, describedby='search-help', "
            "loading=loading, more_filters='Extra', open=opened) }}", value='\"<>&', loading='\"<>&', opened=opened)
    doc = BeautifulSoup(html, 'html.parser')
    assert doc.input['name'] == 'text' and doc.input['value'] == '\"<>&'
    assert doc.input['maxlength'] == '200' and doc.input['aria-describedby'] == 'search-help'
    assert doc.form['data-loading'] == '\"<>&'
    assert doc.form['action'] == '/search' and doc.form['method'] == 'get'
    assert doc.details.has_attr('open') == opened


@pytest.mark.parametrize('locale', ['de', 'en'])
def test_wp2c_single_filter_entry_chips_and_context(semantic_app, locale):
    from bs4 import BeautifulSoup

    semantic_app.config['UI_LOCALE'] = locale
    with semantic_app.test_request_context():
        html = render_template_string('''{% from 'ui/_semantic.html' import filter_bar_sem %}
            {{ filter_bar_sem('/search', search_name='text', search_value='Soup',
                filters='<input name="archived" value="1">'|safe,
                more_filters='<input name="category" value="soup">'|safe,
                profile='<nav>Patienten</nav>'|safe, reset_url='/reset',
                active_filters=[{'label': 'Archiv', 'href': '/search?text=Soup&category=soup'},
                                {'label': 'Suppe', 'href': '/search?text=Soup&archived=1'}]) }}''')
        empty = render_template_string("{% from 'ui/_semantic.html' import filter_bar_sem %}{{ filter_bar_sem('/search', reset_url='/reset') }}")
    doc = BeautifulSoup(html, 'html.parser')
    trigger = doc.select_one('[data-semantic="view.filter"]')
    assert len(doc.select('[data-semantic="view.filter"]')) == 1
    assert trigger.get_text(strip=True) == '2'
    assert trigger.select_one('use')['href'].endswith('#tabler-filter')
    assert len(doc.select('.admin-filter-chips a')) == 2
    assert doc.select_one('[data-semantic="view.reset"]')['href'] == '/reset'
    assert doc.select_one('.admin-filter-profile').get_text(strip=True) == 'Patienten'
    assert doc.select_one('.admin-filter-profile').find_parent('details') is None
    assert doc.select_one('input[name="text"]')['value'] == 'Soup'
    assert doc.select_one('.admin-filter-slots input[name="archived"]')['value'] == '1'
    for control in doc.select('[data-semantic="view.search"], [data-semantic="view.reset"], [data-semantic="actions.apply"]'):
        assert not control.get_text(strip=True)
    clean = BeautifulSoup(empty, 'html.parser')
    assert not clean.select('.admin-filter-more, .admin-filter-chips, [data-semantic="view.reset"]')


@pytest.mark.parametrize('locale,more_name', [('de', 'Weitere Aktionen für Broccoli'), ('en', 'More actions for Broccoli')])
def test_wp2c_row_budget_and_object_forwarding(semantic_app, locale, more_name):
    from bs4 import BeautifulSoup

    semantic_app.config['UI_LOCALE'] = locale
    with semantic_app.test_request_context():
        html = render_template_string('''{% from 'ui/_semantic.html' import row_actions %}
            {{ row_actions([{'key':'actions.edit','href':'/edit'},
                            {'key':'actions.copy','name':'intent','value':'copy','form':'editor'},
                            {'key':'actions.history','href':'/history'}], object='Broccoli') }}''')
        empty = render_template_string('''{% from 'ui/_semantic.html' import row_actions, more_actions %}
            {{ row_actions([]) }}{{ more_actions([]) }}''')
    doc = BeautifulSoup(html, 'html.parser')
    assert len(doc.select('.admin-row-actions > a')) == 1
    assert len(doc.select('.ui-sem-action-items > :is(a, button)')) == 2
    assert doc.summary['aria-label'] == more_name
    assert doc.summary.get_text(strip=True) == ''
    assert doc.summary.select_one('use')['href'].endswith('#tabler-dots')
    assert all('Broccoli' in node['aria-label'] for node in doc.select('a, button'))
    assert all(node.get_text(strip=True) for node in doc.select('.ui-sem-action-items > :is(a, button)'))
    assert (doc.button['name'], doc.button['value'], doc.button['form']) == ('intent', 'copy', 'editor')
    assert not empty.strip()


def test_wp2c_chip_names_are_text_even_for_markup(semantic_app):
    from bs4 import BeautifulSoup

    name = Markup('<img src=x onerror=alert(1)>"Archiv')
    with semantic_app.test_request_context():
        html = render_template_string('''{% from 'ui/_semantic.html' import filter_bar_sem %}
            {{ filter_bar_sem('/search', active_filters=[{'label': name, 'href': '/search?q=keep'}]) }}''', name=name)
    doc = BeautifulSoup(html, 'html.parser')
    assert not doc.select('img, script')
    assert doc.select_one('.admin-filter-chip').get_text(strip=True) == str(name)
    assert doc.select_one('.admin-filter-chip')['aria-label'].startswith(str(name))


@pytest.mark.parametrize('locale,more,details', [
    ('de', 'Weitere Aktionen für', 'Details'), ('en', 'More actions for', 'Details'),
])
def test_icon_summary_keeps_native_disclosure_and_accessible_names(semantic_app, locale, more, details):
    from bs4 import BeautifulSoup

    semantic_app.config['UI_LOCALE'] = locale
    name = Markup('<img src=x onerror=alert(1)>"Küche')
    with semantic_app.test_request_context():
        html = render_template_string('''{% from 'ui/_semantic.html' import icon_summary %}
            <details>{{ icon_summary('actions.more', object=name, id='key-more') }}
                <details>{{ icon_summary('ui.disclosure.details', aria_label=detail_name, show_text=true) }}</details>
            </details>
            <details>{{ icon_summary('actions.delete', aria_label='Schlüssel widerrufen') }}</details>''',
            name=name, detail_name=f'{details}: {name}')
    doc = BeautifulSoup(html, 'html.parser')
    summary = doc.select_one('#key-more')
    assert summary.name == 'summary' and summary.parent.name == 'details'
    assert summary['aria-label'] == f'{more} {name}'
    assert summary['data-ui-tooltip'] == summary['aria-label']
    assert 'ui-sem-control--icon-only' in summary['class']
    assert not summary.get_text(strip=True)
    assert not doc.select('button, a, img, script, [title], [type], [name], [value], [form]')
    assert all(svg['aria-hidden'] == 'true' for svg in doc.select('svg'))
    menu_entry = doc.select_one('[data-semantic="ui.disclosure.details"]')
    assert menu_entry.get_text(strip=True) == details
    assert details in menu_entry['aria-label']
    assert 'ui-sem-control--icon-only' not in menu_entry['class']
    assert 'btn-danger' in doc.select_one('[data-semantic="actions.delete"]')['class']


@pytest.mark.parametrize('args', ["aria_label=' '", "object=''", "show_text='yes'"])
def test_icon_summary_rejects_invalid_name_contract(semantic_app, args):
    with semantic_app.test_request_context(), pytest.raises(SemanticError):
        render_template_string("{% from 'ui/_semantic.html' import icon_summary %}"
                               "{{ icon_summary('actions.more', " + args + ') }}')


@pytest.mark.parametrize('hidden', [True, False])
def test_icon_summary_keeps_native_hidden_and_safe_attrs(semantic_app, hidden):
    from bs4 import BeautifulSoup

    with semantic_app.test_request_context():
        template = "{% from 'ui/_semantic.html' import icon_summary %}{{ icon_summary('actions.more', **options) }}"
        default = render_template_string(template, options={})
        assert default == render_template_string(template, options={'attrs': None})
        doc = BeautifulSoup(render_template_string(template, options={
            'attrs': {'hidden': hidden, 'data-recipe-details': '\"<>&'},
        }), 'html.parser')
    assert doc.summary.has_attr('hidden') is hidden
    assert doc.summary['data-recipe-details'] == '\"<>&'
    assert not doc.select('button, a, input, img, script')


@pytest.mark.parametrize('attrs', [{'hidden': 'false'}, {'onclick': 'bad()'}, {'autofocus': 'true'}])
def test_icon_summary_rejects_unsafe_or_nonboolean_attrs(semantic_app, attrs):
    with semantic_app.test_request_context(), pytest.raises(SemanticError):
        render_template_string("{% from 'ui/_semantic.html' import icon_summary %}"
                               "{{ icon_summary('actions.more', attrs=attrs) }}", attrs=attrs)


@pytest.mark.parametrize('focus', [True, False])
def test_icon_button_keeps_native_boolean_autofocus(semantic_app, focus):
    doc = _p2c_action(semantic_app, attrs={'autofocus': focus})
    assert doc.button.has_attr('autofocus') is focus


@pytest.mark.parametrize('locale,labels', [('de', ['Aktivieren', 'Übernehmen', 'Verlauf']), ('en', ['Activate', 'Apply', 'History'])])
def test_p2c_canonical_actions(semantic_app, locale, labels):
    semantic_app.config['UI_LOCALE'] = locale
    for name, label in zip(('activate', 'apply', 'history'), labels):
        key = 'actions.' + name
        item = load_registry()[key]
        assert item.role == 'neutral'
        assert item.icon_only_allowed
        doc = _p2c_action(semantic_app, key)
        assert doc.button.span is None
        assert doc.button['aria-label'] == doc.button['data-ui-tooltip'] == label
        assert doc.select_one('use')['href'].endswith('#tabler-' + item.resolved_icon)


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('key,text,aria', [
    ('data.revision', 'Festhalten', 'Gespeicherten Stand festhalten'),
    ('recipe.quantity', 'Berechnen', 'Mengen berechnen'),
    ('recipe.quantity', 'Originalmengen', 'Originalmengen ansehen'),
    ('actions.refresh', 'Originalausbeute', 'Originalausbeute verwenden'),
    ('actions.activate', 'Aktivieren', 'Rezept aktivieren'),
    ('actions.history', 'Rezept-History', 'Rezept-History'),
    ('actions.back', 'Zur Liste', 'Zur Liste der Rezepte'),
    ('actions.back', 'Zum Rezept', 'Zum Rezept'),
    ('actions.back', 'Zu Rezepten', 'Zu Rezepten'),
    ('actions.delete', 'Verwerfen', 'Stapel verwerfen'),
    ('actions.delete', 'Verwerfen', 'Verwerfen bestätigen'),
    ('actions.apply', 'Übernehmen', 'Importstapel übernehmen'),
    ('actions.preview', 'Vorschau speichern', 'Vorschau speichern'),
    ('actions.print', 'Drucken', 'Drucken · PDF öffnen'),
    ('actions.print', 'PDF öffnen', 'PDF öffnen · Stand 1 · Suppe'),
    ('actions.history', 'Verlauf', 'Verlauf · Suppe'),
])
def test_p4_recipe_context_labels_survive_en_and_keep_name(semantic_app, locale, key, text, aria):
    semantic_app.config['UI_LOCALE'] = locale
    extra = {'consequence_key': 'actions.delete'} if key == 'actions.delete' else {}
    doc = _p2c_action(semantic_app, key, href='/x', text=text, aria_label=aria, title=aria, **extra)
    control = doc.a or doc.button
    assert control.span is None
    assert text.lower() in control['aria-label'].lower()
    assert control['aria-label'] == aria == control['data-ui-tooltip']


@pytest.mark.parametrize('template,key,text,aria,icon', [
    ('rezepte_revisionen.html', 'data.revision', 'Festhalten', 'Gespeicherten Stand festhalten', 'versions'),
    ('rezepte_import.html', 'actions.apply', 'Übernehmen', 'Importstapel übernehmen', 'check'),
    ('rezepte_editor.html', 'actions.back', 'Zur Liste', 'Zur Liste der Rezepte', 'arrow-left'),
    ('rezepte_ansicht.html', 'actions.back', 'Zur Liste', 'Zur Liste der Rezepte', 'arrow-left'),
    ('rezepte_images.html', 'actions.back', 'Zum Rezept', 'Zum Rezept', 'arrow-left'),
    ('rezepte_import.html', 'actions.back', 'Zu Rezepten', 'Zu Rezepten', 'arrow-left'),
    ('rezepte.html', 'actions.print', 'PDF öffnen', 'PDF öffnen · Stand 1 · Suppe', 'printer'),
    ('rezepte.html', 'actions.history', 'Verlauf', 'Verlauf für Suppe', 'history'),
    ('rezepte_editor.html', 'actions.activate', 'Aktivieren', 'Rezept aktivieren', 'circle-check'),
])
def test_p4_judge_labels_render_from_owned_templates(semantic_app, template, key, text, aria, icon):
    """Exercise the actual action calls for all five judge findings."""
    from types import SimpleNamespace

    from bs4 import BeautifulSoup

    source = (ROOT.parent / 'templates/admin' / template).read_text(encoding='utf-8')
    calls = re.findall(r'\{\{\s*(icon_button\(.*?)\s*\}\}', source, re.S)
    if (template, key) == ('rezepte.html', 'actions.print'):
        matching = [call for call in calls if call.startswith("icon_button('actions.print',")
                    and "t('recipe.pdf_open.label')" in call]
    elif (template, key) == ('rezepte.html', 'actions.history'):
        matching = [call for call in calls if call.startswith("icon_button('actions.history',")
                    and "_anchor='recipe-freeze'" in call]
    else:
        matching = [call for call in calls if call.startswith(f"icon_button('{key}',")
                    and f"text='{text}'" in call]
    assert len(matching) == 1
    recipe = SimpleNamespace(public_id='r1', active=False, payload=SimpleNamespace(title='Suppe'))
    semantic_app.jinja_env.globals['url_for'] = lambda endpoint, **kwargs: '/target'
    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from 'ui/_semantic.html' import icon_button %}{{ " + matching[0] + ' }}',
            recipe=recipe, item=recipe, recipe_id='r1', can_write=False, token='token', batch=None,
            links=SimpleNamespace(latest_revision=SimpleNamespace(public_id='v1', revision_number=1)))
    control = BeautifulSoup(html, 'html.parser').select_one('a, button')
    recipe_menu = (template, key) in {
        ('rezepte.html', 'actions.print'), ('rezepte.html', 'actions.history'),
    }
    visible = text if template == 'rezepte_editor.html' or recipe_menu else ''  # Spec §5.4.
    assert (control.get_text(strip=True), control['aria-label']) == (visible, aria)
    assert text.lower() in aria.lower() and len(text) <= 18 and len(text.split()) <= 2
    assert control['data-ui-tooltip'] == aria
    assert control.select_one('use')['href'].endswith('#tabler-' + icon)
    if key == 'data.revision':
        assert (control['type'], control['form']) == ('submit', 'recipe-freeze-form')


def test_p4_german_aria_without_text_is_composed_in_en(semantic_app):
    semantic_app.config['UI_LOCALE'] = 'en'
    for key, aria in [('recipe.quantity', 'Mengen berechnen'),
                      ('actions.print', 'Drucken · PDF öffnen'),
                      ('actions.back', 'Zurück zur Rezeptliste')]:
        control = _p2c_action(semantic_app, key, href='/target', aria_label=aria, show_text=True).a
        assert control['aria-label'] == f'{control.span.text}: {aria}'
        assert control['data-ui-tooltip'] == control['aria-label']


def test_p4_owned_templates_pair_german_aria_with_text():
    root = Path(__file__).resolve().parents[1] / 'cafeteria/templates/admin'
    call = re.compile(r'icon_button\((.*?)\)', re.S)
    files = (
        '_recipe_template_selection.html', '_rezepte_fields.html', 'rezepte.html',
        'rezepte_ansicht.html', 'rezepte_editor.html', 'rezepte_images.html',
        'rezepte_import.html', 'rezepte_revision.html', 'rezepte_revisionen.html',
        'rezepte_scale.html',
    )
    for name in files:
        source = (root / name).read_text(encoding='utf-8')
        for args in call.findall(source):
            if 'aria_label=' not in args:
                continue
            if 'show_text=true' not in args.replace(' ', ''):
                continue
            assert 'text=' in args, f'{name}: visible text missing for {args[:160]}'


def _visible_word_in_name(node, visible):
    text = ' '.join(node.get_text(' ', strip=True).split())
    assert visible in text, text
    accessible = node.get('aria-label', text)
    assert visible.lower() in accessible.lower(), (visible, accessible, text)


@pytest.mark.parametrize('locale,more,image,upload,edit', [
    ('de', 'Mehr', 'Bild', 'Hochladen', 'Bearbeiten'),
    ('en', 'More', 'Image', 'Upload', 'Edit'),
])
def test_p4_registry_visible_text_is_in_accessible_name(semantic_app, locale, more, image, upload, edit):
    """Judge-2: EN labels More/Image/Upload/Edit must occur in the accessible name."""
    from types import SimpleNamespace

    from bs4 import BeautifulSoup
    from werkzeug.datastructures import MultiDict

    semantic_app.config['UI_LOCALE'] = locale
    semantic_app.jinja_env.globals['csrf_token'] = lambda: 'token'
    for endpoint in ('admin.recipes_list', 'admin.recipe_status', 'admin.recipe_edit',
                     'admin.recipe_form_rows', 'admin.recipe_images', 'admin.recipe_asset'):
        semantic_app.add_url_rule('/stub/' + endpoint, endpoint=endpoint, view_func=lambda **_kwargs: '')
    ingredient = SimpleNamespace(
        food_public_id='', group_label='', note='', source_reference='', source_kind='',
        fetched_at='', ingredient_text='Karotte', quantity='1', unit_code='G', line_public_id='')
    step = SimpleNamespace(instruction='Kochen', duration_minutes='', image_sha256='')
    payload = SimpleNamespace(
        title='Suppe', source=SimpleNamespace(kind='manual', reference='', url='', note='', fetched_at=''),
        ingredients=[ingredient], steps=[step], images=[])
    recipe = SimpleNamespace(
        payload=SimpleNamespace(title='Suppe', images=[]), active=True, public_id='r1', row_version=1)
    with semantic_app.test_request_context():
        editor = render_template_string(
            "{% extends 'admin/rezepte_editor.html' %}{% block sidebar %}{% endblock %}",
            confirmation=False, payload=payload, active=True, recipe_id='r1', can_write=True,
            links={'recipe_images': '/bilder', 'recipe_revisions': '/revisionen', 'recipe_scale': '/skala'},
            data=MultiDict(), choices=SimpleNamespace(units=[], foods=[], tags=[]),
            source_names={}, image_names={}, action='recipe.update')
        images = render_template_string(
            "{% extends 'admin/rezepte_images.html' %}{% block sidebar %}{% endblock %}",
            recipe=recipe, token='token')
    editor_doc = BeautifulSoup(editor, 'html.parser')
    for summary in editor_doc.select('.admin-compact-actions > summary'):
        assert summary.get_text(strip=True) == ''
        assert ('Weitere Aktionen' if locale == 'de' else 'More actions') in summary['aria-label']
        assert summary['data-ui-tooltip'] == summary['aria-label']
    _visible_word_in_name(editor_doc.select_one('a[data-semantic="data.image"]'), image)
    edit_control = editor_doc.select_one('button[data-recipe-toggle^="step-details"]')
    assert edit_control.get_text(strip=True) == ''
    assert edit in edit_control['aria-label']
    assert edit_control['data-ui-tooltip'] == edit_control['aria-label']
    upload_button = BeautifulSoup(images, 'html.parser').select_one('button[data-semantic="actions.upload"]')
    assert upload_button.get_text(strip=True) == ''
    assert upload_button['aria-label'] == upload_button['data-ui-tooltip'] == upload
    assert upload_button.select_one('use')['href'].endswith('#tabler-upload')
