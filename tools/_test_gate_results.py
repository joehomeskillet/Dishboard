"""Pure result accounting for test_gate; no pytest or database dependency."""
from __future__ import annotations

import json
import hashlib
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

RANK = {'passed': 0, 'skipped': 1, 'failed': 2, 'error': 3}
URL_USERINFO = re.compile(r'(\b[a-z][a-z0-9+.-]*://)([^\s/@]+)@')


def canonical_nodeid(identity: str) -> str:
    """Keep URL-bearing case identities distinct without storing userinfo."""
    def replace(match: re.Match[str]) -> str:
        if match.group(2).startswith('[userinfo-sha256='):
            return match.group(0)
        digest = hashlib.sha256((identity + '\0' + match.group(2)).encode()).hexdigest()
        return match.group(1) + '[userinfo-sha256=' + digest + ']@'
    return URL_USERINFO.sub(replace, identity)


def shard_files(files: list[str], timings: dict[str, float], workers: int) -> list[list[str]]:
    if not 1 <= workers <= 4:
        raise ValueError('worker count must be between 1 and 4')
    if len(set(files)) != len(files):
        raise ValueError('duplicate test files')
    if any(not math.isfinite(v) or v < 0 for v in timings.values()):
        raise ValueError('invalid historical duration')
    shards: list[list[str]] = [[] for _ in range(workers)]
    totals = [0.0] * workers
    default = max(1.0, sum(timings.values()) / max(1, len(timings)))
    for name in sorted(files, key=lambda n: (-timings.get(n, default), n)):
        index = min(range(workers), key=lambda i: (totals[i], len(shards[i]), i))
        shards[index].append(name)
        totals[index] += timings.get(name, default)
    return [shard for shard in shards if shard]


def is_infrastructure(message: str) -> bool:
    return any(marker in message.lower() for marker in (
        'connection refused', 'playwright sync api inside the asyncio loop',
        'undefinedtable', 'database system is starting up', 'too many clients already',
        'fastdb refuses reset: active connections',
        'asyncio.run() cannot be called from a running event loop',
    ))


def nodeid(case: ET.Element) -> str:
    for prop in case.findall('./properties/property'):
        if prop.get('name') == 'gate_nodeid':
            return canonical_nodeid(prop.attrib['value'])
    parts = case.get('classname', '').split('.')
    index = next((i for i, part in enumerate(parts) if part.startswith('test_')), None)
    if index is None or not case.get('name'):
        raise ValueError('JUnit case lacks an identifiable test module/name')
    path = '/'.join(parts[:index + 1]) + '.py'
    if not path.startswith('tests/'):
        path = 'tests/' + path
    return canonical_nodeid('::'.join([path, *parts[index + 1:], case.attrib['name']]))


@dataclass
class Results:
    statuses: dict[str, str] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)
    infra: set[str] = field(default_factory=set)
    suites: list[ET.Element] = field(default_factory=list)


class JunitTreeBuilder(ET.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise ValueError('DOCTYPE declarations are forbidden in JUnit')


def read_junit(paths: list[Path]) -> Results:
    result = Results()
    durations: dict[str, float] = defaultdict(float)
    for path in paths:
        root = ET.parse(path, parser=ET.XMLParser(target=JunitTreeBuilder())).getroot()
        local: dict[str, str] = {}
        cases = list(root.iter('testcase'))
        if not cases:
            raise ValueError('JUnit report contains no test cases')
        for case in cases:
            identity = nodeid(case)
            if identity in result.statuses:
                raise ValueError('duplicate test ID across shards: ' + identity)
            state = next((status for tag, status in (
                ('error', 'error'), ('failure', 'failed'), ('skipped', 'skipped'),
            ) if case.find(tag) is not None), 'passed')
            previous = local.get(identity, 'passed')
            local[identity] = max((previous, state), key=RANK.__getitem__)
            duration = float(case.get('time', '0'))
            if not math.isfinite(duration) or duration < 0:
                raise ValueError('invalid JUnit duration')
            durations[identity.split('::')[0]] += duration
            for child in [*case.findall('error'), *case.findall('failure')]:
                if is_infrastructure(child.get('message', '') + '\n' + (child.text or '')):
                    result.infra.add(identity)
        result.statuses.update(local)
        result.suites.extend([root] if root.tag == 'testsuite' else root.findall('testsuite'))
    result.timings = dict(durations)
    return result


def compare_results(actual: dict[str, str], baseline: set[str]) -> tuple[set[str], set[str], set[str]]:
    red = {key for key, state in actual.items() if state in ('failed', 'error')}
    skipped_known = {key for key in baseline if actual.get(key) == 'skipped'}
    fixed = {key for key in baseline if actual.get(key) == 'passed'}
    return (red - baseline) | skipped_known, fixed, red & baseline


def reference_changes(actual: dict[str, str], reference: dict[str, str]) -> dict[str, tuple[str | None, str | None]]:
    return {key: (reference.get(key), actual.get(key)) for key in sorted(actual.keys() | reference.keys())
            if actual.get(key) != reference.get(key)}


def read_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {canonical_nodeid(line.strip()) for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')}


def select_reference(reference: dict[str, str], files: list[str], *, full: bool) -> dict[str, str]:
    if full:
        return reference
    return {key: value for key, value in reference.items() if key.split('::')[0] in files}


def write_timings(path: Path, measured: dict[str, float]) -> None:
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update({key: round(value, 3) for key, value in measured.items()})
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def merge_junit(result: Results, destination: Path) -> None:
    root = ET.Element('testsuites')
    for suite in result.suites:
        root.append(suite)
    ET.ElementTree(root).write(destination, encoding='utf-8', xml_declaration=True)


def redact(text: str, env: dict[str, str]) -> str:
    text = URL_USERINFO.sub(lambda match: match.group(0)
                           if match.group(2).startswith('[userinfo-sha256=')
                           else match.group(1) + '[redacted]@', text)
    for key, value in env.items():
        if len(value) >= 8 and any(word in key.upper() for word in ('PASSWORD', 'SECRET', 'TOKEN')):
            text = text.replace(value, '[redacted]')
    return text


def redact_junit(path: Path, env: dict[str, str]) -> None:
    """Redact decoded XML values before serializing the report again."""
    tree = ET.parse(path, parser=ET.XMLParser(target=JunitTreeBuilder()))
    for element in tree.iter():
        for key, value in element.attrib.items():
            element.set(key, redact(value, env))
        if element.text is not None:
            element.text = redact(element.text, env)
        if element.tail is not None:
            element.tail = redact(element.tail, env)
    tree.write(path, encoding='utf-8', xml_declaration=True)
