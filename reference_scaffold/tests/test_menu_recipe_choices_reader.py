"""Bounded immutable recipe-choice reader: labels, ordering, retention and query cost.

Fixtures freeze revisions with the real producer `cafeteria.recipe_snapshot_v22`
and the same digest expression the freeze verb uses, so a label assertion is made
against genuine stored snapshot bytes rather than a placeholder object.
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import pytest
from flask import Flask, session
from sqlalchemy import Engine, event, text
from werkzeug.exceptions import Unauthorized

from test_rendered_ui import admin_app, admin_engine  # noqa: F401
from test_admin_workflow_routes import _login

from cafeteria.menu_recipe_choices import RecipeChoicePage, RecipeChoiceQuery, list_recipe_choices

_FREEZE = '''INSERT INTO cafeteria.recipe_revisions(location_id,recipe_id,revision_number,
    snapshot_json,content_hash_sha256,created_by)
    SELECT r.location_id,r.id,
     COALESCE((SELECT max(h.revision_number) FROM cafeteria.recipe_revisions h WHERE h.recipe_id=r.id),0)+1,
     cafeteria.recipe_snapshot_v22(r.id),
     encode(public.digest(convert_to(cafeteria.recipe_snapshot_v22(r.id)::text,'UTF8'),'sha256'),'hex'),
     :actor
    FROM cafeteria.recipes r WHERE r.id=:recipe
    RETURNING public_id::text AS public_id,content_hash_sha256,revision_number'''
_NEW_RECIPE = '''INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,servings,
    servings_unit_id,source_kind,active)
    SELECT :location,:actor,:actor,:title,CAST(:servings AS numeric),id,'manual',:active
    FROM cafeteria.measurement_units WHERE code='PORTION' RETURNING id'''


def active_location(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(
            text('SELECT id FROM cafeteria.locations WHERE active ORDER BY id')).scalar_one())


def create_recipe(engine: Engine, actor_id: int, title: str, *, servings: str = '4',
                  location_id: int | None = None, active: bool = True) -> int:
    """Create one recipe head; the frozen label is produced later by freeze_revision."""
    with engine.begin() as connection:
        if location_id is None:
            location_id = int(connection.execute(
                text('SELECT id FROM cafeteria.locations WHERE active ORDER BY id')).scalar_one())
        return int(connection.execute(text(_NEW_RECIPE), {
            'location': location_id, 'actor': actor_id, 'title': title,
            'servings': servings, 'active': active}).scalar_one())


def update_head(engine: Engine, actor_id: int, recipe_id: int, *, title: str | None = None,
                servings: str | None = None) -> None:
    """Mutate the current recipe head; frozen revisions must not follow this change."""
    with engine.begin() as connection:
        connection.execute(text('''UPDATE cafeteria.recipes
            SET title=COALESCE(:title,title),servings=COALESCE(CAST(:servings AS numeric),servings),
                updated_by=:actor WHERE id=:recipe'''),
            {'title': title, 'servings': servings, 'actor': actor_id, 'recipe': recipe_id})


def freeze_revision(engine: Engine, actor_id: int, recipe_id: int) -> dict[str, str]:
    """Freeze the current head with the production snapshot producer and digest."""
    with engine.begin() as connection:
        row = connection.execute(text(_FREEZE), {'actor': actor_id, 'recipe': recipe_id}).one()
    return {'public_id': str(row.public_id), 'hash': str(row.content_hash_sha256),
            'number': str(row.revision_number)}


def set_recipe_active(engine: Engine, actor_id: int, recipe_id: int, *, active: bool) -> None:
    with engine.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.recipes SET active=:active,updated_by=:actor WHERE id=:recipe'),
            {'active': active, 'actor': actor_id, 'recipe': recipe_id})


def insert_corrupt_revision(engine: Engine, actor_id: int, recipe_id: int) -> str:
    """A stored revision without snapshot title/yield; the head must not fill the gap."""
    with engine.begin() as connection:
        return str(connection.execute(text(
            '''INSERT INTO cafeteria.recipe_revisions(location_id,recipe_id,revision_number,
               snapshot_json,content_hash_sha256,created_by)
               SELECT r.location_id,r.id,
                COALESCE((SELECT max(h.revision_number) FROM cafeteria.recipe_revisions h
                          WHERE h.recipe_id=r.id),0)+1,
                CAST(:snapshot AS jsonb),
                encode(public.digest(convert_to(CAST(:snapshot AS jsonb)::text,'UTF8'),'sha256'),'hex'),
                :actor
               FROM cafeteria.recipes r WHERE r.id=:recipe RETURNING public_id::text'''),
            {'snapshot': '{"schema_version": 1, "recipe": {}}', 'actor': actor_id,
             'recipe': recipe_id}).scalar_one())


@contextmanager
def counted(engine: Engine) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(connection, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        statements.append(statement)

    event.listen(engine, 'before_cursor_execute', record)
    try:
        yield statements
    finally:
        event.remove(engine, 'before_cursor_execute', record)


@pytest.fixture
def reader(admin_app: Flask, admin_engine: Engine):  # noqa: F811
    _, actor_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with admin_engine.connect() as connection:
        authz = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': actor_id}).scalar_one()

    def call(selected: Sequence[object] = (), **query: object) -> RecipeChoicePage:
        with admin_app.test_request_context():
            session['user'] = {'id': int(actor_id), 'name': 'Küche'}
            session['authz_version'] = int(authz)
            return list_recipe_choices(admin_engine, list(selected), RecipeChoiceQuery(**query))

    return call, int(actor_id), admin_engine


def _by_id(page: RecipeChoicePage, revision_public_id: str):
    for choice in (*page.choices, *page.retained):
        if choice.revision_public_id == revision_public_id:
            return choice
    return None


def test_changed_head_never_relabels_a_frozen_revision(reader) -> None:
    call, actor_id, engine = reader
    recipe_id = create_recipe(engine, actor_id, 'Alte Kürbissuppe', servings='4')
    first = freeze_revision(engine, actor_id, recipe_id)
    update_head(engine, actor_id, recipe_id, title='Neue Kürbissuppe', servings='8')
    second = freeze_revision(engine, actor_id, recipe_id)

    page = call(search='Kürbissuppe')
    old, new = _by_id(page, first['public_id']), _by_id(page, second['public_id'])
    assert old is not None and new is not None
    assert (old.title, old.yield_label, old.revision_number) == ('Alte Kürbissuppe', '4 PORTION', 1)
    assert (new.title, new.yield_label, new.revision_number) == ('Neue Kürbissuppe', '8 PORTION', 2)
    assert old.content_hash_sha256 == first['hash'] and new.content_hash_sha256 == second['hash']
    assert old.content_hash_sha256 != new.content_hash_sha256
    assert old.selectable and new.selectable


def test_corrupt_snapshot_stays_bound_but_never_borrows_head_metadata(reader) -> None:
    call, actor_id, engine = reader
    recipe_id = create_recipe(engine, actor_id, 'Beschädigte Bindung', servings='6')
    corrupt = insert_corrupt_revision(engine, actor_id, recipe_id)

    page = call([corrupt], search='Beschädigte')
    choice = _by_id(page, corrupt)
    assert choice is not None
    assert choice.title == '' and choice.yield_label == ''
    assert choice.metadata_available is False and choice.selectable is False
    assert choice.revision_public_id == corrupt


def test_page_is_bounded_deterministic_and_reports_a_real_next_page(reader) -> None:
    call, actor_id, engine = reader
    for index in range(1, 8):
        recipe_id = create_recipe(engine, actor_id, f'Reihensuppe {index:03d}')
        freeze_revision(engine, actor_id, recipe_id)

    first = call(search='Reihensuppe', limit=3)
    assert len(first.choices) == 3 and first.has_next is True
    assert first.next_offset == 3 and first.previous_offset is None
    assert call(search='Reihensuppe', limit=3).choices == first.choices

    second = call(search='Reihensuppe', limit=3, offset=3)
    third = call(search='Reihensuppe', limit=3, offset=6)
    assert second.previous_offset == 0 and third.has_next is False and third.next_offset is None
    titles = [choice.title for choice in (*first.choices, *second.choices, *third.choices)]
    assert titles == sorted(titles) and len(set(titles)) == 7


def test_recipe_201_and_revision_51_are_reachable_with_finite_actions(reader) -> None:
    call, actor_id, engine = reader
    location_id = active_location(engine)
    with engine.begin() as connection:
        ids = [int(row.id) for row in connection.execute(text(
            '''INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,servings,
               servings_unit_id,source_kind,active)
               SELECT :location,:actor,:actor,'Serienrezept '||to_char(n,'FM000'),4,u.id,'manual',true
               FROM generate_series(1,201) n,cafeteria.measurement_units u
               WHERE u.code='PORTION' RETURNING id'''),
            {'location': location_id, 'actor': actor_id})]
        connection.execute(text(
            '''INSERT INTO cafeteria.recipe_revisions(location_id,recipe_id,revision_number,
               snapshot_json,content_hash_sha256,created_by)
               SELECT r.location_id,r.id,1,cafeteria.recipe_snapshot_v22(r.id),
                encode(public.digest(convert_to(cafeteria.recipe_snapshot_v22(r.id)::text,'UTF8'),'sha256'),'hex'),
                :actor
               FROM cafeteria.recipes r WHERE r.id=ANY(:ids)'''),
            {'actor': actor_id, 'ids': ids})
    assert len(ids) == 201

    searched = call(search='Serienrezept 201')
    assert [choice.title for choice in searched.choices] == ['Serienrezept 201']
    assert searched.has_next is False
    paged = call(search='Serienrezept', limit=50, offset=200)
    assert [choice.title for choice in paged.choices] == ['Serienrezept 201']

    deep = create_recipe(engine, actor_id, 'Tiefe Revisionen', servings='1')
    frozen = [freeze_revision(engine, actor_id, deep)]
    for number in range(2, 52):
        update_head(engine, actor_id, deep, servings=str(number))
        frozen.append(freeze_revision(engine, actor_id, deep))
    assert frozen[-1]['number'] == '51'

    head = call(search='Tiefe Revisionen', limit=50)
    tail = call(search='Tiefe Revisionen', limit=50, offset=50)
    numbers = [choice.revision_number for choice in (*head.choices, *tail.choices)]
    assert numbers == list(range(51, 0, -1))
    assert tail.choices[0].revision_public_id == frozen[0]['public_id']
    assert tail.choices[0].yield_label == '1 PORTION'


def test_selected_archived_and_outside_page_options_are_retained(reader) -> None:
    call, actor_id, engine = reader
    archived_id = create_recipe(engine, actor_id, 'Archivierte Sauce')
    archived = freeze_revision(engine, actor_id, archived_id)
    set_recipe_active(engine, actor_id, archived_id, active=False)
    outside_id = create_recipe(engine, actor_id, 'Ausserhalb der Seite')
    outside = freeze_revision(engine, actor_id, outside_id)

    page = call([archived['public_id'], outside['public_id']], search='Archivierte', limit=50)
    offered = {choice.revision_public_id for choice in page.choices}
    assert archived['public_id'] not in offered and outside['public_id'] not in offered
    retained = {choice.revision_public_id: choice for choice in page.retained}
    assert set(retained) == {archived['public_id'], outside['public_id']}
    assert retained[archived['public_id']].recipe_active is False
    assert retained[archived['public_id']].selectable is False
    assert retained[archived['public_id']].title == 'Archivierte Sauce'
    assert retained[outside['public_id']].selectable is True
    assert call([outside['public_id']], search='Ausserhalb').retained == ()


def test_foreign_and_malformed_selections_disclose_nothing(reader) -> None:
    call, actor_id, engine = reader
    with engine.begin() as connection:
        foreign_location = int(connection.execute(text(
            "INSERT INTO cafeteria.locations(code,name,active) VALUES('FREMD','Fremdes Haus',false)"
            ' RETURNING id')).scalar_one())
    foreign_recipe = create_recipe(engine, actor_id, 'Fremde Suppe', location_id=foreign_location)
    foreign = freeze_revision(engine, actor_id, foreign_recipe)

    page = call([foreign['public_id'], 'not-a-uuid'], search='keine-treffer-erwartet')
    assert page.choices == ()
    values = {choice.revision_public_id: choice for choice in page.retained}
    assert set(values) == {foreign['public_id'], 'not-a-uuid'}
    for choice in values.values():
        assert choice.title == '' and choice.yield_label == '' and choice.recipe_public_id == ''
        assert choice.content_hash_sha256 == '' and choice.revision_number is None
        assert choice.metadata_available is False and choice.selectable is False


def test_query_count_and_rows_stay_bounded_independent_of_recipe_count(reader) -> None:
    call, actor_id, engine = reader
    for index in range(4):
        recipe_id = create_recipe(engine, actor_id, f'Kleiner Bestand {index}')
        freeze_revision(engine, actor_id, recipe_id)
    with counted(engine) as small:
        small_page = call(limit=5)
    small_reads = [statement for statement in small if 'recipe_revisions' in statement]

    location_id = active_location(engine)
    with engine.begin() as connection:
        ids = [int(row.id) for row in connection.execute(text(
            '''INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,servings,
               servings_unit_id,source_kind,active)
               SELECT :location,:actor,:actor,'Grosser Bestand '||to_char(n,'FM000'),4,u.id,'manual',true
               FROM generate_series(1,60) n,cafeteria.measurement_units u
               WHERE u.code='PORTION' RETURNING id'''),
            {'location': location_id, 'actor': actor_id})]
        connection.execute(text(
            '''INSERT INTO cafeteria.recipe_revisions(location_id,recipe_id,revision_number,
               snapshot_json,content_hash_sha256,created_by)
               SELECT r.location_id,r.id,1,cafeteria.recipe_snapshot_v22(r.id),
                encode(public.digest(convert_to(cafeteria.recipe_snapshot_v22(r.id)::text,'UTF8'),'sha256'),'hex'),
                :actor
               FROM cafeteria.recipes r WHERE r.id=ANY(:ids)'''),
            {'actor': actor_id, 'ids': ids})
    with counted(engine) as large:
        large_page = call(limit=5)

    assert len(small_reads) == 1 and len(small) == len(large)
    assert len(large_page.choices) == 5 and len(small_page.choices) == 4
    assert large_page.has_next is True and small_page.has_next is False


def test_selected_lookup_adds_exactly_one_bounded_statement(reader) -> None:
    call, actor_id, engine = reader
    recipe_id = create_recipe(engine, actor_id, 'Gebundene Referenz')
    revision = freeze_revision(engine, actor_id, recipe_id)
    with counted(engine) as without:
        call(search='Gebundene Referenz')
    with counted(engine) as with_selection:
        page = call([revision['public_id']], search='keine-treffer-erwartet')
    assert len(with_selection) == len(without) + 1
    assert len(page.retained) == 1 and page.retained[0].title == 'Gebundene Referenz'


def test_reader_rejects_a_user_without_an_active_role(admin_app: Flask, admin_engine: Engine) -> None:  # noqa: F811
    _, actor_id = _login(admin_app, admin_engine, [])
    with admin_engine.connect() as connection:
        authz = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': actor_id}).scalar_one()
    with admin_app.test_request_context():
        session['user'] = {'id': int(actor_id), 'name': 'Küche'}
        session['authz_version'] = int(authz)
        with counted(admin_engine) as statements:
            with pytest.raises(Unauthorized) as denied:
                list_recipe_choices(admin_engine, [], RecipeChoiceQuery())
        assert denied.value.code == 401
        assert not any('recipe_revisions' in statement.lower() for statement in statements)
