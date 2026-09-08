-- Wird als Owner nach schema.sql/seed.sql ausgeführt. Keine Passwörter und keine CREATE ROLE-Anweisungen.
BEGIN;
SET search_path TO cafeteria, public;

DO $require_auth_issuer$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cafeteria_auth_issuer') THEN
        RAISE EXCEPTION 'Required role cafeteria_auth_issuer is missing.' USING ERRCODE = '42501';
    END IF;
END;
$require_auth_issuer$;

REVOKE ALL ON SCHEMA cafeteria
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public
FROM cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT USAGE ON SCHEMA cafeteria
TO cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

-- Jede erneute Anwendung entfernt frühere breite Grants, bevor der aktuelle
-- Least-Privilege-Vertrag aufgebaut wird.
REVOKE ALL ON ALL TABLES IN SCHEMA cafeteria FROM cafeteria_app, cafeteria_backup;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA cafeteria FROM cafeteria_app, cafeteria_backup;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    menu_weeks, menu_services, dish_templates, component_allergens, component_labels,
    menu_items, menu_item_prices, menu_item_components, menu_item_labels,
    menu_item_allergens, origin_declarations,
    import_batches, import_rows, settings
TO cafeteria_app;
GRANT SELECT, INSERT, UPDATE ON menu_components TO cafeteria_app;
GRANT SELECT, INSERT ON branding_assets TO cafeteria_app;

GRANT SELECT ON users, user_role_cache, local_credentials TO cafeteria_app;
GRANT UPDATE (last_login_at) ON users TO cafeteria_app;
GRANT SELECT ON api_keys TO cafeteria_app;
GRANT UPDATE (last_used_at) ON api_keys TO cafeteria_app;
GRANT UPDATE (failed_login_count, locked_until, last_failed_at) ON local_credentials
TO cafeteria_app;
GRANT SELECT, INSERT ON publication_revisions TO cafeteria_app;
REVOKE EXECUTE ON FUNCTION record_publication_lifecycle()
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION bootstrap_auth_capability_secret()
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION rotate_auth_capability_secret()
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION ensure_auth_capability_state()
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION hard_reset_auth_capability_state()
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION sync_entra_user(uuid, uuid, text, text, text, text, text[])
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION resolve_auth_actor(text)
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION provision_local_user(text, text, text, text, text[])
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION set_local_password(text, text, text)
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION disable_local_user(text, text)
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION issue_publication_capability(bigint, bigint, interval)
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION withdraw_publication_revision(bigint, text, text)
FROM PUBLIC, cafeteria_app, cafeteria_backup;
REVOKE EXECUTE ON FUNCTION lock_expected_active_location(bigint)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE EXECUTE ON FUNCTION lock_active_publication(bigint)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION withdraw_publication_revision(bigint, text, text) TO cafeteria_app;

GRANT SELECT ON
    schema_migrations, application_roles, locations, offer_profiles,
    meal_periods, menu_types, dietary_labels, allergens, active_publications,
    audit_events, publication_lifecycle_events
TO cafeteria_app;
-- Anzeigenamen und Wochenendschalter sind pflegbar; Patientenschalter bleibt per CHECK fest.
-- Code, Preisflag und Mahlzeiten bleiben ohne Schreibrecht.
GRANT UPDATE (display_name, allows_weekend) ON offer_profiles TO cafeteria_app;

GRANT USAGE, SELECT ON
    menu_weeks_id_seq, menu_services_id_seq, dish_templates_id_seq,
    menu_components_id_seq, menu_items_id_seq, origin_declarations_id_seq,
    publication_revisions_id_seq,
    import_batches_id_seq, settings_id_seq
TO cafeteria_app;

GRANT SELECT ON
    schema_migrations, users, application_roles, user_role_cache, local_credentials,
    locations, offer_profiles, meal_periods, menu_types,
    menu_weeks, menu_services, dish_templates, menu_components,
    component_allergens, component_labels, menu_items, menu_item_prices,
    menu_item_components, dietary_labels, menu_item_labels, allergens,
    menu_item_allergens, origin_declarations, publication_revisions,
    publication_lifecycle_events, import_batches, import_rows, audit_events, api_keys,
    settings, branding_assets, active_publications
TO cafeteria_backup;
GRANT SELECT ON
    users_id_seq, locations_id_seq, offer_profiles_id_seq, meal_periods_id_seq,
    menu_types_id_seq, menu_weeks_id_seq, menu_services_id_seq,
    dish_templates_id_seq, menu_components_id_seq, menu_items_id_seq,
    dietary_labels_id_seq,
    allergens_id_seq, origin_declarations_id_seq, publication_revisions_id_seq,
    publication_lifecycle_events_id_seq, import_batches_id_seq,
    audit_events_id_seq, settings_id_seq
TO cafeteria_backup;
GRANT SELECT ON SEQUENCE api_keys_id_seq TO cafeteria_backup;

ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    REVOKE ALL ON TABLES FROM cafeteria_app, cafeteria_backup;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    REVOKE ALL ON SEQUENCES FROM cafeteria_app, cafeteria_backup;

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cafeteria
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE ALL ON ALL TABLES IN SCHEMA cafeteria FROM cafeteria_auth_issuer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA cafeteria FROM cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    withdraw_publication_revision(bigint, text, text)
TO cafeteria_app;
GRANT EXECUTE ON FUNCTION
    lock_component_metadata_masters(text[], text[]),
    lock_expected_active_location(bigint),
    lock_active_publication(bigint)
