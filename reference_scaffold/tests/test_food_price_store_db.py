"""PRICE-LEDGER: append-only food purchase prices on real PostgreSQL."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria.auth.local_users import ActorExpectation
from cafeteria.food_price_store import append_price_revision, get_price_on, list_price_revisions
from cafeteria.master_data_types import MasterDataValidationError, StaleObjectError
from prepared_food_fixtures import create_food, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def _actor(ids) -> ActorExpectation:
    return ActorExpectation(ids['actor'], ids['authz'])


def test_append_intervals_get_price_on_and_immutable_bytes(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Kartoffeln', unit='KG')
    first = append_price_revision(
        engine, _actor(ids), food['public_id'],
        intervals=[
            {'valid_from': '2026-01-01', 'valid_to': '2026-09-01', 'unit_price': '2.40', 'unit_code': 'KG'},
            {'valid_from': '2026-09-01', 'valid_to': None, 'unit_price': '2.80', 'unit_code': 'KG'},
        ],
    )
    assert first['noop'] is False
    august = get_price_on(engine, food['public_id'], date(2026, 8, 31), first['revision_public_id'])
    september = get_price_on(engine, food['public_id'], date(2026, 9, 1), first['revision_public_id'])
    assert august is not None and august['unit_price'] == Decimal('2.40')
    assert september is not None and september['unit_price'] == Decimal('2.80')
    with pytest.raises(MasterDataValidationError):
        append_price_revision(
            engine, _actor(ids), food['public_id'], expected_head_version=int(first['row_version']),
            intervals=[
                {'valid_from': '2026-01-01', 'valid_to': '2026-10-01', 'unit_price': '2.40', 'unit_code': 'KG'},
                {'valid_from': '2026-09-01', 'valid_to': None, 'unit_price': '2.80', 'unit_code': 'KG'},
            ],
        )
    listed = list_price_revisions(engine, food['public_id'])
    original_hash = listed[0]['content_hash_sha256']
    original_json = listed[0]['edition_json']
    second = append_price_revision(
        engine, _actor(ids), food['public_id'], expected_head_version=int(first['row_version']),
        intervals=[{'valid_from': '2026-01-01', 'valid_to': None, 'unit_price': '3.00', 'unit_code': 'KG'}],
    )
    assert second['revision_public_id'] != first['revision_public_id']
    after = list_price_revisions(engine, food['public_id'])
    assert after[0]['content_hash_sha256'] == original_hash
    assert after[0]['edition_json'] == original_json
    still = get_price_on(engine, food['public_id'], date(2026, 8, 31), first['revision_public_id'])
    assert still is not None and still['unit_price'] == Decimal('2.40')


def test_stale_cas_and_app_cannot_mutate_revision(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Zwiebeln', unit='KG')
    first = append_price_revision(
        engine, _actor(ids), food['public_id'],
        intervals=[{'valid_from': '2026-01-01', 'valid_to': None, 'unit_price': '1.10', 'unit_code': 'KG'}],
    )
    with pytest.raises(StaleObjectError):
        append_price_revision(
            engine, _actor(ids), food['public_id'], expected_head_version=int(first['row_version']) + 4,
            intervals=[{'valid_from': '2026-01-01', 'valid_to': None, 'unit_price': '1.20', 'unit_code': 'KG'}],
        )
    listed = list_price_revisions(engine, food['public_id'])
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as connection:
            connection.execute(text(
                'UPDATE cafeteria.food_purchase_price_revisions SET revision_number=9 WHERE public_id=CAST(:id AS uuid)'
            ), {'id': listed[0]['public_id']})
    assert error.value.orig.sqlstate in ('42501', '55000')
    with pytest.raises(DBAPIError) as denied:
        with engine.begin() as connection:
            connection.execute(text('SELECT cafeteria.food_price_edition_build_v36(1, CAST(:p AS jsonb))'), {
                'p': '{"intervals":[]}',
            })
    assert denied.value.orig.sqlstate == '42501'
