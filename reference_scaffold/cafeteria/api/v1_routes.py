from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, current_app, request

from ..public import routes as public_routes

bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

CHANNEL_TO_PROFILE = {'cafeteria': 'staff_guest', 'patienten': 'patient'}
API_CACHE_CONTROL = 'public, max-age=60, stale-if-error=86400'


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
