from __future__ import annotations

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

_BLOCKED_SECRET_MARKERS = (
    'changeme',
    'change',
    'default',
    'password',
    'secret',
    'demo',
    'example',
    'placeholder',
)


def validate_database_role_secret(secret: str, *, label: str) -> None:
    if not isinstance(secret, str):
        raise RuntimeError(f'{label} benötigt ein starkes eigenes Secret mit mindestens 32 Zeichen.')
    compact = ''.join(character for character in secret.casefold() if character.isalnum())
    if (
        not 32 <= len(secret) <= 1024
        or len(set(secret)) < 12
        or any(marker in compact for marker in _BLOCKED_SECRET_MARKERS)
    ):
        raise RuntimeError(f'{label} benötigt ein starkes eigenes Secret mit mindestens 32 Zeichen.')


def build_role_database_url(database_url: str, *, role: str, password: str) -> str:
    validate_database_role_secret(password, label=role)
    try:
        parsed = make_url(database_url)
    except ArgumentError as exc:
        raise RuntimeError('PostgreSQL-Datenbank-URL ist ungültig.') from exc
    if not parsed.drivername.startswith('postgresql') or not parsed.host or not parsed.database:
        raise RuntimeError('PostgreSQL-Datenbank-URL ist ungültig.')
    return parsed.set(username=role, password=password).render_as_string(hide_password=False)


def database_url_password(database_url: str) -> str:
    try:
        parsed = make_url(database_url)
    except ArgumentError as exc:
        raise RuntimeError('PostgreSQL-Datenbank-URL ist ungültig.') from exc
    return parsed.password or ''
