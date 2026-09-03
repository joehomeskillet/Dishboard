from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, text

from .component_assignment_store import replace_component_links_connection
from .component_catalog_store import AdminScope, resolve_single_active_location_connection
from .component_effects import rematerialize_auto_effects
from .workflow_snapshot import MEAL_NAMES, external_id

PROFILE_MEALS = {'patient': ('LUNCH', 'DINNER'), 'staff_guest': ('LUNCH',)}
PROFILE_DAYS = {'patient': 7, 'staff_guest': 5}
MENU_TYPES = ('MENU_1', 'VEGGIE')


class StaleDraftError(RuntimeError):
    pass


def ensure_week_connection(
    connection: Connection,
    profile_code: str,
    week_start: date,
    actor_id: int,
) -> bool:
    location_id = resolve_single_active_location_connection(connection)
    inserted = connection.execute(
        text(
            '''
            INSERT INTO cafeteria.menu_weeks(
                location_id, profile_id, week_start, workflow_state, created_by, updated_by
            )
            SELECT :location_id, p.id, :week_start, 'draft', :actor_id, :actor_id
            FROM cafeteria.offer_profiles p
            WHERE p.code=:profile_code
            ON CONFLICT (location_id, profile_id, week_start) DO NOTHING
            RETURNING id
            '''
        ),
        {
            'location_id': location_id,
            'week_start': week_start,
            'profile_code': profile_code,
            'actor_id': actor_id,
        },
    ).scalar_one_or_none()
    return inserted is not None


def ensure_week(engine: Engine, profile_code: str, week_start: date, actor_id: int) -> None:
    with engine.begin() as connection:
        ensure_week_connection(connection, profile_code, week_start, actor_id)


