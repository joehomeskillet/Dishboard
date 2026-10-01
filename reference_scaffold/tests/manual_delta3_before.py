"""Manual historical capture; deliberately excluded from normal test discovery.

Run explicitly through gate.sh. Git blobs are verified byte-for-byte before use;
the current checkout and shared renderers are never replaced. Captures supplement
the original red-run evidence, rather than pretending to be contemporaneous.
"""
# ruff: noqa: S101 -- assertions verify the explicitly requested historical evidence.
from __future__ import annotations

import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest
from flask import Response
from jinja2 import ChoiceLoader, DictLoader

from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import _login, _payload
from test_menu_collection import _save, _scope

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path('/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18/.claude/state/'
                'claude-session-2026-09-29/audit/DELTA')
CASES = [
    ('01', '895a9fb7', 'operations', 'admin-settings-bereiche.css', 'operations', '/admin/bereiche-zeiten'),
    ('02', '44707ea5', 'menu_collection', 'admin-menu-collection.css', 'staff_guest', '/admin/cafeteria/menues'),
    ('02', '44707ea5', 'menu_collection', 'admin-menu-collection.css', 'patient', '/admin/patienten/menues'),
]


def _git(*args: str) -> bytes:
    failures = []
    for _ in range(2):
        # Arguments come only from fixed refs and the explicit source list below.
        result = subprocess.run(  # noqa: S603 -- fixed, read-only Git argument list; no shell.
            ['rtk', 'git', *args], cwd=ROOT, capture_output=True, check=False, timeout=20,  # noqa: S607 -- required host RTK command.
        )
        if result.returncode == 0:
            return result.stdout
        failures.append((result.stdout + result.stderr).decode('utf-8', errors='replace'))
    raise AssertionError('Git capture failed twice: ' + '\n'.join(failures))


@lru_cache
def _sources(base: str, template: str, stylesheet: str):
    paths = [f'templates/admin/{template}.html', 'static/app.css', 'static/admin.js', f'static/{stylesheet}']
    contents, hashes = {}, {}
    for path in paths:
        spec = f'{base}:reference_scaffold/cafeteria/{path}'
        raw = _git('show', '--no-color', spec)
        blob = b'blob ' + str(len(raw)).encode() + b'\0' + raw
        assert hashlib.sha1(blob, usedforsecurity=False).hexdigest() == _git('rev-parse', spec).decode().strip()
        contents[path] = raw.decode('utf-8')
        hashes[path] = hashlib.sha256(raw).hexdigest()
    return contents, hashes


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('coarse', [False, True])
@pytest.mark.parametrize('package,base,template,stylesheet,profile,route', CASES)
def test_historical_viewport_capture(
    admin_app, admin_engine, browser, live_server, monkeypatch,  # noqa: F811
    package, base, template, stylesheet, profile, route, width, coarse,
):
    contents, hashes = _sources(base, template, stylesheet)
    original_loader = admin_app.jinja_loader
    monkeypatch.setattr(admin_app, 'jinja_loader', ChoiceLoader([
        DictLoader({f'admin/{template}.html': contents[f'templates/admin/{template}.html']}),
        original_loader,
    ]))
    admin_app.jinja_env.cache.clear()
    original_static = admin_app.view_functions['static']

    def historical_static(filename):
        source = contents.get('static/' + filename)
        if source is None:
            return original_static(filename=filename)
        return Response(source, mimetype='text/css' if filename.endswith('.css') else 'text/javascript')

    monkeypatch.setitem(admin_app.view_functions, 'static', historical_static)
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    if package == '02':
        payload = _payload(staff=profile == 'staff_guest')
        payload.update(description='Beschreibung <b>kein HTML</b>', note='Hinweis & Vorsicht')
        _save(admin_engine, _scope(client, admin_engine, profile), title='Menü <&> - 0', payload=payload)
    cookie = client.get_cookie(admin_app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(base_url=live_server, has_touch=coarse, reduced_motion='reduce',
                             viewport={'width': width, 'height': 900 if width == 1440 else 844}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        assert page.goto(route).status == 200
        page.evaluate('document.fonts.ready')
        assert page.locator('main details').count() > 0, 'Historical template was not loaded'
        assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
        folder = EVIDENCE / f'DELTA-3-{package}' / 'before-reconstructed'
        folder.mkdir(parents=True, exist_ok=True)
        stem = f'{profile}-{width}-{"coarse" if coarse else "fine"}'
        page.screenshot(path=str(folder / f'{stem}.png'))
        assert page.evaluate("matchMedia('(pointer: coarse)').matches") is coarse
        assert not posts
        (folder / f'{stem}.json').write_text(json.dumps({
            'historical_base': base, 'reconstructed': True, 'route': route,
            'viewport': page.viewport_size, 'coarse_before_and_after_capture': coarse,
            'browser': browser.version, 'source_sha256': hashes,
        }, ensure_ascii=False, indent=2))
