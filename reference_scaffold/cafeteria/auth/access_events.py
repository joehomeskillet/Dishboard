"""Bounded authentication outcomes through the separate issuer connection."""
from __future__ import annotations

from uuid import UUID, uuid4

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from .service import AuthorizationState


class AccessEventUnavailable(RuntimeError):
    """No durable authentication decision can be confirmed."""


def record_access_event(
    provider: str, action: str, reason: str | None = None,
    identity: AuthorizationState | None = None,
) -> UUID:
    """Only server-owned fields; retries retain the event UUID and exact tuple."""
    if provider not in ('local', 'entra') or action not in (
        'auth.login.accepted', 'auth.login.rejected', 'auth.login.unavailable',
        'auth.logout.requested', 'auth.frontchannel.requested',
    ):
        raise ValueError('Invalid authentication event.')
    if (action == 'auth.login.rejected' and (
            reason not in ('credentials', 'role', 'flow', 'throttled') or identity is not None)
        or action == 'auth.login.unavailable' and (reason != 'unavailable' or identity is not None)
        or action in ('auth.login.accepted', 'auth.logout.requested', 'auth.frontchannel.requested')
            and reason is not None
        or action == 'auth.login.accepted' and identity is None):
        raise ValueError('Invalid authentication outcome.')
    if identity is not None and (
        not isinstance(identity, AuthorizationState) or identity.auth_provider != provider
        or type(identity.user_id) is not int or identity.user_id <= 0
        or type(identity.authz_version) is not int or identity.authz_version <= 0
    ):
        raise ValueError('Invalid authentication identity.')
    event = uuid4()
    params = dict(event=str(event), provider=provider, action=action, reason=reason,
                  actor=identity.user_id if identity else None,
                  version=identity.authz_version if identity else None)
    engine = current_app.extensions.get('cafeteria_auth_issuer_db')
    if engine is not None:
        for attempt in range(2):
            try:
                with engine.begin() as connection:
                    recorded = connection.execute(text('''
                        SELECT cafeteria.record_auth_access_v25(
                            CAST(:event AS uuid),:provider,:action,:reason,:actor,:version)
                    '''), params).scalar_one()
                if str(recorded) == str(event):
                    return event
                break
            except DBAPIError as error:
                if attempt == 0 and (
                    error.connection_invalidated
                    or getattr(error.orig, 'sqlstate', None) in ('40001', '40P01')
                ):
                    continue
                break
            except SQLAlchemyError:
                break
    # Never log the driver exception, submitted values, claims, or session state.
    current_app.logger.warning('Authentication decision audit unavailable.')
    raise AccessEventUnavailable('Anmeldung vorübergehend nicht verfügbar.') from None
