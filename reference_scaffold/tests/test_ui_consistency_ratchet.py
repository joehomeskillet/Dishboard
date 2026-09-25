"""Static ratchet and detector examples: no application, DB or browser required."""
import importlib.util
import json
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'ui_consistency_inventory', Path(__file__).resolve().parents[2] / 'tools/ui_consistency_inventory.py')
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


def test_template_consistency_does_not_regress():
    baseline = json.loads(inventory.BASELINE.read_text())
    assert not inventory.regressions(inventory.inventory(), baseline)


def test_all_six_detectors_and_jinja_quoting():
    source = '''{# <button class="btn">Ignored</button> #}
    <a class="btn" href="{{ url_for('edit', q='>') }}">{{ icon('trash') }}Bearbeiten</a>
    <button class="btn"><span>Speichern und zurück zum Wochenplan</span></button>
    <span class="badge bg-green-lt">Live</span><table class="table"></table>
    <form><input type="search"></form>'''
    assert inventory.count_template(source) == dict(zip(inventory.CATEGORIES, (2, 1, 1, 1, 1, 1, 0)))


def test_shared_patterns_hidden_text_and_reductions():
    source = '''<button class="btn">{{ icon_label('actions.save') }}</button>
    <span class="badge admin-label">Live</span><table class="admin-table"></table>
    {{ filter_bar('/search') }}
    <button class="btn">{{ sem_icon('actions.edit') }}<span class="visually-hidden">Very long hidden label</span></button>'''
    zero = dict.fromkeys(inventory.CATEGORIES, 0)
    assert inventory.count_template(source) == zero
    assert not inventory.regressions({'x': zero}, {'x': dict.fromkeys(zero, 3)})
    assert inventory.regressions({'new': dict.fromkeys(zero, 1)}, {})


def test_local_shared_class_copies_and_svg_icons_are_still_inventory():
    source = '''<div class="admin-list-row">Local copy</div>
    <form class="admin-filter-bar">{{ field('q', 'Suche', type='search') }}</form>
    <button class="btn"><svg><use href="#tabler-trash"></use></svg>Speichern</button>'''
    result = inventory.count_template(source)
    assert result['local_lists'] == result['local_filters'] == result['wrong_icons'] == 1


def test_plain_lists_filter_containers_and_mixed_literal_buttons():
    source = '''<ul><li>Record</li></ul><ol><li>Record</li></ol>
    <nav><ul><li>Navigation</li></ul></nav><ul class="pagination"></ul>
    <section class="filter-bar"><div class="filter-fields">Query</div></section>
    <button class="btn">{{ icon_label('actions.save') }} and close</button>'''
    result = inventory.count_template(source)
    assert result['local_lists'] == 2
    assert result['local_filters'] == result['literal_buttons'] == 1
    assert result['long_labels'] == 1
    assert inventory.count_template('''<button class="btn">{{ icon(sem('view.reset').resolved_icon) }}{{ t(sem('view.reset').label_key) }}</button>''')['long_labels'] == 0


def test_list_typography_declarations_nested_rules_and_false_positives():
    css = '''/* td { color: red; } */
    .admin-list-row, .admin-table td { font-size: 1rem; color: var(--app-text); }
    @media (width < 600px) { .recipe-list > tr { font-weight: 700; padding: 0; } }
    .title { color: red; content: "td { color: red; }"; }
    .other-row { font-weight: 600 }
    .other-list { color: inherit; }
    th { font-size: 14px; }'''
    hits = inventory.list_typography_overrides(css)
    assert [hit['property'] for hit in hits] == [
        'font-size', 'color', 'font-weight', 'font-weight', 'color', 'font-size']
    assert [hit['line'] for hit in hits] == [2, 2, 3, 5, 6, 7]


def test_list_typography_ratchet_rejects_new_and_increased_overrides():
    zero = dict.fromkeys(inventory.CATEGORIES, 0)
    added = zero | {'list_typography_overrides': 1}
    assert inventory.regressions({'static/admin-new.css': added}, {})
    assert inventory.regressions({'static/admin-old.css': added}, {'static/admin-old.css': zero})
    assert not inventory.regressions({'static/admin-old.css': zero}, {'static/admin-old.css': added})
