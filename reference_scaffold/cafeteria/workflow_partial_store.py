from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import Connection, Engine, text

from .component_assignment_store import replace_component_links_connection
from .component_catalog_store import AdminScope, resolve_single_active_location_connection
from .component_effects import rematerialize_auto_effects
from .workflow_snapshot import external_id


_MEALS = {'patient': ('LUNCH', 'DINNER'), 'staff_guest': ('LUNCH',)}
_DAYS = {'patient': 7, 'staff_guest': 5}
_OPTIONS = ('MENU_1', 'VEGGIE')
_STATES = {'open', 'closed', 'holiday', 'company_holiday'}
_MODES = {'auto', 'manual'}
_PATIENT_KEYS = frozenset({
    'title', 'description', 'note', 'allergen_mode', 'origin_mode', 'label_mode', 'assignments',
    'labels', 'allergens', 'origins'})
_STAFF_KEYS = _PATIENT_KEYS | {'internal_rappen', 'external_rappen'}
_COUNTRY = re.compile(r'[A-Z]{2}')
_WEEK_QUERY = 'SELECT w.id,w.location_id,p.code AS profile_code,w.week_start,w.row_version FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id WHERE w.location_id=:location_id AND p.code=:profile_code AND w.week_start=:week_start'
_WEEK_QUERY_FOR_UPDATE = 'SELECT w.id,w.location_id,p.code AS profile_code,w.week_start,w.row_version FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id WHERE w.location_id=:location_id AND p.code=:profile_code AND w.week_start=:week_start FOR UPDATE OF w'
_SERVICE_QUERY = 'SELECT s.id,s.row_version,s.service_state FROM cafeteria.menu_services s JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id WHERE s.menu_week_id=:week_id AND s.service_date=:service_date AND mp.code=:meal'
_SERVICE_QUERY_FOR_UPDATE = 'SELECT s.id,s.row_version,s.service_state FROM cafeteria.menu_services s JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id WHERE s.menu_week_id=:week_id AND s.service_date=:service_date AND mp.code=:meal FOR UPDATE OF s'
_ITEM_QUERY = 'SELECT i.id,i.row_version,i.allergen_mode,i.origin_mode,i.label_mode FROM cafeteria.menu_items i JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id WHERE i.service_id=:service_id AND mt.code=:option'
_ITEM_QUERY_FOR_UPDATE = 'SELECT i.id,i.row_version,i.allergen_mode,i.origin_mode,i.label_mode FROM cafeteria.menu_items i JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id WHERE i.service_id=:service_id AND mt.code=:option FOR UPDATE OF i'

class PartialWorkflowValidationError(ValueError): pass
class PartialWorkflowNotFoundError(LookupError): pass
class PartialWorkflowConflictError(RuntimeError): pass
@dataclass(frozen=True)
class WeekRef:
    week_id: int; location_id: int; profile_code: str; week_start: date; row_version: int

def _expected(value: int, label: str) -> int:
    if type(value) is not int or value < 0:
        raise PartialWorkflowValidationError(f'{label} ist ungültig.')
    return value

def _week(value: date) -> date:
    if type(value) is not date or value.isoweekday() != 1:
        raise PartialWorkflowValidationError('Die Woche muss an einem Montag beginnen.')
    return value

def _slot(scope: AdminScope, week_start: date, day: str, meal: str, option: str | None = None) -> date:
    clean_week = _week(week_start)
    if type(day) is not str:
        raise PartialWorkflowValidationError('Tag muss ein ISO-Datum sein.')
    try:
        service_date = date.fromisoformat(day)
    except ValueError as error:
        raise PartialWorkflowValidationError('Tag muss ein ISO-Datum sein.') from error
    if service_date.isoformat() != day:
        raise PartialWorkflowValidationError('Tag muss ein ISO-Datum sein.')
    if not clean_week <= service_date < clean_week + timedelta(days=_DAYS[scope.profile_code]):
        raise PartialWorkflowValidationError('Tag liegt ausserhalb des Profilrasters.')
    if type(meal) is not str or meal not in _MEALS[scope.profile_code]:
        raise PartialWorkflowValidationError('Mahlzeit liegt ausserhalb des Profilrasters.')
    if option is not None and (type(option) is not str or option not in _OPTIONS):
        raise PartialWorkflowValidationError('Menüart ist ungültig.')
    return service_date

