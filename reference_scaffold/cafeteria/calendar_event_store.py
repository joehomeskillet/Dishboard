"""Kitchen event header store: date, window, area, title, guests. Guests do not scale."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, time
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from .component_catalog_store import resolve_single_active_location_connection

_LOCK_TIMEOUT = "SET LOCAL lock_timeout = '5s'"
_SCOPES = frozenset({'patient', 'staff_guest', 'both'})
_ACTOR = '''SELECT u.disabled_at IS NULL AS active, u.authz_version, EXISTS (
    SELECT 1 FROM cafeteria.user_role_cache r JOIN cafeteria.application_roles a ON a.role_code=r.role_code AND a.active
    WHERE r.user_id=u.id AND r.role_code IN ('Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin')
) AS drafts FROM cafeteria.users u WHERE u.id=:actor'''


class CalendarEventError(ValueError):
    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class CalendarEventValidationError(CalendarEventError):
    """Invalid input."""
class CalendarEventNotFoundError(CalendarEventError):
    """Event not visible in the location."""
class CalendarEventConflictError(CalendarEventError):
    """CAS or immutable-scope conflict."""
class CalendarEventActorDeniedError(CalendarEventError):
    """Actor missing, disabled or without draft role."""
class CalendarEventUnavailableError(CalendarEventError):
    """Database or location configuration failure."""


@dataclass(frozen=True)
class EventScope:
    actor_id: int
    location_id: int
    expected_authz_version: int


def _positive(value: int, name: str) -> None:
    if value <= 0:
        raise CalendarEventValidationError(f'{name} ungültig.', field=name)


def _text(value: str | None, limit: int, *, field: str, required: bool = True) -> str | None:
    if value is None or value == '':
        if required:
            raise CalendarEventValidationError('Pflichtfeld.', field=field)
        return None
    trimmed = value.strip(' \t\r\n')
    if required and not trimmed:
        raise CalendarEventValidationError('Pflichtfeld.', field=field)
    if len(trimmed) > limit:
        raise CalendarEventValidationError('Text zu lang.', field=field)
    return trimmed or None


@contextmanager
def _transaction(engine: Engine, scope: EventScope) -> Iterator[Connection]:
    _positive(scope.actor_id, 'actor_id')
    _positive(scope.location_id, 'location_id')
    _positive(scope.expected_authz_version, 'expected_authz_version')
    try:
        with engine.connect() as connection:
            trans = connection.begin()
            try:
                connection.execute(text(_LOCK_TIMEOUT))
                actor = connection.execute(text(_ACTOR), {'actor': scope.actor_id}).mappings().one_or_none()
                if actor is None or not actor['active'] or not actor['drafts']:
                    raise CalendarEventActorDeniedError('Keine Berechtigung für Anlässe.')
                if actor['authz_version'] != scope.expected_authz_version:
                    raise CalendarEventActorDeniedError('Die Sitzung ist veraltet.')
                location = resolve_single_active_location_connection(connection)
                if int(location) != scope.location_id:
                    raise CalendarEventUnavailableError('Standort ist nicht aktiv.')
                yield connection
            except Exception:
                trans.rollback()
                raise
            else:
                trans.commit()
    except CalendarEventError:
        raise
    except DBAPIError as error:
        state = getattr(getattr(error, 'orig', None), 'sqlstate', '') or ''
        if state in ('40001', '40P01', '55P03'):
            raise CalendarEventConflictError('Der Anlass wird gerade bearbeitet.') from error
        if state in ('23505', '55000'):
            raise CalendarEventConflictError('Der Anlass wurde zwischenzeitlich geändert.') from error
        if state in ('23514', '23502', '22007', '22008'):
            raise CalendarEventValidationError('Ungültige Anlassdaten.') from error
        raise CalendarEventUnavailableError('Anlass konnte nicht gespeichert werden.') from error


def create_event(
    engine: Engine, scope: EventScope, *, event_date: date, title: str,
    profile_scope: str, guest_count: int = 0, note: str | None = None,
    starts_at: time | None = None, ends_at: time | None = None,
) -> str:
    title = _text(title, 120, field='title') or ''
    note = _text(note, 2000, field='note', required=False)
    if profile_scope not in _SCOPES:
        raise CalendarEventValidationError('Bereich ist patient, staff_guest oder both.', field='profile_scope')
    if guest_count < 0:
        raise CalendarEventValidationError('Gästezahl darf nicht negativ sein.', field='guest_count')
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        raise CalendarEventValidationError('Ende muss nach Beginn liegen.', field='ends_at')
    with _transaction(engine, scope) as connection:
        return str(connection.execute(text('''
            INSERT INTO cafeteria.kitchen_events(
                location_id, event_date, starts_at, ends_at, profile_scope, title,
                guest_count, note, created_by, updated_by)
            VALUES (:location, :event_date, :starts_at, :ends_at, :profile_scope, :title,
                    :guest_count, :note, :actor, :actor)
            RETURNING public_id
        '''), {
            'location': scope.location_id, 'event_date': event_date, 'starts_at': starts_at,
            'ends_at': ends_at, 'profile_scope': profile_scope, 'title': title,
            'guest_count': guest_count, 'note': note, 'actor': scope.actor_id,
        }).scalar_one())


def update_event(
    engine: Engine, scope: EventScope, public_id: str, *, expected_row_version: int,
    title: str, profile_scope: str, guest_count: int, note: str | None,
    event_date: date, starts_at: time | None, ends_at: time | None,
) -> None:
    title = _text(title, 120, field='title') or ''
    note = _text(note, 2000, field='note', required=False)
    if profile_scope not in _SCOPES:
        raise CalendarEventValidationError('Bereich ist patient, staff_guest oder both.', field='profile_scope')
    if guest_count < 0:
        raise CalendarEventValidationError('Gästezahl darf nicht negativ sein.', field='guest_count')
    try:
        uid = str(UUID(public_id))
    except ValueError as error:
        raise CalendarEventValidationError('Ungültige Anlass-ID.', field='public_id') from error
    with _transaction(engine, scope) as connection:
        row = connection.execute(text(
            'SELECT id, row_version FROM cafeteria.kitchen_events '
            'WHERE public_id=CAST(:id AS uuid) AND location_id=:location FOR UPDATE'
        ), {'id': uid, 'location': scope.location_id}).mappings().one_or_none()
        if row is None:
            raise CalendarEventNotFoundError('Anlass nicht gefunden.')
        if row['row_version'] != expected_row_version:
            raise CalendarEventConflictError('Der Anlass wurde zwischenzeitlich geändert.')
        connection.execute(text('''
            UPDATE cafeteria.kitchen_events
            SET event_date=:event_date, starts_at=:starts_at, ends_at=:ends_at,
                profile_scope=:profile_scope, title=:title, guest_count=:guest_count,
                note=:note, updated_by=:actor
            WHERE id=:id
        '''), {
            'id': row['id'], 'event_date': event_date, 'starts_at': starts_at, 'ends_at': ends_at,
            'profile_scope': profile_scope, 'title': title, 'guest_count': guest_count,
            'note': note, 'actor': scope.actor_id,
        })


def list_events(
    engine: Engine, location_id: int, date_from: date, date_to: date,
) -> tuple[dict[str, Any], ...]:
    with engine.connect() as connection:
        rows = connection.execute(text('''
            SELECT public_id, event_date, starts_at, ends_at, profile_scope, title,
                   guest_count, note, row_version
            FROM cafeteria.kitchen_events
            WHERE location_id=:location AND archived_at IS NULL
              AND event_date BETWEEN :start AND :end
            ORDER BY event_date, starts_at NULLS FIRST, title
        '''), {'location': location_id, 'start': date_from, 'end': date_to}).mappings().all()
    return tuple(dict(row) for row in rows)


def get_event(engine: Engine, location_id: int, public_id: str) -> Mapping[str, Any]:
    try:
        uid = str(UUID(public_id))
    except ValueError as error:
        raise CalendarEventValidationError('Ungültige Anlass-ID.', field='public_id') from error
    with engine.connect() as connection:
        row = connection.execute(text('''
            SELECT public_id, event_date, starts_at, ends_at, profile_scope, title,
                   guest_count, note, row_version
            FROM cafeteria.kitchen_events
            WHERE public_id=CAST(:id AS uuid) AND location_id=:location AND archived_at IS NULL
        '''), {'id': uid, 'location': location_id}).mappings().one_or_none()
    if row is None:
        raise CalendarEventNotFoundError('Anlass nicht gefunden.')
    return dict(row)