def load_draft_connection(
    connection: Connection,
    profile_code: str,
    week_start: date,
    *,
    lock_week: bool = False,
) -> dict[str, Any]:
    location_id = resolve_single_active_location_connection(connection)
    week_query = (
        '''
        SELECT w.id, w.week_start, w.workflow_state, w.title, w.shared_note, w.row_version,
               l.code AS location_code, l.name AS location_name
        FROM cafeteria.menu_weeks w
        JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
        JOIN cafeteria.locations l ON l.id=w.location_id
        WHERE w.location_id=:location_id AND p.code=:profile_code AND w.week_start=:week_start
        FOR UPDATE OF w
        '''
        if lock_week
        else
        '''
        SELECT w.id, w.week_start, w.workflow_state, w.title, w.shared_note, w.row_version,
               l.code AS location_code, l.name AS location_name
        FROM cafeteria.menu_weeks w
        JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
        JOIN cafeteria.locations l ON l.id=w.location_id
        WHERE w.location_id=:location_id AND p.code=:profile_code AND w.week_start=:week_start
        '''
    )
    week = connection.execute(
        text(week_query),
        {
            'location_id': location_id,
            'profile_code': profile_code,
            'week_start': week_start,
        },
    ).mappings().one()
    services = connection.execute(
        text(
            '''
            SELECT s.id, s.service_date, mp.code AS meal_code, s.service_state, s.notice
            FROM cafeteria.menu_services s
            JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
            WHERE s.menu_week_id=:week_id
            ORDER BY s.service_date, mp.sort_order
            '''
        ),
        {'week_id': week['id']},
    ).mappings().all()
    item_sql = '''
        SELECT i.id, s.service_date, mp.code AS meal_code, mt.code AS type_code,
               i.external_id, i.title, COALESCE(i.description, '') AS description,
               COALESCE(i.note, '') AS note, i.allergen_review_status,
               i.allergen_mode, i.origin_mode, i.label_mode,
               ARRAY(
                   SELECT c.component_text FROM cafeteria.menu_item_components c
                   WHERE c.menu_item_id=i.id ORDER BY c.sort_order
               ) AS components,
               COALESCE((
                   SELECT jsonb_agg(jsonb_build_object(
                       'component_public_id', mc.public_id::text,
                       'component_text', CASE WHEN c.component_id IS NULL
                                              THEN c.component_text ELSE NULL END
                   ) ORDER BY c.sort_order)
                   FROM cafeteria.menu_item_components c
                   LEFT JOIN cafeteria.menu_components mc ON mc.id=c.component_id
                   WHERE c.menu_item_id=i.id
               ), '[]'::jsonb) AS assignments,
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
                       'ingredient', o.ingredient, 'country_code', o.country_code, 'text', o.declaration_text
                   ) ORDER BY o.ingredient)
                   FROM cafeteria.origin_declarations o WHERE o.menu_item_id=i.id
               ), '[]'::jsonb) AS origins
               {cost_columns}
        FROM cafeteria.menu_items i
        JOIN cafeteria.menu_services s ON s.id=i.service_id
        JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
        JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
        {cost_join}
        WHERE s.menu_week_id=:week_id
        ORDER BY s.service_date, mp.code, mt.code
    '''
    if profile_code == 'staff_guest':
        item_sql = item_sql.format(
            cost_columns=', pr.internal_rappen, pr.external_rappen',
            cost_join='LEFT JOIN cafeteria.menu_item_prices pr ON pr.menu_item_id=i.id',
        )
    else:
        item_sql = item_sql.format(cost_columns='', cost_join='')
    items = connection.execute(text(item_sql), {'week_id': week['id']}).mappings().all()
    service_map = {(row['service_date'].isoformat(), row['meal_code']): row for row in services}
    item_map = {
        (row['service_date'].isoformat(), row['meal_code'], row['type_code']): row
        for row in items
    }
    days = []
    for offset in range(PROFILE_DAYS[profile_code]):
        service_date = (week_start + timedelta(days=offset)).isoformat()
        day_services = []
        for meal_code in PROFILE_MEALS[profile_code]:
            service_row = service_map.get((service_date, meal_code))
            options = []
            for type_code in MENU_TYPES:
                item = item_map.get((service_date, meal_code, type_code))
                option: dict[str, Any] = {
                    'type_code': type_code,
                    'external_id': item['external_id'] if item else '',
                    'title': item['title'] if item else '',
                    'description': item['description'] if item else '',
                    'components': list(item['components']) if item else [],
                    'assignments': list(item['assignments']) if item else [],
                    'allergen_mode': item['allergen_mode'] if item else 'manual',
                    'origin_mode': item['origin_mode'] if item else 'manual',
                    'label_mode': item['label_mode'] if item else 'manual',
                    'labels': list(item['labels']) if item else [],
                    'allergens': list(item['allergens']) if item else [],
                    'origins': list(item['origins']) if item else [],
                    'note': item['note'] if item else '',
                    'allergen_review_status': (
                        item['allergen_review_status'] if item else 'not_checked'
                    ),
                }
                if profile_code == 'staff_guest':
                    option['internal_rappen'] = item['internal_rappen'] if item else ''
                    option['external_rappen'] = item['external_rappen'] if item else ''
                options.append(option)
            day_services.append(
                {
                    'meal_code': meal_code,
                    'meal_name': MEAL_NAMES[meal_code],
                    'service_state': service_row['service_state'] if service_row else 'open',
                    'notice': service_row['notice'] or '' if service_row else '',
                    'options': options,
                }
            )
        days.append({'date': service_date, 'services': day_services})
    return {
        'id': int(week['id']),
        'profile_code': profile_code,
        'week_start': week['week_start'].isoformat(),
        'week_end': (week['week_start'] + timedelta(days=6)).isoformat(),
        'workflow_state': week['workflow_state'],
        'title': week['title'] or '',
        'shared_note': week['shared_note'] or '',
        'row_version': int(week['row_version']),
        'location': {'code': week['location_code'], 'name': week['location_name']},
        'days': days,
    }


