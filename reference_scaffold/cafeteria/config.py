from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from urllib.parse import quote

from .credentials import (
    build_role_database_url,
    database_url_password,
    validate_database_role_secret,
)

DEMO_SECRET = 'demo-only-not-for-production'
_PLACEHOLDER_SECRETS = frozenset({
    'change-me',
    'changeme',
    'default',
    'demo',
    'password',
    'secret',
    '***',
})
_CONFIG_FILE = Path(__file__).resolve()


def _default_sql_path(filename: str) -> str:
    app_or_scaffold = _CONFIG_FILE.parent.parent
    repo_candidate = app_or_scaffold.parent / 'database' / filename
    packaged_candidate = app_or_scaffold / 'database' / filename
    if repo_candidate.is_file():
        return str(repo_candidate)
    if packaged_candidate.is_file():
        return str(packaged_candidate)
    return str(repo_candidate)


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, 'true' if default else 'false').strip().lower() in {'1', 'true', 'yes', 'on'}


def _secret(name: str, default: str = '') -> str:
    file_path = os.getenv(f'{name}_FILE')
    if file_path:
        try:
            return Path(file_path).read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            if not _bool('DEMO_MODE'):
                raise
    return os.getenv(name, default)


def _redis_url() -> str:
    explicit = os.getenv('SESSION_REDIS_URL')
    if explicit is not None:
        return explicit
    host = os.getenv('REDIS_HOST', 'redis')
    port = os.getenv('REDIS_PORT', '6379')
    database = os.getenv('REDIS_DB', '0')
    password = _secret('REDIS_PASSWORD')
    credentials = f':{quote(password, safe="")}@' if password else ''
    return f'redis://{credentials}{host}:{port}/{database}'


def _database_url() -> str:
    explicit = _secret('DATABASE_URL')
    if explicit:
        return explicit
    user = os.getenv('POSTGRES_USER', 'cafeteria_app')
    password = _secret('POSTGRES_PASSWORD')
    host = os.getenv('POSTGRES_HOST', 'db')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'cafeteria')
    sslmode = os.getenv('POSTGRES_SSLMODE', 'disable')
    credentials = quote(user, safe='')
    if password:
        credentials += ':' + quote(password, safe='')
    return f'postgresql+psycopg://{credentials}@{host}:{port}/{quote(database, safe="")}?sslmode={quote(sslmode, safe="")}'


def _trusted_proxy_peers() -> tuple[str, ...]:
    peers: list[str] = []
    for value in os.getenv('TRUSTED_PROXY_PEERS', '').split(','):
        candidate = value.strip()
        if not candidate:
            continue
        if '/' in candidate:
            raise RuntimeError('TRUSTED_PROXY_PEERS akzeptiert nur einzelne IP-Adressen.')
        try:
            normalized = ipaddress.ip_address(candidate).compressed
        except ValueError as exc:
            raise RuntimeError('TRUSTED_PROXY_PEERS enthält eine ungültige IP-Adresse.') from exc
        if normalized not in peers:
            peers.append(normalized)
    return tuple(peers)


