from __future__ import annotations

import datetime as dt
import re
from typing import Any
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import Engine, text
from sqlalchemy.exc import NoResultFound

from ..component_catalog_store import resolve_single_active_location_connection
from ..public import routes as public_routes
from ..workflow import derive_admin_status
from ..workflow_snapshot import build_snapshot
from ..workflow_store import load_draft_connection
from .auth import require_api_scope

bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

CHANNEL_TO_PROFILE = {'cafeteria': 'staff_guest', 'patienten': 'patient'}
API_CACHE_CONTROL = 'public, max-age=60, stale-if-error=86400'
_ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')


def _error(code: str, detail: str, status_code: int):
    response = jsonify({'error': code, 'detail': detail})
    response.headers['Cache-Control'] = 'no-store'
    return response, status_code


def _published_success(payload: dict) -> object:
    response = jsonify(payload)
    response.headers['Cache-Control'] = API_CACHE_CONTROL
    revision = payload.get('revision_id') if isinstance(payload, dict) else None
    if revision:
        response.headers['X-Snapshot-Revision'] = str(revision)
    return response


def status_payload() -> dict:
    today_iso = public_routes.effective_today().isoformat()
    channels: list[dict] = []
    for channel, profile_code in CHANNEL_TO_PROFILE.items():
        snapshot = public_routes.published_snapshot(profile_code)
        if snapshot is None:
            channels.append(
                {
                    'channel': channel,
                    'profile_code': profile_code,
                    'published': False,
                    'revision_id': None,
                    'week_start': None,
                    'week_end': None,
                    'today_state': None,
                },
            )
            continue
        day = next(
            (
                item
                for item in snapshot.get('days', [])
                if item.get('date') == today_iso
            ),
            None,
        )
        channels.append(
            {
                'channel': channel,
                'profile_code': profile_code,
                'published': True,
                'revision_id': snapshot.get('revision_id'),
                'week_start': snapshot.get('week_start'),
                'week_end': snapshot.get('week_end'),
                'today_state': None if not isinstance(day, dict) else day.get('state'),
            },
        )
    return {
        'service': 'dishboard',
        'api_version': '1.0.0',
        'time': dt.datetime.now(ZoneInfo('Europe/Zurich')).isoformat(timespec='seconds'),
        'channels': channels,
        'fhir': {'version': '5.0.0', 'base_path': '/fhir', 'metadata': '/fhir/metadata'},
        'docs': {'openapi': '/api/v1/openapi.json', 'swagger_ui': '/api/v1/docs'},
    }


def _day_payload(profile: str, requested_date: str, snapshot: dict | None) -> dict | None:
    if snapshot is None:
        return None
    for item in snapshot.get('days', []):
        if item.get('date') == requested_date:
            res = dict(snapshot)
            res.update(
                {
                    'channel': next(
                        channel
                        for channel, profile_code in CHANNEL_TO_PROFILE.items()
                        if profile_code == profile
                    ),
                    'profile_code': profile,
                    'revision_id': snapshot.get('revision_id'),
                    'date': requested_date,
                    'day': item,
                },
            )
            return res
    return None


def list_weeks(engine: Engine, profile_code: str) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        location_id = resolve_single_active_location_connection(connection)
        rows = connection.execute(
            text(
                '''
                SELECT w.week_start, w.title, w.workflow_state
                FROM cafeteria.menu_weeks w
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                WHERE w.location_id=:location_id AND p.code=:profile_code
                ORDER BY w.week_start DESC, w.id DESC
                LIMIT 12
                '''
            ),
            {'location_id': location_id, 'profile_code': profile_code},
        ).mappings().all()
    return [
        {
            'week_start': row['week_start'].isoformat(),
            'week_end': (row['week_start'] + dt.timedelta(days=6)).isoformat(),
            'title': row['title'] or '',
            'workflow_state': str(row['workflow_state']),
            'status': derive_admin_status(engine, profile_code, row['week_start']),
        }
        for row in rows
    ]


def _week_start(raw: str) -> dt.date | None:
    if _ISO_DATE.fullmatch(raw) is None:
        return None
    try:
        parsed = dt.date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoweekday() == 1 else None


