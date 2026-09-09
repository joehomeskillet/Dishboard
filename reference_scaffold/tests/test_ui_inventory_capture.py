"""Recorder behaviour of the MP-UI-INVENTORY capture helper against a real browser.

These are the four proof gaps Root confirmed: a console failure raised after
DOMContentLoaded must still be recorded, readiness must wait for fonts and images
instead of a fixed delay, an absent publish modal must produce a blocked record
rather than an invented success row, and an ordinary run must leave the versioned
matrix, manifest and original screenshots untouched.
"""
from __future__ import annotations

import base64
import json
import sys
import threading
import time
from pathlib import Path

import pytest
from flask import Flask
from werkzeug.serving import make_server

from test_rendered_ui import browser  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'ui-inventory-grok-0909'
MATRIX_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-route-matrix.json'
MANIFEST_PATH = ROOT / 'docs' / 'superpowers' / 'backlog-0909' / 'ui-before-manifest.json'
sys.path.insert(0, str(EVIDENCE))

from capture import Outputs, capture_publish_dialog, shot  # noqa: E402

# The image is referenced at parse time and served with a real delay, so readiness
# genuinely stays open and the errors land inside the recording window. The original
# recorder detached its listeners right after DOMContentLoaded and reported an empty
# console for exactly this page.
LATE_ERROR = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>Late</title></head><body><h1>Late failure</h1>
<img id="late" src="/slow.gif" alt="spaet">
<script>
  window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { console.error('late console failure'); }, 120);
    setTimeout(() => { throw new Error('late page error'); }, 160);
  });
</script></body></html>"""

SLOW_ASSETS = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>Slow</title></head><body><h1 id="headline">Slow assets</h1>
<img id="late" src="/slow.gif" alt="spaet"></body></html>"""

NO_MODAL = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>No modal</title></head><body><h1>Ohne Dialog</h1></body></html>"""

PIXEL = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
SLOW_IMAGE_SECONDS = 0.6


def _serve(pages: dict[str, str]):
    app = Flask(__name__)

    def make(body: str):
        return lambda: (body, 200, {'Content-Type': 'text/html; charset=utf-8'})

    def slow_gif():
        time.sleep(SLOW_IMAGE_SECONDS)
        return PIXEL, 200, {'Content-Type': 'image/gif'}

    for route, body in pages.items():
        app.add_url_rule(route, endpoint=route.strip('/') or 'root', view_func=make(body))
    app.add_url_rule('/slow.gif', endpoint='slow_gif', view_func=slow_gif)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_port}'


@pytest.fixture
def served():
    started = []

    def start(pages: dict[str, str]) -> str:
        server, live = _serve(pages)
        started.append(server)
        return live

    yield start
    for server in started:
        server.shutdown()
        server.server_close()


def test_console_failure_after_dom_content_loaded_is_recorded(browser, served, tmp_path):  # noqa: F811
    live = served({'/late': LATE_ERROR})
    out = Outputs.into(tmp_path)
    with browser.new_context(base_url=live) as context:
        row = shot(context.new_page(), '/late', 1440, 900, out=out)
    assert any('late console failure' in entry for entry in row['console']), row['console']
    assert any('late page error' in entry for entry in row['request_failures']), row['request_failures']
    assert row['rendered'] is True


def test_readiness_waits_for_late_image_instead_of_a_fixed_delay(browser, served, tmp_path):  # noqa: F811
    live = served({'/slow': SLOW_ASSETS})
    out = Outputs.into(tmp_path)
    with browser.new_context(base_url=live) as context:
        page = context.new_page()
        row = shot(page, '/slow', 1440, 900, out=out)
        pending = page.evaluate(
            '() => Array.from(document.images).filter(img => !img.complete).length'
        )
    assert row['readiness']['load'] is True
    assert row['readiness']['fonts'] is True
    assert row['readiness']['images'] is True
    assert row['readiness']['error'] is None
    assert pending == 0
    assert row['computed_fonts']['body']
    assert 'platform_source' in row['computed_fonts']


def test_absent_publish_modal_produces_a_blocked_record_not_a_success(browser, served, tmp_path):  # noqa: F811
    live = served({'/admin/cafeteria': NO_MODAL})
    out = Outputs.into(tmp_path)
    with browser.new_context(base_url=live) as context:
        rows, blocks = capture_publish_dialog(context.new_page(), out=out)
    assert rows == []
    assert len(blocks) == 1
    assert blocks[0]['id'] == 'publish_dialog'
    assert blocks[0]['status'] == 'blocked_modal_not_open'
    assert 'publish trigger absent' in blocks[0]['error']
    assert not list(out.screen_dir.glob('*dialog-publish*.png'))


def test_redirected_run_leaves_versioned_outputs_untouched(browser, served, tmp_path):  # noqa: F811
    matrix_before = MATRIX_PATH.read_bytes()
    manifest_before = MANIFEST_PATH.read_bytes()
    screenshots_before = {
        path.name: path.read_bytes()
        for path in sorted((EVIDENCE / 'screenshots').glob('*.png'))
    }
    assert screenshots_before, 'original evidence screenshots must exist'

    live = served({'/late': LATE_ERROR})
    out = Outputs.into(tmp_path)
    with browser.new_context(base_url=live) as context:
        row = shot(context.new_page(), '/late', 390, 844, out=out)
    out.manifest_paths[0].write_text(
        json.dumps({'captures': [row]}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    assert out.manifest_paths[0].is_file()
    assert list(out.screen_dir.glob('*.png'))
    assert MATRIX_PATH.read_bytes() == matrix_before
    assert MANIFEST_PATH.read_bytes() == manifest_before
    assert {
        path.name: path.read_bytes()
        for path in sorted((EVIDENCE / 'screenshots').glob('*.png'))
    } == screenshots_before


def test_default_outputs_still_point_at_the_versioned_baseline() -> None:
    default = Outputs()
    assert default.screen_dir == EVIDENCE / 'screenshots'
    assert MANIFEST_PATH in default.manifest_paths
    assert EVIDENCE / 'ui-before-manifest.json' in default.manifest_paths
    redirected = Outputs.into(Path('/tmp/example-capture'))
    assert MANIFEST_PATH not in redirected.manifest_paths
    assert redirected.screen_dir == Path('/tmp/example-capture/screenshots')
