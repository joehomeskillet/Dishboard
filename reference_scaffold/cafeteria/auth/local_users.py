"""Version-bound issuer commands and capability-protected local account reads."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, ParamSpec, TypeVar
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from ..roles import require_capability
from .issuer import (
    _validate_actor_identifier, _validate_roles, _validate_username, validate_local_password,
)


class LocalUserError(ValueError):
    """A safe, public account-command error without database parameters."""


class InvalidInput(LocalUserError):
    pass


class ActorDenied(LocalUserError):
    pass


class StaleActor(LocalUserError):
    pass


class UnknownTarget(LocalUserError):
    pass


class StaleTarget(LocalUserError):
    pass


class LastLocalAdmin(LocalUserError):
    pass


class DuplicateUsername(LocalUserError):
    pass


class IssuerUnavailable(LocalUserError):
    pass


class ReadUnavailable(LocalUserError):
    pass


@dataclass(frozen=True)
class LocalUser:
    public_id: UUID
    username: str
    display_name: str
    roles: tuple[str, ...]
    disabled_at: datetime | None
    locked_until: datetime | None
    last_login_at: datetime | None
    password_changed_at: datetime
    authz_version: int


@dataclass(frozen=True)
class AuditEntry:
    public_id: UUID
    occurred_at: datetime
    action: str
    actor_display_name: str | None
    target_public_id: UUID | None
    target_display_name: str
    summary: str


@dataclass(frozen=True)
class ActorExpectation:
    user_id: int
    authz_version: int


@dataclass(frozen=True)
class TargetExpectation:
    public_id: UUID
    authz_version: int


@dataclass(frozen=True)
class LocalUserContext:
    actor: ActorExpectation
    target: TargetExpectation | None
    target_username: str | None


@dataclass(frozen=True)
class MutationResult:
    public_id: UUID
    authz_version: int
    changed: bool


_ERRORS: dict[str, tuple[type[LocalUserError], str]] = {
    'P1901': (InvalidInput, 'Lokale Benutzerangaben sind ungültig.'),
    'P1902': (ActorDenied, 'Aktiver Administrator erforderlich.'),
    'P1903': (StaleActor, 'Die Berechtigung wurde geändert. Erneut anmelden.'),
    'P1904': (UnknownTarget, 'Lokaler Benutzer ist unbekannt.'),
    'P1905': (StaleTarget, 'Das Konto wurde zwischenzeitlich geändert.'),
    'P1906': (LastLocalAdmin, 'Ein weiterer ungesperrter lokaler Admin muss verbleiben.'),
    '22023': (InvalidInput, 'Lokale Benutzerangaben sind ungültig.'),
    '42501': (ActorDenied, 'Aktiver Administrator erforderlich.'),
}


def _execute(engine: Engine | None, sql: str, values: dict[str, Any]) -> Any:
    if engine is None:
        raise IssuerUnavailable('Benutzerverwaltung ist derzeit nicht verfügbar.')
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SET LOCAL statement_timeout = '15s'"))
            return connection.execute(text(sql), values).mappings().one()
    except SQLAlchemyError as exc:
        original = getattr(exc, 'orig', None)
        code = str(getattr(original, 'sqlstate', '') or '')
        constraint = getattr(getattr(original, 'diag', None), 'constraint_name', None)
        if code == '23505' and constraint == 'local_credentials_username_key':
            raise DuplicateUsername('Dieser Benutzername ist bereits vergeben.') from None
        error, message = _ERRORS.get(code, (IssuerUnavailable,
                                          'Benutzerverwaltung ist derzeit nicht verfügbar.'))
        raise error(message) from None


def _expectations(actor: ActorExpectation, target: TargetExpectation | None = None) -> dict[str, Any]:
    if not isinstance(actor, ActorExpectation) or any(
        type(value) is not int or not 0 < value <= 9223372036854775807
        for value in (actor.user_id, actor.authz_version)
    ):
        raise InvalidInput('Ungültige Administratorerwartung.')
    values: dict[str, Any] = {'actor': actor.user_id, 'actor_version': actor.authz_version}
    if target is not None:
        if (not isinstance(target, TargetExpectation) or not isinstance(target.public_id, UUID)
                or type(target.authz_version) is not int
                or not 0 < target.authz_version <= 9223372036854775807):
            raise InvalidInput('Ungültige Kontoerwartung.')
        values.update(target=target.public_id, target_version=target.authz_version)
    return values


def _context(engine: Engine, *, actor_id: int | None = None, actor_identifier: str | None = None,
             target_id: UUID | None = None, target_username: str | None = None) -> LocalUserContext:
    row = _execute(engine, '''SELECT * FROM cafeteria.local_user_command_context_v19(
        CAST(:actor_id AS bigint), CAST(:actor_identifier AS text),
        CAST(:target_id AS uuid), CAST(:target_username AS text))''',
        {'actor_id': actor_id, 'actor_identifier': actor_identifier,
         'target_id': target_id, 'target_username': target_username})
    target = (TargetExpectation(row.resolved_target_public_id, row.target_authz_version)
              if row.resolved_target_public_id is not None else None)
    return LocalUserContext(ActorExpectation(row.actor_user_id, row.actor_authz_version),
                            target, row.resolved_target_username)


def load_local_command_context(issuer_engine: Engine, *, actor_identifier: str,
                               target_username: str | None = None) -> LocalUserContext:
    identifier = _validate_actor_identifier(actor_identifier)
    if target_username is not None:
        _validate_username(target_username)
    return _context(issuer_engine, actor_identifier=identifier, target_username=target_username)


def load_local_target_context(issuer_engine: Engine, *, actor: ActorExpectation,
                              target: TargetExpectation) -> LocalUserContext:
    _expectations(actor, target)
    context = _context(issuer_engine, actor_id=actor.user_id, target_id=target.public_id)
    if context.actor != actor:
        raise StaleActor('Die Berechtigung wurde geändert. Erneut anmelden.')
    if context.target != target:
        raise StaleTarget('Das Konto wurde zwischenzeitlich geändert.')
    return context


def _result(engine: Engine, sql: str, values: dict[str, Any]) -> MutationResult:
    row = _execute(engine, sql, values)
    return MutationResult(row.public_id, row.authz_version, row.changed)


def create_local_user(issuer_engine: Engine, *, actor: ActorExpectation, username: str,
                      display_name: str, password: str, roles: tuple[str, ...]) -> MutationResult:
    values = _expectations(actor)
    _validate_username(username)
    if not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 120:
        raise InvalidInput('Lokaler Anzeigename muss 1 bis 120 Zeichen enthalten.')
    _validate_roles(list(roles))
    validate_local_password(password, username)
    values.update(username=username, display_name=display_name.strip(), roles=list(roles),
                  password_hash=generate_password_hash(password))
    return _result(issuer_engine, '''SELECT * FROM cafeteria.create_local_user_v19(
        :actor, :actor_version, :username, :display_name, :password_hash, CAST(:roles AS text[]))''', values)


def replace_local_roles(issuer_engine: Engine, *, actor: ActorExpectation,
                        target: TargetExpectation, roles: tuple[str, ...]) -> MutationResult:
    values = _expectations(actor, target)
    _validate_roles(list(roles))
    values['roles'] = list(roles)
    return _result(issuer_engine, '''SELECT * FROM cafeteria.replace_local_roles_v19(
        :actor, :actor_version, :target, :target_version, CAST(:roles AS text[]))''', values)


def reset_local_password(issuer_engine: Engine, *, actor: ActorExpectation,
                         target: TargetExpectation, password: str) -> MutationResult:
    values = _expectations(actor, target)
    context = load_local_target_context(issuer_engine, actor=actor, target=target)
    if context.target_username is None:
        raise UnknownTarget('Lokaler Benutzer ist unbekannt.')
    validate_local_password(password, context.target_username)
    values['password_hash'] = generate_password_hash(password)
    return _result(issuer_engine, '''SELECT * FROM cafeteria.reset_local_password_v19(
        :actor, :actor_version, :target, :target_version, :password_hash)''', values)


def deactivate_local_user(issuer_engine: Engine, *, actor: ActorExpectation,
                          target: TargetExpectation) -> MutationResult:
    return _result(issuer_engine, '''SELECT * FROM cafeteria.deactivate_local_user_v19(
        :actor, :actor_version, :target, :target_version)''', _expectations(actor, target))


def reactivate_local_user(issuer_engine: Engine, *, actor: ActorExpectation,
                          target: TargetExpectation) -> MutationResult:
    return _result(issuer_engine, '''SELECT * FROM cafeteria.reactivate_local_user_v19(
        :actor, :actor_version, :target, :target_version)''', _expectations(actor, target))


LOCAL_USER_PAGE_SIZE = 50
LOCAL_USER_MAX_PAGE = 10000
_ACCOUNT_SELECT = '''SELECT u.public_id, c.username, u.display_name,
    ARRAY(SELECT r.role_code FROM cafeteria.user_role_cache r
          JOIN cafeteria.application_roles ar ON ar.role_code=r.role_code AND ar.active
          WHERE r.user_id=u.id AND r.source='local' ORDER BY r.role_code) AS roles,
    u.disabled_at, c.locked_until, u.last_login_at, c.password_changed_at, u.authz_version
    FROM cafeteria.users u JOIN cafeteria.local_credentials c ON c.user_id=u.id
    WHERE u.auth_provider='local' '''
_EVENT_SUMMARIES = {
    'auth.local_user_provisioned': 'Lokales Konto angelegt.',
    'auth.local_admin_bootstrapped': 'Erstes lokales Administratorkonto angelegt.',
    'auth.local_role_granted': 'Lokale Rolle zugewiesen.',
    'auth.local_roles_changed': 'Lokale Rollen geändert.',
    'auth.local_password_changed': 'Lokales Passwort geändert.',
    'auth.local_user_disabled': 'Lokales Konto deaktiviert.',
    'auth.local_user_reactivated': 'Lokales Konto reaktiviert.',
    'auth.local_login_locked': 'Lokale Anmeldung vorübergehend gesperrt.',
}


def _page_offset(page: int) -> int:
    if type(page) is not int or not 1 <= page <= LOCAL_USER_MAX_PAGE:
        raise InvalidInput('Ungültige Seite der Benutzerverwaltung.')
    return (page - 1) * LOCAL_USER_PAGE_SIZE


_ReadParams = ParamSpec('_ReadParams')
_ReadResult = TypeVar('_ReadResult')


def _safe_account_read(function: Callable[_ReadParams, _ReadResult]) -> Callable[_ReadParams, _ReadResult]:
    @wraps(function)
    def wrapped(*args: _ReadParams.args, **kwargs: _ReadParams.kwargs) -> _ReadResult:
        try:
            return function(*args, **kwargs)
        except SQLAlchemyError:
            raise ReadUnavailable('Die Kontenansicht ist derzeit nicht verfügbar.') from None
    return wrapped


def _read_accounts(engine: Engine, sql: str, values: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    with engine.begin() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        return tuple(dict(row) for row in connection.execute(text(sql), values).mappings())


def _local_user(row: dict[str, Any]) -> LocalUser:
    return LocalUser(**{**row, 'roles': tuple(row['roles'])})


@_safe_account_read
@require_capability('users.manage')
def list_local_users(app_engine: Engine, *, page: int, status: str) -> tuple[LocalUser, ...]:
    """Read at most 50 local accounts for the currently authorised admin session."""
    offset = _page_offset(page)
    if status not in ('all', 'active', 'disabled'):
        raise InvalidInput('Ungültiger Kontostatus.')
    rows = _read_accounts(app_engine, _ACCOUNT_SELECT + '''
        AND (:status='all' OR (:status='active' AND u.disabled_at IS NULL)
             OR (:status='disabled' AND u.disabled_at IS NOT NULL))
        ORDER BY c.username, u.public_id LIMIT :limit OFFSET :offset''',
        {'status': status, 'limit': LOCAL_USER_PAGE_SIZE, 'offset': offset})
    return tuple(_local_user(row) for row in rows)


@_safe_account_read
@require_capability('users.manage')
def get_local_user(app_engine: Engine, *, public_id: UUID) -> LocalUser | None:
    if not isinstance(public_id, UUID):
        raise InvalidInput('Ungültiges lokales Konto.')
    rows = _read_accounts(app_engine, _ACCOUNT_SELECT + ' AND u.public_id=:target',
                          {'target': public_id})
    return _local_user(rows[0]) if rows else None


@_safe_account_read
@require_capability('users.manage')
def list_local_user_events(app_engine: Engine, *, page: int,
                           target_public_id: UUID | None) -> tuple[AuditEntry, ...]:
    """Known account/lock events only; never a complete login/logout history."""
    offset = _page_offset(page)
    if target_public_id is not None and not isinstance(target_public_id, UUID):
        raise InvalidInput('Ungültiges lokales Konto.')
    rows = _read_accounts(app_engine, '''
        SELECT a.public_id, a.occurred_at, a.action, actor.display_name AS actor_display_name,
               target.public_id AS target_public_id, target.display_name AS target_display_name
        FROM cafeteria.audit_events a
        JOIN cafeteria.users target ON target.auth_provider='local' AND (
            target.public_id=a.entity_public_id OR (a.entity_public_id IS NULL AND
            target.id::text=CASE WHEN a.action='auth.local_login_locked'
                THEN a.details->>'user_id' ELSE a.details->>'target_user_id' END))
        JOIN cafeteria.local_credentials c ON c.user_id=target.id
        LEFT JOIN cafeteria.users actor ON actor.id=a.actor_user_id
        WHERE a.entity_type='user' AND a.action=ANY(CAST(:actions AS text[]))
          AND (CAST(:target AS uuid) IS NULL OR target.public_id=CAST(:target AS uuid))
        ORDER BY a.occurred_at DESC, a.public_id DESC LIMIT :limit OFFSET :offset''',
        {'actions': list(_EVENT_SUMMARIES), 'target': target_public_id,
         'limit': LOCAL_USER_PAGE_SIZE, 'offset': offset})
    return tuple(AuditEntry(**row, summary=_EVENT_SUMMARIES[row['action']]) for row in rows)
