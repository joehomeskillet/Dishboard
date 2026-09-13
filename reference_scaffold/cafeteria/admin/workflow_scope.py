"""Existing scoped forms, bound to their original actor/authz and location."""
from __future__ import annotations

import hashlib
import hmac
import re
import base64
import json
from dataclasses import asdict, replace
from datetime import date
from time import time
from typing import Literal, cast

from flask import abort, current_app, request, session

from ..component_catalog_store import (
    AdminScope, ComponentCatalogConfigurationError, ComponentNotFoundError,
    resolve_single_active_location_connection,
)
from ..security import csrf_token, validate_csrf
from ..menu_template_binding import (
    TemplateContext, lock_templates, require_empty_template_target,
    require_template_source, template_public_id,
)
from ..workflow_write_context import WriteConflictError, write_transaction


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
                 copy_source: tuple[date, date, int] | None = None,
                 template_context: str = '') -> str:
    raw = csrf_token()
    context = '-' if copy_source is None else ':'.join(str(value) for value in copy_source)
    if template_context:
        context = 'proposal-' + hashlib.sha256(template_context.encode()).hexdigest()
    digest = _csrf_digest(scope, profile, purpose, raw, context)
    return (f'v2.{raw}.{purpose}.{scope.actor_id}.{scope.expected_authz_version}.'
            f'{scope.location_id}.{context}.{digest}')


def _validated(profile: str, purposes: set[str], *, check_current: bool = True) -> tuple[AdminScope, str]:
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
    if check_current and current != original:
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


def _template_signature(encoded: str) -> str:
    secret = current_app.secret_key
    if not isinstance(secret, (str, bytes)) or not secret:
        abort(503, description='Formularsignatur ist nicht konfiguriert.')
    key = secret.encode() if isinstance(secret, str) else secret
    return hmac.new(key, b'dishboard-menu-proposal-v1\0' + encoded.encode(), hashlib.sha256).hexdigest()


def _sign_template_context(context: TemplateContext) -> str:
    # Separate domain from scoped CSRF: this URL-safe token never contains a CSRF secret.
    encoded = base64.urlsafe_b64encode(json.dumps(asdict(context), sort_keys=True,
        separators=(',', ':')).encode()).decode().rstrip('=')
    return f't1.{encoded}.{_template_signature(encoded)}'


def read_template_context(token: str, *, target: bool) -> TemplateContext:
    """Verify transport only; callers preserve expired/stale expectations for redisplay."""
    if type(token) is not str or len(token) > 4096:
        abort(400, description='Vorschlagskontext ist ungültig.')
    parts = token.split('.')
    if (len(parts) != 3 or parts[0] != 't1'
            or not re.fullmatch(r'[A-Za-z0-9_-]+', parts[1])
            or not re.fullmatch(r'[0-9a-f]{64}', parts[2])
            or not hmac.compare_digest(parts[2], _template_signature(parts[1]))):
        abort(400, description='Vorschlagssignatur ist ungültig.')
    try:
        data = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
        context = TemplateContext(**data)
        if any(type(value) is not int or value <= 0 for value in (
                context.actor_id, context.authz_version, context.location_id, context.expires_at)):
            raise ValueError
        if (not template_public_id(context.template_public_id)
                or not isinstance(context.expected_updated_at, str)):
            raise ValueError
        template_public_id(context.recipe_public_id)
        if target:
            week = date.fromisoformat(context.week or '')
            day = date.fromisoformat(context.day or '')
            if (context.profile not in ('patient', 'staff_guest') or week.weekday() != 0
                    or (day - week).days not in range(7) or context.option not in ('MENU_1', 'VEGGIE')
                    or context.meal not in (('LUNCH', 'DINNER') if context.profile == 'patient' else ('LUNCH',))
                    or type(context.expected_item_row_version) is not int
                    or context.expected_item_row_version != 0):
                raise ValueError
        elif any(value is not None for value in (
                context.profile, context.week, context.day, context.meal, context.option,
                context.expected_item_row_version)):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        abort(400, description='Vorschlagskontext ist ungültig.')
    return context


def issue_template_source(scope: AdminScope, public_id: str) -> str:
    """Fresh planning entry only; a redisplay must keep its existing source token."""
    public_id = template_public_id(public_id) or ''
    with write_transaction(current_app.extensions['cafeteria_db'], scope) as connection:
        row = next(iter(lock_templates(connection, scope, [public_id]).values()))
        context = TemplateContext(scope.actor_id, int(scope.expected_authz_version or 0),
            scope.location_id, public_id, row['updated_at'].isoformat(),
            row['recipe_public_id'], int(time()) + 3600)
        require_template_source(row, scope, context)
    return _sign_template_context(context)


def bind_template_target(source_token: str, scope: AdminScope, week: date,
                         day: str, meal: str, option: str) -> str:
    """After planning POST CSRF validation, extend the original source by its checked target."""
    from .workflow_routes import _raster
    source = read_template_context(source_token, target=False)
    source.require_source(scope)
    _raster(scope.profile_code, week, day, meal, option)
    target = replace(source, profile=scope.profile_code, week=week.isoformat(),
                     day=day, meal=meal, option=option, expected_item_row_version=0)
    validate_template_target(target, scope)
    return _sign_template_context(target)


def validate_template_target(context: TemplateContext, scope: AdminScope) -> None:
    with write_transaction(current_app.extensions['cafeteria_db'], scope) as connection:
        context.require_source(scope)
        try:
            row = next(iter(lock_templates(connection, scope, [context.template_public_id]).values()))
        except ComponentNotFoundError as error:
            raise WriteConflictError('Die ursprüngliche Gerichtvorlage ist nicht mehr verfügbar.') from error
        require_template_source(row, scope, context)
        require_empty_template_target(connection, scope, context)


def validate_menu_csrf(profile: str) -> AdminScope:
    """Keep original authority available to a rejected menu form without re-signing it."""
    scope, context = _validated(profile, {'overview', 'menu'}, check_current=False)
    token = request.form.get('template_context', '')
    expected = 'proposal-' + hashlib.sha256(token.encode()).hexdigest() if token else '-'
    if context != expected:
        abort(400, description='Formularkontext ist ungültig.')
    return scope