class Config:
    def __init__(self) -> None:
        self.APP_ENV = os.getenv('APP_ENV', 'development').strip().lower()
        self.DEMO_MODE = _bool('DEMO_MODE')
        self.SEED_DEMO = _bool('SEED_DEMO')
        self.DEMO_TODAY = os.getenv('DEMO_TODAY', '2026-09-01' if self.DEMO_MODE else '')
        self.SECRET_KEY = _secret('FLASK_SECRET_KEY', DEMO_SECRET if self.DEMO_MODE else '')
        self.DATABASE_URL = _database_url()
        self.SCHEMA_PATH = os.getenv('SCHEMA_PATH', _default_sql_path('schema.sql'))
        self.SEED_PATH = os.getenv('SEED_PATH', _default_sql_path('seed.sql'))
        self.DEMO_SEED_PATH = os.getenv('DEMO_SEED_PATH', _default_sql_path('seed_demo.sql'))
        self.PERMISSIONS_PATH = os.getenv('PERMISSIONS_PATH', _default_sql_path('permissions.sql'))
        self.POSTGRES_APP_PASSWORD = _secret('POSTGRES_APP_PASSWORD')
        self.POSTGRES_BACKUP_PASSWORD = _secret('POSTGRES_BACKUP_PASSWORD')
        self.POSTGRES_AUTH_ISSUER_PASSWORD = _secret('POSTGRES_AUTH_ISSUER_PASSWORD')
        self.AUTH_ISSUER_DATABASE_URL = ''
        if self.POSTGRES_AUTH_ISSUER_PASSWORD:
            self.AUTH_ISSUER_DATABASE_URL = build_role_database_url(
                self.DATABASE_URL,
                role='cafeteria_auth_issuer',
                password=self.POSTGRES_AUTH_ISSUER_PASSWORD,
            )
        self.ENTRA_ENABLED = _bool('ENTRA_ENABLED')
        self.LOCAL_AUTH_ENABLED = _bool('LOCAL_AUTH_ENABLED')
        self.DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
        self.DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '5'))
        self.DB_POOL_TIMEOUT_SECONDS = int(os.getenv('DB_POOL_TIMEOUT_SECONDS', '10'))
        self.DB_STATEMENT_TIMEOUT_MS = int(os.getenv('DB_STATEMENT_TIMEOUT_MS', '15000'))
        self.DB_LOCK_TIMEOUT_MS = int(os.getenv('DB_LOCK_TIMEOUT_MS', '5000'))
        self.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS = int(os.getenv('DB_IDLE_IN_TRANSACTION_TIMEOUT_MS', '30000'))
        self.SESSION_REDIS_URL = _redis_url()
        self.REDIS_PASSWORD = _secret('REDIS_PASSWORD')
        self.SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'suedhang_menu_session')
        self.SESSION_COOKIE_SECURE = _bool('SESSION_COOKIE_SECURE', True)
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = 'Lax'
        self.PERMANENT_SESSION_LIFETIME = int(os.getenv('SESSION_LIFETIME_SECONDS', '28800'))
        self.APP_PUBLIC_BASE_URL = os.getenv('APP_PUBLIC_BASE_URL', 'http://localhost:8080').rstrip('/')
        self.ENTRA_TENANT_ID = os.getenv('ENTRA_TENANT_ID', '')
        self.ENTRA_CLIENT_ID = os.getenv('ENTRA_CLIENT_ID', '')
        self.ENTRA_CLIENT_SECRET = _secret('ENTRA_CLIENT_SECRET')
        self.TRUSTED_PROXY_PEERS = _trusted_proxy_peers()
        self.MAX_CONTENT_LENGTH = int(os.getenv('MAX_UPLOAD_BYTES', str(5 * 1024 * 1024)))
        self.FRAME_ANCESTORS = os.getenv('FRAME_ANCESTORS', "'self'")
        configured_last_good_dir = os.getenv('LAST_GOOD_DIR')
        # Development-only fallback; production rejects it below.
        self.LAST_GOOD_DIR = configured_last_good_dir or '/tmp/cafeteria-last-good'  # nosec B108

        protected_database_boot = self.APP_ENV in {'production', 'migration'}
        if protected_database_boot:
            if _secret('AUTH_ISSUER_DATABASE_URL'):
                raise RuntimeError(
                    'AUTH_ISSUER_DATABASE_URL ist verboten; '
                    'POSTGRES_AUTH_ISSUER_PASSWORD_FILE verwenden.'
                )
            if not os.getenv('POSTGRES_AUTH_ISSUER_PASSWORD_FILE'):
                raise RuntimeError('POSTGRES_AUTH_ISSUER_PASSWORD_FILE ist erforderlich.')
            validate_database_role_secret(
                self.POSTGRES_AUTH_ISSUER_PASSWORD,
                label='PostgreSQL-Auth-Issuer',
            )
            sibling_secrets = {
                value
                for value in (
                    self.POSTGRES_APP_PASSWORD,
                    self.POSTGRES_BACKUP_PASSWORD,
                    _secret('POSTGRES_PASSWORD'),
                    database_url_password(self.DATABASE_URL),
                )
                if value
            }
            if self.POSTGRES_AUTH_ISSUER_PASSWORD in sibling_secrets:
                raise RuntimeError('PostgreSQL-Auth-Issuer benötigt ein eigenes, separates Secret.')

        if self.APP_ENV == 'production':
            last_good_path = Path(self.LAST_GOOD_DIR)
            # Security deny-list, not a storage destination.
            temporary_roots = (Path('/tmp'), Path('/var/tmp'))  # nosec B108
            if (
                not configured_last_good_dir
                or not last_good_path.is_absolute()
                or any(
                    last_good_path == root or root in last_good_path.parents
                    for root in temporary_roots
                )
            ):
                raise RuntimeError(
                    'LAST_GOOD_DIR muss in Produktion explizit auf persistenten '
                    'absoluten Speicher ausserhalb temporärer Verzeichnisse zeigen.'
                )
            if self.DEMO_MODE or self.SEED_DEMO or self.DEMO_TODAY:
                raise RuntimeError('DEMO_MODE, SEED_DEMO und DEMO_TODAY sind in Produktion verboten.')
            if not self.SECRET_KEY or self.SECRET_KEY == DEMO_SECRET:
                raise RuntimeError('In Produktion ist ein eigenes FLASK_SECRET_KEY erforderlich.')
            if self.ENTRA_ENABLED and (
                not self.ENTRA_TENANT_ID
                or not self.ENTRA_CLIENT_ID
                or not self.ENTRA_CLIENT_SECRET
            ):
                raise RuntimeError('Entra-Konfiguration ist in Produktion unvollständig.')
            if not self.SESSION_REDIS_URL:
                raise RuntimeError('SESSION_REDIS_URL ist in Produktion für Sessions und Rate-Limits erforderlich.')
            if not self.SESSION_COOKIE_SECURE:
                raise RuntimeError('SESSION_COOKIE_SECURE muss in Produktion true sein.')
