"""Real PostgreSQL weighted full-text search (pg_catalog.german) over the recipe reader
document built at read time (F1/F2 root freeze). No schema change; the search document is
composed per row from title, description, ingredient text/food name and step instructions."""
from __future__ import annotations

import time

import pytest
from sqlalchemy import event, text

from cafeteria import master_data_store as masters, recipe_store as store
from cafeteria.recipe_reads import LIST_RECIPES_SQL, _list_recipes_connection
from cafeteria.recipe_types import RecipeValidationError
from test_master_data_db import signed_in
from test_master_data_routes import (  # noqa: F401
    Forms, app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import line, payload, target, STORAGE_PUBLIC_ID


@pytest.fixture
def search_lab(b3):  # noqa: F811
    app, owner, _, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)

        def food(name):
            return masters.create_food(engine, actor, {'name': name, 'base_unit_code': 'G',
                'storage_location_public_ids': [STORAGE_PUBLIC_ID]})

        def recipe(title, **changes):
            return store.create_recipe(engine, actor, payload(title=title, **changes),
                                       expected_location_id=location)

        yield {'engine': engine, 'owner': owner, 'actor': actor, 'location': location,
               'food': food, 'recipe': recipe}


def step(instruction):
    return {'instruction': instruction, 'duration_minutes': 0, 'image_sha256': None}


def ids(rows):
    return {row.public_id for row in rows}


def test_terms_split_across_title_and_food_match(search_lab):
    lab = search_lab
    lauch = lab['food']('Lauch')
    both = lab['recipe']('Kraftvolle Suppe', ingredients=[line('Frisch', food_public_id=lauch.public_id)])
    lab['recipe']('Kraftvolle Suppe', ingredients=[line('Karotte')])
    lab['recipe']('Herzhafter Auflauf', ingredients=[line('Frisch', food_public_id=lauch.public_id)])
    result = store.list_recipes(lab['engine'], text_search='suppe lauch')
    assert ids(result) == {both.public_id}


def test_ingredient_text_and_step_instruction_are_searchable(search_lab):
    lab = search_lab
    ingredient_hit = lab['recipe']('Herbstgericht', ingredients=[line('Frische Muskatnuss')])
    step_hit = lab['recipe']('Herbstgericht', steps=[step('Sauce langsam passieren')])
    lab['recipe']('Herbstgericht')
    assert ids(store.list_recipes(lab['engine'], text_search='muskatnuss')) == {ingredient_hit.public_id}
    assert ids(store.list_recipes(lab['engine'], text_search='passieren')) == {step_hit.public_id}


def test_ranking_prefers_title_over_steps_then_title_then_uuid(search_lab):
    lab = search_lab
    title_a = lab['recipe']('Zauberwort Auflauf')
    title_b = lab['recipe']('Zauberwort Auflauf')  # identical title/weight -> tie broken by public_id
    step_only = lab['recipe']('Andere Suppe', steps=[step('Zauberwort einruehren')])
    ordered = [row.public_id for row in store.list_recipes(lab['engine'], text_search='zauberwort')]
    tie_pair = sorted((title_a.public_id, title_b.public_id))
    assert ordered == [*tie_pair, step_only.public_id]


def test_kartoffel_suppe_documents_actual_compound_behaviour(search_lab):
    lab = search_lab
    engine = lab['engine']
    split_words = lab['recipe']('Kartoffel Suppe')
    compound = lab['recipe']('Kartoffelsuppe')
    assert ids(store.list_recipes(engine, text_search='kartoffel suppe')) == {split_words.public_id}
    assert ids(store.list_recipes(engine, text_search='kartoffelsuppe')) == {compound.public_id}
    with engine.connect() as current:
        debug = current.execute(text(
            "SELECT token, lexemes FROM ts_debug('pg_catalog.german','Kartoffelsuppe')")).all()
    # Root probe (2026-09-15): to_tsvector('pg_catalog.german','Kartoffelsuppe') = 'kartoffelsupp':1 —
    # the German dictionary stems the compound to a single lexeme, no decompounding into two words,
    # which is exactly why 'kartoffel suppe' (two lexemes, AND-combined) never matches this document.
    assert len(debug) == 1 and debug[0].lexemes == ['kartoffelsupp']


