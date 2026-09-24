"""DB-free source inventory. Counts static evidence, not rendered runtime branches.

Jinja expressions are masked before HTML parsing (quoted attributes may contain
HTML). Their original text remains available for registry/icon recognition.
Dynamic labels cannot be measured here; browser gates cover shared components.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'reference_scaffold/cafeteria/templates'
BASELINE = ROOT / 'reference_scaffold/tests/ui_consistency_baseline.json'
REPORT = ROOT / 'docs/ui-consistency-inventory.md'
CATEGORIES = ('literal_buttons', 'long_labels', 'legacy_labels', 'wrong_icons',
              'local_lists', 'local_filters')
JINJA = re.compile(r'{#.*?#}|{%.*?%}|{{.*?}}', re.S)
TOKEN = re.compile(r'JINJATOKEN(\d+)END')
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
        'meta', 'param', 'source', 'track', 'wbr'}


@dataclass
class Node:
    tag: str
    attrs: dict
    parent: Node | None = None
    parts: list = field(default_factory=list)

    def text(self):
        if ('hidden' in self.attrs or self.attrs.get('aria-hidden') == 'true'
                or 'visually-hidden' in self.attrs.get('class', '').split()
                or self.tag in {'script', 'style', 'svg'}):
            return ''
        return ''.join(p.text() if isinstance(p, Node) else p for p in self.parts)

    def source(self):
        attributes = ' '.join(v or '' for v in self.attrs.values())
        return attributes + ''.join(p.source() if isinstance(p, Node) else p for p in self.parts)


class TemplateParser(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.expressions = []
        self.nodes = []
        self.stack = []

        def mask(match):
            value = match.group()
            if value.startswith('{#'):
                return ''
            self.expressions.append(value)
            return f'JINJATOKEN{len(self.expressions) - 1}END'

        self.feed(JINJA.sub(mask, source))

    def restore(self, text):
        return TOKEN.sub(lambda m: self.expressions[int(m[1])], text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.stack[-1] if self.stack else None)
        self.nodes.append(node)
        if self.stack:
            self.stack[-1].parts.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].parts.append(data)


def canonical_icons():
    ui = ROOT / 'reference_scaffold/cafeteria/ui'
    registry = json.loads((ui / 'semantic_registry.json').read_text())
    fallback = json.loads((ui / 'icon_fallbacks.json').read_text())
    keys = dict(zip(('Anlegen', 'Bearbeiten', 'Speichern', 'Löschen', 'Archivieren',
                     'Kopieren', 'Vorschau', 'Öffnen', 'Suchen', 'Filtern', 'Mehr'),
                    ('actions.add', 'actions.edit', 'actions.save', 'actions.delete',
                     'actions.archive', 'actions.copy', 'actions.preview', 'actions.open',
                     'view.search', 'view.filter', 'actions.more'), strict=True))
    icons = {row['key']: row['icon'] for row in registry}
    return {verb: fallback.get(icons[key], {}).get('icon', icons[key])
            for verb, key in keys.items()}


def count_template(source, icons=None, shared=False):
    parser = TemplateParser(source)
    counts = dict.fromkeys(CATEGORIES, 0)
    icons = canonical_icons() if icons is None else icons
    for node in parser.nodes:
        attrs = {k: parser.restore(v or '') for k, v in node.attrs.items()}
        classes = attrs.get('class', '').split()
        raw = parser.restore(node.source())
        literal = ' '.join(TOKEN.sub('', node.text()).split())
        if node.tag in {'a', 'button', 'summary'} and 'btn' in classes:
            semantic = bool(re.search(r'\b(?:icon_label|icon_button|sem)\s*\(', raw))
            counts['literal_buttons'] += bool(literal and not semantic)
            counts['long_labels'] += len(literal) > 18 or len(literal.split()) > 2
            found = re.findall(r"\bicon\(\s*['\"]([^'\"]+)", raw)
            found += re.findall(r'#tabler-([\w-]+)', raw)
            for verb, expected in icons.items():
                if re.search(r'\b' + re.escape(verb) + r'\b', literal):
                    counts['wrong_icons'] += bool(found and any(i != expected for i in found))
                    break
        if 'badge' in classes and not any(
                c == 'admin-label' or c.startswith('admin-status--') for c in classes):
            counts['legacy_labels'] += 1
        is_list = node.tag == 'table' or any(
            c in {'list-group', 'admin-list-row'} or c.endswith('-list-row') for c in classes)
        if is_list and 'admin-table' not in classes and not (shared and 'admin-list-row' in classes):
            counts['local_lists'] += 1
        is_filter = (node.tag == 'form' and (
            attrs.get('role') == 'search' or re.search(r'\b(?:search|filter)\b',
                                                    attrs.get('class', ''))
            or re.search(r"\bfield\([^}]*type\s*=\s*['\"]search", raw)
            or any(n.tag in {'input', 'select'} and (
                n.attrs.get('type') == 'search' or n.attrs.get('name') in {'q', 'query', 'search'}
                or (n.tag == 'select' and attrs.get('method', 'get').lower() == 'get'))
                   and _inside(n, node) for n in parser.nodes)))
        if is_filter and not (shared and 'admin-filter-bar' in classes):
            counts['local_filters'] += 1
    return counts


def _inside(child, parent):
    while child.parent:
        child = child.parent
        if child is parent:
            return True
    return False


def inventory(templates=TEMPLATES):
    icons = canonical_icons()
    return {p.relative_to(templates).as_posix(): count_template(
                p.read_text(), icons, shared=p.relative_to(templates).as_posix() == 'admin/_macros.html')
            for p in sorted(templates.rglob('*.html'))}


def regressions(current, baseline):
    return [f'{name}: {category} {counts[category]} > {baseline.get(name, {}).get(category, 0)}'
            for name, counts in current.items() for category in CATEGORIES
            if counts[category] > baseline.get(name, {}).get(category, 0)]


def markdown(current):
    totals = {c: sum(row[c] for row in current.values()) for c in CATEGORIES}
    lines = ['# UI consistency inventory — P4 migration queue', '',
             'Static source counts across all templates; runtime branches and dynamic labels',
             'need rendered review. Public/signage entries are inventory, not migration permission.',
             'Zero rows retained so every template is accounted for.', '',
             'Categories: literal buttons, long labels (>2 words or >18 characters), legacy labels,',
             'wrong canonical icons, local tables/row lists, local filter/search forms.', '',
             'Update after reviewed reductions: `rtk python3 tools/ui_consistency_inventory.py --update-baseline`.',
             'Existing ceilings only decrease; regressions refuse the update. New templates start at zero.', '',
             '| Template | ' + ' | '.join(CATEGORIES) + ' |',
             '|---|' + '---:|' * len(CATEGORIES)]
    lines += ['| ' + name + ' | ' + ' | '.join(str(row[c]) for c in CATEGORIES) + ' |'
              for name, row in current.items()]
    lines += ['| **TOTAL** | ' + ' | '.join(str(totals[c]) for c in CATEGORIES) + ' |', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-baseline', action='store_true')
    args = parser.parse_args()
    current = inventory()
    if args.update_baseline:
        if BASELINE.exists():
            failures = regressions(current, json.loads(BASELINE.read_text()))
            if failures:
                parser.error('Baseline cannot increase:\n' + '\n'.join(failures))
        BASELINE.write_text(json.dumps(current, indent=2, ensure_ascii=False) + '\n')
        REPORT.write_text(markdown(current))
    print(json.dumps({c: sum(r[c] for r in current.values()) for c in CATEGORIES}))


if __name__ == '__main__':
    main()
