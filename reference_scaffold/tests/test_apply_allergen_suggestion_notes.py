from __future__ import annotations

import importlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qsl, urlencode

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


def module():
    return importlib.import_module('apply_allergen_suggestion_notes')


def baseline(proposal):
    return {
        'id': proposal.id, 'profile': proposal.profile, 'week': '2026-08-31',
        'day': proposal.day, 'meal': proposal.meal, 'option': proposal.option,
        'title': proposal.title, 'components': list(proposal.components),
        'note': '', 'review': 'not_checked', 'version': 4, 'state': {'price': 1250},
    }


def test_mismatch_diagnostics_distinguish_form_order_and_database_fields_without_values():
    tool = module()
    proposal = tool.parse_proposals(tool.DOCUMENT.read_bytes())[2]
    before = baseline(proposal)
    after = deepcopy(before)
    after.update(note=proposal.note, version=5)
    data = [['_csrf', 'SECRET'], ['note', ''], ['origin_ingredient', 'A'], ['origin_country_code', 'CH']]
    readback = [['_csrf', 'NEW_SECRET'], ['note', proposal.note], ['origin_country_code', 'CH'], ['origin_ingredient', 'A']]
    assert tool.verified_save(proposal, before, after)
    assert not tool.form_unchanged(data, readback, proposal.note)
    assert tool.saved_state_fields(proposal, before, after, data, readback) == [
        'form.origin_country_code', 'form.origin_ingredient',
    ]
    after['state']['origins'] = [{'ingredient': 'SENSITIVE_VALUE'}]
    after['UNTRUSTED_FIELD_NAME'] = 'PRIVATE'
    fields = tool.saved_state_fields(proposal, before, after, data, readback)
    assert fields == ['database.state.origins', 'database.unrecognized_field',
                      'form.origin_country_code', 'form.origin_ingredient']
    assert 'SECRET' not in json.dumps(fields)
    assert 'SENSITIVE_VALUE' not in json.dumps(fields)
    assert 'UNTRUSTED_FIELD_NAME' not in json.dumps(fields)


def test_main_records_only_allowlisted_mismatch_code_and_names(monkeypatch, tmp_path):
    tool = module()
    report = tmp_path / 'diagnostic.json'
    monkeypatch.setattr(tool, 'arguments', lambda: tool.argparse.Namespace(apply=True, report=report))
    monkeypatch.setattr(tool, 'sync_playwright', MagicMock())
    monkeypatch.setattr(tool, 'login', lambda *args: None)
    def mismatch(*args):
        raise tool.SavedStateMismatch(['database.state.origins', 'form.note',
                                      '_csrf', 'password=SECRET', 'form._csrf'])
    run = MagicMock(side_effect=mismatch)
    monkeypatch.setattr(tool, 'process', run)
    assert tool.main() == 1
    assert run.call_count == 1
    result = json.loads(report.read_text())
    assert result['status'] == 'stopped'
    assert result['error_code'] == 'saved_state_mismatch'
    assert result['changed_fields'] == ['database.state.origins', 'form.note']
    assert not any(value in report.read_text() for value in ('SECRET', '_csrf', 'password'))


def test_reviewed_document_has_exact_scope_and_rejects_changed_text():
    tool = module()
    raw = tool.DOCUMENT.read_bytes()
    proposals = tool.parse_proposals(raw)
    assert [row.id for row in proposals] == list(range(77, 115))
    assert sum(row.profile == 'staff_guest' for row in proposals) == 10
    with pytest.raises(ValueError):
        tool.parse_proposals(raw.replace(b'77 |', b'76 |', 1))


@pytest.mark.parametrize('field,value', [
    ('version', 5), ('review', 'checked'), ('note', 'My edit'),
    ('id', 999), ('title', 'Changed dish'), ('components', ['Different']),
    ('profile', 'patient'), ('day', '2026-09-01'), ('week', '2026-09-07'),
])
def test_preflight_rejects_concurrent_changes(field, value):
    tool = module()
    proposal = tool.parse_proposals(tool.DOCUMENT.read_bytes())[0]
    row = baseline(proposal)
    row[field] = value
    assert tool.classify(proposal, row) == 'conflict'


def test_checked108_is_always_skipped_and_identical_note_is_idempotent():
    tool = module()
    proposals = tool.parse_proposals(tool.DOCUMENT.read_bytes())
    assert tool.classify(proposals[31], baseline(proposals[31])) == 'skipped_checked'
    row = baseline(proposals[0])
    assert tool.classify(proposals[0], row) == 'eligible'
    row.update(note=proposals[0].note, version=8, review='checked')
    assert tool.classify(proposals[0], row) == 'already_present'


