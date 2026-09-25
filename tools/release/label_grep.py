#!/usr/bin/env python3
"""Sichtbare Texte, die ein Stand entfernt, und jede Testdatei, die sie noch zitiert.

Usage: label_grep.py <worktree> <base> [--files]

Verglichen wird git merge-base(<base>, HEAD)..HEAD in den Templates und in der DE-Übersetzung:
Button-/Link-/Summary-Texte, text=/label=/title=/aria_label=-Argumente und Registry-Labels von
icon_button()/icon_label() ohne eigenen text=. Gesucht wird als einfacher Teilstring in allen
Testdateien. Gesperrte Abnahmetests *_accept.py sind als LOCKED markiert: Sie dürfen nicht
geändert werden und pinnen den Produkttext, der Text muss also im Produkt bleiben.

Exit 1 bei LOCKED-Treffern, sonst 0.
--files: nur die Trefferdateien relativ zu reference_scaffold, eine pro Zeile, immer Exit 0
         (so fügt release_gate.sh sie dem Gate hinzu).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

TEMPLATES = 'reference_scaffold/cafeteria/templates'
DE_LOCALE = 'reference_scaffold/cafeteria/translations/de.json'
TAG_TEXT = re.compile(r'(?:\}\}|>)\s*([A-ZÄÖÜ][^<>{}]{3,60}?)\s*</(?:button|a|summary)>')
KWARG_TEXT = re.compile(r'\b(?:text|label|title|aria_label)\s*=\s*([\'"])([^\'"{}<>]{4,60})\1')
REGISTRY_CALL = re.compile(r'\b(?:icon_button|icon_label)\(\s*[\'"]([\w.]+)[\'"]')
LOCALE_LINE = re.compile(r'^\s*"([\w.]+\.(?:label|aria))"\s*:\s*"(.+?)",?\s*$')


def git(worktree: str, *args: str) -> str:
    return subprocess.run(['git', '-C', worktree, *args], capture_output=True, text=True, check=True).stdout


def locale_labels(worktree: str, rev: str) -> dict[str, str]:
    try:
        return json.loads(git(worktree, 'show', f'{rev}:{DE_LOCALE}'))
    except (subprocess.CalledProcessError, ValueError):
        return {}


def visible_texts(line: str, labels: dict[str, str]) -> set[str]:
    found = {text.strip() for text in TAG_TEXT.findall(line)}
    found |= {match[1].strip() for match in KWARG_TEXT.findall(line)}
    if 'text=' not in line:
        found |= {labels[f'{key}.label'] for key in REGISTRY_CALL.findall(line) if f'{key}.label' in labels}
    return found


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    worktree, base = argv[0], argv[1]
    files_only = '--files' in argv[2:]
    merge_base = git(worktree, 'merge-base', base, 'HEAD').strip()
    labels = {'-': locale_labels(worktree, merge_base), '+': locale_labels(worktree, 'HEAD')}

    removed: set[str] = set()
    added: set[str] = set()
    diff = git(worktree, 'diff', '--no-renames', '-U0', f'{merge_base}..HEAD', '--', TEMPLATES, DE_LOCALE)
    current_file = ''
    for line in diff.splitlines():
        if line.startswith('diff --git '):
            current_file = line.rsplit(' b/', 1)[-1]
            continue
        if not line or line[0] not in '+-' or line.startswith(('--- ', '+++ ')):
            continue
        sign, body = line[0], line[1:]
        target = removed if sign == '-' else added
        if current_file.endswith('.json'):
            match = LOCALE_LINE.match(body)
            if match:
                target.add(match.group(2).strip())
        else:
            target |= visible_texts(body, labels[sign])

    gone = sorted(text for text in removed - added if text and not text.startswith(('{', '«')))
    tests_root = Path(worktree, 'reference_scaffold')
    sources = {
        path.relative_to(tests_root).as_posix(): path.read_text(encoding='utf-8', errors='ignore')
        for path in sorted((tests_root / 'tests').rglob('*.py'))
    }
    hit_files: set[str] = set()
    locked = 0
    for text in gone:
        hits = [rel for rel, src in sources.items() if text in src]
        hit_files.update(hits)
        marked = [('LOCKED ' if rel.endswith('_accept.py') else '') + rel for rel in hits]
        locked += sum(rel.endswith('_accept.py') for rel in hits)
        if not files_only:
            print(f'{text!r}: {", ".join(marked) if marked else "-"}')

    if files_only:
        print('\n'.join(sorted(hit_files)))
        return 0
    print(f'entfernte_texte={len(gone)} trefferdateien={len(hit_files)} locked={locked}')
    if locked:
        print('LOCKED: gesperrter Abnahmetest zitiert den Text - Produkttext beibehalten, Label zurücksetzen.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
