"""DB-free presentation contracts, including failure paths and trust boundaries."""
from __future__ import annotations

import json
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


def test_registry_source_schema_and_frozen_resolution():
    registry = load_registry()
    source = Path(__file__).resolve().parents[2] / 'docs/design/semantic-ui-language-2026-09-20'
    seeds = json.loads((source / '05_SEMANTIC_REGISTRY.json').read_text())
    assert len(seeds) == 184
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
