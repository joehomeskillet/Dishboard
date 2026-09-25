"""DB-free presentation contracts, including failure paths and trust boundaries."""
from __future__ import annotations

import json
import hashlib
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
        assert button.get_text(strip=True) == publish_label
        assert button.has_attr('disabled') is blocked
    assert trigger['data-bs-toggle'] == 'modal'
    assert nojs['form'] == 'week-publish-form'
    for button in (trigger, nojs):
        assert button.get('aria-describedby') == ('week-publish-guidance' if blocked else None)
    primary = doc.select('.btn-primary')
    assert len(primary) == 1
    assert primary[0].get_text(strip=True) == (
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
    assert [item.get_text(strip=True) for item in doc.select('.admin-week-more-menu .dropdown-item')] == [
        'CSV exportieren', 'Vorwoche kopieren', 'Übernehmen',
    ]


def test_registry_source_schema_and_frozen_resolution():
    registry = load_registry()
    source = Path(__file__).resolve().parents[2] / 'docs/design/semantic-ui-language-2026-09-20'
    seeds = json.loads((source / '05_SEMANTIC_REGISTRY.json').read_text())
    # P2c adds activate/apply/history; no aliases for different business actions.
    assert len(seeds) == 187
    assert len(registry) == 208
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
            with pytest.raises(SemanticError, match=key):
                render_template_string("{% from 'ui/_semantic.html' import icon_button %}{{ icon_button(key, icon_only=true) }}", key=key)
        html = render_template_string("{% from 'ui/_semantic.html' import icon_button %}{{ icon_button('actions.edit', icon_only=true) }}")
        assert 'title="Bearbeiten"' in html and 'aria-label="Bearbeiten"' in html
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
            {{ form_footer({'label': 'Speichern', 'name': 'intent', 'value': 'save', 'form': 'editor'},
                '/cancel', rare=icon_button('actions.edit', href='#edit'),
                secondary=[{'label': 'Vorschau', 'href': '#preview'}],
                danger=icon_button('actions.delete', consequence_key='ui.request_failed')) }}
        ''')
    document = BeautifulSoup(html, 'html.parser')
    primary = document.select('.btn-primary')
    assert len(primary) == 1
    assert (primary[0]['name'], primary[0]['value'], primary[0]['form']) == ('intent', 'save', 'editor')
    assert document.select_one('.admin-form-main a[href="#preview"]')
    assert document.select_one('.admin-form-main a[href="/cancel"]')
    rare = document.select_one('details.admin-form-rare')
    assert not rare.has_attr('open')
    assert rare.select_one('summary.btn-ghost')
    assert rare.select_one('a[href="#edit"]')
    danger = document.select_one('.admin-form-danger')
    assert danger.select_one('.btn-danger svg')
    assert danger.select_one('.btn-danger span').get_text(strip=True) == 'Löschen'
    assert danger.select_one('.ui-sem-consequence').get_text(strip=True)

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
    assert document.summary.get_text(strip=True) == 'Mehr'
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
    ('de', 'Weitere Optionen', 'Mehr'),
    ('en', 'More options', 'More'),
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
    assert document.select_one('.admin-compact-actions summary').get_text(strip=True) == more


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


# Captured before edits at d2e66fed8fe3fce9aab21f5613140327dd19822b.
# Hash raw UTF-8 HTML, including whitespace; no normalized DOM comparison.
@pytest.mark.parametrize('template,macro,call,digest', [
    ('ui/_semantic.html', 'icon_button',
     "icon_button('actions.edit', href='/edit', icon_only=true, id='edit')",
     'aaf97101c867535298c70ab702aa0781ab7aab98839b25c7fa72c359c44d8b63'),
    ('ui/_semantic.html', 'action_menu',
     "action_menu([{'key':'actions.copy','name':'intent','value':'copy','form':'editor'}])",
     'd4b0ad3c7e58376d372c4393df66f2ca9cb4c1a00910a82c1f610b7fd59eb125'),
    ('ui/_semantic.html', 'row_actions',
     "row_actions([{'key':'actions.edit','href':'/edit'}, {'key':'actions.copy','name':'intent','value':'copy'}])",
     'a1737fa5e73b1371bb2f701ddb1f99e72ae0791b83802016ec97ecd110ab7e2a'),
    ('ui/_semantic.html', 'filter_bar_sem',
     "filter_bar_sem('/search', search_name='text', search_value='Soup', more_filters='Extra', active=true, reset_url='/reset')",
     'd7862c1e706c16184dc9edd010aed7602a72225eb852a7ba0daf6e098da6bd18'),
    ('admin/_macros.html', 'filter_bar',
     "filter_bar('/search', search_name='text', search_value='Soup', more_filters='Extra', active=true, reset_url='/reset')",
     'ebfead26ebeecd53a7849d2a8a645651f37adc61bff381502ad9b146cec762e3'),
    ('admin/_macros.html', 'field',
     "field('q', 'Suche', 'Soup', type='search', hint='Help', error='Error')",
     '9bbf6ded90cc791728d0add549697446ca1ac979266596a6ba2d0afa30d4d84f'),
])
def test_p2c_legacy_bytes(semantic_app, template, macro, call, digest):
    with semantic_app.test_request_context():
        html = render_template_string(
            "{% from '" + template + "' import " + macro + ' %}{{ ' + call + ' }}')
    assert hashlib.sha256(html.encode()).hexdigest() == digest


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
    assert doc.button.span.text == hostile
    assert doc.button['aria-label'] == hostile + ' Kontext'
    assert doc.button['title'] == hostile
    assert set(doc.button['class']) >= {'btn', 'ui-sem-control', 'dropdown-item'}
    assert doc.select_one('use')['href'].endswith('#tabler-edit')
    assert not doc.select('script, img')
    icon = _p2c_action(semantic_app, icon_only=True, aria_label='Vorlage X bearbeiten')
    assert icon.button['title'] == icon.button['aria-label'] == 'Vorlage X bearbeiten'
    assert icon.button.span is None
    custom = _p2c_action(semantic_app, icon_only=True, aria_label=hostile, title='Eigener Tooltip')
    assert custom.button['aria-label'] == hostile
    assert custom.button['title'] == 'Eigener Tooltip'


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
    ({'emphasis': 'primary', 'icon_only': True}, 'visible text'),
    ({'emphasis': 'danger'}, 'consequence_key'),
    ({'emphasis': 'danger', 'icon_only': True}, 'icon-only'),
    ({'text': 'one two three'}, 'text must'),
    ({'text': 'x' * 19}, 'text must'), ({'text': ''}, 'text must'),
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
def test_p2d_context_name_composes_visible_label(semantic_app, locale, key, text, aria_label, visible, href):
    semantic_app.config['UI_LOCALE'] = locale
    doc = _p2c_action(semantic_app, key, text=text, aria_label=aria_label, href=href)
    control = doc.select_one('.ui-sem-control')
    assert control.span.text == visible
    assert control['aria-label'] == control['title'] == f'{visible}: {aria_label}'
    assert not doc.select('img, script')


@pytest.mark.parametrize('icon_only', [False, True])
@pytest.mark.parametrize('title', [None, 'Eigener Tooltip'])
def test_p2d_composed_name_respects_icon_only_and_explicit_title(semantic_app, icon_only, title):
    semantic_app.config['UI_LOCALE'] = 'en'
    doc = _p2c_action(semantic_app, aria_label='Vorlage X bearbeiten', icon_only=icon_only, title=title)
    expected = 'Vorlage X bearbeiten' if icon_only else 'Edit: Vorlage X bearbeiten'
    assert doc.button['aria-label'] == expected
    assert doc.button['title'] == (title if title is not None else expected)
    assert (doc.button.span is None) == icon_only


@pytest.mark.parametrize('aria_label', [None, 'Vorlage X BEARBEITEN'])
def test_p2d_matching_or_absent_name_keeps_exact_markup(semantic_app, aria_label):
    with semantic_app.test_request_context():
        template = "{% from 'ui/_semantic.html' import icon_button %}{{ icon_button('actions.edit', **options) }}"
        baseline = render_template_string(template, options={})
        actual = render_template_string(template, options={'aria_label': aria_label})
    expected = baseline if aria_label is None else baseline.replace(
        'title="Bearbeiten"', 'title="Bearbeiten" aria-label="Vorlage X BEARBEITEN"')
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
    assert set(doc.button.attrs) == set(attrs) - {'hidden'} | {'class', 'data-semantic', 'title', 'type', 'name', 'value', 'form'}
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
        assert control['title'] == item['title']
        assert 'dropdown-item' in control['class'] and 'btn-primary' not in control['class']
        assert control['data-confirm'] == 'Weiter?'
        assert control['formaction'] == '/edit' and control['formnovalidate'] == ''
        assert (control['name'], control['value'], control['form']) == ('intent', 'edit', 'editor')
    assert doc.select_one('#context').span is None
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


@pytest.mark.parametrize('locale,labels', [('de', ['Aktivieren', 'Übernehmen', 'Verlauf']), ('en', ['Activate', 'Apply', 'History'])])
def test_p2c_canonical_actions(semantic_app, locale, labels):
    semantic_app.config['UI_LOCALE'] = locale
    for name, label in zip(('activate', 'apply', 'history'), labels):
        key = 'actions.' + name
        item = load_registry()[key]
        assert item.role == 'neutral'
        assert item.icon_only_allowed == (name == 'history')
        doc = _p2c_action(semantic_app, key)
        assert doc.button.span.text == doc.button['title'] == label
        assert doc.select_one('use')['href'].endswith('#tabler-' + item.resolved_icon)
