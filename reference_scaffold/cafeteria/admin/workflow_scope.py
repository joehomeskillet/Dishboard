"""Existing scoped forms, bound to their original actor/authz and location."""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date
from typing import Literal, cast

from flask import abort, current_app, request, session

from ..component_catalog_store import (
    AdminScope, ComponentCatalogConfigurationError, resolve_single_active_location_connection,
)
from ..security import csrf_token, validate_csrf


def _scope(profile: str) -> AdminScope:
    user = session.get('user') or {}
    actor = user.get('id')
    authz = session.get('authz_version')
    if type(actor) is not int or actor <= 0 or type(authz) is not int or authz <= 0:
        abort(401)
    try:
        with current_app.extensions['cafeteria_db'].connect() as connection:
            location = resolve_single_active_location_connection(connection)
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    return AdminScope(actor, location, cast(Literal['patient', 'staff_guest'], profile), authz)


def _csrf_digest(scope: AdminScope, profile: str, purpose: str, raw: str, context: str = '-') -> str:
    secret = current_app.secret_key
    if not isinstance(secret, (str, bytes)) or not secret:
        abort(503, description='Formularsignatur ist nicht konfiguriert.')
    key = secret.encode('utf-8') if isinstance(secret, str) else secret
    binding = (f'dishboard-admin-v2\0{raw}\0{scope.actor_id}\0{scope.expected_authz_version}'
               f'\0{profile}\0{purpose}\0{scope.location_id}\0{context}')
    return hmac.new(key, binding.encode(), hashlib.sha256).hexdigest()


def _scoped_csrf(profile: str, purpose: str, scope: AdminScope, *,
                 copy_source: tuple[date, date, int] | None = None) -> str:
    raw = csrf_token()
    context = '-' if copy_source is None else ':'.join(str(value) for value in copy_source)
    digest = _csrf_digest(scope, profile, purpose, raw, context)
    return (f'v2.{raw}.{purpose}.{scope.actor_id}.{scope.expected_authz_version}.'
            f'{scope.location_id}.{context}.{digest}')


def _validated(profile: str, purposes: set[str]) -> tuple[AdminScope, str]:
    values = request.form.getlist('_csrf')
    if len(values) != 1 or len(values[0]) > 2048:
        abort(400, description='CSRF-Prüfung fehlgeschlagen.')
    parts = values[0].split('.')
    if len(parts) == 3:
        abort(409, description='Formular ist veraltet. Bitte neu laden.')
    if len(parts) != 8 or parts[0] != 'v2':
        abort(400, description='CSRF-Prüfung fehlgeschlagen.')
    _, raw, purpose, actor, authz, location, context, digest = parts
    validate_csrf(raw)
    if purpose not in purposes:
        abort(400, description='Formularzweck ist ungültig.')
    if any(re.fullmatch(r'[1-9][0-9]{0,18}', value) is None
           or int(value) > 2**63 - 1 for value in (actor, authz, location)):
        abort(400, description='Formularbindung ist ungültig.')
    original = AdminScope(int(actor), int(location), cast(Literal['patient', 'staff_guest'], profile), int(authz))
    current = _scope(profile)
    if not hmac.compare_digest(digest, _csrf_digest(original, profile, purpose, raw, context)):
        abort(409, description='Formularbindung wurde geändert. Bitte neu laden.')
    if current != original:
        abort(409, description='Berechtigung oder aktiver Standort wurde zwischenzeitlich geändert.')
    return original, context


def _validate_scoped_csrf(profile: str, purposes: set[str]) -> AdminScope:
    scope, context = _validated(profile, purposes)
    if context != '-':
        abort(400, description='Formularkontext ist ungültig.')
    return scope


def validate_copy_csrf(profile: str, source: date, target: date) -> tuple[AdminScope, int]:
    scope, context = _validated(profile, {'copy'})
    parts = context.split(':')
    if (len(parts) != 3 or parts[:2] != [source.isoformat(), target.isoformat()]
            or re.fullmatch(r'[1-9][0-9]{0,18}', parts[2]) is None or int(parts[2]) > 2**63 - 1):
        abort(409, description='Kopierquelle wurde geändert. Bitte Formular neu laden.')
    return scope, int(parts[2])
