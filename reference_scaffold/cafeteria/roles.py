from __future__ import annotations

from functools import wraps

from flask import abort, current_app, g, session

from .auth.service import load_user_authorization

ROLE_CAPABILITIES = {
    'Cafeteria.Editor': {
        'draft.read', 'draft.write', 'csv.validate', 'csv.import', 'csv.export', 'preview.read',
    },
    'Cafeteria.Publisher': {
        'draft.read', 'draft.write', 'csv.validate', 'csv.import', 'csv.export', 'preview.read',
        'publication.validate', 'publication.publish', 'publication.withdraw', 'audit.read',
    },
    'Cafeteria.Admin': {'*'},
}


def capabilities(roles: list[str] | None = None) -> set[str]:
    result: set[str] = set()
    authoritative_roles = roles if roles is not None else getattr(g, 'auth_roles', ())
    for role in authoritative_roles:
        result |= ROLE_CAPABILITIES.get(role, set())
    return result


def require_capability(capability: str):
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            session_user = session.get('user')
            session_authz_version = session.get('authz_version')
            if not isinstance(session_user, dict) or not isinstance(session_user.get('id'), int):
                abort(401)
            if not isinstance(session_authz_version, int):
                session.clear()
                abort(401)
            authorization = load_user_authorization(
                current_app.extensions['cafeteria_db'],
                session_user['id'],
            )
            if authorization is None or authorization.authz_version != session_authz_version:
                session.clear()
                abort(401)
            g.auth_user = authorization
            g.auth_roles = authorization.roles
            allowed = capabilities()
            if '*' not in allowed and capability not in allowed:
                abort(403)
            return function(*args, **kwargs)
        return wrapped
    return decorator
