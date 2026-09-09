from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, text

from .component_binding_state import prepare_bindings
from .component_catalog_store import resolve_single_active_location_connection
from .workflow_item_write import option_assignments, write_draft_item
from .workflow_write_context import begin_write, write_scope, write_transaction
from .operations_settings import (
    OperationsSchedule,
    SlotRule,
    get_schedule_connection,
    normalise_time,
    slot_defaults,
)
from .workflow_snapshot import MEAL_NAMES

PROFILE_MEALS = {'patient': ('LUNCH', 'DINNER'), 'staff_guest': ('LUNCH',)}
PROFILE_DAYS = {'patient': 7, 'staff_guest': 5}
MENU_TYPES = ('MENU_1', 'VEGGIE')
# Ein Slot ausserhalb des gepflegten Rasters ist heute nur das Cafeteria-Wochenende.
# Er gilt als geschlossen, solange die Wochenvorgaben ihn nicht kennen.
WEEKEND_DEFAULT = SlotRule('closed', None, None, 'Am Wochenende geschlossen')


def schedule_rule(schedule: OperationsSchedule, service_date: date, meal: str) -> SlotRule:
    """Vorgabe eines Slots; Slots ausserhalb des Rasters gelten als geschlossen."""
    try:
        return slot_defaults(schedule, service_date, meal)
    except KeyError:
        return WEEKEND_DEFAULT


class StaleDraftError(RuntimeError):
    pass


def ensure_week_connection(
    connection: Connection,
    profile_code: str,
    week_start: date,
    actor_id: int,
    *,
    expected_authz_version: int,
    expected_location_id: int,
) -> bool:
    scope = write_scope(actor_id, expected_location_id, profile_code, expected_authz_version)
    begin_write(connection, scope)
    location_id = scope.location_id
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


