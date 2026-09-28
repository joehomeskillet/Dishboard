"""Exercise the real status shell with isolated state and no host command access."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name('deploy_status.sh')
LIVE = 'a' * 40
STUB = r'''
import json
import os
from pathlib import Path
import sys

data = json.loads(Path(os.environ['STUB_DATA']).read_text())
command, args = Path(sys.argv[0]).name, sys.argv[1:]
with Path(os.environ['STUB_CALLS']).open('a') as stream:
    stream.write(json.dumps([command, *args]) + '\n')
if command == 'dirname':
    print(os.path.dirname(args[0]))
elif command == 'cat':
    path = Path(args[0]).resolve()
    assert path.parent == Path(data['state']).resolve(), path
    print(path.read_text(), end='')
elif command == 'docker':
    assert args[0] == 'inspect' and args[-1] == 'suedhang-cafeteria-app-1', args
    if data.get('container_missing'):
        sys.exit(1)
    print(data['live'], 'synthetic-start', data['health'])
elif command == 'curl':
    assert args[-1] == 'http://127.0.0.1:8789/auth/login', args
    print(data['login'], end='')
    sys.exit(data.get('curl_exit', 0))
elif command == 'date':
    if args == ['+%s']:
        print(data['now'])
    elif args == ['-d', 'synthetic-start', '+%s']:
        print(data['now'] - data['age'] * 60)
    elif args == ['-d', 'synthetic-start', '+%Y-%m-%d %H:%M %Z']:
        print('2026-09-28 00:00 UTC')
    else:
        raise AssertionError(args)
elif command == 'git':
    assert args[0] == '-C', args
    args = args[2:]
    if args[:2] == ['rev-parse', '--short=10']:
        assert args[2] in ('main', 'github/main'), args
        print('b' * 10 if args[2] == 'main' else 'c' * 10)
    elif args == ['for-each-ref', '--format=%(refname:short)', 'refs/heads/integrate/']:
        if data.get('refs_error'):
            sys.exit(1)
        print('\n'.join(name for name in data['branches'] if name.startswith('integrate/')))
    elif args[:2] == ['rev-list', '--count']:
        if args[2] == data['live'] + '..github/main':
            print(4)
        else:
            assert args[2].startswith('github/main..'), args
            branch = data['branches'].get(args[2].removeprefix('github/main..'))
            if branch is None:
                sys.exit(128)
            print(branch['ahead'])
    elif args[:3] == ['log', '-1', '--format=%ct']:
        branch = data['branches'].get(args[3])
        if branch is None:
            sys.exit(128)
        print(data['now'] - branch.get('tip_age', 0))
    else:
        raise AssertionError(args)
else:
    raise AssertionError(command)
'''


class DeployStatusTests(unittest.TestCase):
    def run_status(self, *arguments, branches=None, line='integrate/train',
                   environment=None, **changes):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'state'
            state.mkdir()
            if line is not None:
                (state / 'line').write_text(line + '\n')
            (state / 'last_success').write_text('synthetic-success\n')
            (state / 'ALERT').write_text('synthetic-alert\n')
            source = SCRIPT.read_text()
            # Only redirect the fixed state path in the test copy. Production has no test override.
            self.assertEqual(source.count('STATE=/var/lib/dishboard-release-train\n'), 1)
            source = source.replace('STATE=/var/lib/dishboard-release-train\n', f'STATE="{state}"\n')
            script = root / 'tools/release/deploy_status.sh'
            script.parent.mkdir(parents=True)
            script.write_text(source)
            binaries = root / 'bin'
            binaries.mkdir()
            driver = binaries / 'stub'
            driver.write_text(f'#!{sys.executable}\n' + STUB)
            driver.chmod(0o700)
            for name in ('dirname', 'cat', 'docker', 'curl', 'date', 'git'):
                (binaries / name).symlink_to(driver)
            data = dict(live=LIVE, health='healthy', login='200', now=1_800_000_000,
                        age=121, state=str(state), branches=branches if branches is not None
                        else {'integrate/train': {'ahead': 0}})
            data.update(changes)
            config, calls = root / 'stub.json', root / 'calls.jsonl'
            config.write_text(json.dumps(data))
            env = {'PATH': str(binaries), 'STUB_DATA': str(config), 'STUB_CALLS': str(calls)}
            env.update(environment or {})
            # Fixed interpreter, test-owned script and arguments, and a stub-only PATH.
            result = subprocess.run(['/bin/bash', str(script), *arguments], env=env,  # noqa: S603
                                    text=True, capture_output=True, timeout=10, check=False)
            invocations = [json.loads(row) for row in calls.read_text().splitlines()]
            self.assertNotIn('Traceback', result.stderr)
            return result, invocations

    def test_discovers_other_active_lines_but_only_lists_stale_lines(self):
        result, _ = self.run_status(branches={
            'integrate/train': {'ahead': 0},
            'integrate/active': {'ahead': 3, 'tip_age': 6 * 86400},
            'integrate/stale': {'ahead': 9, 'tip_age': 7 * 86400},
        })
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('integrate/active: 3 Commits vor github/main', result.stdout)
        self.assertIn('integrate/stale: 9 Commits vor github/main', result.stdout)
        self.assertIn('3 Commits warten in integrate/active', result.stdout)
        self.assertNotIn('9 Commits warten', result.stdout)
        self.assertEqual(result.stdout.count('integrate/train: 0 Commits'), 1)

    def test_stale_discovered_lines_do_not_make_train_overdue(self):
        result, _ = self.run_status(branches={
            'integrate/train': {'ahead': 0}, 'integrate/old': {'ahead': 5, 'tip_age': 8 * 86400},
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('integrate/old: 5 Commits', result.stdout)
        self.assertIn('STATUS: OK', result.stdout)

    def test_all_explicit_arguments_are_checked_without_discovery(self):
        result, calls = self.run_status('fix/first', 'fix/second', branches={
            'fix/first': {'ahead': 0}, 'fix/second': {'ahead': 2, 'tip_age': 8 * 86400},
            'integrate/other': {'ahead': 5},
        })
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('fix/first: 0 Commits', result.stdout)
        self.assertIn('fix/second: 2 Commits', result.stdout)
        self.assertIn('2 Commits warten in fix/second', result.stdout)
        self.assertNotIn('integrate/other', result.stdout)
        self.assertFalse(any('for-each-ref' in call for call in calls))

    def test_selected_train_keeps_current_age_rule_even_with_an_old_tip(self):
        for age, expected in ((120, 0), (121, 1)):
            with self.subTest(age=age):
                result, _ = self.run_status(age=age, branches={
                    'integrate/train': {'ahead': 1, 'tip_age': 8 * 86400},
                })
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_default_precedence_and_single_explicit_line(self):
        cases = [
            ((), 'fix/configured', {'DISHBOARD_INTEGRATION_BRANCH': 'fix/env'}, 'fix/configured'),
            ((), None, {'DISHBOARD_INTEGRATION_BRANCH': 'fix/env'}, 'fix/env'),
            ((), None, {}, 'integrate/uiux-0920'),
            (('fix/explicit',), 'fix/configured', {'DISHBOARD_INTEGRATION_BRANCH': 'fix/env'}, 'fix/explicit'),
        ]
        for arguments, line, environment, expected in cases:
            with self.subTest(expected=expected):
                result, _ = self.run_status(*arguments, line=line, environment=environment,
                                            branches={expected: {'ahead': 0}})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected + ': 0 Commits vor github/main', result.stdout)
                self.assertIn('Zug-Linie:     ' + (line or 'nicht konfiguriert'), result.stdout)

    def test_state_and_missing_container_exit_are_preserved(self):
        result, calls = self.run_status(container_missing=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('last_success:\nsynthetic-success\nALERT:\nsynthetic-alert', result.stdout)
        self.assertIn('Container suedhang-cafeteria-app-1 nicht lesbar', result.stderr)
        self.assertFalse(any(call[0] in ('curl', 'git') for call in calls))

    def test_expected_revision_is_exact_not_a_short_prefix(self):
        for expected, code in ((LIVE, 0), (LIVE[:10], 1), ('d' * 40, 1)):
            with self.subTest(expected=expected):
                result, _ = self.run_status(environment={'DISHBOARD_EXPECTED_REVISION': expected})
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual('entspricht nicht Kandidat' in result.stdout, bool(code))

    def test_health_login_and_curl_failure_still_fail(self):
        for changes in ({'health': 'unhealthy'}, {'health': 'ohne-healthcheck'},
                        {'login': '302'}, {'login': '500'}, {'login': '000', 'curl_exit': 7}):
            with self.subTest(changes=changes):
                result, _ = self.run_status(**changes)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('WARNUNG: Produktion nicht gesund', result.stdout)
                self.assertNotIn('STATUS: OK', result.stdout)

    def test_missing_requested_line_is_not_reported_as_ok(self):
        result, _ = self.run_status('fix/missing', 'integrate/train')
        self.assertEqual(result.returncode, 2)
        self.assertIn('fix/missing: nicht lesbar', result.stdout)
        self.assertIn('integrate/train: 0 Commits', result.stdout)
        self.assertNotIn('STATUS: OK', result.stdout)

    def test_failed_line_discovery_cannot_claim_success(self):
        result, _ = self.run_status(refs_error=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('lokale Integrationslinien nicht lesbar', result.stderr)
        self.assertNotIn('STATUS: OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
