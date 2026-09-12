from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

API_KEY_SCOPES = ('preview.read',)
API_KEY_CHANNELS = ('cafeteria', 'patienten')
API_KEY_MAX_LIFETIME = timedelta(days=90)
API_KEY_RE = re.compile(r'^dbk_[A-Za-z0-9_-]{32}$')


@dataclass(frozen=True)
class ApiKeyRecord:
    public_id: str
    label: str
    key_prefix: str
    scopes: tuple[str, ...]
    channels: tuple[str, ...]
    created_at: datetime
    created_by_name: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None

    @property
    def state(self) -> str:
        if self.revoked_at is not None:
            return 'revoked'
        if self.expires_at is not None and self.expires_at <= datetime.now(UTC):
            return 'expired'
        return 'active'


@dataclass(frozen=True)
class ApiKeyIdentity:
    public_id: str
    label: str
    scopes: tuple[str, ...]
    channels: tuple[str, ...]
    expires_at: datetime | None


class ApiKeyValidationError(ValueError):
    pass


def generate_api_key() -> tuple[str, str, str]:
    plaintext = f'dbk_{secrets.token_urlsafe(24)}'
    key_prefix = plaintext[:12]
    key_hash = f'sha256:{hashlib.sha256(plaintext.encode()).hexdigest()}'
    return plaintext, key_prefix, key_hash


def create_api_key(
    engine: Engine,
    *,
    actor_id: int,
    label: str,
    scopes: Sequence[str],
    channels: Sequence[str],
    expires_at: datetime | None,
) -> tuple[ApiKeyRecord, str]:
    clean_label = _label(label)
    clean_scopes = _scopes(scopes)
    clean_channels = _channels(channels)
    clean_actor_id = _positive_id(actor_id, 'actor_id')
    if not isinstance(expires_at, datetime) or expires_at.utcoffset() is None:
        raise ApiKeyValidationError('Ein Ablaufdatum mit Zeitzone ist erforderlich.')
    now = datetime.now(UTC)
    if not now < expires_at <= now + API_KEY_MAX_LIFETIME:
        raise ApiKeyValidationError('Ablaufzeit muss in der Zukunft und innerhalb von 90 Tagen liegen.')
    plaintext, key_prefix, key_hash = generate_api_key()
    try:
        with engine.begin() as connection:
            public_id = connection.execute(
                text(
                    '''
                    SELECT cafeteria.create_api_key(
                        :actor_id, :label, :key_prefix, :key_hash,
                        CAST(:scopes AS text[]), :expires_at, CAST(:channels AS text[])
                    )::text
                    '''
                ),
                {
                    'actor_id': clean_actor_id,
                    'label': clean_label,
                    'key_prefix': key_prefix,
                    'key_hash': key_hash,
                    'scopes': list(clean_scopes),
                    'channels': list(clean_channels),
                    'expires_at': expires_at,
                },
            ).scalar_one()
            record = _record_by_public_id(connection, str(public_id))
    except DBAPIError as error:
        _raise_permission(error)
        raise
    return record, plaintext


def list_api_keys(engine: Engine) -> list[ApiKeyRecord]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    '''
                    SELECT k.public_id::text AS public_id, k.label, k.key_prefix, k.scopes, k.channels,
                           k.created_at, u.display_name AS created_by_name, k.expires_at,
                           k.last_used_at, k.revoked_at
                    FROM cafeteria.api_keys k
                    JOIN cafeteria.users u ON u.id=k.created_by
                    ORDER BY k.created_at DESC, k.id DESC
                    '''
                )
            ).mappings().all()
    except DBAPIError as error:
        _raise_permission(error)
        raise
    return [_record(row) for row in rows]


def revoke_api_key(engine: Engine, *, actor_id: int, public_id: str) -> bool:
    clean_actor_id = _positive_id(actor_id, 'actor_id')
    clean_public_id = _public_id(public_id)
    try:
        with engine.begin() as connection:
            return bool(
                connection.execute(
                    text('SELECT cafeteria.revoke_api_key(:actor_id, CAST(:public_id AS uuid))'),
                    {'actor_id': clean_actor_id, 'public_id': clean_public_id},
                ).scalar_one()
            )
    except DBAPIError as error:
        _raise_permission(error)
        raise


