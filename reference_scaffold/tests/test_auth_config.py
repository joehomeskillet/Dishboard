from __future__ import annotations

from pathlib import Path

import pytest

from cafeteria.config import Config


def _production_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('DEMO_MODE', 'false')
    monkeypatch.setenv('SEED_DEMO', 'false')
    monkeypatch.setenv('DEMO_TODAY', '')
    monkeypatch.setenv('FLASK_SECRET_KEY', 'production-only-long-flask-secret')
    monkeypatch.setenv('ENTRA_ENABLED', 'true')
    monkeypatch.setenv('ENTRA_TENANT_ID', '00000000-0000-0000-0000-000000000001')
    monkeypatch.setenv('ENTRA_CLIENT_ID', '00000000-0000-0000-0000-000000000002')
    monkeypatch.setenv('ENTRA_CLIENT_SECRET', 'production-only-entra-secret')
    monkeypatch.setenv('SESSION_REDIS_URL', 'redis://:production-only@redis:6379/0')
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'true')
    monkeypatch.setenv('LAST_GOOD_DIR', '/var/lib/cafeteria/last-good')
    monkeypatch.setenv(
        'DATABASE_URL',
        'postgresql+psycopg://cafeteria_app:App-Role-2026-A7bQ9xV4kM2rP8tN@db/cafeteria',
    )
    issuer_secret = tmp_path / 'issuer-password.txt'
    issuer_secret.write_text('Issuer-Role-2026-Z8yW6uT4sR2qP9nM\n', encoding='utf-8')
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD_FILE', str(issuer_secret))


def test_production_rejects_missing_or_placeholder_auth_issuer_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _production_environment(monkeypatch, tmp_path)
    monkeypatch.delenv('AUTH_ISSUER_DATABASE_URL', raising=False)
    monkeypatch.delenv('AUTH_ISSUER_DATABASE_URL_FILE', raising=False)
    monkeypatch.delenv('POSTGRES_AUTH_ISSUER_PASSWORD_FILE', raising=False)

    with pytest.raises(RuntimeError, match='POSTGRES_AUTH_ISSUER_PASSWORD_FILE'):
        Config()

    for placeholder in ('change-me', 'default-issuer-secret', 'demo-auth-password'):
        placeholder_file = tmp_path / 'placeholder.txt'
        placeholder_file.write_text(placeholder + '\n', encoding='utf-8')
        monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD_FILE', str(placeholder_file))
        with pytest.raises(RuntimeError, match='Issuer|stark|32'):
            Config()


def test_production_accepts_only_dedicated_issuer_role(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _production_environment(monkeypatch, tmp_path)
    monkeypatch.setenv(
        'AUTH_ISSUER_DATABASE_URL',
        'postgresql+psycopg://cafeteria_app:strong-runtime-secret@db/cafeteria',
    )
    with pytest.raises(RuntimeError, match='AUTH_ISSUER_DATABASE_URL'):
        Config()

    monkeypatch.delenv('AUTH_ISSUER_DATABASE_URL')
    config = Config()
    assert config.AUTH_ISSUER_DATABASE_URL.startswith(
        'postgresql+psycopg://cafeteria_auth_issuer:'
    )


def test_local_auth_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('LOCAL_AUTH_ENABLED', raising=False)

    assert Config().LOCAL_AUTH_ENABLED is False

    monkeypatch.setenv('LOCAL_AUTH_ENABLED', 'true')
    assert Config().LOCAL_AUTH_ENABLED is True


def test_production_allows_local_auth_while_entra_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _production_environment(monkeypatch, tmp_path)
    monkeypatch.setenv('ENTRA_ENABLED', 'false')
    monkeypatch.setenv('LOCAL_AUTH_ENABLED', 'true')
    monkeypatch.delenv('ENTRA_TENANT_ID')
    monkeypatch.delenv('ENTRA_CLIENT_ID')
    monkeypatch.delenv('ENTRA_CLIENT_SECRET')

    config = Config()

    assert config.ENTRA_ENABLED is False
    assert config.LOCAL_AUTH_ENABLED is True


@pytest.mark.parametrize('missing_name', ('ENTRA_TENANT_ID', 'ENTRA_CLIENT_ID', 'ENTRA_CLIENT_SECRET'))
def test_production_requires_complete_entra_configuration_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    missing_name: str,
) -> None:
    _production_environment(monkeypatch, tmp_path)
    monkeypatch.delenv(missing_name)

    with pytest.raises(RuntimeError, match='Entra-Konfiguration'):
        Config()


