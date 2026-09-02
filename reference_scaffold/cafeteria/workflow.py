from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Engine, text

from .db import issue_publication_capability
from .workflow_snapshot import build_snapshot
from .workflow_store import (
    StaleDraftError,
    draft_row_version,
    ensure_week,
    ensure_week_connection,
    load_draft_connection,
    persist_draft,
    persist_draft_connection,
)

PROFILE_MEALS = {'patient': ('LUNCH', 'DINNER'), 'staff_guest': ('LUNCH',)}
PROFILE_DAYS = {'patient': 7, 'staff_guest': 5}
MENU_TYPES = ('MENU_1', 'VEGGIE')
SERVICE_STATES = {'open', 'closed', 'holiday', 'company_holiday'}
SIGNAGE_LIMITS = {
    'staff_guest': {
        'day': {'title': 46, 'description': 70, 'components': 70},
        'week': {'title': 36, 'components': 48},
    },
    'patient': {
        'day': {'title': 42, 'components': 62},
        'week': {'title': 36, 'components': 48},
    },
}
PUBLICATION_TITLE_LIMIT = 36
PUBLICATION_COMPONENTS_LIMIT = 48


class WorkflowValidationError(ValueError):
    def __init__(self, message: str, *, field_name: str | None = None) -> None:
        super().__init__(message)
        self.field_name = field_name


class PublicationConfigurationError(RuntimeError):
    pass


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    unexpected = set(value) - expected
    missing = expected - set(value)
    if unexpected:
        raise WorkflowValidationError(f'Unzulässiges {label}: {sorted(unexpected)[0]}')
    if missing:
        raise WorkflowValidationError(f'Fehlendes {label}: {sorted(missing)[0]}')


def _validate_values(profile_code: str, week_start: date, values: dict[str, Any]) -> None:
    if profile_code not in PROFILE_MEALS:
        raise WorkflowValidationError('Unbekanntes Profil.')
    if week_start.isoweekday() != 1:
        raise WorkflowValidationError('Die Woche muss an einem Montag beginnen.')
    _require_exact_keys(values, {'title', 'shared_note', 'days'}, 'Wurzelfeld')
    if not isinstance(values['title'], str) or not values['title'].strip():
        raise WorkflowValidationError('Wochentitel fehlt.')
    if not isinstance(values['shared_note'], str):
        raise WorkflowValidationError('Wochenhinweis ist ungültig.')
    days = values['days']
    if not isinstance(days, list) or len(days) != PROFILE_DAYS[profile_code]:
        raise WorkflowValidationError('Das Raster hat eine ungültige Anzahl Tage.')
    required_option_keys = {'type_code', 'title', 'components'}
    allowed_option_keys = required_option_keys | {
        'external_id',
        'description',
        'labels',
        'allergens',
        'origins',
        'note',
        'allergen_review_status',
    }
    if profile_code == 'staff_guest':
        required_option_keys |= {'internal_rappen', 'external_rappen'}
        allowed_option_keys |= {'internal_rappen', 'external_rappen'}
    for offset, day_value in enumerate(days):
        if not isinstance(day_value, dict):
            raise WorkflowValidationError('Ungültiger Tag im Raster.')
        _require_exact_keys(day_value, {'date', 'services'}, 'Tagesfeld')
        expected_date = (week_start + timedelta(days=offset)).isoformat()
        if day_value['date'] != expected_date:
            raise WorkflowValidationError('Servicedaten müssen lückenlos zur Woche passen.')
        services = day_value['services']
        if not isinstance(services, list) or len(services) != len(PROFILE_MEALS[profile_code]):
            raise WorkflowValidationError('Mahlzeitenraster ist unvollständig.')
        if {service.get('meal_code') for service in services if isinstance(service, dict)} != set(
            PROFILE_MEALS[profile_code]
        ):
            raise WorkflowValidationError('Mahlzeitenraster enthält ein unzulässiges Angebot.')
        for service in services:
            _require_exact_keys(
                service,
                {'meal_code', 'service_state', 'notice', 'options'},
                'Mahlzeitenfeld',
            )
            state = service['service_state']
            if state not in SERVICE_STATES:
                raise WorkflowValidationError('Unzulässiger Schliessungsstatus.')
            if not isinstance(service['notice'], str):
                raise WorkflowValidationError('Servicehinweis ist ungültig.')
            if state != 'open' and not service['notice'].strip():
                raise WorkflowValidationError('Geschlossene Mahlzeit braucht einen Hinweis.')
            options = service['options']
            if not isinstance(options, list) or len(options) != 2:
                raise WorkflowValidationError('Jede Rasterzelle braucht zwei Menüarten.')
            if {option.get('type_code') for option in options if isinstance(option, dict)} != set(MENU_TYPES):
                raise WorkflowValidationError('Menüartenraster ist unvollständig.')
            for option in options:
                unexpected = set(option) - allowed_option_keys
                missing = required_option_keys - set(option)
                if unexpected:
                    raise WorkflowValidationError(f'Unzulässiges Menüfeld: {sorted(unexpected)[0]}')
                if missing:
                    raise WorkflowValidationError(f'Fehlendes Menüfeld: {sorted(missing)[0]}')
                components = option['components']
                if not isinstance(components, list) or any(not isinstance(item, str) for item in components):
                    raise WorkflowValidationError('Komponentenliste ist ungültig.')
                for key in ('external_id', 'description', 'note', 'allergen_review_status'):
                    if key in option and not isinstance(option[key], str):
                        raise WorkflowValidationError('Menümetadaten sind ungültig.')
                for key in ('labels', 'allergens', 'origins'):
                    if key in option and not isinstance(option[key], list):
                        raise WorkflowValidationError('Menümetadaten sind ungültig.')
                if state != 'open':
                    continue
                if not isinstance(option['title'], str) or not option['title'].strip():
                    raise WorkflowValidationError('Offenes Menü braucht einen Titel.')
                if profile_code == 'staff_guest':
                    internal = option['internal_rappen']
                    external = option['external_rappen']
                    if type(internal) is not int or type(external) is not int:
                        raise WorkflowValidationError('Cafeteria-Beträge müssen ganze Rappen sein.')
                    if internal <= 0 or external < internal:
                        raise WorkflowValidationError('Cafeteria-Beträge sind ungültig.')


