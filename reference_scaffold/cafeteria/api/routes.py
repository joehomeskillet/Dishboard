from flask import Blueprint, current_app, jsonify, request

from ..db import active_snapshot
from ..public.routes import effective_today

bp = Blueprint('api', __name__, url_prefix='/api/v1/published')


def response_for(profile_code: str):
    if request.args:
        return jsonify({'error': 'query_parameters_not_allowed'}), 400
    snapshot = active_snapshot(
        current_app.extensions['cafeteria_db'],
        profile_code,
        effective_today().isoformat(),
        last_good_dir=current_app.config['LAST_GOOD_DIR'],
    )
    if not snapshot:
        return jsonify({'error': 'no_published_menu', 'profile': profile_code}), 404
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