def test_phrase_order_and_distance(search_lab):
    lab = search_lab
    ordered = lab['recipe']('Kartoffel Suppe')
    lab['recipe']('Suppe mit Kartoffel')
    assert ids(store.list_recipes(lab['engine'], text_search='"kartoffel suppe"')) == {ordered.public_id}

    # F7: positions are counted across the E'\n'-joined ingredient document; the last word of
    # one ingredient row and the first word of the next row land on adjacent tsvector positions,
    # so a phrase query can match across two ingredient rows. Documented actual behaviour, not a
    # promise of per-row phrase boundaries.
    cross_line = lab['recipe']('Fruehlingsgericht',
        ingredients=[line('Geriebener Ingwer'), line('Kurkuma Frisch')])
    assert ids(store.list_recipes(lab['engine'], text_search='"ingwer kurkuma"')) == {cross_line.public_id}


def test_archive_location_and_tag_filters_still_apply_with_text_search(search_lab):
    lab = search_lab
    engine, owner, actor, location = lab['engine'], lab['owner'], lab['actor'], lab['location']
    tag = masters.create_vocabulary(engine, 'tag', actor, code='SEARCHTAG', name='Suchtag')
    tagged = lab['recipe']('Geheime Fischsuppe', tag_public_ids=[tag.public_id])
    untagged = lab['recipe']('Offene Fischsuppe')
    archived_hit = lab['recipe']('Archivierte Fischsuppe')
    store.set_recipe_active(engine, actor, target(archived_hit), active=False, expected_location_id=location)
    with owner.begin() as current:
        foreign_location = current.execute(text(
            "INSERT INTO cafeteria.locations(code,name,active) "
            "VALUES('FTS_OTHER','Fremdes FTS-Haus',false) RETURNING id")).scalar_one()
        current.execute(text("INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,"
            "servings,servings_unit_id,source_kind) SELECT :location,:actor,:actor,'Fremde Fischsuppe',"
            "4,id,'manual' FROM cafeteria.measurement_units WHERE code='PORTION'"),
            {'location': foreign_location, 'actor': actor.user_id})

    active_only = store.list_recipes(engine, text_search='fischsuppe')
    assert ids(active_only) == {tagged.public_id, untagged.public_id}

    with_archived = store.list_recipes(engine, text_search='fischsuppe', include_archived=True)
    assert ids(with_archived) == {tagged.public_id, untagged.public_id, archived_hit.public_id}

    tagged_only = store.list_recipes(engine, text_search='fischsuppe', tag=tag.public_id)
    assert ids(tagged_only) == {tagged.public_id}


def test_existing_filters_unchanged_without_text_search(search_lab):
    lab = search_lab
    engine = lab['engine']
    lauch = lab['food']('Lauch')
    alpha = lab['recipe']('Alpha Suppe', ingredients=[line('Frisch', food_public_id=lauch.public_id)])
    beta = lab['recipe']('Beta Suppe')
    without_text_search = store.list_recipes(engine, search='suppe')
    assert [row.public_id for row in without_text_search] == [alpha.public_id, beta.public_id]
    ingredient_filtered = store.list_recipes(engine, ingredient='lauch')
    assert ids(ingredient_filtered) == {alpha.public_id}


def test_food_rename_visible_only_in_new_read_transaction_without_blocking(search_lab):
    lab = search_lab
    engine, actor, location = lab['engine'], lab['actor'], lab['location']
    food_item = lab['food']('Sellerie')
    recipe = lab['recipe']('Wurzelgemuese', ingredients=[line('Frisch', food_public_id=food_item.public_id)])

    def values(term):
        return {'archived': False, 'limit': 200, 'offset': 0, 'search': '', 'ingredient': '',
                'tag': None, 'text_search': term, 'location': location}

    def guard_lock_timeout(conn):
        conn.execute(text("SET LOCAL lock_timeout='2s'"))

    with engine.begin() as reader:
        reader.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        assert ids(_list_recipes_connection(reader, values('sellerie'))) == {recipe.public_id}

        event.listen(engine, 'begin', guard_lock_timeout)
        try:
            started = time.monotonic()
            masters.update_food(engine, actor, target(food_item), {'name': 'Petersilienwurzel',
                'base_unit_code': 'G', 'storage_location_public_ids': [STORAGE_PUBLIC_ID]})
            elapsed = time.monotonic() - started
        finally:
            event.remove(engine, 'begin', guard_lock_timeout)
        assert elapsed < 2.0  # committed without waiting for the open RR READ ONLY reader

        # F9: the reader's RR READ ONLY snapshot predates the rename commit — still the old name.
        assert ids(_list_recipes_connection(reader, values('sellerie'))) == {recipe.public_id}
        assert _list_recipes_connection(reader, values('petersilienwurzel')) == ()

    with engine.begin() as fresh_reader:
        fresh_reader.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        assert ids(_list_recipes_connection(fresh_reader, values('petersilienwurzel'))) == {recipe.public_id}
        assert _list_recipes_connection(fresh_reader, values('sellerie')) == ()


