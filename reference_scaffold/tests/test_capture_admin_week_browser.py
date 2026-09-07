"""DB-free real browser proof of saved-week scope across a simulated date change."""
from __future__ import annotations

import json
import sys
from contextlib import nullcontext
from datetime import date, timedelta
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
from flask import Flask, redirect, render_template_string, request
from werkzeug.serving import make_server

from test_rendered_ui import browser  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import capture_admin_live_proof as tool  # noqa: E402

SAVED = date(2026, 8, 31)
CURRENT = date(2026, 9, 7)
SHELL = """{% extends 'admin/base_tabler.html' %}
{% block sidebar %}
<aside class="navbar navbar-vertical navbar-expand-xl admin-sidebar">
 <div class="container-fluid">
  <button class="navbar-toggler btn" data-bs-toggle="collapse" data-bs-target="#sidebar-menu"
   aria-controls="sidebar-menu" aria-expanded="false" aria-label="Menü">Menü</button>
  <div class="collapse navbar-collapse admin-nav-collapse" id="sidebar-menu">
   <nav class="admin-nav" aria-label="Backend">
   {% for item in ['menues', 'wochen', 'komponenten'] %}
    <a href="/admin/{{ family }}/{{ item }}" {% if section == item %}aria-current="page"{% endif %}>{{ item }}</a>
   {% endfor %}
   </nav>
  </div>
 </div>
</aside>
{% endblock %}
{% block main_attributes %}data-week="{{ week }}"{% endblock %}
{% block content %}{{ content|safe }}{% endblock %}
"""


