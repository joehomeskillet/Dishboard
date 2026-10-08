"""Collection-only and existing skips must not create false runtime conflicts."""
from types import SimpleNamespace

import pytest

import conftest


@pytest.fixture(autouse=True)
def runner_runtime_guard(monkeypatch):
    monkeypatch.setenv('TEST_GATE_RUNTIME_GUARD', '1')


@pytest.mark.parametrize('flag', [None, '', '0', 'yes'])
def test_direct_pytest_accepts_mixed_runtimes_without_runner_opt_in(tmp_path, monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv('TEST_GATE_RUNTIME_GUARD', raising=False)
    else:
        monkeypatch.setenv('TEST_GATE_RUNTIME_GUARD', flag)
    source = tmp_path / 'test_async.py'
    source.write_text('import asyncio\ndef invoke():\n    return asyncio.run(work())\n')
    conftest.pytest_collection_modifyitems(
        [item(native), item(managed), item(managed, path=source)], config())


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


@pytest.mark.parametrize('selected_browser', ['firefox', 'webkit'])
def test_non_chromium_browser_does_not_request_shared_chromium(selected_browser):
    from _support.browser import browser

    closed = []
    instance = SimpleNamespace(close=lambda: closed.append(selected_browser))
    request = SimpleNamespace(getfixturevalue=lambda name:
                              pytest.fail(f'{selected_browser} must not request {name}'))
    fixture = browser.__wrapped__(request=request, browser_name=selected_browser,
                                  launch_browser=lambda: instance)
    assert next(fixture) is instance
    fixture.close()
    assert closed == [selected_browser]


def test_chromium_browser_requests_shared_fixture_without_owning_its_cleanup():
    from _support.browser import browser

    requested = []
    instance = SimpleNamespace(close=lambda: pytest.fail('Shared fixture owns Chromium cleanup'))

    def getfixturevalue(name):
        requested.append(name)
        return instance

    request = SimpleNamespace(getfixturevalue=getfixturevalue)
    fixture = browser.__wrapped__(request=request, browser_name='chromium',
                                  launch_browser=lambda: pytest.fail('Chromium must reuse shared browser'))
    assert next(fixture) is instance
    fixture.close()
    assert requested == ['shared_browser']
