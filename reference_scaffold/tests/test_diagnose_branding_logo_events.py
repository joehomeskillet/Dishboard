"""Offline event-shape regressions; no live origin, login or database access."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import diagnose_branding_logo_events as tool  # noqa: E402


@pytest.mark.parametrize('status,mime,location', [
    (200, 'image/png', None), (304, None, None),
    (302, 'text/html; charset=utf-8', '/static/img/suedhang-logo@2x.png?private=DO_NOT_EMIT'),
    (200, 'text/html', None),
])
def test_safe_image_events_preserve_status_mime_and_redirect(status, mime, location, capsys):
    request = MagicMock(url=tool.BASE_URL + '/static/img/suedhang-logo.png?private=DO_NOT_EMIT',
                        method='GET', resource_type='image', redirected_from=None, failure=None)
    headers = {'set-cookie': 'DO_NOT_EMIT', 'authorization': 'DO_NOT_EMIT'}
    if mime is not None:
        headers['content-type'] = mime
    if location:
        headers['location'] = location
    response = SimpleNamespace(request=request, url=request.url, headers=headers,
                               status=status, from_service_worker=False)
    events = tool.LogoEvents()
    events.request(request)
    events.phase = 'branding_editor'
    events.response(response)
    events.terminal(request, 'requestfinished')
    raw = capsys.readouterr().out
    assert 'DO_NOT_EMIT' not in raw and 'set-cookie' not in raw and 'authorization' not in raw
    rows = [json.loads(line) for line in raw.splitlines()]
    assert set(rows[1]) == {
        'event', 'phase', 'request_id', 'started_phase', 'path', 'method', 'resource_type',
        'status', 'content_type', 'content_type_present', 'redirected_from_logo',
        'from_service_worker', 'redirect_present', 'redirect_to_logo', 'redirect_external',
    }
    assert [row['event'] for row in rows] == ['request', 'response', 'requestfinished']
    assert {row['request_id'] for row in rows} == {1}
    assert {row['path'] for row in rows} == {'/static/img/suedhang-logo.png'}
    assert rows[1]['started_phase'] == 'login' and rows[1]['phase'] == 'branding_editor'
    assert rows[1]['status'] == status and rows[1]['content_type'] == mime
    assert rows[1]['content_type_present'] == (mime is not None)
    assert rows[1]['redirect_present'] == bool(location)
    assert rows[1]['redirect_to_logo'] == ('/static/img/suedhang-logo@2x.png' if location else None)
    assert rows[2]['status'] == status and request in events.finished


def test_cancellation_is_distinct_from_missing_mime_and_other_requests_are_ignored(capsys):
    events = tool.LogoEvents()
    for url in [tool.BASE_URL + '/auth/local?private=DO_NOT_EMIT',
                'https://other.invalid/static/img/suedhang-logo.png?private=DO_NOT_EMIT']:
        events.request(MagicMock(url=url))
    request = MagicMock(url=tool.BASE_URL + '/static/img/suedhang-logo.png', method='GET',
                        resource_type='image', redirected_from=None,
                        failure='net::ERR_ABORTED https://fixture.invalid?private=DO_NOT_EMIT')
    events.request(request)
    events.terminal(request, 'requestfailed')
    raw = capsys.readouterr().out
    assert 'DO_NOT_EMIT' not in raw and '/auth/local' not in raw and 'other.invalid' not in raw
    row = json.loads(raw.splitlines()[-1])
    assert row['event'] == 'requestfailed' and row['failure_code'] == 'net::ERR_ABORTED'
    assert row['status'] is None and row['content_type_present'] is None
    assert len(events.requests) == 1


def test_operator_exception_messages_are_never_emitted(monkeypatch, capsys):
    def fail(*_args):
        raise RuntimeError('DO_NOT_EMIT password/form/cookie')
    monkeypatch.setattr(tool, 'BrandingProof', fail)
    assert tool.main() == 2
    assert json.loads(capsys.readouterr().out) == {
        'event': 'diagnostic_error', 'phase': 'login', 'error_type': 'RuntimeError', 'exit_code': 2,
    }
