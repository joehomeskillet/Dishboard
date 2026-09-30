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
    assert inventory.count_template(source) == dict(zip(inventory.CATEGORIES, (2, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0)))


def test_shared_patterns_hidden_text_and_reductions():
    source = '''<button class="btn">{{ icon_label('actions.save') }}</button>
    <span class="badge admin-label">Live</span><table class="admin-table"></table>
    {{ filter_bar('/search') }}
    <button class="btn">{{ sem_icon('actions.edit') }}<span class="visually-hidden">Very long hidden label</span></button>'''
    zero = dict.fromkeys(inventory.CATEGORIES, 0)
    assert inventory.count_template(source) == zero | {'local_status': 1}
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


def test_foundation_detectors_include_aliases_without_counting_shared_components():
    source = '''{# {{ status_badge('active') }} <details></details> #}
    <!-- {{ status_badge('active') }} <details></details> -->
    {% from 'admin/_macros.html' import status_badge as state %}
    {{ state('active') }}{{ status_badge('draft') }}
    <span class="badge admin-status--warning">Fehlende Daten</span>
    <div class="admin-form-footer">Local footer</div><details><summary>Info</summary></details>
    {{ status_badge_sem('review.pending') }}{{ form_footer(primary, '/back') }}
    {% call disclosure_section() %}Content{% endcall %}'''
    counts = inventory.count_template(source)
    assert counts['local_status'] == 3
    assert counts['local_footers'] == counts['raw_details'] == 1
    shared = inventory.count_template(source, shared=True)
    assert shared['local_status'] == shared['local_footers'] == shared['raw_details'] == 0
    assert inventory.count_template("{{ label('Vegan', 'category') }}")['local_status'] == 0


def test_pixel_height_detector_counts_declarations_not_media_strings_or_comments():
    css = '''/* .ignored { min-height: 48px; } */
    @media (min-height: 700px) {
      .control { min-height: 36px; content: "min-height: 48px;"; }
      .other { MIN-HEIGHT: 44.0px }
    }
    .valid { min-height: var(--app-control-min-height); --min-height: 40px; }'''
    assert inventory.css_px_heights(css) == 2


def test_foundation_ratchet_rejects_new_occurrences():
    for category in ('local_status', 'local_footers', 'raw_details', 'css_px_heights'):
        assert category in inventory.CATEGORIES
        zero = dict.fromkeys(inventory.CATEGORIES, 0)
        added = zero | {category: 1}
        assert inventory.regressions({'new': added}, {})
        assert inventory.regressions({'existing': added}, {'existing': zero})
        assert not inventory.regressions({'existing': zero}, {'existing': added})
