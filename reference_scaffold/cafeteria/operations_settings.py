"""Wiederkehrende Wochenvorgaben und Bereichsnamen.

Vorgaben liegen als JSONB im vorhandenen Settings-Namensraum je Standort und Profil.
Sie verändern niemals bestehende `menu_services`-Zeilen; sie liefern nur Standardwerte
für Slots, die noch keine Zeile haben. Schreiben ist Compare-and-Set über `revision`
beziehungsweise über den bisherigen Anzeigenamen, jeweils mit Akteur-, `authz_version`-
und Adminnachweis unter bis zum Transaktionsende gehaltenen IAM-Sperren.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from .patient_payload import PROFILES, patient_text_is_forbidden

SETTING_KEY = 'operations_schedule'
MEALS = ('LUNCH', 'DINNER')
SLOT_STATES = ('open', 'closed')
SLOT_KEYS = frozenset({'state', 'start', 'end', 'notice'})
SCHEDULE_KEYS = frozenset({'revision', 'slots'})
MAX_NOTICE_LENGTH = 200
MAX_AREA_NAME_LENGTH = 80
TIME_RE = re.compile(r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
PROFILE_SLOTS: dict[str, tuple[tuple[int, str], ...]] = {
    'staff_guest': tuple((day, 'LUNCH') for day in range(1, 8)),
    'patient': tuple((day, meal) for day in range(1, 8) for meal in MEALS),
}

_SAVE_SCHEDULE_SQL = """
    INSERT INTO cafeteria.settings(location_id, profile_id, setting_key, setting_value, updated_by)
    SELECT :location_id, p.id, 'operations_schedule', CAST(:value AS jsonb), u.id
    FROM cafeteria.users u CROSS JOIN cafeteria.offer_profiles p
    WHERE p.code=:profile AND u.id=:actor_id AND u.authz_version=:authz_version
      AND u.disabled_at IS NULL
      AND CAST(:expected_revision AS integer) = 0
      AND EXISTS (
        SELECT 1 FROM cafeteria.user_role_cache r
        JOIN cafeteria.application_roles a ON a.role_code=r.role_code AND a.active
        WHERE r.user_id=u.id AND r.role_code='Cafeteria.Admin'
      )
    ON CONFLICT (location_id, profile_id, setting_key) DO NOTHING
    RETURNING id
"""
_UPDATE_SCHEDULE_SQL = """
    UPDATE cafeteria.settings s
    SET setting_value=CAST(:value AS jsonb), updated_by=:actor_id, updated_at=clock_timestamp()
    FROM cafeteria.offer_profiles p
    WHERE p.code=:profile AND s.profile_id=p.id AND s.location_id=:location_id
      AND s.setting_key='operations_schedule'
      AND (s.setting_value->>'revision')::int=:expected_revision
    RETURNING s.id
"""
_SAVE_AREA_NAME_SQL = """
    UPDATE cafeteria.offer_profiles p SET display_name=:new_name
    FROM cafeteria.users u
    WHERE p.code=:profile AND p.display_name=:expected_name
      AND u.id=:actor_id AND u.authz_version=:authz_version AND u.disabled_at IS NULL
      AND EXISTS (
        SELECT 1 FROM cafeteria.user_role_cache r
        JOIN cafeteria.application_roles a ON a.role_code=r.role_code AND a.active
        WHERE r.user_id=u.id AND r.role_code='Cafeteria.Admin'
      )
    RETURNING p.id
