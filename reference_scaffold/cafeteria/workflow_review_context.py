from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

from sqlalchemy import Connection, Engine, text

from .component_assignment_store import _require_location
from .component_catalog_store import AdminScope, ComponentNotFoundError
from .workflow_partial_store import resolve_week_ref
from .workflow_publication import require_expected_active_location
from .workflow_store import StaleDraftError


_TOKEN = re.compile(r'sha256:[0-9a-f]{64}')


def context_token(context: dict[str, Any]) -> str:
    encoded = json.dumps(
        context, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode('utf-8')
    return 'sha256:' + hashlib.sha256(encoded).hexdigest()


def week_context_connection(connection: Connection, week_id: int) -> dict[str, Any]:
    context = connection.execute(
        text('SELECT cafeteria.workflow_week_context(:week_id)'), {'week_id': week_id},
    ).scalar_one()
    if not isinstance(context, dict):
        raise ComponentNotFoundError('Woche nicht gefunden.')
    return context


def _context_receipt(connection: Connection, context: dict[str, Any]) -> dict[str, Any] | None:
    row = connection.execute(text('''
        SELECT a.public_id::text AS public_id, a.occurred_at,
               u.display_name AS actor_name, a.actor_user_id
        FROM cafeteria.audit_events a
        JOIN cafeteria.users u ON u.id=a.actor_user_id
        WHERE a.action='workflow.week_context_reviewed'
          AND a.entity_type='menu_week'
          AND a.entity_public_id=CAST(:public_id AS uuid)
          AND a.profile_code=:profile
          AND a.details->>'reviewed_token'=:token
          AND a.details->'context'=CAST(:context AS jsonb)
        ORDER BY a.id DESC LIMIT 1
    '''), {
        'public_id': context['week_public_id'], 'profile': context['profile_code'],
        'token': context_token(context), 'context': json.dumps(context, ensure_ascii=False),
    }).mappings().one_or_none()
    return dict(row) if row is not None else None


def week_context_review_open_connection(connection: Connection, week_id: int) -> bool:
    return _context_receipt(connection, week_context_connection(connection, week_id)) is None


def get_week_review(engine: Engine, scope: AdminScope, week_start: date) -> dict[str, Any]:
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            _require_location(connection, scope)
            week = resolve_week_ref(connection, scope, week_start)
            context = week_context_connection(connection, week.week_id)
            return {
                'context': context, 'token': context_token(context),
                'receipt': _context_receipt(connection, context),
            }


def review_week_context(
    engine: Engine, scope: AdminScope, week_start: date, expected_token: str,
) -> str:
    if not isinstance(expected_token, str) or _TOKEN.fullmatch(expected_token) is None:
        raise ValueError('Wochenprüfversion ist ungültig.')
    with engine.begin() as connection:
        require_expected_active_location(connection, scope.location_id, lock=True)
        week = resolve_week_ref(connection, scope, week_start, for_update=True)
        connection.execute(text('''
            SELECT s.id FROM cafeteria.menu_services s
            JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
            WHERE s.menu_week_id=:week_id
            ORDER BY s.service_date, mp.sort_order, s.id FOR UPDATE OF s
        '''), {'week_id': week.week_id}).all()
        context = week_context_connection(connection, week.week_id)
        if context_token(context) != expected_token:
            raise StaleDraftError('Wochenkopf oder Servicehinweise wurden geändert. Bitte erneut prüfen.')
        if _context_receipt(connection, context) is not None:
            raise StaleDraftError('Diese Wochenversion wurde bereits geprüft.')
        receipt = connection.execute(text('''
            SELECT cafeteria.record_week_context_review(
                :actor, :location, :profile, :week_id, :token, CAST(:context AS jsonb)
            )
        '''), {
            'actor': scope.actor_id, 'location': scope.location_id, 'profile': scope.profile_code,
            'week_id': week.week_id, 'token': expected_token,
            'context': json.dumps(context, ensure_ascii=False),
        }).scalar_one()
        return str(receipt)
