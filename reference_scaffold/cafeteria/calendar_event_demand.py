"""Copy recipe revision + target portion onto an event. Reads never join live menu_item_components."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Engine, text

from .calendar_event_store import CalendarEventNotFoundError, CalendarEventValidationError, EventScope, _transaction


def replace_event_demand(
    engine: Engine, scope: EventScope, event_public_id: str,
    items: list[dict[str, object]],
) -> None:
    try:
        uid = str(UUID(event_public_id))
    except ValueError as error:
        raise CalendarEventValidationError('Ungültige Anlass-ID.') from error
    with _transaction(engine, scope) as connection:
        event_id = connection.execute(text(
            'SELECT id FROM cafeteria.kitchen_events '
            'WHERE public_id=CAST(:id AS uuid) AND location_id=:location AND archived_at IS NULL FOR UPDATE'
        ), {'id': uid, 'location': scope.location_id}).scalar_one_or_none()
        if event_id is None:
            raise CalendarEventNotFoundError('Anlass nicht gefunden.')
        connection.execute(text(
            'DELETE FROM cafeteria.kitchen_event_demand_items WHERE event_id=:id'
        ), {'id': event_id})
        for index, item in enumerate(items, start=1):
            revision = str(item['recipe_revision_public_id'])
            row = connection.execute(text('''
                SELECT rr.id, rr.content_hash_sha256, u.id AS unit_id
                FROM cafeteria.recipe_revisions rr
                JOIN cafeteria.measurement_units u ON u.code=:unit
                WHERE rr.public_id=CAST(:revision AS uuid) AND rr.location_id=:location
            '''), {
                'revision': revision, 'unit': item['target_quantity_unit_code'],
                'location': scope.location_id,
            }).mappings().one_or_none()
            if row is None:
                raise CalendarEventValidationError('Rezeptrevision oder Einheit nicht gefunden.')
            quantity = Decimal(str(item['target_quantity']))
            connection.execute(text('''
                INSERT INTO cafeteria.kitchen_event_demand_items(
                    event_id, sort_order, recipe_revision_id, recipe_content_hash_sha256,
                    target_quantity, target_quantity_unit_id, component_text, created_by, updated_by)
                VALUES (:event, :sort, :revision, :hash, :qty, :unit, :text, :actor, :actor)
            '''), {
                'event': event_id, 'sort': index, 'revision': row['id'],
                'hash': row['content_hash_sha256'], 'qty': quantity, 'unit': row['unit_id'],
                'text': str(item.get('component_text') or 'Anlassbedarf').strip(),
                'actor': scope.actor_id,
            })
