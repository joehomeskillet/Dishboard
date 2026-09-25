#!/usr/bin/env python3
"""PACKAGE_CONTENTS.txt und MANIFEST_SHA256.txt nur für geänderte Pfade nachführen, danach prüfen.

Usage: sync_manifest.py <worktree> <base>

Ein voller `tools/build_manifest.py` (Schreibmodus) baut aus dem Arbeitsbaum neu und zieht dabei fremde
Artefakte mit. Hier werden nur die getrackten Pfade angefasst, die sich seit git merge-base(<base>, HEAD)
geändert haben (Commits plus nicht committete Änderungen), in der Sortierung des Builders.
Gelöschte Pfade fallen aus beiden Dateien. Anschliessend läuft die Prüfung von build_manifest.py;
Exit 1, wenn sie scheitert.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_manifest import CONTENTS_NAME, MANIFEST_NAME, _is_package_path, verify_files  # noqa: E402


def changed_paths(root: Path, base: str) -> list[str]:
    def git(*args: str) -> str:
        return subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, check=True).stdout

    merge_base = git('merge-base', base, 'HEAD').strip()
    names = set(git('diff', '--no-renames', '--name-only', f'{merge_base}..HEAD').split('\n'))
    names |= set(git('diff', '--no-renames', '--name-only', 'HEAD').split('\n'))
    return sorted(name for name in names if name and _is_package_path(name))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    root = Path(argv[0]).resolve()
    paths = changed_paths(root, argv[1])

    contents_file = root / CONTENTS_NAME
    manifest_file = root / MANIFEST_NAME
    contents = {line for line in contents_file.read_text(encoding='utf-8').splitlines() if line}
    manifest_head: list[str] = []
    manifest_rows: dict[str, str] = {}
    for line in manifest_file.read_text(encoding='utf-8').splitlines():
        if line.startswith('#'):
            manifest_head.append(line)
        elif line.strip():
            digest, rel = line.split('  ', 1)
            manifest_rows[rel] = digest

    added, updated, removed = [], [], []
    for rel in paths:
        target = root / rel
        if not target.is_file():
            if rel in contents or rel in manifest_rows:
                removed.append(rel)
            contents.discard(rel)
            manifest_rows.pop(rel, None)
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if rel not in contents:
            contents.add(rel)
            added.append(rel)
        elif manifest_rows.get(rel) != digest:
            updated.append(rel)
        if rel != MANIFEST_NAME:
            manifest_rows[rel] = digest

    contents_file.write_text('\n'.join(sorted(contents, key=str.casefold)) + '\n', encoding='utf-8')
    # PACKAGE_CONTENTS.txt wurde eben neu geschrieben; sein eigener Hash muss die neuen Bytes spiegeln.
    if CONTENTS_NAME in manifest_rows:
        manifest_rows[CONTENTS_NAME] = hashlib.sha256(contents_file.read_bytes()).hexdigest()
    rows = [f'{manifest_rows[rel]}  {rel}' for rel in sorted(manifest_rows, key=str.casefold)]
    manifest_file.write_text('\n'.join(manifest_head + rows) + '\n', encoding='utf-8')

    print(f'added={len(added)} updated={len(updated)} removed={len(removed)}')
    for label, items in (('added', added), ('updated', updated), ('removed', removed)):
        for rel in items:
            print(f'  {label}: {rel}')

    errors = verify_files(root)
    for error in errors:
        print(f'- {error}')
    print('Manifestprüfung fehlgeschlagen' if errors else 'Paketliste und SHA-256-Manifest: OK')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