def test_readback_detects_side_effects_and_missing_note():
    tool = module()
    proposal = tool.parse_proposals(tool.DOCUMENT.read_bytes())[0]
    before = baseline(proposal)
    after = deepcopy(before)
    after.update(note=proposal.note, version=5)
    assert tool.verified_save(proposal, before, after)
    after['state']['price'] = 1300
    assert not tool.verified_save(proposal, before, after)
    after = deepcopy(before)
    assert not tool.verified_save(proposal, before, after)


def test_form_comparison_preserves_repeated_fields_and_detects_loss():
    tool = module()
    before = [['_csrf', 'private'], ['row_version', '4'], ['note', ''],
              ['component_public_id', 'a'], ['component_public_id', 'b']]
    after = [['_csrf', 'new'], ['row_version', '5'], ['note', 'proposal'],
             ['component_public_id', 'a'], ['component_public_id', 'b']]
    assert tool.form_unchanged(before, after, 'proposal')
    assert not tool.form_unchanged(before, after[:-1], 'proposal')
    assert not tool.form_unchanged(before, after, 'wrong')


def test_network_guard_is_one_shot_exact_origin_and_exact_payload():
    tool = module()
    gate = tool.NetworkGate()
    assert not gate.allow('GET', 'https://other.invalid/admin')
    assert not gate.allow('GET', tool.BASE + '/admin/patienten/menu/review')
    assert not gate.allow('POST', tool.BASE + '/admin/patienten/menu', 'note=x')
    assert gate.allow('POST', tool.BASE + '/auth/local', 'username=x&password=test')
    assert not gate.allow('POST', tool.BASE + '/auth/local', 'username=x&password=test')
    gate.pending = (tool.BASE + '/admin/cafeteria/menu', [('note', 'x'), ('row_version', '4')])
    assert not gate.allow('POST', tool.BASE + '/admin/cafeteria/menu', 'note=x&row_version=5')
    assert gate.allow('POST', tool.BASE + '/admin/cafeteria/menu', 'note=x&row_version=4')
    assert not gate.allow('POST', tool.BASE + '/admin/cafeteria/menu', 'note=x&row_version=4')


def test_network_gate_rejects_cross_origin_and_post_preserving_redirects():
    tool = module()
    gate = tool.NetworkGate()
    assert not gate.allow_redirect('POST', tool.BASE + '/auth/local', 303, 'https://evil.invalid/admin')
    assert not gate.allow_redirect('GET', tool.BASE + '/admin', 302, '//evil.invalid/steal')
    assert not gate.allow_redirect('POST', tool.BASE + '/auth/local', 307, '/admin/cafeteria/menu')
    assert not gate.allow_redirect('POST', tool.BASE + '/auth/local', 308, '/admin/')


def test_network_gate_validates_only_expected_api_post_redirects():
    tool = module()
    gate = tool.NetworkGate()
    assert gate.allow_redirect('POST', tool.BASE + '/auth/local', 302, '/admin/cafeteria')
    assert not gate.allow_redirect('POST', tool.BASE + '/auth/local', 303, '/admin/cafeteria')
    assert not gate.allow_redirect('GET', tool.BASE + '/admin/cafeteria/menu', 302, '/admin/cafeteria')
    action = tool.BASE + '/admin/cafeteria/menu'
    gate.pending = (action, [('note', 'proposal'), ('row_version', '4')])
    assert gate.allow_redirect(
        'POST', action, 303,
        '/admin/cafeteria/menu?week=2026-08-31&day=2026-08-31&meal=LUNCH&option=MENU_1',
    )


class _FakeRoute:
    def __init__(self, method, url, post_data='', status=200, location=None):
        self.request = type('Request', (), {'method': method, 'url': url, 'post_data': post_data})()
        self.status = status
        self.location = location
        self.fetch_kwargs = None
        self.fulfilled = False
        self.aborted = False
        self.continued = False

    def fetch(self, **kwargs):
        self.fetch_kwargs = kwargs
        headers = {'location': self.location} if self.location else {}
        return type('Response', (), {'status': self.status, 'headers': headers})()

    def fulfill(self, response=None):
        self.fulfilled = True
        self.fulfilled_response = response

    def abort(self):
        self.aborted = True

    def continue_(self):
        self.continued = True


