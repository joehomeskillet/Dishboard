"""Global admin presentation; settings retains the last actor/time, not an audit history."""
from __future__ import annotations

import json

from sqlalchemy import Engine, text

ADMIN_DENSITIES = ('compact', 'comfortable')
DEFAULT_ADMIN_DENSITY = 'compact'
ADMIN_DISPLAY_CHOICES = {
    'admin_density': ADMIN_DENSITIES,
    'admin_font_size': ('normal', 'large'),
    'admin_content_width': ('contained', 'full'),
    'admin_menu_images': ('show', 'hide'),
}
DEFAULT_ADMIN_DISPLAY = {key: choices[0] for key, choices in ADMIN_DISPLAY_CHOICES.items()}


def get_admin_display(engine: Engine) -> dict[str, str]:
    values = DEFAULT_ADMIN_DISPLAY.copy()
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT setting_key, setting_value FROM cafeteria.settings
            WHERE location_id IS NULL AND profile_id IS NULL
              AND setting_key IN ('admin_density', 'admin_font_size', 'admin_content_width', 'admin_menu_images')
        """))
        for key, value in rows:
            if isinstance(value, str) and value in ADMIN_DISPLAY_CHOICES[key]:
                values[key] = value
    return values


def get_admin_density(engine: Engine) -> str:
    return get_admin_display(engine)['admin_density']


def set_admin_display(engine: Engine, actor_id: int, authz_version: int, values: dict[str, str]) -> None:
    if set(values) != set(ADMIN_DISPLAY_CHOICES) or any(
        not isinstance(value, str) or value not in ADMIN_DISPLAY_CHOICES[key]
        for key, value in values.items()
    ):
        raise ValueError('Darstellung enthält eine ungültige Auswahl.')
    _save_admin_display(engine, actor_id, authz_version, values)


def set_admin_density(engine: Engine, actor_id: int, authz_version: int, value: str) -> None:
    if not isinstance(value, str) or value not in ADMIN_DENSITIES:
        raise ValueError('Bitte Kompakt oder Komfortabel auswählen.')
    _save_admin_display(engine, actor_id, authz_version, {'admin_density': value})


def _save_admin_display(engine: Engine, actor_id: int, authz_version: int, values: dict[str, str]) -> None:
    if type(actor_id) is not int or actor_id <= 0 or type(authz_version) is not int or authz_version <= 0:
        raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
    with engine.begin() as connection:
        saved = connection.execute(text("""
            INSERT INTO cafeteria.settings(location_id, profile_id, setting_key, setting_value, updated_by)
            SELECT NULL, NULL, setting.key, setting.value, u.id
            FROM cafeteria.users u CROSS JOIN jsonb_each(CAST(:values AS jsonb)) setting
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
        """), {'actor_id': actor_id, 'authz_version': authz_version, 'values': json.dumps(values)}).all()
        if len(saved) != len(values):
            raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
