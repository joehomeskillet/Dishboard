"""Shared browser fixtures; native PDF browser files require runner isolation."""
from __future__ import annotations

import ast
import inspect

import pytest

from _support.browser import browser, shared_browser  # noqa: F401


def pytest_collection_modifyitems(items: list[pytest.Item], config: pytest.Config) -> None:
    if config.option.collectonly:
        return
    providers: set[str] = set()
    inspected = set()
    for item in items:
        marks = list(item.iter_markers())
        if any(mark.name == 'skip' or (mark.name == 'skipif' and any(
                condition is True for condition in (*mark.args, mark.kwargs.get('condition'))
        )) for mark in marks):
            continue
        path = getattr(item, 'path', None)
        if path is not None and path not in inspected:
            inspected.add(path)
            tree = ast.parse(path.read_text(encoding='utf-8'))
            if any(isinstance(node, ast.AsyncFunctionDef) or (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'run' and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {'asyncio', 'anyio'}
            ) for node in ast.walk(tree)):
                providers.add('asyncio')
        info = getattr(item, '_fixtureinfo', None)
        definitions = info.name2fixturedefs.get('browser', ()) if info else ()
        if definitions:
            function = definitions[-1].func
            source = inspect.getsource(function)
            providers.add(function.__module__ if 'sync_playwright(' in source else 'managed')
    if len(providers) > 1 and providers != {'managed'}:
        raise pytest.UsageError(
            'Mixed native and managed browser runtimes require tools/test_gate.py; '
            'the runner isolates native PDF/Chrome files before starting pytest.'
        )
