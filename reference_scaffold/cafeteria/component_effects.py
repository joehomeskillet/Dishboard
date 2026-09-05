from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import Connection, text

from .component_catalog_store import ComponentConflictError


class AutoOriginConflictError(ComponentConflictError):
    pass


def effective_rows(
    connection: Connection, item_id: int, item: Mapping[str, object]
) -> dict[str, list[dict[str, object]]]:
    assignments = list(connection.execute(
        text(
            'SELECT c.id FROM cafeteria.menu_item_components mic '
            'LEFT JOIN cafeteria.menu_components c ON c.id=mic.component_id '
            'WHERE mic.menu_item_id=:item_id'
        ),
        {'item_id': item_id},
    ).scalars())
    component_ids = sorted({int(value) for value in assignments if value is not None})
    # Freitext/unresolved assignments cannot substantiate automatic dietary labels.
    label_component_ids = component_ids if None not in assignments else []
    return {
        'labels': (
            _auto_labels(connection, label_component_ids)
            if item['label_mode'] == 'auto'
            else _manual_labels(connection, item_id)
        ),
        'allergens': (
            _auto_allergens(connection, component_ids)
            if item['allergen_mode'] == 'auto'
            else _manual_allergens(connection, item_id)
        ),
        'origins': (
            _auto_origins(connection, component_ids)
            if item['origin_mode'] == 'auto'
            else _manual_origins(connection, item_id)
        ),
    }


def _auto_labels(
    connection: Connection, component_ids: list[int]
) -> list[dict[str, object]]:
    if not component_ids:
        return []
    rows = connection.execute(
        text(
            '''
            SELECT l.id, l.code, l.display_name AS name
            FROM cafeteria.component_labels cl
            JOIN cafeteria.dietary_labels l ON l.id=cl.label_id
            WHERE cl.component_id=ANY(CAST(:ids AS bigint[]))
            GROUP BY l.id, l.code, l.display_name
            HAVING count(DISTINCT cl.component_id)=:component_count
            ORDER BY l.code, l.display_name
            '''
        ),
        {'ids': component_ids, 'component_count': len(component_ids)},
    ).mappings()
    return [dict(row) for row in rows]


def _auto_allergens(
    connection: Connection, component_ids: list[int]
) -> list[dict[str, object]]:
    if not component_ids:
        return []
    rows = connection.execute(
        text(
            '''
            SELECT a.id, a.code, a.display_name AS name,
                   CASE WHEN bool_or(ca.presence='contains')
                        THEN 'contains' ELSE 'may_contain' END AS presence
            FROM cafeteria.component_allergens ca
            JOIN cafeteria.allergens a ON a.id=ca.allergen_id
            WHERE ca.component_id=ANY(CAST(:ids AS bigint[]))
            GROUP BY a.id, a.code, a.display_name
            ORDER BY a.code, presence, a.display_name
            '''
        ),
        {'ids': component_ids},
    ).mappings()
    return [dict(row) for row in rows]


def _auto_origins(
    connection: Connection, component_ids: list[int]
) -> list[dict[str, object]]:
    if not component_ids:
        return []
    rows = connection.execute(
        text(
            '''
            SELECT name, origin_country_code
            FROM cafeteria.menu_components
            WHERE id=ANY(CAST(:ids AS bigint[])) AND origin_country_code IS NOT NULL
            ORDER BY name, origin_country_code
            '''
        ),
        {'ids': component_ids},
    ).mappings()
    countries: dict[str, str] = {}
    for row in rows:
        name = str(row['name'])
        country = str(row['origin_country_code'])
        if name in countries and countries[name] != country:
            raise AutoOriginConflictError('Komponentenname hat widersprüchliche Herkunft.')
        countries[name] = country
    return [
        {'ingredient': name, 'country_code': country, 'text': f'{name}: {country}'}
        for name, country in sorted(countries.items())
    ]


def _manual_labels(connection: Connection, item_id: int) -> list[dict[str, object]]:
    rows = connection.execute(
        text(
            '''
            SELECT l.id, l.code, l.display_name AS name
            FROM cafeteria.menu_item_labels il
            JOIN cafeteria.dietary_labels l ON l.id=il.label_id
            WHERE il.menu_item_id=:item_id ORDER BY l.code, l.display_name
            '''
        ),
        {'item_id': item_id},
    ).mappings()
    return [dict(row) for row in rows]


def _manual_allergens(
    connection: Connection, item_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        text(
            '''
            SELECT a.id, a.code, a.display_name AS name, ia.presence
            FROM cafeteria.menu_item_allergens ia
            JOIN cafeteria.allergens a ON a.id=ia.allergen_id
            WHERE ia.menu_item_id=:item_id
            ORDER BY a.code, ia.presence, a.display_name
            '''
        ),
        {'item_id': item_id},
    ).mappings()
    return [dict(row) for row in rows]


def _manual_origins(
    connection: Connection, item_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        text(
            '''
            SELECT ingredient, country_code, declaration_text AS text
            FROM cafeteria.origin_declarations WHERE menu_item_id=:item_id
            ORDER BY ingredient, country_code, declaration_text
            '''
        ),
        {'item_id': item_id},
    ).mappings()
    return [dict(row) for row in rows]


def rematerialize_auto_effects(
    connection: Connection, item_id: int, item: Mapping[str, object]
) -> None:
    effects = effective_rows(connection, item_id, item)
    if item['label_mode'] == 'auto':
        connection.execute(
            text('DELETE FROM cafeteria.menu_item_labels WHERE menu_item_id=:id'),
            {'id': item_id},
        )
        if effects['labels']:
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_item_labels(menu_item_id,label_id) '
                    'VALUES (:id,:value_id)'
                ),
                [{'id': item_id, 'value_id': row['id']} for row in effects['labels']],
            )
    if item['allergen_mode'] == 'auto':
        connection.execute(
            text('DELETE FROM cafeteria.menu_item_allergens WHERE menu_item_id=:id'),
            {'id': item_id},
        )
        if effects['allergens']:
            connection.execute(
                text(
                    'INSERT INTO cafeteria.menu_item_allergens(menu_item_id,allergen_id,presence) '
                    'VALUES (:id,:value_id,:presence)'
                ),
                [
                    {'id': item_id, 'value_id': row['id'], 'presence': row['presence']}
                    for row in effects['allergens']
                ],
            )
    if item['origin_mode'] == 'auto':
        connection.execute(
            text('DELETE FROM cafeteria.origin_declarations WHERE menu_item_id=:id'),
            {'id': item_id},
        )
        if effects['origins']:
            connection.execute(
                text(
                    'INSERT INTO cafeteria.origin_declarations('
                    'menu_item_id,ingredient,country_code,declaration_text) '
                    'VALUES (:id,:ingredient,:country_code,:text)'
                ),
                [{'id': item_id, **row} for row in effects['origins']],
            )


def public_effects(
    effects: dict[str, list[dict[str, object]]]
) -> dict[str, object]:
    return {
        key: [
            {name: value for name, value in row.items() if name != 'id'}
            for row in rows
        ]
        for key, rows in effects.items()
    }
