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
    menu_weeks, menu_services, dish_templates,
    menu_items, menu_item_prices, menu_item_components, menu_item_labels,
    menu_item_allergens, origin_declarations,
    import_batches, import_rows, settings
TO cafeteria_app;

GRANT SELECT ON users, user_role_cache, local_credentials TO cafeteria_app;
GRANT UPDATE (last_login_at) ON users TO cafeteria_app;
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
GRANT EXECUTE ON FUNCTION withdraw_publication_revision(bigint, text, text) TO cafeteria_app;

GRANT SELECT ON
    schema_migrations, application_roles, locations, offer_profiles,
    meal_periods, menu_types, dietary_labels, allergens, active_publications,
    audit_events, publication_lifecycle_events
TO cafeteria_app;

GRANT USAGE, SELECT ON
    menu_weeks_id_seq, menu_services_id_seq, dish_templates_id_seq,
    menu_items_id_seq, origin_declarations_id_seq, publication_revisions_id_seq,
    import_batches_id_seq, settings_id_seq
TO cafeteria_app;

GRANT SELECT ON
    schema_migrations, users, application_roles, user_role_cache, local_credentials,
    locations, offer_profiles, meal_periods, menu_types,
    menu_weeks, menu_services, dish_templates, menu_items, menu_item_prices,
    menu_item_components, dietary_labels, menu_item_labels, allergens,
    menu_item_allergens, origin_declarations, publication_revisions,
    publication_lifecycle_events, import_batches, import_rows, audit_events,
    settings, active_publications
TO cafeteria_backup;
GRANT SELECT ON
    users_id_seq, locations_id_seq, offer_profiles_id_seq, meal_periods_id_seq,
    menu_types_id_seq, menu_weeks_id_seq, menu_services_id_seq,
    dish_templates_id_seq, menu_items_id_seq, dietary_labels_id_seq,
    allergens_id_seq, origin_declarations_id_seq, publication_revisions_id_seq,
    publication_lifecycle_events_id_seq, import_batches_id_seq,
    audit_events_id_seq, settings_id_seq
TO cafeteria_backup;

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
    normalize_patient_key(text),
    patient_key_is_forbidden(text),
    jsonb_has_patient_forbidden_key(jsonb),
    jsonb_has_patient_forbidden_value(jsonb)
TO cafeteria_app;
GRANT EXECUTE ON FUNCTION
    sync_entra_user(uuid, uuid, text, text, text, text, text[]),
    issue_publication_capability(bigint, bigint, interval),
    provision_local_user(text, text, text, text, text[]),
    set_local_password(text, text, text),
    disable_local_user(text, text)
TO cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    REVOKE EXECUTE ON FUNCTIONS
    FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    REVOKE ALL ON TABLES FROM cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    REVOKE ALL ON SEQUENCES FROM cafeteria_auth_issuer;

COMMIT;
