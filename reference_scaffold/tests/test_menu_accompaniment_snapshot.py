from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pytest
from sqlalchemy import Engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from cafeteria.csvio import snapshot_to_csv  # noqa: E402
from cafeteria.db import _read_last_good, active_snapshot  # noqa: E402
from cafeteria.patient_payload import (  # noqa: E402
    PATIENT_ALLOWED_COMPACT_KEYS,
    validate_snapshot_payload,
)
from cafeteria.workflow import derive_admin_status, publish_draft  # noqa: E402
from cafeteria.workflow_snapshot import build_snapshot  # noqa: E402
from demo_snapshots import cafeteria_snapshot, patient_snapshot  # noqa: E402
from test_admin_workflow_db import (  # noqa: E402
    WEEK_START,
    _actor_id,
    _patient_values,
    _save_reviewed,
)
from test_admin_workflow_db import database_engine as database_engine  # noqa: E402, F401
from test_admin_workflow_snapshot_contract import _staff_draft  # noqa: E402


BASELINE_BYTES = 5945
BASELINE_SHA256 = 'a8954ba7b1459caf51110a934eaaf0398217d5c0d7c7c481b508df5e35419238'


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')


def _option(snapshot: dict[str, Any]) -> dict[str, Any]:
    return snapshot['days'][0]['services'][0]['options'][0]


@pytest.mark.parametrize('draft_value', (None, 'none'))
def test_build_snapshot_omits_none_byte_exactly(draft_value: str | None) -> None:
    draft = _staff_draft()
    if draft_value is not None:
        draft['days'][0]['services'][0]['options'][0]['accompaniment_code'] = draft_value

    snapshot = build_snapshot('staff_guest', draft, 'CAF-2026-KW37-R1')
    raw = _canonical_bytes(snapshot)

    assert len(raw) == BASELINE_BYTES
    assert hashlib.sha256(raw).hexdigest() == BASELINE_SHA256
    assert 'accompaniment_code' not in _option(snapshot)
    assert 'accompaniment_name' not in _option(snapshot)


@pytest.mark.parametrize('snapshot_factory', (patient_snapshot, cafeteria_snapshot))
@pytest.mark.parametrize(
    ('code', 'name'),
    (
        ('soup', None),
        (None, 'Suppe'),
        ('soup', 'Salat (gemischt und grün)'),
        ('salad', 'Suppe'),
        ('none', 'Suppe'),
        ('bread', 'Suppe'),
        ([], 'Suppe'),
        ('soup', 7),
    ),
)
def test_validator_rejects_incomplete_or_mismatched_accompaniment_pair(
    snapshot_factory: Any,
    code: object,
    name: object,
) -> None:
    snapshot = snapshot_factory()
    option = _option(snapshot)
    if code is not None:
        option['accompaniment_code'] = code
    if name is not None:
        option['accompaniment_name'] = name

    with pytest.raises(ValueError):
        validate_snapshot_payload(snapshot['profile_code'], snapshot)


def test_patient_compact_key_allowlist_contains_accompaniment_pair() -> None:
    assert {'accompanimentcode', 'accompanimentname'} <= PATIENT_ALLOWED_COMPACT_KEYS


def test_csv_export_ignores_accompaniment_pair_without_changing_bytes() -> None:
    baseline = cafeteria_snapshot()
    selected = deepcopy(baseline)
    _option(selected).update(
        accompaniment_code='salad',
        accompaniment_name='Salat (gemischt und grün)',
    )

    assert snapshot_to_csv(selected) == snapshot_to_csv(baseline)


@pytest.mark.parametrize('schema_version', (1, 2))
def test_read_last_good_accepts_legacy_snapshot_without_accompaniment(
    tmp_path: Path,
    schema_version: int,
) -> None:
    snapshot = patient_snapshot()
    snapshot['schema_version'] = schema_version
    if schema_version == 1:
        snapshot.pop('area_name', None)
    target = tmp_path / 'patient.json'
    target.write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')

    assert _read_last_good(tmp_path, 'patient') == snapshot


@pytest.mark.parametrize('schema_version', (1, 2))
def test_active_snapshot_reads_legacy_revision_without_mutating_it(
    database_engine: Engine,
    schema_version: int,
) -> None:
    actor_id = _actor_id(database_engine)
    legacy = patient_snapshot()
    legacy['schema_version'] = schema_version
    if schema_version == 1:
        legacy.pop('area_name', None)
    raw = _canonical_bytes(legacy)
    digest = hashlib.sha256(raw).hexdigest()

    with database_engine.begin() as connection:
        location_id = connection.execute(
            text(
                'SELECT id FROM cafeteria.locations WHERE code=:code'
            ),
            {'code': legacy['location']['code']},
        ).scalar_one()
        week_id = connection.execute(
            text(
                "INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start, "
                "workflow_state, title, created_by, updated_by) "
                "SELECT :location_id, id, :week_start, 'published', :title, :actor_id, :actor_id "
                "FROM cafeteria.offer_profiles WHERE code='patient' RETURNING id"
            ),
            {
                'location_id': location_id,
                'week_start': WEEK_START,
                'title': legacy['title'],
                'actor_id': actor_id,
            },
        ).scalar_one()
        connection.execute(
            text(
                'INSERT INTO cafeteria.publication_revisions('
                'menu_week_id, revision_number, revision_code, snapshot_json, '
                'content_hash_sha256, published_by) '
                'VALUES (:week_id, 1, :revision_code, CAST(:snapshot AS jsonb), '
                ':digest, :actor_id)'
            ),
            {
                'week_id': week_id,
                'snapshot': raw.decode('utf-8'),
                'digest': digest,
                'revision_code': legacy['revision_id'],
                'actor_id': actor_id,
            },
        )
    with database_engine.connect() as connection:
        before = connection.execute(
            text(
                'SELECT snapshot_json::text, content_hash_sha256 '
                'FROM cafeteria.publication_revisions WHERE revision_code=:revision_code'
            ),
            {'revision_code': legacy['revision_id']},
        ).one()

    assert active_snapshot(database_engine, 'patient', WEEK_START.isoformat()) == legacy

    with database_engine.connect() as connection:
        after = connection.execute(
            text(
                'SELECT snapshot_json::text, content_hash_sha256 '
                'FROM cafeteria.publication_revisions WHERE revision_code=:revision_code'
            ),
            {'revision_code': legacy['revision_id']},
        ).one()
    assert after == before


def test_unselected_publication_keeps_hash_and_live_status(database_engine: Engine) -> None:
    actor_id = _actor_id(database_engine)
    row_version = _save_reviewed(database_engine, 'patient', _patient_values())
    published = publish_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=row_version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    with database_engine.connect() as connection:
        before_hash = connection.execute(
            text(
                'SELECT content_hash_sha256 FROM cafeteria.publication_revisions '
                'WHERE revision_code=:revision_code'
            ),
            {'revision_code': published['revision_id']},
        ).scalar_one()

    loaded = active_snapshot(database_engine, 'patient', WEEK_START.isoformat())

    with database_engine.connect() as connection:
        after_hash = connection.execute(
            text(
                'SELECT content_hash_sha256 FROM cafeteria.publication_revisions '
                'WHERE revision_code=:revision_code'
            ),
            {'revision_code': published['revision_id']},
        ).scalar_one()
    assert loaded == published
    assert before_hash == after_hash
    assert 'accompaniment_code' not in _option(published)
    assert 'accompaniment_name' not in _option(published)
    assert derive_admin_status(database_engine, 'patient', WEEK_START) == 'live'