def _preview_revision(profile_code: str, week_start: dt.date) -> str:
    prefix = 'PAT' if profile_code == 'patient' else 'CAF'
    iso_calendar = week_start.isocalendar()
    return f'{prefix}-{iso_calendar.year}-KW{iso_calendar.week:02d}-R1'


@bp.before_request
def reject_query_parameters():
    if request.query_string:
        return _error(
            'query_parameters_not_allowed',
            'Query-Parameter sind in der API nicht erlaubt.',
            400,
        )


@bp.get('/status')
def status():
    response = jsonify(status_payload())
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/keys/me')
@require_api_scope('')
def key_identity():
    identity = g.api_key
    return jsonify(
        {
            'label': identity.label,
            'scopes': list(identity.scopes),
            'expires_at': (
                identity.expires_at.isoformat() if identity.expires_at is not None else None
            ),
            'public_id': identity.public_id,
        }
    )


@bp.get('/weeks/<any(cafeteria, patienten):channel>')
@require_api_scope('preview.read')
def weeks(channel: str):
    profile = CHANNEL_TO_PROFILE[channel]
    return jsonify({'channel': channel, 'weeks': list_weeks(_database(), profile)})


@bp.get('/weeks/<any(cafeteria, patienten):channel>/<date>/preview')
@require_api_scope('preview.read')
def weeks_preview(channel: str, date: str):
    week_start = _week_start(date)
    if week_start is None:
        return _error(
            'invalid_week_start',
            'Der Wochenbeginn muss ein Montag im Format YYYY-MM-DD sein.',
            400,
        )
    profile = CHANNEL_TO_PROFILE[channel]
    try:
        with _database().connect() as connection:
            draft = load_draft_connection(connection, profile, week_start)
    except NoResultFound:
        return _error('week_not_found', 'Die angeforderte Woche wurde nicht gefunden.', 404)
    snapshot = build_snapshot(profile, draft, _preview_revision(profile, week_start))
    response = jsonify(snapshot)
    response.headers['X-Draft-Row-Version'] = str(draft['row_version'])
    return response


def _database() -> Engine:
    return current_app.extensions['cafeteria_db']


@bp.get('/published/<any(cafeteria, patienten):channel>')
def published_channel(channel: str):
    profile = CHANNEL_TO_PROFILE.get(channel)
    if profile is None:
        return _error('invalid_channel', 'Unbekannter Kanal.', 404)
    snapshot = public_routes.published_snapshot(profile)
    if snapshot is None:
        return _error(
            'no_published_menu',
            'Kein publizierter Menüplan für diesen Kanal.',
            404,
        )
    return _published_success(snapshot)


@bp.get('/published/<any(cafeteria, patienten):channel>/today')
def published_today(channel: str):
    profile = CHANNEL_TO_PROFILE.get(channel)
    if profile is None:
        return _error('invalid_channel', 'Unbekannter Kanal.', 404)
    snapshot = public_routes.published_snapshot(profile)
    today_iso = public_routes.effective_today().isoformat()
    payload = _day_payload(profile, today_iso, snapshot)
    if payload is None:
        return _error(
            'no_published_menu',
            'Kein publizierter Menüplan für diesen Kanal.',
            404,
        )
    return _published_success(payload)


@bp.get('/published/<any(cafeteria, patienten):channel>/days/<date>')
def published_days(channel: str, date: str):
    profile = CHANNEL_TO_PROFILE.get(channel)
    if profile is None:
        return _error('invalid_channel', 'Unbekannter Kanal.', 404)
    try:
        requested_date = dt.date.fromisoformat(date).isoformat()
    except ValueError:
        return _error(
            'invalid_date',
            'Das Datum muss im Format YYYY-MM-DD vorliegen.',
            400,
        )
    try:
        snapshot = public_routes.active_snapshot(
            current_app.extensions['cafeteria_db'],
            profile,
            requested_date,
            last_good_dir=current_app.config['LAST_GOOD_DIR'],
        )
    except ValueError:
        return _error(
            'no_published_menu',
            'Kein publizierter Menüplan für dieses Datum.',
            404,
        )
    payload = _day_payload(profile, requested_date, snapshot)
    if payload is None:
        return _error(
            'no_published_menu',
            'Kein publizierter Menüplan für dieses Datum.',
            404,
        )
    return _published_success(payload)
