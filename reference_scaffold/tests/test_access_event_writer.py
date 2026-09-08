"""Ambiguous commit retry and session-establishment diagnostics retain safe semantics."""
from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria.auth import access_events, routes
from test_auth_routes import auth_app, _csrf_payload, _provision  # noqa: F401


def test_python_writer_retries_ambiguous_commit_with_one_server_uuid(auth_app, monkeypatch, caplog):  # noqa: F811
    app, owner, issuer = auth_app
    event = uuid4()
    factory = Mock(return_value=event)
    monkeypatch.setattr(access_events, 'uuid4', factory)
    attempts = []

    @contextmanager
    def begin():
        with issuer.begin() as connection:
            yield connection
        attempts.append(True)
        if len(attempts) == 1:
            # The real transaction committed; the caller did not receive its acknowledgement.
            raise DBAPIError(None, None, RuntimeError('private-driver-sentinel'), connection_invalidated=True)

    app.extensions['cafeteria_auth_issuer_db'] = Mock(begin=begin)
    try:
        with app.app_context():
            assert access_events.record_access_event('local', 'auth.login.rejected', 'credentials') == event
    finally:
        app.extensions['cafeteria_auth_issuer_db'] = issuer
    assert factory.call_count == 1 and len(attempts) == 2
    with owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.audit_events WHERE public_id=CAST(:id AS uuid)'), {'id': str(event)}).scalar_one() == 1
    assert 'private-driver-sentinel' not in caplog.text


def test_python_writer_invalid_tuple_and_outage_never_log_unbounded_data(auth_app, caplog):  # noqa: F811
    app, _, issuer = auth_app
    with app.app_context():
        with pytest.raises(ValueError, match='Invalid authentication'):
            access_events.record_access_event('unbounded-secret-sentinel', 'auth.login.rejected', 'credentials')
        app.extensions.pop('cafeteria_auth_issuer_db')
        try:
            with pytest.raises(access_events.AccessEventUnavailable):
                access_events.record_access_event('local', 'auth.login.rejected', 'credentials')
        finally:
            app.extensions['cafeteria_auth_issuer_db'] = issuer
    assert 'unbounded-secret-sentinel' not in caplog.text
    assert 'Authentication decision audit unavailable.' in caplog.text


def test_session_establishment_failure_returns_503_without_claiming_session(auth_app, monkeypatch, caplog):  # noqa: F811
    app, owner, issuer = auth_app
    _provision(issuer, owner)
    client = app.test_client()
    data = _csrf_payload(client, username='local.editor', password='Correct-Horse-2026!Battery')
    monkeypatch.setattr(routes, '_establish_session', Mock(side_effect=RedisError('private-session-sentinel')))
    response = client.post('/auth/local', data=data)
    assert response.status_code == 503
    with client.session_transaction() as session:
        assert 'user' not in session
    with owner.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action='auth.login.accepted'")).scalar_one() == 1
    # Accepted credential/authorization decision is durable; browser session success is not asserted.
    assert 'Authentication session establishment unavailable.' in caplog.text
    assert 'private-session-sentinel' not in caplog.text
    assert 'private-session-sentinel' not in response.get_data(as_text=True)


def test_public_event_uuid_is_ignored_by_authentication_writer(auth_app, monkeypatch):  # noqa: F811
    app, owner, _ = auth_app
    server_event, submitted_event = uuid4(), uuid4()
    factory = Mock(return_value=server_event)
    monkeypatch.setattr(access_events, 'uuid4', factory)
    client = app.test_client()
    response = client.post('/auth/local', data=_csrf_payload(
        client, username='unknown.user', password='irrelevant-test-password', event=str(submitted_event),
    ))
    assert response.status_code == 401 and factory.call_count == 1
    with owner.connect() as connection:
        rows = connection.execute(text("SELECT public_id FROM cafeteria.audit_events WHERE entity_type='authentication'")).scalars().all()
    assert rows == [server_event] and submitted_event not in rows
