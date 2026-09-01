-- Klinik Südhang Menüplanung – PostgreSQL-Baseline
-- Zwei fachlich getrennte Profile: patient und staff_guest.
-- Die Datei ist eine SQL-Baseline für eine leere Datenbank, keine behauptete Alembic-Migration.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS cafeteria;
SET search_path TO cafeteria, public;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL CHECK (btrim(name) <> ''),
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    application_version text NOT NULL CHECK (btrim(application_version) <> ''),
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    auth_provider text NOT NULL DEFAULT 'entra' CHECK (auth_provider IN ('entra', 'system', 'demo')),
    entra_tenant_id uuid,
    entra_object_id uuid,
    entra_subject_id text,
    display_name text NOT NULL CHECK (btrim(display_name) <> ''),
    email text,
    preferred_username text,
    last_seen_roles jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(last_seen_roles) = 'array'),
    last_login_at timestamptz,
    disabled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        auth_provider <> 'entra'
        OR (entra_tenant_id IS NOT NULL AND entra_object_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_entra_identity
    ON users(entra_tenant_id, entra_object_id)
    WHERE auth_provider = 'entra';

CREATE TABLE IF NOT EXISTS application_roles (
    role_code text PRIMARY KEY CHECK (role_code ~ '^Cafeteria\.(Editor|Publisher|Admin)$'),
    display_name text NOT NULL,
    description text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS user_role_cache (
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_code text NOT NULL REFERENCES application_roles(role_code),
    source text NOT NULL DEFAULT 'entra_token' CHECK (source IN ('entra_token', 'demo')),
    first_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (user_id, role_code)
);

CREATE TABLE IF NOT EXISTS locations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    code text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_-]{2,32}$'),
    name text NOT NULL CHECK (btrim(name) <> ''),
    timezone text NOT NULL DEFAULT 'Europe/Zurich',
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS offer_profiles (
    id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE CHECK (code IN ('patient', 'staff_guest')),
    display_name text NOT NULL,
    allows_prices boolean NOT NULL,
    allows_weekend boolean NOT NULL,
    allowed_meals text[] NOT NULL,
    CHECK (cardinality(allowed_meals) >= 1),
    CHECK (
        (code = 'patient' AND allows_prices = false AND allows_weekend = true AND allowed_meals @> ARRAY['LUNCH','DINNER']::text[])
        OR
        (code = 'staff_guest' AND allows_prices = true AND allows_weekend = false AND allowed_meals = ARRAY['LUNCH']::text[])
    )
);

CREATE TABLE IF NOT EXISTS meal_periods (
    id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE CHECK (code IN ('LUNCH', 'DINNER')),
    display_name text NOT NULL,
    sort_order smallint NOT NULL UNIQUE CHECK (sort_order > 0)
);

CREATE TABLE IF NOT EXISTS menu_types (
    id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE CHECK (code IN ('MENU_1', 'VEGGIE')),
    display_name text NOT NULL,
    sort_order smallint NOT NULL UNIQUE CHECK (sort_order > 0)
);

CREATE TABLE IF NOT EXISTS menu_weeks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    location_id bigint NOT NULL REFERENCES locations(id),
    profile_id smallint NOT NULL REFERENCES offer_profiles(id),
    week_start date NOT NULL,
    workflow_state text NOT NULL DEFAULT 'draft' CHECK (workflow_state IN ('draft', 'ready', 'published', 'archived')),
    title text,
    shared_note text,
    row_version bigint NOT NULL DEFAULT 1 CHECK (row_version > 0),
    created_by bigint REFERENCES users(id),
    updated_by bigint REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (EXTRACT(ISODOW FROM week_start) = 1),
    UNIQUE (location_id, profile_id, week_start)
);

