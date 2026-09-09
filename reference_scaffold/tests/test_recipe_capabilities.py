"""Recipe capability boundaries, strict direct SQL and atomic audit failures."""
import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from werkzeug.exceptions import Forbidden, Unauthorized

from cafeteria import recipe_store as store
from cafeteria.recipe_types import RecipeConfigurationError, RecipeConflictError, RecipeUnavailableError
from test_recipe_store_db import (  # noqa: F401
    pg16, installed_pg16, seeded_pg16, app_engine, payload, target, snapshot, make_actor, signed_in,
)
from test_recipe_store_db import master as master


@pytest.mark.parametrize('table', ['recipes', 'recipe_ingredients', 'recipe_steps', 'recipe_tags', 'recipe_assets',
                                  'recipe_images', 'recipe_revisions', 'cookbooks', 'cookbook_recipes'])
def test_recipe_tables_have_only_application_and_backup_read_rights(master, table):
    owner, _, _ = master
    with owner.connect() as current:
        assert current.execute(text("SELECT has_table_privilege('cafeteria_app',:table,'SELECT'),"
            "has_table_privilege('cafeteria_backup',:table,'SELECT'),"
            "has_table_privilege('cafeteria_app',:table,'INSERT,UPDATE,DELETE,TRUNCATE'),"
            "has_table_privilege('cafeteria_auth_issuer',:table,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),
            {'table': 'cafeteria.' + table}).one() == (True, True, False, False)


def test_only_fixed_verbs_and_invoker_payload_reader_are_granted(master):
    owner, _, _ = master
    public_verbs = {'create_recipe_v22', 'update_recipe_v22', 'set_recipe_active_v22',
                    'add_recipe_image_v22', 'create_cookbook_v22', 'update_cookbook_v22', 'set_cookbook_active_v22',
                    'replace_cookbook_recipes_v22'}
    with owner.connect() as current:
        rows = current.execute(text("SELECT p.proname,p.prosecdef,p.proconfig,has_function_privilege('cafeteria_app',p.oid,'EXECUTE'),"
            "has_function_privilege('public',p.oid,'EXECUTE'),has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE')"
            "FROM pg_proc p WHERE p.pronamespace='cafeteria'::regnamespace AND p.proname LIKE '%_v22'")).all()
    assert public_verbs <= {row[0] for row in rows}
    for name, definer, settings, app, public, issuer in rows:
        assert not public and not issuer
        assert app == (name in public_verbs or name == 'recipe_payload_v22')
        assert settings == ['search_path=pg_catalog, cafeteria, pg_temp']
        if name in public_verbs:
            assert definer
        if name == 'recipe_payload_v22':
            assert not definer
    with owner.connect() as current:
        for signature in ('recipe_dependency_preview_v27(bigint,uuid,bigint)',
                          'freeze_recipe_v27(bigint,bigint,bigint,uuid,bigint,text)'):
            assert current.execute(text("SELECT has_function_privilege('cafeteria_app',:fn,'EXECUTE'),"
                "has_function_privilege('public',:fn,'EXECUTE'),has_function_privilege('cafeteria_auth_issuer',:fn,'EXECUTE')"),
                {'fn': 'cafeteria.' + signature}).one() == (True, False, False)


@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'])
def test_all_existing_editor_roles_can_write_with_original_actor(master, role):
    owner, engine, _ = master
    actor = make_actor(owner, role)
    with signed_in(engine, actor):
        created = store.create_recipe(engine, actor, payload(), expected_location_id=store.get_location(engine))
        assert store.get_recipe(engine, created.public_id).row_version == 1


def test_missing_stale_and_revoked_session_never_writes(master):
    owner, engine, actor = master
    from flask import session
    before = snapshot(owner)
    session.clear()
    with pytest.raises(Unauthorized):
        store.list_recipes(engine)
    assert snapshot(owner) == before
    with owner.begin() as current:
        current.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id': actor.user_id})
    with signed_in(engine, actor):
        with pytest.raises(Unauthorized):
            store.create_recipe(engine, actor, payload(), expected_location_id=1)
    fresh = make_actor(owner)
    with owner.begin() as current:
        current.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Publisher'"))
    with signed_in(engine, fresh):
        with pytest.raises(Unauthorized):
            store.list_recipes(engine)
    assert snapshot(owner)['recipes'] == []


def test_capability_denial_precedes_recipe_command(master, monkeypatch):
    from cafeteria import roles
    owner, engine, actor = master
    before = snapshot(owner)
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    with pytest.raises(Forbidden):
        store.create_recipe(engine, actor, payload(), expected_location_id=1)
    assert snapshot(owner) == before


def test_original_location_rejects_switch_and_invalid_configuration(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    with owner.begin() as current:
        current.execute(text("UPDATE cafeteria.locations SET active=false"))
        current.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES('OTHER','Anderes Haus',true)"))
    before = snapshot(owner)
    with pytest.raises(RecipeConflictError):
        store.create_recipe(engine, actor, payload(), expected_location_id=location)
    assert snapshot(owner) == before
    with owner.begin() as current:
        current.execute(text('UPDATE cafeteria.locations SET active=false'))
    with pytest.raises(RecipeConfigurationError):
        store.get_location(engine)
    with pytest.raises(RecipeConfigurationError):
        store.create_recipe(engine, actor, payload(), expected_location_id=location)


@pytest.mark.parametrize('field,value', [('title', True), ('prep_minutes', True), ('cook_minutes', 1.5),
                                       ('servings', 'NaN'), ('description', '<markup>'), ('ingredients', None)])
def test_direct_sql_rejects_invalid_payload_before_persistence(master, field, value):
    owner, engine, actor = master
    data = payload(**{field: value})
    before = snapshot(owner)
    with pytest.raises(DBAPIError) as failure:
        with engine.begin() as current:
            current.execute(text('SELECT cafeteria.create_recipe_v22(:actor,:version,:location,NULL,NULL,CAST(:payload AS jsonb))'),
                {'actor': actor.user_id, 'version': actor.authz_version, 'location': store.get_location(engine), 'payload': json.dumps(data)})
    assert failure.value.orig.sqlstate == 'P1901'
    assert snapshot(owner) == before


def test_audit_failure_rolls_back_entire_recipe_and_children(master):
    owner, engine, actor = master
    location = store.get_location(engine)
    with owner.begin() as current:
        current.execute(text("CREATE FUNCTION cafeteria.reject_recipe_test_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit unavailable'; END $$"))
        current.execute(text('CREATE TRIGGER recipe_test_audit BEFORE INSERT ON cafeteria.audit_events FOR EACH ROW EXECUTE FUNCTION cafeteria.reject_recipe_test_audit()'))
    before = snapshot(owner)
    with pytest.raises(RecipeUnavailableError):
        store.create_recipe(engine, actor, payload(), expected_location_id=location)
    assert snapshot(owner) == before


def test_outer_failure_boundary_covers_authorization(monkeypatch):
    from flask import Flask, session
    from cafeteria import roles
    app = Flask(__name__)
    app.secret_key = 'recipe-isolated-outage'
    def fail(*args, **kwargs):
        raise OperationalError('lookup', {}, Exception('offline'))
    monkeypatch.setattr(roles, 'load_user_authorization', fail)
    app.extensions['cafeteria_db'] = None
    with app.test_request_context():
        session['user'] = {'id': 1}
        session['authz_version'] = 1
        with pytest.raises(RecipeUnavailableError):
            store.list_recipes(None)