def authenticate_api_key(engine: Engine, presented: str | None) -> ApiKeyIdentity | None:
    if type(presented) is not str or API_KEY_RE.fullmatch(presented) is None:
        return None
    key_prefix = presented[:12]
    expected_hash = f'sha256:{hashlib.sha256(presented.encode()).hexdigest()}'
    try:
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    '''
                    SELECT public_id::text AS public_id, label, key_hash, scopes, channels,
                           expires_at, revoked_at
                    FROM cafeteria.api_keys
                    WHERE key_prefix=:key_prefix
                    '''
                ),
                {'key_prefix': key_prefix},
            ).mappings().one_or_none()
            # Compare even without a row so unknown and wrong prefixes cost the same time.
            stored_hash = str(row['key_hash']) if row is not None else f'sha256:{"0" * 64}'
            if not hmac.compare_digest(stored_hash, expected_hash) or row is None:
                return None
            expires_at = row['expires_at']
            if row['revoked_at'] is not None or (
                expires_at is not None and expires_at <= datetime.now(UTC)
            ):
                return None
            connection.execute(
                text(
                    '''
                    UPDATE cafeteria.api_keys
                    SET last_used_at=clock_timestamp()
                    WHERE public_id=CAST(:public_id AS uuid)
                      AND (
                          last_used_at IS NULL
                          OR last_used_at < clock_timestamp() - interval '60 seconds'
                      )
                    '''
                ),
                {'public_id': row['public_id']},
            )
            return ApiKeyIdentity(
                public_id=str(row['public_id']),
                label=str(row['label']),
                scopes=tuple(row['scopes']),
                channels=_channels(row['channels']),
                expires_at=expires_at,
            )
    except DBAPIError as error:
        _raise_permission(error)
        raise


def _label(value: str) -> str:
    if type(value) is not str:
        raise ApiKeyValidationError('Bezeichnung ist ungültig.')
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 80:
        raise ApiKeyValidationError('Bezeichnung ist ungültig.')
    return cleaned


def _scopes(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ApiKeyValidationError('API-Schlüssel-Scopes sind ungültig.')
    cleaned = tuple(value)
    if cleaned != API_KEY_SCOPES:
        raise ApiKeyValidationError('API-Schlüssel-Scopes sind ungültig.')
    return API_KEY_SCOPES


def _positive_id(value: int, field: str) -> int:
    if type(value) is not int or value < 1:
        raise ApiKeyValidationError(f'{field} ist ungültig.')
    return value


def _channels(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ApiKeyValidationError('Mindestens einen gültigen Kanal auswählen.')
    if not value or any(type(item) is not str or item not in API_KEY_CHANNELS for item in value):
        raise ApiKeyValidationError('Mindestens einen gültigen Kanal auswählen.')
    if len(set(value)) != len(value):
        raise ApiKeyValidationError('Kanäle dürfen nicht mehrfach angegeben werden.')
    return tuple(channel for channel in API_KEY_CHANNELS if channel in value)


def _public_id(value: str) -> str:
    try:
        return str(UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ApiKeyValidationError('public_id ist ungültig.') from error


def _record_by_public_id(connection: Any, public_id: str) -> ApiKeyRecord:
    row = connection.execute(
        text(
            '''
            SELECT k.public_id::text AS public_id, k.label, k.key_prefix, k.scopes, k.channels,
                   k.created_at, u.display_name AS created_by_name, k.expires_at,
                   k.last_used_at, k.revoked_at
            FROM cafeteria.api_keys k
            JOIN cafeteria.users u ON u.id=k.created_by
            WHERE k.public_id=CAST(:public_id AS uuid)
            '''
        ),
        {'public_id': public_id},
    ).mappings().one()
    return _record(row)


def _record(row: Mapping[str, object]) -> ApiKeyRecord:
    return ApiKeyRecord(
        public_id=str(row['public_id']),
        label=str(row['label']),
        key_prefix=str(row['key_prefix']),
        scopes=_scopes(row['scopes']),
        channels=_channels(row['channels']),
        created_at=_record_datetime(row['created_at']),
        created_by_name=str(row['created_by_name']),
        expires_at=_record_optional_datetime(row['expires_at']),
        last_used_at=_record_optional_datetime(row['last_used_at']),
        revoked_at=_record_optional_datetime(row['revoked_at']),
    )


def _record_datetime(value: object) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError('API-Schlüssel-Datensatz enthält eine ungültige Zeitangabe.')
    return value


def _record_optional_datetime(value: object) -> datetime | None:
    return None if value is None else _record_datetime(value)


def _raise_permission(error: DBAPIError) -> None:
    if getattr(error.orig, 'sqlstate', None) == '42501':
        raise PermissionError('API-Schlüssel-Aktion ist nicht berechtigt.') from error
