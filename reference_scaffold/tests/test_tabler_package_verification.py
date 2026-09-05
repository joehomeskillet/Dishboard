from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('tabler_package_validator', ROOT / 'tools/validate_package.py')
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


@pytest.mark.parametrize('fault', [None, 'modified', 'missing'])
def test_package_offline_gate_reports_real_locked_asset_result(tmp_path, monkeypatch, capsys, fault):
    vendor = ROOT / 'reference_scaffold/cafeteria/static/vendor'
    copied_vendor = tmp_path / 'vendor'
    shutil.copytree(vendor, copied_vendor)
    lock = json.loads((vendor / 'tabler.lock.json').read_text())
    artifact = copied_vendor / lock['files'][0]['path']
    if fault == 'modified':
        artifact.write_bytes(artifact.read_bytes() + b'\n/* changed */\n')
    elif fault == 'missing':
        artifact.unlink()
    actual_run = validator.run
    invoked = []

    def bounded_run(command, cwd):
        if command[1:2] == ['tools/vendor_tabler.py']:
            invoked.append((command, cwd))
            # Run the real offline verifier against an isolated artifact copy.
            return actual_run([*command, '--output-dir', str(copied_vendor)], cwd)
        if command[1:3] == ['-m', 'pytest']:
            # Avoid recursively executing this suite or acquiring a DB/browser slot.
            return subprocess.CompletedProcess(command, 0, 'Focused subprocess gate stub\n', '')
        return actual_run(command, cwd)

    monkeypatch.setattr(validator, 'run', bounded_run)
    monkeypatch.setattr(sys, 'argv', ['validate_package.py', '--root', str(ROOT), '--offline'])
    result = validator.main()
    output = capsys.readouterr().out
    assert invoked == [([sys.executable, 'tools/vendor_tabler.py', '--verify'], ROOT)]
    if fault is None:
        assert '[OK] TABLER VERIFY:' in output
        assert '[FEHLER] Tabler-Artefakte' not in output
    else:
        assert result == 1
        assert '[FEHLER] Tabler-Artefakte stimmen nicht mit dem Lock überein:' in output
        assert '[OK] TABLER VERIFY:' not in output
        assert ('SHA256 mismatch' if fault == 'modified' else 'No such file') in output
    # Other package issues (e.g. checkout metadata) are outside this focused gate.


@pytest.mark.parametrize('fault', [None, 'reference_only', 'hex_tokens', 'hex_app'])
def test_package_checks_extracted_css_definitions_and_both_hex_boundaries(monkeypatch, capsys, fault):
    actual_read = Path.read_text
    actual_run = validator.run
    tokens_path = ROOT / 'reference_scaffold/cafeteria/static/tokens.css'
    app_path = tokens_path.with_name('app.css')

    def read(path, *args, **kwargs):
        value = actual_read(path, *args, **kwargs)
        if path == tokens_path and fault == 'reference_only':
            value, removed = re.subn(r'^\s*--sh-primary:\s*[^;]+;\s*$', '', value, flags=re.M)
            assert removed == 1
            value += '\n/* --sh-primary: comment is not a definition */\n'
        if (path == tokens_path and fault == 'hex_tokens') or (path == app_path and fault == 'hex_app'):
            value += '\n.unmapped-color { color: #123456; }\n'
        return value

    def bounded_run(command, cwd):
        if command[1:3] == ['-m', 'pytest']:
            return subprocess.CompletedProcess(command, 0, 'Focused subprocess gate stub\n', '')
        return actual_run(command, cwd)

    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(validator, 'run', bounded_run)
    monkeypatch.setattr(sys, 'argv', ['validate_package.py', '--root', str(ROOT), '--offline'])
    result = validator.main()
    output = capsys.readouterr().out
    missing = '[FEHLER] Scaffold-CSS fehlen Prototype-Tokens:'
    hex_error = '[FEHLER] Scaffold-CSS enthaelt Hard-Coded Hex-Farben ausserhalb :root:'
    if fault == 'reference_only':
        assert 'var(--sh-primary)' in actual_read(app_path)
        assert result == 1 and missing + " ['--sh-primary']" in output
    else:
        assert missing not in output
    if fault in {'hex_tokens', 'hex_app'}:
        assert result == 1 and hex_error in output
        assert ('tokens.css Line' if fault == 'hex_tokens' else 'app.css Line') in output
    else:
        assert hex_error not in output
