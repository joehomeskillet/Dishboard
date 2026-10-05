"""One managed Playwright runtime and Chromium per pytest process."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Playwright


@pytest.fixture(scope='session')
def shared_browser(playwright: Playwright, browser_type_launch_args: dict,
                   connect_options: dict | None) -> Iterator[Browser]:
    options = {'headless': True, 'args': ['--no-sandbox', '--disable-dev-shm-usage'],
               **browser_type_launch_args}
    instance = (playwright.chromium.connect(**connect_options) if connect_options
                else playwright.chromium.launch(**options))
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture(scope='session')
def browser(shared_browser: Browser, browser_name: str, launch_browser) -> Iterator[Browser]:
    # Retain pytest-playwright's browser_name parametrization and non-Chromium CLI support.
    if browser_name == 'chromium':
        yield shared_browser
    else:
        instance = launch_browser()
        try:
            yield instance
        finally:
            instance.close()
