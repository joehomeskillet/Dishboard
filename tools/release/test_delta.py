#!/usr/bin/env python3
"""Je geänderter Testdatei: Testfunktionen, assert/expect und skip/xfail vorher/nachher.

Usage: test_delta.py <worktree> <base>
Verglichen wird ab git merge-base(<base>, HEAD), damit ein inzwischen weitergerücktes main keine
fremden Änderungen als Verluste zeigt. Exit 1, wenn eine Datei Tests oder Assertions verliert
oder neue skip/xfail bekommt (Markierung «<-- CHECK»), sonst 0.
"""
from __future__ import annotations

import re
import subprocess
import sys


def git(worktree: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', '-C', worktree, *args], capture_output=True, text=True, check=check)


def stats(src: str) -> tuple[set[str], int, int, int]:
    return (set(re.findall(r'^\s*def (test_\w+)', src, re.M)),
            len(re.findall(r'\bassert\b', src)), len(re.findall(r'\bexpect\(', src)),
            len(re.findall(r'pytest\.mark\.(?:skip|xfail)|pytest\.skip\(|pytest\.xfail\(', src)))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    worktree, base = argv
    merge_base = git(worktree, 'merge-base', base, 'HEAD').stdout.strip()
    files = git(worktree, 'diff', '--no-renames', '--name-only', f'{merge_base}..HEAD', '--',
                'reference_scaffold/tests').stdout.split()

    def load(rev: str, path: str) -> str:
        out = git(worktree, 'show', f'{rev}:{path}', check=False)
        return out.stdout if out.returncode == 0 else ''

    problems = 0
    for path in files:
        before, after = stats(load(merge_base, path)), stats(load('HEAD', path))
        removed = sorted(before[0] - after[0])
        flag = removed or after[1] + after[2] < before[1] + before[2] or after[3] > before[3]
        problems += bool(flag)
        print(f'{path}: tests {len(before[0])}->{len(after[0])} asserts {before[1]}->{after[1]} '
              f'expects {before[2]}->{after[2]} skips {before[3]}->{after[3]}'
              + (f' removed={removed}' if removed else '') + (' <-- CHECK' if flag else ''))
    print(f'basis={merge_base[:10]} files={len(files)} flagged={problems}')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