def _exact(payload: Mapping[str, object], keys: frozenset[str], label: str) -> None:
    if not isinstance(payload, Mapping) or frozenset(payload) != keys:
        raise PartialWorkflowValidationError(f'{label} hat ungültige Felder.')

def _string(value: object, label: str, *, required: bool = False) -> str:
    if type(value) is not str or (required and not value.strip()):
        raise PartialWorkflowValidationError(f'{label} ist ungültig.')
    return value

def _validate_item(scope: AdminScope, payload: Mapping[str, object]) -> None:
    _exact(payload, _STAFF_KEYS if scope.profile_code == 'staff_guest' else _PATIENT_KEYS, 'Menü')
    _string(payload['title'], 'Titel', required=True)
    _string(payload['description'], 'Beschreibung')
    _string(payload['note'], 'Hinweis')
    for mode in ('allergen_mode', 'origin_mode', 'label_mode'):
        if type(payload[mode]) is not str or payload[mode] not in _MODES:
            raise PartialWorkflowValidationError(f'{mode} ist ungültig.')
    assignments = payload['assignments']
    if type(assignments) is not list or any(
        not isinstance(row, Mapping)
        or frozenset(row) != {'component_public_id', 'component_text'}
        for row in assignments
    ):
        raise PartialWorkflowValidationError('Komponenten sind ungültig.')
    labels = payload['labels']
    if type(labels) is not list or any(type(value) is not str or not value for value in labels):
        raise PartialWorkflowValidationError('Labels sind ungültig.')
    allergens = payload['allergens']
    if type(allergens) is not list or any(
            not isinstance(row, Mapping)
            or frozenset(row) != {'code', 'presence'}
            or type(row['code']) is not str
            or not row['code']
            or row['presence'] not in {'contains', 'may_contain'}
            for row in allergens
    ):
        raise PartialWorkflowValidationError('Allergene sind ungültig.')
    origins = payload['origins']
    if type(origins) is not list:
        raise PartialWorkflowValidationError('Herkünfte sind ungültig.')
    ingredients = []
    for row in origins:
        if not isinstance(row, Mapping) or frozenset(row) != {'ingredient', 'country_code', 'text'}:
            raise PartialWorkflowValidationError('Herkunft hat ungültige Felder.')
        ingredient = _string(row['ingredient'], 'Zutat', required=True)
        country = _string(row['country_code'], 'Ländercode')
        declaration = _string(row['text'], 'Herkunftstext', required=True)
        if _COUNTRY.fullmatch(country) is None or declaration != f'{ingredient}: {country}':
            raise PartialWorkflowValidationError('Herkunft ist ungültig.')
        ingredients.append(ingredient)
    if len(ingredients) != len(set(ingredients)):
        raise PartialWorkflowValidationError('Zutat ist doppelt vorhanden.')
    if scope.profile_code == 'staff_guest':
        internal = payload['internal_rappen']
        external = payload['external_rappen']
        if type(internal) is not int or type(external) is not int or internal <= 0 or external < internal:
            raise PartialWorkflowValidationError('Cafeteria-Beträge sind ungültig.')

def _require_location(connection: Connection, scope: AdminScope) -> None:
    if resolve_single_active_location_connection(connection) != scope.location_id:
        raise PartialWorkflowNotFoundError('Standort nicht gefunden.')

def resolve_week_ref(connection: Connection, scope: AdminScope, week_start: date, *,
                     for_update: bool = False) -> WeekRef:
    clean_week = _week(week_start)
    _require_location(connection, scope)
    query = _WEEK_QUERY_FOR_UPDATE if for_update else _WEEK_QUERY
    params = {'location_id': scope.location_id, 'profile_code': scope.profile_code,
              'week_start': clean_week}
    row = connection.execute(text(query), params).mappings().one_or_none()
    if row is None:
        raise PartialWorkflowNotFoundError('Woche nicht gefunden.')
    return WeekRef(int(row['id']), int(row['location_id']), str(row['profile_code']), row['week_start'],
                   int(row['row_version']))

def _service(connection: Connection, week_ref: WeekRef, service_date: date, meal: str, *,
             for_update: bool) -> Mapping[str, object] | None:
    query = _SERVICE_QUERY_FOR_UPDATE if for_update else _SERVICE_QUERY
    params = {'week_id': week_ref.week_id, 'service_date': service_date, 'meal': meal}
    return connection.execute(text(query), params).mappings().one_or_none()

