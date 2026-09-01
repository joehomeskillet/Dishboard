from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from ..db import SCHEMA_VERSION, validate_database

bp = Blueprint('health', __name__, url_prefix='/health')


@bp.get('/live')
def live():
    return jsonify({'status': 'ok'}), 200


@bp.get('/ready')
def ready():
    try:
        engine = current_app.extensions['cafeteria_db']
        with engine.connect() as connection:
            connection.execute(text('SELECT 1')).scalar_one()
        db_status = validate_database(engine)
        redis_client = current_app.config.get('SESSION_REDIS')
        if redis_client is not None:
            redis_client.ping()
        if not db_status['ready'] or db_status['schema_version'] < SCHEMA_VERSION:
            raise RuntimeError('database_not_ready')
        return jsonify({'status': 'ready', 'database': db_status}), 200
    except Exception as exc:
        return jsonify({'status': 'not_ready', 'reason': type(exc).__name__}), 503
