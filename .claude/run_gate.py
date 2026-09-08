"""Capture only this worktree's authorized focused pool gate, without credentials."""
from pathlib import Path
import os
import re
import subprocess
import sys
import time

os.umask(0o077)
root = Path(__file__).resolve().parents[1]
assert root.name == 'prepared-food-schema27-0909'
command = ['rtk', '/nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test-prepared-food-schema27-0909-gate.sh',
           str(root), '-q', '-p', 'no:cacheprovider', '--tb=short', *sys.argv[1:]]
result = subprocess.run(command, capture_output=True, text=True, check=False,
                        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
output = result.stdout + result.stderr
output = re.sub(r'postgres(?:ql)?(?:\+\w+)?://[^\s\x27\x22<>]+', '[REDACTED-DB-URL]', output)
output = re.sub(r'rediss?://[^\s\x27\x22<>]+', '[REDACTED-REDIS-URL]', output)
path = Path(__file__).resolve().parent / f'gate-{time.time_ns()}.log'
path.write_text('ARGV=' + repr(command) + '\n' + output + f'\nEXIT_CODE={result.returncode}\n')
print(output, end='')
print(f'CAPTURE={path.name} EXIT_CODE={result.returncode}')
raise SystemExit(result.returncode)
