from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / 'reference_scaffold/cafeteria/static/vendor'
LOCK_PATH = VENDOR / 'swagger-ui.lock.json'
VENDOR_SCRIPT = ROOT / 'tools/vendor_swagger_ui.py'


def _sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_locked_assets_match_sha256():
    lock = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    for row in lock['files']:
        path = VENDOR / row['path']
        assert _sha256_hex(path) == row['sha256'], row['path']


def test_vendor_swagger_ui_verify_succeeds():
    result = subprocess.run(
        [sys.executable, str(VENDOR_SCRIPT), '--verify'],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'SWAGGER UI VERIFY:' in result.stdout


@pytest.mark.parametrize('fault', [None, 'modified'])
def test_vendor_swagger_ui_verify_detects_tampering(tmp_path, fault):
    copied_vendor = tmp_path / 'vendor'
    shutil.copytree(VENDOR, copied_vendor)
    lock = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    artifact = copied_vendor / lock['files'][0]['path']
    if fault == 'modified':
        artifact.write_bytes(artifact.read_bytes() + b'\n/* changed */\n')
    result = subprocess.run(
        [
            sys.executable,
            str(VENDOR_SCRIPT),
            '--verify',
            '--output-dir',
            str(copied_vendor),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if fault is None:
        assert result.returncode == 0
        assert 'SWAGGER UI VERIFY:' in result.stdout
    else:
        assert result.returncode != 0
        assert 'SHA256 mismatch' in result.stderr
