from __future__ import annotations

import hashlib
import ipaddress
from dataclasses import dataclass
from typing import Any, Mapping

from redis.exceptions import RedisError
from sqlalchemy import Engine, text
from werkzeug.security import check_password_hash

from ..db import LOCAL_USERNAME_PATTERN


_DUMMY_PASSWORD_HASH = (
    'scrypt:32768:8:1$jt0rzSrPqvNJbYzp$'
    'f44cd342ed9d2383b3085c996da4c7f4fde3c7bf1a5d4901b44c3fd71333bdb9'
    'c986dc231b3766c4798b21f6d36153fa2b53aaf3072d6166e8e0855e44c9896d'
)
LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW_SECONDS = 300
DATABASE_LOCK_THRESHOLD = 5
DATABASE_LOCK_MINUTES = 15


class RateLimitUnavailable(RuntimeError):
    pass


class RateLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthorizationState:
    user_id: int
    display_name: str
    auth_provider: str
    authz_version: int
    roles: tuple[str, ...]


def normalize_username(value: str) -> str:
    return value.strip().lower()


def login_rate_key(username: str, remote_address: str) -> str:
    identity = f'{normalize_username(username)}\x00{remote_address}'.encode()
    return f'dishboard:auth:local:{hashlib.sha256(identity).hexdigest()}'


def trusted_client_address(
    environ: Mapping[str, Any],
    effective_address: str,
    trusted_proxy_cidrs: tuple[str, ...],
) -> str:
    """Use forwarded client IP only when the direct socket peer is trusted."""
    original = environ.get('werkzeug.proxy_fix.orig')
    if isinstance(original, Mapping):
        socket_peer = original.get('REMOTE_ADDR')
    else:
        socket_peer = environ.get('REMOTE_ADDR')
    if not isinstance(socket_peer, str):
        return 'unknown'
    try:
        peer = ipaddress.ip_address(socket_peer)
        trusted = any(peer in ipaddress.ip_network(cidr, strict=False) for cidr in trusted_proxy_cidrs)
    except ValueError:
        return 'unknown'
    return effective_address if trusted else socket_peer


def consume_login_attempt(redis_client: Any, key: str) -> None:
    if redis_client is None:
        raise RateLimitUnavailable('Redis-Rate-Limitierung ist nicht verfügbar.')
    try:
        pipeline = redis_client.pipeline(transaction=True)
        pipeline.incr(key)
        pipeline.expire(key, LOGIN_RATE_WINDOW_SECONDS, nx=True)
        result = pipeline.execute()
    except RedisError as exc:
        raise RateLimitUnavailable('Redis-Rate-Limitierung ist nicht verfügbar.') from exc
    if not isinstance(result, (list, tuple)) or not result:
        raise RateLimitUnavailable('Redis-Rate-Limitierung lieferte keine gültige Antwort.')
    try:
        attempts = int(result[0])
    except (TypeError, ValueError) as exc:
        raise RateLimitUnavailable('Redis-Rate-Limitierung lieferte keine gültige Antwort.') from exc
    if attempts > LOGIN_RATE_LIMIT:
        raise RateLimitExceeded('Zu viele Anmeldeversuche.')


def clear_login_attempts(redis_client: Any, key: str) -> None:
    if redis_client is None:
        raise RateLimitUnavailable('Redis-Rate-Limitierung ist nicht verfügbar.')
    try:
        redis_client.delete(key)
    except RedisError as exc:
        raise RateLimitUnavailable('Redis-Rate-Limitierung ist nicht verfügbar.') from exc


def _active_roles(connection: Any, user_id: int) -> tuple[str, ...]:
    roles = connection.execute(
        text(
            '''
            SELECT r.role_code
            FROM cafeteria.user_role_cache r
            JOIN cafeteria.application_roles a
              ON a.role_code=r.role_code AND a.active
            WHERE r.user_id=:user_id
            ORDER BY r.role_code
            '''
        ),
        {'user_id': user_id},
    ).scalars().all()
    return tuple(str(role) for role in roles)


