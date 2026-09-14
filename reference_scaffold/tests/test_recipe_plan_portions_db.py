"""Store/Load/Copy/Review contract for MP-REC-PLAN-PORTIONS target quantities.

Target quantity + unit are an optional pair on a component assignment, only meaningful
together with a bound recipe revision (D3: the unit must equal the revision snapshot's
declared servings_unit_code; no conversion happens here). Presence follows the same
optional-key pattern as recipe_revision_public_id: both keys absent from an assignment row
keeps a stored value unchanged; both present and empty removes it; exactly one present is
rejected. See docs/superpowers reports (wp-pp-store-0914.md) for the frozen interface
contract handed to PP-UI.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import json

import pytest
from sqlalchemy import text

from cafeteria.component_assignment_contract import AssignmentValidationError
from cafeteria.component_assignment_store import (
    StaleItemError, assign_component, replace_component_links,
)
from cafeteria.component_catalog_store import AdminScope
from cafeteria.workflow_copy_store import copy_previous_week
from cafeteria.workflow_review import _review_payload, get_component_review_token
from cafeteria.workflow_snapshot import build_snapshot
from cafeteria.workflow_store import load_draft_connection
from test_admin_workflow_snapshot_contract import _staff_draft
from test_recipe_menu_binding_db import (  # noqa: F401
    binding, app_engine, seeded_pg16, installed_pg16, pg16,
)

WEEK_START = date(2026, 9, 7)
NEXT_WEEK_START = date(2026, 9, 14)


def _scope(ids):
    return AdminScope(ids['actor'], ids['location'], 'patient', ids['authz'])


def _insert_bound_revision(owner, ids, unit_code):
    """Recipe_revisions is immutable after insert; freeze the servings unit right away."""
    with owner.begin() as connection:
        recipe_id = connection.execute(
            text(
                """INSERT INTO cafeteria.recipes(
                    location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
                    VALUES(:location,:actor,:actor,'Portionstest',4,
                    (SELECT id FROM cafeteria.measurement_units WHERE code=:unit_code),'manual')
                    RETURNING id"""
            ),
            {**ids, 'unit_code': unit_code},
        ).scalar_one()
        row = connection.execute(
            text(
                """INSERT INTO cafeteria.recipe_revisions(
                    location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
                    SELECT :location,:recipe,1,snap,
                           encode(public.digest(convert_to(snap::text,'UTF8'),'sha256'),'hex'),:actor
                    FROM (SELECT CAST(:snapshot AS jsonb) AS snap) sub
                    RETURNING id, public_id"""
            ),
            {**ids, 'recipe': recipe_id,
             'snapshot': json.dumps({'recipe': {'servings_unit_code': unit_code}})},
        ).one()
    return int(row.id), str(row.public_id)


def _row(owner, ids):
    with owner.connect() as connection:
        return connection.execute(
            text(
                'SELECT recipe_revision_id, target_quantity, target_quantity_unit_id '
                'FROM cafeteria.menu_item_components WHERE menu_item_id=:item'
            ),
            ids,
        ).one_or_none()


def _assignment(revision, *, quantity=None, unit=None, present=False, label='Suppe'):
    row = {'component_public_id': None, 'component_text': label,
           'recipe_revision_public_id': revision}
    if present:
        row['target_quantity'] = quantity
        row['target_quantity_unit_code'] = unit
    return row


def _rows(owner, ids):
    with owner.connect() as connection:
        return [
            (row.sort_order, row.component_text, row.recipe_revision_id, row.target_quantity)
            for row in connection.execute(
                text(
                    'SELECT sort_order, component_text, recipe_revision_id, target_quantity '
                    'FROM cafeteria.menu_item_components WHERE menu_item_id=:item ORDER BY sort_order'
                ),
                ids,
            )
        ]


def test_round_trip_exact_decimal_persists_and_loads(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    revision_id, revision = _insert_bound_revision(owner, ids, 'PORTION')
    replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='2.500000', unit='PORTION', present=True)], 1,
    )
    saved = _row(owner, ids)
    assert saved.recipe_revision_id == revision_id
    assert saved.target_quantity == Decimal('2.500000')
    assert format(saved.target_quantity, 'f') == '2.500000'
    with engine.connect() as connection:
        draft = load_draft_connection(connection, 'patient', WEEK_START)
    option = draft['days'][0]['services'][0]['options'][0]
    assert option['assignments'][0]['target_quantity'] == '2.500000'
    assert option['assignments'][0]['target_quantity_unit_code'] == 'PORTION'


@pytest.mark.parametrize(
    ('quantity', 'unit', 'match'),
    [
        ('0', 'PORTION', 'Menge'),
        ('-1', 'PORTION', 'Menge'),
        ('2.5', None, 'gemeinsam angegeben'),
        (None, 'PORTION', 'gemeinsam angegeben'),
        ('2.5', 'ZZZZZZZ', 'unbekannt'),
        ('2.5', 'G', 'Ausbeuteeinheit'),
    ],
)
def test_rejects_nonpositive_incomplete_unknown_or_mismatched_unit(
    binding, quantity, unit, match,  # noqa: F811
):
    owner, engine, ids = binding
    scope = _scope(ids)
    _, revision = _insert_bound_revision(owner, ids, 'PORTION')
    before = _row(owner, ids)
    with pytest.raises(AssignmentValidationError, match=match):
        replace_component_links(
            engine, scope, ids['item'],
            [_assignment(revision, quantity=quantity, unit=unit, present=True)], 1,
        )
    assert _row(owner, ids) == before


def test_target_quantity_requires_bound_revision(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    before = _row(owner, ids)
    with pytest.raises(AssignmentValidationError, match='gebundene Rezeptrevision'):
        replace_component_links(
            engine, scope, ids['item'],
            [{'component_public_id': None, 'component_text': 'Suppe',
              'target_quantity': '2.500000', 'target_quantity_unit_code': 'PORTION'}], 1,
        )
    assert _row(owner, ids) == before


def test_presence_rule_absent_keys_preserve_and_empty_pair_clears(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    _, revision = _insert_bound_revision(owner, ids, 'PORTION')
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='2.500000', unit='PORTION', present=True)], 1,
    )
    assert _row(owner, ids).target_quantity == Decimal('2.500000')
    # Resubmitting the same row without the target keys at all keeps the stored value.
    version = replace_component_links(
        engine, scope, ids['item'], [_assignment(revision)], version,
    )
    preserved = _row(owner, ids)
    assert preserved.target_quantity == Decimal('2.500000')
    assert preserved.target_quantity_unit_id is not None
    # Resubmitting with both target keys present but empty clears the value explicitly.
    replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='', unit='', present=True)], version,
    )
    cleared = _row(owner, ids)
    assert cleared.target_quantity is None and cleared.target_quantity_unit_id is None


def test_assign_component_append_preserves_existing_target_quantity(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    revision_id, revision = _insert_bound_revision(owner, ids, 'PORTION')
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='2.500000', unit='PORTION', present=True)], 1,
    )
    assign_component(engine, scope, ids['item'], None, 'Zusatz', version)
    with owner.connect() as connection:
        rows = connection.execute(
            text(
                'SELECT sort_order, target_quantity, target_quantity_unit_id, recipe_revision_id '
                'FROM cafeteria.menu_item_components WHERE menu_item_id=:item ORDER BY sort_order'
            ),
            ids,
        ).all()
    assert rows[0].target_quantity == Decimal('2.500000')
    assert rows[0].recipe_revision_id == revision_id
    assert rows[1].target_quantity is None


def test_absent_keys_keep_target_when_earlier_row_is_deleted(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    _, soup = _insert_bound_revision(owner, ids, 'PORTION')
    main_id, main = _insert_bound_revision(owner, ids, 'PORTION')
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(soup, quantity='2.000000', unit='PORTION', present=True, label='Tomatensuppe'),
         _assignment(main, quantity='3.500000', unit='PORTION', present=True, label='Hauptspeise')],
        1,
    )
    # An old/NoJS client deletes the first row; the second one moves up to sort_order 1.
    replace_component_links(
        engine, scope, ids['item'], [_assignment(main, label='Hauptspeise')], version,
    )
    assert _rows(owner, ids) == [(1, 'Hauptspeise', main_id, Decimal('3.500000'))]


def test_absent_keys_keep_own_targets_when_rows_are_reordered(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    soup_id, soup = _insert_bound_revision(owner, ids, 'PORTION')
    main_id, main = _insert_bound_revision(owner, ids, 'PORTION')
    with owner.connect() as connection:
        catalog = str(connection.execute(
            text('SELECT public_id FROM cafeteria.menu_components WHERE id=:exact'), ids
        ).scalar_one())
    catalog_row = {'component_public_id': catalog, 'component_text': None,
                   'recipe_revision_public_id': main}
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(soup, quantity='2.000000', unit='PORTION', present=True, label='Tomatensuppe'),
         {**catalog_row, 'target_quantity': '3.500000', 'target_quantity_unit_code': 'PORTION'}],
        1,
    )
    replace_component_links(
        engine, scope, ids['item'], [catalog_row, _assignment(soup, label='Tomatensuppe')], version,
    )
    assert _rows(owner, ids) == [
        (1, 'Exact Patient', main_id, Decimal('3.500000')),
        (2, 'Tomatensuppe', soup_id, Decimal('2.000000')),
    ]


def test_absent_keys_never_move_target_to_other_component_with_same_revision(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    shared_id, shared = _insert_bound_revision(owner, ids, 'PORTION')
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(shared, quantity='2.500000', unit='PORTION', present=True, label='Tomatensuppe'),
         _assignment(shared, label='Gemüsesuppe')],
        1,
    )
    assert _rows(owner, ids) == [
        (1, 'Tomatensuppe', shared_id, Decimal('2.500000')),
        (2, 'Gemüsesuppe', shared_id, None),
    ]
    # Deleting the first row must not hand its target to the row that moves up.
    replace_component_links(
        engine, scope, ids['item'], [_assignment(shared, label='Gemüsesuppe')], version,
    )
    assert _rows(owner, ids) == [(1, 'Gemüsesuppe', shared_id, None)]


@pytest.mark.parametrize(
    ('stored', 'resubmitted'),
    [
        (('2.500000', '3.000000'), 2),
        (('2.500000', '3.000000'), 1),
        (('2.500000',), 2),
    ],
    ids=['duplicate-old-and-new', 'duplicate-old', 'duplicate-new'],
)
def test_absent_keys_drop_target_for_ambiguous_duplicate_identity(
    binding, stored, resubmitted,  # noqa: F811
):
    owner, engine, ids = binding
    scope = _scope(ids)
    revision_id, revision = _insert_bound_revision(owner, ids, 'PORTION')
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity=quantity, unit='PORTION', present=True) for quantity in stored],
        1,
    )
    assert [row[3] for row in _rows(owner, ids)] == [Decimal(quantity) for quantity in stored]
    replace_component_links(
        engine, scope, ids['item'], [_assignment(revision) for _ in range(resubmitted)], version,
    )
    assert _rows(owner, ids) == [
        (position, 'Suppe', revision_id, None) for position in range(1, resubmitted + 1)
    ]


@pytest.mark.parametrize('change', ['revision', 'component'])
def test_absent_keys_drop_target_when_revision_or_component_changes(binding, change):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    revision_id, revision = _insert_bound_revision(owner, ids, 'PORTION')
    other_id, other = _insert_bound_revision(owner, ids, 'PORTION')
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='2.500000', unit='PORTION', present=True)], 1,
    )
    if change == 'revision':
        resubmitted, expected = _assignment(other), (1, 'Suppe', other_id, None)
    else:
        resubmitted, expected = _assignment(revision, label='Eintopf'), (1, 'Eintopf', revision_id, None)
    replace_component_links(engine, scope, ids['item'], [resubmitted], version)
    assert _rows(owner, ids) == [expected]


def test_copy_previous_week_carries_target_quantity_with_revision(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    revision_id, revision = _insert_bound_revision(owner, ids, 'PORTION')
    replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='2.500000', unit='PORTION', present=True)], 1,
    )
    with owner.connect() as connection:
        source_version = connection.execute(
            text('SELECT row_version FROM cafeteria.menu_weeks WHERE id=:week'), ids
        ).scalar_one()
    copy_previous_week(engine, scope, NEXT_WEEK_START, 0, source_row_version=source_version)
    with owner.connect() as connection:
        copied = connection.execute(
            text(
                '''
                SELECT link.recipe_revision_id, link.target_quantity, link.target_quantity_unit_id
                FROM cafeteria.menu_item_components link
                JOIN cafeteria.menu_items item ON item.id=link.menu_item_id
                JOIN cafeteria.menu_services service ON service.id=item.service_id
                JOIN cafeteria.menu_weeks week ON week.id=service.menu_week_id
                WHERE week.week_start=:week_start
                '''
            ),
            {'week_start': NEXT_WEEK_START},
        ).one()
        unit_code = connection.execute(
            text('SELECT code FROM cafeteria.measurement_units WHERE id=:unit'),
            {'unit': copied.target_quantity_unit_id},
        ).scalar_one()
    assert copied.recipe_revision_id == revision_id
    assert copied.target_quantity == Decimal('2.500000')
    assert unit_code == 'PORTION'


def test_review_payload_components_stable_unless_target_quantity_changes(binding):  # noqa: F811
    """D7: target quantity/unit live in the review payload and drive its CAS hash.

    ``item_row_version`` always advances on every save (existing, unrelated design: any save
    resets ``allergen_review_status`` and therefore always changes the overall review token,
    even re-saving byte-identical content). The part of the payload that actually represents
    the component binding -- and therefore the meaningful CAS surface for D7 -- is
    ``components``; it stays byte-identical across a save that repeats the same target
    quantity, and changes as soon as the target quantity itself changes.
    """
    owner, engine, ids = binding
    scope = _scope(ids)
    _, revision = _insert_bound_revision(owner, ids, 'PORTION')
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='2.500000', unit='PORTION', present=True)], 1,
    )
    with engine.connect() as connection:
        first = _review_payload(connection, scope, ids['item'])
    assert first['components'][0]['target_quantity'] == '2.500000'
    assert first['components'][0]['target_quantity_unit_code'] == 'PORTION'
    token_first = get_component_review_token(engine, scope, ids['item'])
    version = replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='2.500000', unit='PORTION', present=True)], version,
    )
    with engine.connect() as connection:
        second = _review_payload(connection, scope, ids['item'])
    assert second['components'] == first['components']
    replace_component_links(
        engine, scope, ids['item'],
        [_assignment(revision, quantity='3.000000', unit='PORTION', present=True)], version,
    )
    with engine.connect() as connection:
        third = _review_payload(connection, scope, ids['item'])
    assert third['components'] != second['components']
    assert third['components'][0]['target_quantity'] == '3.000000'
    assert get_component_review_token(engine, scope, ids['item']) != token_first


def test_row_version_conflict_still_rejected_with_target_quantity(binding):  # noqa: F811
    owner, engine, ids = binding
    scope = _scope(ids)
    _, revision = _insert_bound_revision(owner, ids, 'PORTION')
    before = _row(owner, ids)
    with pytest.raises(StaleItemError):
        replace_component_links(
            engine, scope, ids['item'],
            [_assignment(revision, quantity='2.500000', unit='PORTION', present=True)], 999,
        )
    assert _row(owner, ids) == before


def test_build_snapshot_never_reads_target_quantity_assignments():
    draft = _staff_draft()
    baseline = build_snapshot('staff_guest', draft, 'CAF-2026-KW37-R1')
    option = draft['days'][0]['services'][0]['options'][0]
    option['assignments'] = [
        {'component_public_id': None, 'component_text': 'Rind & Crème',
         'recipe_revision_public_id': '11111111-1111-4111-8111-111111111111',
         'target_quantity': '2.500000', 'target_quantity_unit_code': 'PORTION'},
    ]
    with_target = build_snapshot('staff_guest', draft, 'CAF-2026-KW37-R1')
    assert with_target == baseline
    raw = json.dumps(with_target, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    assert 'target_quantity' not in raw
