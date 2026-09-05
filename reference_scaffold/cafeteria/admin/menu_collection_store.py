from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, text

from ..component_catalog_metadata import escape_like
from ..component_catalog_store import (
    AdminScope, ComponentCatalogConfigurationError,
    resolve_single_active_location_connection,
)

PAGE_SIZE = 24


def find_menus(
    engine: Engine, scope: AdminScope, query: str = '', page: int = 1,
) -> tuple[list[dict[str, Any]], bool]:
    """Read saved occurrences; metadata is materialized only for this page."""
    if len(query) > 200 or not 1 <= page <= 10000:
        raise ValueError('Ungültige Menüsuche.')
    with engine.connect() as connection:
        if resolve_single_active_location_connection(connection) != scope.location_id:
            raise ComponentCatalogConfigurationError('Der aktive Standort wurde geändert.')
        rows = connection.execute(text(r'''
            WITH page_items AS MATERIALIZED (
                SELECT i.id, i.title, COALESCE(i.description, '') AS description,
                       COALESCE(i.note, '') AS note, i.allergen_review_status,
                       w.week_start, w.workflow_state, s.service_date,
                       mp.code AS meal_code, mp.sort_order AS meal_order,
                       mt.code AS type_code, mt.sort_order AS type_order
                FROM cafeteria.menu_items i
                JOIN cafeteria.menu_services s ON s.id=i.service_id
                JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
                JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
                WHERE w.location_id=:location_id AND p.code=:profile_code
                  AND (:query='' OR i.title ILIKE :pattern ESCAPE '\' OR EXISTS (
                      SELECT 1 FROM cafeteria.menu_item_components mic
                      WHERE mic.menu_item_id=i.id
                        AND mic.component_text ILIKE :pattern ESCAPE '\'
                  ))
                ORDER BY s.service_date DESC, mp.sort_order, mt.sort_order, i.id
                LIMIT :limit OFFSET :offset
            )
            SELECT i.*,
                EXISTS (
                    SELECT 1 FROM cafeteria.menu_item_components mic
                    JOIN cafeteria.menu_components c ON c.id=mic.component_id
                    WHERE mic.menu_item_id=i.id
                      AND mic.component_row_version IS DISTINCT FROM c.row_version
                ) AS stale_components,
                ARRAY(
                    SELECT mic.component_text FROM cafeteria.menu_item_components mic
                    WHERE mic.menu_item_id=i.id ORDER BY mic.sort_order
                ) AS components,
                COALESCE((
                    SELECT jsonb_agg(jsonb_build_object('code', dl.code, 'name', dl.display_name)
                                     ORDER BY dl.code)
                    FROM cafeteria.menu_item_labels il
                    JOIN cafeteria.dietary_labels dl ON dl.id=il.label_id
                    WHERE il.menu_item_id=i.id
                ), '[]'::jsonb) AS labels,
                COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'code', a.code, 'name', a.display_name, 'presence', ia.presence
                    ) ORDER BY a.code, ia.presence)
                    FROM cafeteria.menu_item_allergens ia
                    JOIN cafeteria.allergens a ON a.id=ia.allergen_id
                    WHERE ia.menu_item_id=i.id
                ), '[]'::jsonb) AS allergens,
                COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'ingredient', o.ingredient, 'country_code', o.country_code,
                        'text', o.declaration_text
                    ) ORDER BY o.ingredient)
                    FROM cafeteria.origin_declarations o WHERE o.menu_item_id=i.id
                ), '[]'::jsonb) AS origins
            FROM page_items i
            ORDER BY i.service_date DESC, i.meal_order, i.type_order, i.id
        '''), {
            'location_id': scope.location_id, 'profile_code': scope.profile_code,
            'query': query, 'pattern': '%' + escape_like(query) + '%',
            'limit': PAGE_SIZE + 1, 'offset': (page - 1) * PAGE_SIZE,
        }).mappings().all()
    return [dict(row) for row in rows[:PAGE_SIZE]], len(rows) > PAGE_SIZE
