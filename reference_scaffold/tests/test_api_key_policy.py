from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria import api_keys, db as database
from cafeteria.api.v1_routes import weeks, weeks_preview
from test_api_keyed import app, database_engines
from test_api_keys_db import ROOT, _create_user

__all__ = ['app', 'database_engines']


def _counts(engine):
    with engine.connect() as connection:
        return tuple(connection.execute(text('''
            SELECT (SELECT count(*) FROM cafeteria.api_keys),
                   (SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE 'api.key_%')
        ''')).one())


def test_python_creation_rejects_invalid_channels_and_expiry_without_mutation(database_engines):
    owner, engine = database_engines
    actor = _create_user(owner, suffix='901', roles=['Cafeteria.Admin'])
    defaults = dict(actor_id=actor, label='Policy', scopes=api_keys.API_KEY_SCOPES,
                    channels=['cafeteria'], expires_at=datetime.now(UTC) + timedelta(days=30))
    before = _counts(owner)
    for channels in ([], ['staff_guest'], ['cafeteria', 'cafeteria'], ['patienten', None], 'cafeteria'):
        with pytest.raises(api_keys.ApiKeyValidationError):
            api_keys.create_api_key(engine, **(defaults | {'channels': channels}))
    for expiry in (None, datetime.now(), datetime.now(UTC) - timedelta(seconds=1),
                   datetime.now(UTC) + timedelta(days=90, seconds=5)):
        with pytest.raises(api_keys.ApiKeyValidationError):
            api_keys.create_api_key(engine, **(defaults | {'expires_at': expiry}))
    assert _counts(owner) == before


def test_exact_ninety_day_boundary_and_normalized_channel_order(database_engines, monkeypatch):
    owner, engine = database_engines
    actor = _create_user(owner, suffix='902', roles=['Cafeteria.Admin'])
    now = datetime.now(UTC)

    class ClockMeta(type):
        def __instancecheck__(cls, instance):
            return isinstance(instance, datetime)

    class Clock(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(api_keys, 'datetime', Clock)
    # datetime instances must still satisfy the validator's datetime type guard.
    expiry = Clock.fromtimestamp((now + timedelta(days=90)).timestamp(), UTC)
    record, _ = api_keys.create_api_key(
        engine, actor_id=actor, label='Boundary', scopes=api_keys.API_KEY_SCOPES,
        channels=['patienten', 'cafeteria'], expires_at=expiry,
    )
    assert record.expires_at == expiry
    assert record.channels == ('cafeteria', 'patienten')
    with pytest.raises(api_keys.ApiKeyValidationError):
        api_keys.create_api_key(
            engine, actor_id=actor, label='Too late', scopes=api_keys.API_KEY_SCOPES,
            channels=['cafeteria'], expires_at=expiry + timedelta(microseconds=1),
        )


def test_database_writer_enforces_channels_and_expiry_and_old_signature_is_gone(database_engines):
    owner, engine = database_engines
    actor = _create_user(owner, suffix='903', roles=['Cafeteria.Admin'])
    _, prefix, digest = api_keys.generate_api_key()
    defaults = {'actor': actor, 'prefix': prefix, 'digest': digest,
                'channels': ['cafeteria'], 'expiry': datetime.now(UTC) + timedelta(days=30)}
    statement = text('''SELECT cafeteria.create_api_key(
        :actor, 'SQL policy', :prefix, :digest, ARRAY['preview.read']::text[],
        :expiry, CAST(:channels AS text[]))''')
    before = _counts(owner)
    for changes in ({'expiry': None}, {'expiry': datetime.now(UTC) - timedelta(seconds=1)},
                    {'expiry': datetime.now(UTC) + timedelta(days=91)}, {'channels': None},
                    {'channels': []}, {'channels': ['cafeteria', 'cafeteria']},
                    {'channels': ['patient']}, {'channels': [None]}):
        with pytest.raises(DBAPIError):
            with engine.begin() as connection:
                connection.execute(statement, defaults | changes)
    with owner.connect() as connection:
        assert connection.execute(text("SELECT to_regprocedure('cafeteria.create_api_key(bigint,text,text,text,text[],timestamptz)')")).scalar_one() is None
    assert _counts(owner) == before


def test_preview_channels_and_aliases_are_enforced_before_loading_drafts(app, database_engines):
    owner, engine = database_engines
    actor = _create_user(owner, suffix='904', roles=['Cafeteria.Admin'])
    app.add_url_rule('/alias/weeks/<channel>', view_func=weeks)
    app.add_url_rule('/alias/weeks/<channel>/<date>/preview', view_func=weeks_preview)
    client = app.test_client()
    for granted in (['cafeteria'], ['patienten'], ['cafeteria', 'patienten']):
        record, token = api_keys.create_api_key(
            engine, actor_id=actor, label=' / '.join(granted), scopes=api_keys.API_KEY_SCOPES,
            channels=granted, expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        headers = {'Authorization': f'Bearer {token}'}
        identity = client.get('/api/v1/keys/me', headers=headers)
        assert identity.get_json()['channels'] == granted
        for channel in ('cafeteria', 'patienten'):
            for prefix in ('/api/v1', '/alias'):
                for suffix in ('', '/2026-08-31/preview'):
                    response = client.get(f'{prefix}/weeks/{channel}{suffix}', headers=headers)
                    assert response.headers['Cache-Control'] == 'no-store'
                    if channel in granted:
                        assert response.status_code == (404 if suffix else 200)
                    else:
                        assert response.status_code == 403
                        assert response.get_json()['error'] == 'insufficient_channel'
        assert api_keys.revoke_api_key(engine, actor_id=actor, public_id=record.public_id)
        assert client.get('/api/v1/weeks/cafeteria', headers=headers).status_code == 401


def test_schema29_migration_preserves_legacy_rights_expiry_and_authentication(database_engines, monkeypatch):
    owner, engine = database_engines
    with owner.begin() as connection:
        connection.execute(text('DROP SCHEMA cafeteria CASCADE'))
    with monkeypatch.context() as patch:
        patch.setattr(database, 'MIGRATION_FILES', database.MIGRATION_FILES[:-1])
        database.run_migrations(owner, ROOT / 'database/schema.sql')
    database._execute_script(owner, str(ROOT / 'database/seed.sql'))
    actor = _create_user(owner, suffix='905', roles=['Cafeteria.Admin'])
    keys = []
    for expiry in (None, datetime.now(UTC) + timedelta(days=180)):
        token, prefix, digest = api_keys.generate_api_key()
        with engine.begin() as connection:
            public_id = connection.execute(text('''SELECT cafeteria.create_api_key(
                :actor, 'Legacy', :prefix, :digest, ARRAY['preview.read']::text[], :expiry)::text
            '''), {'actor': actor, 'prefix': prefix, 'digest': digest, 'expiry': expiry}).scalar_one()
        keys.append((public_id, token, expiry))
    before = _counts(owner)
    database.run_migrations(owner, ROOT / 'database/schema.sql')
    assert _counts(owner) == before
    for public_id, token, expiry in keys:
        identity = api_keys.authenticate_api_key(engine, token)
        assert identity is not None
        assert identity.public_id == public_id
        assert identity.channels == ('cafeteria', 'patienten')
        assert identity.expires_at == expiry
    with owner.connect() as connection:
        assert connection.execute(text('''SELECT column_default FROM information_schema.columns
            WHERE table_schema='cafeteria' AND table_name='api_keys' AND column_name='channels'
        ''')).scalar_one() is None
