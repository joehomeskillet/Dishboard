"""Run the real post-deploy phase with a stub-only PATH and isolated state."""
from pathlib import Path
import json
import shlex
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name('hourly_train.sh')
SHA = 'a' * 40
STUB = r'''
import json, os, sys, time
from pathlib import Path
p = Path(os.environ['STUB_DATA'])
d = json.loads(p.read_text())
name, args = Path(sys.argv[0]).name, sys.argv[1:]
with Path(os.environ['STUB_CALLS']).open('a') as out:
    out.write(json.dumps([name, *args]) + '\n')
if name == 'systemctl':
    assert args == ['start', 'dishboard-deploy-main.service']
    sys.exit(d.get('deploy_exit', 0))
elif name == 'timeout':
    assert args[1] == 'docker'
    os.execv(str(Path(sys.argv[0]).parent / 'docker'), ['docker', *args[2:]])
elif name == 'docker':
    assert args[0] == 'inspect' and args[-1] == 'suedhang-cafeteria-app-1'
    if d.get('inspect_exit'):
        sys.exit(d['inspect_exit'])
    i = min(d.get('index', 0), len(d['health']) - 1)
    d['last_health'] = d['health'][i]
    d['index'] = d.get('index', 0) + 1
    p.write_text(json.dumps(d))
    print(d['live'], d['last_health'])
elif name == 'sleep':
    if d.get('expire'):
        time.sleep(1.1)
elif name == 'bash':
    assert args[-1] == 'integrate/test'
    assert args[0].endswith('/tools/release/deploy_status.sh')
    assert os.environ['DISHBOARD_EXPECTED_REVISION'] == 'a' * 40
    good = d['live'] == 'a' * 40 and d.get('last_health', d['health'][0]) == 'healthy'
    sys.exit(d.get('status_exit', 0) if good else 1)
elif name == 'date':
    print('2026-09-28T05:00:00Z')
elif name == 'mv':
    Path(args[0]).rename(args[1])
elif name == 'rm':
    Path(args[-1]).unlink(missing_ok=True)
else:
    raise AssertionError((name, args))
'''


class ReadinessTests(unittest.TestCase):
    def run_phase(self, health, **changes):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / 'bin'
            binaries.mkdir()
            driver = binaries / 'stub'
            driver.write_text(f'#!{sys.executable}\n' + STUB)
            driver.chmod(0o700)
            for name in ('systemctl', 'timeout', 'docker', 'sleep', 'bash', 'date', 'mv', 'rm'):
                (binaries / name).symlink_to(driver)
            data = dict(health=health, live=SHA)
            data.update(changes)
            config, calls = root / 'data.json', root / 'calls.jsonl'
            config.write_text(json.dumps(data))
            source = SCRIPT.read_text().split('STEP=Deploy\n', 1)[1]
            if changes.get('expire'):
                source = source.replace('SECONDS + 60', 'SECONDS + 1')
            prefix = 'set -euo pipefail\n' + ''.join(
                f'{key}={shlex.quote(value)}\n' for key, value in
                dict(OUT=str(root), STATE=str(root), WT=str(root), SHA=SHA,
                     LINE='integrate/test').items())
            script = root / 'phase.sh'
            script.write_text(prefix + source)
            (root / 'ALERT').write_text('old alert')
            result = subprocess.run(['/bin/bash', str(script)], text=True, capture_output=True,
                                    env={'PATH': str(binaries), 'STUB_DATA': str(config),
                                         'STUB_CALLS': str(calls)}, timeout=5, check=False)
            invocations = [json.loads(row) for row in calls.read_text().splitlines()]
            self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(sum(c[0] == 'systemctl' for c in invocations), 1)
            return result, invocations, (root / 'last_success').exists(), (root / 'ALERT').exists()

    def test_starting_then_healthy_waits_before_final_status(self):
        result, calls, success, alert = self.run_phase(['starting', 'starting', 'healthy'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(c[0] == 'docker' for c in calls), 3)
        self.assertEqual(sum(c[0] == 'bash' for c in calls), 1)
        self.assertTrue(success)
        self.assertFalse(alert)

    def test_terminal_health_or_revision_failure_never_waits(self):
        for changes in ({'health': ['unhealthy']}, {'health': ['ohne-healthcheck']},
                        {'health': ['starting'], 'live': 'b' * 40}):
            with self.subTest(changes=changes):
                result, calls, success, alert = self.run_phase(**changes)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(any(c[0] in ('sleep', 'bash') for c in calls))
                self.assertFalse(success)
                self.assertTrue(alert)

    def test_starting_deadline_fails_without_final_success(self):
        result, calls, success, alert = self.run_phase(['starting'], expire=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(any(c[0] == 'sleep' for c in calls))
        self.assertFalse(any(c[0] == 'bash' for c in calls))
        self.assertFalse(success)
        self.assertTrue(alert)

    def test_inspect_failure_is_fatal(self):
        result, calls, success, _ = self.run_phase(['starting'], inspect_exit=1)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(any(c[0] in ('sleep', 'bash') for c in calls))
        self.assertFalse(success)

    def test_final_status_and_deploy_failures_are_preserved(self):
        for changes, expected in (({'status_exit': 1}, 1), ({'status_exit': 2}, 2),
                                  ({'deploy_exit': 7}, 7), ({}, 0)):
            with self.subTest(changes=changes):
                result, calls, success, alert = self.run_phase(['healthy'], **changes)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertFalse(any(c[0] == 'sleep' for c in calls))
                self.assertEqual(success, expected == 0)
                self.assertEqual(alert, expected != 0)


if __name__ == '__main__':
    unittest.main()
