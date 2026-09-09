"""Adversarial proof that the corrected recorder catches what the original missed.

Serves one page that fails after DOMContentLoaded while a slow image keeps the
page busy, then records it twice: once with a faithful replica of the original
listener lifetime and fixed delay, once with the corrected shot(). Offline,
local loopback only, no product write and no database.
"""
from __future__ import annotations

import base64
import sys
import tempfile
import threading
import time
from pathlib import Path

from flask import Flask
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

EVIDENCE = Path(__file__).resolve().parents[1] / 'ui-inventory-grok-0909'
sys.path.insert(0, str(EVIDENCE))

from capture import Outputs, shot  # noqa: E402

PIXEL = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
PAGE = """<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Late</title>
</head><body><h1>Late failure</h1><img src="/slow.gif" alt="spaet">
<script>
  window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { console.error('late console failure'); }, 120);
    setTimeout(() => { throw new Error('late page error'); }, 160);
  });
</script></body></html>"""


def serve() -> tuple[object, str]:
    app = Flask(__name__)
    app.add_url_rule('/late', 'late', lambda: (PAGE, 200, {'Content-Type': 'text/html'}))

    def slow_gif():
        time.sleep(0.6)
        return PIXEL, 200, {'Content-Type': 'image/gif'}

    app.add_url_rule('/slow.gif', 'slow', slow_gif)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_port}'


def original_recorder(page, path: str) -> dict:
    """Faithful replica of f136490 capture.shot(): detach right after goto, fixed 250 ms."""
    console: list[str] = []
    failed: list[str] = []

    def on_console(msg) -> None:
        if msg.type in {'error', 'warning'}:
            console.append(f'{msg.type}: {msg.text}')

    def on_pageerror(err) -> None:
        failed.append(str(err))

    page.on('console', on_console)
    page.on('pageerror', on_pageerror)
    try:
        page.goto(path, wait_until='domcontentloaded', timeout=30000)
    finally:
        page.remove_listener('console', on_console)
        page.remove_listener('pageerror', on_pageerror)
    page.wait_for_timeout(250)
    return {'console': console, 'request_failures': failed}


def main() -> int:
    server, live = serve()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            try:
                with tempfile.TemporaryDirectory() as directory:
                    out = Outputs.into(Path(directory))
                    with browser.new_context(base_url=live) as context:
                        before = original_recorder(context.new_page(), '/late')
                    with browser.new_context(base_url=live) as context:
                        after = shot(context.new_page(), '/late', 1440, 900, out=out)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()

    caught_before = any('late console failure' in entry for entry in before['console'])
    caught_after = any('late console failure' in entry for entry in after['console'])
    error_after = any('late page error' in entry for entry in after['request_failures'])
    print(f'original_recorder_console={before["console"]}')
    print(f'original_recorder_pageerrors={before["request_failures"]}')
    print(f'corrected_recorder_console={after["console"]}')
    print(f'corrected_recorder_pageerrors={after["request_failures"]}')
    print(f'corrected_readiness={after["readiness"]}')
    print(f'ORIGINAL_CAUGHT_LATE_CONSOLE={caught_before} '
          f'CORRECTED_CAUGHT_LATE_CONSOLE={caught_after} '
          f'CORRECTED_CAUGHT_LATE_PAGEERROR={error_after}')
    ok = (not caught_before) and caught_after and error_after
    print('REGRESSION_PROOF=' + ('PASS' if ok else 'INCONCLUSIVE'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
