from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import current_app, g, jsonify, make_response, request

from ..api_keys import authenticate_api_key

_BEARER_CHALLENGE = 'Bearer realm="dishboard-api"'


def _unauthorized():
    response = jsonify(
        {
            'error': 'unauthorized',
            'detail': 'Ein gültiger API-Schlüssel ist erforderlich.',
        }
    )
    response.status_code = 401
    response.headers['WWW-Authenticate'] = _BEARER_CHALLENGE
    response.headers['Cache-Control'] = 'no-store'
    return response


def _insufficient_scope():
    response = jsonify(
        {
            'error': 'insufficient_scope',
            'detail': 'Der API-Schlüssel hat nicht den erforderlichen Scope.',
        }
    )
    response.status_code = 403
    response.headers['Cache-Control'] = 'no-store'
    return response


def require_api_scope(scope: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any):
            authorization = request.headers.get('Authorization')
            parts = authorization.split(' ') if authorization is not None else []
            if len(parts) != 2 or parts[0] != 'Bearer' or not parts[1]:
                return _unauthorized()
            identity = authenticate_api_key(
                current_app.extensions['cafeteria_db'],
                parts[1],
            )
            if identity is None:
                return _unauthorized()
            if scope and scope not in identity.scopes:
                return _insufficient_scope()
            g.api_key = identity
            response = make_response(function(*args, **kwargs))
            response.mimetype = 'application/json'
            response.headers['Cache-Control'] = 'no-store'
            return response

        return wrapped

    return decorator