def ensure_week(engine: Engine, profile_code: str, week_start: date, actor_id: int, *,
                expected_authz_version: int, expected_location_id: int) -> None:
    scope = write_scope(actor_id, expected_location_id, profile_code, expected_authz_version)
    with write_transaction(engine, scope) as connection:
        ensure_week_connection(connection, profile_code, week_start, actor_id,
                               expected_authz_version=expected_authz_version,
                               expected_location_id=expected_location_id)


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
               l.code AS location_code, l.name AS location_name,
               p.display_name AS area_name, p.allows_weekend
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
               l.code AS location_code, l.name AS location_name,
               p.display_name AS area_name, p.allows_weekend
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
            SELECT s.id, s.service_date, mp.code AS meal_code, s.service_state, s.notice,
                   s.row_version,
                   to_char(s.service_start, 'HH24:MI') AS service_start,
                   to_char(s.service_end, 'HH24:MI') AS service_end
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
                                              THEN c.component_text ELSE NULL END,
                       'recipe_revision_public_id', rr.public_id::text
                   ) ORDER BY c.sort_order)
                   FROM cafeteria.menu_item_components c
                   LEFT JOIN cafeteria.menu_components mc ON mc.id=c.component_id
                   LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
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
    schedule = get_schedule_connection(connection, location_id, profile_code)
    allows_weekend = bool(week['allows_weekend'])
    day_offsets = list(range(PROFILE_DAYS[profile_code]))
    if profile_code == 'staff_guest':
        # Wochenendtage erscheinen nur bei einer bestehenden Zeile oder in einer noch
        # leeren Woche mit freigegebenem Betrieb; eine gespeicherte Woche wächst erst
        # durch die bewusste Übernahme der Wochenvorgaben.
        day_offsets += [offset for offset in (5, 6) if (
            (allows_weekend and not services)
            or any(row['service_date'] == week_start + timedelta(days=offset) for row in services)
        )]
    days = []
    for offset in day_offsets:
        service_day = week_start + timedelta(days=offset)
        service_date = service_day.isoformat()
        day_services = []
        for meal_code in PROFILE_MEALS[profile_code]:
            service_row = service_map.get((service_date, meal_code))
            rule = schedule_rule(schedule, service_day, meal_code)
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
                    'service_state': service_row['service_state'] if service_row else rule.state,
                    'notice': service_row['notice'] or '' if service_row else rule.notice,
                    'service_start': (
                        service_row['service_start'] if service_row else rule.start
                    ),
                    'service_end': service_row['service_end'] if service_row else rule.end,
                    'service_row_version': (
                        int(service_row['row_version']) if service_row else 0
                    ),
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
        'area_name': str(week['area_name']),
        'allows_weekend': allows_weekend,
        'days': days,
    }


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
    expected_authz_version: int,
    expected_location_id: int,
    reject_catalog_assignments: bool = False,
) -> int:
    scope = write_scope(actor_id, expected_location_id, profile_code, expected_authz_version)
    begin_write(connection, scope)
    location_id = scope.location_id
    requested = [row for day in values['days'] for service in day['services']
                 if service['service_state'] == 'open'
                 for option in service['options'] for row in option_assignments(option)]
    bindings = prepare_bindings(connection, scope, requested, weeks=[week_start])
    week = connection.execute(
        text(
            '''
            SELECT w.id, w.row_version, w.location_id
            FROM cafeteria.menu_weeks w
            JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            WHERE w.location_id=:location_id AND p.code=:profile_code AND w.week_start=:week_start
            FOR UPDATE OF w
            '''
        ),
        {'location_id': location_id, 'profile_code': profile_code, 'week_start': week_start},
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
    previous_items = {
        (int(row['service_id']), str(row['type_code'])): dict(row)
        for row in connection.execute(
            text(
                '''
                SELECT i.id,i.service_id,i.row_version,mt.code AS type_code
                FROM cafeteria.menu_items i JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
                WHERE i.service_id=ANY(CAST(:service_ids AS bigint[]))
                ORDER BY i.id FOR UPDATE OF i
                '''
            ),
            {'service_ids': service_ids},
        ).mappings()
    }
    bindings.recheck()
    if reject_catalog_assignments and any(
            row['component_id'] is not None or row['recipe_revision_id'] is not None
            for row in bindings.links):
        raise StaleDraftError('Full Import ist bei bestehenden Katalog- oder Rezeptzuweisungen gesperrt.')
    bound_ids = {int(row['menu_item_id']) for row in bindings.links if row['recipe_revision_id'] is not None}
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
    # Bestehende Menü- und Serviceidentitäten, manuell gepflegte Zeiten und ausgelassene
    # Wochenendtage bleiben erhalten. Wochenendzeilen dürfen
    # nicht gelöscht und neu eingefügt werden, weil der Trigger die Neuanlage bei
    # ausgeschaltetem Wochenendbetrieb ablehnt.
    previous_services = {
        (row['service_date'].isoformat(), row['meal_code']): row
        for row in connection.execute(
            text(
                '''
                SELECT s.id, s.service_date, mp.code AS meal_code,
                       to_char(s.service_start, 'HH24:MI') AS service_start,
                       to_char(s.service_end, 'HH24:MI') AS service_end
                FROM cafeteria.menu_services s
                JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
                WHERE s.menu_week_id=:week_id
                '''
            ),
            {'week_id': week['id']},
        ).mappings()
    }
    schedule = get_schedule_connection(connection, location_id, profile_code)
    supplied_slots: set[tuple[str, str]] = set()
    for day_value in values['days']:
        for service_value in day_value['services']:
            service_day = date.fromisoformat(day_value['date'])
            meal_code = service_value['meal_code']
            slot = (day_value['date'], meal_code)
            supplied_slots.add(slot)
            previous = previous_services.get(slot)
            if (
                previous is None
                and profile_code == 'staff_guest'
                and service_day.isoweekday() > 5
                and not schedule.allows_weekend
            ):
                raise StaleDraftError('Cafeteria-Services am Wochenende sind nicht freigegeben.')
            if previous is None:
                rule = schedule_rule(schedule, service_day, meal_code)
                fallback = (rule.start, rule.end)
            else:
                fallback = (previous['service_start'], previous['service_end'])
            start = (
                normalise_time(service_value['service_start'])
                if 'service_start' in service_value
                else fallback[0]
            )
            end = (
                normalise_time(service_value['service_end'])
                if 'service_end' in service_value
                else fallback[1]
            )
            if start is not None and end is not None and end <= start:
                raise ValueError('Endzeit muss nach der Beginnzeit liegen.')
            parameters = {
                'week_id': week['id'],
                'service_date': day_value['date'],
                'state': service_value['service_state'],
                'notice': service_value['notice'].strip(),
                'meal_code': meal_code,
                'service_start': start,
                'service_end': end,
            }
            if previous is None:
                service_id = connection.execute(
                    text(
                        '''
                        INSERT INTO cafeteria.menu_services(
                            menu_week_id, service_date, meal_period_id, service_state, notice,
                            service_start, service_end
                        )
                        SELECT :week_id, CAST(:service_date AS date), mp.id, :state,
                               NULLIF(:notice, ''),
                               CAST(:service_start AS time), CAST(:service_end AS time)
                        FROM cafeteria.meal_periods mp WHERE mp.code=:meal_code
                        RETURNING id
                        '''
                    ),
                    parameters,
                ).scalar_one()
            else:
                service_id = int(previous['id'])
                if service_value['service_state'] != 'open':
                    if any(int(row['id']) in bound_ids for (sid, _), row in previous_items.items()
                           if sid == service_id):
                        raise StaleDraftError('Rezeptbezüge müssen vor dem Schliessen bewusst entfernt werden.')
                    connection.execute(text('DELETE FROM cafeteria.menu_items WHERE service_id=:service_id'),
                                       {'service_id': service_id})
                connection.execute(
                    text(
                        '''
                        UPDATE cafeteria.menu_services
                        SET service_state=:state, notice=NULLIF(:notice, ''),
                            service_start=CAST(:service_start AS time),
                            service_end=CAST(:service_end AS time)
                        WHERE id=:service_id
                        '''
                    ),
                    {**parameters, 'service_id': service_id},
                )
            if service_value['service_state'] == 'open':
                for sort_order, option in enumerate(service_value['options'], start=1):
                    write_draft_item(
                        connection,
                        scope,
                        int(service_id),
                        day_value['date'],
                        service_value['meal_code'],
                        option,
                        sort_order,
                        bindings,
                        previous_items.get((int(service_id), option['type_code'])),
                    )
    for (previous_date, previous_meal), previous_row in previous_services.items():
        if (previous_date, previous_meal) in supplied_slots:
            continue
        if profile_code == 'staff_guest' and date.fromisoformat(previous_date).isoweekday() > 5:
            # Ein Fünf-Tage-Ersatz liefert gespeicherte Wochenendzeilen nicht mit und
            # darf sie deshalb auch nicht entfernen.
            continue
        if any(int(row['id']) in bound_ids for (sid, _), row in previous_items.items()
               if sid == int(previous_row['id'])):
            raise StaleDraftError('Rezeptbezüge dürfen beim Vollersatz nicht entfallen.')
        connection.execute(
            text('DELETE FROM cafeteria.menu_services WHERE id=:service_id'),
            {'service_id': int(previous_row['id'])},
        )
    supplies_weekend = any(
        date.fromisoformat(supplied_date).isoweekday() > 5 for supplied_date, _ in supplied_slots
    )
    if (
        profile_code == 'staff_guest'
        and schedule.allows_weekend
        and not previous_services
        and not supplies_weekend
    ):
        # Eine noch leere Woche übernimmt die Wochenendvorgaben, wenn der Ersatz das
        # Wochenende gar nicht erwähnt. Nennt er es, ist seine Angabe massgebend.
        for offset in (5, 6):
            service_day = week_start + timedelta(days=offset)
            rule = schedule_rule(schedule, service_day, 'LUNCH')
            connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.menu_services(
                        menu_week_id, service_date, meal_period_id, service_state, notice,
                        service_start, service_end
                    )
                    SELECT :week_id, :service_date, mp.id, :state, NULLIF(:notice, ''),
                           CAST(:service_start AS time), CAST(:service_end AS time)
                    FROM cafeteria.meal_periods mp WHERE mp.code='LUNCH'
                    '''
                ),
                {
                    'week_id': week['id'],
                    'service_date': service_day,
                    'state': rule.state,
                    'notice': rule.notice,
                    'service_start': rule.start,
                    'service_end': rule.end,
                },
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
    expected_authz_version: int,
    expected_location_id: int,
) -> int:
    scope = write_scope(actor_id, expected_location_id, profile_code, expected_authz_version)
    with write_transaction(engine, scope) as connection:
        return persist_draft_connection(
            connection,
            profile_code,
            week_start,
            expected_row_version=expected_row_version,
            actor_id=actor_id,
            values=values,
            expected_authz_version=expected_authz_version,
            expected_location_id=expected_location_id,
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