def _item(connection: Connection, service_id: int, option: str, *, for_update: bool) -> Mapping[str, object] | None:
    query = _ITEM_QUERY_FOR_UPDATE if for_update else _ITEM_QUERY
    return connection.execute(text(query), {'service_id': service_id, 'option': option}).mappings().one_or_none()

def resolve_item_id(
    connection: Connection, scope: AdminScope, week_ref: WeekRef, day: str, meal: str,
    option: str, *, for_update: bool = False,
) -> int:
    if (
        type(week_ref) is not WeekRef
        or week_ref.location_id != scope.location_id
        or week_ref.profile_code != scope.profile_code
    ):
        raise PartialWorkflowNotFoundError('Woche nicht gefunden.')
    service_date = _slot(scope, week_ref.week_start, day, meal, option)
    service = _service(connection, week_ref, service_date, meal, for_update=for_update)
    if service is None:
        raise PartialWorkflowNotFoundError('Menü nicht gefunden.')
    item = _item(connection, int(service['id']), option, for_update=for_update)
    if item is None:
        raise PartialWorkflowNotFoundError('Menü nicht gefunden.')
    return int(item['id'])

def _week_for_write(connection: Connection, scope: AdminScope, week_start: date,
                    create: bool) -> tuple[WeekRef, bool]:
    _require_location(connection, scope)
    created = False
    if create:
        sql = (
            'INSERT INTO cafeteria.menu_weeks(location_id,profile_id,week_start,'
            'workflow_state,created_by,updated_by) SELECT :location_id,p.id,:week_start,'
            "'draft',:actor_id,:actor_id FROM cafeteria.offer_profiles p "
            'WHERE p.code=:profile_code ON CONFLICT (location_id,profile_id,week_start) '
            'DO NOTHING RETURNING id'
        )
        params = {'location_id': scope.location_id, 'profile_code': scope.profile_code,
                  'week_start': week_start, 'actor_id': scope.actor_id}
        created = connection.execute(text(sql), params).scalar_one_or_none() is not None
    return resolve_week_ref(connection, scope, week_start, for_update=True), created

def _touch_week(connection: Connection, scope: AdminScope, week_ref: WeekRef, created: bool) -> None:
    if not created:
        connection.execute(
            text('UPDATE cafeteria.menu_weeks SET updated_by=:actor_id WHERE id=:week_id'),
            {'actor_id': scope.actor_id, 'week_id': week_ref.week_id},
        )

def persist_week_header(
    engine: Engine, scope: AdminScope, week_start: date, payload: Mapping[str, object], expected_week_row_version: int,
) -> int:
    clean_week = _week(week_start)
    expected = _expected(expected_week_row_version, 'expected_week_row_version')
    _exact(payload, frozenset({'title', 'shared_note'}), 'Wochenkopf')
    title = _string(payload['title'], 'Wochentitel', required=True)
    note = _string(payload['shared_note'], 'Wochenhinweis')
    with engine.begin() as connection:
        _require_location(connection, scope)
        if expected == 0:
            sql = (
                'INSERT INTO cafeteria.menu_weeks(location_id,profile_id,week_start,'
                'workflow_state,title,shared_note,created_by,updated_by) '
                "SELECT :location_id,p.id,:week_start,'draft',:title,NULLIF(:note,''),"
                ':actor_id,:actor_id FROM cafeteria.offer_profiles p '
                'WHERE p.code=:profile_code ON CONFLICT (location_id,profile_id,week_start) '
                'DO NOTHING RETURNING row_version'
            )
            params = {'location_id': scope.location_id, 'profile_code': scope.profile_code,
                      'week_start': clean_week, 'title': title, 'note': note,
                      'actor_id': scope.actor_id}
            row = connection.execute(text(sql), params).scalar_one_or_none()
            resolve_week_ref(connection, scope, clean_week, for_update=True)
            if row is None:
                raise PartialWorkflowConflictError('Woche wurde zwischenzeitlich angelegt.')
            return int(row)
        week_ref = resolve_week_ref(connection, scope, clean_week, for_update=True)
        if week_ref.row_version != expected:
            raise PartialWorkflowConflictError('Woche wurde zwischenzeitlich geändert.')
        row = connection.execute(text(
            "UPDATE cafeteria.menu_weeks SET title=:title,shared_note=NULLIF(:note,''),"
            'updated_by=:actor_id WHERE id=:week_id RETURNING row_version'
        ), {'title': title, 'note': note, 'actor_id': scope.actor_id,
            'week_id': week_ref.week_id}).scalar_one()
        return int(row)

