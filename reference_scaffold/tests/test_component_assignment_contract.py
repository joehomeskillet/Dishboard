"""R5a keeps the new DTO internal until all writers preserve its third field."""
from uuid import uuid4

import pytest

from cafeteria.component_assignment_contract import AssignmentValidationError, normalize_assignments
from cafeteria.component_assignment_store import _normalize_assignments as legacy_normalize


def test_missing_and_explicit_null_are_different_and_roundtrip():
    legacy = {'component_public_id': None, 'component_text': 'Kartoffeln'}
    missing, = normalize_assignments([legacy])
    explicit, = normalize_assignments([{**legacy, 'recipe_revision_public_id': None}])
    assert not missing.recipe_field_present and explicit.recipe_field_present
    assert missing.as_payload() == legacy
    assert explicit.as_payload() == {**legacy, 'recipe_revision_public_id': None}


@pytest.mark.parametrize('catalogue', [False, True])
def test_recipe_is_independent_of_catalogue_link(catalogue):
    row = {'component_public_id': str(uuid4()) if catalogue else None,
           'component_text': None if catalogue else 'Kartoffeln',
           'recipe_revision_public_id': str(uuid4())}
    assignment, = normalize_assignments((row,))
    assert assignment.as_payload() == row
    with pytest.raises(ValueError):
        legacy_normalize([row])


@pytest.mark.parametrize('changes', [
    {'extra': 'x'}, {'recipe_revision_public_id': True}, {'recipe_revision_public_id': 123},
    {'recipe_revision_public_id': 'broken'}, {'component_public_id': False},
    {'component_public_id': str(uuid4())}, {'component_text': None}, {'component_text': '  '},
])
def test_strict_boundary_rejects_invalid_fields(changes):
    with pytest.raises(AssignmentValidationError):
        normalize_assignments([{'component_public_id': None, 'component_text': 'Kartoffeln', **changes}])


@pytest.mark.parametrize('value', [True, {}, 'text', [True], [{'component_text': 'Missing key'}]])
def test_strict_shape(value):
    with pytest.raises(AssignmentValidationError):
        normalize_assignments(value)
