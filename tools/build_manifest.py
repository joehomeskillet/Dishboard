#!/usr/bin/env python3
"""Erzeugt oder prüft Paketliste und SHA-256-Manifest.

MANIFEST_SHA256.txt enthält absichtlich keinen Hash für sich selbst. Die Datei
PACKAGE_CONTENTS.txt enthält dagegen sämtliche ausgelieferten Dateien.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path, PurePosixPath

CONTENTS_NAME = 'PACKAGE_CONTENTS.txt'
MANIFEST_NAME = 'MANIFEST_SHA256.txt'
EXCLUDED_DIRS = {
    '__pycache__', '.pytest_cache', '.git', '.mypy_cache', '.ruff_cache',
    '.claude', '.playwright-mcp', '.serena', '.vscode',
}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo'}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _is_package_path(relative: PurePosixPath | Path) -> bool:
    posix = relative.as_posix() if isinstance(relative, Path) else str(relative)
    parts = PurePosixPath(posix).parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return False
    if PurePosixPath(posix).suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if PurePosixPath(posix).name in {'.DS_Store', 'Thumbs.db'}:
        return False
    if posix == 'deployment/.env':
        return False
    return True


def _tracked_relative_paths(root: Path) -> set[str] | None:
    try:
        result = subprocess.run(
            ['git', 'ls-files', '-z'],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return {
        path
        for path in result.stdout.decode('utf-8', 'surrogateescape').split('\0')
        if path
    }


def included_files(root: Path) -> list[Path]:
    tracked = _tracked_relative_paths(root)
    if tracked is not None:
        files: list[Path] = []
        for relative_posix in sorted(tracked, key=str.casefold):
            if not _is_package_path(relative_posix):
                continue
            path = root / relative_posix
            if path.is_file() and not path.is_symlink():
                files.append(path)
        return files

    files: list[Path] = []
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if not _is_package_path(relative):
            continue
        files.append(path)
    return sorted(files, key=lambda value: value.relative_to(root).as_posix().casefold())


def write_files(root: Path) -> None:
    contents_path = root / CONTENTS_NAME
    manifest_path = root / MANIFEST_NAME

    # Beide Zieldateien müssen in der Inhaltsliste stehen, auch bei einem
    # erstmaligen Lauf.
    contents_path.touch(exist_ok=True)
    manifest_path.touch(exist_ok=True)

    files = included_files(root)
    relative_names = [path.relative_to(root).as_posix() for path in files]
    contents_path.write_text('\n'.join(relative_names) + '\n', encoding='utf-8')

    # PACKAGE_CONTENTS.txt wurde gerade verändert; Dateiliste nochmals holen.
    files = included_files(root)
    lines = [
        '# SHA-256  relative/path',
        '# MANIFEST_SHA256.txt ist wegen Selbstreferenz von der Hashliste ausgenommen.',
    ]
    for path in files:
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        lines.append(f'{sha256(path)}  {relative}')
    manifest_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def verify_files(root: Path) -> list[str]:
    errors: list[str] = []
    contents_path = root / CONTENTS_NAME
    manifest_path = root / MANIFEST_NAME
    if not contents_path.is_file():
        errors.append(f'{CONTENTS_NAME} fehlt.')
        return errors
    if not manifest_path.is_file():
        errors.append(f'{MANIFEST_NAME} fehlt.')
        return errors

    expected_contents = [path.relative_to(root).as_posix() for path in included_files(root)]
    listed_contents = [line.strip() for line in contents_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if listed_contents != expected_contents:
        missing = sorted(set(expected_contents) - set(listed_contents))
        stale = sorted(set(listed_contents) - set(expected_contents))
        if missing:
            errors.append(f'In PACKAGE_CONTENTS.txt fehlen: {missing}')
        if stale:
            errors.append(f'In PACKAGE_CONTENTS.txt sind veraltete Einträge: {stale}')
        if not missing and not stale:
            errors.append('PACKAGE_CONTENTS.txt ist nicht deterministisch sortiert.')

    manifest_entries: dict[str, str] = {}
    for line_number, raw in enumerate(manifest_path.read_text(encoding='utf-8').splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        try:
            digest, relative = line.split('  ', 1)
        except ValueError:
            errors.append(f'Ungültige Manifestzeile {line_number}: {raw!r}')
            continue
        if len(digest) != 64 or any(char not in '0123456789abcdef' for char in digest):
            errors.append(f'Ungültiger SHA-256 in Zeile {line_number}.')
            continue
        normalized = PurePosixPath(relative).as_posix()
        if normalized in manifest_entries:
            errors.append(f'Doppelter Manifestpfad: {normalized}')
        manifest_entries[normalized] = digest

    expected_manifest_paths = {
        path.relative_to(root).as_posix()
        for path in included_files(root)
        if path.relative_to(root).as_posix() != MANIFEST_NAME
    }
    missing_hashes = sorted(expected_manifest_paths - set(manifest_entries))
    stale_hashes = sorted(set(manifest_entries) - expected_manifest_paths)
    if missing_hashes:
        errors.append(f'Hash fehlt für: {missing_hashes}')
    if stale_hashes:
        errors.append(f'Hash verweist auf nicht ausgelieferte Datei: {stale_hashes}')

    for relative, expected_digest in manifest_entries.items():
        path = root / Path(relative)
        if path.is_file():
            actual = sha256(path)
            if actual != expected_digest:
                errors.append(f'Checksumme abweichend: {relative}')

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--verify', action='store_true', help='Vorhandene Dateien prüfen statt neu schreiben.')
    args = parser.parse_args()
    root = args.root.resolve()

    if args.verify:
        errors = verify_files(root)
        if errors:
            print('Manifestprüfung fehlgeschlagen:')
            for error in errors:
                print(f'- {error}')
            return 1
        print('Paketliste und SHA-256-Manifest: OK')
        return 0

    write_files(root)
    print(root / CONTENTS_NAME)
    print(root / MANIFEST_NAME)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
