from __future__ import annotations

from functools import wraps

from flask import abort, session

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
    for role in roles if roles is not None else session.get('roles', []):
        result |= ROLE_CAPABILITIES.get(role, set())
    return result


def require_capability(capability: str):
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if not session.get('user'):
                abort(401)
            allowed = capabilities()
            if '*' not in allowed and capability not in allowed:
                abort(403)
            return function(*args, **kwargs)
        return wrapped
    return decorator