def load_draft(
    engine: Engine,
    profile_code: str,
    week_start: date,
    *,
    actor_id: int,
) -> dict[str, Any]:
    if profile_code not in PROFILE_MEALS or week_start.isoweekday() != 1:
        raise WorkflowValidationError('Profil oder Wochenbeginn ist ungültig.')
    ensure_week(engine, profile_code, week_start, actor_id)
    with engine.connect() as connection:
        draft = load_draft_connection(connection, profile_code, week_start)
    if profile_code == 'patient':
        build_snapshot(
            profile_code,
            draft,
            f'PAT-{week_start.year}-KW{week_start.isocalendar().week:02d}-R1',
        )
    return draft


def save_draft(
    engine: Engine,
    profile_code: str,
    week_start: date,
    *,
    expected_row_version: int,
    actor_id: int,
    values: dict[str, Any],
) -> int:
    validate_draft_values(profile_code, week_start, values)
    return persist_draft(
        engine,
        profile_code,
        week_start,
        expected_row_version=expected_row_version,
        actor_id=actor_id,
        values=values,
    )


def validate_draft_values(
    profile_code: str,
    week_start: date,
    values: dict[str, Any],
) -> None:
    _validate_values(profile_code, week_start, values)
    candidate = {
        **values,
        'week_start': week_start.isoformat(),
        'location': {'code': 'KIRCHLINDACH', 'name': 'Südhang'},
    }
    build_snapshot(
        profile_code,
        candidate,
        f"{'PAT' if profile_code == 'patient' else 'CAF'}-{week_start.year}-KW{week_start.isocalendar().week:02d}-R1",
    )


def validate_publication_fit(profile_code: str, values: dict[str, Any]) -> None:
    if profile_code not in SIGNAGE_LIMITS:
        raise WorkflowValidationError('Unbekanntes Profil.')
    for day_index, day in enumerate(values['days']):
        for service in day['services']:
            if service['service_state'] != 'open':
                continue
            meal_code = service['meal_code']
            for option in service['options']:
                prefix = f"service_{day_index}_{meal_code}_{option['type_code']}"
                if len(option['title']) > PUBLICATION_TITLE_LIMIT:
                    raise WorkflowValidationError(
                        'Gericht überschreitet die gemeinsame Playergrenze von 36 Zeichen.',
                        field_name=f'{prefix}_title',
                    )
                rendered_components = ' · '.join(option['components'])
                if len(rendered_components) > PUBLICATION_COMPONENTS_LIMIT:
                    raise WorkflowValidationError(
                        'Komponenten überschreiten die gemeinsame Playergrenze von 48 Zeichen.',
                        field_name=f'{prefix}_components',
                    )
                description = option.get('description', '')
                if profile_code == 'staff_guest' and len(description) > SIGNAGE_LIMITS[
                    'staff_guest'
                ]['day']['description']:
                    raise WorkflowValidationError(
                        'Beschreibung überschreitet die Tagesplayergrenze von 70 Zeichen.'
                    )

                # Validate allergen review status before publishing
                if option.get("allergen_review_status") != "checked":
                    raise WorkflowValidationError(
                        "Allergendeklaration ist nicht geprüft.",
                        field_name=f"{prefix}_allergen_reviewed",
                    )


