"""Pure contract checks using only existing synthetic recipe fixtures."""
from copy import deepcopy
from dataclasses import replace
from decimal import Inexact, localcontext

import pytest

from cafeteria.admin.recipe_document import DOCUMENT_VERSION, build_recipe_document
from cafeteria.admin.recipe_forms import FormError
from cafeteria.recipe_snapshots import frozen_json
from cafeteria.recipe_types import RecipeConfigurationError
from test_recipe_pdf import prepared_revision, recipe, revision


def test_complete_document_preserves_content_and_one_selected_quantity():
    payload = recipe()
    before = deepcopy(payload)
    selected = revision(payload)
    document = build_recipe_document(selected.snapshot['recipe'], '6', revision=selected)
    assert document['document_version'] == DOCUMENT_VERSION
    assert document['identity'] == {
        'kind': 'revision', 'recipe_public_id': selected.recipe_public_id,
        'revision_public_id': selected.public_id, 'revision_number': selected.revision_number,
        'content_hash_sha256': selected.content_hash_sha256, 'created_at': selected.created_at.isoformat(),
    }
    assert document['title'] == payload['title']
    assert document['description'] == payload['description']
    assert document['yield'] == {'amount': '6', 'original_amount': '4', 'unit': 'PORTION',
                                 'is_scaled': True, 'measurement_status': None}
    assert document['times'] == {'prep_minutes': 10, 'cook_minutes': 25}
    assert document['ingredients'][0]['amount'] == '0.1875'
    assert document['ingredients'][0]['original_amount'] == '0.125'
    assert document['ingredients'][0]['unit'] == 'KG'
    assert [row['group_label'] for row in document['ingredients']] == [
        item['group_label'] for item in payload['ingredients']]
    assert document['steps'][0]['duration_minutes'] == 0
    assert document['steps'][0]['instruction'] == payload['steps'][0]['instruction']
    assert document == build_recipe_document(selected.snapshot['recipe'], '6', revision=selected)
    document['ingredients'][0]['text'] = 'Only the projection changes'
    document['provenance'][0]['source']['kind'] = 'Only the projection changes'
    assert payload == before and selected.snapshot['recipe'] == frozen_json(before)


def test_legacy_missing_amount_steps_and_times_are_explicit_without_fabrication():
    payload = recipe()
    payload.update(steps=[], prep_minutes=None, cook_minutes=0)
    payload['ingredients'] = [dict(payload['ingredients'][0], quantity=None, unit_code=None)]
    document = build_recipe_document(payload)
    assert document['identity']['kind'] == 'draft'
    assert document['identity']['revision_number'] is None
    assert document['identity']['content_hash_sha256'] is None
    assert document['ingredients'][0]['amount'] is None
    assert document['ingredients'][0]['unit'] is None
    assert document['steps'] == [] and document['empty_steps'] == 'Keine Schritte gespeichert.'
    assert document['times'] == {'prep_minutes': None, 'cook_minutes': 0}
    assert not document['yield']['is_scaled']
    payload['ingredients'] = []
    assert build_recipe_document(payload)['empty_ingredients'] == 'Keine Zutaten gespeichert.'


def test_exact_provenance_dedup_preserves_notes_timestamps_and_associations():
    payload = recipe()
    origin = dict(payload['ingredients'][0], source_kind='file_import', source_reference='Synthetic A',
                  fetched_at='2026-09-01T12:00:00Z', note='Synthetic original note')
    payload['ingredients'] = [origin, dict(origin, ingredient_text='Second ingredient', note='Different cooking note'),
                              dict(origin, source_reference='Different source'),
                              dict(origin, fetched_at='2026-09-01T12:00:00+00:00')]
    document = build_recipe_document(payload)
    ids = [item['source_id'] for item in document['ingredients']]
    assert ids[0] == ids[1] and len(set(ids)) == 3
    grouped = next(item for item in document['provenance'] if item['id'] == ids[0])
    assert grouped['uses'] == ['ingredient:1', 'ingredient:2']
    assert grouped['source']['note'] is None
    assert document['ingredients'][1]['note'] == 'Different cooking note'
    assert 'Different cooking note' not in document['source_notes']
    payload['source'].update(kind=origin['source_kind'], reference=origin['source_reference'],
                             fetched_at=origin['fetched_at'], note='Distinct recipe source note')
    with_note = build_recipe_document(payload)
    assert with_note['recipe_source_id'] != with_note['ingredients'][0]['source_id']
    assert 'Distinct recipe source note' in with_note['source_notes']


