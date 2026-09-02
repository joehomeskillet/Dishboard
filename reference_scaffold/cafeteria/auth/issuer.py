from __future__ import annotations

import re

from sqlalchemy import Engine, text
from werkzeug.security import generate_password_hash

from ..db import ENTRA_APPLICATION_ROLES, LOCAL_USERNAME_PATTERN


_COMMON_WEAK_PASSWORDS = frozenset(
    {
        'adminadminadmin',
        'changemechangeme',
        'defaultpassword',
        'passwordpassword',
    }
)
_WEAK_PASSWORD_MARKERS = ('changeme', 'default', 'password')
_ACTOR_IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._@+-]{2,127}$')


def validate_local_password(password: str, username: str) -> None:
    if not isinstance(password, str) or not 14 <= len(password) <= 1024:
        raise ValueError('Lokales Passwort muss 14 bis 1024 Zeichen lang sein.')
    compact_password = ''.join(character for character in password.casefold() if character.isalnum())
    compact_username = ''.join(character for character in username.casefold() if character.isalnum())
    classes = sum(
        (
            any(character.islower() for character in password),
            any(character.isupper() for character in password),
            any(character.isdigit() for character in password),
            any(not character.isalnum() for character in password),
        )
    )
    if (
        compact_password in _COMMON_WEAK_PASSWORDS
        or any(marker in compact_password for marker in _WEAK_PASSWORD_MARKERS)
        or len(set(password)) < 4
        or classes < 3
        or (len(compact_username) >= 3 and compact_username in compact_password)
    ):
        raise ValueError('Lokales Passwort ist zu schwach oder enthält den Benutzernamen.')


def _validate_username(username: str) -> None:
    if not isinstance(username, str) or not LOCAL_USERNAME_PATTERN.fullmatch(username):
        raise ValueError('Lokaler Benutzername ist ungültig.')


def _validate_roles(roles: list[str]) -> None:
    if not isinstance(roles, list) or not roles:
        raise ValueError('Lokale Rollen müssen als nichtleere Liste übergeben werden.')
    if any(not isinstance(role, str) or role not in ENTRA_APPLICATION_ROLES for role in roles):
        raise ValueError('Lokale Rollenliste enthält unbekannte oder ungültige Rollen.')
    if len(set(roles)) != len(roles):
        raise ValueError('Lokale Rollenliste enthält doppelte Rollen.')


def _validate_actor_identifier(actor_identifier: str) -> str:
    if not isinstance(actor_identifier, str):
        raise ValueError('Actor-Identifier ist ungültig.')
    normalized = actor_identifier.strip().casefold()
    if not _ACTOR_IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError('Actor-Identifier ist ungültig.')
    return normalized


def provision_local_user(
    issuer_engine: Engine,
    *,
    actor_identifier: str,
    username: str,
    display_name: str,
    password: str,
    roles: list[str],
) -> int:
    _validate_username(username)
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError('Lokaler Anzeigename ist ungültig.')
    validate_local_password(password, username)
    _validate_roles(roles)
    actor = _validate_actor_identifier(actor_identifier)
    with issuer_engine.begin() as connection:
        user_id = connection.execute(
            text(
                '''
                SELECT cafeteria.provision_local_user(
                    :actor_identifier, :username, :display_name,
                    :password_hash, CAST(:roles AS text[])
                )
                '''
            ),
            {
                'actor_identifier': actor,
                'username': username,
                'display_name': display_name.strip(),
                'password_hash': generate_password_hash(password),
                'roles': roles,
            },
        ).scalar_one()
    return int(user_id)


def set_local_password(
    issuer_engine: Engine,
    *,
    actor_identifier: str,
    username: str,
    password: str,
) -> int:
    _validate_username(username)
    validate_local_password(password, username)
    actor = _validate_actor_identifier(actor_identifier)
    with issuer_engine.begin() as connection:
        user_id = connection.execute(
            text(
                'SELECT cafeteria.set_local_password('
                ':actor_identifier, :username, :password_hash)'
            ),
            {
                'actor_identifier': actor,
                'username': username,
                'password_hash': generate_password_hash(password),
            },
        ).scalar_one()
    return int(user_id)


def disable_local_user(
    issuer_engine: Engine,
    *,
    actor_identifier: str,
    username: str,
) -> int:
    _validate_username(username)
    actor = _validate_actor_identifier(actor_identifier)
    with issuer_engine.begin() as connection:
        user_id = connection.execute(
            text('SELECT cafeteria.disable_local_user(:actor_identifier, :username)'),
            {'actor_identifier': actor, 'username': username},
        ).scalar_one()
    return int(user_id)


def bootstrap_first_local_admin(
    issuer_engine: Engine,
    *,
    username: str,
    display_name: str,
    password: str,
) -> int:
    """Bootstrap the first local administrator on a fresh database without Entra.
    
    Fails if any active administrator already exists (race-safe via SQL advisory lock).
    Uses the system user as the audit actor.
    """
    _validate_username(username)
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError('Lokaler Anzeigename ist ungültig.')
    validate_local_password(password, username)
    with issuer_engine.begin() as connection:
        user_id = connection.execute(
            text(
                '''
                SELECT cafeteria.bootstrap_first_local_admin(
                    :username, :display_name, :password_hash
                )
                '''
            ),
            {
                'username': username,
                'display_name': display_name.strip(),
                'password_hash': generate_password_hash(password),
            },
        ).scalar_one()
    return int(user_id)
