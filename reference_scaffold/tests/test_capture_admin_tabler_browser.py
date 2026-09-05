from __future__ import annotations

# ruff: noqa: F811

import sys
from pathlib import Path

import pytest
from flask import Flask, make_response, redirect, request
from playwright.sync_api import Browser
from sqlalchemy import Engine, text

from cafeteria.admin import week_review_routes  # noqa: F401
from cafeteria.component_catalog_store import create_component
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, _login, _scope
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from capture_admin_live_proof import capture_viewport  # noqa: E402

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')


@pytest.mark.parametrize('viewport', ['mobile', 'desktop'])
def test_complete_read_only_live_capture_on_real_tabler_fixture(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,
    viewport: str, tmp_path: Path,
) -> None:
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    _save(admin_engine, 'staff_guest', _staff_values())
    _save(admin_engine, 'patient', _patient_values())
    for profile in ('staff_guest', 'patient'):
        create_component(admin_engine, _scope(admin_engine, actor, profile),
                         'side', 'Reis', 'CH', 'current', (), ())

    # Synthetic login transport only; every admin route/template and DB authorization is real.
    def local_login():
        if request.method == 'POST':
            response = redirect('/admin/cafeteria')
            response.set_cookie('session', cookie.value, httponly=True)
            return response
        return make_response('<form method="post"><input name="username">'
                             '<input name="password" type="password">'
                             '<button type="submit">Anmelden</button></form>')

    admin_app.add_url_rule('/auth/local', view_func=local_login, methods=['GET', 'POST'])

    @admin_app.after_request
    def csp(response):
        response.headers['Content-Security-Policy'] = "script-src 'self'; style-src 'self'"
        return response

    with admin_engine.connect() as connection:
        before = connection.execute(text('''
            SELECT (SELECT count(*) FROM cafeteria.menu_items),
                   (SELECT count(*) FROM cafeteria.audit_events),
                   (SELECT count(*) FROM cafeteria.publication_revisions)
        ''')).one()
    proof = {'checks': {}, 'pages': [], 'catalogs': {}, 'unavailable': [], 'failures': []}
    capture_viewport(browser, live_server, tmp_path, viewport, 'fixture-only', proof, csv_preview=True)
    assert proof['failures'] == [], ', '.join(proof['failures'])
    assert proof['unavailable'] == []
    assert len(proof['pages']) == 21
    assert all(proof['checks'].values())
    for family in ('cafeteria', 'patienten'):
        prefix = f'{viewport}.{family}'
        assert proof['checks'][f'{prefix}.week_review.http_200']
        assert proof['checks'][f'{prefix}.component_detail.public_id']
        assert proof['catalogs'][prefix]['existing_components'] == 1
        assert proof['checks'][f'{prefix}.menus.local_assets_http_200']
        assert proof['checks'][f'{prefix}.menus.no_legacy_app_css']
        assert proof['checks'][f'{prefix}.menus.one_tabler_no_extra_bootstrap']
        nav_check = 'nav_keyboard_collapses' if viewport == 'mobile' else 'nav_fixed_desktop'
        assert proof['checks'][f'{prefix}.menus.{nav_check}']
    with admin_engine.connect() as connection:
        after = connection.execute(text('''
            SELECT (SELECT count(*) FROM cafeteria.menu_items),
                   (SELECT count(*) FROM cafeteria.audit_events),
                   (SELECT count(*) FROM cafeteria.publication_revisions)
        ''')).one()
    assert tuple(after) == tuple(before)
