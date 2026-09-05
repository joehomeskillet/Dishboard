#!/usr/bin/env python3
"""Verify or reproduce pinned local Swagger UI assets without npm or runtime downloads."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'reference_scaffold/cafeteria/static/vendor'
LOCK = VENDOR / 'swagger-ui.lock.json'
OUTPUT_SUBDIR = 'swagger-ui'
DIST_URL = 'https://registry.npmjs.org/swagger-ui-dist/-/swagger-ui-dist-5.32.15.tgz'
DIST_INTEGRITY = (
    'sha512-TSFER+rFQlf1nzk6WvKkMaHTxAPQ3eAAxigFThnxQedSREanfZgSbJFayZVs/ULnSbNdrJOb99vLD6xpb3R3eg=='
)
LICENSE_URL = 'https://raw.githubusercontent.com/swagger-api/swagger-ui/v5.32.15/LICENSE'
MAX_BYTES = 25 * 1024 * 1024
ALLOWED_HOSTS = {'registry.npmjs.org', 'raw.githubusercontent.com'}
MEMBERS = {
    'swagger-ui.css': 'package/swagger-ui.css',
    'swagger-ui-bundle.js': 'package/swagger-ui-bundle.js',
    'LICENSE': 'package/LICENSE',
}


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


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_lock(dist_data: bytes, license_data: bytes | None) -> dict[str, Any]:
    sources: list[dict[str, Any]] = [
        {
            'id': 'dist',
            'url': DIST_URL,
            'sha256': sha256_hex(dist_data),
            'integrity': DIST_INTEGRITY,
        },
    ]
    files: list[dict[str, Any]] = []
    with tarfile.open(fileobj=io.BytesIO(dist_data), mode='r:gz') as archive:
        for filename, member in MEMBERS.items():
            if filename == 'LICENSE':
                continue
            data = member_bytes(archive, member)
            files.append({
                'path': f'{OUTPUT_SUBDIR}/{filename}',
                'source': 'dist',
                'member': member,
                'sha256': sha256_hex(data),
            })
        try:
            license_member = member_bytes(archive, MEMBERS['LICENSE'])
        except (KeyError, ValueError):
            license_member = None
    if license_member is not None:
        files.append({
            'path': f'{OUTPUT_SUBDIR}/LICENSE',
            'source': 'dist',
            'member': MEMBERS['LICENSE'],
            'sha256': sha256_hex(license_member),
        })
    else:
        if license_data is None:
            raise ValueError('LICENSE missing from tarball and no fallback source provided')
        sources.append({
            'id': 'license',
            'url': LICENSE_URL,
            'sha256': sha256_hex(license_data),
        })
        files.append({
            'path': f'{OUTPUT_SUBDIR}/LICENSE',
            'source': 'license',
            'sha256': sha256_hex(license_data),
        })
    return {
        'schema_version': 1,
        'packages': {'swagger-ui-dist': '5.32.15'},
        'sources': sources,
        'files': files,
    }


def download_dist(cache: Path | None) -> bytes:
    url = urllib.parse.urlsplit(DIST_URL)
    if url.scheme != 'https' or url.hostname not in ALLOWED_HOSTS:
        raise ValueError('Source must use the pinned official HTTPS host')
    cached = cache / 'dist' if cache else None
    if cached and cached.is_file():
        data = cached.read_bytes()
    else:
        with urllib.request.urlopen(DIST_URL, timeout=45) as response:
            data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Source exceeds size limit')
    integrity = 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()
    if integrity != DIST_INTEGRITY:
        raise ValueError('Registry integrity mismatch: dist')
    if cached and not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return data


def download_license(cache: Path | None) -> bytes:
    cached = cache / 'license' if cache else None
    if cached and cached.is_file():
        return cached.read_bytes()
    with urllib.request.urlopen(LICENSE_URL, timeout=45) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Source exceeds size limit')
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return data


def build(lock: dict[str, Any], output: Path, cache: Path | None) -> None:
    sources = {row['id']: source_bytes(row, cache) for row in lock['sources']}
    pending = []
    for row in lock['files']:
        data = sources[row['source']]
        if 'member' in row:
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
                data = member_bytes(archive, row['member'])
        check_hash(data, row['sha256'], row['path'])
        pending.append((destination(output, row['path']), data))
    changed = 0
    for path, data in pending:
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
        changed += 1
    print(f'SWAGGER UI BUILD: {len(pending)} verified artifacts; {changed} changed.')


def verify(lock: dict[str, Any], output: Path) -> None:
    for row in lock['files']:
        path = destination(output, row['path'])
        check_hash(path.read_bytes(), row['sha256'], row['path'])
    print(f"SWAGGER UI VERIFY: {len(lock['files'])} artifacts match swagger-ui.lock.json.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify', action='store_true', help='Offline hash check; no writes')
    action.add_argument('--build', action='store_true', help='Download/copy the locked artifacts')
    parser.add_argument('--write-lock', action='store_true', help='Write swagger-ui.lock.json from sources')
    parser.add_argument('--output-dir', type=Path, default=VENDOR)
    parser.add_argument('--cache-dir', type=Path, help='Optional verified source cache')
    args = parser.parse_args()
    try:
        if args.write_lock:
            dist_data = download_dist(args.cache_dir)
            license_data = None
            with tarfile.open(fileobj=io.BytesIO(dist_data), mode='r:gz') as archive:
                try:
                    member_bytes(archive, MEMBERS['LICENSE'])
                except (KeyError, ValueError):
                    license_data = download_license(args.cache_dir)
            lock = build_lock(dist_data, license_data)
            LOCK.parent.mkdir(parents=True, exist_ok=True)
            LOCK.write_text(json.dumps(lock, indent=2) + '\n')
            print(f'SWAGGER UI LOCK: wrote {LOCK}.')
        if not LOCK.is_file():
            raise ValueError('swagger-ui.lock.json is missing; run with --build --write-lock first')
        lock = json.loads(LOCK.read_text())
        if lock['schema_version'] != 1:
            raise ValueError('Unsupported lock schema')
        if args.build:
            build(lock, args.output_dir, args.cache_dir)
        if args.verify or args.build:
            verify(lock, args.output_dir)
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
