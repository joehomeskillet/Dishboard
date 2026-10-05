"""Conservatively isolate unchanged tests which start their own sync runtime."""
from __future__ import annotations

import ast
from pathlib import Path


def browser_groups(files: list[str], tests: Path) -> list[list[str]]:
    dependencies: dict[str, set[str]] = {}
    native: set[str] = set()
    for path in tests.rglob('test_*.py'):
        tree = ast.parse(path.read_text(), filename=str(path))
        name = path.stem
        dependencies[name] = {
            node.module.split('.')[0] for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
            and node.module.startswith('test_')
        }
        dependencies[name].update(
            alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names if alias.name.startswith('test_')
        )
        private_loop = any(isinstance(node, ast.AsyncFunctionDef) or (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {'asyncio', 'anyio'} and node.func.attr == 'run'
        ) for node in ast.walk(tree))
        if private_loop or any(isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Name) and node.func.id == 'sync_playwright'
                or isinstance(node.func, ast.Attribute) and node.func.attr == 'sync_playwright'
        ) for node in ast.walk(tree)):
            native.add(name)
    while True:
        expanded = native | {name for name, imports in dependencies.items() if imports & native}
        if expanded == native:
            break
        native = expanded
    regular = [name for name in files if Path(name).stem not in native]
    return ([regular] if regular else []) + [[name] for name in files if Path(name).stem in native]
