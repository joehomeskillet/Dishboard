"""HTTP-level full-text search parameter `text` on `/admin/rezepte` (real PostgreSQL).
Additive per F3/F4 root freeze: existing `q`/`ingredient`/`tag`/`archived`/`page` stay
byte-identical; `text` is allowlisted, forwarded to `store.list_recipes(text_search=...)`
and kept across pagination links without ever adding a blank `text=` parameter."""
import re
from urllib.parse import parse_qs, urlsplit

import pytest

from cafeteria import master_data_store as masters, recipe_store as store, roles
from test_master_data_db import signed_in
from test_recipe_filter_reads import complete_snapshot, page_link, recipe_ids
from test_recipe_search_db import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, search_lab, seeded_pg16,
)
from test_recipe_store_db import line, payload, target


def visible_ids(html):
    # recipe_ids() only matches the "Bearbeiten" link (active + can_write); archived cards
    # render just "Ansehen" (href ".../ansicht"), so this also accepts that suffix.
    return set(re.findall(r'href="/admin/rezepte/([0-9a-f-]{36})(?:/ansicht)?"', html))


def seed_search_pages(fixture, count=53):
    app, _, _, actor = fixture
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        location = store.get_location(engine)
        result = [store.create_recipe(engine, actor, payload(title=f'Wurzelsuppe {index:03}'),
            expected_location_id=location).public_id for index in range(1, count + 1)]
    return result


def test_text_query_filters_and_orders_by_relevance(b3, search_lab):  # noqa: F811
    lab = search_lab
    client = b3[2]
    title_hit = lab['recipe']('Zauberwort Auflauf')
    ingredient_hit = lab['recipe']('Herbstgericht', ingredients=[line('Frische Muskatnuss')])
    lab['recipe']('Unbeteiligtes Gericht')
    response = client.get('/admin/rezepte', query_string={'text': 'zauberwort'})
    assert response.status_code == 200
    assert recipe_ids(response.text) == [title_hit.public_id]
    assert 'Sortiert nach Relevanz' in response.text
    response = client.get('/admin/rezepte', query_string={'text': 'muskatnuss'})
    assert recipe_ids(response.text) == [ingredient_hit.public_id]


def test_text_query_combines_with_existing_filters(b3, search_lab):  # noqa: F811
    lab = search_lab
    engine, actor, location = lab['engine'], lab['actor'], lab['location']
    tag = masters.create_vocabulary(engine, 'tag', actor, code='FTSTAG', name='Suchtag')
    tagged_hit = lab['recipe']('Geheime Fischsuppe', tag_public_ids=[tag.public_id])
    untagged = lab['recipe']('Offene Fischsuppe')
    archived_hit = lab['recipe']('Archivierte Fischsuppe')
    store.set_recipe_active(engine, actor, target(archived_hit), active=False, expected_location_id=location)
    client = b3[2]
    response = client.get('/admin/rezepte', query_string={'text': 'fischsuppe', 'tag': tag.public_id})
    assert recipe_ids(response.text) == [tagged_hit.public_id]
    response = client.get('/admin/rezepte', query_string={'text': 'fischsuppe', 'archived': '1'})
    assert visible_ids(response.text) == {tagged_hit.public_id, untagged.public_id, archived_hit.public_id}


def test_pagination_links_keep_text_without_blank_params(b3):  # noqa: F811
    ids = seed_search_pages(b3)
    client = b3[2]
    first = client.get('/admin/rezepte', query_string={'text': 'wurzelsuppe'})
    assert first.status_code == 200
    assert recipe_ids(first.text) == ids[:50]
    next_url = page_link(first.text, 2)
    query = parse_qs(urlsplit(next_url).query, keep_blank_values=True)
    assert query == {'q': [''], 'ingredient': [''], 'tag': [''], 'archived': ['0'],
                     'text': ['wurzelsuppe'], 'page': ['2']}
    second = client.get(next_url)
    assert recipe_ids(second.text) == ids[50:]
    # Without an active text filter, pagination links omit the key rather than adding text=.
    no_text = client.get('/admin/rezepte', query_string={'q': 'Wurzelsuppe'})
    other_next = page_link(no_text.text, 2)
    assert 'text' not in parse_qs(urlsplit(other_next).query, keep_blank_values=True)


@pytest.mark.parametrize('query', [
    [('text', 'a'), ('text', 'b')], {'unknown': '1', 'text': 'suppe'},
])
def test_duplicate_or_unknown_query_still_400(b3, query):  # noqa: F811
    response = b3[2].get('/admin/rezepte', query_string=query)
    assert response.status_code == 400 and response.headers['Cache-Control'] == 'no-store'


def test_overlong_text_query_400_without_database_write(b3):  # noqa: F811
    _, owner, client, _ = b3
    before = complete_snapshot(owner)
    response = client.get('/admin/rezepte', query_string={'text': 'x' * 201})
    assert response.status_code == 400 and response.headers['Cache-Control'] == 'no-store'
    assert complete_snapshot(owner) == before


def test_list_without_text_unchanged(b3, search_lab):  # noqa: F811
    lab = search_lab
    lab['recipe']('Alpha Suppe')
    lab['recipe']('Beta Suppe')
    client = b3[2]
    baseline = client.get('/admin/rezepte')
    explicit_blank = client.get('/admin/rezepte', query_string={'text': ''})
    assert recipe_ids(baseline.text) == recipe_ids(explicit_blank.text)
    assert recipe_ids(baseline.text) != []
    assert 'Sortiert nach Relevanz' not in baseline.text
    assert 'Sortiert nach Relevanz' not in explicit_blank.text


def test_search_requires_draft_read_and_is_no_store(b3, monkeypatch):  # noqa: F811
    app, _, client, _ = b3
    query = {'text': 'suppe'}
    assert app.test_client().get('/admin/rezepte', query_string=query).status_code == 401
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', set())
    response = client.get('/admin/rezepte', query_string=query)
    assert response.status_code == 403 and response.headers['Cache-Control'] == 'no-store'
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    response = client.get('/admin/rezepte', query_string=query)
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