CREATE TABLE IF NOT EXISTS menu_services (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    menu_week_id bigint NOT NULL REFERENCES menu_weeks(id) ON DELETE CASCADE,
    service_date date NOT NULL,
    meal_period_id smallint NOT NULL REFERENCES meal_periods(id),
    service_state text NOT NULL DEFAULT 'open' CHECK (service_state IN ('open', 'closed', 'holiday', 'company_holiday')),
    notice text,
    row_version bigint NOT NULL DEFAULT 1 CHECK (row_version > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((service_state = 'open') OR (notice IS NOT NULL AND btrim(notice) <> '')),
    UNIQUE (menu_week_id, service_date, meal_period_id)
);

CREATE TABLE IF NOT EXISTS dish_templates (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    menu_type_id smallint REFERENCES menu_types(id),
    profile_scope text NOT NULL DEFAULT 'common' CHECK (profile_scope IN ('common', 'patient', 'staff_guest')),
    title text NOT NULL CHECK (btrim(title) <> ''),
    description text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS menu_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    service_id bigint NOT NULL REFERENCES menu_services(id) ON DELETE CASCADE,
    menu_type_id smallint NOT NULL REFERENCES menu_types(id),
    dish_template_id bigint REFERENCES dish_templates(id) ON DELETE SET NULL,
    external_id text NOT NULL CHECK (btrim(external_id) <> ''),
    title text NOT NULL CHECK (btrim(title) <> ''),
    description text,
    note text,
    allergen_review_status text NOT NULL DEFAULT 'not_checked' CHECK (allergen_review_status IN ('not_checked', 'checked')),
    sort_order smallint NOT NULL CHECK (sort_order > 0),
    row_version bigint NOT NULL DEFAULT 1 CHECK (row_version > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (service_id, menu_type_id),
    UNIQUE (external_id)
);

CREATE TABLE IF NOT EXISTS menu_item_prices (
    menu_item_id bigint PRIMARY KEY REFERENCES menu_items(id) ON DELETE CASCADE,
    internal_rappen integer NOT NULL CHECK (internal_rappen > 0),
    external_rappen integer NOT NULL CHECK (external_rappen > 0),
    currency char(3) NOT NULL DEFAULT 'CHF' CHECK (currency = 'CHF'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (external_rappen >= internal_rappen)
);

CREATE TABLE IF NOT EXISTS menu_item_components (
    menu_item_id bigint NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    sort_order smallint NOT NULL CHECK (sort_order > 0),
    component_text text NOT NULL CHECK (btrim(component_text) <> ''),
    PRIMARY KEY (menu_item_id, sort_order)
);

CREATE TABLE IF NOT EXISTS dietary_labels (
    id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_]{2,32}$'),
    display_name text NOT NULL,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS menu_item_labels (
    menu_item_id bigint NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    label_id smallint NOT NULL REFERENCES dietary_labels(id),
    PRIMARY KEY (menu_item_id, label_id)
);

CREATE TABLE IF NOT EXISTS allergens (
    id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_]{1,32}$'),
    display_name text NOT NULL,
    eu_number smallint NOT NULL UNIQUE CHECK (eu_number BETWEEN 1 AND 14),
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS menu_item_allergens (
    menu_item_id bigint NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    allergen_id smallint NOT NULL REFERENCES allergens(id),
    presence text NOT NULL CHECK (presence IN ('contains', 'may_contain')),
    PRIMARY KEY (menu_item_id, allergen_id, presence)
);

CREATE TABLE IF NOT EXISTS origin_declarations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    menu_item_id bigint NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    ingredient text NOT NULL CHECK (btrim(ingredient) <> ''),
    country_code char(2) NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
    declaration_text text NOT NULL CHECK (btrim(declaration_text) <> ''),
    UNIQUE (menu_item_id, ingredient)
);

CREATE TABLE IF NOT EXISTS publication_revisions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    menu_week_id bigint NOT NULL REFERENCES menu_weeks(id) ON DELETE CASCADE,
    revision_number integer NOT NULL CHECK (revision_number > 0),
    revision_code text NOT NULL CHECK (btrim(revision_code) <> ''),
    snapshot_json jsonb NOT NULL CHECK (jsonb_typeof(snapshot_json) = 'object'),
    content_hash_sha256 text NOT NULL DEFAULT repeat('0', 64),
    published_by bigint NOT NULL REFERENCES users(id),
    published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    withdrawn_at timestamptz,
    withdrawal_reason text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (menu_week_id, revision_number),
    UNIQUE (revision_code),
    CHECK ((withdrawn_at IS NULL) = (withdrawal_reason IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_one_active_per_profile_week
    ON publication_revisions(menu_week_id)
    WHERE withdrawn_at IS NULL;

CREATE TABLE IF NOT EXISTS import_batches (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    profile_id smallint NOT NULL REFERENCES offer_profiles(id),
    source_filename text NOT NULL CHECK (btrim(source_filename) <> ''),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL DEFAULT 'validated' CHECK (status IN ('validated', 'rejected', 'imported')),
    row_count integer NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    error_count integer NOT NULL DEFAULT 0 CHECK (error_count >= 0),
    created_by bigint REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS import_rows (
    import_batch_id bigint NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    row_number integer NOT NULL CHECK (row_number > 0),
    row_payload jsonb NOT NULL CHECK (jsonb_typeof(row_payload) = 'object'),
    validation_errors jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(validation_errors) = 'array'),
    PRIMARY KEY (import_batch_id, row_number)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor_user_id bigint REFERENCES users(id),
    action text NOT NULL CHECK (btrim(action) <> ''),
    entity_type text NOT NULL CHECK (btrim(entity_type) <> ''),
    entity_public_id uuid,
    profile_code text CHECK (profile_code IN ('patient', 'staff_guest')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object')
);

CREATE TABLE IF NOT EXISTS settings (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    location_id bigint REFERENCES locations(id) ON DELETE CASCADE,
    profile_id smallint REFERENCES offer_profiles(id) ON DELETE CASCADE,
    setting_key text NOT NULL CHECK (setting_key ~ '^[a-z0-9_.-]{2,80}$'),
    setting_value jsonb NOT NULL,
    updated_by bigint REFERENCES users(id),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE NULLS NOT DISTINCT (location_id, profile_id, setting_key)
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION bump_row_version_and_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION validate_menu_service()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile text;
    v_meal text;
    v_week_start date;
BEGIN
    SELECT p.code, m.code, w.week_start
      INTO v_profile, v_meal, v_week_start
      FROM menu_weeks w
      JOIN offer_profiles p ON p.id = w.profile_id
      JOIN meal_periods m ON m.id = NEW.meal_period_id
     WHERE w.id = NEW.menu_week_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Woche oder Mahlzeit.' USING ERRCODE = '23503';
    END IF;

    IF NEW.service_date NOT BETWEEN v_week_start AND (v_week_start + 6) THEN
        RAISE EXCEPTION 'Servicedatum liegt ausserhalb der Kalenderwoche.' USING ERRCODE = '23514';
    END IF;

    IF v_profile = 'staff_guest' THEN
        IF v_meal <> 'LUNCH' THEN
            RAISE EXCEPTION 'Cafeteria erlaubt ausschliesslich LUNCH.' USING ERRCODE = '23514';
        END IF;
        IF EXTRACT(ISODOW FROM NEW.service_date) > 5 THEN
            RAISE EXCEPTION 'Cafeteria-Services am Wochenende sind unzulässig.' USING ERRCODE = '23514';
        END IF;
    ELSIF v_profile = 'patient' THEN
        IF v_meal NOT IN ('LUNCH', 'DINNER') THEN
            RAISE EXCEPTION 'Patientenprofil erlaubt nur LUNCH und DINNER.' USING ERRCODE = '23514';
        END IF;
    ELSE
        RAISE EXCEPTION 'Unbekanntes Angebotsprofil.' USING ERRCODE = '23514';
    END IF;

    IF TG_OP = 'UPDATE' AND NEW.service_state <> 'open'
       AND EXISTS (SELECT 1 FROM menu_items WHERE service_id = NEW.id) THEN
        RAISE EXCEPTION 'Ein Service mit Menüs kann nicht geschlossen werden.' USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION validate_menu_item()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_state text;
BEGIN
    SELECT service_state INTO v_state FROM menu_services WHERE id = NEW.service_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannter Service.' USING ERRCODE = '23503';
    END IF;
    IF v_state <> 'open' THEN
        RAISE EXCEPTION 'Geschlossene Services dürfen keine Menüpositionen enthalten.' USING ERRCODE = '23514';
    END IF;
    IF btrim(NEW.external_id) = '' OR btrim(NEW.title) = '' THEN
        RAISE EXCEPTION 'external_id und Titel dürfen nicht leer sein.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION validate_menu_item_price()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile text;
    v_meal text;
    v_service_date date;
BEGIN
    SELECT p.code, mp.code, s.service_date
      INTO v_profile, v_meal, v_service_date
      FROM menu_items i
      JOIN menu_services s ON s.id = i.service_id
      JOIN menu_weeks w ON w.id = s.menu_week_id
      JOIN offer_profiles p ON p.id = w.profile_id
      JOIN meal_periods mp ON mp.id = s.meal_period_id
     WHERE i.id = NEW.menu_item_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Menüposition.' USING ERRCODE = '23503';
    END IF;
    IF v_profile <> 'staff_guest' OR v_meal <> 'LUNCH' OR EXTRACT(ISODOW FROM v_service_date) > 5 THEN
        RAISE EXCEPTION 'Kosten sind nur im Cafeteria-Mittag von Montag bis Freitag zulässig.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION jsonb_has_patient_forbidden_key(v jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    k text;
    child jsonb;
BEGIN
    IF jsonb_typeof(v) = 'object' THEN
        FOR k, child IN SELECT key, value FROM jsonb_each(v)
        LOOP
            IF lower(k) IN ('price', 'prices', 'preis', 'preise', 'internal_rappen', 'external_rappen', 'preis_intern', 'preis_extern', 'currency', 'chf', 'rappen')
               OR lower(k) ~ '(^|_)(price|preis)(_|$)'
               OR lower(k) ~ '_rappen$' THEN
                RETURN true;
            END IF;
            IF jsonb_has_patient_forbidden_key(child) THEN
                RETURN true;
            END IF;
        END LOOP;
    ELSIF jsonb_typeof(v) = 'array' THEN
        FOR child IN SELECT value FROM jsonb_array_elements(v)
        LOOP
            IF jsonb_has_patient_forbidden_key(child) THEN
                RETURN true;
            END IF;
        END LOOP;
    END IF;
    RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION validate_publication_revision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile text;
    v_day jsonb;
    v_service jsonb;
    v_option jsonb;
    v_meals text[];
    v_open_cafeteria_days integer := 0;
BEGIN
    SELECT p.code INTO v_profile
      FROM menu_weeks w
      JOIN offer_profiles p ON p.id = w.profile_id
     WHERE w.id = NEW.menu_week_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Publikationswoche.' USING ERRCODE = '23503';
    END IF;

    IF NEW.snapshot_json->>'profile_code' IS DISTINCT FROM v_profile THEN
        RAISE EXCEPTION 'Snapshot-Profil stimmt nicht mit der Woche überein.' USING ERRCODE = '23514';
    END IF;
    IF jsonb_typeof(NEW.snapshot_json->'days') IS DISTINCT FROM 'array'
       OR jsonb_array_length(NEW.snapshot_json->'days') <> 7 THEN
        RAISE EXCEPTION 'Jeder Snapshot muss genau sieben Kalendertage enthalten.' USING ERRCODE = '23514';
    END IF;
    IF NEW.snapshot_json->>'revision_id' IS DISTINCT FROM NEW.revision_code THEN
        RAISE EXCEPTION 'revision_id im Snapshot stimmt nicht mit revision_code überein.' USING ERRCODE = '23514';
    END IF;

    IF v_profile = 'patient' THEN
        IF jsonb_has_patient_forbidden_key(NEW.snapshot_json)
           OR NEW.snapshot_json::text ~* '(CHF|0\\.00)' THEN
            RAISE EXCEPTION 'Patienten-Snapshot enthält unzulässige Kosteninformationen.' USING ERRCODE = '23514';
        END IF;
        FOR v_day IN SELECT value FROM jsonb_array_elements(NEW.snapshot_json->'days')
        LOOP
            SELECT array_agg(DISTINCT value->>'meal_code' ORDER BY value->>'meal_code')
              INTO v_meals
              FROM jsonb_array_elements(COALESCE(v_day->'services', '[]'::jsonb));
            IF v_meals IS DISTINCT FROM ARRAY['DINNER','LUNCH']::text[] THEN
                RAISE EXCEPTION 'Jeder Patiententag braucht Mittag und Abend.' USING ERRCODE = '23514';
            END IF;
            FOR v_service IN SELECT value FROM jsonb_array_elements(v_day->'services')
            LOOP
                IF jsonb_array_length(COALESCE(v_service->'options', '[]'::jsonb)) <> 2 THEN
                    RAISE EXCEPTION 'Jede Patientenmahlzeit braucht zwei Menüoptionen.' USING ERRCODE = '23514';
                END IF;
            END LOOP;
        END LOOP;
    ELSE
        FOR v_day IN SELECT value FROM jsonb_array_elements(NEW.snapshot_json->'days')
        LOOP
            FOR v_service IN SELECT value FROM jsonb_array_elements(COALESCE(v_day->'services', '[]'::jsonb))
            LOOP
                IF v_service->>'meal_code' <> 'LUNCH' THEN
                    RAISE EXCEPTION 'Cafeteria-Snapshot darf kein Abendessen enthalten.' USING ERRCODE = '23514';
                END IF;
                v_open_cafeteria_days := v_open_cafeteria_days + 1;
                IF jsonb_array_length(COALESCE(v_service->'options', '[]'::jsonb)) <> 2 THEN
                    RAISE EXCEPTION 'Jeder Cafeteria-Tag braucht zwei Menükarten.' USING ERRCODE = '23514';
                END IF;
                FOR v_option IN SELECT value FROM jsonb_array_elements(v_service->'options')
                LOOP
                    IF NOT (v_option ? 'prices')
                       OR NOT ((v_option->'prices') ? 'internal_rappen')
                       OR NOT ((v_option->'prices') ? 'external_rappen') THEN
                        RAISE EXCEPTION 'Cafeteria-Menüs brauchen interne und externe Kosten.' USING ERRCODE = '23514';
                    END IF;
                END LOOP;
            END LOOP;
        END LOOP;
        IF v_open_cafeteria_days <> 5 THEN
            RAISE EXCEPTION 'Cafeteria-Snapshot braucht genau fünf Werktage.' USING ERRCODE = '23514';
        END IF;
    END IF;

    NEW.content_hash_sha256 := encode(digest(convert_to(NEW.snapshot_json::text, 'UTF8'), 'sha256'), 'hex');
    NEW.published_at := COALESCE(NEW.published_at, clock_timestamp());
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION protect_audit_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Audit-Ereignisse sind unveränderlich.' USING ERRCODE = '55000';
END;
$$;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_locations_updated_at ON locations;
CREATE TRIGGER trg_locations_updated_at BEFORE UPDATE ON locations
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_menu_weeks_version ON menu_weeks;
CREATE TRIGGER trg_menu_weeks_version BEFORE UPDATE ON menu_weeks
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

DROP TRIGGER IF EXISTS trg_menu_services_validate ON menu_services;
CREATE TRIGGER trg_menu_services_validate BEFORE INSERT OR UPDATE ON menu_services
FOR EACH ROW EXECUTE FUNCTION validate_menu_service();

DROP TRIGGER IF EXISTS trg_menu_services_version ON menu_services;
CREATE TRIGGER trg_menu_services_version BEFORE UPDATE ON menu_services
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

DROP TRIGGER IF EXISTS trg_dish_templates_updated_at ON dish_templates;
CREATE TRIGGER trg_dish_templates_updated_at BEFORE UPDATE ON dish_templates
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_menu_items_validate ON menu_items;
CREATE TRIGGER trg_menu_items_validate BEFORE INSERT OR UPDATE ON menu_items
FOR EACH ROW EXECUTE FUNCTION validate_menu_item();

DROP TRIGGER IF EXISTS trg_menu_items_version ON menu_items;
CREATE TRIGGER trg_menu_items_version BEFORE UPDATE ON menu_items
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

DROP TRIGGER IF EXISTS trg_menu_item_prices_validate ON menu_item_prices;
CREATE TRIGGER trg_menu_item_prices_validate BEFORE INSERT OR UPDATE ON menu_item_prices
FOR EACH ROW EXECUTE FUNCTION validate_menu_item_price();

DROP TRIGGER IF EXISTS trg_menu_item_prices_updated_at ON menu_item_prices;
CREATE TRIGGER trg_menu_item_prices_updated_at BEFORE UPDATE ON menu_item_prices
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_publication_validate ON publication_revisions;
CREATE TRIGGER trg_publication_validate BEFORE INSERT OR UPDATE ON publication_revisions
FOR EACH ROW EXECUTE FUNCTION validate_publication_revision();

DROP TRIGGER IF EXISTS trg_audit_no_update ON audit_events;
CREATE TRIGGER trg_audit_no_update BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION protect_audit_event();

CREATE OR REPLACE VIEW active_publications AS
SELECT
    r.id AS revision_db_id,
    r.public_id AS revision_public_id,
    r.revision_code,
    r.revision_number,
    r.snapshot_json,
    r.content_hash_sha256,
    r.published_at,
    w.public_id AS week_public_id,
    w.week_start,
    (w.week_start + 6) AS week_end,
    p.code AS profile_code,
    l.code AS location_code,
    l.name AS location_name
FROM publication_revisions r
JOIN menu_weeks w ON w.id = r.menu_week_id
JOIN offer_profiles p ON p.id = w.profile_id
JOIN locations l ON l.id = w.location_id
WHERE r.withdrawn_at IS NULL;

COMMIT;