def persist_service_state(
    engine: Engine, scope: AdminScope, week_start: date, day: str, meal: str,
    payload: Mapping[str, object], expected_service_row_version: int,
) -> int:
    service_date = _slot(scope, week_start, day, meal)
    expected = _expected(expected_service_row_version, 'expected_service_row_version')
    _exact(payload, frozenset({'service_state', 'notice'}), 'Service')
    state = _string(payload['service_state'], 'Servicestatus')
    notice = _string(payload['notice'], 'Servicehinweis')
    if state not in _STATES or (state != 'open' and not notice.strip()):
        raise PartialWorkflowValidationError('Servicestatus oder Hinweis ist ungültig.')
    with engine.begin() as connection:
        week_ref, created_week = _week_for_write(connection, scope, week_start, expected == 0)
        service = _service(connection, week_ref, service_date, meal, for_update=True)
        if expected == 0:
            if service is not None:
                raise PartialWorkflowConflictError('Service wurde zwischenzeitlich angelegt.')
            sql = (
                'INSERT INTO cafeteria.menu_services(menu_week_id,service_date,'
                'meal_period_id,service_state,notice) SELECT :week_id,:service_date,mp.id,'
                ":state,NULLIF(:notice,'') FROM cafeteria.meal_periods mp "
                'WHERE mp.code=:meal RETURNING row_version'
            )
            params = {'week_id': week_ref.week_id, 'service_date': service_date,
                      'state': state, 'notice': notice, 'meal': meal}
            row = connection.execute(text(sql), params).scalar_one()
            _touch_week(connection, scope, week_ref, created_week)
            return int(row)
        if service is None:
            raise PartialWorkflowNotFoundError('Service nicht gefunden.')
        if int(service['row_version']) != expected:
            raise PartialWorkflowConflictError('Service wurde zwischenzeitlich geändert.')
        has_items = connection.execute(text(
            'SELECT EXISTS(SELECT 1 FROM cafeteria.menu_items WHERE service_id=:id)'
        ), {'id': service['id']}).scalar_one()
        if state != 'open' and has_items:
            raise PartialWorkflowConflictError('Service mit Menü kann nicht geschlossen werden.')
        row = connection.execute(text(
            "UPDATE cafeteria.menu_services SET service_state=:state,notice=NULLIF(:notice,'') "
            'WHERE id=:id RETURNING row_version'
        ), {'state': state, 'notice': notice, 'id': service['id']}).scalar_one()
        _touch_week(connection, scope, week_ref, created_week)
        return int(row)

def _replace_effects(connection: Connection, item_id: int, payload: Mapping[str, object]) -> None:
    deletes = (
        'DELETE FROM cafeteria.menu_item_labels WHERE menu_item_id=:item_id',
        'DELETE FROM cafeteria.menu_item_allergens WHERE menu_item_id=:item_id',
        'DELETE FROM cafeteria.origin_declarations WHERE menu_item_id=:item_id',
    )
    for statement in deletes:
        connection.execute(text(statement), {'item_id': item_id})
    if payload['label_mode'] == 'manual':
        for code in payload['labels']:
            sql = ('INSERT INTO cafeteria.menu_item_labels(menu_item_id,label_id) '
                   'SELECT :item_id,id FROM cafeteria.dietary_labels WHERE code=:code')
            result = connection.execute(text(sql), {'item_id': item_id, 'code': code})
            if result.rowcount != 1:
                raise PartialWorkflowValidationError('Label ist ungültig.')
    if payload['allergen_mode'] == 'manual':
        for row in payload['allergens']:
            sql = ('INSERT INTO cafeteria.menu_item_allergens(menu_item_id,allergen_id,presence) '
                   'SELECT :item_id,id,:presence FROM cafeteria.allergens WHERE code=:code')
            params = {'item_id': item_id, 'code': row['code'], 'presence': row['presence']}
            result = connection.execute(text(sql), params)
            if result.rowcount != 1:
                raise PartialWorkflowValidationError('Allergen ist ungültig.')
    if payload['origin_mode'] == 'manual':
        for row in payload['origins']:
            sql = ('INSERT INTO cafeteria.origin_declarations(menu_item_id,ingredient,'
                   'country_code,declaration_text) VALUES '
                   '(:item_id,:ingredient,:country_code,:text)')
            connection.execute(text(sql), {'item_id': item_id, **row})

