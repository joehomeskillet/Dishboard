"""Opt-in test-gate event stream; never auto-loaded by ordinary pytest runs."""
from __future__ import annotations

import json
from pathlib import Path

from _test_gate_results import canonical_nodeid

_destination: Path | None = None


def pytest_addoption(parser):
    parser.addoption('--gate-events', help='test-gate JSONL event destination')
    parser.addoption('--gate-pool-name', help='pool identity visible to process preflight')


def pytest_configure(config):
    global _destination
    value = config.getoption('--gate-events')
    _destination = Path(value) if value else None
    if _destination:
        _destination.write_text('')


def emit(event):
    if _destination:
        with _destination.open('a') as stream:
            stream.write(json.dumps(event, ensure_ascii=True) + '\n')


def pytest_collection_finish(session):
    for item in session.items:
        item.user_properties.append(('gate_nodeid', canonical_nodeid(item.nodeid)))
    emit({'event': 'collection', 'ids': [canonical_nodeid(item.nodeid) for item in session.items]})


def pytest_runtest_logreport(report):
    emit({'event': 'phase', 'id': canonical_nodeid(report.nodeid), 'phase': report.when,
          'outcome': report.outcome, 'seconds': report.duration})


def pytest_sessionfinish(session, exitstatus):
    emit({'event': 'finish', 'exit': int(exitstatus)})
