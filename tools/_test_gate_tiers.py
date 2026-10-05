"""Static gate commands; no package installation or service activation."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path


def run_static(root: Path, python: str, output: Path) -> int:
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    commands = []
    if shutil.which('ruff'):
        commands.append(['rtk', 'ruff', 'check', 'tools/test_gate.py', 'tools/_test_gate_results.py',
                         'tools/_test_gate_pools.py', 'tools/_test_gate_browser.py',
                         'tools/_test_gate_impact.py', 'tools/_test_gate_tiers.py',
                         'reference_scaffold/tests/_support', 'reference_scaffold/tests/conftest.py'])
    commands.extend([
        ['rtk', python, str(root / 'tools/test_template_syntax.py')],
        ['rtk', python, str(root / 'tools/build_manifest.py'), '--verify'],
        ['rtk', python, str(root / 'tools/validate_package.py'), '--offline'],
    ])
    results = []
    for index, command in enumerate(commands):
        start = time.monotonic()
        result = subprocess.run(command, cwd=root, shell=False, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / f'check-{index}.log').write_text(result.stdout)
        results.append({'command': command, 'exit': result.returncode,
                        'seconds': time.monotonic() - start})
        print(f'Tier 0: {command[2]} exit={result.returncode} '
              f'{results[-1]["seconds"]:.2f}s; {output / f"check-{index}.log"}', flush=True)
    (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    return int(any(result['exit'] != 0 for result in results))
