from __future__ import annotations

import pytest
from sqlalchemy import text
from werkzeug.datastructures import MultiDict

from test_component_catalog_routes import (
    _create_csrf, _create_fields, app, client, database_engine,  # noqa: F401
)


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
def test_query_contract_rejects_unknown_duplicate_and_conflicting_fields(request, family):
    http = request.getfixturevalue('client')
    path = f'/admin/{family}/komponenten'
    for params in [
        {'unexpected': '1'}, {'usage': 'maybe'}, {'status': 'deleted'}, {'presence': 'free_from'},
        {'presence': 'contains'}, {'allergen': 'unknown', 'presence': 'contains'},
        {'origin': 'Switzerland'}, {'category': 'invalid'}, {'label': 'UNKNOWN_LABEL'},
        {'allergen': 'UNKNOWN_ALLERGEN'}, {'q': 'x' * 201}, {'include_archived': 'yes'},
        {'include_archived': '1', 'status': 'active'}, {'profile': 'patient'},
    ]:
        response = http.get(path, query_string=params)
        assert response.status_code == 400, params
    for key in ['q', 'category', 'include_archived', 'status', 'usage', 'allergen', 'presence', 'label', 'origin']:
        response = http.get(path, query_string=MultiDict([(key, ''), (key, '')]))
        assert response.status_code == 400, key


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
def test_filter_get_keeps_values_count_and_legacy_archive_links(request, family):
    http = request.getfixturevalue('client')
    path = f'/admin/{family}/komponenten'
    fields = _create_fields()
    fields['_csrf'] = _create_csrf(http, family)
    created = http.post(path, data=fields)
    assert created.status_code == 303
    params = {'q': 'Kartoffel', 'category': 'side', 'usage': 'unused', 'allergen': 'GLUTEN',
              'presence': 'contains', 'label': 'VEGAN', 'origin': 'CH', 'status': 'active'}
    response = http.get(path, query_string=params)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '1 Treffer' in body
    assert f'href="{created.headers["Location"]}"' in body
    assert f'href="{path}">Zurücksetzen</a>' in body
    assert 'Nicht erfasst bedeutet keine bestätigte Allergenfreiheit.' in body
    for key, value in params.items():
        if key == 'q':
            assert 'value="Kartoffel"' in body
            continue
        # Restrict to the GET form; create/editor fields have independent values.
        form = body.split('class="search-form', 1)[1].split('</form>', 1)[0]
        select = form.split(f'name="{key}"', 1)[1].split('</select>', 1)[0]
        assert f'value="{value}" selected' in select, key
    assert '0 Treffer' in http.get(path, query_string={**params, 'origin': 'DE'}).get_data(as_text=True)
    legacy = http.get(path, query_string={'include_archived': '1'})
    assert legacy.status_code == 200
    status_html = legacy.get_data(as_text=True).split('id="f-status"', 1)[1].split('</select>', 1)[0]
    assert 'value="all" selected' in status_html

    # Existing inactive metadata still matches and cannot silently disappear from the query form.
    engine = request.getfixturevalue('database_engine')
    with engine.begin() as connection:
        connection.execute(text("UPDATE cafeteria.allergens SET active=false WHERE code='GLUTEN'"))
        connection.execute(text("UPDATE cafeteria.dietary_labels SET active=false WHERE code='VEGAN'"))
    inactive = http.get(path, query_string=params)
    assert inactive.status_code == 200
    form = inactive.get_data(as_text=True).split('class="search-form', 1)[1].split('</form>', 1)[0]
    assert '1 Treffer' in form
    assert 'value="GLUTEN" selected>GLUTEN (inaktiv)' in form
    assert 'value="VEGAN" selected>VEGAN (inaktiv)' in form