def test_production_rejects_insecure_session_cookie(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _production_environment(monkeypatch, tmp_path)
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')

    with pytest.raises(RuntimeError, match='SESSION_COOKIE_SECURE'):
        Config()


def test_production_builds_dedicated_issuer_url_from_password_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _production_environment(monkeypatch, tmp_path)
    monkeypatch.delenv('AUTH_ISSUER_DATABASE_URL', raising=False)
    monkeypatch.delenv('AUTH_ISSUER_DATABASE_URL_FILE', raising=False)
    monkeypatch.setenv(
        'DATABASE_URL',
        'postgresql+psycopg://cafeteria_app:app-runtime-value@postgres.internal:5544/menuplan',
    )
    issuer_secret = tmp_path / 'issuer-password.txt'
    issuer_secret.write_text('Issuer-Only-2026-7VgJ9wL4pQ2xR8mK\n', encoding='utf-8')
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD_FILE', str(issuer_secret))

    config = Config()

    assert config.AUTH_ISSUER_DATABASE_URL.startswith(
        'postgresql+psycopg://cafeteria_auth_issuer:'
    )
    assert '@postgres.internal:5544/menuplan' in config.AUTH_ISSUER_DATABASE_URL
    assert 'app-runtime-value' not in config.AUTH_ISSUER_DATABASE_URL


def test_production_and_migration_reject_weak_or_reused_issuer_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _production_environment(monkeypatch, tmp_path)
    weak = tmp_path / 'weak-issuer.txt'
    weak.write_text('x\n', encoding='utf-8')
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD_FILE', str(weak))
    with pytest.raises(RuntimeError, match='Issuer|32|stark'):
        Config()

    shared = 'Shared-Database-2026-7VgJ9wL4pQ2xR8mK'
    weak.write_text(shared + '\n', encoding='utf-8')
    monkeypatch.setenv('POSTGRES_APP_PASSWORD', shared)
    with pytest.raises(RuntimeError, match='eigenes|unterscheiden|Issuer'):
        Config()

    monkeypatch.delenv('POSTGRES_APP_PASSWORD')
    monkeypatch.setenv(
        'DATABASE_URL',
        f'postgresql+psycopg://cafeteria_app:{shared}@db/cafeteria',
    )
    with pytest.raises(RuntimeError, match='eigenes|unterscheiden|Issuer'):
        Config()

    monkeypatch.setenv('APP_ENV', 'migration')
    monkeypatch.delenv('POSTGRES_AUTH_ISSUER_PASSWORD_FILE', raising=False)
    monkeypatch.delenv('POSTGRES_AUTH_ISSUER_PASSWORD', raising=False)
    monkeypatch.delenv('AUTH_ISSUER_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='Issuer|POSTGRES_AUTH_ISSUER_PASSWORD'):
        Config()


@pytest.mark.parametrize(
    'last_good_dir',
    (None, '/tmp/cafeteria-last-good', '/tmp/dishboard/nested-last-good', 'relative/cache'),
)
def test_production_requires_explicit_persistent_last_good_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    last_good_dir: str | None,
) -> None:
    _production_environment(monkeypatch, tmp_path)
    if last_good_dir is None:
        monkeypatch.delenv('LAST_GOOD_DIR', raising=False)
    else:
        monkeypatch.setenv('LAST_GOOD_DIR', last_good_dir)

    with pytest.raises(RuntimeError, match='LAST_GOOD_DIR'):
        Config()


def test_non_production_keeps_local_last_good_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.delenv('LAST_GOOD_DIR', raising=False)

    assert Config().LAST_GOOD_DIR == '/tmp/cafeteria-last-good'
