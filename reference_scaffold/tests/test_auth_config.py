from __future__ import annotations

import pytest

from cafeteria.config import Config


def _production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('DEMO_MODE', 'false')
    monkeypatch.setenv('SEED_DEMO', 'false')
    monkeypatch.setenv('DEMO_TODAY', '')
    monkeypatch.setenv('FLASK_SECRET_KEY', 'production-only-long-flask-secret')
    monkeypatch.setenv('ENTRA_TENANT_ID', '00000000-0000-0000-0000-000000000001')
    monkeypatch.setenv('ENTRA_CLIENT_ID', '00000000-0000-0000-0000-000000000002')
    monkeypatch.setenv('ENTRA_CLIENT_SECRET', 'production-only-entra-secret')
    monkeypatch.setenv('SESSION_REDIS_URL', 'redis://:production-only@redis:6379/0')


def test_production_rejects_missing_or_placeholder_auth_issuer_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _production_environment(monkeypatch)
    monkeypatch.delenv('AUTH_ISSUER_DATABASE_URL', raising=False)
    monkeypatch.delenv('AUTH_ISSUER_DATABASE_URL_FILE', raising=False)

    with pytest.raises(RuntimeError, match='AUTH_ISSUER_DATABASE_URL'):
        Config()

    for placeholder in ('change-me', 'default-issuer-secret', 'demo-auth-password'):
        monkeypatch.setenv(
            'AUTH_ISSUER_DATABASE_URL',
            f'postgresql+psycopg://cafeteria_auth_issuer:{placeholder}@db/cafeteria',
        )
        with pytest.raises(RuntimeError, match='AUTH_ISSUER_DATABASE_URL'):
            Config()


def test_production_accepts_only_dedicated_issuer_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _production_environment(monkeypatch)
    monkeypatch.setenv(
        'AUTH_ISSUER_DATABASE_URL',
        'postgresql+psycopg://cafeteria_app:strong-runtime-secret@db/cafeteria',
    )
    with pytest.raises(RuntimeError, match='cafeteria_auth_issuer'):
        Config()

    monkeypatch.setenv(
        'AUTH_ISSUER_DATABASE_URL',
        'postgresql+psycopg://cafeteria_auth_issuer:strong-runtime-secret@db/cafeteria',
    )
    config = Config()
    assert config.AUTH_ISSUER_DATABASE_URL.startswith(
        'postgresql+psycopg://cafeteria_auth_issuer:'
    )


def test_local_auth_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('LOCAL_AUTH_ENABLED', raising=False)

    assert Config().LOCAL_AUTH_ENABLED is False

    monkeypatch.setenv('LOCAL_AUTH_ENABLED', 'true')
    assert Config().LOCAL_AUTH_ENABLED is True
