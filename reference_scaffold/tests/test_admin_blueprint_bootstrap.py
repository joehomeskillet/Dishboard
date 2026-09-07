from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('first_module', [
    'routes', 'workflow_routes', 'api_routes', 'menu_collection_routes',
    'week_management_routes', 'display_routes', 'print_routes', 'week_review_routes',
    'recipe_routes', 'recipe_revision_routes', 'recipe_image_routes', 'cookbook_routes',
])
def test_admin_blueprint_is_complete_before_first_registration(first_module: str) -> None:
    # Fresh interpreters expose ordering bugs hidden by pytest's shared import cache.
    program = '''
import importlib
import sys
from flask import Flask, url_for

module = importlib.import_module('cafeteria.admin.' + sys.argv[1])
minimal = Flask('minimal')
minimal.register_blueprint(module.bp)

import cafeteria
applications = [minimal, cafeteria.create_app(), cafeteria.create_app()]
expected = {
    'admin.api_overview', 'admin.api_key_create', 'admin.api_key_revoke',
    'admin.cafeteria', 'admin.patienten', 'admin.export_csv',
    'admin.menu_collection', 'admin.week_management', 'admin.display_settings',
    'admin.print_week', 'admin.week_review_get', 'admin.week_review_post',
    'admin.recipes_list', 'admin.recipe_new', 'admin.recipe_edit', 'admin.recipe_form_rows',
    'admin.recipe_status', 'admin.recipe_revisions', 'admin.recipe_freeze',
    'admin.recipe_revision', 'admin.recipe_scale', 'admin.recipe_images', 'admin.recipe_asset',
    'admin.cookbooks_list', 'admin.cookbook_new', 'admin.cookbook_edit',
    'admin.cookbook_recipes', 'admin.cookbook_status',
}
for app in applications:
    endpoints = [rule.endpoint for rule in app.url_map.iter_rules()]
    assert expected <= set(endpoints), sorted(expected - set(endpoints))
    for endpoint in expected:
        assert endpoints.count(endpoint) == 1, endpoint
    with app.test_request_context():
        assert url_for('admin.api_overview') == '/admin/api'
        assert url_for('admin.api_key_create') == '/admin/api/keys'
        assert url_for('admin.api_key_revoke', public_id='example') == '/admin/api/keys/example/revoke'
        assert url_for('admin.recipes_list') == '/admin/rezepte'
        assert url_for('admin.cookbooks_list') == '/admin/kochbuecher'
        recipe_id = '00000000-0000-4000-8000-000000000001'
        assert url_for('admin.recipe_edit', recipe_id=recipe_id) == '/admin/rezepte/' + recipe_id
        assert url_for('admin.recipe_images', recipe_id=recipe_id) == '/admin/rezepte/' + recipe_id + '/bilder'
for app in applications[1:]:
    assert app.test_client().get('/admin/api').status_code == 401
    assert app.test_client().get('/admin/rezepte').status_code == 401
    assert app.test_client().get('/admin/kochbuecher').status_code == 401
    for engine in ('cafeteria_db', 'cafeteria_auth_issuer_db'):
        if engine in app.extensions:
            app.extensions[engine].dispose()
print('complete blueprint: minimal app and two real factories')
'''
    result = subprocess.run(
        [sys.executable, '-c', program, first_module],
        cwd=Path(__file__).resolve().parents[1],
        env={
            'APP_ENV': 'development',
            'DEMO_MODE': 'true',
            'SESSION_REDIS_URL': '',
            'DATABASE_URL': 'postgresql+psycopg://localhost/menuplan_test_blueprint',
        },
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == 'complete blueprint: minimal app and two real factories'