"""


class OperationsConflictError(RuntimeError):
    """Eine parallele Änderung hat die erwartete Version oder den erwarteten Namen überholt."""


@dataclass(frozen=True)
class SlotRule:
    state: str
    start: str | None
    end: str | None
    notice: str


@dataclass(frozen=True)
class OperationsSchedule:
    profile_code: str
    revision: int
    slots: dict[tuple[int, str], SlotRule]
    allows_weekend: bool = False


def _profile_slots(profile: str) -> tuple[tuple[int, str], ...]:
    slots = PROFILE_SLOTS.get(profile)
    if slots is None:
        raise ValueError('Unbekannter Bereich.')
    return slots


def normalise_time(value: Any) -> str | None:
    if value is None or value == '':
        return None
    if not isinstance(value, str) or TIME_RE.fullmatch(value) is None:
        raise ValueError('Zeiten müssen als HH:MM zwischen 00:00 und 23:59 angegeben werden.')
    return value


def default_schedule(profile: str) -> OperationsSchedule:
    return OperationsSchedule(
        profile_code=profile,
        revision=0,
        slots={slot: (
            SlotRule('closed', None, None, 'Am Wochenende geschlossen')
            if profile == 'staff_guest' and slot[0] > 5 else SlotRule('open', None, None, '')
        ) for slot in _profile_slots(profile)},
        allows_weekend=profile == 'patient',
    )


def _parse_slot(profile: str, value: Any) -> SlotRule:
    if not isinstance(value, dict) or set(value) != SLOT_KEYS:
        raise ValueError('Jeder Slot braucht genau state, start, end und notice.')
    if value['state'] not in SLOT_STATES:
        raise ValueError('Der Betrieb eines Slots muss open oder closed sein.')
    start = normalise_time(value['start'])
    end = normalise_time(value['end'])
    if start is not None and end is not None and end <= start:
        raise ValueError('Das Serviceende muss nach dem Servicebeginn liegen.')
    notice = value['notice']
    if not isinstance(notice, str) or len(notice) > MAX_NOTICE_LENGTH:
        raise ValueError('Ein Hinweis ist Text mit höchstens 200 Zeichen.')
    if any(unicodedata.category(character).startswith('C') for character in notice):
        raise ValueError('Ein Hinweis darf keine Steuerzeichen enthalten.')
    if value['state'] == 'closed' and not notice.strip():
        raise ValueError('Ein geschlossener Slot braucht einen Hinweis.')
    if profile == 'patient' and patient_text_is_forbidden(notice):
        raise ValueError('Patientenhinweise dürfen keine Kosteninformationen enthalten.')
    return SlotRule(state=value['state'], start=start, end=end, notice=notice)


def parse_schedule(profile: str, value: Any) -> OperationsSchedule:
    expected = _profile_slots(profile)
    if value is None:
        return default_schedule(profile)
    if not isinstance(value, dict) or set(value) != SCHEDULE_KEYS:
        raise ValueError('Wochenvorgaben brauchen genau die Schlüssel revision und slots.')
    revision = value['revision']
    if type(revision) is not int or revision < 0:
        raise ValueError('Die Version der Wochenvorgaben muss eine Ganzzahl ab 0 sein.')
    raw_slots = value['slots']
    if not isinstance(raw_slots, dict) or set(raw_slots) != {str(day) for day, _ in expected}:
        raise ValueError('Wochenvorgaben brauchen genau die Wochentage des Bereichs.')
    slots: dict[tuple[int, str], SlotRule] = {}
    for day, meal in expected:
        day_value = raw_slots[str(day)]
        expected_meals = {other_meal for other_day, other_meal in expected if other_day == day}
        if not isinstance(day_value, dict) or set(day_value) != expected_meals:
            raise ValueError('Jeder Wochentag braucht genau die Mahlzeiten des Bereichs.')
        slots[(day, meal)] = _parse_slot(profile, day_value[meal])
    return OperationsSchedule(
        profile_code=profile, revision=revision, slots=slots, allows_weekend=profile == 'patient'
    )


def _schedule_payload(schedule: OperationsSchedule) -> dict[str, Any]:
    slots: dict[str, dict[str, dict[str, Any]]] = {}
    for (day, meal), rule in schedule.slots.items():
        slots.setdefault(str(day), {})[meal] = {
            'state': rule.state, 'start': rule.start, 'end': rule.end, 'notice': rule.notice,
        }
    return {'revision': schedule.revision, 'slots': slots}


def get_schedule_connection(
    connection: Connection, location_id: int, profile: str
) -> OperationsSchedule:
    _profile_slots(profile)
    stored = connection.execute(text("""
        SELECT s.setting_value, p.allows_weekend FROM cafeteria.offer_profiles p
        LEFT JOIN cafeteria.settings s ON s.profile_id=p.id AND s.location_id=:location_id
          AND s.setting_key='operations_schedule'
        WHERE p.code=:profile
    """), {'location_id': location_id, 'profile': profile}).one()
    return replace(parse_schedule(profile, stored.setting_value), allows_weekend=stored.allows_weekend)


def get_schedule(engine: Engine, location_id: int, profile: str) -> OperationsSchedule:
    with engine.connect() as connection:
        return get_schedule_connection(connection, location_id, profile)


def slot_defaults(schedule: OperationsSchedule, service_date: dt.date, meal: str) -> SlotRule:
    rule = schedule.slots[(service_date.isoweekday(), meal)]
    if schedule.profile_code == 'staff_guest' and service_date.isoweekday() > 5 and not schedule.allows_weekend:
        return SlotRule('closed', None, None, 'Am Wochenende geschlossen')
    return rule


def _require_actor_shape(actor_id: int, authz_version: int) -> None:
    if (
        type(actor_id) is not int or actor_id <= 0
        or type(authz_version) is not int or authz_version <= 0
    ):
        raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')


def _actor_is_active_admin(connection: Connection, actor_id: int, authz_version: int) -> bool:
    try:
        connection.execute(text('SELECT cafeteria.lock_operations_actor(:actor_id, :authz_version)'),
                           {'actor_id': actor_id, 'authz_version': authz_version})
    except DBAPIError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '42501':
            raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.') from None
        raise
    return True


def save_schedule(
    engine: Engine,
    actor_id: int,
    authz_version: int,
    location_id: int,
    profile: str,
    expected_revision: int,
    slots: Any,
) -> int:
    _require_actor_shape(actor_id, authz_version)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('Die erwartete Version der Wochenvorgaben muss eine Ganzzahl ab 0 sein.')
    schedule = parse_schedule(profile, {'revision': expected_revision + 1, 'slots': slots})
    parameters = {
        'location_id': location_id,
        'profile': profile,
        'actor_id': actor_id,
        'authz_version': authz_version,
        'expected_revision': expected_revision,
        'value': json.dumps(_schedule_payload(schedule)),
    }
    with engine.begin() as connection:
        actor_is_admin = _actor_is_active_admin(connection, actor_id, authz_version)
        statement = _SAVE_SCHEDULE_SQL if expected_revision == 0 else _UPDATE_SCHEDULE_SQL
        saved = connection.execute(text(statement), parameters).scalar_one_or_none()
        if saved is None:
            if not actor_is_admin:
                raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
            raise OperationsConflictError('Wochenvorgaben wurden zwischenzeitlich geändert.')
    return schedule.revision


def get_area_names(engine_or_connection: Engine | Connection) -> dict[str, str]:
    statement = text('SELECT code, display_name FROM cafeteria.offer_profiles')
    if isinstance(engine_or_connection, Engine):
        with engine_or_connection.connect() as connection:
            rows = connection.execute(statement).all()
    else:
        rows = engine_or_connection.execute(statement).all()
    names = {str(code): str(display_name) for code, display_name in rows}
    if set(names) != PROFILES:
        raise RuntimeError('Die Bereichsnamen sind unvollständig.')
    return names


def get_area_profiles(engine_or_connection: Engine | Connection) -> dict[str, dict[str, Any]]:
    statement = text('SELECT code, display_name, allows_weekend, allows_prices, allowed_meals '
                     'FROM cafeteria.offer_profiles')
    if isinstance(engine_or_connection, Engine):
        with engine_or_connection.connect() as connection:
            rows = connection.execute(statement).mappings().all()
    else:
        rows = engine_or_connection.execute(statement).mappings().all()
    profiles = {row['code']: {key: value for key, value in row.items() if key != 'code'} for row in rows}
    if set(profiles) != PROFILES:
        raise RuntimeError('Die Bereiche sind unvollständig.')
    return profiles


def save_weekend_switch(
    engine: Engine, actor_id: int, authz_version: int, profile: str, expected: bool, value: bool
) -> bool:
    _require_actor_shape(actor_id, authz_version)
    if profile != 'staff_guest' or type(expected) is not bool or type(value) is not bool:
        raise ValueError('Nur der Cafeteria-Wochenendbetrieb ist mit booleschen Werten schaltbar.')
    with engine.begin() as connection:
        _actor_is_active_admin(connection, actor_id, authz_version)
        saved = connection.execute(text('''
            UPDATE cafeteria.offer_profiles SET allows_weekend=:value
            WHERE code=:profile AND allows_weekend=:expected RETURNING id
        '''), {'profile': profile, 'expected': expected, 'value': value}).scalar_one_or_none()
        if saved is None:
            raise OperationsConflictError('Wochenendbetrieb wurde zwischenzeitlich geändert.')
    return value


def _normalise_area_name(profile: str, value: Any) -> str:
    if profile not in PROFILES:
        raise ValueError('Unbekannter Bereich.')
    if not isinstance(value, str):
        raise ValueError('Ein Bereichsname ist Text mit 1 bis 80 Zeichen.')
    name = value.strip()
    if not 1 <= len(name) <= MAX_AREA_NAME_LENGTH:
        raise ValueError('Ein Bereichsname ist Text mit 1 bis 80 Zeichen.')
    if any(unicodedata.category(character).startswith('C') for character in name):
        raise ValueError('Ein Bereichsname darf keine Steuerzeichen enthalten.')
    if profile == 'patient' and patient_text_is_forbidden(name):
        raise ValueError('Patientenbereichsnamen dürfen keine Kosteninformationen enthalten.')
    return name


def save_area_name(
    engine: Engine,
    actor_id: int,
    authz_version: int,
    profile: str,
    expected_name: str,
    new_name: str,
) -> str:
    _require_actor_shape(actor_id, authz_version)
    name = _normalise_area_name(profile, new_name)
    if not isinstance(expected_name, str):
        raise ValueError('Der bisherige Bereichsname muss als Text übergeben werden.')
    parameters = {
        'profile': profile,
        'expected_name': expected_name,
        'new_name': name,
        'actor_id': actor_id,
        'authz_version': authz_version,
    }
    with engine.begin() as connection:
        actor_is_admin = _actor_is_active_admin(connection, actor_id, authz_version)
        saved = connection.execute(text(_SAVE_AREA_NAME_SQL), parameters).scalar_one_or_none()
        if saved is None:
            if not actor_is_admin:
                raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
            raise OperationsConflictError('Anzeigename wurde zwischenzeitlich geändert.')
    return name