def _insert_item(
    connection: Connection,
    scope: AdminScope,
    service_id: int,
    service_date: str,
    meal_code: str,
    option: dict[str, Any],
    sort_order: int,
) -> None:
    item_insert = connection.execute(
        text(
            '''
            INSERT INTO cafeteria.menu_items(
                service_id, menu_type_id, external_id, title, description, note,
                allergen_review_status, sort_order, allergen_mode, origin_mode, label_mode
            )
            SELECT :service_id, mt.id, :external_id, :title, NULLIF(:description, ''),
                   NULLIF(:note, ''), :allergen_review_status, :sort_order,
                   :allergen_mode, :origin_mode, :label_mode
            FROM cafeteria.menu_types mt WHERE mt.code=:type_code
            RETURNING id
            '''
        ),
        {
            'service_id': service_id,
            'external_id': option.get('external_id')
            or external_id(scope.profile_code, service_date, meal_code, option['type_code']),
            'title': option['title'].strip(),
            'description': str(option.get('description', '')).strip(),
            'note': str(option.get('note', '')).strip(),
            'allergen_review_status': option.get('allergen_review_status', 'not_checked'),
            'sort_order': sort_order,
            'type_code': option['type_code'],
            'allergen_mode': option.get('allergen_mode', 'manual'),
            'origin_mode': option.get('origin_mode', 'manual'),
            'label_mode': option.get('label_mode', 'manual'),
        },
    )
    if item_insert.rowcount != 1:
        raise ValueError('Menüart konnte nicht eindeutig zugeordnet werden.')
    item_id = item_insert.scalar_one()
    assignments = option.get('assignments')
    if assignments is None:
        assignments = [
            {'component_public_id': None, 'component_text': component}
            for component in option['components']
            if component.strip()
        ]
    replace_component_links_connection(connection, scope, int(item_id), assignments)
    for label in option.get('labels', []):
        label_insert = connection.execute(
            text(
                '''
                INSERT INTO cafeteria.menu_item_labels(menu_item_id, label_id)
                SELECT :item_id, id FROM cafeteria.dietary_labels WHERE code=:code
                '''
            ),
            {'item_id': item_id, 'code': label['code']},
        )
        if label_insert.rowcount != 1:
            raise ValueError('Menülabel konnte nicht eindeutig zugeordnet werden.')
    for allergen in option.get('allergens', []):
        allergen_insert = connection.execute(
            text(
                '''
                INSERT INTO cafeteria.menu_item_allergens(menu_item_id, allergen_id, presence)
                SELECT :item_id, id, :presence FROM cafeteria.allergens WHERE code=:code
                '''
            ),
            {
                'item_id': item_id,
                'code': allergen['code'],
                'presence': allergen['presence'],
            },
        )
        if allergen_insert.rowcount != 1:
            raise ValueError('Allergen konnte nicht eindeutig zugeordnet werden.')
    for origin in option.get('origins', []):
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.origin_declarations(
                    menu_item_id, ingredient, country_code, declaration_text
                ) VALUES (:item_id, :ingredient, :country_code, :declaration_text)
                '''
            ),
            {
                'item_id': item_id,
                'ingredient': origin['ingredient'],
                'country_code': origin['country_code'],
                'declaration_text': origin['text'],
            },
        )
    rematerialize_auto_effects(
        connection,
        int(item_id),
        {
            'allergen_mode': option.get('allergen_mode', 'manual'),
            'origin_mode': option.get('origin_mode', 'manual'),
            'label_mode': option.get('label_mode', 'manual'),
        },
    )
    if scope.profile_code == 'staff_guest':
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.menu_item_prices(
                    menu_item_id, internal_rappen, external_rappen
                ) VALUES (:item_id, :internal, :external)
                '''
            ),
            {
                'item_id': item_id,
                'internal': option['internal_rappen'],
                'external': option['external_rappen'],
            },
        )


def draft_row_version(engine: Engine, profile_code: str, week_start: date) -> int:
    with engine.connect() as connection:
        row_version = connection.execute(
            text(
                '''
                SELECT w.row_version
                FROM cafeteria.menu_weeks w
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                WHERE p.code=:profile_code AND w.week_start=:week_start
                '''
            ),
            {'profile_code': profile_code, 'week_start': week_start},
        ).scalar_one_or_none()
    return int(row_version) if row_version is not None else 0