def authenticate_local_user(
    engine: Engine,
    *,
    username: str,
    password: str,
) -> AuthorizationState | None:
    normalized = normalize_username(username)
    if not LOCAL_USERNAME_PATTERN.fullmatch(normalized) or len(password) > 1024:
        check_password_hash(_DUMMY_PASSWORD_HASH, password[:1024])
        return None

    with engine.begin() as connection:
        row = connection.execute(
            text(
                '''
                SELECT u.id, u.display_name, u.auth_provider, u.authz_version,
                       u.disabled_at, c.password_hash,
                       c.failed_login_count,
                       c.locked_until IS NOT NULL
                           AND c.locked_until > clock_timestamp() AS locked
                FROM cafeteria.local_credentials c
                JOIN cafeteria.users u ON u.id=c.user_id
                WHERE c.username=:username AND u.auth_provider='local'
                FOR UPDATE OF c, u
                '''
            ),
            {'username': normalized},
        ).mappings().first()
        if row is None:
            check_password_hash(_DUMMY_PASSWORD_HASH, password)
            return None

        valid_password = check_password_hash(row.password_hash, password)
        if row.disabled_at is not None or row.locked or not valid_password:
            if row.disabled_at is None:
                next_count = int(row.failed_login_count) + 1
                connection.execute(
                    text(
                        '''
                        UPDATE cafeteria.local_credentials
                        SET failed_login_count=:count,
                            last_failed_at=clock_timestamp(),
                            locked_until=CASE
                                WHEN :count >= :threshold
                                THEN clock_timestamp() + make_interval(mins => :minutes)
                                ELSE locked_until
                            END
                        WHERE user_id=:user_id
                        '''
                    ),
                    {
                        'count': next_count,
                        'threshold': DATABASE_LOCK_THRESHOLD,
                        'minutes': DATABASE_LOCK_MINUTES,
                        'user_id': row.id,
                    },
                )
                if next_count == DATABASE_LOCK_THRESHOLD:
                    connection.execute(
                        text(
                            '''
                            INSERT INTO cafeteria.audit_events(
                                actor_user_id, action, entity_type, details
                            )
                            VALUES (
                                NULL, 'auth.local_login_locked', 'user',
                                jsonb_build_object(
                                    'user_id', CAST(:user_id AS bigint),
                                    'failed_login_count', :failed_count
                                )
                            )
                            '''
                        ),
                        {'user_id': row.id, 'failed_count': next_count},
                    )
            return None

        roles = _active_roles(connection, int(row.id))
        if not roles:
            return None
        connection.execute(
            text(
                '''
                UPDATE cafeteria.local_credentials
                SET failed_login_count=0, locked_until=NULL, last_failed_at=NULL
                WHERE user_id=:user_id
                '''
            ),
            {'user_id': row.id},
        )
        connection.execute(
            text('UPDATE cafeteria.users SET last_login_at=clock_timestamp() WHERE id=:user_id'),
            {'user_id': row.id},
        )
        return AuthorizationState(
            user_id=int(row.id),
            display_name=str(row.display_name),
            auth_provider=str(row.auth_provider),
            authz_version=int(row.authz_version),
            roles=roles,
        )


def load_user_authorization(engine: Engine, user_id: int) -> AuthorizationState | None:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                '''
                SELECT id, display_name, auth_provider, authz_version, disabled_at
                FROM cafeteria.users
                WHERE id=:user_id
                '''
            ),
            {'user_id': user_id},
        ).mappings().first()
        if row is None or row.disabled_at is not None:
            return None
        roles = _active_roles(connection, int(row.id))
    if not roles:
        return None
    return AuthorizationState(
        user_id=int(row.id),
        display_name=str(row.display_name),
        auth_provider=str(row.auth_provider),
        authz_version=int(row.authz_version),
        roles=roles,
    )
