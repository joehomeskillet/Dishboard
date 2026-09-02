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
assert base['x-app-image']['image'] == '${APP_IMAGE:?Set APP_IMAGE to an immutable image digest}'

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
assert '--requirepass' not in (root / 'docker-compose.yml').read_text(encoding='utf-8')
assert '--aclfile /tmp/redis-users.acl' in (root / 'docker-compose.yml').read_text(encoding='utf-8')

migrate = services['migrate']
assert 'env_file' not in migrate
assert migrate['environment']['APP_ENV'] == 'migration'
assert migrate['environment']['DEMO_MODE'] == 'false'
assert migrate['environment']['SEED_DEMO'] == 'false'
assert migrate['environment']['DEMO_TODAY'] == ''
assert migrate['environment']['ENTRA_ENABLED'] == 'false'
assert migrate['environment']['POSTGRES_USER'] == 'cafeteria_owner'
assert migrate['environment']['POSTGRES_APP_PASSWORD_FILE'] == '/run/secrets/postgres_app_password'
assert migrate['environment']['POSTGRES_BACKUP_PASSWORD_FILE'] == '/run/secrets/postgres_backup_password'
assert migrate['environment']['POSTGRES_AUTH_ISSUER_PASSWORD_FILE'] == (
    '/run/secrets/postgres_auth_issuer_password'
)
assert set(migrate['secrets']) == {
    'postgres_owner_password', 'postgres_app_password', 'postgres_backup_password',
    'postgres_auth_issuer_password',
}
assert set(migrate['environment']).isdisjoint({
    'ENTRA_TENANT_ID', 'ENTRA_CLIENT_ID', 'FLASK_SECRET_KEY_FILE',
    'ENTRA_CLIENT_SECRET_FILE', 'REDIS_PASSWORD_FILE',
})
assert migrate['command'] == ['python', '/app/manage.py', 'init-db', '--wait-seconds', '60']

app = services['app']
assert app['build']['dockerfile'] == 'deployment/Dockerfile'
assert app['environment']['APP_IMAGE'] == '${APP_IMAGE}'
assert app['environment']['POSTGRES_HOST'] == 'db'
assert app['environment']['POSTGRES_USER'] == 'cafeteria_app'
assert app['environment']['POSTGRES_AUTH_ISSUER_PASSWORD_FILE'] == (
    '/run/secrets/postgres_auth_issuer_password'
)
assert app['environment']['LAST_GOOD_DIR'] == '/var/lib/cafeteria/last-good'
assert 'last_good_data:/var/lib/cafeteria' in app['volumes']
assert app['depends_on']['db']['condition'] == 'service_healthy'
assert app['depends_on']['redis']['condition'] == 'service_healthy'
assert app['depends_on']['migrate']['condition'] == 'service_completed_successfully'
assert app['healthcheck']
assert set(app['secrets']) == {
    'postgres_app_password', 'postgres_auth_issuer_password', 'flask_secret_key',
    'entra_client_secret', 'redis_password',
}
assert app['networks']['cafeteria_internal']['ipv4_address'] == '172.31.213.20'

assert services['backup']['environment']['POSTGRES_USER'] == 'cafeteria_backup'
assert services['restore']['environment']['POSTGRES_USER'] == 'cafeteria_owner'
restore_control_mount = './postgres-restore-control.sh:/usr/local/bin/postgres-restore-control.sh:ro'
assert restore_control_mount in services['backup']['volumes']
assert restore_control_mount in services['restore']['volumes']
assert services['restore']['command'] == [
    'restore-stage', '/backups/restore.dump', '/backups/restore.dump.sha256'
]
assert {'postgres_data', 'postgres_backups', 'redis_data', 'last_good_data'} <= set(base.get('volumes', {}))
assert {
    'postgres_owner_password', 'postgres_app_password', 'postgres_backup_password',
    'postgres_auth_issuer_password', 'flask_secret_key', 'entra_client_secret', 'redis_password'
} <= set(base.get('secrets', {}))
network = base['networks']['cafeteria_internal']
assert network['driver'] == 'bridge'
assert network['ipam']['config'] == [
    {'subnet': '172.31.213.0/24', 'gateway': '172.31.213.1'}
]
assert 'caddy' in overlay.get('services', {})
assert overlay['services']['caddy']['depends_on']['app']['condition'] == 'service_healthy'
assert overlay['services']['caddy']['environment']['CAFETERIA_DOMAIN'] == '${CAFETERIA_DOMAIN:-dishboard.joelduss.xyz}'
assert overlay['services']['caddy']['networks']['cafeteria_internal']['ipv4_address'] == '172.31.213.10'

example = (root / '.env.example').read_text(encoding='utf-8')
for token in (
    'APP_ENV=production',
    'APP_IMAGE=registry.example.invalid/dishboard@sha256:REPLACE_WITH_IMAGE_DIGEST',
    'APP_PUBLIC_BASE_URL=https://dishboard.joelduss.xyz',
    'DEMO_MODE=false', 'SEED_DEMO=false', 'DEMO_TODAY=', 'SESSION_COOKIE_SECURE=true',
    'TRUSTED_PROXY_PEERS=172.31.213.1,172.31.213.10',
    'LOCAL_AUTH_ENABLED=false',
    'LAST_GOOD_DIR=/var/lib/cafeteria/last-good',
    'RESTORE_CONTROLLER_HEARTBEAT_SECONDS=5',
    'RESTORE_CONTROLLER_TIMEOUT_SECONDS=30',
    'RESTORE_ROLLBACK_RETENTION_SECONDS=604800',
    'ENTRA_ENABLED=false', 'CAFETERIA_DOMAIN=dishboard.joelduss.xyz',
):
    assert token in example, token
retention_service = (root / 'systemd' / 'dishboard-retention-prune.service').read_text(
    encoding='utf-8'
)
retention_timer = (root / 'systemd' / 'dishboard-retention-prune.timer').read_text(
    encoding='utf-8'
)
assert 'restore.sh --prune-retained' in retention_service
assert 'Type=oneshot' in retention_service
assert 'OnCalendar=daily' in retention_timer
assert 'Persistent=true' in retention_timer
assert not (root / '.env').exists()
bootstrap = (root / 'bootstrap.sh').read_text(encoding='utf-8')
assert bootstrap.count('generate_secret secrets/postgres_auth_issuer_password.txt 48') == 1
assert 'AUTH_ISSUER_DATABASE_URL' not in (root / 'docker-compose.yml').read_text(encoding='utf-8')

print('Compose-Struktur: OK (statisch; kein Containerstart)')
