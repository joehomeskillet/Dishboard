"""App-role binding writers: exact revisions, loss protection and atomic receipts."""
from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import text

from cafeteria.component_assignment_store import (
    ComponentAssignmentConflictError, assign_component, replace_component_links,
)
from cafeteria.component_catalog_store import AdminScope, ComponentNotFoundError
from cafeteria.workflow_write_context import WriteConflictError, WritePermissionError
from cafeteria.workflow_copy_store import copy_previous_week
from cafeteria.workflow_partial_store import persist_menu_item
from cafeteria.workflow_review import get_component_review_token, review_component, _review_payload
from cafeteria.workflow_store import load_draft_connection
from cafeteria.workflow import save_draft, import_draft
from test_recipe_menu_binding_db import (  # noqa: F401
    binding, app_engine, seeded_pg16, installed_pg16, pg16,
)


def scope_and_revision(owner, ids):
    scope = AdminScope(ids['actor'], ids['location'], 'patient', ids['authz'])
    with owner.connect() as connection:
        revision = str(connection.execute(text('SELECT public_id FROM cafeteria.recipe_revisions '
                                               'WHERE id=:location_revision'), ids).scalar_one())
    return scope, revision


def state(owner, ids):
    with owner.connect() as connection:
        item = tuple(connection.execute(text('SELECT public_id,row_version,allergen_review_status '
                                              'FROM cafeteria.menu_items WHERE id=:item'), ids).one())
        links = [tuple(row) for row in connection.execute(text('SELECT sort_order,component_text,'
            'component_id,component_row_version,recipe_revision_id FROM cafeteria.menu_item_components '
            'WHERE menu_item_id=:item ORDER BY sort_order'), ids)]
        receipts = list(connection.execute(text("SELECT details FROM cafeteria.audit_events "
            "WHERE action='workflow.menu_saved' AND entity_public_id=:public_id ORDER BY id"),
            {'public_id': item[0]}).scalars())
    return item, links, receipts


def assignment(revision, label='Suppe'):
    return {'component_public_id': None, 'component_text': label,
            'recipe_revision_public_id': revision}


def test_exact_recipe_roundtrip_append_legacy_refusal_and_explicit_detach(binding):  # noqa: F811
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    version = replace_component_links(engine, scope, ids['item'], [assignment(revision)], 1)
    assert version == 2
    first = state(owner, ids)
    assert first[1][0][-1] == ids['location_revision']
    assert first[2][0]['recipe_revisions'][0]['revision_public_id'] == revision
    assert first[2][0]['row_version_before'] == 1
    version = assign_component(engine, scope, ids['item'], None, 'Zusatz', version)
    assert version == 3 and state(owner, ids)[1][0][-1] == ids['location_revision']
    before = state(owner, ids)
    for legacy in ([], [{'component_public_id': None, 'component_text': 'Suppe'}]):
        with pytest.raises(ComponentAssignmentConflictError, match='Rezeptbezüge'):
            replace_component_links(engine, scope, ids['item'], legacy, version)
        assert state(owner, ids) == before
    assert replace_component_links(engine, scope, ids['item'], [assignment(None)], version) == 4
    after = state(owner, ids)
    assert after[1][0][-1] is None and len(after[2]) == 3
    assert after[0][0] == first[0][0] and after[0][2] == 'not_checked'


def test_archived_recipe_preserve_increase_detach_and_foreign_scope(binding):  # noqa: F811
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    version = replace_component_links(engine, scope, ids['item'], [assignment(revision)], 1)
    with owner.begin() as connection:
        connection.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:location_recipe'), ids)
        foreign = str(connection.execute(text('SELECT public_id FROM cafeteria.recipe_revisions '
            'WHERE id=:other_location_revision'), ids).scalar_one())
    version = replace_component_links(engine, scope, ids['item'], [assignment(revision, 'Bewahrt')], version)
    before = state(owner, ids)
    with pytest.raises(ComponentAssignmentConflictError, match='Archiviertes Rezept'):
        replace_component_links(engine, scope, ids['item'], [assignment(revision)] * 2, version)
    with pytest.raises(ComponentNotFoundError, match='Rezeptrevision'):
        replace_component_links(engine, scope, ids['item'], [assignment(foreign)], version)
    assert state(owner, ids) == before
    assert replace_component_links(engine, scope, ids['item'], [assignment(None)], version) == version + 1


@pytest.mark.parametrize('change', ['missing', 'stale', 'disabled', 'role'])
def test_original_actor_required_before_any_menu_mutation(binding, change):  # noqa: F811
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    if change == 'missing':
        scope = replace(scope, expected_authz_version=None)
    elif change == 'stale':
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:actor'), ids)
    else:
        with owner.begin() as connection:
            connection.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor'
                if change == 'disabled' else 'DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor'), ids)
    before = state(owner, ids)
    with pytest.raises((WriteConflictError, WritePermissionError)):
        replace_component_links(engine, scope, ids['item'], [assignment(revision)], 1)
    assert state(owner, ids) == before


