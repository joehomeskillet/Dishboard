from __future__ import annotations

import hmac
import secrets

from flask import abort, session


def csrf_token() -> str:
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def validate_csrf(candidate: str | None) -> None:
    expected = session.get('_csrf_token')
    if not expected or not candidate or not hmac.compare_digest(expected, candidate):
        abort(400, description='CSRF-Prüfung fehlgeschlagen.')