def import_draft(
    engine: Engine,
    profile_code: str,
    week_start: date,
    *,
    expected_row_version: int,
    actor_id: int,
    values: dict[str, Any],
) -> int:
    validate_draft_values(profile_code, week_start, values)
    with engine.begin() as connection:
        persisted_version = expected_row_version
        if expected_row_version == 0:
            if not ensure_week_connection(connection, profile_code, week_start, actor_id):
                raise StaleDraftError('Der Entwurf wurde zwischenzeitlich geändert.')
            persisted_version = 1
        return persist_draft_connection(
            connection,
            profile_code,
            week_start,
            expected_row_version=persisted_version,
            actor_id=actor_id,
            values=values,
        )


def current_draft_row_version(engine: Engine, profile_code: str, week_start: date) -> int:
    if profile_code not in PROFILE_MEALS or week_start.isoweekday() != 1:
        raise WorkflowValidationError('Profil oder Wochenbeginn ist ungültig.')
    return draft_row_version(engine, profile_code, week_start)


def _draft_values(draft: dict[str, Any]) -> dict[str, Any]:
    days = []
    for day in draft['days']:
        services = []
        for service in day['services']:
            services.append(
                {
                    'meal_code': service['meal_code'],
                    'service_state': service['service_state'],
                    'notice': service['notice'],
                    'options': service['options'],
                }
            )
        days.append({'date': day['date'], 'services': services})
    return {
        'title': draft['title'],
        'shared_note': draft['shared_note'],
        'days': days,
    }


def publish_draft(
    engine: Engine,
    profile_code: str,
    week_start: date,
    *,
    expected_row_version: int,
    actor_id: int,
    issuer_engine: Engine | None,
) -> dict[str, Any]:
    with engine.connect() as connection:
        previous_id = connection.execute(
            text(
                '''
                SELECT r.id
                FROM cafeteria.publication_revisions r
                JOIN cafeteria.menu_weeks w ON w.id=r.menu_week_id
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                WHERE p.code=:profile_code AND w.week_start=:week_start AND r.withdrawn_at IS NULL
                '''
            ),
            {'profile_code': profile_code, 'week_start': week_start},
        ).scalar_one_or_none()
    capability = None
    if previous_id is not None:
        if issuer_engine is None:
            raise PublicationConfigurationError('Publikations-Issuer ist nicht konfiguriert.')
        capability = issue_publication_capability(issuer_engine, actor_id, int(previous_id))
    with engine.begin() as connection:
        draft = load_draft_connection(
            connection,
            profile_code,
            week_start,
            lock_week=True,
        )
        if draft['row_version'] != expected_row_version:
            raise StaleDraftError('Der Entwurf wurde zwischenzeitlich geändert.')
        values = _draft_values(draft)
        _validate_values(profile_code, week_start, values)
        validate_publication_fit(profile_code, values)
        revision_number = int(
            connection.execute(
                text(
                    'SELECT COALESCE(max(revision_number), 0) + 1 '
                    'FROM cafeteria.publication_revisions WHERE menu_week_id=:week_id'
                ),
                {'week_id': draft['id']},
            ).scalar_one()
        )
        prefix = 'PAT' if profile_code == 'patient' else 'CAF'
        revision_code = (
            f'{prefix}-{week_start.year}-KW{week_start.isocalendar().week:02d}-R{revision_number}'
        )
        snapshot = build_snapshot(profile_code, draft, revision_code)
        current_id = connection.execute(
            text(
                'SELECT id FROM cafeteria.publication_revisions '
                'WHERE menu_week_id=:week_id AND withdrawn_at IS NULL'
            ),
            {'week_id': draft['id']},
        ).scalar_one_or_none()
        if current_id != previous_id:
            raise StaleDraftError('Die aktive Publikation wurde zwischenzeitlich geändert.')
        if current_id is not None:
            assert capability is not None
            connection.execute(
                text(
                    'SELECT cafeteria.withdraw_publication_revision('
                    ':revision_id, :capability, :reason)'
                ),
                {
                    'revision_id': current_id,
                    'capability': capability,
                    'reason': 'Durch neue Küchenrevision ersetzt.',
                },
            ).scalar_one()
        connection.execute(
            text(
                "UPDATE cafeteria.menu_weeks SET workflow_state='published', updated_by=:actor_id "
                'WHERE id=:week_id'
            ),
            {'actor_id': actor_id, 'week_id': draft['id']},
        )
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.publication_revisions(
                    menu_week_id, revision_number, revision_code, snapshot_json, published_by
                ) VALUES (
                    :week_id, :revision_number, :revision_code, CAST(:snapshot AS jsonb), :actor_id
                )
                '''
            ),
            {
                'week_id': draft['id'],
                'revision_number': revision_number,
                'revision_code': revision_code,
                'snapshot': json.dumps(snapshot, ensure_ascii=False),
                'actor_id': actor_id,
            },
        )
    return snapshot
