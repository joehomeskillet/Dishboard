from __future__ import annotations

import importlib
import sys
from copy import deepcopy
from pathlib import Path

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
