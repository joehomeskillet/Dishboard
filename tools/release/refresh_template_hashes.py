#!/usr/bin/env python3
"""Template-Quellhashes in der UI-Routenmatrix nachführen, ohne das 12k-Zeilen-JSON neu zu formatieren.

Usage: refresh_template_hashes.py [<worktree>] [--apply]
<worktree> ist ohne Angabe das Repo dieses Skripts. Nur `sha256`-Werte von Einträgen, deren `path` auf ein
vorhandenes Template zeigt, werden ersetzt; jedes andere Byte bleibt. Ohne --apply nur Anzeige.
Exit 1, wenn ein alter Hash mehrdeutig ist (Eintrag übersprungen, von Hand prüfen).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def entries(node):
    if isinstance(node, dict):
        if isinstance(node.get('path'), str) and isinstance(node.get('sha256'), str):
            yield node
        for value in node.values():
            yield from entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from entries(value)


def main(argv: list[str]) -> int:
    apply = '--apply' in argv
    positional = [arg for arg in argv if not arg.startswith('--')]
    root = Path(positional[0]) if positional else Path(__file__).resolve().parents[2]
    matrix = root / 'docs/superpowers/backlog-0909/ui-route-matrix.json'
    templates = root / 'reference_scaffold/cafeteria/templates'
    text = matrix.read_text(encoding='utf-8')

    changes = []
    for entry in entries(json.loads(text)):
        source = templates / entry['path']
        if not source.is_file():
            continue
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != entry['sha256']:
            changes.append((entry['path'], entry['sha256'], digest))

    ambiguous = 0
    for path, old, new in changes:
        count = text.count(f'"sha256": "{old}"')
        print(f'{path}: {old[:12]} -> {new[:12]} (Vorkommen des alten Hashes: {count})')
        if count != 1:
            print('  !! mehrdeutig, übersprungen')
            ambiguous += 1
            continue
        text = text.replace(f'"sha256": "{old}"', f'"sha256": "{new}"')
    print('stale entries:', len(changes))
    if apply and changes:
        matrix.write_text(text, encoding='utf-8')
        print('written')
    return 1 if ambiguous else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