@pytest.mark.parametrize(('viewport', 'selected', 'fault', 'weekend'), [
    ('desktop', '2026-08-31', None, False),
    ('mobile', '2026-08-31', None, True),
    ('desktop', None, None, False),
    ('desktop', '2026-09-07', None, False),
    ('desktop', '2026-08-31', 'preview404', False),
    ('desktop', '2026-08-31', 'review404', False),
    ('desktop', '2026-08-31', 'review500', False),
    ('desktop', '2026-08-31', 'copy404', False),
    ('desktop', '2026-08-31', 'editor_scope', False),
])
def test_explicit_saved_week_and_missing_week_keep_read_only_coverage(
    browser, tmp_path, monkeypatch, viewport, selected, fault, weekend,  # noqa: F811
):
    app = Flask(__name__, template_folder=str(ROOT / 'reference_scaffold/cafeteria/templates'),
                static_folder=str(ROOT / 'reference_scaffold/cafeteria/static'), static_url_path='/static')
    app.secret_key = 'synthetic-browser-fixture'
    visits = []
    saved_state = {'week': SAVED.isoformat(), 'state': 'draft'}
    before = dict(saved_state)

    @app.before_request
    def observe():
        visits.append((request.method, request.path, request.args.get('week')))

    @app.after_request
    def csp(response):
        response.headers['Content-Security-Policy'] = "script-src 'self'; style-src 'self'"
        return response

    @app.route('/auth/local', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            return redirect('/admin/cafeteria')
        return ('<form method="post"><input name="username"><input name="password" type="password">'
                '<button type="submit">Anmelden</button></form>')

    @app.route('/admin/<family>')
    @app.route('/admin/<family>/<path:section>')
    def admin(family, section=''):
        profile = 'patient' if family == 'patienten' else 'staff_guest'
        week = date.fromisoformat(request.args.get('week', CURRENT.isoformat()))
        source = week - timedelta(days=7) if section == 'copy' else week
        if section in {'preview', 'wochen/pruefung', 'copy'} and source != SAVED:
            return 'No saved week', 404
        fault_section = {'preview404': 'preview', 'review404': 'wochen/pruefung',
                         'review500': 'wochen/pruefung', 'copy404': 'copy'}.get(fault)
        if section == fault_section:
            return 'Required view unavailable', 500 if fault == 'review500' else 404
        content = ''
        if not section:
            day_count = 7 if profile == 'patient' or weekend else 5
            link_week = CURRENT if fault == 'editor_scope' else week
            for offset in range(day_count):
                for _ in range(4 if profile == 'patient' else 2):
                    day = week + timedelta(days=offset)
                    content += (f'<article class="menu-slot" data-day="{day}"><a '
                                f'href="/admin/{family}/menu?week={link_week}&day={day}">Menü</a></article>')
            content += f'<a target="_blank" rel="noopener" href="/admin/{family}/preview?week={week}">Vorschau</a>'
        elif section in {'menues', 'wochen'}:
            content = (f'<nav aria-label="Profil"><a aria-current="page" '
                       f'href="/admin/{family}/{section}">Profil</a></nav>')
        elif section == 'menu':
            content = f'<form action="/admin/{family}/menu"><input name="row_version" type="hidden" value="1"></form>'
        elif section == 'preview':
            return (f'<div class="preview-banner" role="status">PREVIEW</div>'
                    f'<section data-preview="last-saved" data-profile="{profile}" '
                    f'data-week="{week}" data-workflow-state="draft"></section>')
        elif section == 'wochen/pruefung':
            content = '<h1>Wochenkopf und Servicehinweise prüfen</h1><div role="status">Geprüft</div>'
        elif section == 'copy':
            fields = {'_csrf': 'synthetic', 'source_week': source, 'target_week': week, 'target_row_version': 0}
            content = f'<form method="post" action="/admin/{family}/copy">' + ''.join(
                f'<input type="hidden" name="{name}" value="{value}">' for name, value in fields.items()) + '</form>'
        return render_template_string(SHELL, family=family, profile=profile, section=section,
                                      week=week.isoformat(), content=content)

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    outdir = tmp_path / 'proof'
    argv = ['proof', '--outdir', str(outdir), '--base-url', base]
    if selected is not None:
        argv += ['--week', selected]
    monkeypatch.setattr(sys, 'argv', argv)
    monkeypatch.setattr(tool, '_password', lambda: 'synthetic-password')
    monkeypatch.setattr(tool, 'VIEWPORTS', {viewport: tool.VIEWPORTS[viewport]})
    monkeypatch.setattr(tool, 'sync_playwright', lambda: nullcontext(SimpleNamespace(
        chromium=SimpleNamespace(launch=lambda **_kwargs: nullcontext(browser)))))
    try:
        result = tool.main()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    proof = json.loads((outdir / 'proof.json').read_text())
    expected_week = selected or CURRENT.isoformat()
    success = selected == SAVED.isoformat() and fault is None
    assert result == (0 if success else 1), proof['failures']
    assert proof['status'] == ('passed' if success else 'failed')
    assert proof['selected_week'] == expected_week
    assert set(proof['weeks'].values()) == {expected_week}
    assert saved_state == before
    assert [visit for visit in visits if visit[0] not in {'GET', 'HEAD'}] == [('POST', '/auth/local', None)]
    assert not any('TimeoutError' in failure for failure in proof['failures'])
    for family in ('cafeteria', 'patienten'):
        prefix = f'{viewport}.{family}'
        assert proof['checks'][f'{prefix}.overview.slots'] is True
        assert proof['checks'][f'{prefix}.catalog.local_assets_http_200'] is True
        assert f'{prefix}.copy.http_200' in proof['checks']
        assert f'{prefix}.week_review.http_200' in proof['checks']
        for suffix in ('preview', 'wochen/pruefung'):
            assert ('GET', f'/admin/{family}/{suffix}', expected_week) in visits
        assert ('GET', f'/admin/{family}/copy',
                (date.fromisoformat(expected_week) + timedelta(days=7)).isoformat()) in visits
        if expected_week != SAVED.isoformat():
            assert proof['checks'][f'{prefix}.preview.saved_week_exists'] is False
            assert proof['checks'][f'{prefix}.week_review.saved_week_exists'] is False
        if success:
            assert all(proof['checks'].values())
        for section in ('preview', 'week_review', 'copy'):
            if proof['checks'][f'{prefix}.{section}.http_200'] is False:
                assert not any(page['name'] == f'{prefix}.{section}' for page in proof['pages'])
                assert f'{prefix}.{section}.no_inline_style' not in proof['checks']
