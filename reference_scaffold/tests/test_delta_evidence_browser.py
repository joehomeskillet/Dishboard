"""Requested-viewport evidence keeps emulated pointer/target sizes on long pages."""
from __future__ import annotations

import json
import struct

import pytest

from delta_browser_evidence import capture_delta
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('mobile', [False, True])
@pytest.mark.parametrize('javascript', [False, True])
def test_viewport_capture_keeps_touch_media(browser, tmp_path, mobile, javascript):  # noqa: F811
    with browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True,
                             is_mobile=mobile, java_script_enabled=javascript) as context:
        page = context.new_page()
        page.set_content('''<meta name="viewport" content="width=device-width,initial-scale=1">
            <style>body {height:1800px; margin:0; --app-control-min-height:36px;}
            button {height:var(--app-control-min-height)}
            @media(pointer:coarse) {body {--app-control-min-height:44px}}</style>
            <main><button class="ui-sem-control">Action</button><span id="private">fixture</span></main>''')
        path = tmp_path / 'capture.png'
        capture_delta(page, path, True, masks=[page.locator('#private')])
        assert page.evaluate("matchMedia('(pointer: coarse)').matches")
        metrics = json.loads(path.with_suffix('.json').read_text())
        assert metrics['after']['minimum'] == '44px'
        assert metrics['after']['controls'][0]['height'] == 44
        assert struct.unpack('>II', path.read_bytes()[16:24]) == (390, 844)
        assert page.locator('#private').is_visible()
