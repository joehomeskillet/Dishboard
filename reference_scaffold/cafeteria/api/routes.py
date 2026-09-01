from flask import Blueprint, jsonify, request

from ..public.routes import published_snapshot

bp = Blueprint('api', __name__, url_prefix='/api/v1/published')


def error_response(payload: dict[str, str], status_code: int):
    response = jsonify(payload)
    response.headers['Cache-Control'] = 'no-store'
    return response, status_code


def response_for(profile_code: str):
    if request.query_string:
        return error_response({'error': 'query_parameters_not_allowed'}, 400)
    snapshot = published_snapshot(profile_code)
    if not snapshot:
        return error_response({'error': 'no_published_menu', 'profile': profile_code}, 404)
    response = jsonify(snapshot)
    response.headers['Cache-Control'] = 'public, max-age=60, stale-if-error=86400'
    response.headers['X-Snapshot-Revision'] = snapshot.get('revision_id', '')
    return response


@bp.get('/cafeteria')
def cafeteria():
    return response_for('staff_guest')


@bp.get('/patienten')
def patienten():
    return response_for('patient')
