"""DELTA-5 source ratchet: native exceptions, exact legacy identities, no count budget."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import re

import pytest
from jinja2 import Environment, nodes

from delta5_audit import ROOT, write_json
from test_ui_consistency_ratchet import inventory

TEMPLATES = ROOT / 'reference_scaffold/cafeteria/templates'
# Exact source identities of the pending DELTA-3 L2 migration; removal is allowed.
PENDING_L2 = Counter({
    ('admin/_recipe_document.html', 'call', '34d56fb598611004'): 1,
    ('admin/_recipe_document.html', 'call', '58af18bd3b23fcec'): 1,
    ('admin/_recipe_document.html', 'details', 'aa379c61f760ebb6'): 1,
    ('admin/_recipe_document.html', 'details', 'b9b44bdfa441bd6c'): 1,
    ('admin/_recipe_template_selection.html', 'call', '2ee1812bd4fb5a65'): 1,
    ('admin/_recipe_template_selection.html', 'call', '5e5ff03315f312c7'): 1,
    ('admin/_recipe_template_selection.html', 'call', '87adf8f1156665fc'): 1,
    ('admin/_recipe_template_selection.html', 'details', '32f119108ec1651c'): 1,
    ('admin/_recipe_template_selection.html', 'details', 'd2bbe65ecd707768'): 1,
    ('admin/_recipe_template_selection.html', 'details', 'd892f4ee59d27973'): 1,
    ('admin/print_template_editor.html', 'call', '3227d5f29d7fcd06'): 1,
    ('admin/print_template_editor.html', 'call', '346b363942155531'): 1,
    ('admin/print_template_editor.html', 'call', '58e680004365968f'): 1,
    ('admin/print_template_editor.html', 'call', '5e63f46253a4f75b'): 1,
    ('admin/print_template_editor.html', 'call', '9e7d895f8d56c719'): 1,
    ('admin/print_template_editor.html', 'call', 'de94f2bc9c24bcca'): 1,
    ('admin/print_template_editor.html', 'call', 'e4f2d39ed746a1cd'): 1,
    ('admin/print_template_editor.html', 'details', '228c5323c7b01680'): 1,
    ('admin/print_template_editor.html', 'details', '4412edeefc84b12b'): 1,
    ('admin/print_template_editor.html', 'details', '6f68c666d7fea4ae'): 1,
    ('admin/print_template_editor.html', 'details', '8b71fe9fe8e61fd0'): 1,
    ('admin/print_template_editor.html', 'details', 'a334a0c5c5114515'): 1,
    ('admin/rezepte_editor.html', 'call', '19ff9acf74fa7a5a'): 1,
    ('admin/rezepte_editor.html', 'call', '5d14c855103247af'): 1,
    ('admin/rezepte_editor.html', 'call', '7dfc3ed2fe627624'): 1,
    ('admin/rezepte_editor.html', 'call', 'a4e01f96a6c90f71'): 1,
    ('admin/rezepte_editor.html', 'call', 'e9a64ba309395b27'): 2,
    ('admin/rezepte_editor.html', 'details', '07f6bfcfe8736de6'): 1,
    ('admin/rezepte_editor.html', 'details', '22639f44c17c82b4'): 1,
    ('admin/rezepte_editor.html', 'details', '4cdd715a965998f1'): 1,
    ('admin/rezepte_editor.html', 'details', '4dffd7452399448e'): 1,
    ('admin/rezepte_images.html', 'call', '08ae6b156c87459d'): 1,
    ('admin/rezepte_images.html', 'call', 'a22729fb60b2a31e'): 1,
    ('admin/rezepte_images.html', 'details', '0146a4b088288c47'): 1,
    ('admin/rezepte_import.html', 'call', '09755412b4e44ae0'): 1,
    ('admin/rezepte_import.html', 'call', '78e4212ad112897f'): 1,
    ('admin/rezepte_import.html', 'call', '86ca46c616ecf310'): 1,
    ('admin/rezepte_import.html', 'call', 'bb96e022c7261c85'): 1,
    ('admin/rezepte_import.html', 'details', '2d4c3659918d6e95'): 1,
    ('admin/rezepte_import.html', 'details', 'ca15bb88617a8392'): 1,
    ('admin/rezepte_import.html', 'details', 'dbb0336e96cf5c36'): 1,
    ('admin/rezepte_revision.html', 'call', 'a22729fb60b2a31e'): 1,
    ('admin/rezepte_revisionen.html', 'call', 'a22729fb60b2a31e'): 1,
    ('admin/rezepte_revisionen.html', 'call', 'c057a3ad56ed9802'): 1,
})


def source_occurrences(source):
    aliases = {'disclosure_section', 'icon_summary'}
    tree = Environment().parse(source)
    for imported in tree.find_all(nodes.FromImport):
        for name in imported.names:
            if isinstance(name, tuple) and name[0] in aliases:
                aliases.add(name[1])
    result = Counter()
    for call in tree.find_all(nodes.Call):
        name = call.node.name if isinstance(call.node, nodes.Name) else (
            call.node.attr if isinstance(call.node, nodes.Getattr) else None)
        if name in aliases:
            result['call', sha256(repr(call).encode()).hexdigest()[:16]] += 1
    parser = inventory.TemplateParser(re.sub(r'<!--.*?-->', '', source, flags=re.S))
    for node in parser.nodes:
        if node.tag != 'details':
            continue
        parent, native = node, False
        while parent:
            classes = (parent.attrs.get('class') or '').split()
            native |= 'admin-sidebar' in classes or parent.attrs.get('role') == 'combobox'
            parent = parent.parent
        if not native:
            normalized = ' '.join(parser.restore(node.source()).split())
            result['details', sha256(normalized.encode()).hexdigest()[:16]] += 1
    return result


def assert_no_new_sources(found, baseline):
    assert not found - baseline, f'New UI-DELTA source cases: {found - baseline}'


def test_source_inventory_rejects_new_forbidden_cases(tmp_path):
    found = Counter()
    for path in sorted((TEMPLATES / 'admin').rglob('*.html')):
        if path.name == '_macros.html':
            # Read-only compatibility definitions; real caller identities checked below.
            continue
        for (kind, digest), count in source_occurrences(path.read_text()).items():
            found[path.relative_to(TEMPLATES).as_posix(), kind, digest] += count
    write_json(tmp_path / 'source-inventory.json', [
        dict(path=path, kind=kind, fingerprint=digest, count=count)
        for (path, kind, digest), count in sorted(found.items())])
    assert_no_new_sources(found, PENDING_L2)


@pytest.mark.parametrize('source', [
    '<details><summary>Info</summary><p>Content</p></details>',
    '{% call disclosure_section() %}Content{% endcall %}',
    "{% from 'admin/_macros.html' import disclosure_section as info %}"
    '{% call info() %}Content{% endcall %}',
    "{{ icon_summary('ui.disclosure.details') }}",
    "{% import 'admin/_macros.html' as ui %}{{ ui.icon_summary('ui.disclosure.details') }}",
])
def test_source_ratchet_rejects_added_duplicate_and_replaced_cases(source):
    original = Counter({('old.html', *key): n for key, n in source_occurrences(source).items()})
    assert original
    assert_no_new_sources(Counter(), original)
    assert_no_new_sources(original, original)
    for changed in [original + original,
                    Counter({('new.html', *key): n for key, n in source_occurrences(source).items()}),
                    Counter({('old.html', 'call', 'different-source'): 1})]:
        with pytest.raises(AssertionError, match='New UI-DELTA source cases'):
            assert_no_new_sources(changed, original)


def test_source_ratchet_classifies_native_exceptions_and_comments():
    source = '''{# <details><summary>Ignored</summary></details> #}
        <!-- <details><summary>Ignored</summary></details> -->
        <aside class="admin-sidebar"><details><summary>Navigation</summary>Links</details></aside>
        <div role="combobox"><details><summary>Choice</summary>Choices</details></div>
        <label><input type="checkbox">Choose</label><input type="date"><select><option>A</option></select>'''
    assert source_occurrences(source) == Counter()
