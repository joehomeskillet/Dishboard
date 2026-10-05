#!/usr/bin/env python3
"""Run duration-balanced pytest shards on exclusive disposable test pools."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import ExitStack
from pathlib import Path

from _test_gate_browser import browser_groups
from _test_gate_impact import build_map, changed_paths, select_tests
from _test_gate_tiers import run_static
from _test_gate_pools import (
    Pool, check_existing_pytest, enough_memory, load_pool, lock_pools,
)
from _test_gate_results import (
    Results, compare_results, is_infrastructure as is_infrastructure, merge_junit, read_baseline,
    read_junit, redact, reference_changes, select_reference, shard_files, write_timings,
)

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / 'reference_scaffold'
TESTS = SCAFFOLD / 'tests'


def events(path: Path) -> list[dict]:
    if not path.exists():
        manifest = path.parent / 'groups.json'
        if not manifest.exists():
            return []
        count = len(json.loads(manifest.read_text()))
        stream = [event for index in range(count)
                  for event in events(path.parent / f'group-{index}' / path.name)]
        collections = [event for event in stream if event['event'] == 'collection']
        phases = [event for event in stream if event['event'] == 'phase']
        finishes = [event for event in stream if event['event'] == 'finish']
        combined = ([{'event': 'collection', 'ids': [identity for event in collections
                     for identity in event['ids']]}] if collections else []) + phases
        if len(finishes) == count:
            combined.append({'event': 'finish', 'exit': max(event['exit'] for event in finishes)})
        return combined
    content = path.read_text()
    # A live writer can leave its final line incomplete between write and flush.
    return [json.loads(line) for line in content.splitlines(keepends=True)
            if line.endswith('\n')]


def run_shard(pool: Pool, files: list[str], output: Path, seed: int, python: str,
              lease_fds: tuple[int, ...]) -> int:
    output.mkdir(mode=0o700)
    groups = browser_groups(files, TESTS)
    if len(groups) > 1:
        (output / 'groups.json').write_text(json.dumps(groups, indent=2) + '\n')
        codes = [run_process(pool, group, output / f'group-{index}', seed, python, lease_fds)
                 for index, group in enumerate(groups)]
        merge_junit(read_junit([output / f'group-{index}' / 'junit.xml'
                               for index in range(len(groups))]), output / 'junit.xml')
        return max(codes) if all(code in (0, 1) for code in codes) else 2
    return run_process(pool, files, output, seed, python, lease_fds)


def run_process(pool: Pool, files: list[str], output: Path, seed: int, python: str,
                lease_fds: tuple[int, ...]) -> int:
    output.mkdir(mode=0o700, exist_ok=True)
    environment = pool.env.copy()
    environment['PYTHONPATH'] = os.pathsep.join(filter(None, (
        str(TESTS), str(SCAFFOLD), str(ROOT / 'tools'), environment.get('PYTHONPATH', ''),
    )))
    arguments = ['rtk', python, '-m', 'pytest', '-q', '-p', '_support.gate_events',
                 '--gate-events', str(output / 'events.jsonl'),
                 '--gate-pool-name', pool.name,
                 '--randomly-seed', str(seed), '--junitxml', str(output / 'junit.xml'),
                 '-o', f'cache_dir={output / "cache"}', *files]
    (output / 'command.json').write_text(json.dumps(arguments, indent=2) + '\n')
    started = time.monotonic()
    result = subprocess.run(arguments, cwd=SCAFFOLD, env=environment, shell=False,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            pass_fds=lease_fds)
    (output / 'pytest.log').write_text(redact(result.stdout, environment))
    junit = output / 'junit.xml'
    if junit.exists():
        junit.write_text(redact(junit.read_text(), environment))
    (output / 'process.json').write_text(json.dumps({
        'exit': result.returncode, 'seconds': time.monotonic() - started,
    }) + '\n')
    return result.returncode


def run_selection(files: list[str], pools: list[Pool], timings: dict[str, float],
                  output: Path, seed: int, python: str,
                  lease_fds: tuple[int, ...]) -> tuple[Results, bool]:
    shards = shard_files(files, timings, len(pools))
    paths = [output / f'shard-{index}' for index in range(len(shards))]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(shards)) as executor:
        futures = [executor.submit(run_shard, pools[i], shard, paths[i], seed, python, lease_fds)
                   for i, shard in enumerate(shards)]
        pending = set(futures)
        while pending:
            _, pending = wait(pending, timeout=15)
            for index, path in enumerate(paths):
                stream = events(path / 'events.jsonl')
                total = sum(len(e['ids']) for e in stream if e['event'] == 'collection')
                done = sum(e['event'] == 'phase' and e['phase'] == 'teardown' for e in stream)
                print(f'Shard {index + 1}: {done}/{total or "?"} | '
                      f'{time.monotonic() - started:.0f}s', flush=True)
        codes = [future.result() for future in futures]
    result = read_junit([path / 'junit.xml' for path in paths])
    collected: list[str] = []
    complete = True
    for path, code in zip(paths, codes):
        stream = events(path / 'events.jsonl')
        collection = [e for e in stream if e['event'] == 'collection']
        finish = [e for e in stream if e['event'] == 'finish']
        if len(collection) != 1 or len(finish) != 1 or code not in (0, 1):
            complete = False
        if finish and finish[-1]['exit'] != code:
            complete = False
        collected.extend(identity for e in collection for identity in e['ids'])
        if code == 1 and not any(state in ('failed', 'error') for state in read_junit(
                [path / 'junit.xml']).statuses.values()):
            complete = False
    if len(collected) != len(set(collected)) or set(collected) != set(result.statuses):
        complete = False
    merge_junit(result, output / 'junit.xml')
    (output / 'results.json').write_text(json.dumps(result.statuses, indent=2, sort_keys=True) + '\n')
    (output / 'summary.json').write_text(json.dumps({
        'seconds': time.monotonic() - started, 'test_seconds': sum(result.timings.values()),
        'collected': len(collected), 'complete': complete, 'seed': seed, 'process_exits': codes,
    }, indent=2) + '\n')
    return result, complete


def report(result: Results, baseline: set[str]) -> int:
    new, fixed, known = compare_results(result.statuses, baseline)
    for label, identities in [('NEU rot', new - result.infra), ('behoben', fixed),
                              ('weiter bekannt rot', known - result.infra), ('INFRA', result.infra)]:
        for identity in sorted(identities):
            print(f'{label}: {identity}')
    print(f'NEU rot={len(new - result.infra)} behoben={len(fixed)} '
          f'weiter bekannt rot={len(known - result.infra)} INFRA={len(result.infra)}')
    return 2 if result.infra else int(bool(new))


def parser() -> argparse.ArgumentParser:
    arguments = argparse.ArgumentParser(description=__doc__)
    mode = arguments.add_mutually_exclusive_group()
    mode.add_argument('--full', action='store_true')
    mode.add_argument('--changed', metavar='BASE_REF', help='conservative dependency selection from git diff')
    mode.add_argument('--build-map', action='store_true', help='regenerate Python/template/asset dependency map')
    mode.add_argument('--files', nargs='+', help='paths relative to reference_scaffold')
    mode.add_argument('--import-history', nargs='+', type=Path, help='bootstrap timings and baseline from JUnit')
    arguments.add_argument('--pools', default=os.getenv('TEST_GATE_POOLS', ''), help='comma-separated literal env files')
    arguments.add_argument('--baseline', type=Path, default=TESTS / 'known-failures.txt')
    arguments.add_argument('--timings', type=Path, default=TESTS / '.timings.json')
    arguments.add_argument('--output', type=Path, help='new directory for private logs, JUnit and exact commands')
    arguments.add_argument('--reference-junit', nargs='+', type=Path, help='also compare every selected ID/status')
    arguments.add_argument('--flaky', action='store_true', help='repeat selection with two seeds and compare every ID')
    arguments.add_argument('--seed', type=int, default=920)
    arguments.add_argument('--second-seed', type=int, default=1920)
    arguments.add_argument('--python', default=sys.executable, help='interpreter with project pytest/plugins installed')
    arguments.add_argument('--list', action='store_true', help='show selection and estimated test seconds without running')
    arguments.add_argument('--tier', type=int, choices=range(4), help='0 static, 1 changed, 2 full, 3 nightly two seeds')
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    if args.tier == 0 and (args.full or args.changed or args.files or args.build_map or args.import_history):
        arguments.error('tier 0 cannot be combined with a test-selection mode')
    if args.tier in (2, 3):
        if args.changed or args.files or args.build_map or args.import_history:
            arguments.error('tiers 2 and 3 require the full selection')
        args.full = True
    if args.tier == 1:
        if args.full or args.files or args.build_map or args.import_history:
            arguments.error('tier 1 requires --changed or defaults to HEAD')
        args.changed = args.changed or 'HEAD'
    if args.tier == 3:
        args.flaky = True
        args.output = args.output or ROOT / '.claude/state' / f'test-gate-nightly-{time.time_ns()}'
    if args.tier is None and not any((args.full, args.changed, args.files, args.build_map, args.import_history)):
        arguments.error('provide --tier or a test-selection mode')
    try:
        if args.tier == 0:
            return run_static(ROOT, args.python, args.output or
                              ROOT / '.claude/state' / f'test-gate-static-{time.time_ns()}')
        impact: dict = {}
        if args.build_map or args.changed:
            impact = build_map(ROOT)
            (TESTS / '.impact-map.json').write_text(json.dumps(impact, sort_keys=True, separators=(',', ':')) + '\n')
            if args.build_map:
                print(f'Generated {len(impact["files"])} input mappings for {len(impact["tests"])} test files')
                return 0
        if args.import_history:
            if args.baseline.exists():
                raise ValueError('baseline already exists; bootstrap never overwrites accepted failures')
            history = read_junit(args.import_history)
            if history.infra:
                raise ValueError('cannot accept infrastructure errors as known failures')
            write_timings(args.timings, history.timings)
            failed = sorted(key for key, value in history.statuses.items() if value in ('failed', 'error'))
            args.baseline.write_text(
                '# Imported main baseline; reason: test-audit-0920; owner: orchestrator; date: 2026-09-20\n'
                '# Review each failure before removal. An unselected or skipped test is not fixed.\n'
                + '\n'.join(failed) + '\n')
            print(f'Imported {len(history.timings)} file timings and {len(failed)} known failures')
            return 0
        files = sorted(p.relative_to(SCAFFOLD).as_posix() for p in TESTS.rglob('test_*.py')) if args.full else args.files
        if args.changed:
            names = changed_paths(ROOT, args.changed)
            names = [name for name in names if name not in {
                'reference_scaffold/tests/.timings.json', 'reference_scaffold/tests/.impact-map.json',
            } and not name.startswith('reference_scaffold/.testmondata')]
            files, reasons = select_tests(names, impact)
            for reason in reasons:
                print(reason)
        for name in files:
            path = (SCAFFOLD / name).resolve()
            if not path.is_relative_to(TESTS) or not path.is_file() or not path.name.startswith('test_'):
                raise ValueError('test selection must contain existing test files beneath tests/')
        if not files:
            raise ValueError('empty selection is not a passing gate')
        if args.list:
            timings = json.loads(args.timings.read_text()) if args.timings.exists() else {}
            print('\n'.join(files))
            print(f'Selected {len(files)} files; historical test seconds '
                  f'{sum(timings.get(name, 0) for name in files):.1f}; unknown times '
                  f'{sum(name not in timings for name in files)}')
            return 0
        pool_paths = [Path(p).expanduser() for p in args.pools.split(',') if p]
        if not 1 <= len(pool_paths) <= 4:
            raise ValueError('provide between one and four exclusive pool env files via --pools or TEST_GATE_POOLS')
        if args.flaky and args.seed == args.second_seed:
            raise ValueError('flaky comparison requires different seeds')
        if len(pool_paths) > 1 and not enough_memory():
            print('Available memory below 30 GB: using one pool sequentially')
            pool_paths = pool_paths[:1]
        pools = [load_pool(path) for path in pool_paths]
        for pool in pools:
            check_existing_pytest(pool)
        baseline = read_baseline(args.baseline)
        timings = json.loads(args.timings.read_text()) if args.timings.exists() else {}
        output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix='dishboard-test-gate-'))
        if args.output:
            output.mkdir(mode=0o700, parents=True, exist_ok=False)
        print(f'Artefakte: {output}', flush=True)
        status = 0
        first: Results | None = None
        with ExitStack() as stack:
            lease_fds = lock_pools(pools, stack)
            for seed in ([args.seed, args.second_seed] if args.flaky else [args.seed]):
                run_output = output / f'seed-{seed}'
                run_output.mkdir(mode=0o700)
                result, complete = run_selection(files, pools, timings, run_output, seed, args.python, lease_fds)
                status = max(status, report(result, baseline))
                if not complete:
                    print('INFRA: incomplete collection, missing IDs, or abnormal pytest termination')
                    status = 2
                if args.reference_junit:
                    reference = read_junit(args.reference_junit).statuses
                    selected = select_reference(reference, files, full=args.full)
                    for identity, delta in reference_changes(result.statuses, selected).items():
                        print(f'ID-DELTA: {identity}: {delta[0]} -> {delta[1]}')
                        if delta[1] != 'passed' or delta[0] is None:
                            status = max(status, 1)
                if first is not None:
                    changes = reference_changes(result.statuses, first.statuses)
                    for identity, delta in changes.items():
                        print(f'FLAKY: {identity}: {delta[0]} -> {delta[1]}')
                    status = max(status, int(bool(changes)))
                first = result
                if complete and not result.infra:
                    write_timings(args.timings, result.timings)
        return status
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as exc:
        # Never echo a DSN, shell environment or subprocess command containing credentials.
        print(f'INFRA: {type(exc).__name__}: {redact(str(exc), dict(os.environ))}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
