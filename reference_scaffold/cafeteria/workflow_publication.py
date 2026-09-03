from __future__ import annotations

from datetime import date

from sqlalchemy import Connection, text
from sqlalchemy.exc import DatabaseError

from .component_catalog_store import resolve_single_active_location_connection
from .workflow_store import StaleDraftError


def require_expected_active_location(
    connection: Connection,
    expected_location_id: int,
    *,
    lock: bool,
) -> None:
    if lock:
        matches = bool(
            connection.execute(
                text(
                    'SELECT cafeteria.lock_expected_active_location(:expected_location_id)'
                ),
                {'expected_location_id': expected_location_id},
            ).scalar_one()
        )
    else:
        matches = (
            resolve_single_active_location_connection(connection) == expected_location_id
        )
    if not matches:
        raise StaleDraftError('Der aktive Standort wurde zwischenzeitlich geändert.')


def next_revision_number(
    connection: Connection,
    profile_code: str,
    week_start: date,
) -> int:
    iso_calendar = week_start.isocalendar()
    connection.execute(
        text('SELECT pg_advisory_xact_lock(:profile_key, :week_key)'),
        {
            'profile_key': 1 if profile_code == 'patient' else 2,
            'week_key': iso_calendar.year * 100 + iso_calendar.week,
        },
    )
    return int(
        connection.execute(
            text(
                'SELECT COALESCE(max(r.revision_number), 0) + 1 '
                'FROM cafeteria.publication_revisions r '
                'JOIN cafeteria.menu_weeks w ON w.id=r.menu_week_id '
                'JOIN cafeteria.offer_profiles p ON p.id=w.profile_id '
                'WHERE p.code=:profile_code AND w.week_start=:week_start'
            ),
            {'profile_code': profile_code, 'week_start': week_start},
        ).scalar_one()
    )


def withdraw_replaced_publication(
    connection: Connection,
    revision_id: int,
    capability: str,
) -> None:
    try:
        connection.execute(
            text(
                'SELECT cafeteria.withdraw_publication_revision('
                ':revision_id, :capability, :reason)'
            ),
            {
                'revision_id': revision_id,
                'capability': capability,
                'reason': 'Durch neue Küchenrevision ersetzt.',
            },
        ).scalar_one()
    except DatabaseError as error:
        sqlstate = getattr(error.orig, 'sqlstate', None) or getattr(error.orig, 'pgcode', None)
        if sqlstate == '55000':
            raise StaleDraftError(
                'Die aktive Publikation wurde zwischenzeitlich geändert.'
            ) from error
        raise