TO cafeteria_app;
GRANT EXECUTE ON FUNCTION
    normalize_patient_key(text),
    patient_key_is_forbidden(text),
    jsonb_has_patient_forbidden_key(jsonb),
    jsonb_has_patient_forbidden_value(jsonb)
TO cafeteria_app;
GRANT EXECUTE ON FUNCTION
    sync_entra_user(uuid, uuid, text, text, text, text, text[]),
    issue_publication_capability(bigint, bigint, interval),
    create_local_user_v19(bigint,bigint,text,text,text,text[]),
    replace_local_roles_v19(bigint,bigint,uuid,bigint,text[]),
    reset_local_password_v19(bigint,bigint,uuid,bigint,text),
    deactivate_local_user_v19(bigint,bigint,uuid,bigint),
    reactivate_local_user_v19(bigint,bigint,uuid,bigint),
    local_user_command_context_v19(bigint,text,uuid,text),
    record_auth_access_v25(uuid,text,text,text,bigint,bigint)
TO cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    REVOKE EXECUTE ON FUNCTIONS
    FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    REVOKE ALL ON TABLES FROM cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    REVOKE ALL ON SEQUENCES FROM cafeteria_auth_issuer;

GRANT EXECUTE ON FUNCTION
    workflow_week_context(bigint),
    record_menu_review(bigint, bigint, text, bigint, bigint, text, text),
    record_week_context_review(bigint, bigint, text, bigint, text, jsonb)
TO cafeteria_app;

REVOKE EXECUTE ON FUNCTION
    require_api_key_admin(bigint),
    create_api_key(bigint, text, text, text, text[], timestamptz),
    revoke_api_key(bigint, uuid)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    create_api_key(bigint, text, text, text, text[], timestamptz),
    revoke_api_key(bigint, uuid)
TO cafeteria_app;

GRANT EXECUTE ON FUNCTION lock_operations_actor(bigint,bigint) TO cafeteria_app;

-- B2 M-A schema21 contract.
-- Only fixed public verbs are callable by the application.
REVOKE ALL ON FUNCTION
master_text(text,integer,boolean),
master_factor(numeric),
master_quantity(numeric),
master_json_valid(jsonb,integer),
protect_master_data(),
protect_food_proposal(),
require_master_data_actor(bigint,bigint,text),
master_location(bigint),
master_audit(bigint,bigint,bigint,text,uuid,text,bigint,bigint,jsonb),
master_payload(jsonb,text[]),
master_expectation(uuid,bigint),
master_lock_food_refs(jsonb),
master_food_links(bigint),
master_replace_food_links(bigint,bigint,jsonb),
master_food_category_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
master_tag_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
master_storage_location_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
master_unit_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
master_food_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
create_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
rename_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_food_active_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_tags_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_metadata_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_food_allergen_review_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_storage_locations_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
accept_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
reject_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb) FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
create_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
rename_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_food_active_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_tags_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_metadata_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_food_allergen_review_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_storage_locations_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
accept_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
reject_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb) TO cafeteria_app;
GRANT SELECT ON measurement_units,food_categories,foods,tags,food_tags,food_labels,food_allergens,
 storage_locations,food_storage_locations,food_data_proposals TO cafeteria_app,cafeteria_backup;
GRANT SELECT ON SEQUENCE measurement_units_id_seq,food_categories_id_seq,foods_id_seq,tags_id_seq,
 storage_locations_id_seq,food_data_proposals_id_seq TO cafeteria_backup;

REVOKE ALL ON FUNCTION recipe_location_v22(bigint),recipe_text_v22(text,integer,boolean),recipe_protect_v22(),recipe_fields_v22(jsonb,text[]),
 recipe_payload_v22(bigint),recipe_snapshot_v22(bigint),recipe_refs_v22(bigint,bigint,jsonb),
 recipe_write_v22(text,bigint,bigint,bigint,uuid,bigint,jsonb),recipe_cookbook_v22(text,bigint,bigint,bigint,uuid,bigint,jsonb),
 create_recipe_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 update_recipe_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 set_recipe_active_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 freeze_recipe_revision_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 add_recipe_image_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 create_cookbook_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 update_cookbook_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 set_cookbook_active_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 replace_cookbook_recipes_v22(bigint,bigint,bigint,uuid,bigint,jsonb) FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION recipe_payload_v22(bigint),
 create_recipe_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 update_recipe_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 set_recipe_active_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 freeze_recipe_revision_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 add_recipe_image_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 create_cookbook_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 update_cookbook_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 set_cookbook_active_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 replace_cookbook_recipes_v22(bigint,bigint,bigint,uuid,bigint,jsonb) TO cafeteria_app;
GRANT SELECT ON recipes,recipe_ingredients,recipe_steps,recipe_tags,recipe_images,recipe_assets,recipe_revisions,cookbooks,cookbook_recipes TO cafeteria_app,cafeteria_backup;
GRANT SELECT ON SEQUENCE recipes_id_seq,recipe_revisions_id_seq,cookbooks_id_seq TO cafeteria_backup;

REVOKE ALL ON FUNCTION activate_screen_assignment_v23(bigint,bigint,text,bigint,text,integer)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION activate_screen_assignment_v23(bigint,bigint,text,bigint,text,integer) TO cafeteria_app;

COMMIT;
