"""Real PostgreSQL role, immutable assets, history and atomic brand activation."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier

import pytest
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from cafeteria.branding import (
    SETTING_KEY, BrandingConflictError, BrandingStateError, active_branding,
    change_branding, public_revision, read_branding,
)
from cafeteria.branding_assets import LogoValidationError, load_logo, normalize_logo
from cafeteria.branding_config import BrandingValidationError, default_config, validate_config
from test_admin_workflow_routes import APP_PASSWORD, _login, app, database_engine  # noqa: F401


def _actor(application, engine):
    client, actor = _login(application, engine, ['Cafeteria.Admin'])
    with client.session_transaction() as session:
        return actor, session['authz_version']


def _png(size=(40, 20)):
    output = BytesIO()
    Image.new('RGBA', size, (120, 20, 60, 255)).save(output, format='PNG')
    return output.getvalue()


def test_asset_and_draft_activation_restore_are_atomic_with_runtime_role(app, database_engine):  # noqa: F811
    actor, authz = _actor(app, database_engine)
    logo = normalize_logo(_png())
    runtime = create_engine(database_engine.url.set(username='cafeteria_app', password=APP_PASSWORD), poolclass=NullPool)
    try:
        with runtime.connect() as connection:
            assert read_branding(connection)['version'] == 0
            assert connection.execute(text('SELECT count(*) FROM cafeteria.settings WHERE setting_key=:key'), {'key': SETTING_KEY}).scalar_one() == 0
        config = {**default_config(), 'logo_sha256': logo.sha256, 'font_body': 'carlito'}
        saved = change_branding(runtime, actor, authz, 0, 'save', name='Herbst', config=config, logo=logo)
        with runtime.connect() as connection:
            assert active_branding(connection).id == 1
            assert load_logo(connection, logo.sha256) == logo
        with pytest.raises(LookupError):
            public_revision(saved, 2)
        active = change_branding(runtime, actor, authz, 1, 'activate', revision_id=2)
        assert public_revision(active, 2).config == config
        assert active['revisions'][1]['activated_by'] == actor
        reset = change_branding(runtime, actor, authz, 2, 'reset')
        assert reset['active_revision'] == 2 and reset['revisions'][2]['config'] == default_config()
        changed = change_branding(runtime, actor, authz, 3, 'activate', revision_id=3)
        restored = change_branding(runtime, actor, authz, 4, 'restore', revision_id=2)
        assert restored['active_revision'] == 3
        assert restored['revisions'][3]['restored_from'] == 2
        assert restored['revisions'][:3] == changed['revisions']
        assert public_revision(restored, 2).config == config  # historic assets remain public
        for statement in ('UPDATE cafeteria.branding_assets SET width=1', 'DELETE FROM cafeteria.branding_assets'):
            with runtime.begin() as connection, pytest.raises(DBAPIError):
                connection.execute(text(statement))
    finally:
        runtime.dispose()


@pytest.mark.parametrize('change', ['version', 'disabled', 'role'])
def test_current_authority_is_checked_before_any_write(app, database_engine, change):  # noqa: F811
    actor, authz = _actor(app, database_engine)
    with database_engine.begin() as connection:
        if change == 'version':
            authz += 1
        elif change == 'disabled':
            connection.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor'), {'actor': actor})
        else:
            connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor'), {'actor': actor})
    logo = normalize_logo(_png())
    with pytest.raises(PermissionError):
        change_branding(database_engine, actor, authz, 0, 'save', name='Nicht speichern',
                        config={**default_config(), 'logo_sha256': logo.sha256}, logo=logo)
    with database_engine.connect() as connection:
        assert read_branding(connection)['version'] == 0
        assert connection.execute(text('SELECT count(*) FROM cafeteria.branding_assets')).scalar_one() == 0


def test_concurrent_first_save_has_one_winner(app, database_engine):  # noqa: F811
    actor, authz = _actor(app, database_engine)
    barrier = Barrier(2)
    def save(name):
        barrier.wait(timeout=10)
        try:
            change_branding(database_engine, actor, authz, 0, 'save', name=name, config=default_config())
            return name
        except BrandingConflictError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(save, ['Erste', 'Zweite']))
    assert results.count('conflict') == 1
    with database_engine.connect() as connection:
        document = read_branding(connection)
        assert document['version'] == 1 and len(document['revisions']) == 2


def test_failure_preserves_active_and_rolls_back_new_asset(app, database_engine):  # noqa: F811
    actor, authz = _actor(app, database_engine)
    saved = change_branding(database_engine, actor, authz, 0, 'save', name='Gut', config=default_config())
    logo = normalize_logo(_png())
    with pytest.raises(BrandingConflictError):
        change_branding(database_engine, actor, authz, 0, 'save', name='Veraltet',
                        config={**default_config(), 'logo_sha256': logo.sha256}, logo=logo)
    with pytest.raises(LookupError):
        change_branding(database_engine, actor, authz, 1, 'save', name='Fehlt',
                        config={**default_config(), 'logo_sha256': 'a' * 64})
    with database_engine.connect() as connection:
        assert read_branding(connection) == saved
        assert connection.execute(text('SELECT count(*) FROM cafeteria.branding_assets')).scalar_one() == 0


@pytest.mark.parametrize('value', [None, {}, {'schema_version': 999}])
def test_corrupt_state_is_not_replaced(app, database_engine, value):  # noqa: F811
    actor, authz = _actor(app, database_engine)
    with database_engine.begin() as connection:
        connection.execute(text('INSERT INTO cafeteria.settings(setting_key,setting_value) VALUES (:key,CAST(:value AS jsonb))'),
                           {'key': SETTING_KEY, 'value': json.dumps(value)})
    with pytest.raises(BrandingStateError):
        change_branding(database_engine, actor, authz, 0, 'reset')
    with database_engine.connect() as connection:
        assert connection.execute(text('SELECT setting_value FROM cafeteria.settings WHERE setting_key=:key'), {'key': SETTING_KEY}).scalar_one() == value


@pytest.mark.parametrize('data', [b'', b'<svg onload="alert(1)"></svg>', b'x' * (1024 * 1024 + 1)])
def test_logo_rejects_non_images_and_oversized_files(data):
    with pytest.raises(LogoValidationError):
        normalize_logo(data)


def test_logo_dimensions_animation_and_metadata_are_bounded():
    with pytest.raises(LogoValidationError):
        normalize_logo(_png((2049, 1)))
    output = BytesIO()
    Image.new('RGB', (10, 10)).save(output, format='PNG', save_all=True,
                                  append_images=[Image.new('RGB', (10, 10), 'white')])
    with pytest.raises(LogoValidationError):
        normalize_logo(output.getvalue())
    logo = normalize_logo(_png())
    assert normalize_logo(logo.png) == logo
    with Image.open(BytesIO(logo.png)) as clean:
        assert clean.info == {} and clean.format == 'PNG'


@pytest.mark.parametrize('key,value', [('primary', 'url(https://example.invalid)'),
                                     ('text', '#ffffff'), ('font_body', 'https://example.invalid/font'),
                                     ('logo_sha256', '../file')])
def test_brand_config_rejects_css_external_resources_and_unreadable_colors(key, value):
    with pytest.raises(BrandingValidationError):
        validate_config({**default_config(), key: value})