def _set_price(connection: Connection, item_id: int, scope: AdminScope, payload: Mapping[str, object]) -> None:
    if scope.profile_code != 'staff_guest':
        return
    sql = (
        'INSERT INTO cafeteria.menu_item_prices(menu_item_id,internal_rappen,external_rappen) '
        'VALUES (:item_id,:internal,:external) ON CONFLICT (menu_item_id) DO UPDATE SET '
        'internal_rappen=EXCLUDED.internal_rappen,external_rappen=EXCLUDED.external_rappen'
    )
    params = {'item_id': item_id, 'internal': payload['internal_rappen'],
              'external': payload['external_rappen']}
    connection.execute(text(sql), params)

def persist_menu_item(
    engine: Engine, scope: AdminScope, week_start: date, day: str, meal: str,
    option: str, payload: Mapping[str, object], expected_item_row_version: int,
) -> int:
    service_date = _slot(scope, week_start, day, meal, option)
    expected = _expected(expected_item_row_version, 'expected_item_row_version')
    _validate_item(scope, payload)
    with engine.begin() as connection:
        week_ref, created_week = _week_for_write(connection, scope, week_start, expected == 0)
        service = _service(connection, week_ref, service_date, meal, for_update=True)
        if service is None:
            if expected > 0:
                raise PartialWorkflowNotFoundError('Menü nicht gefunden.')
            sql = (
                'INSERT INTO cafeteria.menu_services(menu_week_id,service_date,meal_period_id,'
                "service_state) SELECT :week_id,:service_date,id,'open' "
                'FROM cafeteria.meal_periods WHERE code=:meal '
                'RETURNING id,row_version,service_state'
            )
            params = {'week_id': week_ref.week_id, 'service_date': service_date, 'meal': meal}
            service = connection.execute(text(sql), params).mappings().one()
        if service['service_state'] != 'open':
            raise PartialWorkflowConflictError('Geschlossener Service kann kein Menü speichern.')
        current = _item(connection, int(service['id']), option, for_update=True)
        if current is not None and expected == 0:
            raise PartialWorkflowConflictError('Menü wurde zwischenzeitlich angelegt.')
        if current is None and expected > 0:
            raise PartialWorkflowNotFoundError('Menü nicht gefunden.')
        if current is not None and int(current['row_version']) != expected:
            raise PartialWorkflowConflictError('Menü wurde zwischenzeitlich geändert.')
        if current is None:
            sql = (
                'INSERT INTO cafeteria.menu_items(service_id,menu_type_id,external_id,title,'
                'description,note,allergen_review_status,sort_order,allergen_mode,origin_mode,'
                "label_mode) SELECT :service_id,id,:external_id,:title,NULLIF(:description,''),"
                "NULLIF(:note,''),'not_checked',:sort_order,:allergen_mode,:origin_mode,:label_mode "
                'FROM cafeteria.menu_types WHERE code=:option RETURNING id'
            )
            params = {
                'service_id': service['id'],
                'external_id': external_id(scope.profile_code, day, meal, option),
                'title': payload['title'], 'description': payload['description'],
                'note': payload['note'], 'sort_order': _OPTIONS.index(option) + 1,
                'allergen_mode': payload['allergen_mode'], 'origin_mode': payload['origin_mode'],
                'label_mode': payload['label_mode'], 'option': option,
            }
            item_id = int(connection.execute(text(sql), params).scalar_one())
        else:
            item_id = int(current['id'])
        replace_component_links_connection(connection, scope, item_id, payload['assignments'])
        _replace_effects(connection, item_id, payload)
        modes = {
            'allergen_mode': payload['allergen_mode'],
            'origin_mode': payload['origin_mode'],
            'label_mode': payload['label_mode'],
        }
        rematerialize_auto_effects(connection, item_id, modes)
        _set_price(connection, item_id, scope, payload)
        if current is None:
            version = 1
        else:
            sql = (
                "UPDATE cafeteria.menu_items SET title=:title,description=NULLIF(:description,''),"
                "note=NULLIF(:note,''),allergen_mode=:allergen_mode,origin_mode=:origin_mode,"
                "label_mode=:label_mode,allergen_review_status='not_checked' "
                'WHERE id=:item_id RETURNING row_version'
            )
            version = int(connection.execute(
                text(sql), {'item_id': item_id, **payload}
            ).scalar_one())
        _touch_week(connection, scope, week_ref, created_week)
        return version