def test_partial_readback_review_change_revert_and_unknown_recipe_effects(binding):  # noqa: F811
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    payload = {'title': 'Suppe', 'description': '', 'note': '', 'allergen_mode': 'auto',
               'origin_mode': 'auto', 'label_mode': 'auto', 'assignments': [assignment(revision)],
               'labels': [], 'allergens': [], 'origins': []}
    version = persist_menu_item(engine, scope, date(2026, 9, 7), '2026-09-07', 'LUNCH', 'MENU_1', payload, 1)
    with engine.connect() as connection:
        option = load_draft_connection(connection, 'patient', date(2026, 9, 7))['days'][0]['services'][0]['options'][0]
        review = _review_payload(connection, scope, ids['item'])
    assert option['assignments'] == [assignment(revision)]
    assert option['allergens'] == option['labels'] == option['origins'] == []
    assert review['components'][0]['recipe_revision_public_id'] == revision
    assert len(review['components'][0]['recipe_content_hash_sha256']) == 64
    token = get_component_review_token(engine, scope, ids['item'])
    version = review_component(engine, scope, ids['item'], token, version)
    approved = get_component_review_token(engine, scope, ids['item'])
    version = persist_menu_item(engine, scope, date(2026, 9, 7), '2026-09-07', 'LUNCH', 'MENU_1',
                                {**payload, 'title': 'Änderung'}, version)
    version = persist_menu_item(engine, scope, date(2026, 9, 7), '2026-09-07', 'LUNCH', 'MENU_1', payload, version)
    assert get_component_review_token(engine, scope, ids['item']) != approved
    assert version == 5 and state(owner, ids)[0][2] == 'not_checked'


def test_exact_archived_copy_keeps_source_text_version_and_revision(binding):  # noqa: F811
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    with owner.connect() as connection:
        component = str(connection.execute(text('SELECT public_id FROM cafeteria.menu_components WHERE id=:exact'), ids).scalar_one())
    replace_component_links(engine, scope, ids['item'], [{**assignment(revision),
        'component_public_id': component, 'component_text': None}], 1)
    before = state(owner, ids)
    with owner.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_components SET name='Neu und archiviert', "
            'row_version=row_version+1,active=false,food_id=:location_food WHERE id=:exact'), ids)
        connection.execute(text('UPDATE cafeteria.foods SET active=false WHERE id=:location_food'), ids)
        connection.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:location_recipe'), ids)
        source_version = connection.execute(text('SELECT row_version FROM cafeteria.menu_weeks WHERE id=:week'), ids).scalar_one()
    assert copy_previous_week(engine, scope, date(2026, 9, 14), 0, source_row_version=source_version) == 1
    with owner.connect() as connection:
        copied = connection.execute(text('''
            SELECT l.component_text,l.component_id,l.component_row_version,l.recipe_revision_id,
                   i.row_version,i.allergen_review_status
            FROM cafeteria.menu_item_components l JOIN cafeteria.menu_items i ON i.id=l.menu_item_id
            JOIN cafeteria.menu_services s ON s.id=i.service_id JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
            WHERE w.week_start='2026-09-14'
        ''')).one()
    assert tuple(copied[:4]) == tuple(before[1][0][1:])
    assert tuple(copied[4:]) == (1, 'not_checked')


def test_bulk_preserves_identity_version_and_blocks_recipe_only_csv(binding):  # noqa: F811
    from test_admin_workflow_db import _patient_values
    owner, engine, ids = binding
    scope, revision = scope_and_revision(owner, ids)
    values = _patient_values()
    first_day = date.fromisoformat(values['days'][0]['date'])
    offset = date(2026, 9, 7) - first_day
    for day in values['days']:
        day['date'] = (date.fromisoformat(day['date']) + offset).isoformat()
    values['days'][0]['services'][0]['options'][0]['assignments'] = [assignment(revision)]
    expected = {'expected_authz_version': scope.expected_authz_version, 'expected_location_id': scope.location_id}
    version = save_draft(engine, 'patient', date(2026, 9, 7), expected_row_version=1,
                         actor_id=scope.actor_id, values=values, **expected)
    first = state(owner, ids)
    assert first[0][1] == 2 and first[1][0][-1] == ids['location_revision']
    version = save_draft(engine, 'patient', date(2026, 9, 7), expected_row_version=version,
                         actor_id=scope.actor_id, values=values, **expected)
    second = state(owner, ids)
    assert second[0][0] == first[0][0] and second[0][1] == 3
    with pytest.raises(RuntimeError, match='Rezept'):
        import_draft(engine, 'patient', date(2026, 9, 7), expected_row_version=version,
                     actor_id=scope.actor_id, values=values, **expected)
    assert state(owner, ids) == second
