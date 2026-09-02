from __future__ import annotations

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


def provision_local_user(
    issuer_engine: Engine,
    *,
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
    with issuer_engine.begin() as connection:
        user_id = connection.execute(
            text(
                '''
                SELECT cafeteria.provision_local_user(
                    :username, :display_name, :password_hash, CAST(:roles AS text[])
                )
                '''
            ),
            {
                'username': username,
                'display_name': display_name.strip(),
                'password_hash': generate_password_hash(password),
                'roles': roles,
            },
        ).scalar_one()
    return int(user_id)


def set_local_password(issuer_engine: Engine, *, username: str, password: str) -> int:
    _validate_username(username)
    validate_local_password(password, username)
    with issuer_engine.begin() as connection:
        user_id = connection.execute(
            text('SELECT cafeteria.set_local_password(:username, :password_hash)'),
            {'username': username, 'password_hash': generate_password_hash(password)},
        ).scalar_one()
    return int(user_id)


def disable_local_user(issuer_engine: Engine, *, username: str) -> int:
    _validate_username(username)
    with issuer_engine.begin() as connection:
        user_id = connection.execute(
            text('SELECT cafeteria.disable_local_user(:username)'),
            {'username': username},
        ).scalar_one()
    return int(user_id)
