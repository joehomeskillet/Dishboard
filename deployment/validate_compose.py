#!/usr/bin/env python3
"""Statische Compose-Pruefung ohne Docker-Engine."""
from __future__ import annotations

from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    print('PyYAML fehlt: python -m pip install pyyaml', file=sys.stderr)
    raise SystemExit(2)

root = Path(__file__).resolve().parent
base = yaml.safe_load((root / 'docker-compose.yml').read_text(encoding='utf-8'))
overlay = yaml.safe_load((root / 'docker-compose.caddy.yml').read_text(encoding='utf-8'))
services = base.get('services', {})
required = {'db', 'redis', 'migrate', 'app', 'backup', 'restore'}
assert required <= set(services), required - set(services)

assert services['db']['image'].startswith('postgres:18.')
assert services['db']['environment']['POSTGRES_USER'] == 'cafeteria_owner'
assert services['db']['environment']['POSTGRES_PASSWORD_FILE'] == '/run/secrets/postgres_owner_password'
assert services['db']['environment']['POSTGRES_INITDB_ARGS'] == '--data-checksums --encoding=UTF8'
assert services['db']['healthcheck']

redis = services['redis']
assert redis['healthcheck']['test'] == ['CMD', '/usr/local/bin/redis-healthcheck.sh']
assert './redis-healthcheck.sh:/usr/local/bin/redis-healthcheck.sh:ro' in redis['volumes']
assert redis['environment']['REDIS_PASSWORD_FILE'] == '/run/secrets/redis_password'
assert 'redis-cli -a' not in (root / 'docker-compose.yml').read_text(encoding='utf-8')
assert '--requirepass "$$(cat /run/secrets/redis_password)"' in (root / 'docker-compose.yml').read_text(encoding='utf-8')

migrate = services['migrate']
assert migrate['environment']['POSTGRES_USER'] == 'cafeteria_owner'
assert migrate['environment']['POSTGRES_APP_PASSWORD_FILE'] == '/run/secrets/postgres_app_password'
assert migrate['environment']['POSTGRES_BACKUP_PASSWORD_FILE'] == '/run/secrets/postgres_backup_password'
assert migrate['command'] == ['python', '/app/manage.py', 'init-db', '--wait-seconds', '60']

app = services['app']
assert app['build']['dockerfile'] == 'deployment/Dockerfile'
assert app['environment']['POSTGRES_HOST'] == 'db'
assert app['environment']['POSTGRES_USER'] == 'cafeteria_app'
assert app['environment']['LAST_GOOD_DIR'] == '/tmp/cafeteria-last-good'
assert app['depends_on']['db']['condition'] == 'service_healthy'
assert app['depends_on']['redis']['condition'] == 'service_healthy'
assert app['depends_on']['migrate']['condition'] == 'service_completed_successfully'
assert app['healthcheck']
assert set(app['secrets']) == {
    'postgres_app_password', 'flask_secret_key', 'entra_client_secret', 'redis_password'
}

assert services['backup']['environment']['POSTGRES_USER'] == 'cafeteria_backup'
assert services['restore']['environment']['POSTGRES_USER'] == 'cafeteria_owner'
assert {'postgres_data', 'postgres_backups', 'redis_data'} <= set(base.get('volumes', {}))
assert {
    'postgres_owner_password', 'postgres_app_password', 'postgres_backup_password',
    'flask_secret_key', 'entra_client_secret', 'redis_password'
} <= set(base.get('secrets', {}))
assert 'caddy' in overlay.get('services', {})
assert overlay['services']['caddy']['depends_on']['app']['condition'] == 'service_healthy'

example = (root / '.env.example').read_text(encoding='utf-8')
for token in ('APP_ENV=development', 'DEMO_TODAY=2026-09-01', 'LAST_GOOD_DIR=/tmp/cafeteria-last-good'):
    assert token in example, token
assert not (root / '.env').exists()

print('Compose-Struktur: OK (statisch; kein Containerstart)')
