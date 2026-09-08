from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('module', ['local_user_routes', 'routes', 'workflow_routes'])
def test_local_user_routes_register_once_in_fresh_factories(module):
    program = '''
import importlib
import sys
from flask import Flask
module = importlib.import_module('cafeteria.admin.' + sys.argv[1])
minimal = Flask('minimal')
minimal.register_blueprint(module.bp)
from cafeteria import create_app
for app in (minimal, create_app(), create_app()):
    endpoints = [rule.endpoint for rule in app.url_map.iter_rules()]
    for name in ('local_users_list','local_user_new','local_user_create',
                 'local_user_detail','local_user_change','local_user_events'):
        assert endpoints.count('admin.' + name) == 1, name
print('local account blueprint complete without duplicate routes')
'''
    result = subprocess.run([sys.executable, '-B', '-c', program, module],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False,
        timeout=30, env={'APP_ENV': 'development', 'DEMO_MODE': 'true', 'SESSION_REDIS_URL': '',
                         'DATABASE_URL': 'postgresql+psycopg://localhost/menuplan_test_iam_bootstrap'})
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == 'local account blueprint complete without duplicate routes'
