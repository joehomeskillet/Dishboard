"""Real recipe rendering before the shared template CAS can commit."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from uuid import uuid4

import pytest
from pypdf import PdfReader
from sqlalchemy import event, text

from cafeteria import recipe_store as store
from cafeteria.admin import recipe_pdf
from cafeteria.branding import change_branding
from cafeteria.branding_config import default_config as brand_defaults
from cafeteria.print_template_config import PROFILES, PrintTemplateValidationError, default_config
from cafeteria.print_templates import (
    PrintTemplateConflictError, active_template, change_template, default_document,
    read_templates, template_revision,
)
from cafeteria.recipe_types import RecipeConfigurationError, RecipeNotFoundError
from test_recipe_print_input_db import freeze_image
from test_recipe_store_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, payload, target, snapshot,
    make_actor, signed_in,
)


@pytest.fixture
def admin(seeded_pg16, app_engine):  # noqa: F811
    actor = make_actor(seeded_pg16, 'Cafeteria.Admin')
    with signed_in(app_engine, actor):
        yield seeded_pg16, app_engine, actor


def state(owner):
    result = snapshot(owner)
    with owner.connect() as connection:
        result['settings'] = connection.execute(text(
            'SELECT to_jsonb(s)::text FROM cafeteria.settings s ORDER BY to_jsonb(s)::text')).all()
    return result


def change(engine, actor, version, action, template='standard', **kwargs):
    return change_template(engine, 'recipe', actor.user_id, actor.authz_version,
                           version, template, action, **kwargs)


def test_recipe_lifecycle_uses_native_renderer_same_connection_and_historical_config(admin, monkeypatch):
    owner, engine, actor = admin
    recipe_id, frozen, digest = freeze_image(engine, actor)
    config = {**default_config(), 'font': 'active_brand', 'palette': 'active_brand',
              'logo': 'none', 'header_text': 'Rezeptvorlage'}
    original_recipes = snapshot(owner)
    saved, _ = change(engine, actor, 0, 'save', name='Rezept', config=config)
    copied, copy_id = change(engine, actor, 1, 'copy', name='Kopie', revision_id=2)
    rendered, connections, branding_reads = [], [], []
    original_renderer = recipe_pdf.render_recipe_pdf
    def render(revision, **kwargs):
        data = original_renderer(revision, **kwargs)
        rendered.append((revision, kwargs, data))
        return data
    def capture(connection, cursor, statement, parameters, context, executemany):
        connections.append((connection, statement))
        if isinstance(parameters, dict) and parameters.get('key') == 'branding.v1':
            branding_reads.append(connection)
    monkeypatch.setattr(recipe_pdf, 'render_recipe_pdf', render)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        activated, _ = change(engine, actor, 2, 'activate', copy_id, revision_id=1,
                               recipe_public_id=recipe_id, recipe_revision_public_id=frozen.public_id,
                               target_yield='8')
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert len(rendered) == 1 and len({id(connection) for connection, _ in connections}) == 1
    statements = ' '.join(statement for _, statement in connections)
    assert all(name in statements for name in ('lock_operations_actor', 'recipe_revisions', 'recipe_assets'))
    assert branding_reads and all(connection is connections[0][0] for connection in branding_reads)
    revision, arguments, data = rendered[0]
    assert revision.public_id == frozen.public_id and set(arguments['images']) == {digest}
    assert arguments['branding'].revision_id == 1 and arguments['target'] == '8'
    pdf = PdfReader(BytesIO(data))
    extracted = '\n'.join(page.extract_text() for page in pdf.pages)
    assert all(value in extracted for value in ('Rezeptvorlage', 'Suppe', 'Karotte', 'Gewünscht: 8'))
    assert 'Markenrevision 1' in pdf.metadata.subject and list(pdf.pages[0].images)
    assert activated['templates'] == copied['templates']
    with engine.connect() as connection:
        assert active_template(connection, 'recipe') == (config, f'{copy_id}:1')
        assert all(read_templates(connection, profile) == default_document() for profile in PROFILES)
    restored, _ = change(engine, actor, 3, 'restore', revision_id=1)
    assert restored['templates'][0]['revisions'][:2] == saved['templates'][0]['revisions']
    assert template_revision(restored, 'standard')['config'] == default_config()
    archived, _ = change(engine, actor, 4, 'archive')
    before = state(owner)
    with pytest.raises(PrintTemplateConflictError):
        change(engine, actor, 5, 'restore', revision_id=1)
    with pytest.raises(PrintTemplateConflictError):
        change(engine, actor, 5, 'archive', copy_id)
    assert state(owner) == before
    available, _ = change(engine, actor, 5, 'reactivate')
    assert archived['templates'][0]['archived'] and not available['templates'][0]['archived']
    assert snapshot(owner) == original_recipes


@pytest.mark.parametrize('failure', ['missing_asset', 'invalid_target', 'brand_contrast', 'foreign_revision', 'unknown_revision'])
def test_failed_recipe_activation_rolls_back_every_setting_and_active_selection(admin, failure):
    owner, engine, actor = admin
    recipe_id, frozen, _ = freeze_image(engine, actor)
    config = default_config()
    if failure == 'brand_contrast':
        dark = {**brand_defaults(), 'surface': '#000000', 'text': '#ffffff',
                'primary': '#ffffff', 'accent': '#ffffff'}
        change_branding(engine, actor.user_id, actor.authz_version, 0, 'save', name='Dunkle Marke', config=dark)
        change_branding(engine, actor.user_id, actor.authz_version, 1, 'activate', revision_id=2)
        config = {**config, 'palette': 'active_brand', 'logo': 'none'}
    saved, _ = change(engine, actor, 0, 'save', name='Entwurf', config=config)
    selection = dict(recipe_public_id=recipe_id, recipe_revision_public_id=frozen.public_id)
    if failure == 'missing_asset':
        # Deliberate owner-only corruption of this isolated fixture, never application permissions.
        with owner.begin() as connection:
            connection.execute(text('ALTER TABLE cafeteria.recipe_assets DISABLE TRIGGER ALL'))
            connection.execute(text('DELETE FROM cafeteria.recipe_assets'))
            connection.execute(text('ALTER TABLE cafeteria.recipe_assets ENABLE TRIGGER ALL'))
    elif failure == 'invalid_target':
        selection['target_yield'] = '0'
    elif failure == 'foreign_revision':
        other = store.create_recipe(engine, actor, payload(title='Fremde Suppe'),
                                    expected_location_id=store.get_location(engine))
        selection['recipe_public_id'] = other.public_id
    elif failure == 'unknown_revision':
        selection['recipe_revision_public_id'] = str(uuid4())
    before = state(owner)
    error = RecipeConfigurationError if failure in ('invalid_target', 'brand_contrast') else RecipeNotFoundError
    with pytest.raises(error):
        change(engine, actor, 1, 'activate', revision_id=2, **selection)
    assert state(owner) == before
    with engine.connect() as connection:
        assert read_templates(connection, 'recipe') == saved
        assert active_template(connection, 'recipe') == (default_config(), 'standard:1')


@pytest.mark.parametrize('change_authority', ['role', 'disabled', 'version'])
def test_recipe_store_rechecks_actor_before_any_initialization(admin, change_authority):
    owner, engine, actor = admin
    with owner.begin() as connection:
        if change_authority == 'role':
            connection.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
        elif change_authority == 'disabled':
            connection.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:id'), {'id': actor.user_id})
        else:
            connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:id'), {'id': actor.user_id})
    before = state(owner)
    with pytest.raises(PermissionError):
        change(engine, actor, 0, 'save', name='Verboten', config=default_config())
    assert state(owner) == before


def test_concurrent_recipe_first_save_has_one_winner_and_one_cas_conflict(admin):
    owner, engine, actor = admin
    barrier = Barrier(2)
    def save(name):
        barrier.wait(timeout=10)
        try:
            change(engine, actor, 0, 'save', name=name, config=default_config())
            return name
        except PrintTemplateConflictError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(save, ['A', 'B']))
    assert outcomes.count('conflict') == 1
    with engine.connect() as connection:
        document = read_templates(connection, 'recipe')
        assert document['version'] == 1 and template_revision(document, 'standard')['name'] in outcomes
        assert connection.execute(text("SELECT count(*) FROM cafeteria.settings WHERE setting_key='print_templates.v1.recipe'")).scalar_one() == 1


@pytest.mark.parametrize('schema_version', [1, 2, 3])
def test_recipe_key_never_rewrites_either_weekly_envelope(admin, schema_version):
    owner, engine, actor = admin
    document = copy.deepcopy(default_document())
    document['schema_version'] = schema_version
    if schema_version == 1:
        del document['templates'][0]['archived']
    with owner.begin() as connection:
        for profile in PROFILES:
            connection.execute(text('INSERT INTO cafeteria.settings(setting_key,setting_value) VALUES(:key,CAST(:value AS jsonb))'),
                               {'key': 'print_templates.v1.' + profile, 'value': json.dumps(document)})
        original = connection.execute(text("SELECT setting_key,setting_value::text FROM cafeteria.settings ORDER BY setting_key")).all()
    change(engine, actor, 0, 'save', name='Separates Rezept', config=default_config())
    with engine.connect() as connection:
        assert connection.execute(text("SELECT setting_key,setting_value::text FROM cafeteria.settings WHERE setting_key!='print_templates.v1.recipe' ORDER BY setting_key")).all() == original
        assert PROFILES == ('staff_guest', 'patient')
        assert all(read_templates(connection, profile)['version'] == 0 for profile in PROFILES)


@pytest.mark.parametrize('profile,options', [
    ('recipe', {}), ('recipe', {'recipe_public_id': str(uuid4())}),
    ('recipe', {'recipe_public_id': True, 'recipe_revision_public_id': str(uuid4())}),
    ('recipe', {'week': '2026-09-07'}), ('other', {}),
    ('staff_guest', {'recipe_public_id': str(uuid4())}),
    ('patient', {'recipe_revision_public_id': str(uuid4())}),
    ('patient', {'target_yield': '8'}),
])
def test_document_kind_and_selection_boundaries_never_initialize_settings(admin, profile, options):
    owner, engine, actor = admin
    before = state(owner)
    with pytest.raises(PrintTemplateValidationError):
        change_template(engine, profile, actor.user_id, actor.authz_version, 0, 'standard', 'activate', **options)
    assert state(owner) == before
