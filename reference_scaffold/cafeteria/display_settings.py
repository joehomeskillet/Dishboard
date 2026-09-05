"""Global admin presentation; settings retains the last actor/time, not an audit history."""
from __future__ import annotations

import json

from sqlalchemy import Engine, text

ADMIN_DENSITIES = ('compact', 'comfortable')
DEFAULT_ADMIN_DENSITY = 'compact'


def get_admin_density(engine: Engine) -> str:
    with engine.connect() as connection:
        value = connection.execute(text("""
            SELECT setting_value FROM cafeteria.settings
            WHERE location_id IS NULL AND profile_id IS NULL AND setting_key='admin_density'
        """)).scalar_one_or_none()
    return value if isinstance(value, str) and value in ADMIN_DENSITIES else DEFAULT_ADMIN_DENSITY


def set_admin_density(engine: Engine, actor_id: int, authz_version: int, value: str) -> None:
    if not isinstance(value, str) or value not in ADMIN_DENSITIES:
        raise ValueError('Bitte Kompakt oder Komfortabel auswählen.')
    if type(actor_id) is not int or actor_id <= 0 or type(authz_version) is not int or authz_version <= 0:
        raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
    with engine.begin() as connection:
        saved = connection.execute(text("""
            INSERT INTO cafeteria.settings(location_id, profile_id, setting_key, setting_value, updated_by)
            SELECT NULL, NULL, 'admin_density', CAST(:value AS jsonb), u.id
            FROM cafeteria.users u
            WHERE u.id=:actor_id AND u.authz_version=:authz_version AND u.disabled_at IS NULL
              AND EXISTS (
                SELECT 1 FROM cafeteria.user_role_cache r
                JOIN cafeteria.application_roles a ON a.role_code=r.role_code AND a.active
                WHERE r.user_id=u.id AND r.role_code='Cafeteria.Admin'
              )
            ON CONFLICT (location_id, profile_id, setting_key) DO UPDATE
            SET setting_value=EXCLUDED.setting_value, updated_by=EXCLUDED.updated_by,
                updated_at=clock_timestamp()
            RETURNING id
        """), {'actor_id': actor_id, 'authz_version': authz_version, 'value': json.dumps(value)}).scalar_one_or_none()
        if saved is None:
            raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
