#!/usr/bin/env python3
"""Verify or reproduce pinned local Tabler assets without npm or runtime downloads."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'reference_scaffold/cafeteria/static/vendor'
LOCK = VENDOR / 'tabler.lock.json'
MAX_BYTES = 25 * 1024 * 1024
ALLOWED_HOSTS = {'registry.npmjs.org', 'raw.githubusercontent.com'}


def check_hash(data: bytes, expected: str, label: str) -> None:
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'SHA256 mismatch: {label}')


def destination(output: Path, relative: str) -> Path:
    path = output / relative
    if not path.resolve().is_relative_to(output.resolve()):
        raise ValueError(f'Output path escapes target: {relative}')
    return path


def source_bytes(source: dict[str, Any], cache: Path | None) -> bytes:
    cached = cache / source['id'] if cache else None
    if cached and cached.is_file():
        data = cached.read_bytes()
    else:
        url = urllib.parse.urlsplit(source['url'])
        if (url.scheme != 'https' or url.hostname not in ALLOWED_HOSTS
                or url.username or url.password or url.query or url.fragment):
            raise ValueError('Source must use the pinned official HTTPS host')
        with urllib.request.urlopen(source['url'], timeout=45) as response:
            data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Source exceeds size limit')
    check_hash(data, source['sha256'], source['id'])
    if source.get('integrity'):
        integrity = 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()
        if integrity != source['integrity']:
            raise ValueError(f"Registry integrity mismatch: {source['id']}")
    if cached and not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return data


def member_bytes(archive: tarfile.TarFile, name: str) -> bytes:
    member = archive.getmember(name)
    if not member.isfile() or member.size > MAX_BYTES:
        raise ValueError(f'Invalid package member: {name}')
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f'Missing package member: {name}')
    return stream.read()


def sprite(archive: tarfile.TarFile, names: list[str], version: str) -> bytes:
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg">',
        f'<!-- Tabler Icons {version} (MIT, https://github.com/tabler/tabler-icons) '
        '— outline subset, built from the official npm package SVG files. See ../README.md. -->',
    ]
    attributes = ('viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"')
    for name in names:
        if not re.fullmatch(r'[a-z0-9-]+', name):
            raise ValueError('Invalid icon name')
        svg = member_bytes(archive, f'package/icons/outline/{name}.svg').decode()
        inner = ' '.join(svg.split('>', 1)[1].rsplit('</svg>', 1)[0].split())
        lines.append(f'<symbol id="tabler-{name}" {attributes}>{inner}</symbol>')
    return ('\n'.join(lines + ['</svg>']) + '\n').encode()


def build(lock: dict[str, Any], output: Path, cache: Path | None) -> None:
    sources = {row['id']: source_bytes(row, cache) for row in lock['sources']}
    pending = []
    for row in lock['files']:
        data = sources[row['source']]
        if 'member' in row or 'icons' in row:
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
                data = (sprite(archive, row['icons'], lock['packages']['@tabler/icons'])
                        if 'icons' in row else member_bytes(archive, row['member']))
        check_hash(data, row['sha256'], row['path'])
        pending.append((destination(output, row['path']), data))
    # Validate every source and result before replacing any vendored artifact.
    changed = 0
    for path, data in pending:
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
        changed += 1
    print(f'TABLER BUILD: {len(pending)} verified artifacts; {changed} changed.')


def verify(lock: dict[str, Any], output: Path) -> None:
    for row in lock['files']:
        path = destination(output, row['path'])
        check_hash(path.read_bytes(), row['sha256'], row['path'])
    print(f"TABLER VERIFY: {len(lock['files'])} artifacts match tabler.lock.json.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify', action='store_true', help='Offline hash check; no writes')
    action.add_argument('--build', action='store_true', help='Download/copy the locked artifacts')
    parser.add_argument('--output-dir', type=Path, default=VENDOR)
    parser.add_argument('--cache-dir', type=Path, help='Optional verified source cache')
    args = parser.parse_args()
    try:
        lock = json.loads(LOCK.read_text())
        if lock['schema_version'] != 1:
            raise ValueError('Unsupported lock schema')
        if args.build:
            build(lock, args.output_dir, args.cache_dir)
        verify(lock, args.output_dir)
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
