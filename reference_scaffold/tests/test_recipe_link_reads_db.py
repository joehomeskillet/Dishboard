"""Real scoped read-role projections, page bounds and immutable reference metadata."""
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from cafeteria import recipe_link_reads as links
from cafeteria.auth.local_users import ActorExpectation
from cafeteria.recipe_types import RecipeValidationError
from test_dish_template_routes import foreign_recipe, make_recipe
from test_master_data_db import signed_in
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_menu_binding_db import binding  # noqa: F401


def seed_recipe_page(owner, actor, count=205):
    """Synthetic lightweight recipe heads; no production import or payload snapshots."""
    with owner.begin() as current:
        return tuple(str(value) for value in current.execute(text('''
            INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,
                servings,servings_unit_id,source_kind)
            SELECT l.id,:actor,:actor,'Rezept '||lpad(n::text,3,'0'),4,u.id,'manual'
            FROM generate_series(1,:count) n CROSS JOIN cafeteria.locations l
            CROSS JOIN cafeteria.measurement_units u WHERE l.active AND u.code='PORTION'
            RETURNING public_id'''), {'actor': actor.user_id, 'count': count}).scalars())


def test_links_follow_all_existing_edges_and_do_not_multiply_counts(binding, monkeypatch):  # noqa: F811
    owner, engine, ids = binding
    actor = ActorExpectation(ids['actor'], ids['authz'])
    with owner.begin() as current:
        recipe_id = str(current.execute(text('SELECT public_id FROM cafeteria.recipes WHERE id=:location_recipe'), ids).scalar_one())
        foreign = str(current.execute(text('SELECT public_id FROM cafeteria.recipes WHERE id=:other_location_recipe'), ids).scalar_one())
        refs = current.execute(text('''INSERT INTO cafeteria.dish_templates(title,recipe_id,active)
            VALUES ('Zweite',:location_recipe,true),('Archivierte',:location_recipe,false),
                   ('Fremde Vorlage',:other_location_recipe,true) RETURNING public_id,title'''), ids).all()
        current.execute(text('''UPDATE cafeteria.menu_items SET dish_template_id=(
            SELECT id FROM cafeteria.dish_templates WHERE title='Zweite') WHERE id=:item'''), ids)
        latest = current.execute(text('''INSERT INTO cafeteria.recipe_revisions(
            location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
            VALUES(:location,:location_recipe,2,'{}',encode(pg_catalog.sha256(convert_to('{}','UTF8')),'hex'),:actor)
            RETURNING public_id,created_at'''), ids).one()
        current.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:location_recipe'), ids)
    original = links.reads.connection
    @contextmanager
    def checked_connection(db):
        with original(db) as (current, location):
            assert current.execute(text('SHOW transaction_isolation')).scalar_one() == 'repeatable read'
            assert current.execute(text('SHOW transaction_read_only')).scalar_one() == 'on'
            yield current, location
    monkeypatch.setattr(links.reads, 'connection', checked_connection)
    statements = []
    def record(_conn, _cursor, statement, _parameters, _context, _many):
        if 'FROM cafeteria.recipes r' in statement or 'FROM cafeteria.dish_templates d' in statement:
            statements.append(statement)
    event.listen(engine, 'before_cursor_execute', record)
    try:
        with signed_in(engine, actor):
            reverse = links.list_recipe_links(engine, [recipe_id, foreign, str(uuid4())])
            assert len(statements) == 1
            assert set(reverse) == {recipe_id}
            assert [row.title for row in reverse[recipe_id].templates] == ['Archivierte', 'Zweite']
            assert reverse[recipe_id].latest_revision.public_id == str(latest.public_id)
            assert reverse[recipe_id].latest_revision.revision_number == 2
            assert reverse[recipe_id].latest_revision.created_at == latest.created_at
            statements.clear()
            rows = links.list_template_links(engine, include_archived=True)
            assert len(statements) == 1
            assert {row.public_id for row in rows} == {str(row.public_id) for row in refs if row.title != 'Fremde Vorlage'}
            assert all(row.recipe_active is False and row.revision_count == 2 for row in rows)
            assert {row.title: row.menu_count for row in rows} == {'Archivierte': 0, 'Zweite': 1}
    finally:
        event.remove(engine, 'before_cursor_execute', record)


def test_choice_page_is_bounded_searchable_and_retains_archived_or_foreign_selection(b3):  # noqa: F811
    app, owner, _, actor = b3
    engine = app.extensions['cafeteria_db']
    ids = seed_recipe_page(owner, actor)
    foreign = foreign_recipe(owner, actor)
    with signed_in(engine, actor):
        first = links.list_recipe_choices(engine, selected=ids[-1])
        assert len(first.choices) == 50 and first.has_next
        assert first.retained.public_id == ids[-1]
        last = links.list_recipe_choices(engine, offset=200)
        assert len(last.choices) == 5 and not last.has_next
        search = links.list_recipe_choices(engine, search='205', selected=ids[0])
        assert [row.public_id for row in search.choices] == [ids[-1]]
        assert search.retained.public_id == ids[0]
        assert not links.list_recipe_choices(engine, search="%' OR true --").choices
        hidden = links.list_recipe_choices(engine, selected=foreign)
        assert hidden.retained.title == 'Rezept nicht verfügbar' and not hidden.retained.available
    with owner.begin() as current:
        current.execute(text('UPDATE cafeteria.recipes SET active=false WHERE public_id=CAST(:id AS uuid)'), {'id': ids[0]})
    with signed_in(engine, actor):
        archived = links.list_recipe_choices(engine, selected=ids[0])
        assert archived.retained.public_id == ids[0] and not archived.retained.active
        assert ids[0] not in {row.public_id for row in archived.choices}


@pytest.mark.parametrize('options', [{'offset': -1}, {'offset': True}, {'search': '\x00'}, {'search': 'x' * 201}])
def test_invalid_choice_query_is_rejected(b3, options):  # noqa: F811
    app, _, _, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor), pytest.raises(RecipeValidationError):
        links.list_recipe_choices(engine, **options)


def test_recipe_without_template_or_revision_has_explicit_empty_projection(b3):  # noqa: F811
    app, _, _, actor = b3
    engine = app.extensions['cafeteria_db']
    recipe = make_recipe(engine, actor)
    with signed_in(engine, actor):
        row = links.list_recipe_links(engine, [recipe.public_id])[recipe.public_id]
    assert row.templates == () and row.latest_revision is None
