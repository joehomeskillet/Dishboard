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
    assert_no_new_sources(found, Counter())


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
