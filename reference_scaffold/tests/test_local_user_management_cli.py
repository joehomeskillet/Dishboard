from __future__ import annotations

import json

import pytest
from sqlalchemy import Engine, text

import manage
from cafeteria.auth import local_users as users
from test_auth_database import DEFAULT_ACTOR, DATABASE_URL, ISSUER_PASSWORD, owner_engine
from test_local_user_management_db import _create, issuer_engine

__all__ = ['owner_engine', 'issuer_engine']


def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    assert DATABASE_URL is not None
    monkeypatch.setenv('DATABASE_URL', DATABASE_URL)
    monkeypatch.setenv('POSTGRES_AUTH_ISSUER_PASSWORD', ISSUER_PASSWORD)
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DEMO_MODE', 'false')


def test_cli_roles_status_and_reactivation_share_versioned_contract(
    owner_engine: Engine, issuer_engine: Engine, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _environment(monkeypatch)
    _create(issuer_engine, 'cli.managed')
    monkeypatch.setattr('builtins.input', lambda _: 'ja')
    versions = []
    for command, extra in [('set-local-roles', ['--role', 'Cafeteria.Publisher']),
                           ('disable-local-user', []), ('reactivate-local-user', [])]:
        assert manage.main([command, '--actor', DEFAULT_ACTOR, '--username', 'cli.managed', *extra]) == 0
        output = json.loads(capsys.readouterr().out)
        versions.append(output['authz_version'])
        assert output['changed']
    assert versions == sorted(set(versions))
    with owner_engine.connect() as connection:
        assert connection.execute(text("SELECT u.disabled_at IS NULL FROM cafeteria.users u "
            "JOIN cafeteria.local_credentials c ON c.user_id=u.id WHERE c.username='cli.managed'")).scalar_one()


def test_cli_does_not_refresh_target_after_confirmation(
    owner_engine: Engine, issuer_engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(monkeypatch)
    context = _create(issuer_engine, 'cli.stale')
    assert context.target is not None

    def change_while_confirming(_):
        users.replace_local_roles(issuer_engine, actor=context.actor, target=context.target,
                                   roles=('Cafeteria.Publisher',))
        return 'ja'

    monkeypatch.setattr('builtins.input', change_while_confirming)
    with pytest.raises(users.StaleTarget):
        manage.main(['disable-local-user', '--actor', DEFAULT_ACTOR, '--username', 'cli.stale'])
    with owner_engine.connect() as connection:
        assert connection.execute(text("SELECT disabled_at IS NULL FROM cafeteria.users "
                                        'WHERE public_id=:id'), {'id': context.target.public_id}).scalar_one()


def test_cli_declining_confirmation_does_not_mutate(
    owner_engine: Engine, issuer_engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(monkeypatch)
    context = _create(issuer_engine, 'cli.cancelled')
    monkeypatch.setattr('builtins.input', lambda _: 'nein')
    with pytest.raises(RuntimeError, match='abgebrochen'):
        manage.main(['disable-local-user', '--actor', DEFAULT_ACTOR, '--username', 'cli.cancelled'])
    fresh = users.load_local_command_context(issuer_engine, actor_identifier=DEFAULT_ACTOR,
                                            target_username='cli.cancelled')
    assert fresh == context
