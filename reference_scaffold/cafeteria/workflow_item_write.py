"""Existing whole-draft item writes, preserving item identity and one version step."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Connection, text

from .component_assignment_contract import Assignment, normalize_assignments
from .component_assignment_store import replace_component_links_connection
from .component_binding_state import BindingState
from .component_catalog_store import AdminScope
from .component_effects import rematerialize_auto_effects
from .workflow_snapshot import external_id
from .workflow_write_context import record_item_write


def option_assignments(option: Mapping[str, Any]) -> tuple[Assignment, ...]:
    if 'assignments' in option:
        return normalize_assignments(option['assignments'])
    return normalize_assignments([
        {'component_public_id': None, 'component_text': value}
        for value in option['components']
    ])


def write_draft_item(
    connection: Connection, scope: AdminScope, service_id: int, service_date: str,
    meal_code: str, option: Mapping[str, Any], sort_order: int, bindings: BindingState,
    current: Mapping[str, Any] | None,
) -> int:
    params = {
        'service_id': service_id,
        'external_id': option.get('external_id')
        or external_id(scope.profile_code, service_date, meal_code, option['type_code']),
        'title': option['title'].strip(), 'description': option.get('description', '').strip(),
        'note': option.get('note', '').strip(), 'sort_order': sort_order,
        'type_code': option['type_code'], 'allergen_mode': option.get('allergen_mode', 'manual'),
        'origin_mode': option.get('origin_mode', 'manual'), 'label_mode': option.get('label_mode', 'manual'),
    }
    before = int(current['row_version']) if current is not None else 0
    if current is None:
        item_id = int(connection.execute(text('''
            INSERT INTO cafeteria.menu_items(service_id,menu_type_id,external_id,title,
                description,note,allergen_review_status,sort_order,allergen_mode,origin_mode,label_mode)
            SELECT :service_id,mt.id,:external_id,:title,NULLIF(:description,''),NULLIF(:note,''),
                   'not_checked',:sort_order,:allergen_mode,:origin_mode,:label_mode
            FROM cafeteria.menu_types mt WHERE mt.code=:type_code RETURNING id
        '''), params).scalar_one())
    else:
        item_id = int(current['id'])
    replace_component_links_connection(connection, scope, item_id,
        [row.as_payload() for row in option_assignments(option)], binding_state=bindings)
    _replace_metadata(connection, item_id, option)
    rematerialize_auto_effects(connection, item_id, params)
    if scope.profile_code == 'staff_guest':
        connection.execute(text('''
            INSERT INTO cafeteria.menu_item_prices(menu_item_id,internal_rappen,external_rappen)
            VALUES(:item_id,:internal,:external) ON CONFLICT(menu_item_id) DO UPDATE
            SET internal_rappen=EXCLUDED.internal_rappen,external_rappen=EXCLUDED.external_rappen
        '''), {'item_id': item_id, 'internal': option['internal_rappen'], 'external': option['external_rappen']})
    after = 1
    if current is not None:
        after = int(connection.execute(text('''
            UPDATE cafeteria.menu_items SET title=:title,external_id=:external_id,
                description=NULLIF(:description,''),note=NULLIF(:note,''),sort_order=:sort_order,
                allergen_mode=:allergen_mode,origin_mode=:origin_mode,label_mode=:label_mode,
                allergen_review_status='not_checked' WHERE id=:item_id RETURNING row_version
        '''), {**params, 'item_id': item_id}).scalar_one())
    record_item_write(connection, scope, item_id, before, after)
    return item_id


def _replace_metadata(connection: Connection, item_id: int, option: Mapping[str, Any]) -> None:
    for statement in (
        'DELETE FROM cafeteria.menu_item_labels WHERE menu_item_id=:item_id',
        'DELETE FROM cafeteria.menu_item_allergens WHERE menu_item_id=:item_id',
        'DELETE FROM cafeteria.origin_declarations WHERE menu_item_id=:item_id',
    ):
        connection.execute(text(statement), {'item_id': item_id})
    if option.get('label_mode', 'manual') == 'manual':
        for label in option.get('labels', []):
            result = connection.execute(text('''
                INSERT INTO cafeteria.menu_item_labels(menu_item_id,label_id)
                SELECT :item_id,id FROM cafeteria.dietary_labels WHERE code=:code
            '''), {'item_id': item_id, 'code': label['code']})
            if result.rowcount != 1:
                raise ValueError('Menülabel konnte nicht eindeutig zugeordnet werden.')
    if option.get('allergen_mode', 'manual') == 'manual':
        for allergen in option.get('allergens', []):
            result = connection.execute(text('''
                INSERT INTO cafeteria.menu_item_allergens(menu_item_id,allergen_id,presence)
                SELECT :item_id,id,:presence FROM cafeteria.allergens WHERE code=:code
            '''), {'item_id': item_id, 'code': allergen['code'], 'presence': allergen['presence']})
            if result.rowcount != 1:
                raise ValueError('Allergen konnte nicht eindeutig zugeordnet werden.')
    if option.get('origin_mode', 'manual') == 'manual':
        for origin in option.get('origins', []):
            connection.execute(text('''
                INSERT INTO cafeteria.origin_declarations(menu_item_id,ingredient,country_code,declaration_text)
                VALUES(:item_id,:ingredient,:country_code,:text)
            '''), {'item_id': item_id, 'ingredient': origin['ingredient'],
                   'country_code': origin['country_code'], 'text': origin['text']})