def persist_draft_connection(
    connection: Connection,
    profile_code: str,
    week_start: date,
    *,
    expected_row_version: int,
    actor_id: int,
    values: dict[str, Any],
    reject_catalog_assignments: bool = False,
) -> int:
    week = connection.execute(
        text(
            '''
            SELECT w.id, w.row_version, w.location_id
            FROM cafeteria.menu_weeks w
            JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            WHERE p.code=:profile_code AND w.week_start=:week_start
            FOR UPDATE OF w
            '''
        ),
        {'profile_code': profile_code, 'week_start': week_start},
    ).mappings().one_or_none()
    if week is None or int(week['row_version']) != expected_row_version:
        raise StaleDraftError('Der Entwurf wurde zwischenzeitlich geändert.')
    service_ids = [
        int(value)
        for value in connection.execute(
            text(
                '''
                SELECT s.id FROM cafeteria.menu_services s
                WHERE s.menu_week_id=:week_id
                ORDER BY s.menu_week_id, s.service_date, s.meal_period_id, s.id
                FOR UPDATE
                '''
            ),
            {'week_id': week['id']},
        ).scalars()
    ]
    item_ids = [
        int(value)
        for value in connection.execute(
            text(
                '''
                SELECT i.id FROM cafeteria.menu_items i
                WHERE i.service_id=ANY(CAST(:service_ids AS bigint[]))
                ORDER BY i.id FOR UPDATE
                '''
            ),
            {'service_ids': service_ids},
        ).scalars()
    ]
    requested_public_ids = sorted(
        {
            str(assignment['component_public_id'])
            for day_value in values['days']
            for service_value in day_value['services']
            for option in service_value['options']
            for assignment in option.get('assignments', [])
            if assignment.get('component_public_id') is not None
        }
    )
    requested_component_ids = {
        int(value)
        for value in connection.execute(
            text(
                '''
                SELECT id FROM cafeteria.menu_components
                WHERE public_id=ANY(CAST(:public_ids AS uuid[]))
                  AND location_id=:location_id
                  AND profile_scope IN ('common', :profile_code)
                '''
            ),
            {
                'public_ids': requested_public_ids,
                'location_id': week['location_id'],
                'profile_code': profile_code,
            },
        ).scalars()
    }
    component_ids = sorted(
        requested_component_ids
        | {
            int(value)
            for value in connection.execute(
                text(
                    'SELECT component_id FROM cafeteria.menu_item_components '
                    'WHERE menu_item_id=ANY(CAST(:item_ids AS bigint[])) '
                    'AND component_id IS NOT NULL'
                ),
                {'item_ids': item_ids},
            ).scalars()
        }
    )
    connection.execute(
        text(
            'SELECT id FROM cafeteria.menu_components '
            'WHERE id=ANY(CAST(:component_ids AS bigint[])) ORDER BY id FOR SHARE'
        ),
        {'component_ids': component_ids},
    ).all()
    links = connection.execute(
        text(
            '''
            SELECT menu_item_id, sort_order, component_id
            FROM cafeteria.menu_item_components
            WHERE menu_item_id=ANY(CAST(:item_ids AS bigint[]))
            ORDER BY menu_item_id, sort_order FOR UPDATE
            '''
        ),
        {'item_ids': item_ids},
    ).mappings().all()
    if reject_catalog_assignments and any(row['component_id'] is not None for row in links):
        raise StaleDraftError('Full Import ist bei bestehenden Katalogzuweisungen gesperrt.')
    scope = AdminScope(actor_id, int(week['location_id']), profile_code)
    connection.execute(
        text(
            '''
            UPDATE cafeteria.menu_weeks
            SET title=:title, shared_note=:shared_note, updated_by=:actor_id
            WHERE id=:week_id
            '''
        ),
        {
            'title': values['title'].strip(),
            'shared_note': values['shared_note'].strip(),
            'actor_id': actor_id,
            'week_id': week['id'],
        },
    )
    connection.execute(
        text('DELETE FROM cafeteria.menu_services WHERE menu_week_id=:week_id'),
        {'week_id': week['id']},
    )
    for day_value in values['days']:
        for service_value in day_value['services']:
            service_id = connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.menu_services(
                        menu_week_id, service_date, meal_period_id, service_state, notice
                    )
                    SELECT :week_id, CAST(:service_date AS date), mp.id, :state, NULLIF(:notice, '')
                    FROM cafeteria.meal_periods mp WHERE mp.code=:meal_code
                    RETURNING id
                    '''
                ),
                {
                    'week_id': week['id'],
                    'service_date': day_value['date'],
                    'state': service_value['service_state'],
                    'notice': service_value['notice'].strip(),
                    'meal_code': service_value['meal_code'],
                },
            ).scalar_one()
            if service_value['service_state'] == 'open':
                for sort_order, option in enumerate(service_value['options'], start=1):
                    _insert_item(
                        connection,
                        scope,
                        int(service_id),
                        day_value['date'],
                        service_value['meal_code'],
                        option,
                        sort_order,
                    )
    return int(
        connection.execute(
            text('SELECT row_version FROM cafeteria.menu_weeks WHERE id=:week_id'),
            {'week_id': week['id']},
        ).scalar_one()
    )


def persist_draft(
    engine: Engine,
    profile_code: str,
    week_start: date,
    *,
    expected_row_version: int,
    actor_id: int,
    values: dict[str, Any],
) -> int:
    with engine.begin() as connection:
        return persist_draft_connection(
            connection,
            profile_code,
            week_start,
            expected_row_version=expected_row_version,
            actor_id=actor_id,
            values=values,
        )


def get_dietary_labels_and_allergens(
    connection: Connection,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Get active dietary labels and allergens for form controls."""
    dietary_labels = connection.execute(
        text(
            '''
            SELECT code, display_name
            FROM cafeteria.dietary_labels
            WHERE active
            ORDER BY code
            '''
        )
    ).mappings().all()

    allergens = connection.execute(
        text(
            '''
            SELECT code, display_name, eu_number
            FROM cafeteria.allergens
            WHERE active
            ORDER BY eu_number, code
            '''
        )
    ).mappings().all()

    return (
        [dict(row) for row in dietary_labels],
        [dict(row) for row in allergens],
    )