def test_stopword_only_query_returns_no_rows_and_blank_is_ignored(search_lab):
    lab = search_lab
    engine = lab['engine']
    baseline = lab['recipe']('Herbstsuppe')
    # F4: whitespace-only input disables the filter after strip() -> identical to no text_search.
    blank = store.list_recipes(engine, text_search='   ')
    without_filter = store.list_recipes(engine)
    assert [row.public_id for row in blank] == [row.public_id for row in without_filter]
    assert baseline.public_id in ids(blank)
    # F4: a query consisting only of German stopwords yields zero rows, not an exception.
    assert store.list_recipes(engine, text_search='und der') == ()


@pytest.mark.parametrize('value', [True, 3, ['x'], 'x' * 201, '\x00'])
def test_invalid_text_search_rejected_before_database(value):
    from cafeteria.recipe_reads import list_recipes
    with pytest.raises(RecipeValidationError):
        list_recipes(None, text_search=value)


def test_search_timing_and_explain_on_realistic_volume(search_lab):
    lab = search_lab
    owner, actor, location, engine = lab['owner'], lab['actor'], lab['location'], lab['engine']
    target_hit = lab['recipe']('Zielrezept Feuerprobe', ingredients=[line('Wuerzige Chiliflocke')],
        steps=[step('Feuerprobe langsam abschmecken')])
    with owner.begin() as current:
        current.execute(text('''INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,
                description,servings,servings_unit_id,source_kind)
            SELECT :location,:actor,:actor,'Messrezept '||lpad(n::text,4,'0'),
                'Messbeschreibung fuer Volumentest '||n,4,u.id,'manual'
            FROM generate_series(1,320) n CROSS JOIN cafeteria.measurement_units u
            WHERE u.code='PORTION' '''), {'location': location, 'actor': actor.user_id})
        current.execute(text('''INSERT INTO cafeteria.recipe_ingredients(
                location_id,recipe_id,sort_order,ingredient_text,source_kind)
            SELECT r.location_id,r.id,g,'Zutat '||g||' fuer Rezept '||r.id,'manual'
            FROM cafeteria.recipes r CROSS JOIN generate_series(1,16) g
            WHERE r.location_id=:location AND r.title LIKE 'Messrezept %' '''), {'location': location})
        current.execute(text('''INSERT INTO cafeteria.recipe_steps(
                location_id,recipe_id,step_number,instruction)
            SELECT r.location_id,r.id,g,'Schritt '||g||' fuer Rezept '||r.id||' langsam kochen'
            FROM cafeteria.recipes r CROSS JOIN generate_series(1,6) g
            WHERE r.location_id=:location AND r.title LIKE 'Messrezept %' '''), {'location': location})
        recipe_count = current.execute(text(
            "SELECT count(*) FROM cafeteria.recipes WHERE location_id=:location"), {'location': location}).scalar_one()
    assert recipe_count >= 300

    values = {'archived': False, 'limit': 200, 'offset': 0, 'search': '', 'ingredient': '',
              'tag': None, 'text_search': 'feuerprobe', 'location': location}
    with engine.begin() as current:
        current.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        started = time.monotonic()
        result = _list_recipes_connection(current, values)
        elapsed = time.monotonic() - started
        explain = current.execute(text('EXPLAIN (ANALYZE, BUFFERS) ' + LIST_RECIPES_SQL), values).all()
    assert ids(result) == {target_hit.public_id}
    assert elapsed <= 2.0
    plan = '\n'.join(row[0] for row in explain)
    assert 'Execution Time' in plan
    print(f'\n--- EXPLAIN (ANALYZE, BUFFERS) list_recipes text_search on {recipe_count} recipes '
          f'(≥15 ingredients, ≥5 steps each) ---\n{plan}\n--- elapsed(python)={elapsed:.4f}s ---')