def test_network_gate_route_uses_fetch_without_implicit_redirect_follow():
    tool = module()
    gate = tool.NetworkGate()
    route = _FakeRoute('GET', tool.BASE + '/admin')
    gate.route(route)
    assert route.fetch_kwargs == {'max_redirects': 0}
    assert route.fulfilled
    assert not route.continued
    assert not route.aborted
    assert not gate.blocked


def test_network_gate_route_blocks_unauthorized_redirect_before_follow():
    tool = module()
    gate = tool.NetworkGate()
    route = _FakeRoute('GET', tool.BASE + '/admin', status=302, location='https://evil.invalid/')
    gate.route(route)
    assert route.fetch_kwargs == {'max_redirects': 0}
    assert route.aborted
    assert not route.fulfilled
    assert not route.continued
    assert gate.blocked


def test_browser_route_blocks_login_post_before_transmission():
    tool = module()
    gate = tool.NetworkGate()
    route = _FakeRoute(
        'POST', tool.BASE + '/auth/local', 'username=x&password=test',
        status=302, location='/admin/cafeteria',
    )
    gate.route(route)
    assert route.fetch_kwargs is None
    assert not route.fulfilled
    assert route.aborted
    assert not route.continued
    assert gate.blocked
    assert gate.login_pending


def test_browser_route_blocks_save_post_before_transmission():
    tool = module()
    gate = tool.NetworkGate()
    action = tool.BASE + '/admin/cafeteria/menu'
    gate.pending = (action, [('note', 'proposal'), ('row_version', '4')])
    route = _FakeRoute(
        'POST', action, 'note=proposal&row_version=4',
        status=303, location='/admin/cafeteria/menu?week=2026-08-31',
    )
    gate.route(route)
    assert route.fetch_kwargs is None
    assert not route.fulfilled
    assert route.aborted
    assert not route.continued
    assert gate.blocked


@pytest.mark.parametrize('status', [300, 301, 302, 303, 304, 307, 308])
def test_browser_never_receives_a_redirect_even_to_an_allowed_url(status):
    tool = module()
    gate = tool.NetworkGate()
    route = _FakeRoute('GET', tool.BASE + '/admin', status=status, location='/admin/cafeteria')
    gate.route(route)
    assert route.fetch_kwargs == {'max_redirects': 0}
    assert route.aborted and gate.blocked
    assert not route.fulfilled and not route.continued


def test_api_post_preserves_exact_repeated_form_fields_and_never_follows_redirect():
    tool = module()
    gate = tool.NetworkGate()
    action = tool.BASE + '/admin/cafeteria/menu'
    data = [['_csrf', 'synthetic'], ['note', 'Milch & Weizen prüfen'], ['row_version', '4'],
            ['component_public_id', 'a'], ['component_public_id', 'b']]
    gate.pending = (action, [tuple(pair) for pair in data])
    request = MagicMock()
    request.post.return_value = MagicMock(status=303, headers={'location': action + '?row_version=5'})
    response = gate.post(request, action, data)
    assert response.status == 303
    request.post.assert_called_once_with(
        action, data=urlencode([tuple(pair) for pair in data]), max_redirects=0, max_retries=0, timeout=15000,
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'Origin': tool.BASE, 'Referer': action},
    )
    assert parse_qsl(request.post.call_args.kwargs['data']) == [tuple(pair) for pair in data]
    request.get.assert_not_called()
    assert gate.pending is None and not gate.blocked


@pytest.mark.parametrize('status,location', [
    (303, 'https://other.invalid/admin'), (303, '//other.invalid/admin'),
    (303, '/admin/patienten/menu'), (303, ''), (302, '/admin/cafeteria/menu'),
    (307, '/admin/cafeteria/menu'), (308, '/admin/cafeteria/menu'),
])
def test_api_post_rejects_unexpected_redirect_without_a_second_transmission(status, location):
    tool = module()
    gate = tool.NetworkGate()
    action = tool.BASE + '/admin/cafeteria/menu'
    gate.pending = (action, [('note', 'proposal')])
    request = MagicMock()
    request.post.return_value = MagicMock(status=status, headers={'location': location})
    with pytest.raises(RuntimeError, match='post_redirect_rejected'):
        gate.post(request, action, [['note', 'proposal']])
    request.post.assert_called_once()
    assert request.post.call_args.kwargs['max_redirects'] == 0
    request.get.assert_not_called()
    assert gate.blocked and gate.pending is None


def test_api_payload_mismatch_blocks_before_transmission():
    tool = module()
    gate = tool.NetworkGate()
    action = tool.BASE + '/admin/cafeteria/menu'
    gate.pending = (action, [('note', 'proposal')])
    request = MagicMock()
    with pytest.raises(RuntimeError, match='post_not_authorized'):
        gate.post(request, action, [['note', 'different']])
    request.post.assert_not_called()
    assert gate.blocked


