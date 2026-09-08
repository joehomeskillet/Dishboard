"""Schema18 parity, forward migration, immutable grants and backup inclusion."""
from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import text

from cafeteria import db as database
from test_component_metadata_master_lock_db import PERMISSIONS, SCHEMA, pg16  # noqa: F401


@pytest.mark.parametrize('source', ['migration', 'schema'])
def test_branding_asset_install_and_permissions_reapply(pg16, source):  # noqa: F811
    if source == 'migration':
        database.run_migrations(pg16, SCHEMA)
    else:
        database._execute_script(pg16, str(SCHEMA))
    for _ in range(2):
        database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        permissions = connection.execute(text('''
            SELECT has_table_privilege('cafeteria_app', 'cafeteria.branding_assets', 'SELECT'),
                   has_table_privilege('cafeteria_app', 'cafeteria.branding_assets', 'INSERT'),
                   has_table_privilege('cafeteria_app', 'cafeteria.branding_assets', 'UPDATE,DELETE,TRUNCATE'),
                   has_table_privilege('cafeteria_backup', 'cafeteria.branding_assets', 'SELECT'),
                   has_table_privilege('cafeteria_backup', 'cafeteria.branding_assets', 'INSERT,UPDATE,DELETE,TRUNCATE'),
                   has_table_privilege('cafeteria_auth_issuer', 'cafeteria.branding_assets', 'SELECT,INSERT,UPDATE,DELETE'),
                   pg_get_serial_sequence('cafeteria.branding_assets', 'sha256')
        ''')).one()
        assert tuple(permissions) == (True, True, False, True, False, False, None)


def test_v17_forward_migration_preserves_settings_and_has_recorded_checksum(pg16):  # noqa: F811
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 17:
            database._execute_migration(pg16, migration)
    with pg16.begin() as connection:
        connection.execute(text('''
            INSERT INTO cafeteria.settings(setting_key,setting_value)
            VALUES ('admin_density','"comfortable"'), ('print_templates.v1.patient',CAST(:value AS jsonb))
        '''), {'value': '{"unchanged":true}'})
        before = connection.execute(text('SELECT to_jsonb(s) FROM cafeteria.settings s ORDER BY id')).scalars().all()
    database.run_migrations(pg16, SCHEMA)
    with pg16.connect() as connection:
        assert connection.execute(text('SELECT to_jsonb(s) FROM cafeteria.settings s ORDER BY id')).scalars().all() == before
        assert connection.execute(text('SELECT count(*) FROM cafeteria.branding_assets')).scalar_one() == 0
        assert connection.execute(text('SELECT name,checksum_sha256 FROM cafeteria.schema_migrations WHERE version=18')).one() == (
            '0015_v17_to_v18.sql', hashlib.sha256(next(item.path for item in plan if item.version == 18).read_bytes()).hexdigest())
        assert connection.execute(text('SELECT version FROM cafeteria.schema_migrations ORDER BY version')).scalars().all() == list(range(4, 25))
