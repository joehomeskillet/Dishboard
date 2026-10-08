"""DB-free contracts for the test gate's safety and result accounting."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / 'tools'
sys.path.insert(0, str(TOOLS))


def gate():
    import test_gate
    return test_gate


def test_lpt_preserves_files_and_balances_longest_first():
    shards = gate().shard_files(['a', 'b', 'c', 'd'], {'a': 8, 'b': 7, 'c': 3, 'd': 2}, 2)
    assert shards == [['a', 'd'], ['b', 'c']]
    assert sorted(x for shard in shards for x in shard) == ['a', 'b', 'c', 'd']


def test_missing_failure_baseline_does_not_accept_a_failed_test(tmp_path):
    baseline = gate().read_baseline(tmp_path / 'absent.txt')
    assert baseline == set()
    assert gate().report(gate().Results(statuses={'test_case': 'failed'}), baseline) == 1


def test_lpt_is_deterministic_for_missing_times():
    assert gate().shard_files(['c', 'a', 'b'], {}, 2) == [['a', 'c'], ['b']]


@pytest.mark.parametrize('workers', [0, 5])
def test_lpt_rejects_unsafe_worker_counts(workers):
    with pytest.raises(ValueError):
        gate().shard_files(['a'], {}, workers)


def test_comparison_does_not_call_unselected_or_skipped_failures_fixed():
    actual = {'a': 'passed', 'b': 'failed', 'c': 'failed', 'd': 'skipped'}
    new, fixed, known = gate().compare_results(actual, {'a', 'b', 'd', 'unselected'})
    assert new == {'c', 'd'}
    assert fixed == {'a'}
    assert known == {'b'}


@pytest.mark.parametrize('message', [
    'psycopg.OperationalError: connection refused',
    'It looks like you are using Playwright Sync API inside the asyncio loop',
    'psycopg.errors.UndefinedTable: relation cafeteria.users does not exist',
    'fastdb refuses reset: active connections remain in the test database',
    'asyncio.run() cannot be called from a running event loop',
])
def test_infrastructure_errors_are_separate(message):
    assert gate().is_infrastructure(message)


def test_assertion_timeout_is_not_infrastructure():
    assert not gate().is_infrastructure('Locator.click: Timeout 30000ms exceeded')


def test_native_browser_consumers_are_isolated_transitively(tmp_path):
    from _test_gate_browser import browser_groups
    (tmp_path / 'test_native.py').write_text('from playwright.sync_api import sync_playwright\ndef browser():\n    return sync_playwright()\n')
    (tmp_path / 'test_importer.py').write_text('from test_native import browser\n')
    (tmp_path / 'test_indirect.py').write_text('from test_importer import browser\n')
    (tmp_path / 'test_regular.py').write_text('def test_ok(): pass\n')
    files = ['tests/test_regular.py', 'tests/test_indirect.py', 'tests/test_native.py']
    assert browser_groups(files, tmp_path) == [[files[0]], [files[1]], [files[2]]]


def test_browser_partition_preserves_regular_single_process(tmp_path):
    from _test_gate_browser import browser_groups
    (tmp_path / 'test_a.py').write_text('def test_a(): pass\n')
    (tmp_path / 'test_b.py').write_text('from test_a import test_a\n')
    files = ['tests/test_b.py', 'tests/test_a.py']
    assert browser_groups(files, tmp_path) == [files]


def test_asyncio_consumers_and_importers_do_not_share_browser_runtime(tmp_path):
    from _test_gate_browser import browser_groups
    (tmp_path / 'test_async.py').write_text('import asyncio\ndef invoke():\n    return asyncio.run(work())\n')
    (tmp_path / 'test_consumer.py').write_text('from test_async import invoke\n')
    (tmp_path / 'test_browser.py').write_text('def test_page(browser): pass\n')
    files = ['tests/test_browser.py', 'tests/test_async.py', 'tests/test_consumer.py']
    assert browser_groups(files, tmp_path) == [[files[0]], [files[1]], [files[2]]]


def test_reference_full_run_retains_ids_from_removed_test_files():
    from _test_gate_results import select_reference
    reference = {'tests/test_a.py::test_a': 'passed', 'tests/test_removed.py::test_b': 'passed'}
    assert select_reference(reference, ['tests/test_a.py'], full=True) == reference
    assert select_reference(reference, ['tests/test_a.py'], full=False) == {'tests/test_a.py::test_a': 'passed'}


def test_url_id_redaction_is_stable_and_does_not_merge_distinct_cases():
    from _test_gate_results import canonical_nodeid, redact
    first = 'tests/test_a.py::test_url[https://first:secret@example.invalid]'
    second = 'tests/test_a.py::test_url[https://second:secret@example.invalid]'
    canonical = canonical_nodeid(first)
    assert canonical != canonical_nodeid(second)
    assert 'first:secret' not in canonical
    assert redact(canonical, {}) == canonical
    assert canonical_nodeid(canonical) == canonical


def test_two_databases_on_one_postgres_cluster_cannot_be_parallel_pools(tmp_path, monkeypatch):
    from contextlib import ExitStack
    import _test_gate_pools as pools
    monkeypatch.setattr(pools, 'published_port', lambda name, port:
                        5432 if port == 5432 else (6380 if name.endswith('one') else 6381))
    selected = []
    for name in ['one', 'two']:
        path = tmp_path / (name + '.env')
        path.write_text(f'TEST_DATABASE_URL=postgresql://127.0.0.1/test_{name}\n'
                        'TEST_DATABASE_CONTAINER=test-pg\n'
                        f'TEST_REDIS_CONTAINER=test-redis-{name}\n'
                        'TEST_REDIS_URL=redis://127.0.0.1/0\n')
        selected.append(pools.load_pool(path))
    with ExitStack() as stack, pytest.raises(ValueError, match='pool collision'):
        pools.lock_pools(selected, stack)


def test_junit_identity_preserves_class_and_parameter_punctuation(tmp_path):
    source = tmp_path / 'shard.xml'
    source.write_text('<testsuites><testsuite><testcase classname="tests.test_x.TestThing" '
                      'name="test_value[a.b::c]" time="1.5"/></testsuite></testsuites>')
    result = gate().read_junit([source])
    assert result.statuses == {'tests/test_x.py::TestThing::test_value[a.b::c]': 'passed'}
    assert result.timings == {'tests/test_x.py': 1.5}


def test_junit_uses_exact_collected_nodeid_when_available(tmp_path):
    source = tmp_path / 'shard.xml'
    source.write_text('<testsuites><testsuite><testcase classname="wrong" name="wrong">'
                      '<properties><property name="gate_nodeid" '
                      'value="tests/test_real.py::test_real[ä]"/></properties>'
                      '<error message="connection refused"/></testcase></testsuite></testsuites>')
    result = gate().read_junit([source])
    assert result.infra == {'tests/test_real.py::test_real[ä]'}


def test_missing_junit_is_not_a_green_gate(tmp_path):
    with pytest.raises((ValueError, FileNotFoundError)):
        gate().read_junit([tmp_path / 'absent.xml'])


def test_duplicate_shard_ids_are_rejected(tmp_path):
    paths = [tmp_path / 'one.xml', tmp_path / 'two.xml']
    for p in paths:
        p.write_text('<testsuite><testcase classname="tests.test_x" name="test_one"/></testsuite>')
    with pytest.raises(ValueError, match='duplicate'):
        gate().read_junit(paths)


def test_teardown_error_cannot_hide_a_call_failure(tmp_path):
    p = tmp_path / 'one.xml'
    p.write_text('<testsuite><testcase classname="tests.test_x" name="test_one">'
                 '<failure message="assert false"/></testcase>'
                 '<testcase classname="tests.test_x" name="test_one">'
                 '<error message="broken teardown"/></testcase></testsuite>')
    assert gate().read_junit([p]).statuses == {'tests/test_x.py::test_one': 'error'}


@pytest.mark.parametrize('url', [
    'postgresql://remote.example/test_db', 'postgresql://127.0.0.1/production',
    'postgresql://127.0.0.1/test_db?host=remote.example', 'sqlite:///test.db',
    'postgresql:///test_db',
])
def test_database_guard_rejects_unsafe_targets(url):
    from _test_gate_pools import validate_database_url
    with pytest.raises(ValueError):
        validate_database_url(url)


def test_database_guard_accepts_loopback_test_database():
    from _test_gate_pools import validate_database_url
    validate_database_url('postgresql+psycopg://user:password@[::1]:5432/menuplan_test')


def test_env_parser_never_executes_shell(tmp_path):
    from _test_gate_pools import read_pool_env
    p = tmp_path / 'pool.env'
    p.write_text('TEST_DATABASE_URL=$(touch /tmp/forbidden)\n')
    with pytest.raises(ValueError):
        read_pool_env(p)


def test_env_parser_handles_quotes_and_export(tmp_path):
    from _test_gate_pools import read_pool_env
    p = tmp_path / 'pool.env'
    p.write_text('export TEST_DATABASE_CONTAINER="example-test-pg16"\n# comment\n'
                 "TEST_REDIS_URL='redis://127.0.0.1:1234/0'\n")
    assert read_pool_env(p)['TEST_DATABASE_CONTAINER'] == 'example-test-pg16'


def test_reference_detects_missing_ids_and_new_skips():
    from _test_gate_results import reference_changes
    assert reference_changes({'a': 'skipped', 'b': 'passed'}, {'a': 'passed', 'c': 'passed'}) == {
        'a': ('passed', 'skipped'), 'b': (None, 'passed'), 'c': ('passed', None),
    }


def test_junit_rejects_entity_declarations(tmp_path):
    path = tmp_path / 'entity.xml'
    path.write_text('<!DOCTYPE testsuite [<!ENTITY value "expanded">]>'
                    '<testsuite><testcase classname="tests.test_x" name="&value;"/></testsuite>')
    with pytest.raises(ValueError, match='DOCTYPE'):
        gate().read_junit([path])


def test_process_redacts_xml_escaped_secrets_in_attributes_text_and_tails(tmp_path, monkeypatch):
    import xml.etree.ElementTree as ET
    from types import SimpleNamespace
    from _test_gate_pools import Pool

    secret = 'sample&secret'
    output = tmp_path / 'process'

    def run(arguments, **kwargs):
        root = ET.Element('testsuite', name=secret)
        case = ET.SubElement(root, 'testcase', classname='tests.test_x', name='test_one')
        failure = ET.SubElement(case, 'failure', message=secret)
        failure.text = secret
        failure.tail = secret
        ET.SubElement(case, 'system-out').text = 'https://user:sample&secret@example.invalid/'
        ET.ElementTree(root).write(output / 'junit.xml', encoding='utf-8')
        return SimpleNamespace(returncode=1, stdout=secret)

    monkeypatch.setattr(gate().subprocess, 'run', run)
    pool = Pool('synthetic', {'GATE_SECRET': secret}, ('synthetic:pg', 'synthetic:redis'))
    assert gate().run_process(pool, ['tests/test_x.py'], output, 920, sys.executable, ()) == 1
    saved = (output / 'junit.xml').read_text()
    assert 'sample&amp;secret' not in saved
    root = ET.fromstring(saved)
    for element in root.iter():
        for value in [*element.attrib.values(), element.text or '', element.tail or '']:
            assert secret not in value
    assert root.attrib['name'] == '[redacted]'
    failure = root.find('./testcase/failure')
    assert failure is not None
    assert failure.attrib['message'] == failure.text == failure.tail == '[redacted]'
    assert root.findtext('./testcase/system-out') == 'https://[redacted]@example.invalid/'
    assert (output / 'pytest.log').read_text() == '[redacted]'
    assert gate().read_junit([output / 'junit.xml']).statuses == {'tests/test_x.py::test_one': 'failed'}


def test_junit_redaction_rejects_entity_declarations(tmp_path):
    from _test_gate_results import redact_junit

    path = tmp_path / 'entity.xml'
    path.write_text('<!DOCTYPE testsuite [<!ENTITY value "expanded">]>'
                    '<testsuite><testcase classname="tests.test_x" name="&value;"/></testsuite>')
    with pytest.raises(ValueError, match='DOCTYPE'):
        redact_junit(path, {})


def test_runner_enables_runtime_guard_for_each_pytest_process(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from _test_gate_pools import Pool

    environments = []

    def run(arguments, **kwargs):
        environments.append(kwargs['env'])
        return SimpleNamespace(returncode=0, stdout='')

    monkeypatch.setattr(gate().subprocess, 'run', run)
    pool = Pool('synthetic', {'TEST_GATE_RUNTIME_GUARD': '0'}, ('synthetic:pg', 'synthetic:redis'))
    assert gate().run_process(pool, ['tests/test_x.py'], tmp_path / 'process',
                              920, sys.executable, ()) == 0
    assert environments[0]['TEST_GATE_RUNTIME_GUARD'] == '1'
    assert pool.env['TEST_GATE_RUNTIME_GUARD'] == '0'


def test_tier_zero_missing_ruff_is_an_infrastructure_error(tmp_path, monkeypatch):
    import _test_gate_tiers as tiers

    monkeypatch.setattr(tiers.shutil, 'which', lambda command: None)
    monkeypatch.setattr(tiers.subprocess, 'run', lambda *args, **kwargs:
                        pytest.fail('Missing Ruff must stop before launching any static checks'))
    with pytest.raises(ValueError, match='Tier 0 requires Ruff on PATH'):
        tiers.run_static(tmp_path, sys.executable, tmp_path / 'static')


def test_lock_prevents_second_gate_on_same_resources():
    from contextlib import ExitStack
    from uuid import uuid4
    from _test_gate_pools import Pool, lock_pools
    key = str(uuid4())
    pool = Pool('unit-test', {}, (key + ':pg', key + ':redis'))
    with ExitStack() as first, ExitStack() as second:
        lock_pools([pool], first)
        with pytest.raises(ValueError, match='leased'):
            lock_pools([pool], second)
