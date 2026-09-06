from __future__ import annotations

from flask import Blueprint, jsonify, make_response, render_template, request

bp = Blueprint('api_docs', __name__, url_prefix='/api/v1')

CSP_DOCS = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; frame-ancestors 'none'"
)


@bp.before_request
def reject_query_parameters():
    if request.query_string:
        response = jsonify({'error': 'query_parameters_not_allowed'})
        response.status_code = 400
        response.headers['Cache-Control'] = 'no-store'
        return response
    return None


def _document() -> dict:
    try:
        from .openapi import build_openapi
    except ImportError:  # WP-A1 noch nicht integriert
        return {
            'openapi': '3.1.0',
            'info': {'title': 'Dishboard Menü-API', 'version': '1.0.0'},
            'paths': {},
        }
    return build_openapi()


@bp.get('/openapi.json')
def openapi_json():
    response = jsonify(_document())
    response.headers['Cache-Control'] = 'public, max-age=300'
    return response


@bp.get('/docs')
def docs():
    response = make_response(render_template('api/docs.html'))
    response.headers['Content-Security-Policy'] = CSP_DOCS
    return response
