"""Bounded authentication history for the currently authorised administrator."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine

from ..roles import require_capability
from .local_users import (
    LOCAL_USER_PAGE_SIZE, InvalidInput, _page_offset, _read_accounts, _safe_account_read,
)

PROVIDER_LABELS = {'local': 'Lokal', 'entra': 'Microsoft Entra'}
ACTION_LABELS = {
    'auth.login.accepted': 'Anmeldung akzeptiert',
    'auth.login.rejected': 'Anmeldung abgewiesen',
    'auth.login.unavailable': 'Anmeldung nicht verfügbar',
    'auth.logout.requested': 'Abmeldung angefordert',
    'auth.frontchannel.requested': 'Lokale Abmeldung angefordert',
}
REASON_LABELS = {
    'credentials': 'Zugangsdaten nicht bestätigt',
    'role': 'Keine ausreichende Berechtigung',
    'flow': 'Anmeldevorgang ungültig oder abgelaufen',
    'throttled': 'Zu viele Anmeldeversuche',
    'unavailable': 'Anmeldedienst vorübergehend nicht verfügbar',
}


@dataclass(frozen=True)
class AccessHistoryEntry:
    public_id: UUID
    occurred_at: datetime
    actor_display_name: str | None
    provider: str
    action: str
    summary: str
    reason_label: str


@dataclass(frozen=True)
class AccessHistoryPage:
    rows: tuple[AccessHistoryEntry, ...]
    has_next: bool


@_safe_account_read
@require_capability('users.manage')
def list_access_history(app_engine: Engine, *, page: int, provider: str = 'all',
                        action: str = 'all') -> AccessHistoryPage:
    """Project fixed authentication fields, with one lookahead row for pagination."""
    offset = _page_offset(page)
    if not isinstance(provider, str) or provider not in ('all', *PROVIDER_LABELS):
        raise InvalidInput('Ungültiger Zugang im Zugriffsverlauf.')
    if not isinstance(action, str) or action not in ('all', *ACTION_LABELS):
        raise InvalidInput('Ungültiges Ereignis im Zugriffsverlauf.')
    records = _read_accounts(app_engine, '''
        SELECT a.public_id, a.occurred_at, actor.display_name AS actor_display_name,
               a.action, a.details->>'provider' AS provider,
               CASE WHEN a.details->>'reason'=ANY(CAST(:reasons AS text[]))
                    THEN a.details->>'reason' END AS reason
        FROM cafeteria.audit_events a
        LEFT JOIN cafeteria.users actor ON actor.id=a.actor_user_id
        WHERE a.entity_type='authentication' AND a.action=ANY(CAST(:actions AS text[]))
          AND a.details->>'provider'=ANY(CAST(:providers AS text[]))
          AND (:provider='all' OR a.details->>'provider'=:provider)
          AND (:action='all' OR a.action=:action)
        ORDER BY a.occurred_at DESC, a.public_id DESC LIMIT :limit OFFSET :offset''',
        {'reasons': list(REASON_LABELS), 'actions': list(ACTION_LABELS),
         'providers': list(PROVIDER_LABELS), 'provider': provider, 'action': action,
         'limit': LOCAL_USER_PAGE_SIZE + 1, 'offset': offset})
    rows = tuple(AccessHistoryEntry(
        public_id=row['public_id'], occurred_at=row['occurred_at'],
        actor_display_name=row['actor_display_name'], provider=row['provider'], action=row['action'],
        summary=ACTION_LABELS[row['action']], reason_label=REASON_LABELS.get(row['reason'], ''),
    ) for row in records[:LOCAL_USER_PAGE_SIZE])
    return AccessHistoryPage(rows, len(records) > LOCAL_USER_PAGE_SIZE)
