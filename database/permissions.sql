-- Wird als Owner nach schema.sql/seed.sql ausgeführt. Keine Passwörter und keine CREATE ROLE-Anweisungen.
BEGIN;
SET search_path TO cafeteria, public;

REVOKE ALL ON SCHEMA cafeteria FROM PUBLIC;
GRANT USAGE ON SCHEMA cafeteria TO cafeteria_app, cafeteria_backup;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    user_role_cache, menu_weeks, menu_services, dish_templates,
    menu_items, menu_item_prices, menu_item_components, menu_item_labels,
    menu_item_allergens, origin_declarations,
    import_batches, import_rows, settings
TO cafeteria_app;

GRANT SELECT, INSERT, UPDATE ON users, local_credentials TO cafeteria_app;
GRANT SELECT, INSERT ON publication_revisions TO cafeteria_app;
REVOKE UPDATE (withdrawn_at, withdrawal_reason, withdrawn_by) ON publication_revisions FROM cafeteria_app;
REVOKE INSERT, UPDATE, DELETE ON publication_lifecycle_events FROM cafeteria_app;
REVOKE ALL ON auth_capability_secrets FROM cafeteria_app;
REVOKE ALL ON auth_capability_nonces FROM cafeteria_app;
REVOKE EXECUTE ON FUNCTION bootstrap_auth_capability_secret() FROM cafeteria_app;
REVOKE EXECUTE ON FUNCTION rotate_auth_capability_secret() FROM cafeteria_app;
REVOKE EXECUTE ON FUNCTION issue_publication_capability(bigint, bigint, interval) FROM cafeteria_app;
GRANT EXECUTE ON FUNCTION withdraw_publication_revision(bigint, text, text) TO cafeteria_app;

GRANT SELECT ON
    schema_migrations, application_roles, locations, offer_profiles,
    meal_periods, menu_types, dietary_labels, allergens, active_publications,
    audit_events, publication_lifecycle_events
TO cafeteria_app;

GRANT INSERT ON audit_events TO cafeteria_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA cafeteria TO cafeteria_app;

GRANT SELECT ON ALL TABLES IN SCHEMA cafeteria TO cafeteria_backup;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA cafeteria TO cafeteria_backup;

ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
    GRANT SELECT ON TABLES TO cafeteria_backup;

COMMIT;
