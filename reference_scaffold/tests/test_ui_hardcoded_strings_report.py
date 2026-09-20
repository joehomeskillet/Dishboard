"""Measurement only: Jinja literal output + text/accessible attributes in HTML.

Heuristic: parse TemplateData with HTMLParser, ignore script/style and whitespace;
count Output Const strings and constant arguments to known legacy UI macros.
Dynamic business data and literals passed to t/semantic macros are excluded.
Counts measure occurrences, not unique phrases or fully rendered branch coverage.
"""
from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, nodes

TEMPLATES = Path(__file__).resolve().parents[1] / 'cafeteria/templates/admin'
PROOF = 'print_template_unavailable.html'
LEGACY = {'page_header', 'field', 'select', 'empty_state', 'disclosure_section'}


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.texts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1
        for name, value in attrs:
            if name in {'title', 'aria-label', 'placeholder', 'alt'} and value and any(c.isalpha() for c in value):
                self.texts.append(value)

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and any(c.isalpha() for c in data):
            self.texts.append(data.strip())


def literal_report(source: str) -> list[str]:
    tree = Environment().parse(source)
    parser = VisibleText()
    texts = []
    for output in tree.find_all(nodes.Output):
        for node in output.nodes:
            if isinstance(node, nodes.TemplateData):
                parser.feed(node.data)
            elif isinstance(node, nodes.Const) and isinstance(node.value, str) and any(c.isalpha() for c in node.value):
                texts.append(node.value)
            else:
                # A neutral marker prevents HTMLParser concatenating unrelated
                # attribute fragments around dynamic template output.
                parser.feed('0')
    for call in tree.find_all(nodes.Call):
        if isinstance(call.node, nodes.Name) and call.node.name in LEGACY:
            texts.extend(arg.value for arg in call.args if isinstance(arg, nodes.Const)
                         and isinstance(arg.value, str) and any(c.isalpha() for c in arg.value))
    parser.close()
    return parser.texts + texts


def template_counts() -> dict[str, int]:
    return {str(path.relative_to(TEMPLATES)): len(literal_report(path.read_text()))
            for path in sorted(TEMPLATES.rglob('*.html'))}


def test_hardcoded_strings_measurement(tmp_path):
    counts = template_counts()
    (tmp_path / 'ui-hardcoded-strings.json').write_text(
        json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    assert counts[PROOF] == 0, literal_report((TEMPLATES / PROOF).read_text())


def test_guard_recognizes_visible_and_accessible_literals():
    assert literal_report('<button title="Löschen">Löschen</button>') == ['Löschen', 'Löschen']
    assert literal_report('<h1>{{ t("actions.save.label") }}</h1>') == []
    assert literal_report('<script>const label="ignored";</script>') == []
