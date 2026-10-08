"""DB-free impact selection contracts, including conservative unknown changes."""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))

from _test_gate_impact import build_map, select_tests  # noqa: E402


def test_git_changed_paths_are_exact_with_rtk_and_untracked_files(tmp_path):
    from _test_gate_impact import changed_paths
    def git(*args):
        return subprocess.run(['rtk', 'git', *args], cwd=tmp_path, shell=False,
                              capture_output=True, text=True, check=True)
    git('init', '-q')
    (tmp_path / 'tracked name.py').write_text('old\n')
    git('add', 'tracked name.py')
    git('-c', 'user.name=Gate Test', '-c', 'user.email=gate@example.invalid',
        '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'baseline')
    (tmp_path / 'tracked name.py').write_text('new\n')
    (tmp_path / 'new.py').write_text('new\n')
    assert changed_paths(tmp_path, 'HEAD') == ['new.py', 'tracked name.py']


def test_python_imports_select_transitive_test_consumers(tmp_path):
    base = tmp_path / 'reference_scaffold'
    (base / 'cafeteria').mkdir(parents=True)
    (base / 'tests').mkdir()
    (tmp_path / 'tools').mkdir()
    (base / 'cafeteria' / 'values.py').write_text('VALUE = 1\n')
    (base / 'cafeteria' / 'service.py').write_text('from .values import VALUE\n')
    (base / 'tests' / 'test_service.py').write_text('from cafeteria.service import VALUE\n')
    impact = build_map(tmp_path)
    assert select_tests(['reference_scaffold/cafeteria/values.py'], impact)[0] == ['tests/test_service.py']


def test_unknown_source_and_deleted_tests_expand_to_full_selection():
    impact = {'tests': ['tests/test_a.py', 'tests/test_b.py'], 'files': {}}
    for changed in ['database/new.sql', 'reference_scaffold/tests/test_deleted.py']:
        assert select_tests([changed], impact)[0] == impact['tests']


def test_asset_change_keeps_mapped_tests_and_ui_guardrails():
    impact = {'tests': ['tests/test_logic.py', 'tests/test_public_contracts.py',
                        'tests/test_admin_browser.py', 'tests/test_unrelated.py'],
              'files': {'reference_scaffold/cafeteria/static/main.css': ['tests/test_logic.py']}}
    selected, _ = select_tests(['reference_scaffold/cafeteria/static/main.css'], impact)
    assert set(selected) == {'tests/test_logic.py', 'tests/test_public_contracts.py', 'tests/test_admin_browser.py'}


def test_changed_test_is_always_selected():
    impact = {'tests': ['tests/test_a.py'], 'files': {}}
    assert select_tests(['reference_scaffold/tests/test_a.py'], impact)[0] == impact['tests']