def test_source_warnings_and_image_provenance_are_preserved_without_new_claims():
    payload = recipe()
    note = 'Synthetischer Test: ungeprüft; Ausbeute nicht gemessen.'
    payload['source'].update(kind='ai_assisted', reference='Synthetic test only', note=note,
                             fetched_at='2026-09-01T12:00:00Z')
    image = {'sha256': 'b' * 64, 'caption': 'Synthetic photo', 'source_url': 'https://example.invalid/image',
             'source_license': 'Synthetic licence', 'fetched_at': '2026-09-01T12:00:00Z'}
    payload['images'] = [image]
    payload['steps'][0]['image_sha256'] = 'c' * 64
    document = build_recipe_document(payload)
    assert note in document['source_notes']
    assert {item['code'] for item in document['warnings']} == {'ai_source', 'allergens_unrecorded'}
    assert document['yield']['measurement_status'] is None
    assert document['images'] == [image]
    assert document['steps'][0]['image_sha256'] == 'c' * 64
    document['images'][0]['caption'] = 'Detached projection'
    assert payload['images'][0]['caption'] == 'Synthetic photo'


def test_prepared_uses_keep_exact_identity_steps_and_full_decimal_precision():
    selected = prepared_revision()
    original_text = selected.canonical_snapshot_text
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        document = build_recipe_document(selected.snapshot['recipe'], '2', revision=selected)
    assert len(document['prepared']) == 2
    for number, use in enumerate(document['prepared'], 1):
        child = selected.prepared_revisions[0]
        body = use['document']
        assert use['use_number'] == number and use['first_use_number'] == 1
        assert body['identity']['revision_public_id'] == child.public_id
        assert body['identity']['content_hash_sha256'] == child.content_hash_sha256
        assert body['yield']['amount'] == '0.00066666666666666666666666666666666666666666666666667'
        assert body['ingredients'][0]['amount'] == '0.00022222222222222222222222222222222222222222222222222'
        assert [step['instruction'] for step in body['steps']] == [
            step['instruction'] for step in child.snapshot['recipe']['steps']]
    assert selected.canonical_snapshot_text == original_text
    broken = replace(selected, prepared_revisions=())
    with pytest.raises(RecipeConfigurationError):
        build_recipe_document(broken.snapshot['recipe'], revision=broken)


@pytest.mark.parametrize('selected', [revision(), prepared_revision()])
def test_payload_cannot_be_mixed_with_a_different_revision(selected):
    changed = dict(selected.snapshot['recipe'], title='Different current draft')
    with pytest.raises(RecipeConfigurationError):
        build_recipe_document(changed, revision=selected)


@pytest.mark.parametrize('target', ['0', '-1', 'NaN', '1.0000001'])
def test_invalid_target_retains_original_named_validation(target):
    with pytest.raises(FormError) as error:
        build_recipe_document(recipe(), target)
    assert error.value.field == 'yield'


def test_long_document_retains_every_ingredient_and_step_without_truncation():
    payload = recipe()
    payload['ingredients'] = [dict(payload['ingredients'][0], ingredient_text=f'Synthetic ingredient {n}')
                              for n in range(60)]
    payload['steps'] = [{'instruction': f'Synthetic step {n}\nSecond line',
                         'duration_minutes': None, 'image_sha256': None} for n in range(40)]
    document = build_recipe_document(payload)
    assert len(document['ingredients']) == 60 and len(document['steps']) == 40
    assert document['ingredients'][-1]['text'] == 'Synthetic ingredient 59'
    assert document['steps'][-1] == {'number': 40, 'instruction': 'Synthetic step 39\nSecond line',
                                     'duration_minutes': None, 'image_sha256': None}
