"""Original actor expectations for the fixed v26 menu-write boundary."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError, OperationalError

if TYPE_CHECKING:
    from .component_catalog_store import AdminScope


class WritePermissionError(PermissionError):
    pass


class WriteConflictError(RuntimeError):
    pass


class WriteUnavailableError(RuntimeError):
    pass


def write_scope(actor: int, location: int, profile: str, authz: int) -> AdminScope:
    """Validate string-facing legacy APIs without refreshing actor expectations."""
    from .component_catalog_store import AdminScope
    if profile not in ('patient', 'staff_guest'):
        raise ValueError('Angebotsprofil ist ungültig.')
    selected: Literal['patient', 'staff_guest'] = 'patient' if profile == 'patient' else 'staff_guest'
    return AdminScope(actor, location, selected, authz)


def actor_parameters(scope: AdminScope) -> dict[str, int]:
    if type(scope.expected_authz_version) is not int or scope.expected_authz_version <= 0:
        raise WriteConflictError('Ursprüngliche Berechtigung fehlt. Bitte Formular neu laden.')
    return {'actor': scope.actor_id, 'authz': scope.expected_authz_version,
            'location': scope.location_id}


def begin_write(connection: Connection, scope: AdminScope) -> None:
    """Call before any business lock/write; repeat only with the same held expectation."""
    connection.execute(text(
        'SELECT cafeteria.begin_menu_binding_write_v26(:actor,:authz,:location)'
    ), actor_parameters(scope))


@contextmanager
def write_transaction(engine: Engine, scope: AdminScope) -> Iterator[Connection]:
    try:
        with engine.begin() as connection:
            begin_write(connection, scope)
            yield connection
    except DBAPIError as error:
        state = getattr(error.orig, 'sqlstate', None)
        if state == 'P1902':
            raise WritePermissionError('Menübearbeitung ist nicht erlaubt.') from error
        if state in {'P1901', 'P1903', '55000', '55P03', '40001', '40P01'}:
            raise WriteConflictError('Daten oder Berechtigung wurden geändert. Bitte neu laden.') from error
        if ((state and (state.startswith('08') or state in {'57P01', '57P02', '57P03'}))
                or (state is None and isinstance(error, OperationalError))):
            raise WriteUnavailableError('Speichern ist vorübergehend nicht verfügbar.') from error
        raise


def record_item_write(
    connection: Connection, scope: AdminScope, item_id: int, before: int, after: int,
) -> None:
    connection.execute(text(
        'SELECT cafeteria.record_menu_binding_write_v26('
        ':actor,:authz,:location,:item,:before,:after)'
    ), {**actor_parameters(scope), 'item': item_id, 'before': before, 'after': after})
