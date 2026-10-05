"""Collection-only and existing skips must not create false runtime conflicts."""
from types import SimpleNamespace

import pytest

import conftest


def native():
    return 'sync_playwright('


def managed():
    return None


def item(function, skipped=False, path=None):
    marks = [SimpleNamespace(name='skipif', args=(True,), kwargs={})] if skipped else []
    return SimpleNamespace(
        _fixtureinfo=SimpleNamespace(name2fixturedefs={'browser': [SimpleNamespace(func=function)]}),
        iter_markers=lambda: iter(marks),
        path=path,
    )


def config(collect=False):
    return SimpleNamespace(option=SimpleNamespace(collectonly=collect))


def test_mixed_runtime_collection_is_refused_before_execution():
    with pytest.raises(pytest.UsageError, match='Mixed native'):
        conftest.pytest_collection_modifyitems([item(native), item(managed)], config())


def test_existing_skip_does_not_start_or_conflict_with_a_runtime():
    conftest.pytest_collection_modifyitems([item(native, skipped=True), item(managed)], config())


def test_collection_only_never_starts_runtime_and_remains_available():
    conftest.pytest_collection_modifyitems([item(native), item(managed)], config(collect=True))


def test_asyncio_file_cannot_share_a_process_with_managed_browser(tmp_path):
    source = tmp_path / 'test_async.py'
    source.write_text('import asyncio\ndef invoke():\n    return asyncio.run(work())\n')
    with pytest.raises(pytest.UsageError, match='Mixed'):
        conftest.pytest_collection_modifyitems([item(managed), item(managed, path=source)], config())
