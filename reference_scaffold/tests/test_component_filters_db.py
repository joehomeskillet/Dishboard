from __future__ import annotations

import pytest

from cafeteria.component_catalog_filters import ComponentFilters
from cafeteria.component_catalog_store import (
    ComponentCatalogValidationError, archive_component, find_components,
)
from test_component_catalog_db import (
    CatalogDatabase, _create, _insert_foreign_component, _link_component, _scope,
    catalog_database,  # noqa: F401
)


@pytest.mark.parametrize('profile', ['patient', 'staff_guest'])
def test_filters_combine_without_leaking_scope_or_conflating_unknown(request: pytest.FixtureRequest, profile: str):
    db: CatalogDatabase = request.getfixturevalue('catalog_database')
    scope = _scope(db, profile)
    match = _create(db, name='Filter 100%_ Suppe', target='common', labels=('VEGAN',),
                    allergens=(('GLUTEN', 'contains'),))
    traces = _create(db, name='Filter Spuren', origin='DE', profile=profile,
                     allergens=(('GLUTEN', 'may_contain'),))
    unknown = _create(db, name='Filter Unbekannt', origin=None, profile=profile)
    archived = _create(db, name='Filter Archiv', category='vegetable', target='common',
                       labels=('VEGAN',), allergens=(('GLUTEN', 'contains'),))
    archive_component(db.app, scope, str(archived['public_id']), 1)
    _create(db, name='Filter Fremdes Profil', profile='patient' if profile == 'staff_guest' else 'staff_guest',
            labels=('VEGAN',), allergens=(('GLUTEN', 'contains'),))
    _insert_foreign_component(db, location_id=db.other_location_id, profile_scope='common', name='Filter Fremder Ort')
    _link_component(db, str(match['public_id']))

    def found(query='Filter', category=None, **filters):
        return {row['public_id'] for row in find_components(
            db.app, scope, query, category, False, filters=ComponentFilters(**filters),
        )}

    assert found() == {match['public_id'], traces['public_id'], unknown['public_id']}
    assert found(usage='used') == {match['public_id']}
    assert found(usage='unused') == {traces['public_id'], unknown['public_id']}
    assert found(allergen='GLUTEN') == {match['public_id'], traces['public_id']}
    assert found(allergen='GLUTEN', presence='contains') == {match['public_id']}
    assert found(allergen='GLUTEN', presence='may_contain') == {traces['public_id']}
    assert found(allergen='unknown') == {unknown['public_id']}
    assert found(origin='unknown') == {unknown['public_id']}
    assert found(origin='DE') == {traces['public_id']}
    assert found(label='VEGAN') == {match['public_id']}
    assert found(status='archived') == {archived['public_id']}
    assert found(status='all') == {match['public_id'], traces['public_id'], unknown['public_id'], archived['public_id']}
    assert found(query='100%_', category='side', usage='used', allergen='GLUTEN',
                 presence='contains', label='VEGAN', origin='CH', status='active') == {match['public_id']}
    assert found(usage='unused', label='VEGAN') == set()
    assert found(category='meat', origin='CH') == set()
    assert found(allergen='MILK') == set()  # Missing declarations are not positive matches.
    assert {row['public_id'] for row in find_components(db.app, scope, 'Filter', None, True)} == found(status='all')
    rows = find_components(db.app, scope, '100%_', None, False, filters=ComponentFilters(usage='used'))
    assert rows[0]['usage_count'] == 1


def test_known_metadata_codes_required_even_if_query_has_no_hits(request: pytest.FixtureRequest):
    db: CatalogDatabase = request.getfixturevalue('catalog_database')
    for values in [{'allergen': 'NO_SUCH_ALLERGEN'}, {'label': 'NO_SUCH_LABEL'}]:
        with pytest.raises(ComponentCatalogValidationError, match='Unbekanntes'):
            find_components(db.app, _scope(db), 'nothing', None, False,
                            filters=ComponentFilters(**values))


@pytest.mark.parametrize('values', [
    {'usage': 'maybe'}, {'status': 'deleted'}, {'presence': 'free_from'},
    {'presence': 'contains'}, {'allergen': 'unknown', 'presence': 'contains'},
    {'origin': 'Switzerland'}, {'origin': 'ch'}, {'allergen': 'gluten'},
    {'label': 'vegan'}, {'label': "' OR 1=1"}, {'status': True},
])
def test_filter_values_reject_unknown_modes_and_invalid_types(values):
    with pytest.raises(ComponentCatalogValidationError):
        ComponentFilters(**values)
