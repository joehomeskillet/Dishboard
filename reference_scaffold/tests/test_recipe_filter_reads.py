"""Real PostgreSQL literal filters, location boundaries and stable native pagination."""
from html import unescape
import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from cafeteria import master_data_store as masters, recipe_store as store, roles
from cafeteria.admin import recipe_routes as routes
from cafeteria.recipe_types import RecipeValidationError
from test_master_data_db import signed_in
from test_master_data_routes import (  # noqa: F401
    Forms, app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import line, payload, snapshot, target


@pytest.fixture
def filter_catalog(b3):  # noqa: F811
    app, owner, _, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        tag = masters.create_vocabulary(engine, 'tag', actor, code='REGIONAL', name='Regional')
        food = masters.create_food(engine, actor, {'name': 'Rüebli', 'base_unit_code': 'G'})
        rows = {}
        specimens = [
            ('mapped', 'Suppe', [line('Wurzel', food_public_id=food.public_id),
                                 line('Wurzel fein', food_public_id=food.public_id)], [tag.public_id]),
            ('text', 'Suppe', [line('RÜEBLI')], [tag.public_id]),
            ('untagged', 'Suppe ohne Tag', [line('Rüebli')], []),
            ('other', 'Andere Suppe', [line('Kartoffel')], [tag.public_id]),
            ('archived', 'Archivierte Suppe', [line('Rüebli')], [tag.public_id]),
            ('literal', "100%_Suppe", [line("Crème 10%_d'Äpfel")], []),
        ]
        for key, title, ingredients, tags in specimens:
            rows[key] = store.create_recipe(engine, actor, payload(title=title, ingredients=ingredients,
                tag_public_ids=tags), expected_location_id=location)
        store.set_recipe_active(engine, actor, target(rows['archived']), active=False, expected_location_id=location)
        store.freeze_revision(engine, actor, target(rows['mapped']), expected_location_id=location)
        masters.set_food_active(engine, actor, target(food), active=False)
        masters.set_vocabulary_active(engine, 'tag', actor, target(tag), active=False)
    with owner.begin() as current:
        foreign_location = current.execute(text("INSERT INTO cafeteria.locations(code,name,active) "
            "VALUES('FILTER_OTHER','Fremdes Haus',false) RETURNING id")).scalar_one()
        foreign_tag = current.execute(text("INSERT INTO cafeteria.tags(location_id,code,name) "
            "VALUES(:location,'SECRET','Fremder geheimer Tag') RETURNING public_id"),
            {'location': foreign_location}).scalar_one()
        current.execute(text("INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,"
            "servings,servings_unit_id,source_kind) SELECT :location,:actor,:actor,'Fremde Suppe',"
            "4,id,'manual' FROM cafeteria.measurement_units WHERE code='PORTION'"),
            {'location': foreign_location, 'actor': actor.user_id})
        current.execute(text("INSERT INTO cafeteria.recipe_ingredients(location_id,recipe_id,sort_order,"
            "ingredient_text,source_kind) SELECT location_id,id,1,'Rüebli','manual' "
            "FROM cafeteria.recipes WHERE location_id=:location"), {'location': foreign_location})
        current.execute(text("INSERT INTO cafeteria.recipe_tags(location_id,recipe_id,tag_id) "
            "SELECT r.location_id,r.id,t.id FROM cafeteria.recipes r JOIN cafeteria.tags t "
            "ON t.location_id=r.location_id WHERE r.location_id=:location"), {'location': foreign_location})
    return {'rows': rows, 'tag': tag.public_id, 'foreign_tag': str(foreign_tag)}


def complete_snapshot(owner):
    result = snapshot(owner)
    with owner.connect() as current:
        for table in ('foods', 'tags'):
            result[table] = current.execute(text(
                f'SELECT to_jsonb(t)::text FROM cafeteria.{table} t ORDER BY to_jsonb(t)::text')).all()
    return result


def recipe_ids(html):
    return re.findall(r'href="/admin/rezepte/([0-9a-f-]{36})"', html)


def page_link(html, page):
    return next(url for url in map(unescape, re.findall(r'href="([^"]+)"', html))
                if parse_qs(urlsplit(url).query).get('page') == [str(page)])


def seed_pages(fixture, count=53):
    app, _, _, actor = fixture
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        tag = masters.create_vocabulary(engine, 'tag', actor, code='PAGE', name='Wochenküche')
        location = store.get_location(engine)
        result = [store.create_recipe(engine, actor,
            payload(title=f'Seitensuppe {index:03}', ingredients=[line('Rüebli'), line('Rüebli fein')],
                    tag_public_ids=[tag.public_id]), expected_location_id=location).public_id
            for index in range(1, count + 1)]
    return tag.public_id, result


def test_literal_and_combined_filters_keep_archived_associations_and_identity(b3, filter_catalog):  # noqa: F811
    app, owner, _, actor = b3
    engine, rows = app.extensions['cafeteria_db'], filter_catalog['rows']
    before = complete_snapshot(owner)
    cases = [
        ({'ingredient': 'rÜeBlI'}, {'mapped', 'text', 'untagged'}),
        ({'ingredient': 'wurzel'}, {'mapped'}),
        ({'tag': filter_catalog['tag']}, {'mapped', 'text', 'other'}),
        ({'search': 'suppe', 'ingredient': 'rüebli', 'tag': filter_catalog['tag']}, {'mapped', 'text'}),
        ({'ingredient': 'rüebli', 'tag': filter_catalog['tag'], 'include_archived': True}, {'mapped', 'text', 'archived'}),
        ({'ingredient': "10%_d'äpfel"}, {'literal'}),
        ({'search': '%_', 'ingredient': '%_'}, {'literal'}),
        ({'ingredient': 'Crème'}, {'literal'}),
        ({'ingredient': 'Kartoffel', 'search': '100%'}, set()),
        ({'tag': filter_catalog['foreign_tag']}, set()),
        ({'tag': str(uuid4())}, set()),
    ]
    with signed_in(engine, actor):
        for filters, expected in cases:
            actual = store.list_recipes(engine, **filters)
            assert {row.public_id for row in actual} == {rows[key].public_id for key in expected}
            assert len(actual) == len(expected)
        duplicates = store.list_recipes(engine, ingredient='rüebli', tag=filter_catalog['tag'])
        assert [row.public_id for row in duplicates] == sorted(rows[key].public_id for key in ('mapped', 'text'))
    assert complete_snapshot(owner) == before


@pytest.mark.parametrize('filters', [
    {'ingredient': 'x' * 201}, {'ingredient': True}, {'ingredient': 3}, {'ingredient': '\x00'},
    {'tag': 'invalid'}, {'tag': False}, {'tag': 3}, {'tag': []}, {'search': '\x00'},
])
def test_reader_rejects_invalid_filters_before_database(filters):
    from cafeteria.recipe_reads import list_recipes
    with pytest.raises(RecipeValidationError):
        list_recipes(None, **filters)


def test_http_filter_pagination_retains_all_args_without_duplicates_or_writes(b3):  # noqa: F811
    _, owner, client, _ = b3
    tag, expected = seed_pages(b3)
    before = complete_snapshot(owner)
    filters = {'q': 'Seitensuppe', 'ingredient': 'rÜeBlI', 'tag': tag, 'archived': '1'}
    first = client.get('/admin/rezepte', query_string=filters)
    assert first.status_code == 200 and first.headers['Cache-Control'] == 'no-store'
    first_ids = recipe_ids(first.text)
    assert first_ids == expected[:50]
    next_url = page_link(first.text, 2)
    assert parse_qs(urlsplit(next_url).query) == {key: [value] for key, value in (filters | {'page': '2'}).items()}
    second = client.get(next_url)
    assert recipe_ids(second.text) == expected[50:]
    previous = client.get(page_link(second.text, 1))
    assert recipe_ids(previous.text) == first_ids
    reset = client.get('/admin/rezepte')
    data = Forms(reset.text).forms['/admin/rezepte']
    assert data['q'] == data['ingredient'] == data['tag'] == '' and 'archived' not in data
    assert complete_snapshot(owner) == before


@pytest.mark.parametrize('query', [
    [('ingredient', 'a'), ('ingredient', 'b')], [('tag', ''), ('tag', '')],
    {'ingredient': 'x' * 201}, {'ingredient': '\x00'}, {'tag': 'invalid'}, {'unknown': '1'},
])
def test_http_rejects_ambiguous_or_invalid_filter_query(b3, query):  # noqa: F811
    response = b3[2].get('/admin/rezepte', query_string=query)
    assert response.status_code == 400 and response.headers['Cache-Control'] == 'no-store'


def test_stale_archived_and_foreign_tags_are_safe_selected_choices(b3, filter_catalog):  # noqa: F811
    client = b3[2]
    for tag in (filter_catalog['foreign_tag'], str(uuid4())):
        response = client.get('/admin/rezepte', query_string={'tag': tag.upper()})
        assert response.status_code == 200 and 'Keine passenden Rezepte' in response.text
        assert 'Fremder geheimer Tag' not in response.text and 'Fremde Suppe' not in response.text
        assert 'Ausgewählter Tag · nicht mehr verfügbar' in response.text
        assert Forms(response.text).forms['/admin/rezepte']['tag'] == tag
    response = client.get('/admin/rezepte', query_string={'tag': filter_catalog['tag']})
    assert 'Regional · archiviert' in response.text
    assert Forms(response.text).forms['/admin/rezepte']['tag'] == filter_catalog['tag']


def test_filters_preserve_read_authorization_and_safe_outage_boundary(b3, monkeypatch):  # noqa: F811
    app, owner, client, actor = b3
    query = {'ingredient': 'Rüebli', 'tag': str(uuid4())}
    assert app.test_client().get('/admin/rezepte', query_string=query).status_code == 401
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    response = client.get('/admin/rezepte', query_string=query)
    assert response.status_code == 200 and 'Rezept anlegen' not in response.text
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', set())
    assert client.get('/admin/rezepte', query_string=query).status_code == 403
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    calls = []
    def unavailable(*args, **kwargs):
        calls.append('unavailable')
        raise OperationalError('private SQL', {}, RuntimeError('hidden detail'))
    monkeypatch.setattr(routes.masters, 'list_vocabulary', unavailable)
    response = client.get('/admin/rezepte', query_string=query)
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'private SQL' not in response.text and 'hidden detail' not in response.text and len(calls) == 1
    with owner.begin() as current:
        current.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
    assert client.get('/admin/rezepte', query_string=query).status_code == 401 and len(calls) == 1