def test_api_timeout_is_not_retried_or_reauthorized():
    tool = module()
    gate = tool.NetworkGate()
    action = tool.BASE + '/admin/cafeteria/menu'
    gate.pending = (action, [('note', 'proposal')])
    request = MagicMock()
    request.post.side_effect = TimeoutError('synthetic')
    with pytest.raises(RuntimeError, match='post_failed_or_uncertain'):
        gate.post(request, action, [['note', 'proposal']])
    with pytest.raises(RuntimeError, match='post_not_authorized'):
        gate.post(request, action, [['note', 'proposal']])
    request.post.assert_called_once()
    assert gate.blocked and gate.pending is None


def test_login_posts_captured_form_once_then_gets_fixed_overview(monkeypatch):
    tool = module()
    gate = tool.NetworkGate()
    page = MagicMock()
    data = [['csrf_token', 'synthetic-csrf'], ['username', tool.USER], ['password', 'synthetic-password']]
    form = MagicMock()
    form.count.return_value = 1
    form.evaluate.return_value = data
    main = MagicMock()
    main.count.return_value = 1
    page.locator.side_effect = [form, main]
    page.context.request.post.return_value = MagicMock(status=302, headers={'location': '/admin/cafeteria'})

    def goto(url, **kwargs):
        page.url = url
        return MagicMock(status=200)

    page.goto.side_effect = goto
    monkeypatch.setattr(tool, '_password', lambda: 'synthetic-password')
    tool.login(page, gate)
    assert [call.args[0] for call in page.goto.call_args_list] == [
        tool.BASE + '/auth/local', tool.BASE + '/admin/cafeteria',
    ]
    assert parse_qsl(page.context.request.post.call_args.kwargs['data']) == [tuple(pair) for pair in data]
    assert page.context.request.post.call_args.kwargs['max_redirects'] == 0
    assert not gate.login_pending
    page.get_by_role.assert_not_called()
    form.get_by_role.assert_not_called()


@pytest.mark.parametrize('apply,status', [(False, 'would_save'), (True, 'saved'), (True, 'conflict')])
def test_process_uses_explicit_post_and_safe_readback_only(monkeypatch, apply, status):
    tool = module()
    proposal = tool.parse_proposals(tool.DOCUMENT.read_bytes())[0]
    before = baseline(proposal)
    after = deepcopy(before)
    after.update(note=proposal.note, version=5)
    snapshots = iter([{proposal.id: before}, {proposal.id: before}, {proposal.id: after}])
    monkeypatch.setattr(tool, 'read_rows', lambda: next(snapshots))
    data = [['_csrf', 'synthetic'], ['note', ''], ['row_version', '4'], ['component_public_id', 'a']]
    changed = deepcopy(data)
    changed[1][1] = proposal.note
    form = MagicMock()
    form.evaluate.return_value = changed
    loads = MagicMock(side_effect=[(form, data), (form, changed)])
    monkeypatch.setattr(tool, 'load_form', loads)
    monkeypatch.setattr(tool, 'form_matches', lambda *args: True)
    page = MagicMock()
    page.context.request.post.return_value = MagicMock(
        status=409 if status == 'conflict' else 303,
        headers={'location': proposal.url + '&row_version=5'},
    )
    assert tool.process(page, tool.NetworkGate(), proposal, apply) == status
    assert loads.call_count == (2 if status == 'saved' else 1)
    if apply:
        page.context.request.post.assert_called_once()
        assert parse_qsl(page.context.request.post.call_args.kwargs['data']) == [tuple(pair) for pair in changed]
    else:
        page.context.request.post.assert_not_called()
    form.get_by_role.assert_not_called()
    page.expect_response.assert_not_called()


def test_dry_run_is_the_default():
    assert not module().arguments(['--report', '/tmp/unused-report.json']).apply


def test_readonly_query_and_failed_read_retry_are_bounded(monkeypatch):
    tool = module()
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        raise tool.subprocess.TimeoutExpired(command, 30)

    monkeypatch.setattr(tool.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='read_only_snapshot_failed_twice'):
        tool.read_rows()
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert calls[0][0][0] == 'rtk'
    assert tool.SQL.startswith('BEGIN READ ONLY;')
    assert tool.SQL.rstrip().endswith('COMMIT;')
    assert 'WHERE i.id BETWEEN 77 AND 114' in tool.SQL
