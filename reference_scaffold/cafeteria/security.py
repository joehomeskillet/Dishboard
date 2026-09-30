from __future__ import annotations

import hmac
import secrets

from flask import g, session

from .errors import FormStale


def csrf_token() -> str:
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_hex(32)
        session['_csrf_token'] = token
    return token


def validate_csrf(candidate: str | None) -> None:
    expected = session.get('_csrf_token')
    if not expected or not candidate or not hmac.compare_digest(expected, candidate):
        g.eh_mutation_state = 'not_started'
        raise FormStale()
