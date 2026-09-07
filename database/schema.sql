-- Klinik Südhang Menüplanung – PostgreSQL-Baseline
-- Zwei fachlich getrennte Profile: patient und staff_guest.
-- Schema v20 für eine leere Datenbank; keine behauptete Alembic-Migration.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS cafeteria;
SET search_path TO cafeteria, public;

-- Der Runner protokolliert hier die feste Migrationskette bis Schema v18.
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
    auth_provider text NOT NULL DEFAULT 'entra' CHECK (auth_provider IN ('entra', 'local', 'system', 'demo')),
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
    authz_version bigint NOT NULL DEFAULT 1 CHECK (authz_version > 0),
    CONSTRAINT users_provider_identity_check CHECK (
        (auth_provider = 'entra' AND entra_tenant_id IS NOT NULL AND entra_object_id IS NOT NULL)
        OR
        (auth_provider IN ('local', 'system', 'demo')
         AND entra_tenant_id IS NULL AND entra_object_id IS NULL AND entra_subject_id IS NULL)
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
    source text NOT NULL DEFAULT 'entra_token' CHECK (source IN ('entra_token', 'local', 'demo')),
    first_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (user_id, role_code)
);

CREATE TABLE IF NOT EXISTS local_credentials (
    user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    username text NOT NULL UNIQUE
        CHECK (username = lower(username))
        CHECK (username ~ '^[a-z0-9][a-z0-9._-]{2,63}$'),
    password_hash text NOT NULL CONSTRAINT local_credentials_werkzeug_password_hash_check CHECK (
        password_hash ~ '^(scrypt:[0-9]+:[0-9]+:[0-9]+|pbkdf2:sha256:[0-9]+)\$[^$]+\$[0-9a-f]+$'
    ),
    failed_login_count integer NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0),
    locked_until timestamptz,
    last_failed_at timestamptz,
    password_changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (locked_until IS NULL OR failed_login_count > 0)
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
    CONSTRAINT offer_profiles_display_name_check
        CHECK (btrim(display_name) <> '' AND length(display_name) <= 80),
    CHECK (cardinality(allowed_meals) >= 1),
    CONSTRAINT offer_profiles_profile_contract_check CHECK (
        (code = 'patient' AND allows_prices = false AND allows_weekend = true AND allowed_meals @> ARRAY['LUNCH','DINNER']::text[])
        OR
        (code = 'staff_guest' AND allows_prices = true AND allowed_meals = ARRAY['LUNCH']::text[])
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
    service_start time,
    service_end time,
    CHECK ((service_state = 'open') OR (notice IS NOT NULL AND btrim(notice) <> '')),
    CONSTRAINT menu_services_time_window_check
        CHECK (service_start IS NULL OR service_end IS NULL OR service_end > service_start),
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

CREATE TABLE IF NOT EXISTS menu_components (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    location_id bigint NOT NULL REFERENCES locations(id),
    profile_scope text NOT NULL CHECK (profile_scope IN ('common', 'patient', 'staff_guest')),
    category text NOT NULL CHECK (category IN ('meat', 'side', 'vegetable', 'sauce', 'dessert', 'other')),
    name text NOT NULL CHECK (btrim(name) <> ''),
    origin_country_code char(2) CHECK (origin_country_code ~ '^[A-Z]{2}$'),
    active boolean NOT NULL DEFAULT true,
    row_version bigint NOT NULL DEFAULT 1 CHECK (row_version > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_menu_components_location_scope_name
    ON menu_components(location_id, profile_scope, lower(btrim(name)));

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
    allergen_mode text NOT NULL DEFAULT 'manual' CHECK (allergen_mode IN ('auto', 'manual')),
    origin_mode text NOT NULL DEFAULT 'manual' CHECK (origin_mode IN ('auto', 'manual')),
    label_mode text NOT NULL DEFAULT 'manual' CHECK (label_mode IN ('auto', 'manual')),
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
    component_id bigint REFERENCES menu_components(id) ON DELETE RESTRICT,
    component_row_version bigint CHECK (component_row_version > 0),
    CONSTRAINT menu_item_components_component_link_check CHECK (
        (component_id IS NULL AND component_row_version IS NULL)
        OR (component_id IS NOT NULL AND component_row_version IS NOT NULL)
    ),
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

CREATE TABLE IF NOT EXISTS component_labels (
    component_id bigint NOT NULL REFERENCES menu_components(id) ON DELETE CASCADE,
    label_id smallint NOT NULL REFERENCES dietary_labels(id),
    PRIMARY KEY (component_id, label_id)
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

CREATE TABLE IF NOT EXISTS component_allergens (
    component_id bigint NOT NULL REFERENCES menu_components(id) ON DELETE CASCADE,
    allergen_id smallint NOT NULL REFERENCES allergens(id),
    presence text NOT NULL CHECK (presence IN ('contains', 'may_contain')),
    PRIMARY KEY (component_id, allergen_id)
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
    menu_week_id bigint NOT NULL REFERENCES menu_weeks(id) ON DELETE RESTRICT,
    revision_number integer NOT NULL CHECK (revision_number > 0),
    revision_code text NOT NULL CHECK (btrim(revision_code) <> ''),
    snapshot_json jsonb NOT NULL CHECK (jsonb_typeof(snapshot_json) = 'object'),
    content_hash_sha256 text NOT NULL DEFAULT repeat('0', 64),
    published_by bigint NOT NULL REFERENCES users(id),
    published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    withdrawn_at timestamptz,
    withdrawal_reason text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    profile_id smallint NOT NULL REFERENCES offer_profiles(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    week_start date NOT NULL,
    withdrawn_by bigint REFERENCES users(id),
    UNIQUE (menu_week_id, revision_number),
    UNIQUE (revision_code),
    CHECK ((withdrawn_at IS NULL) = (withdrawal_reason IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_one_active_per_profile_week
    ON publication_revisions(menu_week_id)
    WHERE withdrawn_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_one_active_per_frozen_identity
    ON publication_revisions(profile_id, location_id, week_start)
    WHERE withdrawn_at IS NULL;

CREATE TABLE IF NOT EXISTS publication_lifecycle_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    revision_id bigint NOT NULL REFERENCES publication_revisions(id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (event_type IN ('activated', 'withdrawn')),
    reason text,
    actor_user_id bigint REFERENCES users(id),
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        (event_type = 'activated' AND (reason IS NULL OR btrim(reason) = ''))
        OR
        (event_type = 'withdrawn' AND reason IS NOT NULL AND btrim(reason) <> '')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_lifecycle_once
    ON publication_lifecycle_events(revision_id, event_type);

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

CREATE TABLE IF NOT EXISTS branding_assets (
    sha256 text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    png_data bytea NOT NULL CHECK (
        octet_length(png_data) BETWEEN 8 AND 1048576
        AND substring(png_data FROM 1 FOR 8) = decode('89504e470d0a1a0a', 'hex')
        AND sha256 = encode(pg_catalog.sha256(png_data), 'hex')
    ),
    width integer NOT NULL CHECK (width BETWEEN 1 AND 2048),
    height integer NOT NULL CHECK (height BETWEEN 1 AND 2048),
    created_by bigint NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

REVOKE ALL ON branding_assets FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT SELECT, INSERT ON branding_assets TO cafeteria_app;
GRANT SELECT ON branding_assets TO cafeteria_backup;

CREATE TABLE IF NOT EXISTS api_keys (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    label text NOT NULL CHECK (btrim(label) <> '' AND length(label) <= 80),
    key_prefix text NOT NULL UNIQUE CHECK (key_prefix ~ '^dbk_[A-Za-z0-9_-]{8}$'),
    key_hash text NOT NULL UNIQUE CHECK (key_hash ~ '^sha256:[0-9a-f]{64}$'),
    scopes text[] NOT NULL CHECK (
        cardinality(scopes) >= 1 AND scopes <@ ARRAY['preview.read']::text[]
    ),
    created_by bigint NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz CHECK (expires_at IS NULL OR expires_at > created_at),
    last_used_at timestamptz,
    revoked_at timestamptz,
    revoked_by bigint REFERENCES users(id),
    CHECK ((revoked_at IS NULL) = (revoked_by IS NULL))
);

CREATE TABLE IF NOT EXISTS auth_capability_secrets (
    id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    secret bytea NOT NULL CHECK (octet_length(secret) = 32),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    retired_at timestamptz,
    CHECK (active OR retired_at IS NOT NULL),
    CHECK (NOT active OR retired_at IS NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_auth_capability_one_active
    ON auth_capability_secrets ((true)) WHERE active;

CREATE TABLE IF NOT EXISTS auth_capability_nonces (
    nonce bytea PRIMARY KEY CHECK (octet_length(nonce) = 16),
    actor_user_id bigint NOT NULL REFERENCES users(id),
    revision_id bigint NOT NULL REFERENCES publication_revisions(id),
    consumed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

REVOKE ALL ON auth_capability_secrets FROM PUBLIC;
REVOKE ALL ON auth_capability_nonces FROM PUBLIC;

INSERT INTO auth_capability_secrets(secret)
SELECT public.gen_random_bytes(32)
WHERE NOT EXISTS (SELECT 1 FROM auth_capability_secrets);

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

CREATE OR REPLACE FUNCTION validate_local_credential()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM users WHERE id = NEW.user_id AND auth_provider = 'local'
    ) THEN
        RAISE EXCEPTION 'Lokale Anmeldedaten benötigen einen lokalen Benutzer.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION validate_user_auth_provider()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.authz_version < OLD.authz_version THEN
        RAISE EXCEPTION 'authz_version darf nicht zurückgesetzt werden.' USING ERRCODE = '42501';
    END IF;
    IF NEW.auth_provider <> 'local'
       AND EXISTS (SELECT 1 FROM local_credentials WHERE user_id = NEW.id) THEN
        RAISE EXCEPTION 'Benutzer mit lokalen Anmeldedaten muss auth_provider=local behalten.' USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1 FROM user_role_cache c
        WHERE c.user_id = NEW.id
          AND NOT (
              (c.source = 'entra_token' AND NEW.auth_provider = 'entra')
              OR (c.source = 'local' AND NEW.auth_provider = 'local')
              OR (c.source = 'demo' AND NEW.auth_provider = 'demo')
          )
    ) THEN
        RAISE EXCEPTION 'Rollenquelle passt nicht zum Authentifizierungsanbieter.' USING ERRCODE = '23514';
    END IF;
    IF NEW.disabled_at IS DISTINCT FROM OLD.disabled_at THEN
        NEW.authz_version := OLD.authz_version + 1;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION validate_user_role_source()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_provider text;
BEGIN
    SELECT auth_provider INTO v_provider FROM users WHERE id = NEW.user_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannter Benutzer für Rollenzuordnung.' USING ERRCODE = '23503';
    END IF;
    IF (NEW.source = 'entra_token' AND v_provider <> 'entra')
       OR (NEW.source = 'local' AND v_provider <> 'local')
       OR (NEW.source = 'demo' AND v_provider <> 'demo') THEN
        RAISE EXCEPTION 'Rollenquelle passt nicht zum Authentifizierungsanbieter.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION bump_user_authz_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id
       AND NEW.role_code IS NOT DISTINCT FROM OLD.role_code
       AND NEW.source IS NOT DISTINCT FROM OLD.source THEN
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' AND NEW.user_id IS DISTINCT FROM OLD.user_id THEN
        UPDATE users SET authz_version = authz_version + 1 WHERE id IN (OLD.user_id, NEW.user_id);
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE users SET authz_version = authz_version + 1 WHERE id = OLD.user_id;
    ELSE
        UPDATE users SET authz_version = authz_version + 1 WHERE id = NEW.user_id;
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

CREATE OR REPLACE FUNCTION validate_menu_week()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.profile_id IS DISTINCT FROM OLD.profile_id THEN
        RAISE EXCEPTION 'Das Angebotsprofil einer Woche ist unveränderlich.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE'
       AND OLD.workflow_state = 'published'
       AND NEW.workflow_state IS DISTINCT FROM OLD.workflow_state THEN
        PERFORM 1 FROM menu_weeks WHERE id = OLD.id FOR UPDATE;
        IF EXISTS (
            SELECT 1 FROM publication_revisions
            WHERE menu_week_id = OLD.id AND withdrawn_at IS NULL
        ) THEN
            RAISE EXCEPTION 'Eine publizierte Woche mit aktiver Publikationsrevision kann nicht zurückgestuft werden.'
                USING ERRCODE = '55000';
        END IF;
    END IF;
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
    v_allows_weekend boolean;
    v_week_start date;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.menu_week_id IS DISTINCT FROM OLD.menu_week_id THEN
        RAISE EXCEPTION 'Ein Service kann nicht in eine andere Woche verschoben werden.' USING ERRCODE = '23514';
    END IF;

    SELECT p.code, m.code, w.week_start, p.allows_weekend
      INTO v_profile, v_meal, v_week_start, v_allows_weekend
      FROM menu_weeks w
      JOIN offer_profiles p ON p.id = w.profile_id
      JOIN meal_periods m ON m.id = NEW.meal_period_id
     WHERE w.id = NEW.menu_week_id
     FOR SHARE OF p;

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
        IF EXTRACT(ISODOW FROM NEW.service_date) > 5 AND NOT v_allows_weekend
           AND (TG_OP = 'INSERT' OR NEW.service_date IS DISTINCT FROM OLD.service_date
                OR NEW.meal_period_id IS DISTINCT FROM OLD.meal_period_id) THEN
            RAISE EXCEPTION 'Cafeteria-Services am Wochenende sind nicht freigegeben.' USING ERRCODE = '23514';
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
    IF TG_OP = 'UPDATE' AND NEW.service_id IS DISTINCT FROM OLD.service_id THEN
        RAISE EXCEPTION 'Eine Menüposition kann nicht einem anderen Service zugeordnet werden.' USING ERRCODE = '23514';
    END IF;
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

CREATE OR REPLACE FUNCTION validate_menu_item_component_scope()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = cafeteria, pg_temp
AS $validate_menu_item_component_scope$
DECLARE
    item_location_id bigint;
    item_profile_scope text;
    component_location_id bigint;
    component_profile_scope text;
BEGIN
    IF NEW.component_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT week_row.location_id, profile.code
    INTO item_location_id, item_profile_scope
    FROM menu_items item
    JOIN menu_services service ON service.id=item.service_id
    JOIN menu_weeks week_row ON week_row.id=service.menu_week_id
    JOIN offer_profiles profile ON profile.id=week_row.profile_id
    WHERE item.id=NEW.menu_item_id
    FOR KEY SHARE OF item, service, week_row;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    SELECT component.location_id, component.profile_scope
    INTO component_location_id, component_profile_scope
    FROM menu_components component
    WHERE component.id=NEW.component_id
    FOR KEY SHARE OF component;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    IF component_location_id IS DISTINCT FROM item_location_id THEN
        RAISE EXCEPTION
            'Komponenten-Location % passt nicht zur Menue-Location %.',
            component_location_id,
            item_location_id
            USING ERRCODE='23514',
                  CONSTRAINT='menu_item_components_scope';
    END IF;

    IF component_profile_scope <> 'common'
       AND component_profile_scope IS DISTINCT FROM item_profile_scope THEN
        RAISE EXCEPTION
            'Komponenten-Profil-Scope % ist fuer Menueprofil % nicht erlaubt.',
            component_profile_scope,
            item_profile_scope
            USING ERRCODE='23514',
                  CONSTRAINT='menu_item_components_scope';
    END IF;

    RETURN NEW;
END;
$validate_menu_item_component_scope$;

CREATE OR REPLACE FUNCTION protect_menu_component_identity()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = cafeteria, pg_temp
AS $protect_menu_component_identity$
BEGIN
    IF NEW.location_id IS DISTINCT FROM OLD.location_id THEN
        RAISE EXCEPTION 'Die Komponenten-Location ist unveraenderlich.'
            USING ERRCODE='23514',
                  CONSTRAINT='menu_components_location_identity';
    END IF;
    IF NEW.profile_scope IS DISTINCT FROM OLD.profile_scope THEN
        RAISE EXCEPTION 'Der Komponenten-Profil-Scope ist unveraenderlich.'
            USING ERRCODE='23514',
                  CONSTRAINT='menu_components_profile_scope_identity';
    END IF;
    RETURN NEW;
END;
$protect_menu_component_identity$;

CREATE OR REPLACE FUNCTION protect_menu_week_location_identity()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = cafeteria, pg_temp
AS $protect_menu_week_location_identity$
BEGIN
    IF NEW.location_id IS DISTINCT FROM OLD.location_id THEN
        RAISE EXCEPTION 'Die Wochen-Location ist unveraenderlich.'
            USING ERRCODE='23514',
                  CONSTRAINT='menu_weeks_location_identity';
    END IF;
    RETURN NEW;
END;
$protect_menu_week_location_identity$;

-- Kosten folgen dem Service: validate_menu_service entscheidet datumsgenau, ob ein
-- Cafeteria-Wochenendservice ueberhaupt entstehen darf. Ein staff_guest-Service an Sa/So
-- existiert daher nur mit erteilter Wochenendfreigabe; seine Menues behalten regulaere
-- Preise auch nach dem Abschalten des Schalters. Profil-, Mahlzeit- und Betragsregeln
-- bleiben unveraendert: Kosten nur fuer staff_guest und nur zum Mittag.
CREATE OR REPLACE FUNCTION validate_menu_item_price()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile text;
    v_meal text;
BEGIN
    SELECT p.code, mp.code
      INTO v_profile, v_meal
      FROM menu_items i
      JOIN menu_services s ON s.id = i.service_id
      JOIN menu_weeks w ON w.id = s.menu_week_id
      JOIN offer_profiles p ON p.id = w.profile_id
      JOIN meal_periods mp ON mp.id = s.meal_period_id
     WHERE i.id = NEW.menu_item_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Menüposition.' USING ERRCODE = '23503';
    END IF;
    IF v_profile <> 'staff_guest' OR v_meal <> 'LUNCH' THEN
        RAISE EXCEPTION 'Kosten sind nur im Cafeteria-Mittag zulässig.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION normalize_patient_key(k text)
RETURNS text
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT lower(
        regexp_replace(
            regexp_replace(
                k,
                U&'[\00AD\0600-\0605\061C\06DD\070F\0890-\0891\08E2\180E\200B-\200F\202A-\202E\2060-\2064\2066-\206F\FEFF\FFF9-\FFFB\+0110BD\+0110CD\+013430-\+01343F\+01BCA0-\+01BCA3\+01D173-\+01D17A\+0E0001\+0E0020-\+0E007F]',
                '',
                'g'
            ),
            '[^A-Za-z0-9]+',
            '',
            'g'
        )
    );
$$;

CREATE OR REPLACE FUNCTION patient_key_is_forbidden(k text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT compact = ''
        OR compact <> ALL (ARRAY[
            'channel', 'days', 'date', 'notice', 'services', 'mealcode', 'mealname',
            'options', 'allergenreviewstatus', 'allergens', 'components', 'description',
            'externalid', 'labels', 'note', 'origins', 'title', 'typecode', 'typename',
            'code', 'name', 'presence', 'countrycode', 'ingredient', 'text', 'state',
            'weekday', 'location', 'profilecode', 'revisionid', 'schemaversion',
            'sharednote', 'weekend', 'weekstart', 'servicestate',
            'servicestart', 'serviceend', 'areaname'
        ]::text[])
        OR compact ~ '(price|prices|preis|preise|cost|costs|amount|amounts|kosten|betrag|rappen|currency|chf|fee|tarif|tariff|charge)'
    FROM (SELECT cafeteria.normalize_patient_key(k) AS compact) s;
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
            IF patient_key_is_forbidden(k) THEN
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

CREATE OR REPLACE FUNCTION jsonb_has_patient_forbidden_value(v jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    child jsonb;
    scalar_text text;
BEGIN
    IF jsonb_typeof(v) = 'object' THEN
        FOR child IN SELECT value FROM jsonb_each(v)
        LOOP
            IF jsonb_has_patient_forbidden_value(child) THEN
                RETURN true;
            END IF;
        END LOOP;
    ELSIF jsonb_typeof(v) = 'array' THEN
        FOR child IN SELECT value FROM jsonb_array_elements(v)
        LOOP
            IF jsonb_has_patient_forbidden_value(child) THEN
                RETURN true;
            END IF;
        END LOOP;
    ELSIF jsonb_typeof(v) = 'string' THEN
        scalar_text := trim(both '"' from v::text);
        scalar_text := regexp_replace(
            scalar_text,
            '(^|[^0-9])(([01]?[0-9]|2[0-3]):[0-5][0-9]([[:space:]]*Uhr)?|([01]?[0-9]|2[0-3])[.][0-5][0-9][[:space:]]*Uhr)([^0-9]|$)',
            '\1\6',
            'g'
        );
        IF scalar_text ~* '(^|[^[:alpha:]])(CHF|Rappen|Franken|Intern|Extern|Fr[.]?)([^[:alpha:]]|$)'
           OR scalar_text ~ '[0-9]+[.,][0-9]{2}([^0-9]|$)' THEN
            RETURN true;
        END IF;
    ELSIF jsonb_typeof(v) = 'number' THEN
        IF v::text ~ '\.' THEN
            RETURN true;
        END IF;
    END IF;
    RETURN false;
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

CREATE OR REPLACE FUNCTION record_local_login_lock()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
BEGIN
    IF NEW.failed_login_count >= 5
       AND NEW.locked_until IS NOT NULL
       AND NEW.locked_until > clock_timestamp()
       AND (OLD.locked_until IS NULL OR OLD.locked_until <= clock_timestamp()) THEN
        INSERT INTO audit_events(actor_user_id, action, entity_type, details)
        VALUES (
            NULL,
            'auth.local_login_locked',
            'user',
            jsonb_build_object(
                'user_id', NEW.user_id,
                'failed_login_count', NEW.failed_login_count
            )
        );
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION validate_publication_revision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile text;
    v_profile_id smallint;
    v_location_id bigint;
    v_workflow_state text;
    v_week_start date;
    v_day jsonb;
    v_day_index integer;
    v_service jsonb;
    v_option jsonb;
    v_meals text[];
    v_menu_types text[];
    v_state text;
    v_expected_weekdays text[] := ARRAY[
        'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'
    ];
    v_prices jsonb;
BEGIN
    SELECT p.code, p.id, w.location_id, w.workflow_state, w.week_start
      INTO v_profile, v_profile_id, v_location_id, v_workflow_state, v_week_start
      FROM menu_weeks w
      JOIN offer_profiles p ON p.id = w.profile_id
     WHERE w.id = NEW.menu_week_id
     FOR UPDATE OF w;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Publikationswoche.' USING ERRCODE = '23503';
    END IF;
    IF TG_OP = 'INSERT' AND NEW.withdrawn_at IS NOT NULL THEN
        RAISE EXCEPTION 'Neue Publikationsrevisionen starten aktiv.' USING ERRCODE = '23514';
    END IF;
    IF v_workflow_state <> 'published' THEN
        RAISE EXCEPTION 'Nur eine publizierte Woche darf eine Publikationsrevision erhalten.' USING ERRCODE = '23514';
    END IF;
    NEW.profile_id := v_profile_id;
    NEW.location_id := v_location_id;
    NEW.week_start := v_week_start;
    IF NEW.snapshot_json->>'profile_code' IS DISTINCT FROM v_profile THEN
        RAISE EXCEPTION 'Snapshot-Profil stimmt nicht mit der Woche überein.' USING ERRCODE = '23514';
    END IF;
    IF NEW.snapshot_json->>'week_start' IS DISTINCT FROM v_week_start::text
       OR NEW.snapshot_json->>'week_end' IS DISTINCT FROM (v_week_start + 6)::text THEN
        RAISE EXCEPTION 'Snapshot-Kalenderwoche stimmt nicht mit der Publikationswoche überein.' USING ERRCODE = '23514';
    END IF;
    IF jsonb_typeof(NEW.snapshot_json->'days') IS DISTINCT FROM 'array'
       OR jsonb_array_length(NEW.snapshot_json->'days') <> 7 THEN
        RAISE EXCEPTION 'Jeder Snapshot muss genau sieben Kalendertage enthalten.' USING ERRCODE = '23514';
    END IF;
    IF NEW.snapshot_json->>'revision_id' IS DISTINCT FROM NEW.revision_code THEN
        RAISE EXCEPTION 'revision_id im Snapshot stimmt nicht mit revision_code überein.' USING ERRCODE = '23514';
    END IF;
    IF NEW.snapshot_json ? 'area_name'
       AND (jsonb_typeof(NEW.snapshot_json->'area_name') IS DISTINCT FROM 'string'
            OR btrim(NEW.snapshot_json->>'area_name') = ''
            OR length(NEW.snapshot_json->>'area_name') > 80) THEN
        RAISE EXCEPTION 'Snapshot-Bereichsname muss ein nicht leerer Text mit höchstens 80 Zeichen sein.' USING ERRCODE = '23514';
    END IF;

    FOR v_day, v_day_index IN
        SELECT value, ordinality::integer
        FROM jsonb_array_elements(NEW.snapshot_json->'days') WITH ORDINALITY
    LOOP
        IF COALESCE(v_day->>'date', '') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
           OR (v_day->>'date')::date <> v_week_start + (v_day_index - 1) THEN
            RAISE EXCEPTION 'Snapshot-Kalendertage müssen lückenlos der Woche entsprechen.' USING ERRCODE = '23514';
        END IF;
        IF v_day->>'weekday' IS DISTINCT FROM v_expected_weekdays[v_day_index] THEN
            RAISE EXCEPTION 'Snapshot-Wochentag stimmt nicht mit dem Datum überein.' USING ERRCODE = '23514';
        END IF;
        IF jsonb_typeof(v_day->'services') IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'Jeder Snapshot-Tag braucht ein Service-Array.' USING ERRCODE = '23514';
        END IF;

        SELECT array_agg(DISTINCT value->>'meal_code' ORDER BY value->>'meal_code')
          INTO v_meals
          FROM jsonb_array_elements(v_day->'services');

        IF v_profile = 'patient' THEN
            IF v_meals IS DISTINCT FROM ARRAY['DINNER','LUNCH']::text[]
               OR jsonb_array_length(v_day->'services') <> 2 THEN
                RAISE EXCEPTION 'Jeder Patiententag braucht genau Mittag und Abend.' USING ERRCODE = '23514';
            END IF;
        ELSIF v_day_index <= 5 THEN
            IF v_meals IS DISTINCT FROM ARRAY['LUNCH']::text[]
               OR jsonb_array_length(v_day->'services') <> 1 THEN
                RAISE EXCEPTION 'Jeder Cafeteria-Werktag braucht genau einen Mittagsservice.' USING ERRCODE = '23514';
            END IF;
        ELSIF jsonb_array_length(v_day->'services') > 1
           OR (jsonb_array_length(v_day->'services') = 1
               AND v_meals IS DISTINCT FROM ARRAY['LUNCH']::text[]) THEN
            RAISE EXCEPTION 'Cafeteria-Wochenende erlaubt höchstens einen Mittagsservice.' USING ERRCODE = '23514';
        END IF;

        FOR v_service IN SELECT value FROM jsonb_array_elements(v_day->'services')
        LOOP
            v_state := COALESCE(NULLIF(v_service->>'service_state', ''), 'open');
            IF v_state NOT IN ('open', 'closed', 'holiday', 'company_holiday') THEN
                RAISE EXCEPTION 'service_state muss open, closed, holiday oder company_holiday sein.' USING ERRCODE = '23514';
            END IF;
            IF (v_service ? 'service_start'
                AND (jsonb_typeof(v_service->'service_start') IS DISTINCT FROM 'string'
                     OR v_service->>'service_start' !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'))
               OR (v_service ? 'service_end'
                AND (jsonb_typeof(v_service->'service_end') IS DISTINCT FROM 'string'
                     OR v_service->>'service_end' !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$')) THEN
                RAISE EXCEPTION 'Servicezeiten müssen als HH:MM zwischen 00:00 und 23:59 angegeben werden.' USING ERRCODE = '23514';
            END IF;
            IF v_service ? 'service_start' AND v_service ? 'service_end'
               AND (v_service->>'service_end')::time <= (v_service->>'service_start')::time THEN
                RAISE EXCEPTION 'Das Serviceende muss nach dem Servicebeginn liegen.' USING ERRCODE = '23514';
            END IF;
            IF jsonb_typeof(v_service->'options') IS DISTINCT FROM 'array' THEN
                RAISE EXCEPTION 'Jede Mahlzeit braucht ein Options-Array.' USING ERRCODE = '23514';
            END IF;
            IF v_state = 'open' THEN
                IF jsonb_array_length(v_service->'options') <> 2 THEN
                    RAISE EXCEPTION 'Eine offene Mahlzeit braucht genau zwei Menüoptionen.' USING ERRCODE = '23514';
                END IF;
                SELECT array_agg(DISTINCT value->>'type_code' ORDER BY value->>'type_code')
                  INTO v_menu_types
                  FROM jsonb_array_elements(v_service->'options');
                IF v_menu_types IS DISTINCT FROM ARRAY['MENU_1','VEGGIE']::text[] THEN
                    RAISE EXCEPTION 'Jede Mahlzeit braucht exakt die Menüarten MENU_1 und VEGGIE.' USING ERRCODE = '23514';
                END IF;
                IF v_profile = 'staff_guest' THEN
                    FOR v_option IN SELECT value FROM jsonb_array_elements(v_service->'options')
                    LOOP
                        v_prices := v_option->'prices';
                        IF jsonb_typeof(v_prices) IS DISTINCT FROM 'object'
                           OR (SELECT count(*) FROM jsonb_object_keys(v_prices)) <> 3
                           OR NOT (v_prices ?& ARRAY['internal_rappen','external_rappen','currency'])
                           OR v_prices->>'currency' IS DISTINCT FROM 'CHF' THEN
                            RAISE EXCEPTION 'Cafeteria-Menüs brauchen exakt die CHF-Kostenstruktur.' USING ERRCODE = '23514';
                        END IF;
                        IF jsonb_typeof(v_prices->'internal_rappen') IS DISTINCT FROM 'number'
                           OR jsonb_typeof(v_prices->'external_rappen') IS DISTINCT FROM 'number'
                           OR (v_prices->'internal_rappen')::text !~ '^[0-9]+$'
                           OR (v_prices->'external_rappen')::text !~ '^[0-9]+$' THEN
                            RAISE EXCEPTION 'Cafeteria-Rappenbeträge müssen JSON-Ganzzahlen sein.' USING ERRCODE = '23514';
                        END IF;
                        IF (v_prices->>'internal_rappen')::integer <= 0
                           OR (v_prices->>'external_rappen')::integer < (v_prices->>'internal_rappen')::integer THEN
                            RAISE EXCEPTION 'Cafeteria-Kosten müssen positive Rappenbeträge mit extern >= intern sein.' USING ERRCODE = '23514';
                        END IF;
                    END LOOP;
                END IF;
            ELSIF jsonb_array_length(v_service->'options') <> 0 THEN
                RAISE EXCEPTION 'Eine geschlossene Mahlzeit darf keine Gerichte enthalten.' USING ERRCODE = '23514';
            END IF;
        END LOOP;
    END LOOP;

    IF v_profile = 'patient'
       AND (jsonb_has_patient_forbidden_key(NEW.snapshot_json)
            OR jsonb_has_patient_forbidden_value(NEW.snapshot_json)) THEN
        RAISE EXCEPTION 'Patienten-Snapshot enthält unzulässige Kosteninformationen.' USING ERRCODE = '23514';
    END IF;

    NEW.content_hash_sha256 := encode(public.digest(convert_to(NEW.snapshot_json::text, 'UTF8'), 'sha256'), 'hex');
    NEW.published_at := COALESCE(NEW.published_at, clock_timestamp());
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION protect_publication_revision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Publikationsrevisionen sind unveränderlich.' USING ERRCODE = '55000';
    END IF;
    IF NEW.snapshot_json IS DISTINCT FROM OLD.snapshot_json
       OR NEW.content_hash_sha256 IS DISTINCT FROM OLD.content_hash_sha256
       OR NEW.revision_code IS DISTINCT FROM OLD.revision_code
       OR NEW.revision_number IS DISTINCT FROM OLD.revision_number
       OR NEW.menu_week_id IS DISTINCT FROM OLD.menu_week_id
       OR NEW.profile_id IS DISTINCT FROM OLD.profile_id
       OR NEW.location_id IS DISTINCT FROM OLD.location_id
       OR NEW.week_start IS DISTINCT FROM OLD.week_start
       OR NEW.published_by IS DISTINCT FROM OLD.published_by
       OR NEW.published_at IS DISTINCT FROM OLD.published_at
       OR NEW.public_id IS DISTINCT FROM OLD.public_id THEN
        RAISE EXCEPTION 'Snapshotbytes und Publikationsidentität sind unveränderlich.' USING ERRCODE = '55000';
    END IF;
    IF OLD.withdrawn_at IS NOT NULL THEN
        RAISE EXCEPTION 'Eine zurückgezogene Publikation kann nicht erneut geändert werden.' USING ERRCODE = '55000';
    END IF;
    IF NEW.withdrawn_at IS NULL
       OR NEW.withdrawal_reason IS NULL
       OR btrim(NEW.withdrawal_reason) = ''
       OR NEW.withdrawn_by IS NULL THEN
        RAISE EXCEPTION 'Nur ein Rückzug ist als Änderung einer Publikationsrevision zulässig.' USING ERRCODE = '55000';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM publication_lifecycle_events e
        WHERE e.revision_id = OLD.id
          AND e.event_type = 'withdrawn'
          AND e.reason IS NOT DISTINCT FROM NEW.withdrawal_reason
          AND e.actor_user_id IS NOT DISTINCT FROM NEW.withdrawn_by
          AND e.occurred_at IS NOT DISTINCT FROM NEW.withdrawn_at
    ) THEN
        RAISE EXCEPTION 'Publikationen dürfen nur über den kontrollierten Rückzug zurückgezogen werden.'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION record_publication_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO publication_lifecycle_events(revision_id, event_type, actor_user_id, occurred_at)
        VALUES (NEW.id, 'activated', NEW.published_by, NEW.published_at);
    END IF;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION sync_entra_user(
    p_tenant_id uuid,
    p_object_id uuid,
    p_subject_id text,
    p_display_name text,
    p_email text,
    p_preferred_username text,
    p_roles text[]
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_roles text[];
    v_old_roles text[];
    v_role_count integer;
    v_user_id bigint;
    v_authz_version bigint;
BEGIN
    IF p_tenant_id IS NULL
       OR p_object_id IS NULL
       OR p_display_name IS NULL
       OR btrim(p_display_name) = ''
       OR p_roles IS NULL
       OR EXISTS (
           SELECT 1
           FROM unnest(p_roles) AS supplied(role_code)
           WHERE supplied.role_code IS NULL OR btrim(supplied.role_code) = ''
       ) THEN
        RAISE EXCEPTION 'Entra-Identität oder Rollenliste ist ungültig.' USING ERRCODE = '22023';
    END IF;
    SELECT COALESCE(
               array_agg(requested.role_code ORDER BY requested.role_code),
               ARRAY[]::text[]
           ),
           count(*)
      INTO v_roles, v_role_count
      FROM (
          SELECT DISTINCT btrim(supplied.role_code) AS role_code
          FROM unnest(p_roles) AS supplied(role_code)
      ) AS requested;
    IF v_role_count <> cardinality(p_roles)
       OR EXISTS (
           SELECT 1
           FROM unnest(v_roles) AS requested(role_code)
           LEFT JOIN application_roles ar
             ON ar.role_code = requested.role_code AND ar.active
           WHERE requested.role_code NOT IN (
                     'Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'
                 )
              OR ar.role_code IS NULL
       ) THEN
        RAISE EXCEPTION 'Entra-Rollenliste enthält unbekannte, inaktive oder doppelte Rollen.'
            USING ERRCODE = '42501';
    END IF;
    INSERT INTO users(
        auth_provider, entra_tenant_id, entra_object_id, entra_subject_id,
        display_name, email, preferred_username, last_seen_roles, last_login_at
    )
    VALUES (
        'entra', p_tenant_id, p_object_id, p_subject_id,
        btrim(p_display_name), p_email, p_preferred_username, to_jsonb(v_roles), clock_timestamp()
    )
    ON CONFLICT (entra_tenant_id, entra_object_id) WHERE auth_provider='entra' DO UPDATE
    SET entra_subject_id=EXCLUDED.entra_subject_id,
        display_name=EXCLUDED.display_name,
        email=EXCLUDED.email,
        preferred_username=EXCLUDED.preferred_username,
        last_seen_roles=EXCLUDED.last_seen_roles,
        last_login_at=clock_timestamp()
    RETURNING id INTO v_user_id;
    SELECT COALESCE(array_agg(role_code ORDER BY role_code), ARRAY[]::text[])
      INTO v_old_roles
      FROM user_role_cache
     WHERE user_id=v_user_id AND source='entra_token';
    DELETE FROM user_role_cache
     WHERE user_id=v_user_id
       AND source='entra_token'
       AND NOT (role_code = ANY(v_roles));
    INSERT INTO user_role_cache(user_id, role_code, source, first_seen_at, last_seen_at)
    SELECT v_user_id, requested.role_code, 'entra_token', clock_timestamp(), clock_timestamp()
      FROM unnest(v_roles) AS requested(role_code)
    ON CONFLICT (user_id, role_code) DO UPDATE
    SET last_seen_at=clock_timestamp()
    WHERE user_role_cache.source='entra_token';
    IF v_old_roles IS DISTINCT FROM v_roles THEN
        SELECT authz_version INTO v_authz_version FROM users WHERE id=v_user_id;
        INSERT INTO audit_events(actor_user_id, action, entity_type, details)
        VALUES (
            v_user_id,
            'auth.entra_roles_changed',
            'user',
            jsonb_build_object(
                'target_user_id', v_user_id,
                'old_roles', to_jsonb(v_old_roles),
                'new_roles', to_jsonb(v_roles),
                'authz_version', v_authz_version
            )
        );
    END IF;
    RETURN v_user_id;
END;
$$;

CREATE OR REPLACE FUNCTION resolve_auth_actor(p_actor_identifier text)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_actor_ids bigint[];
BEGIN
    IF p_actor_identifier IS NULL
       OR btrim(p_actor_identifier) !~ '^[A-Za-z0-9][A-Za-z0-9._@+-]{2,127}$' THEN
        RAISE EXCEPTION 'Actor-Identifier ist ungültig.' USING ERRCODE = '22023';
    END IF;
    SELECT array_agg(DISTINCT u.id ORDER BY u.id)
      INTO v_actor_ids
      FROM users u
      JOIN user_role_cache ur ON ur.user_id=u.id
      JOIN application_roles ar ON ar.role_code=ur.role_code AND ar.active
      LEFT JOIN local_credentials lc ON lc.user_id=u.id
     WHERE u.disabled_at IS NULL
       AND ar.role_code='Cafeteria.Admin'
       AND (
           lower(COALESCE(lc.username, ''))=lower(btrim(p_actor_identifier))
           OR lower(COALESCE(u.email, ''))=lower(btrim(p_actor_identifier))
           OR lower(COALESCE(u.preferred_username, ''))=lower(btrim(p_actor_identifier))
       );
    IF COALESCE(cardinality(v_actor_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Actor-Identifier bezeichnet keinen eindeutigen aktiven Administrator.'
            USING ERRCODE = '42501';
    END IF;
    RETURN v_actor_ids[1];
END;
$$;

CREATE OR REPLACE FUNCTION provision_local_user(
    p_actor_identifier text,
    p_username text,
    p_display_name text,
    p_password_hash text,
    p_roles text[]
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_actor_user_id bigint;
    v_roles text[];
    v_role_count integer;
    v_user_id bigint;
BEGIN
    v_actor_user_id := resolve_auth_actor(p_actor_identifier);
    IF p_username IS NULL
       OR p_username <> lower(p_username)
       OR p_username !~ '^[a-z0-9][a-z0-9._-]{2,63}$'
       OR p_display_name IS NULL
       OR btrim(p_display_name) = ''
       OR p_password_hash IS NULL
       OR p_password_hash !~ '^(scrypt:[0-9]+:[0-9]+:[0-9]+|pbkdf2:sha256:[0-9]+)\$[^$]+\$[0-9a-f]+$'
       OR p_roles IS NULL
       OR cardinality(p_roles) = 0
       OR EXISTS (
           SELECT 1 FROM unnest(p_roles) AS supplied(role_code)
           WHERE supplied.role_code IS NULL OR btrim(supplied.role_code) = ''
       ) THEN
        RAISE EXCEPTION 'Lokale Benutzerangaben sind ungültig.' USING ERRCODE = '22023';
    END IF;

    SELECT array_agg(requested.role_code ORDER BY requested.role_code), count(*)
      INTO v_roles, v_role_count
      FROM (
          SELECT DISTINCT btrim(supplied.role_code) AS role_code
          FROM unnest(p_roles) AS supplied(role_code)
      ) AS requested;
    IF v_role_count <> cardinality(p_roles)
       OR EXISTS (
           SELECT 1
           FROM unnest(v_roles) AS requested(role_code)
           LEFT JOIN application_roles ar
             ON ar.role_code = requested.role_code AND ar.active
           WHERE requested.role_code NOT IN (
                     'Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'
                 )
              OR ar.role_code IS NULL
       ) THEN
        RAISE EXCEPTION 'Lokale Rollenliste enthält unbekannte, inaktive oder doppelte Rollen.'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO users(auth_provider, display_name, last_seen_roles)
    VALUES ('local', btrim(p_display_name), to_jsonb(v_roles))
    RETURNING id INTO v_user_id;

    INSERT INTO local_credentials(user_id, username, password_hash)
    VALUES (v_user_id, p_username, p_password_hash);

    INSERT INTO user_role_cache(user_id, role_code, source)
    SELECT v_user_id, requested.role_code, 'local'
    FROM unnest(v_roles) AS requested(role_code);

    INSERT INTO audit_events(actor_user_id, action, entity_type, details)
    VALUES (
        v_actor_user_id,
        'auth.local_user_provisioned',
        'user',
        jsonb_build_object('target_user_id', v_user_id, 'role_count', cardinality(v_roles))
    );
    INSERT INTO audit_events(actor_user_id, action, entity_type, details)
    SELECT v_actor_user_id, 'auth.local_role_granted', 'user',
           jsonb_build_object('target_user_id', v_user_id, 'role_code', requested.role_code)
    FROM unnest(v_roles) AS requested(role_code);
    RETURN v_user_id;
END;
$$;


CREATE OR REPLACE FUNCTION bootstrap_first_local_admin(
    p_username text,
    p_display_name text,
    p_password_hash text
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_user_id bigint;
    v_system_actor_id bigint;
    v_admin_exists boolean;
BEGIN
    -- Validate inputs exactly like provision_local_user does
    IF p_username IS NULL
       OR p_username <> lower(p_username)
       OR p_username !~ '^[a-z0-9][a-z0-9._-]{2,63}$'
       OR p_display_name IS NULL
       OR btrim(p_display_name) = ''
       OR p_password_hash IS NULL
       OR p_password_hash !~ '^(scrypt:[0-9]+:[0-9]+:[0-9]+|pbkdf2:sha256:[0-9]+)\$[^$]+\$[0-9a-f]+$' THEN
        RAISE EXCEPTION 'Lokale Benutzerangaben sind ungültig.' USING ERRCODE = '22023';
    END IF;

    -- Lock and check that NO active user holds Cafeteria.Admin
    -- Race-safe via transaction-scoped advisory lock (auto-releases at txn end)
    PERFORM pg_advisory_xact_lock(2903847293::bigint);  -- Fixed key for bootstrap lock

    -- Check if any active admin exists
    SELECT EXISTS (
        SELECT 1
        FROM cafeteria.users u
        JOIN cafeteria.user_role_cache urc ON urc.user_id = u.id
        JOIN cafeteria.application_roles ar ON ar.role_code = urc.role_code
        WHERE u.disabled_at IS NULL
          AND urc.role_code = 'Cafeteria.Admin'
          AND ar.active
    ) INTO v_admin_exists;

    IF v_admin_exists THEN
        RAISE EXCEPTION 'Es existiert bereits ein aktiver Administrator; Bootstrap ist gesperrt.' USING ERRCODE = '42501';
    END IF;

    -- Get the system user ID for audit
    SELECT id INTO v_system_actor_id
    FROM cafeteria.users
    WHERE auth_provider = 'system'
      AND public_id = '00000000-0000-0000-0000-000000000001';
    IF v_system_actor_id IS NULL THEN
        RAISE EXCEPTION 'System-Benutzer fehlt in der Datenbank.' USING ERRCODE = '22023';
    END IF;

    -- Create the user exactly like provision_local_user does
    INSERT INTO users(auth_provider, display_name, last_seen_roles)
    VALUES ('local', btrim(p_display_name), '["Cafeteria.Admin"]'::jsonb)
    RETURNING id INTO v_user_id;

    -- Create local credentials
    INSERT INTO local_credentials(user_id, username, password_hash)
    VALUES (v_user_id, p_username, p_password_hash);

    -- Grant Cafeteria.Admin role
    INSERT INTO user_role_cache(user_id, role_code, source)
    VALUES (v_user_id, 'Cafeteria.Admin', 'local');

    -- Audit: system user created the bootstrap admin
    INSERT INTO audit_events(actor_user_id, action, entity_type, details)
    VALUES (
        v_system_actor_id,
        'auth.local_admin_bootstrapped',
        'user',
        jsonb_build_object(
            'target_user_id', v_user_id,
            'username', p_username
        )
    );

    -- Audit: role granted
    INSERT INTO audit_events(actor_user_id, action, entity_type, details)
    VALUES (
        v_system_actor_id,
        'auth.local_role_granted',
        'user',
        jsonb_build_object(
            'target_user_id', v_user_id,
            'role_code', 'Cafeteria.Admin'
        )
    );

    RETURN v_user_id;
END;
$$;

ALTER FUNCTION bootstrap_first_local_admin(text, text, text)
    SET search_path = cafeteria, pg_temp;

REVOKE EXECUTE ON FUNCTION bootstrap_first_local_admin(text, text, text)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

CREATE OR REPLACE FUNCTION set_local_password(
    p_actor_identifier text,
    p_username text,
    p_password_hash text
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_actor_user_id bigint;
    v_user_id bigint;
BEGIN
    v_actor_user_id := resolve_auth_actor(p_actor_identifier);
    IF p_username IS NULL
       OR p_username <> lower(p_username)
       OR p_username !~ '^[a-z0-9][a-z0-9._-]{2,63}$'
       OR p_password_hash IS NULL
       OR p_password_hash !~ '^(scrypt:[0-9]+:[0-9]+:[0-9]+|pbkdf2:sha256:[0-9]+)\$[^$]+\$[0-9a-f]+$' THEN
        RAISE EXCEPTION 'Lokale Passwortangaben sind ungültig.' USING ERRCODE = '22023';
    END IF;

    SELECT c.user_id
      INTO v_user_id
      FROM local_credentials c
      JOIN users u ON u.id=c.user_id AND u.auth_provider='local'
     WHERE c.username=p_username
     FOR UPDATE OF c, u;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Lokaler Benutzer ist unbekannt.' USING ERRCODE = '22023';
    END IF;

    UPDATE local_credentials
       SET password_hash=p_password_hash,
           failed_login_count=0,
           locked_until=NULL,
           last_failed_at=NULL,
           password_changed_at=clock_timestamp()
     WHERE user_id=v_user_id;
    UPDATE users SET authz_version=authz_version + 1 WHERE id=v_user_id;
    INSERT INTO audit_events(actor_user_id, action, entity_type, details)
    VALUES (
        v_actor_user_id,
        'auth.local_password_changed',
        'user',
        jsonb_build_object('target_user_id', v_user_id)
    );
    RETURN v_user_id;
END;
$$;

CREATE OR REPLACE FUNCTION disable_local_user(p_actor_identifier text, p_username text)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_actor_user_id bigint;
    v_user_id bigint;
    v_disabled_at timestamptz;
BEGIN
    v_actor_user_id := resolve_auth_actor(p_actor_identifier);
    IF p_username IS NULL
       OR p_username <> lower(p_username)
       OR p_username !~ '^[a-z0-9][a-z0-9._-]{2,63}$' THEN
        RAISE EXCEPTION 'Lokaler Benutzername ist ungültig.' USING ERRCODE = '22023';
    END IF;

    SELECT u.id, u.disabled_at
      INTO v_user_id, v_disabled_at
      FROM users u
      JOIN local_credentials c ON c.user_id=u.id
     WHERE c.username=p_username AND u.auth_provider='local'
     FOR UPDATE OF u, c;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Lokaler Benutzer ist unbekannt.' USING ERRCODE = '22023';
    END IF;

    IF v_disabled_at IS NULL THEN
        UPDATE users SET disabled_at=clock_timestamp() WHERE id=v_user_id;
        INSERT INTO audit_events(actor_user_id, action, entity_type, details)
        VALUES (
            v_actor_user_id,
            'auth.local_user_disabled',
            'user',
            jsonb_build_object('target_user_id', v_user_id)
        );
    END IF;
    RETURN v_user_id;
END;
$$;

CREATE OR REPLACE FUNCTION bootstrap_auth_capability_secret()
RETURNS smallint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_id smallint;
BEGIN
    IF EXISTS (SELECT 1 FROM auth_capability_secrets) THEN
        RAISE EXCEPTION 'Capability-Secret ist bereits bootstrapped.' USING ERRCODE = '55000';
    END IF;
    INSERT INTO auth_capability_secrets(secret)
    VALUES (public.gen_random_bytes(32))
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION rotate_auth_capability_secret()
RETURNS smallint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_new_id smallint;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM auth_capability_secrets WHERE active) THEN
        RAISE EXCEPTION 'Kein aktives Capability-Secret zum Rotieren.' USING ERRCODE = 'P0002';
    END IF;
    UPDATE auth_capability_secrets
       SET active = false,
           retired_at = clock_timestamp()
     WHERE active;
    INSERT INTO auth_capability_secrets(secret)
    VALUES (public.gen_random_bytes(32))
    RETURNING id INTO v_new_id;
    RETURN v_new_id;
END;
$$;

CREATE OR REPLACE FUNCTION ensure_auth_capability_state()
RETURNS smallint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_schema_owner text;
BEGIN
    SELECT pg_get_userbyid(nspowner)
      INTO v_schema_owner
      FROM pg_namespace
     WHERE nspname='cafeteria';
    IF session_user IS DISTINCT FROM v_schema_owner THEN
        RAISE EXCEPTION 'Capability-Zustand darf nur der Schema-Owner reparieren.'
            USING ERRCODE = '42501';
    END IF;
    CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
    IF to_regprocedure('public.gen_random_bytes(integer)') IS NULL
       OR to_regprocedure('public.hmac(bytea,bytea,text)') IS NULL THEN
        RAISE EXCEPTION 'pgcrypto ist nicht kanonisch im public-Schema verfügbar.'
            USING ERRCODE = '55000';
    END IF;
    CREATE TABLE IF NOT EXISTS auth_capability_secrets (
        id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        secret bytea NOT NULL CHECK (octet_length(secret) = 32),
        active boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        retired_at timestamptz,
        CHECK (active OR retired_at IS NOT NULL),
        CHECK (NOT active OR retired_at IS NULL)
    );
    CREATE TABLE IF NOT EXISTS auth_capability_nonces (
        nonce bytea PRIMARY KEY CHECK (octet_length(nonce) = 16),
        actor_user_id bigint NOT NULL REFERENCES users(id),
        revision_id bigint NOT NULL REFERENCES publication_revisions(id),
        consumed_at timestamptz NOT NULL DEFAULT clock_timestamp()
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_auth_capability_one_active
        ON auth_capability_secrets ((true)) WHERE active;
    IF pg_get_serial_sequence('cafeteria.auth_capability_secrets', 'id')
       IS DISTINCT FROM 'cafeteria.auth_capability_secrets_id_seq' THEN
        RAISE EXCEPTION 'Capability-Secret-Identity-Sequenz ist nicht kanonisch.'
            USING ERRCODE = '55000';
    END IF;
    IF (
        SELECT count(*)
        FROM pg_constraint
        WHERE connamespace='cafeteria'::regnamespace
          AND conrelid IN (
              'cafeteria.auth_capability_secrets'::regclass,
              'cafeteria.auth_capability_nonces'::regclass
          )
    ) <> 8 THEN
        RAISE EXCEPTION 'Capability-Zustand besitzt nicht die kanonischen Constraints.'
            USING ERRCODE = '55000';
    END IF;
    REVOKE ALL ON auth_capability_secrets, auth_capability_nonces FROM PUBLIC;
    REVOKE ALL ON SEQUENCE auth_capability_secrets_id_seq FROM PUBLIC;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cafeteria_app') THEN
        REVOKE ALL ON auth_capability_secrets, auth_capability_nonces FROM cafeteria_app;
        REVOKE ALL ON SEQUENCE auth_capability_secrets_id_seq FROM cafeteria_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cafeteria_backup') THEN
        REVOKE ALL ON auth_capability_secrets, auth_capability_nonces FROM cafeteria_backup;
        REVOKE ALL ON SEQUENCE auth_capability_secrets_id_seq FROM cafeteria_backup;
    END IF;
    RETURN 1;
END;
$$;

CREATE OR REPLACE FUNCTION hard_reset_auth_capability_state()
RETURNS smallint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_discarded_nonce_count bigint;
    v_discarded_secret_count bigint;
    v_new_id smallint;
BEGIN
    PERFORM ensure_auth_capability_state();
    LOCK TABLE auth_capability_secrets IN ACCESS EXCLUSIVE MODE;
    LOCK TABLE auth_capability_nonces IN ACCESS EXCLUSIVE MODE;
    SELECT count(*) INTO v_discarded_secret_count FROM auth_capability_secrets;
    SELECT count(*) INTO v_discarded_nonce_count FROM auth_capability_nonces;
    TRUNCATE TABLE auth_capability_nonces, auth_capability_secrets RESTART IDENTITY;
    INSERT INTO auth_capability_secrets(secret)
    VALUES (public.gen_random_bytes(32))
    RETURNING id INTO v_new_id;
    IF v_new_id IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'Capability-Hard-Reset konnte Secret-ID 1 nicht herstellen.'
            USING ERRCODE = '55000';
    END IF;
    INSERT INTO audit_events(action, entity_type, details)
    VALUES (
        'auth_capability.hard_reset',
        'auth_capability_state',
        jsonb_build_object(
            'discarded_nonce_count', v_discarded_nonce_count,
            'discarded_secret_count', v_discarded_secret_count,
            'new_secret_id', v_new_id
        )
    );
    RETURN v_new_id;
END;
$$;

CREATE OR REPLACE FUNCTION issue_publication_capability(
    p_actor_user_id bigint,
    p_revision_id bigint,
    p_ttl interval DEFAULT interval '5 minutes'
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_authz_version bigint;
    v_disabled_at timestamptz;
    v_withdrawn_at timestamptz;
    v_revision_found boolean;
    v_secret_id smallint;
    v_secret bytea;
    v_nonce bytea;
    v_nonce_hex text;
    v_expires_at timestamptz;
    v_expiry_epoch bigint;
    v_canonical text;
    v_mac text;
BEGIN
    IF p_ttl IS NULL OR p_ttl <= interval '0' OR p_ttl > interval '15 minutes' THEN
        RAISE EXCEPTION 'Capability-Gültigkeit muss positiv und höchstens 15 Minuten sein.'
            USING ERRCODE = '22023';
    END IF;
    SELECT withdrawn_at
      INTO v_withdrawn_at
      FROM publication_revisions
     WHERE id = p_revision_id
     FOR UPDATE;
    v_revision_found := FOUND;
    SELECT authz_version, disabled_at
      INTO v_authz_version, v_disabled_at
      FROM users
     WHERE id = p_actor_user_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Rückzugsakteur ist nicht aktiv oder nicht zur Publikation berechtigt.'
            USING ERRCODE = '42501';
    END IF;
    PERFORM 1
      FROM user_role_cache
     WHERE user_id = p_actor_user_id
     ORDER BY role_code
     FOR UPDATE;
    IF v_disabled_at IS NOT NULL
       OR NOT EXISTS (
           SELECT 1
           FROM user_role_cache ur
           JOIN application_roles ar ON ar.role_code = ur.role_code AND ar.active
           WHERE ur.user_id = p_actor_user_id
             AND ur.role_code IN ('Cafeteria.Publisher', 'Cafeteria.Admin')
       ) THEN
        RAISE EXCEPTION 'Rückzugsakteur ist nicht aktiv oder nicht zur Publikation berechtigt.'
            USING ERRCODE = '42501';
    END IF;
    IF NOT v_revision_found THEN
        RAISE EXCEPTION 'Unbekannte Publikationsrevision.' USING ERRCODE = 'P0002';
    END IF;
    IF v_withdrawn_at IS NOT NULL THEN
        RAISE EXCEPTION 'Publikationsrevision wurde bereits zurückgezogen.' USING ERRCODE = '55000';
    END IF;
    SELECT id, secret
      INTO v_secret_id, v_secret
      FROM auth_capability_secrets
     WHERE active
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Kein aktives Capability-Secret. Owner muss bootstrap_auth_capability_secret() ausführen.'
            USING ERRCODE = '55000';
    END IF;

    v_nonce := public.gen_random_bytes(16);
    v_nonce_hex := encode(v_nonce, 'hex');
    v_expires_at := clock_timestamp() + p_ttl;
    v_expiry_epoch := floor(EXTRACT(EPOCH FROM v_expires_at))::bigint;
    v_canonical := format(
        'v1|%s|%s|%s|%s|%s|%s',
        v_secret_id, p_actor_user_id, p_revision_id, v_authz_version, v_expiry_epoch, v_nonce_hex
    );
    v_mac := encode(public.hmac(convert_to(v_canonical, 'UTF8'), v_secret, 'sha256'), 'hex');
    RETURN format(
        'v1.%s.%s.%s.%s.%s.%s.%s',
        v_secret_id, p_actor_user_id, p_revision_id, v_authz_version, v_expiry_epoch, v_nonce_hex, v_mac
    );
END;
$$;

CREATE OR REPLACE FUNCTION withdraw_publication_revision(
    p_revision_id bigint,
    p_capability text,
    p_reason text
)
RETURNS timestamptz
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_parts text[];
    v_secret_id smallint;
    v_actor_id bigint;
    v_token_revision bigint;
    v_token_authz bigint;
    v_expiry_epoch bigint;
    v_nonce_hex text;
    v_mac_hex text;
    v_secret bytea;
    v_active boolean;
    v_retired_at timestamptz;
    v_canonical text;
    v_expected text;
    v_authz_version bigint;
    v_disabled_at timestamptz;
    v_existing_withdrawal timestamptz;
    v_withdrawn_at timestamptz;
BEGIN
    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'Ein Rückzugsgrund ist erforderlich.' USING ERRCODE = '22023';
    END IF;
    IF p_capability IS NULL OR btrim(p_capability) = '' THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;

    v_parts := string_to_array(p_capability, '.');
    IF array_length(v_parts, 1) IS DISTINCT FROM 8 OR v_parts[1] IS DISTINCT FROM 'v1' THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;
    BEGIN
        v_secret_id := v_parts[2]::smallint;
        v_actor_id := v_parts[3]::bigint;
        v_token_revision := v_parts[4]::bigint;
        v_token_authz := v_parts[5]::bigint;
        v_expiry_epoch := v_parts[6]::bigint;
        v_nonce_hex := lower(v_parts[7]);
        v_mac_hex := lower(v_parts[8]);
    EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END;
    IF v_nonce_hex !~ '^[0-9a-f]{32}$' OR v_mac_hex !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;

    SELECT secret, active, retired_at
      INTO v_secret, v_active, v_retired_at
      FROM auth_capability_secrets
     WHERE id = v_secret_id;
    IF NOT FOUND
       OR (
           NOT v_active
           AND (v_retired_at IS NULL OR v_retired_at < clock_timestamp() - interval '5 minutes')
       ) THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;

    v_canonical := format(
        'v1|%s|%s|%s|%s|%s|%s',
        v_secret_id, v_actor_id, v_token_revision, v_token_authz, v_expiry_epoch, v_nonce_hex
    );
    v_expected := encode(public.hmac(convert_to(v_canonical, 'UTF8'), v_secret, 'sha256'), 'hex');
    IF v_expected IS DISTINCT FROM v_mac_hex THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;
    IF v_token_revision IS DISTINCT FROM p_revision_id THEN
        RAISE EXCEPTION 'Capability passt nicht zur Publikationsrevision.' USING ERRCODE = '42501';
    END IF;
    IF v_expiry_epoch <= floor(EXTRACT(EPOCH FROM clock_timestamp()))::bigint THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;

    SELECT withdrawn_at
      INTO v_existing_withdrawal
      FROM publication_revisions
     WHERE id = p_revision_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Publikationsrevision.' USING ERRCODE = 'P0002';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM auth_capability_nonces
        WHERE nonce = decode(v_nonce_hex, 'hex')
    ) THEN
        RAISE EXCEPTION 'Capability-Nonce wurde bereits verwendet.' USING ERRCODE = '42501';
    END IF;
    IF v_existing_withdrawal IS NOT NULL THEN
        RAISE EXCEPTION 'Publikationsrevision wurde bereits zurückgezogen.' USING ERRCODE = '55000';
    END IF;

    SELECT authz_version, disabled_at
      INTO v_authz_version, v_disabled_at
      FROM users
     WHERE id = v_actor_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;
    PERFORM 1
      FROM user_role_cache
     WHERE user_id = v_actor_id
     ORDER BY role_code
     FOR UPDATE;
    IF v_authz_version IS DISTINCT FROM v_token_authz THEN
        RAISE EXCEPTION 'Capability ist durch eine Rollenänderung ungültig geworden.'
            USING ERRCODE = '42501';
    END IF;
    IF v_disabled_at IS NOT NULL
       OR NOT EXISTS (
           SELECT 1
           FROM user_role_cache ur
           JOIN application_roles ar ON ar.role_code = ur.role_code AND ar.active
           WHERE ur.user_id = v_actor_id
             AND ur.role_code IN ('Cafeteria.Publisher', 'Cafeteria.Admin')
       ) THEN
        RAISE EXCEPTION 'Rückzugsakteur ist nicht aktiv oder nicht zur Publikation berechtigt.'
            USING ERRCODE = '42501';
    END IF;

    BEGIN
        INSERT INTO auth_capability_nonces(nonce, actor_user_id, revision_id)
        VALUES (decode(v_nonce_hex, 'hex'), v_actor_id, v_token_revision);
    EXCEPTION WHEN unique_violation THEN
        RAISE EXCEPTION 'Capability-Nonce wurde bereits verwendet.' USING ERRCODE = '42501';
    END;

    v_withdrawn_at := clock_timestamp();
    INSERT INTO publication_lifecycle_events(
        revision_id, event_type, reason, actor_user_id, occurred_at
    ) VALUES (
        p_revision_id, 'withdrawn', btrim(p_reason), v_actor_id, v_withdrawn_at
    );
    UPDATE publication_revisions
       SET withdrawn_at = v_withdrawn_at,
           withdrawal_reason = btrim(p_reason),
           withdrawn_by = v_actor_id
     WHERE id = p_revision_id;
    RETURN v_withdrawn_at;
END;
$$;

CREATE OR REPLACE FUNCTION protect_publication_lifecycle_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Publikations-Lebenszyklusereignisse sind unveränderlich.' USING ERRCODE = '55000';
END;
$$;

CREATE OR REPLACE FUNCTION cafeteria.lock_component_metadata_masters(
    p_label_codes text[],
    p_allergen_codes text[]
)
RETURNS TABLE (
    master_kind text,
    master_id smallint,
    code text,
    active boolean
)
LANGUAGE plpgsql
SECURITY DEFINER
VOLATILE
PARALLEL UNSAFE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
BEGIN
    IF p_label_codes IS NULL
       OR p_allergen_codes IS NULL
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.unnest(p_label_codes) AS requested(code)
           WHERE requested.code IS NULL
       )
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.unnest(p_allergen_codes) AS requested(code)
           WHERE requested.code IS NULL
       ) THEN
        RAISE EXCEPTION 'metadata code arrays must be non-null and contain no nulls'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT 'label'::text, label.id, label.code, label.active
    FROM cafeteria.dietary_labels AS label
    WHERE label.code = ANY (p_label_codes)
    ORDER BY label.id
    FOR SHARE OF label;

    RETURN QUERY
    SELECT 'allergen'::text, allergen.id, allergen.code, allergen.active
    FROM cafeteria.allergens AS allergen
    WHERE allergen.code = ANY (p_allergen_codes)
    ORDER BY allergen.id
    FOR SHARE OF allergen;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.lock_expected_active_location(
    p_expected_location_id bigint
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
VOLATILE
PARALLEL UNSAFE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_active_count bigint;
    v_active_id bigint;
BEGIN
    IF p_expected_location_id IS NULL OR p_expected_location_id <= 0 THEN
        RAISE EXCEPTION 'expected location id must be a positive bigint'
            USING ERRCODE = '22023';
    END IF;

    LOCK TABLE cafeteria.locations IN SHARE MODE;
    SELECT count(*), min(location.id)
      INTO v_active_count, v_active_id
      FROM cafeteria.locations AS location
     WHERE location.active;
    RETURN v_active_count = 1 AND v_active_id = p_expected_location_id;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.lock_active_publication(
    p_menu_week_id bigint
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
VOLATILE
PARALLEL UNSAFE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_revision_id bigint;
BEGIN
    IF p_menu_week_id IS NULL OR p_menu_week_id <= 0 THEN
        RAISE EXCEPTION 'menu week id must be a positive bigint'
            USING ERRCODE = '22023';
    END IF;

    SELECT revision.id
      INTO v_revision_id
      FROM cafeteria.publication_revisions AS revision
     WHERE revision.menu_week_id = p_menu_week_id
       AND revision.withdrawn_at IS NULL
     ORDER BY revision.id
     LIMIT 1
     FOR UPDATE;
    RETURN v_revision_id;
END;
$function$;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_users_auth_provider ON users;
CREATE TRIGGER trg_users_auth_provider BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION validate_user_auth_provider();

DROP TRIGGER IF EXISTS trg_local_credentials_validate ON local_credentials;
CREATE TRIGGER trg_local_credentials_validate BEFORE INSERT OR UPDATE ON local_credentials
FOR EACH ROW EXECUTE FUNCTION validate_local_credential();

DROP TRIGGER IF EXISTS trg_local_credentials_updated_at ON local_credentials;
CREATE TRIGGER trg_local_credentials_updated_at BEFORE UPDATE ON local_credentials
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_local_credentials_login_lock_audit ON local_credentials;
CREATE TRIGGER trg_local_credentials_login_lock_audit
AFTER UPDATE OF failed_login_count, locked_until ON local_credentials
FOR EACH ROW EXECUTE FUNCTION record_local_login_lock();

DROP TRIGGER IF EXISTS trg_user_role_source ON user_role_cache;
CREATE TRIGGER trg_user_role_source BEFORE INSERT OR UPDATE ON user_role_cache
FOR EACH ROW EXECUTE FUNCTION validate_user_role_source();

DROP TRIGGER IF EXISTS trg_user_role_authz_version ON user_role_cache;
CREATE TRIGGER trg_user_role_authz_version AFTER INSERT OR UPDATE OR DELETE ON user_role_cache
FOR EACH ROW EXECUTE FUNCTION bump_user_authz_version();

DROP TRIGGER IF EXISTS trg_locations_updated_at ON locations;
CREATE TRIGGER trg_locations_updated_at BEFORE UPDATE ON locations
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_menu_weeks_identity ON menu_weeks;
CREATE TRIGGER trg_menu_weeks_identity BEFORE UPDATE ON menu_weeks
FOR EACH ROW EXECUTE FUNCTION validate_menu_week();

DROP TRIGGER IF EXISTS trg_menu_weeks_location_identity ON menu_weeks;
CREATE TRIGGER trg_menu_weeks_location_identity
BEFORE UPDATE OF location_id ON menu_weeks
FOR EACH ROW
EXECUTE FUNCTION protect_menu_week_location_identity();

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

DROP TRIGGER IF EXISTS trg_menu_components_identity ON menu_components;
CREATE TRIGGER trg_menu_components_identity
BEFORE UPDATE OF location_id, profile_scope ON menu_components
FOR EACH ROW
EXECUTE FUNCTION protect_menu_component_identity();

DROP TRIGGER IF EXISTS trg_menu_item_components_scope ON menu_item_components;
CREATE TRIGGER trg_menu_item_components_scope
BEFORE INSERT OR UPDATE OF menu_item_id, component_id ON menu_item_components
FOR EACH ROW
EXECUTE FUNCTION validate_menu_item_component_scope();

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
CREATE TRIGGER trg_publication_validate BEFORE INSERT ON publication_revisions
FOR EACH ROW EXECUTE FUNCTION validate_publication_revision();

DROP TRIGGER IF EXISTS trg_publication_immutable ON publication_revisions;
CREATE TRIGGER trg_publication_immutable BEFORE UPDATE OR DELETE ON publication_revisions
FOR EACH ROW EXECUTE FUNCTION protect_publication_revision();

DROP TRIGGER IF EXISTS trg_publication_lifecycle ON publication_revisions;
CREATE TRIGGER trg_publication_lifecycle AFTER INSERT OR UPDATE ON publication_revisions
FOR EACH ROW EXECUTE FUNCTION record_publication_lifecycle();

DROP TRIGGER IF EXISTS trg_publication_lifecycle_immutable ON publication_lifecycle_events;
CREATE TRIGGER trg_publication_lifecycle_immutable BEFORE UPDATE OR DELETE ON publication_lifecycle_events
FOR EACH ROW EXECUTE FUNCTION protect_publication_lifecycle_event();

DROP TRIGGER IF EXISTS trg_audit_no_update ON audit_events;
CREATE TRIGGER trg_audit_no_update BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION protect_audit_event();

ALTER FUNCTION set_updated_at() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION bump_row_version_and_updated_at() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_week() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_service() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_item() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_item_price() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION normalize_patient_key(text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION patient_key_is_forbidden(text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION jsonb_has_patient_forbidden_key(jsonb) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION jsonb_has_patient_forbidden_value(jsonb) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_publication_revision() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION protect_publication_revision() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION record_publication_lifecycle() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION sync_entra_user(uuid, uuid, text, text, text, text, text[])
    SET search_path = cafeteria, pg_temp;
ALTER FUNCTION resolve_auth_actor(text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION provision_local_user(text, text, text, text, text[])
    SET search_path = cafeteria, pg_temp;
ALTER FUNCTION set_local_password(text, text, text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION disable_local_user(text, text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION bootstrap_auth_capability_secret() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION rotate_auth_capability_secret() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION ensure_auth_capability_state() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION hard_reset_auth_capability_state() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION issue_publication_capability(bigint, bigint, interval) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION withdraw_publication_revision(bigint, text, text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION protect_publication_lifecycle_event() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION protect_audit_event() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION record_local_login_lock() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_local_credential() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_user_auth_provider() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_user_role_source() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION bump_user_authz_version() SET search_path = cafeteria, pg_temp;

DO $auth_issuer_privileges$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cafeteria_auth_issuer') THEN
        RAISE EXCEPTION 'Required role cafeteria_auth_issuer is missing.' USING ERRCODE = '42501';
    END IF;
END;
$auth_issuer_privileges$;

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cafeteria
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria REVOKE EXECUTE ON FUNCTIONS
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE ALL ON SCHEMA cafeteria
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public
FROM cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT USAGE ON SCHEMA cafeteria
TO cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE ALL ON ALL TABLES IN SCHEMA cafeteria FROM cafeteria_auth_issuer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA cafeteria FROM cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    sync_entra_user(uuid, uuid, text, text, text, text, text[]),
    issue_publication_capability(bigint, bigint, interval),
    provision_local_user(text, text, text, text, text[]),
    set_local_password(text, text, text),
    disable_local_user(text, text)
TO cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    lock_component_metadata_masters(text[], text[]),
    lock_expected_active_location(bigint),
    lock_active_publication(bigint)
TO cafeteria_app;

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
    r.week_start,
    (r.week_start + 6) AS week_end,
    p.code AS profile_code,
    l.code AS location_code,
    l.name AS location_name
FROM publication_revisions r
JOIN menu_weeks w ON w.id = r.menu_week_id
JOIN offer_profiles p ON p.id = r.profile_id
JOIN locations l ON l.id = r.location_id
WHERE r.withdrawn_at IS NULL
  AND w.workflow_state = 'published';

-- Existing checked flags are preserved; no historical approval is inferred.
ALTER TABLE cafeteria.menu_weeks ADD COLUMN IF NOT EXISTS
    header_revision bigint NOT NULL DEFAULT 1 CHECK (header_revision > 0);

CREATE OR REPLACE FUNCTION cafeteria.bump_week_header_revision()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
BEGIN
    NEW.header_revision := OLD.header_revision +
        CASE WHEN (NEW.title, NEW.shared_note) IS DISTINCT FROM
                       (OLD.title, OLD.shared_note) THEN 1 ELSE 0 END;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_week_header_revision ON cafeteria.menu_weeks;
CREATE TRIGGER trg_week_header_revision BEFORE UPDATE ON cafeteria.menu_weeks
FOR EACH ROW EXECUTE FUNCTION cafeteria.bump_week_header_revision();

CREATE OR REPLACE FUNCTION cafeteria.workflow_week_context(p_week_id bigint)
RETURNS jsonb LANGUAGE sql STABLE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
    SELECT jsonb_build_object(
        'week_public_id', w.public_id::text, 'location_id', w.location_id,
        'profile_code', p.code, 'week_start', w.week_start::text,
        'header_revision', w.header_revision,
        'title', COALESCE(w.title, ''), 'shared_note', COALESCE(w.shared_note, ''),
        'services', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'public_id', s.public_id::text, 'date', s.service_date::text,
                'meal', mp.code, 'row_version', s.row_version,
                'state', s.service_state, 'notice', COALESCE(s.notice, ''),
                'start', to_char(s.service_start, 'HH24:MI'),
                'end', to_char(s.service_end, 'HH24:MI')
            )) ORDER BY s.service_date, mp.sort_order, s.id)
            FROM cafeteria.menu_services s
            JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
            WHERE s.menu_week_id=w.id
        ), '[]'::jsonb)
    )
    FROM cafeteria.menu_weeks w
    JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
    WHERE w.id=p_week_id;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.require_workflow_review_actor(p_actor_id bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_disabled_at timestamptz;
BEGIN
    SELECT disabled_at INTO v_disabled_at FROM cafeteria.users
    WHERE id=p_actor_id FOR SHARE;
    IF NOT FOUND OR v_disabled_at IS NOT NULL THEN
        RAISE EXCEPTION 'Prüfer ist nicht berechtigt.' USING ERRCODE='42501';
    END IF;
    PERFORM role_code FROM cafeteria.user_role_cache
    WHERE user_id=p_actor_id ORDER BY role_code FOR SHARE;
    IF NOT EXISTS (
        SELECT 1 FROM cafeteria.user_role_cache ur
        JOIN cafeteria.application_roles ar ON ar.role_code=ur.role_code AND ar.active
        WHERE ur.user_id=p_actor_id
          AND ur.role_code IN ('Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin')
    ) THEN
        RAISE EXCEPTION 'Prüfer ist nicht berechtigt.' USING ERRCODE='42501';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.record_menu_review(
    p_actor_id bigint, p_location_id bigint, p_profile text, p_item_id bigint,
    p_source_version bigint, p_submitted_token text, p_reviewed_token text
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_week_id bigint;
    v_service_id bigint;
    v_item cafeteria.menu_items%ROWTYPE;
    v_receipt uuid;
BEGIN
    IF p_source_version IS NULL OR p_source_version < 1
       OR p_submitted_token IS NULL OR p_submitted_token !~ '^sha256:[0-9a-f]{64}$'
       OR p_reviewed_token IS NULL OR p_reviewed_token !~ '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Prüfbeleg ist ungültig.' USING ERRCODE='22023';
    END IF;
    IF NOT cafeteria.lock_expected_active_location(p_location_id) THEN
        RAISE EXCEPTION 'Standort wurde geändert.' USING ERRCODE='55000';
    END IF;
    SELECT w.id, s.id INTO v_week_id, v_service_id
    FROM cafeteria.menu_weeks w
    JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
    JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
    JOIN cafeteria.menu_items i ON i.service_id=s.id
    WHERE i.id=p_item_id AND w.location_id=p_location_id AND p.code=p_profile
    FOR UPDATE OF w;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Menü nicht gefunden.' USING ERRCODE='22023';
    END IF;
    PERFORM id FROM cafeteria.menu_services WHERE id=v_service_id FOR UPDATE;
    SELECT * INTO v_item FROM cafeteria.menu_items WHERE id=p_item_id FOR UPDATE;
    IF v_item.row_version <> p_source_version + 1
       OR v_item.allergen_review_status <> 'checked'
       OR EXISTS (
            SELECT 1 FROM cafeteria.menu_item_components mic
            JOIN cafeteria.menu_components c ON c.id=mic.component_id
            WHERE mic.menu_item_id=p_item_id
              AND mic.component_row_version IS DISTINCT FROM c.row_version
       ) THEN
        RAISE EXCEPTION 'Die Menüprüfung ist veraltet.' USING ERRCODE='55000';
    END IF;
    PERFORM cafeteria.require_workflow_review_actor(p_actor_id);
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, profile_code, details
    ) VALUES (
        p_actor_id, 'workflow.menu_reviewed', 'menu_item', v_item.public_id, p_profile,
        jsonb_build_object(
            'source_item_row_version', p_source_version,
            'reviewed_item_row_version', v_item.row_version,
            'submitted_token', p_submitted_token, 'reviewed_token', p_reviewed_token,
            'week_public_id', (SELECT public_id::text FROM cafeteria.menu_weeks WHERE id=v_week_id)
        )
    ) RETURNING public_id INTO v_receipt;
    RETURN v_receipt;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.record_week_context_review(
    p_actor_id bigint, p_location_id bigint, p_profile text, p_week_id bigint,
    p_token text, p_context jsonb
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_week_uuid uuid;
    v_context jsonb;
    v_receipt uuid;
BEGIN
    IF p_token IS NULL OR p_token !~ '^sha256:[0-9a-f]{64}$'
       OR p_context IS NULL OR jsonb_typeof(p_context) <> 'object' THEN
        RAISE EXCEPTION 'Prüfbeleg ist ungültig.' USING ERRCODE='22023';
    END IF;
    IF NOT cafeteria.lock_expected_active_location(p_location_id) THEN
        RAISE EXCEPTION 'Standort wurde geändert.' USING ERRCODE='55000';
    END IF;
    SELECT w.public_id INTO v_week_uuid
    FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
    WHERE w.id=p_week_id AND w.location_id=p_location_id AND p.code=p_profile
    FOR UPDATE OF w;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Woche nicht gefunden.' USING ERRCODE='22023';
    END IF;
    PERFORM s.id FROM cafeteria.menu_services s
    JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
    WHERE s.menu_week_id=p_week_id
    ORDER BY s.service_date, mp.sort_order, s.id FOR UPDATE OF s;
    v_context := cafeteria.workflow_week_context(p_week_id);
    IF v_context IS DISTINCT FROM p_context THEN
        RAISE EXCEPTION 'Die Wochenprüfung ist veraltet.' USING ERRCODE='55000';
    END IF;
    PERFORM cafeteria.require_workflow_review_actor(p_actor_id);
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, profile_code, details
    ) VALUES (
        p_actor_id, 'workflow.week_context_reviewed', 'menu_week', v_week_uuid, p_profile,
        jsonb_build_object('submitted_token', p_token, 'reviewed_token', p_token,
                           'context', v_context)
    ) RETURNING public_id INTO v_receipt;
    RETURN v_receipt;
END;
$function$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_review_submission
ON cafeteria.audit_events(action, entity_public_id, (details->>'submitted_token'))
WHERE action IN ('workflow.menu_reviewed', 'workflow.week_context_reviewed');

CREATE INDEX IF NOT EXISTS ix_workflow_review_receipts
ON cafeteria.audit_events(entity_public_id, action, id DESC)
WHERE action IN ('workflow.menu_reviewed', 'workflow.week_context_reviewed');

CREATE OR REPLACE FUNCTION cafeteria.require_api_key_admin(p_actor_id bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_disabled_at timestamptz;
BEGIN
    SELECT disabled_at INTO v_disabled_at FROM cafeteria.users
    WHERE id=p_actor_id FOR SHARE;
    IF NOT FOUND OR v_disabled_at IS NOT NULL THEN
        RAISE EXCEPTION 'API-Schlüssel-Akteur ist nicht berechtigt.' USING ERRCODE='42501';
    END IF;
    PERFORM role_code FROM cafeteria.user_role_cache
    WHERE user_id=p_actor_id ORDER BY role_code FOR SHARE;
    IF NOT EXISTS (
        SELECT 1 FROM cafeteria.user_role_cache ur
        JOIN cafeteria.application_roles ar ON ar.role_code=ur.role_code AND ar.active
        WHERE ur.user_id=p_actor_id AND ur.role_code='Cafeteria.Admin'
    ) THEN
        RAISE EXCEPTION 'API-Schlüssel-Akteur ist nicht berechtigt.' USING ERRCODE='42501';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.create_api_key(
    p_actor_id bigint, p_label text, p_key_prefix text, p_key_hash text,
    p_scopes text[], p_expires_at timestamptz
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_public_id uuid;
BEGIN
    PERFORM cafeteria.require_api_key_admin(p_actor_id);
    INSERT INTO cafeteria.api_keys(
        label, key_prefix, key_hash, scopes, created_by, expires_at
    ) VALUES (
        p_label, p_key_prefix, p_key_hash, p_scopes, p_actor_id, p_expires_at
    ) RETURNING public_id INTO v_public_id;
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, details
    ) VALUES (
        p_actor_id, 'api.key_created', 'api_key', v_public_id,
        jsonb_build_object(
            'label', p_label,
            'key_prefix', p_key_prefix,
            'scopes', p_scopes,
            'expires_at', p_expires_at
        )
    );
    RETURN v_public_id;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.revoke_api_key(p_actor_id bigint, p_public_id uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_key cafeteria.api_keys%ROWTYPE;
BEGIN
    PERFORM cafeteria.require_api_key_admin(p_actor_id);
    SELECT * INTO v_key FROM cafeteria.api_keys
    WHERE public_id=p_public_id FOR UPDATE;
    IF NOT FOUND OR v_key.revoked_at IS NOT NULL THEN
        RETURN false;
    END IF;
    UPDATE cafeteria.api_keys
    SET revoked_at=clock_timestamp(), revoked_by=p_actor_id
    WHERE id=v_key.id;
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, details
    ) VALUES (
        p_actor_id, 'api.key_revoked', 'api_key', v_key.public_id,
        jsonb_build_object('label', v_key.label, 'key_prefix', v_key.key_prefix)
    );
    RETURN true;
END;
$function$;

REVOKE ALL ON cafeteria.api_keys FROM PUBLIC;
GRANT SELECT ON cafeteria.api_keys TO cafeteria_app;
GRANT UPDATE (last_used_at) ON cafeteria.api_keys TO cafeteria_app;
GRANT SELECT ON cafeteria.api_keys TO cafeteria_backup;
GRANT SELECT ON SEQUENCE cafeteria.api_keys_id_seq TO cafeteria_backup;

REVOKE ALL ON FUNCTION
    cafeteria.bump_week_header_revision(),
    cafeteria.workflow_week_context(bigint),
    cafeteria.require_workflow_review_actor(bigint),
    cafeteria.record_menu_review(bigint, bigint, text, bigint, bigint, text, text),
    cafeteria.record_week_context_review(bigint, bigint, text, bigint, text, jsonb),
    cafeteria.require_api_key_admin(bigint),
    cafeteria.create_api_key(bigint, text, text, text, text[], timestamptz),
    cafeteria.revoke_api_key(bigint, uuid)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    cafeteria.workflow_week_context(bigint),
    cafeteria.record_menu_review(bigint, bigint, text, bigint, bigint, text, text),
    cafeteria.record_week_context_review(bigint, bigint, text, bigint, text, jsonb),
    cafeteria.create_api_key(bigint, text, text, text, text[], timestamptz),
    cafeteria.revoke_api_key(bigint, uuid)
TO cafeteria_app;

-- Version-bound local administration. All writers share the existing bootstrap lock.
CREATE OR REPLACE FUNCTION begin_local_admin_v19()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'READ COMMITTED required.' USING ERRCODE='P1901';
    END IF;
    PERFORM set_config('lock_timeout', '5s', true);
    PERFORM pg_advisory_xact_lock(2903847293::bigint);
    PERFORM role_code FROM application_roles ORDER BY role_code FOR SHARE;
END;
$$;

CREATE OR REPLACE FUNCTION lock_local_user_v19(
    p_actor bigint, p_actor_version bigint, p_target uuid, p_target_version bigint
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
DECLARE
    v_target bigint;
    v_ids bigint[];
    v_actor users%ROWTYPE;
    v_user users%ROWTYPE;
BEGIN
    IF p_actor IS NULL OR p_actor <= 0 OR p_actor_version IS NULL OR p_actor_version <= 0
       OR (p_target IS NULL) <> (p_target_version IS NULL)
       OR p_target_version <= 0 THEN
        RAISE EXCEPTION 'Invalid expectations.' USING ERRCODE='P1901';
    END IF;
    PERFORM begin_local_admin_v19();
    SELECT u.id INTO v_target FROM users u
      JOIN local_credentials c ON c.user_id=u.id
     WHERE u.public_id=p_target AND u.auth_provider='local';
    SELECT array_agg(DISTINCT candidate.id) INTO v_ids FROM (
        SELECT p_actor AS id UNION SELECT v_target
        UNION SELECT u.id FROM users u
          JOIN local_credentials c ON c.user_id=u.id
          JOIN user_role_cache r ON r.user_id=u.id AND r.source='local'
          JOIN application_roles a ON a.role_code=r.role_code AND a.active
         WHERE u.auth_provider='local' AND u.disabled_at IS NULL
           AND r.role_code='Cafeteria.Admin'
    ) candidate WHERE candidate.id IS NOT NULL;
    PERFORM u.id FROM users u WHERE u.id=ANY(v_ids) ORDER BY u.id FOR UPDATE;
    PERFORM c.user_id FROM local_credentials c WHERE c.user_id=ANY(v_ids)
      ORDER BY c.user_id FOR UPDATE;
    SELECT * INTO v_actor FROM users WHERE id=p_actor;
    IF NOT FOUND OR v_actor.disabled_at IS NOT NULL OR NOT EXISTS (
        SELECT 1 FROM user_role_cache r JOIN application_roles a ON a.role_code=r.role_code
        WHERE r.user_id=p_actor AND r.role_code='Cafeteria.Admin' AND a.active
    ) THEN
        RAISE EXCEPTION 'Active administrator required.' USING ERRCODE='P1902';
    END IF;
    IF v_actor.authz_version <> p_actor_version THEN
        RAISE EXCEPTION 'Stale actor.' USING ERRCODE='P1903';
    END IF;
    IF p_target IS NOT NULL THEN
        SELECT * INTO v_user FROM users WHERE id=v_target AND public_id=p_target
          AND auth_provider='local';
        IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM local_credentials WHERE user_id=v_target) THEN
            RAISE EXCEPTION 'Unknown local target.' USING ERRCODE='P1904';
        END IF;
        IF v_user.authz_version <> p_target_version THEN
            RAISE EXCEPTION 'Stale target.' USING ERRCODE='P1905';
        END IF;
    END IF;
    RETURN v_target;
END;
$$;

CREATE OR REPLACE FUNCTION require_remaining_local_admin_v19(p_target bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM users u JOIN user_role_cache r ON r.user_id=u.id
        JOIN application_roles a ON a.role_code=r.role_code AND a.active
        WHERE u.id=p_target AND u.auth_provider='local' AND u.disabled_at IS NULL
          AND r.role_code='Cafeteria.Admin' AND r.source='local'
    ) AND NOT EXISTS (
        SELECT 1 FROM users u JOIN local_credentials c ON c.user_id=u.id
        JOIN user_role_cache r ON r.user_id=u.id AND r.source='local'
        JOIN application_roles a ON a.role_code=r.role_code AND a.active
        WHERE u.id<>p_target AND u.auth_provider='local' AND u.disabled_at IS NULL
          AND r.role_code='Cafeteria.Admin'
          AND (c.locked_until IS NULL OR c.locked_until<=clock_timestamp())
    ) THEN
        RAISE EXCEPTION 'Last available local administrator.' USING ERRCODE='P1906';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION validate_local_roles_v19(p_roles text[])
RETURNS text[] LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
DECLARE v_roles text[];
BEGIN
    IF p_roles IS NULL OR cardinality(p_roles)=0 OR cardinality(p_roles)>3
       OR array_ndims(p_roles)<>1 OR EXISTS (
        SELECT 1 FROM unnest(p_roles) role
        LEFT JOIN application_roles a ON a.role_code=role AND a.active
        WHERE a.role_code IS NULL
    ) THEN
        RAISE EXCEPTION 'Invalid roles.' USING ERRCODE='P1901';
    END IF;
    SELECT array_agg(DISTINCT role ORDER BY role) INTO v_roles FROM unnest(p_roles) role;
    IF cardinality(v_roles)<>cardinality(p_roles) THEN
        RAISE EXCEPTION 'Duplicate roles.' USING ERRCODE='P1901';
    END IF;
    RETURN v_roles;
END;
$$;

CREATE OR REPLACE FUNCTION local_user_command_context_v19(
    actor_id bigint DEFAULT NULL, actor_identifier text DEFAULT NULL,
    target_public_id uuid DEFAULT NULL, target_username text DEFAULT NULL
) RETURNS TABLE(actor_user_id bigint, actor_authz_version bigint,
                resolved_target_public_id uuid, target_authz_version bigint,
                resolved_target_username text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
DECLARE v_actor bigint;
BEGIN
    IF actor_identifier IS NOT NULL AND actor_id IS NULL AND target_public_id IS NULL THEN
        IF btrim(actor_identifier) !~ '^[A-Za-z0-9][A-Za-z0-9._@+-]{2,127}$'
           OR (target_username IS NOT NULL AND
               target_username !~ '^[a-z0-9][a-z0-9._-]{2,63}$') THEN
            RAISE EXCEPTION 'Invalid selectors.' USING ERRCODE='P1901';
        END IF;
        v_actor := resolve_auth_actor(actor_identifier);
    ELSIF actor_id IS NOT NULL AND actor_id>0 AND target_public_id IS NOT NULL
          AND actor_identifier IS NULL AND target_username IS NULL THEN
        v_actor := actor_id;
    ELSE
        RAISE EXCEPTION 'Invalid selectors.' USING ERRCODE='P1901';
    END IF;
    SELECT u.id, u.authz_version INTO actor_user_id, actor_authz_version
      FROM users u WHERE u.id=v_actor AND u.disabled_at IS NULL
       AND EXISTS (SELECT 1 FROM user_role_cache r
           JOIN application_roles a ON a.role_code=r.role_code AND a.active
           WHERE r.user_id=u.id AND r.role_code='Cafeteria.Admin');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active administrator required.' USING ERRCODE='P1902';
    END IF;
    IF target_public_id IS NOT NULL OR target_username IS NOT NULL THEN
        SELECT u.public_id, u.authz_version, c.username
          INTO resolved_target_public_id, target_authz_version, resolved_target_username
          FROM users u JOIN local_credentials c ON c.user_id=u.id
         WHERE u.auth_provider='local' AND
           ((target_public_id IS NOT NULL AND u.public_id=target_public_id)
            OR (target_username IS NOT NULL AND c.username=target_username));
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Unknown local target.' USING ERRCODE='P1904';
        END IF;
    END IF;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION create_local_user_v19(
    p_actor bigint, p_actor_version bigint, p_username text, p_display_name text,
    p_password_hash text, p_roles text[]
) RETURNS TABLE(public_id uuid, authz_version bigint, changed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
DECLARE v_id bigint; v_roles text[];
BEGIN
    PERFORM lock_local_user_v19(p_actor, p_actor_version, NULL, NULL);
    v_roles := validate_local_roles_v19(p_roles);
    IF p_username IS NULL OR p_username !~ '^[a-z0-9][a-z0-9._-]{2,63}$'
       OR p_display_name IS NULL OR length(btrim(p_display_name)) NOT BETWEEN 1 AND 120
       OR p_password_hash IS NULL OR p_password_hash !~
          '^(scrypt:[0-9]+:[0-9]+:[0-9]+|pbkdf2:sha256:[0-9]+)\$[^$]+\$[0-9a-f]+$' THEN
        RAISE EXCEPTION 'Invalid local account.' USING ERRCODE='P1901';
    END IF;
    INSERT INTO users(auth_provider, display_name, last_seen_roles)
      VALUES ('local', btrim(p_display_name), to_jsonb(v_roles)) RETURNING id INTO v_id;
    INSERT INTO local_credentials(user_id, username, password_hash)
      VALUES (v_id, p_username, p_password_hash);
    INSERT INTO user_role_cache(user_id, role_code, source)
      SELECT v_id, role, 'local' FROM unnest(v_roles) role;
    SELECT u.public_id, u.authz_version INTO public_id, authz_version FROM users u WHERE u.id=v_id;
    INSERT INTO audit_events(actor_user_id, action, entity_type, entity_public_id, details)
      VALUES (p_actor, 'auth.local_user_provisioned', 'user', public_id,
          jsonb_build_object('target_user_id', v_id, 'new_roles', v_roles,
                            'old_authz_version', NULL, 'authz_version', authz_version));
    INSERT INTO audit_events(actor_user_id, action, entity_type, entity_public_id, details)
      SELECT p_actor, 'auth.local_role_granted', 'user', public_id,
        jsonb_build_object('target_user_id', v_id, 'role_code', role,
                          'authz_version', authz_version) FROM unnest(v_roles) role;
    changed := true; RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION replace_local_roles_v19(
    p_actor bigint, p_actor_version bigint, p_target uuid, p_target_version bigint, p_roles text[]
) RETURNS TABLE(public_id uuid, authz_version bigint, changed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
DECLARE v_id bigint; v_old text[]; v_roles text[];
BEGIN
    IF p_target IS NULL THEN RAISE EXCEPTION 'Target required.' USING ERRCODE='P1901'; END IF;
    v_id := lock_local_user_v19(p_actor, p_actor_version, p_target, p_target_version);
    v_roles := validate_local_roles_v19(p_roles);
    SELECT COALESCE(array_agg(role_code ORDER BY role_code), ARRAY[]::text[]) INTO v_old
      FROM user_role_cache WHERE user_id=v_id AND source='local';
    changed := v_old IS DISTINCT FROM v_roles;
    IF changed THEN
        IF NOT ('Cafeteria.Admin'=ANY(v_roles)) THEN
            PERFORM require_remaining_local_admin_v19(v_id);
        END IF;
        DELETE FROM user_role_cache WHERE user_id=v_id AND source='local'
          AND NOT (role_code=ANY(v_roles));
        INSERT INTO user_role_cache(user_id, role_code, source)
          SELECT v_id, role, 'local' FROM unnest(v_roles) role ON CONFLICT DO NOTHING;
        UPDATE users SET last_seen_roles=to_jsonb(v_roles) WHERE id=v_id;
    END IF;
    SELECT u.public_id, u.authz_version INTO public_id, authz_version FROM users u WHERE u.id=v_id;
    IF changed THEN
        INSERT INTO audit_events(actor_user_id, action, entity_type, entity_public_id, details)
          VALUES (p_actor, 'auth.local_roles_changed', 'user', public_id,
            jsonb_build_object('target_user_id', v_id, 'old_roles', v_old, 'new_roles', v_roles,
                'old_authz_version', p_target_version, 'authz_version', authz_version));
    END IF;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION reset_local_password_v19(
    p_actor bigint, p_actor_version bigint, p_target uuid, p_target_version bigint, p_password_hash text
) RETURNS TABLE(public_id uuid, authz_version bigint, changed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
DECLARE v_id bigint;
BEGIN
    IF p_target IS NULL OR p_password_hash IS NULL OR p_password_hash !~
       '^(scrypt:[0-9]+:[0-9]+:[0-9]+|pbkdf2:sha256:[0-9]+)\$[^$]+\$[0-9a-f]+$' THEN
        RAISE EXCEPTION 'Invalid password input.' USING ERRCODE='P1901';
    END IF;
    v_id := lock_local_user_v19(p_actor, p_actor_version, p_target, p_target_version);
    UPDATE local_credentials SET password_hash=p_password_hash, failed_login_count=0,
        locked_until=NULL, last_failed_at=NULL, password_changed_at=clock_timestamp()
      WHERE user_id=v_id;
    UPDATE users u SET authz_version=u.authz_version+1 WHERE u.id=v_id
      RETURNING u.public_id, u.authz_version INTO public_id, authz_version;
    INSERT INTO audit_events(actor_user_id, action, entity_type, entity_public_id, details)
      VALUES (p_actor, 'auth.local_password_changed', 'user', public_id,
        jsonb_build_object('target_user_id', v_id, 'old_authz_version', p_target_version,
                          'authz_version', authz_version));
    changed := true; RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION set_local_status_v19(
    p_actor bigint, p_actor_version bigint, p_target uuid, p_target_version bigint, p_disabled boolean
) RETURNS TABLE(public_id uuid, authz_version bigint, changed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
DECLARE v_id bigint; v_disabled boolean;
BEGIN
    IF p_target IS NULL OR p_disabled IS NULL THEN
        RAISE EXCEPTION 'Target and status required.' USING ERRCODE='P1901';
    END IF;
    v_id := lock_local_user_v19(p_actor, p_actor_version, p_target, p_target_version);
    SELECT disabled_at IS NOT NULL INTO v_disabled FROM users WHERE id=v_id;
    changed := v_disabled <> p_disabled;
    IF changed THEN
        IF p_disabled THEN PERFORM require_remaining_local_admin_v19(v_id); END IF;
        UPDATE users SET disabled_at=CASE WHEN p_disabled THEN clock_timestamp() ELSE NULL END
          WHERE id=v_id;
    END IF;
    SELECT u.public_id, u.authz_version INTO public_id, authz_version FROM users u WHERE u.id=v_id;
    IF changed THEN
        INSERT INTO audit_events(actor_user_id, action, entity_type, entity_public_id, details)
          VALUES (p_actor, CASE WHEN p_disabled THEN 'auth.local_user_disabled'
                               ELSE 'auth.local_user_reactivated' END, 'user', public_id,
            jsonb_build_object('target_user_id', v_id, 'old_disabled', v_disabled,
                'new_disabled', p_disabled, 'old_authz_version', p_target_version,
                'authz_version', authz_version));
    END IF;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION deactivate_local_user_v19(
    p_actor bigint, p_actor_version bigint, p_target uuid, p_target_version bigint
) RETURNS TABLE(public_id uuid, authz_version bigint, changed boolean)
LANGUAGE sql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
    SELECT * FROM set_local_status_v19(p_actor, p_actor_version, p_target, p_target_version, true);
$$;
CREATE OR REPLACE FUNCTION reactivate_local_user_v19(
    p_actor bigint, p_actor_version bigint, p_target uuid, p_target_version bigint
) RETURNS TABLE(public_id uuid, authz_version bigint, changed boolean)
LANGUAGE sql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
    SELECT * FROM set_local_status_v19(p_actor, p_actor_version, p_target, p_target_version, false);
$$;

CREATE OR REPLACE FUNCTION reject_audit_rewrite_v19()
RETURNS trigger LANGUAGE plpgsql SET search_path = cafeteria, pg_temp AS $$
BEGIN
    -- Preserve the existing owner immutability error; role writes fail at the ACL.
    RAISE EXCEPTION 'Audit events are append-only.' USING ERRCODE='55000';
END;
$$;
DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events;
CREATE TRIGGER trg_audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events
FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_rewrite_v19();
DROP TRIGGER IF EXISTS trg_audit_events_no_truncate ON audit_events;
CREATE TRIGGER trg_audit_events_no_truncate BEFORE TRUNCATE ON audit_events
FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_rewrite_v19();

REVOKE EXECUTE ON FUNCTION
    begin_local_admin_v19(), lock_local_user_v19(bigint,bigint,uuid,bigint),
    require_remaining_local_admin_v19(bigint), validate_local_roles_v19(text[]),
    set_local_status_v19(bigint,bigint,uuid,bigint,boolean), reject_audit_rewrite_v19(),
    create_local_user_v19(bigint,bigint,text,text,text,text[]),
    replace_local_roles_v19(bigint,bigint,uuid,bigint,text[]),
    reset_local_password_v19(bigint,bigint,uuid,bigint,text),
    deactivate_local_user_v19(bigint,bigint,uuid,bigint),
    reactivate_local_user_v19(bigint,bigint,uuid,bigint),
    local_user_command_context_v19(bigint,text,uuid,text),
    provision_local_user(text,text,text,text,text[]),
    set_local_password(text,text,text), disable_local_user(text,text)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    create_local_user_v19(bigint,bigint,text,text,text,text[]),
    replace_local_roles_v19(bigint,bigint,uuid,bigint,text[]),
    reset_local_password_v19(bigint,bigint,uuid,bigint,text),
    deactivate_local_user_v19(bigint,bigint,uuid,bigint),
    reactivate_local_user_v19(bigint,bigint,uuid,bigint),
    local_user_command_context_v19(bigint,text,uuid,text)
TO cafeteria_auth_issuer;

CREATE OR REPLACE FUNCTION bootstrap_first_local_admin(
    p_username text, p_display_name text, p_password_hash text
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
DECLARE v_id bigint; v_system bigint;
BEGIN
    PERFORM begin_local_admin_v19();
    IF p_username IS NULL OR p_username !~ '^[a-z0-9][a-z0-9._-]{2,63}$'
       OR p_display_name IS NULL OR btrim(p_display_name)=''
       OR p_password_hash IS NULL OR p_password_hash !~
          '^(scrypt:[0-9]+:[0-9]+:[0-9]+|pbkdf2:sha256:[0-9]+)\$[^$]+\$[0-9a-f]+$' THEN
        RAISE EXCEPTION 'Lokale Benutzerangaben sind ungültig.' USING ERRCODE='22023';
    END IF;
    IF EXISTS (SELECT 1 FROM users u JOIN user_role_cache r ON r.user_id=u.id
        JOIN application_roles a ON a.role_code=r.role_code AND a.active
        WHERE u.disabled_at IS NULL AND r.role_code='Cafeteria.Admin') THEN
        RAISE EXCEPTION 'Es existiert bereits ein aktiver Administrator; Bootstrap ist gesperrt.'
          USING ERRCODE='42501';
    END IF;
    SELECT id INTO v_system FROM users
      WHERE auth_provider='system' AND public_id='00000000-0000-0000-0000-000000000001';
    IF v_system IS NULL THEN
        RAISE EXCEPTION 'System-Benutzer fehlt in der Datenbank.' USING ERRCODE='22023';
    END IF;
    INSERT INTO users(auth_provider, display_name, last_seen_roles)
      VALUES ('local', btrim(p_display_name), '["Cafeteria.Admin"]'::jsonb)
      RETURNING id INTO v_id;
    INSERT INTO local_credentials(user_id, username, password_hash)
      VALUES (v_id, p_username, p_password_hash);
    INSERT INTO user_role_cache(user_id, role_code, source)
      VALUES (v_id, 'Cafeteria.Admin', 'local');
    INSERT INTO audit_events(actor_user_id, action, entity_type, entity_public_id, details)
      SELECT v_system, 'auth.local_admin_bootstrapped', 'user', public_id,
        jsonb_build_object('target_user_id', v_id, 'username', p_username,
                          'authz_version', authz_version) FROM users WHERE id=v_id;
    INSERT INTO audit_events(actor_user_id, action, entity_type, entity_public_id, details)
      SELECT v_system, 'auth.local_role_granted', 'user', public_id,
        jsonb_build_object('target_user_id', v_id, 'role_code', 'Cafeteria.Admin',
                          'authz_version', authz_version) FROM users WHERE id=v_id;
    RETURN v_id;
END;
$$;
REVOKE EXECUTE ON FUNCTION bootstrap_first_local_admin(text,text,text)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

-- Anzeigenamen sind das einzige durch die Anwendung pflegbare Feld der Profile.
GRANT UPDATE (display_name, allows_weekend) ON offer_profiles TO cafeteria_app;

-- Settings writers hold IAM role definitions and the original actor until commit.
-- No credentials, bootstrap state or roles are changed by this guard.
CREATE OR REPLACE FUNCTION lock_operations_actor(p_actor bigint, p_actor_version bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = cafeteria, pg_temp AS $$
BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'READ COMMITTED required.' USING ERRCODE='25001';
    END IF;
    PERFORM set_config('lock_timeout', '5s', true);
    PERFORM role_code FROM application_roles ORDER BY role_code FOR SHARE;
    PERFORM id FROM users WHERE id=p_actor ORDER BY id FOR UPDATE;
    IF p_actor IS NULL OR p_actor <= 0 OR p_actor_version IS NULL OR p_actor_version <= 0
       OR NOT EXISTS (
        SELECT 1 FROM users u WHERE u.id=p_actor AND u.authz_version=p_actor_version
          AND u.disabled_at IS NULL AND EXISTS (
            SELECT 1 FROM user_role_cache r
            JOIN application_roles a ON a.role_code=r.role_code AND a.active
            WHERE r.user_id=u.id AND r.role_code='Cafeteria.Admin'
          )
       ) THEN
        RAISE EXCEPTION 'Current administrator required.' USING ERRCODE='42501';
    END IF;
END;
$$;
REVOKE ALL ON FUNCTION lock_operations_actor(bigint,bigint)
FROM PUBLIC, cafeteria_app, cafeteria_auth_issuer, cafeteria_backup;
GRANT EXECUTE ON FUNCTION lock_operations_actor(bigint,bigint) TO cafeteria_app;

-- B2 M-A schema21 contract.

-- Unicode 16.0.0: reject every category C character and markup delimiters.
CREATE FUNCTION master_text(p_value text, p_max integer, p_required boolean DEFAULT true)
RETURNS text LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v text;
BEGIN
    IF p_value IS NULL THEN
        IF p_required THEN RAISE EXCEPTION 'Missing text.' USING ERRCODE='P1901'; END IF;
        RETURN NULL;
    END IF;
    IF p_value ~ U&'[\0001-\001F\007F-\009F\00AD\0378-\0379\0380-\0383\038B\038D\03A2\0530\0557-\0558\058B-\058C\0590\05C8-\05CF\05EB-\05EE\05F5-\0605\061C\06DD\070E-\070F\074B-\074C\07B2-\07BF\07FB-\07FC\082E-\082F\083F\085C-\085D\085F\086B-\086F\088F-\0896\08E2\0984\098D-\098E\0991-\0992\09A9\09B1\09B3-\09B5\09BA-\09BB\09C5-\09C6\09C9-\09CA\09CF-\09D6\09D8-\09DB\09DE\09E4-\09E5\09FF-\0A00\0A04\0A0B-\0A0E\0A11-\0A12\0A29\0A31\0A34\0A37\0A3A-\0A3B\0A3D\0A43-\0A46\0A49-\0A4A\0A4E-\0A50\0A52-\0A58\0A5D\0A5F-\0A65\0A77-\0A80\0A84\0A8E\0A92\0AA9\0AB1\0AB4\0ABA-\0ABB\0AC6\0ACA\0ACE-\0ACF\0AD1-\0ADF\0AE4-\0AE5\0AF2-\0AF8\0B00\0B04\0B0D-\0B0E\0B11-\0B12\0B29\0B31\0B34\0B3A-\0B3B\0B45-\0B46\0B49-\0B4A\0B4E-\0B54\0B58-\0B5B\0B5E\0B64-\0B65\0B78-\0B81\0B84\0B8B-\0B8D\0B91\0B96-\0B98\0B9B\0B9D\0BA0-\0BA2\0BA5-\0BA7\0BAB-\0BAD\0BBA-\0BBD\0BC3-\0BC5\0BC9\0BCE-\0BCF\0BD1-\0BD6\0BD8-\0BE5\0BFB-\0BFF\0C0D\0C11\0C29\0C3A-\0C3B\0C45\0C49\0C4E-\0C54\0C57\0C5B-\0C5C\0C5E-\0C5F\0C64-\0C65\0C70-\0C76\0C8D\0C91\0CA9\0CB4\0CBA-\0CBB\0CC5\0CC9\0CCE-\0CD4\0CD7-\0CDC\0CDF\0CE4-\0CE5\0CF0\0CF4-\0CFF\0D0D\0D11\0D45\0D49\0D50-\0D53\0D64-\0D65\0D80\0D84\0D97-\0D99\0DB2\0DBC\0DBE-\0DBF\0DC7-\0DC9\0DCB-\0DCE\0DD5\0DD7\0DE0-\0DE5\0DF0-\0DF1\0DF5-\0E00\0E3B-\0E3E\0E5C-\0E80\0E83\0E85\0E8B\0EA4\0EA6\0EBE-\0EBF\0EC5\0EC7\0ECF\0EDA-\0EDB\0EE0-\0EFF\0F48\0F6D-\0F70\0F98\0FBD\0FCD\0FDB-\0FFF\10C6\10C8-\10CC\10CE-\10CF\1249\124E-\124F\1257\1259\125E-\125F\1289\128E-\128F\12B1\12B6-\12B7\12BF\12C1\12C6-\12C7\12D7\1311\1316-\1317\135B-\135C\137D-\137F\139A-\139F\13F6-\13F7\13FE-\13FF\169D-\169F\16F9-\16FF\1716-\171E\1737-\173F\1754-\175F\176D\1771\1774-\177F\17DE-\17DF\17EA-\17EF\17FA-\17FF\180E\181A-\181F\1879-\187F\18AB-\18AF\18F6-\18FF\191F\192C-\192F\193C-\193F\1941-\1943\196E-\196F\1975-\197F\19AC-\19AF\19CA-\19CF\19DB-\19DD\1A1C-\1A1D\1A5F\1A7D-\1A7E\1A8A-\1A8F\1A9A-\1A9F\1AAE-\1AAF\1ACF-\1AFF\1B4D\1BF4-\1BFB\1C38-\1C3A\1C4A-\1C4C\1C8B-\1C8F\1CBB-\1CBC\1CC8-\1CCF\1CFB-\1CFF\1F16-\1F17\1F1E-\1F1F\1F46-\1F47\1F4E-\1F4F\1F58\1F5A\1F5C\1F5E\1F7E-\1F7F\1FB5\1FC5\1FD4-\1FD5\1FDC\1FF0-\1FF1\1FF5\1FFF\200B-\200F\202A-\202E\2060-\206F\2072-\2073\208F\209D-\209F\20C1-\20CF\20F1-\20FF\218C-\218F\242A-\243F\244B-\245F\2B74-\2B75\2B96\2CF4-\2CF8\2D26\2D28-\2D2C\2D2E-\2D2F\2D68-\2D6E\2D71-\2D7E\2D97-\2D9F\2DA7\2DAF\2DB7\2DBF\2DC7\2DCF\2DD7\2DDF\2E5E-\2E7F\2E9A\2EF4-\2EFF\2FD6-\2FEF\3040\3097-\3098\3100-\3104\3130\318F\31E6-\31EE\321F\A48D-\A48F\A4C7-\A4CF\A62C-\A63F\A6F8-\A6FF\A7CE-\A7CF\A7D2\A7D4\A7DD-\A7F1\A82D-\A82F\A83A-\A83F\A878-\A87F\A8C6-\A8CD\A8DA-\A8DF\A954-\A95E\A97D-\A97F\A9CE\A9DA-\A9DD\A9FF\AA37-\AA3F\AA4E-\AA4F\AA5A-\AA5B\AAC3-\AADA\AAF7-\AB00\AB07-\AB08\AB0F-\AB10\AB17-\AB1F\AB27\AB2F\AB6C-\AB6F\ABEE-\ABEF\ABFA-\ABFF\D7A4-\D7AF\D7C7-\D7CA\D7FC-\F8FF\FA6E-\FA6F\FADA-\FAFF\FB07-\FB12\FB18-\FB1C\FB37\FB3D\FB3F\FB42\FB45\FBC3-\FBD2\FD90-\FD91\FDC8-\FDCE\FDD0-\FDEF\FE1A-\FE1F\FE53\FE67\FE6C-\FE6F\FE75\FEFD-\FF00\FFBF-\FFC1\FFC8-\FFC9\FFD0-\FFD1\FFD8-\FFD9\FFDD-\FFDF\FFE7\FFEF-\FFFB\FFFE-\FFFF\+01000C\+010027\+01003B\+01003E\+01004E-\+01004F\+01005E-\+01007F\+0100FB-\+0100FF\+010103-\+010106\+010134-\+010136\+01018F\+01019D-\+01019F\+0101A1-\+0101CF\+0101FE-\+01027F\+01029D-\+01029F\+0102D1-\+0102DF\+0102FC-\+0102FF\+010324-\+01032C\+01034B-\+01034F\+01037B-\+01037F\+01039E\+0103C4-\+0103C7\+0103D6-\+0103FF\+01049E-\+01049F\+0104AA-\+0104AF\+0104D4-\+0104D7\+0104FC-\+0104FF\+010528-\+01052F\+010564-\+01056E\+01057B\+01058B\+010593\+010596\+0105A2\+0105B2\+0105BA\+0105BD-\+0105BF\+0105F4-\+0105FF\+010737-\+01073F\+010756-\+01075F\+010768-\+01077F\+010786\+0107B1\+0107BB-\+0107FF\+010806-\+010807\+010809\+010836\+010839-\+01083B\+01083D-\+01083E\+010856\+01089F-\+0108A6\+0108B0-\+0108DF\+0108F3\+0108F6-\+0108FA\+01091C-\+01091E\+01093A-\+01093E\+010940-\+01097F\+0109B8-\+0109BB\+0109D0-\+0109D1\+010A04\+010A07-\+010A0B\+010A14\+010A18\+010A36-\+010A37\+010A3B-\+010A3E\+010A49-\+010A4F\+010A59-\+010A5F\+010AA0-\+010ABF\+010AE7-\+010AEA\+010AF7-\+010AFF\+010B36-\+010B38\+010B56-\+010B57\+010B73-\+010B77\+010B92-\+010B98\+010B9D-\+010BA8\+010BB0-\+010BFF\+010C49-\+010C7F\+010CB3-\+010CBF\+010CF3-\+010CF9\+010D28-\+010D2F\+010D3A-\+010D3F\+010D66-\+010D68\+010D86-\+010D8D\+010D90-\+010E5F\+010E7F\+010EAA\+010EAE-\+010EAF\+010EB2-\+010EC1\+010EC5-\+010EFB\+010F28-\+010F2F\+010F5A-\+010F6F\+010F8A-\+010FAF\+010FCC-\+010FDF\+010FF7-\+010FFF\+01104E-\+011051\+011076-\+01107E\+0110BD\+0110C3-\+0110CF\+0110E9-\+0110EF\+0110FA-\+0110FF\+011135\+011148-\+01114F\+011177-\+01117F\+0111E0\+0111F5-\+0111FF\+011212\+011242-\+01127F\+011287\+011289\+01128E\+01129E\+0112AA-\+0112AF\+0112EB-\+0112EF\+0112FA-\+0112FF\+011304\+01130D-\+01130E\+011311-\+011312\+011329\+011331\+011334\+01133A\+011345-\+011346\+011349-\+01134A\+01134E-\+01134F\+011351-\+011356\+011358-\+01135C\+011364-\+011365\+01136D-\+01136F\+011375-\+01137F\+01138A\+01138C-\+01138D\+01138F\+0113B6\+0113C1\+0113C3-\+0113C4\+0113C6\+0113CB\+0113D6\+0113D9-\+0113E0\+0113E3-\+0113FF\+01145C\+011462-\+01147F\+0114C8-\+0114CF\+0114DA-\+01157F\+0115B6-\+0115B7\+0115DE-\+0115FF\+011645-\+01164F\+01165A-\+01165F\+01166D-\+01167F\+0116BA-\+0116BF\+0116CA-\+0116CF\+0116E4-\+0116FF\+01171B-\+01171C\+01172C-\+01172F\+011747-\+0117FF\+01183C-\+01189F\+0118F3-\+0118FE\+011907-\+011908\+01190A-\+01190B\+011914\+011917\+011936\+011939-\+01193A\+011947-\+01194F\+01195A-\+01199F\+0119A8-\+0119A9\+0119D8-\+0119D9\+0119E5-\+0119FF\+011A48-\+011A4F\+011AA3-\+011AAF\+011AF9-\+011AFF\+011B0A-\+011BBF\+011BE2-\+011BEF\+011BFA-\+011BFF\+011C09\+011C37\+011C46-\+011C4F\+011C6D-\+011C6F\+011C90-\+011C91\+011CA8\+011CB7-\+011CFF\+011D07\+011D0A\+011D37-\+011D39\+011D3B\+011D3E\+011D48-\+011D4F\+011D5A-\+011D5F\+011D66\+011D69\+011D8F\+011D92\+011D99-\+011D9F\+011DAA-\+011EDF\+011EF9-\+011EFF\+011F11\+011F3B-\+011F3D\+011F5B-\+011FAF\+011FB1-\+011FBF\+011FF2-\+011FFE\+01239A-\+0123FF\+01246F\+012475-\+01247F\+012544-\+012F8F\+012FF3-\+012FFF\+013430-\+01343F\+013456-\+01345F\+0143FB-\+0143FF\+014647-\+0160FF\+01613A-\+0167FF\+016A39-\+016A3F\+016A5F\+016A6A-\+016A6D\+016ABF\+016ACA-\+016ACF\+016AEE-\+016AEF\+016AF6-\+016AFF\+016B46-\+016B4F\+016B5A\+016B62\+016B78-\+016B7C\+016B90-\+016D3F\+016D7A-\+016E3F\+016E9B-\+016EFF\+016F4B-\+016F4E\+016F88-\+016F8E\+016FA0-\+016FDF\+016FE5-\+016FEF\+016FF2-\+016FFF\+0187F8-\+0187FF\+018CD6-\+018CFE\+018D09-\+01AFEF\+01AFF4\+01AFFC\+01AFFF\+01B123-\+01B131\+01B133-\+01B14F\+01B153-\+01B154\+01B156-\+01B163\+01B168-\+01B16F\+01B2FC-\+01BBFF\+01BC6B-\+01BC6F\+01BC7D-\+01BC7F\+01BC89-\+01BC8F\+01BC9A-\+01BC9B\+01BCA0-\+01CBFF\+01CCFA-\+01CCFF\+01CEB4-\+01CEFF\+01CF2E-\+01CF2F\+01CF47-\+01CF4F\+01CFC4-\+01CFFF\+01D0F6-\+01D0FF\+01D127-\+01D128\+01D173-\+01D17A\+01D1EB-\+01D1FF\+01D246-\+01D2BF\+01D2D4-\+01D2DF\+01D2F4-\+01D2FF\+01D357-\+01D35F\+01D379-\+01D3FF\+01D455\+01D49D\+01D4A0-\+01D4A1\+01D4A3-\+01D4A4\+01D4A7-\+01D4A8\+01D4AD\+01D4BA\+01D4BC\+01D4C4\+01D506\+01D50B-\+01D50C\+01D515\+01D51D\+01D53A\+01D53F\+01D545\+01D547-\+01D549\+01D551\+01D6A6-\+01D6A7\+01D7CC-\+01D7CD\+01DA8C-\+01DA9A\+01DAA0\+01DAB0-\+01DEFF\+01DF1F-\+01DF24\+01DF2B-\+01DFFF\+01E007\+01E019-\+01E01A\+01E022\+01E025\+01E02B-\+01E02F\+01E06E-\+01E08E\+01E090-\+01E0FF\+01E12D-\+01E12F\+01E13E-\+01E13F\+01E14A-\+01E14D\+01E150-\+01E28F\+01E2AF-\+01E2BF\+01E2FA-\+01E2FE\+01E300-\+01E4CF\+01E4FA-\+01E5CF\+01E5FB-\+01E5FE\+01E600-\+01E7DF\+01E7E7\+01E7EC\+01E7EF\+01E7FF\+01E8C5-\+01E8C6\+01E8D7-\+01E8FF\+01E94C-\+01E94F\+01E95A-\+01E95D\+01E960-\+01EC70\+01ECB5-\+01ED00\+01ED3E-\+01EDFF\+01EE04\+01EE20\+01EE23\+01EE25-\+01EE26\+01EE28\+01EE33\+01EE38\+01EE3A\+01EE3C-\+01EE41\+01EE43-\+01EE46\+01EE48\+01EE4A\+01EE4C\+01EE50\+01EE53\+01EE55-\+01EE56\+01EE58\+01EE5A\+01EE5C\+01EE5E\+01EE60\+01EE63\+01EE65-\+01EE66\+01EE6B\+01EE73\+01EE78\+01EE7D\+01EE7F\+01EE8A\+01EE9C-\+01EEA0\+01EEA4\+01EEAA\+01EEBC-\+01EEEF\+01EEF2-\+01EFFF\+01F02C-\+01F02F\+01F094-\+01F09F\+01F0AF-\+01F0B0\+01F0C0\+01F0D0\+01F0F6-\+01F0FF\+01F1AE-\+01F1E5\+01F203-\+01F20F\+01F23C-\+01F23F\+01F249-\+01F24F\+01F252-\+01F25F\+01F266-\+01F2FF\+01F6D8-\+01F6DB\+01F6ED-\+01F6EF\+01F6FD-\+01F6FF\+01F777-\+01F77A\+01F7DA-\+01F7DF\+01F7EC-\+01F7EF\+01F7F1-\+01F7FF\+01F80C-\+01F80F\+01F848-\+01F84F\+01F85A-\+01F85F\+01F888-\+01F88F\+01F8AE-\+01F8AF\+01F8BC-\+01F8BF\+01F8C2-\+01F8FF\+01FA54-\+01FA5F\+01FA6E-\+01FA6F\+01FA7D-\+01FA7F\+01FA8A-\+01FA8E\+01FAC7-\+01FACD\+01FADD-\+01FADE\+01FAEA-\+01FAEF\+01FAF9-\+01FAFF\+01FB93\+01FBFA-\+01FFFF\+02A6E0-\+02A6FF\+02B73A-\+02B73F\+02B81E-\+02B81F\+02CEA2-\+02CEAF\+02EBE1-\+02EBEF\+02EE5E-\+02F7FF\+02FA1E-\+02FFFF\+03134B-\+03134F\+0323B0-\+0E00FF\+0E01F0-\+10FFFF<>]' THEN
        RAISE EXCEPTION 'Invalid text character.' USING ERRCODE='P1901';
    END IF;
    v := btrim(regexp_replace(normalize(p_value, NFC), U&'[ \00A0\1680\2000-\200A\2028\2029\202F\205F\3000]+', ' ', 'g'));
    IF length(v)>p_max OR (p_required AND v='') THEN
        RAISE EXCEPTION 'Invalid text length.' USING ERRCODE='P1901';
    END IF;
    RETURN v;
END;
$fn$;
CREATE FUNCTION master_factor(p_value numeric) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $fn$
 SELECT p_value IS NOT NULL AND p_value > 0 AND p_value < 100000000000
        AND p_value=round(p_value,9);
$fn$;
CREATE FUNCTION master_quantity(p_value numeric) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $fn$
 SELECT p_value IS NOT NULL AND p_value > 0 AND p_value < 1000000000000
        AND p_value=round(p_value,6);
$fn$;

CREATE TABLE IF NOT EXISTS measurement_units (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    code text NOT NULL UNIQUE CHECK(code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    display_name text NOT NULL CHECK(display_name=master_text(display_name,120)),
    dimension text NOT NULL CHECK(dimension IN ('mass','volume','count','contextual')),
    base_factor numeric,
    active boolean NOT NULL DEFAULT true,
    CHECK((dimension='contextual' AND base_factor IS NULL) OR
          (dimension<>'contextual' AND master_factor(base_factor)))
);

CREATE TABLE IF NOT EXISTS food_categories (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    code text NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    name text NOT NULL CHECK(name=master_text(name,120)),
    sort_order smallint NOT NULL DEFAULT 1 CHECK(sort_order BETWEEN 1 AND 9999),
    active boolean NOT NULL DEFAULT true,
    UNIQUE(location_id,id), UNIQUE(location_id,code)
);

CREATE UNIQUE INDEX uq_food_categories_name ON food_categories(location_id,lower(btrim(name)));

CREATE TABLE IF NOT EXISTS tags (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    code text NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    name text NOT NULL CHECK(name=master_text(name,120)),
    active boolean NOT NULL DEFAULT true,
    UNIQUE(location_id,id), UNIQUE(location_id,code)
);

CREATE TABLE IF NOT EXISTS storage_locations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    code text NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    name text NOT NULL CHECK(name=master_text(name,120)),
    sort_order smallint NOT NULL DEFAULT 1 CHECK(sort_order BETWEEN 1 AND 9999),
    active boolean NOT NULL DEFAULT true,
    UNIQUE(location_id,id), UNIQUE(location_id,code)
);

CREATE TABLE IF NOT EXISTS foods (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    name text NOT NULL CHECK(name=master_text(name,120)),
    category_id bigint, base_unit_id bigint NOT NULL REFERENCES measurement_units(id),
    density_g_per_ml numeric CHECK(density_g_per_ml IS NULL OR master_factor(density_g_per_ml)),
    piece_weight_g numeric CHECK(piece_weight_g IS NULL OR master_factor(piece_weight_g)),
    note text NOT NULL DEFAULT '' CHECK(note=master_text(note,500,false)),
    active boolean NOT NULL DEFAULT true,
    allergen_review_status text NOT NULL DEFAULT 'not_checked'
        CHECK(allergen_review_status IN ('not_checked','checked')),
    source_kind text NOT NULL DEFAULT 'manual'
        CHECK(source_kind IN ('manual','url','file_import','ai_assisted','off','supplier')),
    source_reference text CHECK(source_reference=master_text(source_reference,200,false)),
    source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
    source_note text CHECK(source_note=master_text(source_note,500,false)),
    fetched_at timestamptz,
    CHECK(source_kind='manual' OR (nullif(source_reference,'') IS NOT NULL AND fetched_at IS NOT NULL
        AND (nullif(source_url,'') IS NOT NULL OR nullif(source_note,'') IS NOT NULL))),
    CHECK(source_kind<>'url' OR source_url IS NOT NULL),
    UNIQUE(location_id,id),
    FOREIGN KEY(location_id,category_id) REFERENCES food_categories(location_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX uq_foods_name ON foods(location_id,lower(btrim(name)));

CREATE TABLE IF NOT EXISTS food_tags (
    location_id bigint NOT NULL, food_id bigint NOT NULL, tag_id bigint NOT NULL,
    PRIMARY KEY(food_id,tag_id),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(location_id,tag_id) REFERENCES tags(location_id,id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS food_storage_locations (
    location_id bigint NOT NULL, food_id bigint NOT NULL, storage_location_id bigint NOT NULL,
    PRIMARY KEY(food_id,storage_location_id),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(location_id,storage_location_id) REFERENCES storage_locations(location_id,id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS food_labels (
    location_id bigint NOT NULL, food_id bigint NOT NULL,
    label_id smallint NOT NULL REFERENCES dietary_labels(id) ON DELETE RESTRICT,
    PRIMARY KEY(food_id,label_id),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS food_allergens (
    location_id bigint NOT NULL, food_id bigint NOT NULL,
    allergen_id smallint NOT NULL REFERENCES allergens(id) ON DELETE RESTRICT,
    presence text NOT NULL CHECK(presence IN ('contains','may_contain')),
    PRIMARY KEY(food_id,allergen_id),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT
);

CREATE FUNCTION master_json_valid(p_value jsonb, p_depth integer DEFAULT 0)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v jsonb; n integer;
BEGIN
    IF p_value IS NULL OR p_depth>5 THEN RETURN false; END IF;
    IF p_depth=0 THEN
        SELECT count(*) INTO n FROM jsonb_path_query(p_value,'strict $.**') node
          CROSS JOIN LATERAL jsonb_object_keys(
            CASE WHEN jsonb_typeof(node)='object' THEN node ELSE '{}'::jsonb END) k;
        IF n>200 THEN RETURN false; END IF;
    END IF;
    IF jsonb_typeof(p_value)='object' THEN
        SELECT count(*) INTO n FROM jsonb_object_keys(p_value);
        IF n>200 THEN RETURN false; END IF;
        FOR v IN SELECT value FROM jsonb_each(p_value) LOOP
            IF NOT master_json_valid(v,p_depth+1) THEN RETURN false; END IF;
        END LOOP;
    ELSIF jsonb_typeof(p_value)='array' THEN
        FOR v IN SELECT value FROM jsonb_array_elements(p_value) LOOP
            IF NOT master_json_valid(v,p_depth+1) THEN RETURN false; END IF;
        END LOOP;
    END IF;
    RETURN true;
END;
$fn$;

CREATE TABLE IF NOT EXISTS food_data_proposals (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id), location_id bigint NOT NULL REFERENCES locations(id), food_id bigint,
    source text NOT NULL CHECK(source IN ('off','supplier','ai','file_import')),
    source_reference text NOT NULL CHECK(source_reference=master_text(source_reference,200)),
    source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
    source_note text CHECK(source_note=master_text(source_note,500,false)),
    fetched_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object' AND
        octet_length(payload::text)<=65536 AND master_json_valid(payload)),
    status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','accepted','rejected')),
    decided_by bigint REFERENCES users(id), decided_at timestamptz,
    decision_detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK((status='open' AND decided_by IS NULL AND decided_at IS NULL AND decision_detail='{}')
       OR (status<>'open' AND decided_by IS NOT NULL AND decided_at IS NOT NULL)),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT
);

CREATE FUNCTION protect_master_data() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'Archive instead of deleting master data.' USING ERRCODE='55000';
    END IF;
    IF NEW.id<>OLD.id OR NEW.public_id<>OLD.public_id OR NEW.created_at<>OLD.created_at
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR to_jsonb(NEW)->'location_id' IS DISTINCT FROM to_jsonb(OLD)->'location_id'
       OR to_jsonb(NEW)->'code' IS DISTINCT FROM to_jsonb(OLD)->'code' THEN
        RAISE EXCEPTION 'Immutable master identity.' USING ERRCODE='55000';
    END IF;
    IF TG_TABLE_NAME='measurement_units' THEN
        IF NEW.dimension<>OLD.dimension OR NEW.base_factor IS DISTINCT FROM OLD.base_factor
            OR (OLD.code IN ('G','ML','STK') AND NOT NEW.active) THEN
            RAISE EXCEPTION 'Immutable unit semantics.' USING ERRCODE='55000';
        END IF;
    ELSIF TG_TABLE_NAME='foods' THEN
        IF (to_jsonb(NEW)-ARRAY['name','category_id','base_unit_id','density_g_per_ml','piece_weight_g',
            'note','active','allergen_review_status','updated_at','updated_by','row_version'])
            IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['name','category_id','base_unit_id','density_g_per_ml',
            'piece_weight_g','note','active','allergen_review_status','updated_at','updated_by','row_version']) THEN
            RAISE EXCEPTION 'Immutable food origin.' USING ERRCODE='55000';
        END IF;
    END IF;
    RETURN NEW;
END;
$fn$;
CREATE FUNCTION protect_food_proposal() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'Proposal cannot be deleted.' USING ERRCODE='55000';
    END IF;
    IF OLD.status<>'open' OR NEW.status NOT IN ('accepted','rejected') OR
       (to_jsonb(NEW)-ARRAY['food_id','status','decided_by','decided_at','decision_detail','row_version','updated_at','updated_by'])
       IS DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['food_id','status','decided_by','decided_at','decision_detail','row_version','updated_at','updated_by']) OR
       (NEW.food_id IS DISTINCT FROM OLD.food_id AND NOT
         (OLD.food_id IS NULL AND NEW.food_id IS NOT NULL AND NEW.status='accepted')) OR
       (NEW.status='accepted' AND NEW.food_id IS NULL) THEN
        RAISE EXCEPTION 'Immutable proposal source or decision.' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END;
$fn$;

CREATE TRIGGER trg_measurement_units_identity BEFORE UPDATE OR DELETE ON measurement_units
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_measurement_units_no_truncate BEFORE TRUNCATE ON measurement_units
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_measurement_units_version BEFORE UPDATE ON measurement_units
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_food_categories_identity BEFORE UPDATE OR DELETE ON food_categories
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_food_categories_no_truncate BEFORE TRUNCATE ON food_categories
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_food_categories_version BEFORE UPDATE ON food_categories
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_tags_identity BEFORE UPDATE OR DELETE ON tags
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_tags_no_truncate BEFORE TRUNCATE ON tags
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_tags_version BEFORE UPDATE ON tags
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_storage_locations_identity BEFORE UPDATE OR DELETE ON storage_locations
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_storage_locations_no_truncate BEFORE TRUNCATE ON storage_locations
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_storage_locations_version BEFORE UPDATE ON storage_locations
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_foods_identity BEFORE UPDATE OR DELETE ON foods
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_foods_no_truncate BEFORE TRUNCATE ON foods
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_foods_version BEFORE UPDATE ON foods
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_food_data_proposals_identity BEFORE UPDATE OR DELETE ON food_data_proposals
FOR EACH ROW EXECUTE FUNCTION protect_food_proposal();
CREATE TRIGGER trg_food_data_proposals_no_truncate BEFORE TRUNCATE ON food_data_proposals
FOR EACH STATEMENT EXECUTE FUNCTION protect_food_proposal();
CREATE TRIGGER trg_food_data_proposals_version BEFORE UPDATE ON food_data_proposals
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

INSERT INTO measurement_units(code,display_name,dimension,base_factor) VALUES
 ('G','Gramm','mass',1),('KG','Kilogramm','mass',1000),('ML','Milliliter','volume',1),
 ('L','Liter','volume',1000),('EL','Esslöffel (15 ml)','volume',15),
 ('TL','Teelöffel (5 ml)','volume',5),('STK','Stück','count',1),
 ('PORTION','Portion','contextual',NULL),('PRISE','Prise','contextual',NULL);

CREATE FUNCTION require_master_data_actor(p_actor bigint,p_version bigint,p_capability text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v users%ROWTYPE;
BEGIN
    IF current_setting('transaction_isolation')<>'read committed' OR p_actor IS NULL OR p_actor<=0
       OR p_version IS NULL OR p_version<=0 THEN
        RAISE EXCEPTION 'Invalid actor expectation or isolation.' USING ERRCODE='P1901';
    END IF;
    PERFORM set_config('lock_timeout','5s',true);
    PERFORM role_code FROM application_roles ORDER BY role_code FOR SHARE;
    SELECT * INTO v FROM users WHERE id=p_actor FOR SHARE;
    IF NOT FOUND OR v.disabled_at IS NOT NULL THEN
        RAISE EXCEPTION 'Active actor required.' USING ERRCODE='P1902';
    END IF;
    IF v.authz_version<>p_version THEN
        RAISE EXCEPTION 'Stale actor.' USING ERRCODE='P1903';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM user_role_cache r JOIN application_roles a USING(role_code)
        WHERE r.user_id=p_actor AND a.active AND (r.role_code='Cafeteria.Admin' OR
          (p_capability IN ('masterdata.write','recipe.write') AND
            r.role_code IN ('Cafeteria.Editor','Cafeteria.Publisher')) OR
          (p_capability='recipe.import' AND r.role_code='Cafeteria.Publisher'))) THEN
        RAISE EXCEPTION 'Capability denied.' USING ERRCODE='P1902';
    END IF;
END;
$fn$;
CREATE FUNCTION master_location(p_location bigint) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF NOT lock_expected_active_location(p_location) THEN
        RAISE EXCEPTION 'Master data location unavailable.' USING ERRCODE='P1901', DETAIL='master_location';
    END IF;
END;
$fn$;
CREATE FUNCTION master_audit(p_actor bigint,p_version bigint,p_location bigint,p_kind text,
    p_target uuid,p_action text,p_before bigint,p_after bigint,p_details jsonb DEFAULT '{}'::jsonb)
RETURNS void LANGUAGE sql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
 VALUES(p_actor,'masterdata.'||p_action,p_kind,p_target,jsonb_build_object(
    'actor_authz_version',p_version,'location_id',p_location,'action',p_action,
    'row_version_before',p_before,'row_version_after',p_after)||p_details);
$fn$;

CREATE FUNCTION master_payload(p_payload jsonb,p_keys text[]) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload)<>'object' OR
       EXISTS(SELECT 1 FROM jsonb_object_keys(p_payload) k WHERE NOT k=ANY(p_keys)) THEN
        RAISE EXCEPTION 'Invalid command fields.' USING ERRCODE='P1901';
    END IF;
END;
$fn$;
CREATE FUNCTION master_expectation(p_target uuid,p_version bigint) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF p_target IS NULL OR p_version IS NULL OR p_version<=0 THEN
        RAISE EXCEPTION 'Invalid object expectation.' USING ERRCODE='P1901';
    END IF;
END;
$fn$;

CREATE FUNCTION master_food_category_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v food_categories%ROWTYPE; n text; s smallint; a boolean; old_version bigint; affected bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action='create' THEN
        PERFORM master_payload(p_payload,ARRAY['code','name','sort_order']);
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL OR
           p_payload->>'code' IS NULL OR NOT (p_payload->>'code' ~ '^[A-Z][A-Z0-9_]{0,15}$') THEN
            RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901';
        END IF;
        INSERT INTO food_categories(location_id,code,name,created_by,updated_by,sort_order)
        VALUES(p_location,p_payload->>'code',master_text(p_payload->>'name',120),p_actor,p_actor
            ,COALESCE((p_payload->>'sort_order')::smallint,1)) RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM food_categories WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000',DETAIL='stale_object';
        END IF;
        old_version:=v.row_version;
        IF p_action='update' THEN
            PERFORM master_payload(p_payload,ARRAY['name','sort_order']);
            n:=master_text(p_payload->>'name',120);
            s:=COALESCE((p_payload->>'sort_order')::smallint,v.sort_order);
            IF n=v.name AND s=v.sort_order THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            UPDATE food_categories SET name=n,updated_by=p_actor,sort_order=s
             WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action='active' THEN
            PERFORM master_payload(p_payload,ARRAY['active']);
            IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid active state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>'active')::boolean;
            IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
            UPDATE food_categories SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food_category',v.public_id,p_action,old_version,v.row_version,
        jsonb_build_object('fields',p_payload-'code'));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid vocabulary data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_food_category_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_category_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION update_food_category_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_category_mutate('update',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_active_food_category_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_category_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION master_tag_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v tags%ROWTYPE; n text; s smallint; a boolean; old_version bigint; affected bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action='create' THEN
        PERFORM master_payload(p_payload,ARRAY['code','name']);
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL OR
           p_payload->>'code' IS NULL OR NOT (p_payload->>'code' ~ '^[A-Z][A-Z0-9_]{0,15}$') THEN
            RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901';
        END IF;
        INSERT INTO tags(location_id,code,name,created_by,updated_by)
        VALUES(p_location,p_payload->>'code',master_text(p_payload->>'name',120),p_actor,p_actor
            ) RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM tags WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000',DETAIL='stale_object';
        END IF;
        old_version:=v.row_version;
        IF p_action='update' THEN
            PERFORM master_payload(p_payload,ARRAY['name']);
            n:=master_text(p_payload->>'name',120);
            IF n=v.name  THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            UPDATE tags SET name=n,updated_by=p_actor
             WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action='active' THEN
            PERFORM master_payload(p_payload,ARRAY['active']);
            IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid active state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>'active')::boolean;
            IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
            UPDATE tags SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'tag',v.public_id,p_action,old_version,v.row_version,
        jsonb_build_object('fields',p_payload-'code'));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid vocabulary data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_tag_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_tag_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION update_tag_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_tag_mutate('update',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_active_tag_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_tag_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION master_storage_location_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v storage_locations%ROWTYPE; n text; s smallint; a boolean; old_version bigint; affected bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action='create' THEN
        PERFORM master_payload(p_payload,ARRAY['code','name','sort_order']);
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL OR
           p_payload->>'code' IS NULL OR NOT (p_payload->>'code' ~ '^[A-Z][A-Z0-9_]{0,15}$') THEN
            RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901';
        END IF;
        INSERT INTO storage_locations(location_id,code,name,created_by,updated_by,sort_order)
        VALUES(p_location,p_payload->>'code',master_text(p_payload->>'name',120),p_actor,p_actor
            ,COALESCE((p_payload->>'sort_order')::smallint,1)) RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM storage_locations WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000',DETAIL='stale_object';
        END IF;
        old_version:=v.row_version;
        IF p_action='update' THEN
            PERFORM master_payload(p_payload,ARRAY['name','sort_order']);
            n:=master_text(p_payload->>'name',120);
            s:=COALESCE((p_payload->>'sort_order')::smallint,v.sort_order);
            IF n=v.name AND s=v.sort_order THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            UPDATE storage_locations SET name=n,updated_by=p_actor,sort_order=s
             WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action='active' THEN
            PERFORM master_payload(p_payload,ARRAY['active']);
            IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid active state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>'active')::boolean;
            IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
            IF NOT a THEN
                SELECT count(*) INTO affected FROM food_storage_locations WHERE storage_location_id=v.id;
                IF affected>0 THEN
                    RAISE EXCEPTION 'Storage location still assigned.' USING ERRCODE='55000',
                        DETAIL='storage_assignments:'||affected::text;
                END IF;
            END IF;
            UPDATE storage_locations SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'storage_location',v.public_id,p_action,old_version,v.row_version,
        jsonb_build_object('fields',p_payload-'code'));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid vocabulary data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_storage_location_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_storage_location_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION update_storage_location_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_storage_location_mutate('update',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_active_storage_location_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_storage_location_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION master_unit_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v measurement_units%ROWTYPE; n text; a boolean; old_version bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action='create' THEN
        PERFORM master_payload(p_payload,ARRAY['code','display_name','dimension','base_factor']);
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901';
        END IF;
        INSERT INTO measurement_units(code,display_name,dimension,base_factor,created_by,updated_by)
        VALUES(p_payload->>'code',master_text(p_payload->>'display_name',120),p_payload->>'dimension',
            (p_payload->>'base_factor')::numeric,p_actor,p_actor) RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM measurement_units WHERE public_id=p_target FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown unit.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN
            RAISE EXCEPTION 'Stale unit.' USING ERRCODE='55000',DETAIL='stale_object';
        END IF;
        old_version:=v.row_version;
        IF p_action='rename' THEN
            PERFORM master_payload(p_payload,ARRAY['display_name']);
            n:=master_text(p_payload->>'display_name',120);
            IF n=v.display_name THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            UPDATE measurement_units SET display_name=n,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action='active' THEN
            PERFORM master_payload(p_payload,ARRAY['active']);
            IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid active state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>'active')::boolean;
            IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
            UPDATE measurement_units SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'measurement_unit',v.public_id,p_action,old_version,
        v.row_version,jsonb_build_object('fields',p_payload));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid unit data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_unit_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_unit_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION rename_unit_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_unit_mutate('rename',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_active_unit_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_unit_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION master_lock_food_refs(p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE result jsonb:='{}'; v record; ids bigint[]:='{}'; item jsonb; codes text[]; found_count integer;
BEGIN
    IF p_payload ? 'base_unit_code' THEN
        SELECT id,active INTO v FROM measurement_units WHERE code=p_payload->>'base_unit_code' FOR SHARE;
        IF NOT FOUND OR NOT v.active THEN RAISE EXCEPTION 'Unknown active unit.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('base_unit_id',v.id);
    END IF;
    IF nullif(p_payload->>'category_public_id','') IS NOT NULL OR p_payload ? 'category_code' THEN
        SELECT id,active INTO v FROM food_categories WHERE location_id=(p_payload->>'location_id')::bigint
         AND ((p_payload ? 'category_code' AND code=p_payload->>'category_code') OR
              (NOT p_payload ? 'category_code' AND public_id=(p_payload->>'category_public_id')::uuid)) FOR SHARE;
        IF NOT FOUND OR NOT v.active THEN RAISE EXCEPTION 'Unknown active category.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('category_id',v.id);
    END IF;
    IF p_payload ? 'tags' THEN
        IF jsonb_typeof(p_payload->'tags')<>'array' OR jsonb_array_length(p_payload->'tags')>64 THEN
            RAISE EXCEPTION 'Invalid tags.' USING ERRCODE='P1901';
        END IF;
        ids:='{}';
        FOR v IN SELECT id,active FROM tags WHERE location_id=(p_payload->>'location_id')::bigint
          AND public_id IN (SELECT value::uuid FROM jsonb_array_elements_text(p_payload->'tags'))
          ORDER BY id FOR SHARE LOOP
            IF NOT v.active THEN RAISE EXCEPTION 'Archived tag.' USING ERRCODE='P1901'; END IF;
            ids:=array_append(ids,v.id);
        END LOOP;
        SELECT count(DISTINCT value) INTO found_count FROM jsonb_array_elements_text(p_payload->'tags');
        IF cardinality(ids)<>found_count THEN RAISE EXCEPTION 'Unknown tag.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('tags',ids);
    END IF;
    IF p_payload ? 'storage_locations' THEN
        IF jsonb_typeof(p_payload->'storage_locations')<>'array' OR jsonb_array_length(p_payload->'storage_locations')>64 THEN
            RAISE EXCEPTION 'Invalid storage locations.' USING ERRCODE='P1901';
        END IF;
        ids:='{}';
        FOR v IN SELECT id,active FROM storage_locations WHERE location_id=(p_payload->>'location_id')::bigint
          AND public_id IN (SELECT value::uuid FROM jsonb_array_elements_text(p_payload->'storage_locations'))
          ORDER BY id FOR SHARE LOOP
            IF NOT v.active THEN RAISE EXCEPTION 'Archived storage location.' USING ERRCODE='P1901'; END IF;
            ids:=array_append(ids,v.id);
        END LOOP;
        SELECT count(DISTINCT value) INTO found_count FROM jsonb_array_elements_text(p_payload->'storage_locations');
        IF cardinality(ids)<>found_count THEN RAISE EXCEPTION 'Unknown storage location.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('storage_locations',ids);
    END IF;
    IF p_payload ? 'allergens' THEN
        IF jsonb_typeof(p_payload->'allergens')<>'array' OR jsonb_array_length(p_payload->'allergens')>64 THEN
            RAISE EXCEPTION 'Invalid allergens.' USING ERRCODE='P1901';
        END IF;
        FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'allergens') LOOP
            PERFORM master_payload(item,ARRAY['code','presence']);
            IF item->>'code' IS NULL OR item->>'presence' IS NULL OR
               item->>'presence' NOT IN ('contains','may_contain') THEN
                RAISE EXCEPTION 'Invalid allergen declaration.' USING ERRCODE='P1901';
            END IF;
        END LOOP;
        IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'allergens') x
                  GROUP BY x->>'code' HAVING count(DISTINCT x->>'presence')>1) THEN
            RAISE EXCEPTION 'Conflicting allergen presence.' USING ERRCODE='P1901';
        END IF;
        SELECT array_agg(DISTINCT x->>'code') INTO codes FROM jsonb_array_elements(p_payload->'allergens') x;
        ids:='{}';
        FOR v IN SELECT id,active FROM allergens WHERE code=ANY(codes) ORDER BY id FOR SHARE LOOP
            IF NOT v.active THEN RAISE EXCEPTION 'Archived allergen.' USING ERRCODE='P1901'; END IF;
            ids:=array_append(ids,v.id);
        END LOOP;
        IF cardinality(ids)<>COALESCE(cardinality(codes),0) THEN RAISE EXCEPTION 'Unknown allergen.' USING ERRCODE='P1901'; END IF;
        SELECT COALESCE(jsonb_agg(jsonb_build_object('id',a.id,'presence',x->>'presence') ORDER BY a.id),'[]')
          INTO item FROM (SELECT DISTINCT value AS x FROM jsonb_array_elements(p_payload->'allergens')) pairs
          JOIN allergens a ON a.code=x->>'code';
        result:=result||jsonb_build_object('allergens',item);
    END IF;
    IF p_payload ? 'labels' THEN
        IF jsonb_typeof(p_payload->'labels')<>'array' OR jsonb_array_length(p_payload->'labels')>64 THEN
            RAISE EXCEPTION 'Invalid labels.' USING ERRCODE='P1901';
        END IF;
        SELECT array_agg(DISTINCT value) INTO codes FROM jsonb_array_elements_text(p_payload->'labels');
        ids:='{}';
        FOR v IN SELECT id,active FROM dietary_labels WHERE code=ANY(codes) ORDER BY id FOR SHARE LOOP
            IF NOT v.active THEN RAISE EXCEPTION 'Archived label.' USING ERRCODE='P1901'; END IF;
            ids:=array_append(ids,v.id);
        END LOOP;
        IF cardinality(ids)<>COALESCE(cardinality(codes),0) THEN RAISE EXCEPTION 'Unknown label.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('labels',ids);
    END IF;
    RETURN result;
END;
$fn$;
CREATE FUNCTION master_food_links(p_id bigint) RETURNS jsonb
LANGUAGE sql STABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT jsonb_build_object(
  'tags',COALESCE((SELECT jsonb_agg(tag_id ORDER BY tag_id) FROM food_tags WHERE food_id=p_id),'[]'),
  'storage_locations',COALESCE((SELECT jsonb_agg(storage_location_id ORDER BY storage_location_id)
      FROM food_storage_locations WHERE food_id=p_id),'[]'),
  'labels',COALESCE((SELECT jsonb_agg(label_id ORDER BY label_id) FROM food_labels WHERE food_id=p_id),'[]'),
  'allergens',COALESCE((SELECT jsonb_agg(jsonb_build_object('id',allergen_id,'presence',presence) ORDER BY allergen_id)
      FROM food_allergens WHERE food_id=p_id),'[]'));
$fn$;
CREATE FUNCTION master_replace_food_links(p_id bigint,p_location bigint,p_links jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF p_links ? 'tags' THEN
        DELETE FROM food_tags WHERE food_id=p_id;
        INSERT INTO food_tags(location_id,food_id,tag_id)
          SELECT p_location,p_id,value::bigint FROM jsonb_array_elements_text(p_links->'tags') ORDER BY value::bigint;
    END IF;
    IF p_links ? 'storage_locations' THEN
        DELETE FROM food_storage_locations WHERE food_id=p_id;
        INSERT INTO food_storage_locations(location_id,food_id,storage_location_id)
          SELECT p_location,p_id,value::bigint FROM jsonb_array_elements_text(p_links->'storage_locations') ORDER BY value::bigint;
    END IF;
    IF p_links ? 'allergens' THEN
        DELETE FROM food_allergens WHERE food_id=p_id;
        INSERT INTO food_allergens(location_id,food_id,allergen_id,presence)
          SELECT p_location,p_id,(value->>'id')::smallint,value->>'presence'
          FROM jsonb_array_elements(p_links->'allergens') ORDER BY (value->>'id')::smallint;
    END IF;
    IF p_links ? 'labels' THEN
        DELETE FROM food_labels WHERE food_id=p_id;
        INSERT INTO food_labels(location_id,food_id,label_id)
          SELECT p_location,p_id,value::smallint FROM jsonb_array_elements_text(p_links->'labels') ORDER BY value::smallint;
    END IF;
END;
$fn$;
CREATE FUNCTION master_food_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v foods%ROWTYPE; previous foods%ROWTYPE; refs jsonb; links jsonb; old_version bigint; a boolean; review text;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action IN ('create','update') THEN
        PERFORM master_payload(p_payload,ARRAY['name','category_public_id','base_unit_code',
           'density_g_per_ml','piece_weight_g','note','source_kind','source_reference','source_url','source_note','fetched_at']);
        IF p_action='update' AND p_payload ?| ARRAY['source_kind','source_reference','source_url','source_note','fetched_at'] THEN
            RAISE EXCEPTION 'Origin is immutable.' USING ERRCODE='P1901';
        END IF;
        IF p_payload->>'base_unit_code' IS NULL THEN RAISE EXCEPTION 'Unit required.' USING ERRCODE='P1901'; END IF;
    ELSIF p_action='metadata' THEN
        PERFORM master_payload(p_payload,ARRAY['allergens','labels']);
        IF NOT p_payload ?& ARRAY['allergens','labels'] THEN RAISE EXCEPTION 'Metadata required.' USING ERRCODE='P1901'; END IF;
    ELSIF p_action='tags' THEN PERFORM master_payload(p_payload,ARRAY['tags']);
    ELSIF p_action='storage_locations' THEN PERFORM master_payload(p_payload,ARRAY['storage_locations']);
    ELSIF p_action='review' THEN PERFORM master_payload(p_payload,ARRAY['checked']);
    ELSIF p_action='active' THEN PERFORM master_payload(p_payload,ARRAY['active']);
    ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
    END IF;
    refs:=master_lock_food_refs(p_payload||jsonb_build_object('location_id',p_location));
    IF p_action='create' THEN
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL THEN RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901'; END IF;
        INSERT INTO foods(location_id,name,category_id,base_unit_id,density_g_per_ml,piece_weight_g,note,
            source_kind,source_reference,source_url,source_note,fetched_at,created_by,updated_by)
        VALUES(p_location,master_text(p_payload->>'name',120),(refs->>'category_id')::bigint,
            (refs->>'base_unit_id')::bigint,(p_payload->>'density_g_per_ml')::numeric,(p_payload->>'piece_weight_g')::numeric,
            master_text(COALESCE(p_payload->>'note',''),500,false),COALESCE(p_payload->>'source_kind','manual'),
            master_text(p_payload->>'source_reference',200,false),master_text(p_payload->>'source_url',2048,false),
            master_text(p_payload->>'source_note',500,false),(p_payload->>'fetched_at')::timestamptz,p_actor,p_actor)
        RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM foods WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown food.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN RAISE EXCEPTION 'Stale food.' USING ERRCODE='55000',DETAIL='stale_object'; END IF;
        previous:=v; old_version:=v.row_version;
        IF p_action='update' THEN
            v.name:=master_text(p_payload->>'name',120); v.category_id:=(refs->>'category_id')::bigint;
            v.base_unit_id:=(refs->>'base_unit_id')::bigint;
            v.density_g_per_ml:=(p_payload->>'density_g_per_ml')::numeric;
            v.piece_weight_g:=(p_payload->>'piece_weight_g')::numeric;
            v.note:=master_text(COALESCE(p_payload->>'note',''),500,false);
            IF v IS NOT DISTINCT FROM previous THEN RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version); END IF;
            UPDATE foods SET name=v.name,category_id=v.category_id,base_unit_id=v.base_unit_id,
              density_g_per_ml=v.density_g_per_ml,piece_weight_g=v.piece_weight_g,note=v.note,updated_by=p_actor
              WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action IN ('metadata','tags','storage_locations') THEN
            IF p_action<>'metadata' AND NOT refs ? p_action THEN RAISE EXCEPTION 'Missing assignments.' USING ERRCODE='P1901'; END IF;
            links:=master_food_links(v.id);
            IF NOT EXISTS(SELECT 1 FROM jsonb_each(refs) e WHERE e.value IS DISTINCT FROM links->e.key) THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            review:=CASE WHEN refs ? 'allergens' AND refs->'allergens' IS DISTINCT FROM links->'allergens'
              THEN 'not_checked' ELSE v.allergen_review_status END;
            PERFORM master_replace_food_links(v.id,p_location,refs);
            UPDATE foods SET updated_by=p_actor,allergen_review_status=review WHERE id=v.id RETURNING * INTO v;
        ELSE
            IF jsonb_typeof(p_payload->CASE WHEN p_action='review' THEN 'checked' ELSE 'active' END) IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>CASE WHEN p_action='review' THEN 'checked' ELSE 'active' END)::boolean;
            IF p_action='active' THEN
                IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
                UPDATE foods SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
            ELSE
                review:=CASE WHEN a THEN 'checked' ELSE 'not_checked' END;
                IF review=v.allergen_review_status THEN
                    RAISE EXCEPTION 'State already set.' USING ERRCODE='55000';
                END IF;
                UPDATE foods SET allergen_review_status=review,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
            END IF;
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food',v.public_id,p_action,old_version,v.row_version,
        jsonb_build_object('fields',p_payload));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation OR invalid_datetime_format THEN
    RAISE EXCEPTION 'Invalid food data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_food_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION update_food_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('update',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_food_active_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION replace_food_tags_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('tags',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION replace_food_metadata_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('metadata',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_food_allergen_review_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('review',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION replace_food_storage_locations_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('storage_locations',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION create_proposal_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE food bigint; v food_data_proposals%ROWTYPE;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    PERFORM master_payload(p_payload,ARRAY['source','source_reference','source_url','source_note','fetched_at','payload','food_public_id']);
    IF p_target IS NOT NULL OR p_target_version IS NOT NULL THEN RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901'; END IF;
    IF p_payload->>'food_public_id' IS NOT NULL THEN
        SELECT id INTO food FROM foods WHERE public_id=(p_payload->>'food_public_id')::uuid
         AND location_id=p_location FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown food.' USING ERRCODE='22023'; END IF;
    END IF;
    INSERT INTO food_data_proposals(location_id,food_id,source,source_reference,source_url,source_note,
        fetched_at,payload,created_by,updated_by)
    VALUES(p_location,food,p_payload->>'source',master_text(p_payload->>'source_reference',200),
        master_text(p_payload->>'source_url',2048,false),master_text(p_payload->>'source_note',500,false),
        (p_payload->>'fetched_at')::timestamptz,p_payload->'payload',p_actor,p_actor) RETURNING * INTO v;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food_proposal',v.public_id,'create',NULL,v.row_version,
        jsonb_build_object('source',v.source,'source_reference',v.source_reference));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation OR invalid_datetime_format THEN
    RAISE EXCEPTION 'Invalid proposal data.' USING ERRCODE='P1901';
END;
$fn$;
CREATE FUNCTION accept_proposal_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v food_data_proposals%ROWTYPE; original food_data_proposals%ROWTYPE; f foods%ROWTYPE;
    before_version bigint; refs jsonb; selected jsonb:='{}'; links jsonb; merged jsonb;
    field text; item jsonb; current_item jsonb; adopted text[]:='{}'; unchanged text[]:='{}';
    unsupported text[]; fields text[]; value numeric; category bigint; changed boolean:=false;
    decision jsonb; stamp timestamptz;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'recipe.import');
    PERFORM master_location(p_location);
    PERFORM master_expectation(p_target,p_target_version);
    PERFORM master_payload(p_payload,ARRAY['food_public_id','food_row_version','fields']);
    IF jsonb_typeof(p_payload->'fields') IS DISTINCT FROM 'array' OR
       jsonb_array_length(p_payload->'fields') NOT BETWEEN 1 AND 64 THEN
        RAISE EXCEPTION 'Select proposal fields.' USING ERRCODE='P1901';
    END IF;
    SELECT array_agg(DISTINCT x ORDER BY x) INTO fields FROM jsonb_array_elements_text(p_payload->'fields') x;
    IF EXISTS(SELECT 1 FROM unnest(fields) x WHERE x IS NULL OR
      x NOT IN ('density_g_per_ml','piece_weight_g','category_code','allergens','labels')) THEN
        RAISE EXCEPTION 'Unsupported selection.' USING ERRCODE='P1901';
    END IF;
    SELECT * INTO original FROM food_data_proposals WHERE public_id=p_target AND location_id=p_location;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unknown proposal.' USING ERRCODE='22023'; END IF;
    FOREACH field IN ARRAY fields LOOP
        IF NOT original.payload ? field THEN RAISE EXCEPTION 'Missing proposal field.' USING ERRCODE='P1901'; END IF;
        selected:=selected||jsonb_build_object(field,original.payload->field);
    END LOOP;
    refs:=master_lock_food_refs(selected||jsonb_build_object('location_id',p_location));
    PERFORM master_expectation((p_payload->>'food_public_id')::uuid,(p_payload->>'food_row_version')::bigint);
    SELECT * INTO f FROM foods WHERE public_id=(p_payload->>'food_public_id')::uuid AND location_id=p_location FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unknown food.' USING ERRCODE='22023'; END IF;
    IF f.row_version<>(p_payload->>'food_row_version')::bigint THEN
        RAISE EXCEPTION 'Stale food.' USING ERRCODE='55000',DETAIL='stale_object';
    END IF;
    before_version:=f.row_version;
    SELECT * INTO v FROM food_data_proposals WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
    IF v.row_version<>p_target_version OR v.status<>'open' THEN
        RAISE EXCEPTION 'Stale proposal.' USING ERRCODE='55000',DETAIL='stale_object';
    END IF;
    IF v.food_id IS NOT NULL AND v.food_id<>f.id THEN RAISE EXCEPTION 'Different proposal target.' USING ERRCODE='55000'; END IF;
    links:=master_food_links(f.id); merged:=links;
    FOREACH field IN ARRAY fields LOOP
        changed:=false;
        IF field IN ('density_g_per_ml','piece_weight_g') THEN
            value:=(selected->>field)::numeric;
            IF NOT master_factor(value) THEN RAISE EXCEPTION 'Invalid factor.' USING ERRCODE='P1901'; END IF;
            IF (to_jsonb(f)->>field)::numeric IS NULL THEN
                IF field='density_g_per_ml' THEN f.density_g_per_ml:=value; ELSE f.piece_weight_g:=value; END IF;
                changed:=true;
            ELSIF (to_jsonb(f)->>field)::numeric<>value THEN
                RAISE EXCEPTION 'Confirmed factor differs.' USING ERRCODE='55000';
            END IF;
        ELSIF field='category_code' THEN
            category:=(refs->>'category_id')::bigint;
            IF f.category_id IS NULL THEN f.category_id:=category; changed:=true;
            ELSIF f.category_id<>category THEN RAISE EXCEPTION 'Confirmed category differs.' USING ERRCODE='55000'; END IF;
        ELSIF field='labels' THEN
            FOR item IN SELECT x FROM jsonb_array_elements(refs->'labels') x LOOP
                IF NOT merged->'labels' @> jsonb_build_array(item) THEN
                    merged:=jsonb_set(merged,'{labels}',(merged->'labels')||jsonb_build_array(item)); changed:=true;
                END IF;
            END LOOP;
        ELSE
            FOR item IN SELECT x FROM jsonb_array_elements(refs->'allergens') x LOOP
                SELECT x INTO current_item FROM jsonb_array_elements(merged->'allergens') x WHERE x->'id'=item->'id';
                IF FOUND AND current_item->'presence'<>item->'presence' THEN
                    RAISE EXCEPTION 'Confirmed allergen presence differs.' USING ERRCODE='55000';
                ELSIF NOT FOUND THEN
                    merged:=jsonb_set(merged,'{allergens}',(merged->'allergens')||jsonb_build_array(item)); changed:=true;
                END IF;
            END LOOP;
            IF changed THEN f.allergen_review_status:='not_checked'; END IF;
        END IF;
        IF changed THEN adopted:=array_append(adopted,field); ELSE unchanged:=array_append(unchanged,field); END IF;
    END LOOP;
    IF cardinality(adopted)>0 THEN
        PERFORM master_replace_food_links(f.id,p_location,
          (CASE WHEN 'labels'=ANY(adopted) THEN jsonb_build_object('labels',merged->'labels') ELSE '{}'::jsonb END)||
          (CASE WHEN 'allergens'=ANY(adopted) THEN jsonb_build_object('allergens',merged->'allergens') ELSE '{}'::jsonb END));
        UPDATE foods SET density_g_per_ml=f.density_g_per_ml,piece_weight_g=f.piece_weight_g,
          category_id=f.category_id,allergen_review_status=f.allergen_review_status,updated_by=p_actor
          WHERE id=f.id RETURNING row_version INTO f.row_version;
    END IF;
    SELECT COALESCE(array_agg(k ORDER BY k),'{}') INTO unsupported FROM jsonb_object_keys(v.payload) k
      WHERE k NOT IN ('density_g_per_ml','piece_weight_g','category_code','allergens','labels');
    stamp:=clock_timestamp();
    decision:=jsonb_build_object('status','accepted','decided_at',stamp,'adopted',adopted,'unchanged',unchanged,
      'not_supported',unsupported,'food_public_id',f.public_id,'food_row_version_before',before_version,
      'food_row_version_after',f.row_version);
    UPDATE food_data_proposals SET food_id=f.id,status='accepted',decided_by=p_actor,decided_at=stamp,
      decision_detail=decision,updated_by=p_actor WHERE id=v.id;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food_proposal',v.public_id,'accept',
      v.row_version,v.row_version+1,decision||jsonb_build_object('source_reference',v.source_reference));
    RETURN decision;
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid proposal decision.' USING ERRCODE='P1901';
END;
$fn$;
CREATE FUNCTION reject_proposal_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v food_data_proposals%ROWTYPE; decision jsonb; stamp timestamptz; food uuid;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'recipe.import');
    PERFORM master_location(p_location);
    PERFORM master_expectation(p_target,p_target_version);
    PERFORM master_payload(p_payload,ARRAY['reason']);
    PERFORM master_text(p_payload->>'reason',500,false);
    SELECT * INTO v FROM food_data_proposals WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unknown proposal.' USING ERRCODE='22023'; END IF;
    IF v.row_version<>p_target_version OR v.status<>'open' THEN
        RAISE EXCEPTION 'Stale proposal.' USING ERRCODE='55000',DETAIL='stale_object';
    END IF;
    SELECT public_id INTO food FROM foods WHERE id=v.food_id AND location_id=p_location;
    stamp:=clock_timestamp();
    decision:=jsonb_build_object('status','rejected','decided_at',stamp,'adopted','[]'::jsonb,'unchanged','[]'::jsonb,
      'not_supported','[]'::jsonb,'food_public_id',food,'food_row_version_before',NULL,'food_row_version_after',NULL);
    UPDATE food_data_proposals SET status='rejected',decided_by=p_actor,decided_at=stamp,
      decision_detail=decision,updated_by=p_actor WHERE id=v.id;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food_proposal',v.public_id,'reject',
      v.row_version,v.row_version+1,decision||jsonb_build_object('reason',master_text(p_payload->>'reason',500,false)));
    RETURN decision;
END;
$fn$;

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


CREATE FUNCTION recipe_text_v22(p_value text,p_max integer,p_required boolean DEFAULT true)
RETURNS text LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v text;
BEGIN
 IF p_value IS NULL THEN
  IF p_required THEN RAISE EXCEPTION 'Missing text.' USING ERRCODE='P1901'; END IF;
  RETURN NULL;
 END IF;
 v:=normalize(replace(replace(p_value,E'\r\n',E'\n'),E'\r',E'\n'),NFC);
 PERFORM master_text(replace(v,E'\n',''),2147483647,false);
 v:=regexp_replace(v,U&'^[\000A \00A0\1680\2000-\200A\2028\2029\202F\205F\3000]+|[\000A \00A0\1680\2000-\200A\2028\2029\202F\205F\3000]+$','','g');
 IF length(v)>p_max OR (p_required AND v='') THEN
  RAISE EXCEPTION 'Invalid text length.' USING ERRCODE='P1901';
 END IF;
 RETURN v;
END;$fn$;

CREATE TABLE IF NOT EXISTS recipes (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
 location_id bigint NOT NULL REFERENCES locations(id), UNIQUE(location_id,id),
 row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 created_by bigint NOT NULL REFERENCES users(id), updated_by bigint NOT NULL REFERENCES users(id),
 title text NOT NULL CHECK(title=master_text(title,120)),
 description text CHECK(description=recipe_text_v22(description,2000,false)),
 servings numeric NOT NULL CHECK(master_quantity(servings)),
 servings_unit_id bigint NOT NULL REFERENCES measurement_units(id) ON DELETE RESTRICT,
 prep_minutes integer CHECK(prep_minutes BETWEEN 0 AND 10080),
 cook_minutes integer CHECK(cook_minutes BETWEEN 0 AND 10080),
 source_kind text NOT NULL CHECK(source_kind IN ('manual','url','file_import','ai_assisted')),
 source_reference text CHECK(source_reference=master_text(source_reference,200,false)),
 source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
 source_note text CHECK(source_note=master_text(source_note,500,false)), fetched_at timestamptz,
 active boolean NOT NULL DEFAULT true,
 CHECK(source_kind='manual' OR (nullif(source_reference,'') IS NOT NULL AND fetched_at IS NOT NULL)),
 CHECK(source_kind<>'url' OR nullif(source_url,'') IS NOT NULL),
 CHECK(source_kind NOT IN ('file_import','ai_assisted') OR nullif(source_note,'') IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS recipe_assets (
 location_id bigint NOT NULL REFERENCES locations(id),
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 image_data bytea NOT NULL CHECK(octet_length(image_data) BETWEEN 1 AND 1048576),
 content_type text NOT NULL CHECK(content_type IN ('image/png','image/jpeg')),
 width integer NOT NULL CHECK(width BETWEEN 1 AND 10000),
 height integer NOT NULL CHECK(height BETWEEN 1 AND 10000),
 created_by bigint NOT NULL REFERENCES users(id),created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(location_id,sha256),
 CHECK(sha256=encode(public.digest(image_data,'sha256'),'hex')),
 CHECK((content_type='image/png' AND substring(image_data FROM 1 FOR 8)=decode('89504e470d0a1a0a','hex'))
    OR (content_type='image/jpeg' AND substring(image_data FROM 1 FOR 3)=decode('ffd8ff','hex')))
);
CREATE TABLE IF NOT EXISTS recipe_ingredients (
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,sort_order smallint NOT NULL CHECK(sort_order BETWEEN 1 AND 64),
 line_public_id uuid NOT NULL DEFAULT gen_random_uuid(),UNIQUE(recipe_id,line_public_id),
 group_label text CHECK(group_label=master_text(group_label,120,false)),
 ingredient_text text NOT NULL CHECK(ingredient_text=master_text(ingredient_text,500)),
 food_id bigint, quantity numeric CHECK(quantity IS NULL OR master_quantity(quantity)),unit_id bigint REFERENCES measurement_units(id) ON DELETE RESTRICT,
 note text CHECK(note=master_text(note,500,false)),
 source_kind text NOT NULL CHECK(source_kind IN ('manual','url','file_import','ai_assisted')),
 source_reference text CHECK(source_reference=master_text(source_reference,200,false)),fetched_at timestamptz,
 PRIMARY KEY(recipe_id,sort_order),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT,
 CHECK((quantity IS NULL)=(unit_id IS NULL)),
 CHECK(source_kind='manual' OR (nullif(source_reference,'') IS NOT NULL AND fetched_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS recipe_steps (
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,step_number smallint NOT NULL CHECK(step_number BETWEEN 1 AND 64),
 instruction text NOT NULL CHECK(instruction=recipe_text_v22(instruction,8000)),
 duration_minutes integer CHECK(duration_minutes BETWEEN 0 AND 10080),image_sha256 text,
 PRIMARY KEY(recipe_id,step_number),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,image_sha256) REFERENCES recipe_assets(location_id,sha256) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS recipe_images (
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,sort_order smallint NOT NULL CHECK(sort_order BETWEEN 1 AND 64),
 sha256 text NOT NULL,caption text CHECK(caption=master_text(caption,500,false)),
 source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
 source_license text CHECK(source_license=master_text(source_license,500,false)),fetched_at timestamptz,
 PRIMARY KEY(recipe_id,sort_order),
 UNIQUE(recipe_id,sha256),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,sha256) REFERENCES recipe_assets(location_id,sha256) ON DELETE RESTRICT,
 CHECK(source_url IS NULL OR (nullif(source_license,'') IS NOT NULL AND fetched_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS recipe_tags (
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,tag_id bigint NOT NULL,
 PRIMARY KEY(recipe_id,tag_id),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,tag_id) REFERENCES tags(location_id,id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS recipe_revisions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,revision_number bigint NOT NULL CHECK(revision_number>0),
 snapshot_json jsonb NOT NULL CHECK(jsonb_typeof(snapshot_json)='object'),
 content_hash_sha256 text NOT NULL CHECK(content_hash_sha256 ~ '^[0-9a-f]{64}$'),
 created_by bigint NOT NULL REFERENCES users(id),created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(location_id,id),UNIQUE(recipe_id,revision_number),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 CHECK(content_hash_sha256=encode(public.digest(convert_to(snapshot_json::text,'UTF8'),'sha256'),'hex'))
);
CREATE TABLE IF NOT EXISTS cookbooks (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
 location_id bigint NOT NULL REFERENCES locations(id),UNIQUE(location_id,id),
 name text NOT NULL CHECK(name=master_text(name,120)),description text CHECK(description=recipe_text_v22(description,2000,false)),
 active boolean NOT NULL DEFAULT true,row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_by bigint NOT NULL REFERENCES users(id),updated_by bigint NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS cookbook_recipes (
 location_id bigint NOT NULL,cookbook_id bigint NOT NULL,recipe_id bigint NOT NULL,
 sort_order smallint NOT NULL CHECK(sort_order BETWEEN 1 AND 9999),
 PRIMARY KEY(cookbook_id,sort_order),UNIQUE(cookbook_id,recipe_id),
 FOREIGN KEY(location_id,cookbook_id) REFERENCES cookbooks(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT
);
CREATE FUNCTION recipe_protect_v22() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
 IF TG_OP IN ('DELETE','TRUNCATE') OR TG_TABLE_NAME IN ('recipe_assets','recipe_revisions') THEN
  RAISE EXCEPTION 'Immutable recipe history.' USING ERRCODE='55000';
 END IF;
 IF NEW.location_id<>OLD.location_id THEN RAISE EXCEPTION 'Immutable scope.' USING ERRCODE='55000'; END IF;
 IF TG_TABLE_NAME='recipes' AND (to_jsonb(NEW)->'source_kind',to_jsonb(NEW)->'source_reference',
 to_jsonb(NEW)->'source_url',to_jsonb(NEW)->'source_note',to_jsonb(NEW)->'fetched_at') IS DISTINCT FROM
 (to_jsonb(OLD)->'source_kind',to_jsonb(OLD)->'source_reference',to_jsonb(OLD)->'source_url',
 to_jsonb(OLD)->'source_note',to_jsonb(OLD)->'fetched_at') THEN
  RAISE EXCEPTION 'Immutable provenance.' USING ERRCODE='55000';
 END IF;
 RETURN NEW;
END;$fn$;
CREATE TRIGGER recipes_protect BEFORE UPDATE OR DELETE ON recipes FOR EACH ROW EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipes_version BEFORE UPDATE ON recipes FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();
CREATE TRIGGER recipes_no_truncate BEFORE TRUNCATE ON recipes FOR EACH STATEMENT EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER cookbooks_protect BEFORE UPDATE OR DELETE ON cookbooks FOR EACH ROW EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER cookbooks_version BEFORE UPDATE ON cookbooks FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();
CREATE TRIGGER cookbooks_no_truncate BEFORE TRUNCATE ON cookbooks FOR EACH STATEMENT EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipe_assets_immutable BEFORE UPDATE OR DELETE ON recipe_assets FOR EACH ROW EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipe_assets_no_truncate BEFORE TRUNCATE ON recipe_assets FOR EACH STATEMENT EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipe_revisions_immutable BEFORE UPDATE OR DELETE ON recipe_revisions FOR EACH ROW EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipe_revisions_no_truncate BEFORE TRUNCATE ON recipe_revisions FOR EACH STATEMENT EXECUTE FUNCTION recipe_protect_v22();

CREATE FUNCTION recipe_payload_v22(p_id bigint) RETURNS jsonb LANGUAGE sql STABLE
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT jsonb_build_object(
 'title',r.title,'description',r.description,'servings',trim_scale(r.servings)::text,'servings_unit_code',u.code,
 'prep_minutes',r.prep_minutes,'cook_minutes',r.cook_minutes,
 'source',jsonb_build_object('kind',r.source_kind,'reference',r.source_reference,'url',r.source_url,'note',r.source_note,'fetched_at',r.fetched_at),
 'ingredients',COALESCE((SELECT jsonb_agg(jsonb_build_object('line_public_id',i.line_public_id,'group_label',i.group_label,'ingredient_text',i.ingredient_text,
 'food_public_id',f.public_id,'quantity',trim_scale(i.quantity)::text,'unit_code',iu.code,'note',i.note,
 'source_kind',i.source_kind,'source_reference',i.source_reference,'fetched_at',i.fetched_at) ORDER BY i.sort_order)
 FROM recipe_ingredients i LEFT JOIN foods f ON f.id=i.food_id AND f.location_id=i.location_id
 LEFT JOIN measurement_units iu ON iu.id=i.unit_id WHERE i.recipe_id=r.id AND i.location_id=r.location_id),'[]'::jsonb),
 'steps',COALESCE((SELECT jsonb_agg(jsonb_build_object('instruction',s.instruction,'duration_minutes',s.duration_minutes,
 'image_sha256',s.image_sha256) ORDER BY s.step_number) FROM recipe_steps s WHERE s.recipe_id=r.id AND s.location_id=r.location_id),'[]'::jsonb),
 'tag_public_ids',COALESCE((SELECT jsonb_agg(t.public_id ORDER BY t.public_id) FROM recipe_tags rt JOIN tags t ON t.id=rt.tag_id
 AND t.location_id=rt.location_id WHERE rt.recipe_id=r.id AND rt.location_id=r.location_id),'[]'::jsonb),
 'images',COALESCE((SELECT jsonb_agg(jsonb_build_object('sha256',i.sha256,'caption',i.caption,'source_url',i.source_url,
 'source_license',i.source_license,'fetched_at',i.fetched_at) ORDER BY i.sort_order)
 FROM recipe_images i WHERE i.recipe_id=r.id AND i.location_id=r.location_id),'[]'::jsonb))
 FROM recipes r JOIN measurement_units u ON u.id=r.servings_unit_id WHERE r.id=p_id;
$fn$;
CREATE FUNCTION recipe_fields_v22(p_value jsonb,p_keys text[]) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE field record;
BEGIN
 PERFORM master_payload(p_value,p_keys);
 FOR field IN SELECT key,value FROM jsonb_each(p_value) LOOP
  IF field.value='null'::jsonb THEN CONTINUE; END IF;
  IF field.key IN ('ingredients','steps','tag_public_ids','images','recipes') THEN
   IF jsonb_typeof(field.value)<>'array' THEN RAISE EXCEPTION 'Array required.' USING ERRCODE='P1901'; END IF;
  ELSIF field.key='source' THEN
   IF jsonb_typeof(field.value)<>'object' THEN RAISE EXCEPTION 'Source required.' USING ERRCODE='P1901'; END IF;
  ELSIF field.key='active' THEN
   IF jsonb_typeof(field.value)<>'boolean' THEN RAISE EXCEPTION 'Boolean required.' USING ERRCODE='P1901'; END IF;
  ELSIF field.key IN ('prep_minutes','cook_minutes','duration_minutes','width','height') THEN
   IF jsonb_typeof(field.value)<>'number' OR field.value::text !~ '^[0-9]+$' THEN
    RAISE EXCEPTION 'Integer required.' USING ERRCODE='P1901';
   END IF;
  ELSIF jsonb_typeof(field.value)<>'string' THEN RAISE EXCEPTION 'Text required.' USING ERRCODE='P1901';
  END IF;
  IF field.key='fetched_at' AND (field.value#>>'{}') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
   RAISE EXCEPTION 'Timestamp requires offset.' USING ERRCODE='P1901';
  END IF;
 END LOOP;
 IF (SELECT count(*) FROM jsonb_object_keys(p_value))<>cardinality(p_keys) THEN
  RAISE EXCEPTION 'Missing fields.' USING ERRCODE='P1901';
 END IF;
END;$fn$;
CREATE FUNCTION recipe_snapshot_v22(p_id bigint) RETURNS jsonb LANGUAGE sql STABLE
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT jsonb_build_object('schema_version',1,'recipe',recipe_payload_v22(r.id),
 'calculation',jsonb_build_object('precision',50,'rounding','ROUND_HALF_UP','quantity_places',6,
 'bases',jsonb_build_object('mass','G','volume','ML','count','STK'),'contextual','same-code-only'),
 'units',COALESCE((SELECT jsonb_agg(jsonb_build_object('public_id',u.public_id,'code',u.code,
 'display_name',u.display_name,'dimension',u.dimension,'base_factor',trim_scale(u.base_factor)::text) ORDER BY u.id)
 FROM measurement_units u WHERE u.id=r.servings_unit_id OR u.id IN
 (SELECT unit_id FROM recipe_ingredients WHERE recipe_id=r.id AND location_id=r.location_id)),'[]'::jsonb),
 'foods',COALESCE((SELECT jsonb_agg(jsonb_build_object('public_id',f.public_id,'name',f.name,'row_version',f.row_version,
 'density_g_per_ml',trim_scale(f.density_g_per_ml)::text,'piece_weight_g',trim_scale(f.piece_weight_g)::text,
 'source_kind',f.source_kind,'source_reference',f.source_reference,'source_url',f.source_url,'source_note',f.source_note,
 'fetched_at',f.fetched_at,'factor_decisions',COALESCE((SELECT jsonb_agg(p.decision_detail ORDER BY p.id)
 FROM food_data_proposals p WHERE p.food_id=f.id AND p.location_id=f.location_id AND p.status='accepted'),'[]'::jsonb))
 ORDER BY f.id) FROM foods f WHERE f.location_id=r.location_id AND f.id IN
 (SELECT food_id FROM recipe_ingredients WHERE recipe_id=r.id AND location_id=r.location_id)),'[]'::jsonb))
 FROM recipes r WHERE r.id=p_id;
$fn$;

CREATE FUNCTION recipe_refs_v22(p_location bigint,p_id bigint,p_payload jsonb) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE item jsonb; ref record; field_name text;
BEGIN
 PERFORM recipe_fields_v22(p_payload,ARRAY['title','description','servings','servings_unit_code','prep_minutes','cook_minutes','source','ingredients','steps','tag_public_ids','images']);
 FOREACH field_name IN ARRAY ARRAY['ingredients','steps','tag_public_ids','images'] LOOP
  IF jsonb_typeof(p_payload->field_name)<>'array' OR jsonb_array_length(p_payload->field_name)>64 THEN
   RAISE EXCEPTION 'Invalid recipe list.' USING ERRCODE='P1901';
  END IF;
 END LOOP;
 PERFORM recipe_fields_v22(p_payload->'source',ARRAY['kind','reference','url','note','fetched_at']);
 FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'ingredients') LOOP
  PERFORM recipe_fields_v22(item,ARRAY['line_public_id','group_label','ingredient_text','food_public_id','quantity','unit_code','note','source_kind','source_reference','fetched_at']);
  IF (item->>'quantity' IS NULL)<>(item->>'unit_code' IS NULL) THEN
   RAISE EXCEPTION 'Quantity requires unit.' USING ERRCODE='P1901';
  END IF;
 END LOOP;
 FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'steps') LOOP
  PERFORM recipe_fields_v22(item,ARRAY['instruction','duration_minutes','image_sha256']);
 END LOOP;
 FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'images') LOOP
  PERFORM recipe_fields_v22(item,ARRAY['sha256','caption','source_url','source_license','fetched_at']);
 END LOOP;
 -- Lock existing and requested references before the recipe aggregate.
 FOR ref IN SELECT * FROM measurement_units WHERE code=p_payload->>'servings_unit_code'
 OR code IN (SELECT value->>'unit_code' FROM jsonb_array_elements(p_payload->'ingredients'))
 OR id IN (SELECT servings_unit_id FROM recipes WHERE id=p_id)
 OR id IN (SELECT unit_id FROM recipe_ingredients WHERE recipe_id=p_id) ORDER BY id FOR SHARE LOOP
  IF NOT ref.active AND NOT EXISTS(SELECT 1 FROM recipes WHERE id=p_id AND servings_unit_id=ref.id)
   AND NOT EXISTS(SELECT 1 FROM recipe_ingredients WHERE recipe_id=p_id AND unit_id=ref.id) THEN
   RAISE EXCEPTION 'Archived unit.' USING ERRCODE='55000';
  END IF;
 END LOOP;
 IF NOT EXISTS(SELECT 1 FROM measurement_units WHERE code=p_payload->>'servings_unit_code') OR
 EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'ingredients') i WHERE i->>'unit_code' IS NOT NULL
 AND NOT EXISTS(SELECT 1 FROM measurement_units WHERE code=i->>'unit_code')) THEN
  RAISE EXCEPTION 'Unknown unit.' USING ERRCODE='22023';
 END IF;
 FOR ref IN SELECT * FROM tags WHERE location_id=p_location AND (public_id IN
 (SELECT value::text::uuid FROM jsonb_array_elements_text(p_payload->'tag_public_ids'))
 OR id IN(SELECT tag_id FROM recipe_tags WHERE recipe_id=p_id)) ORDER BY id FOR SHARE LOOP
  IF NOT ref.active AND NOT EXISTS(SELECT 1 FROM recipe_tags WHERE recipe_id=p_id AND tag_id=ref.id) THEN
   RAISE EXCEPTION 'Archived tag.' USING ERRCODE='55000';
  END IF;
 END LOOP;
 IF (SELECT count(DISTINCT value) FROM jsonb_array_elements_text(p_payload->'tag_public_ids'))<>jsonb_array_length(p_payload->'tag_public_ids')
 OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(p_payload->'tag_public_ids') i WHERE NOT EXISTS
 (SELECT 1 FROM tags WHERE public_id=i.value::uuid AND location_id=p_location)) THEN
  RAISE EXCEPTION 'Unknown or duplicate tag.' USING ERRCODE='22023';
 END IF;
 FOR ref IN SELECT * FROM foods WHERE location_id=p_location AND (public_id IN
 (SELECT (value->>'food_public_id')::uuid FROM jsonb_array_elements(p_payload->'ingredients'))
 OR id IN(SELECT food_id FROM recipe_ingredients WHERE recipe_id=p_id)) ORDER BY id FOR SHARE LOOP
  IF NOT ref.active AND NOT EXISTS(SELECT 1 FROM recipe_ingredients WHERE recipe_id=p_id AND food_id=ref.id) THEN
   RAISE EXCEPTION 'Archived food.' USING ERRCODE='55000';
  END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'ingredients') i WHERE i->>'food_public_id' IS NOT NULL
 AND NOT EXISTS(SELECT 1 FROM foods WHERE public_id=(i->>'food_public_id')::uuid AND location_id=p_location)) THEN
  RAISE EXCEPTION 'Unknown food.' USING ERRCODE='22023';
 END IF;
END;$fn$;

CREATE FUNCTION recipe_location_v22(p_location bigint) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
 IF p_location IS NULL OR p_location<=0 THEN RAISE EXCEPTION 'Original location required.' USING ERRCODE='P1901'; END IF;
 IF NOT lock_expected_active_location(p_location) THEN
  IF (SELECT count(*) FROM locations WHERE active)<>1 THEN
   RAISE EXCEPTION 'Ambiguous active location.' USING ERRCODE='P1904';
  END IF;
  RAISE EXCEPTION 'Original location changed.' USING ERRCODE='55000';
 END IF;
END;$fn$;

CREATE FUNCTION recipe_write_v22(p_action text,p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE recipe recipes%ROWTYPE; original jsonb; item jsonb; origin recipe_ingredients%ROWTYPE;
 audit_before jsonb; audit_after jsonb;
 version_before bigint; new_snapshot jsonb; revision recipe_revisions%ROWTYPE; digest_value text;
 n integer; line_ids uuid[]:=ARRAY[]::uuid[]; line_id uuid; ingredient_ids jsonb:='[]'::jsonb;
BEGIN
 PERFORM require_master_data_actor(p_actor,p_authz,'recipe.write');
 PERFORM recipe_location_v22(p_location);
 IF p_action='create' THEN
  IF p_target IS NOT NULL OR p_version IS NOT NULL THEN RAISE EXCEPTION 'Unexpected target.' USING ERRCODE='P1901'; END IF;
 ELSE
  PERFORM master_expectation(p_target,p_version);
  SELECT * INTO recipe FROM recipes WHERE public_id=p_target AND location_id=p_location;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown recipe.' USING ERRCODE='22023'; END IF;
 END IF;
 IF p_action IN ('create','update') THEN
  PERFORM recipe_refs_v22(p_location,recipe.id,p_payload);
 ELSIF p_action='freeze' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY[]::text[]);
  PERFORM recipe_refs_v22(p_location,recipe.id,recipe_payload_v22(recipe.id));
 ELSIF p_action='active' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['active']);
  IF jsonb_typeof(p_payload->'active')<>'boolean' THEN RAISE EXCEPTION 'Boolean required.' USING ERRCODE='P1901'; END IF;
 ELSIF p_action='image' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['sha256','data','content_type','width','height','caption','source_url','source_license','fetched_at']);
 ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
 END IF;
 IF p_action<>'create' THEN
  SELECT * INTO recipe FROM recipes WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
  IF recipe.row_version<>p_version THEN RAISE EXCEPTION 'Stale recipe.' USING ERRCODE='55000'; END IF;
  IF NOT recipe.active AND NOT (p_action='active' AND (p_payload->>'active')::boolean) THEN
   RAISE EXCEPTION 'Archived recipe.' USING ERRCODE='55000';
  END IF;
  original:=recipe_payload_v22(recipe.id);
  audit_before:=original||jsonb_build_object('active',recipe.active);
  version_before:=recipe.row_version;
 ELSE version_before:=0;
 END IF;
 IF p_action IN ('create','update') THEN
  IF p_action='update' AND original->'source' IS DISTINCT FROM p_payload->'source' THEN
   -- Compare timestamp instants, not equivalent JSON timestamp spellings.
   IF (original->'source'-'fetched_at') IS DISTINCT FROM (p_payload->'source'-'fetched_at') OR
    (original->'source'->>'fetched_at')::timestamptz IS DISTINCT FROM (p_payload->'source'->>'fetched_at')::timestamptz THEN
    RAISE EXCEPTION 'Immutable provenance.' USING ERRCODE='55000';
   END IF;
  END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'ingredients') LOOP
   line_id:=(item->>'line_public_id')::uuid;
   IF line_id IS NULL THEN line_id:=gen_random_uuid();
   ELSE
    SELECT * INTO origin FROM recipe_ingredients WHERE recipe_id=recipe.id AND line_public_id=line_id;
    IF NOT FOUND OR line_id=ANY(line_ids) THEN RAISE EXCEPTION 'Unknown or duplicate ingredient identity.' USING ERRCODE='P1901'; END IF;
    IF (origin.source_kind,origin.source_reference,origin.fetched_at) IS DISTINCT FROM
     (item->>'source_kind',item->>'source_reference',(item->>'fetched_at')::timestamptz) THEN
     RAISE EXCEPTION 'Immutable ingredient provenance.' USING ERRCODE='55000';
    END IF;
   END IF;
   line_ids:=array_append(line_ids,line_id);
   ingredient_ids:=ingredient_ids||jsonb_build_array(item||jsonb_build_object('line_public_id',line_id));
  END LOOP;
  p_payload:=jsonb_set(p_payload,'{ingredients}',ingredient_ids);
  -- An archived reference may remain only on its original logical association.
  IF EXISTS(SELECT 1 FROM measurement_units u WHERE NOT u.active AND u.code=p_payload->>'servings_unit_code'
   AND u.id IS DISTINCT FROM recipe.servings_unit_id) OR EXISTS(
   SELECT 1 FROM jsonb_array_elements(p_payload->'ingredients') i
    LEFT JOIN recipe_ingredients old ON old.recipe_id=recipe.id AND old.line_public_id=(i->>'line_public_id')::uuid
    LEFT JOIN measurement_units u ON u.code=i->>'unit_code'
    LEFT JOIN foods f ON f.public_id=(i->>'food_public_id')::uuid AND f.location_id=p_location
   WHERE (NOT u.active AND u.id IS DISTINCT FROM old.unit_id) OR (NOT f.active AND f.id IS DISTINCT FROM old.food_id)) THEN
   RAISE EXCEPTION 'New archived association.' USING ERRCODE='55000';
  END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'images') i
   GROUP BY i->>'sha256' HAVING count(*)>1) THEN
   RAISE EXCEPTION 'Duplicate image identity.' USING ERRCODE='P1901';
  END IF;
  -- Existing assets must already belong to this recipe, including its immutable history.
  IF EXISTS(SELECT 1 FROM (
    SELECT value->>'sha256' AS sha FROM jsonb_array_elements(p_payload->'images')
    UNION SELECT value->>'image_sha256' FROM jsonb_array_elements(p_payload->'steps')) requested
   WHERE sha IS NOT NULL AND NOT EXISTS(SELECT 1 FROM recipe_images WHERE recipe_id=recipe.id AND sha256=sha)
   AND NOT EXISTS(SELECT 1 FROM recipe_steps WHERE recipe_id=recipe.id AND image_sha256=sha)
   AND NOT EXISTS(SELECT 1 FROM recipe_revisions h WHERE h.recipe_id=recipe.id AND
    (EXISTS(SELECT 1 FROM jsonb_array_elements(h.snapshot_json->'recipe'->'images') i WHERE i->>'sha256'=sha)
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(h.snapshot_json->'recipe'->'steps') s WHERE s->>'image_sha256'=sha)))) THEN
   RAISE EXCEPTION 'Unknown recipe asset.' USING ERRCODE='22023';
  END IF;
  -- A step reference needs its provenance in this self-contained aggregate.
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'steps') s
   WHERE s->>'image_sha256' IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM jsonb_array_elements(p_payload->'images') i WHERE i->>'sha256'=s->>'image_sha256')) THEN
   RAISE EXCEPTION 'Step image requires its provenance.' USING ERRCODE='55000';
  END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'images') LOOP
   IF (SELECT count(*)=0 OR bool_or(
     (image->>'source_url',image->>'source_license',(image->>'fetched_at')::timestamptz) IS DISTINCT FROM
     (item->>'source_url',item->>'source_license',(item->>'fetched_at')::timestamptz)) FROM (
    SELECT value AS image FROM jsonb_array_elements(original->'images')
    UNION ALL SELECT image FROM recipe_revisions h,
     LATERAL jsonb_array_elements(h.snapshot_json->'recipe'->'images') image WHERE h.recipe_id=recipe.id) origins
    WHERE image->>'sha256'=item->>'sha256') THEN
    RAISE EXCEPTION 'Immutable image provenance.' USING ERRCODE='55000';
   END IF;
  END LOOP;
  IF p_action='create' THEN
   INSERT INTO recipes(location_id,title,description,servings,servings_unit_id,prep_minutes,cook_minutes,
    source_kind,source_reference,source_url,source_note,fetched_at,created_by,updated_by)
   VALUES(p_location,master_text(p_payload->>'title',120),recipe_text_v22(p_payload->>'description',2000,false),
    (p_payload->>'servings')::numeric,(SELECT id FROM measurement_units WHERE code=p_payload->>'servings_unit_code'),
    (p_payload->>'prep_minutes')::integer,(p_payload->>'cook_minutes')::integer,p_payload->'source'->>'kind',
    p_payload->'source'->>'reference',p_payload->'source'->>'url',p_payload->'source'->>'note',
    (p_payload->'source'->>'fetched_at')::timestamptz,p_actor,p_actor) RETURNING * INTO recipe;
  END IF;
  DELETE FROM recipe_ingredients WHERE recipe_id=recipe.id;
  INSERT INTO recipe_ingredients(location_id,recipe_id,sort_order,line_public_id,group_label,ingredient_text,food_id,quantity,unit_id,note,source_kind,source_reference,fetched_at)
   SELECT p_location,recipe.id,j.n,(i->>'line_public_id')::uuid,master_text(i->>'group_label',120,false),
   master_text(i->>'ingredient_text',500),(SELECT id FROM foods WHERE public_id=(i->>'food_public_id')::uuid AND location_id=p_location),
   (i->>'quantity')::numeric,(SELECT id FROM measurement_units WHERE code=i->>'unit_code'),master_text(i->>'note',500,false),
   i->>'source_kind',master_text(i->>'source_reference',200,false),(i->>'fetched_at')::timestamptz
   FROM jsonb_array_elements(p_payload->'ingredients') WITH ORDINALITY j(i,n);
  DELETE FROM recipe_steps WHERE recipe_id=recipe.id;
  INSERT INTO recipe_steps(location_id,recipe_id,step_number,instruction,duration_minutes,image_sha256)
   SELECT p_location,recipe.id,j.n,recipe_text_v22(i->>'instruction',8000),(i->>'duration_minutes')::integer,i->>'image_sha256'
   FROM jsonb_array_elements(p_payload->'steps') WITH ORDINALITY j(i,n);
  DELETE FROM recipe_images WHERE recipe_id=recipe.id;
  INSERT INTO recipe_images(location_id,recipe_id,sort_order,sha256,caption,source_url,source_license,fetched_at)
   SELECT p_location,recipe.id,j.n,i->>'sha256',master_text(i->>'caption',500,false),master_text(i->>'source_url',2048,false),
   master_text(i->>'source_license',500,false),(i->>'fetched_at')::timestamptz
   FROM jsonb_array_elements(p_payload->'images') WITH ORDINALITY j(i,n);
  DELETE FROM recipe_tags WHERE recipe_id=recipe.id;
  INSERT INTO recipe_tags(location_id,recipe_id,tag_id) SELECT p_location,recipe.id,t.id FROM tags t
   WHERE t.location_id=p_location AND t.public_id IN(SELECT value::uuid FROM jsonb_array_elements_text(p_payload->'tag_public_ids'));
  IF p_action='update' THEN
   IF original=recipe_payload_v22(recipe.id) AND
    (recipe.title,recipe.description,recipe.servings,recipe.servings_unit_id,recipe.prep_minutes,recipe.cook_minutes) IS NOT DISTINCT FROM
    (master_text(p_payload->>'title',120),recipe_text_v22(p_payload->>'description',2000,false),(p_payload->>'servings')::numeric,
    (SELECT id FROM measurement_units WHERE code=p_payload->>'servings_unit_code'),(p_payload->>'prep_minutes')::integer,(p_payload->>'cook_minutes')::integer) THEN
    RETURN jsonb_build_object('public_id',recipe.public_id,'row_version',recipe.row_version);
   END IF;
   UPDATE recipes SET title=master_text(p_payload->>'title',120),description=recipe_text_v22(p_payload->>'description',2000,false),
    servings=(p_payload->>'servings')::numeric,servings_unit_id=(SELECT id FROM measurement_units WHERE code=p_payload->>'servings_unit_code'),
    prep_minutes=(p_payload->>'prep_minutes')::integer,cook_minutes=(p_payload->>'cook_minutes')::integer,updated_by=p_actor
    WHERE id=recipe.id RETURNING * INTO recipe;
  END IF;
 ELSIF p_action='active' THEN
  IF recipe.active=(p_payload->>'active')::boolean THEN RAISE EXCEPTION 'No state transition.' USING ERRCODE='55000'; END IF;
  UPDATE recipes SET active=(p_payload->>'active')::boolean,updated_by=p_actor WHERE id=recipe.id RETURNING * INTO recipe;
 ELSIF p_action='freeze' THEN
  new_snapshot:=recipe_snapshot_v22(recipe.id);
  digest_value:=encode(public.digest(convert_to(new_snapshot::text,'UTF8'),'sha256'),'hex');
  SELECT * INTO revision FROM recipe_revisions WHERE recipe_id=recipe.id ORDER BY revision_number DESC LIMIT 1;
  IF FOUND AND revision.snapshot_json=new_snapshot THEN RAISE EXCEPTION 'Identical revision.' USING ERRCODE='55000'; END IF;
  INSERT INTO recipe_revisions(location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
   VALUES(p_location,recipe.id,COALESCE(revision.revision_number,0)+1,new_snapshot,digest_value,p_actor) RETURNING * INTO revision;
  UPDATE recipes SET updated_by=p_actor WHERE id=recipe.id RETURNING * INTO recipe;
 ELSE
  -- Identity and provenance belong to this recipe, not the globally deduplicated bytes.
  IF EXISTS(SELECT 1 FROM (
   SELECT value AS image FROM jsonb_array_elements(original->'images')
   UNION ALL SELECT image FROM recipe_revisions h,
    LATERAL jsonb_array_elements(h.snapshot_json->'recipe'->'images') image WHERE h.recipe_id=recipe.id) origins
   WHERE image->>'sha256'=p_payload->>'sha256' AND
    (image->>'source_url',image->>'source_license',(image->>'fetched_at')::timestamptz) IS DISTINCT FROM
    (master_text(p_payload->>'source_url',2048,false),master_text(p_payload->>'source_license',500,false),
     (p_payload->>'fetched_at')::timestamptz)) THEN
   RAISE EXCEPTION 'Immutable image provenance.' USING ERRCODE='55000';
  END IF;
  SELECT value INTO item FROM jsonb_array_elements(original->'images')
   WHERE value->>'sha256'=p_payload->>'sha256';
  IF FOUND THEN
   IF item->>'caption' IS DISTINCT FROM master_text(p_payload->>'caption',500,false) THEN
    RAISE EXCEPTION 'Edit existing caption through the aggregate.' USING ERRCODE='55000';
   END IF;
   RETURN jsonb_build_object('public_id',recipe.public_id,'row_version',recipe.row_version);
  END IF;
  SELECT count(*) INTO n FROM recipe_images WHERE recipe_id=recipe.id;
  IF n>=64 THEN RAISE EXCEPTION 'Image limit.' USING ERRCODE='P1901'; END IF;
  INSERT INTO recipe_assets(location_id,sha256,image_data,content_type,width,height,created_by)
   VALUES(p_location,p_payload->>'sha256',decode(p_payload->>'data','base64'),p_payload->>'content_type',
   (p_payload->>'width')::integer,(p_payload->>'height')::integer,p_actor) ON CONFLICT DO NOTHING;
  INSERT INTO recipe_images(location_id,recipe_id,sort_order,sha256,caption,source_url,source_license,fetched_at)
   VALUES(p_location,recipe.id,n+1,p_payload->>'sha256',master_text(p_payload->>'caption',500,false),
   master_text(p_payload->>'source_url',2048,false),master_text(p_payload->>'source_license',500,false),(p_payload->>'fetched_at')::timestamptz);
  UPDATE recipes SET updated_by=p_actor WHERE id=recipe.id RETURNING * INTO recipe;
 END IF;
 audit_after:=recipe_payload_v22(recipe.id)||jsonb_build_object('active',recipe.active);
 INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
 VALUES(p_actor,'recipe.'||p_action,'recipe',recipe.public_id,jsonb_build_object('actor_authz_version',p_authz,
  'changes',COALESCE((SELECT jsonb_object_agg(key,jsonb_build_object('before',audit_before->key,'after',value))
   FROM jsonb_each(audit_after) WHERE audit_before->key IS DISTINCT FROM value),'{}'::jsonb),
  'location_id',p_location,'row_version_before',version_before,'row_version_after',recipe.row_version,
  'ingredient_line_ids',line_ids,'ingredients_before',original->'ingredients',
  'ingredients_after',recipe_payload_v22(recipe.id)->'ingredients',
  'images_before',original->'images','images_after',recipe_payload_v22(recipe.id)->'images',
  'revision_public_id',revision.public_id,'content_hash_sha256',digest_value));
 IF p_action='freeze' THEN
  RETURN jsonb_build_object('public_id',revision.public_id,'recipe_public_id',recipe.public_id,
   'revision_number',revision.revision_number,'recipe_row_version',recipe.row_version,'content_hash_sha256',digest_value);
 END IF;
 RETURN jsonb_build_object('public_id',recipe.public_id,'row_version',recipe.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation OR invalid_datetime_format OR datetime_field_overflow THEN
 RAISE EXCEPTION 'Invalid recipe input.' USING ERRCODE='P1901';
END;$fn$;

CREATE FUNCTION recipe_cookbook_v22(p_action text,p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE book cookbooks%ROWTYPE; ref record; ids bigint[]; before_ids bigint[]; name_value text; description_value text; version_before bigint;
 audit_before jsonb; audit_after jsonb;
BEGIN
 PERFORM require_master_data_actor(p_actor,p_authz,'recipe.write');
 PERFORM recipe_location_v22(p_location);
 IF p_action='assign' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['recipes']);
  IF jsonb_typeof(p_payload->'recipes')<>'array' OR jsonb_array_length(p_payload->'recipes')>64 OR
  (SELECT count(DISTINCT value) FROM jsonb_array_elements_text(p_payload->'recipes'))<>jsonb_array_length(p_payload->'recipes') THEN
   RAISE EXCEPTION 'Invalid recipe list.' USING ERRCODE='P1901';
  END IF;
  FOR ref IN SELECT * FROM recipes WHERE location_id=p_location AND public_id IN
  (SELECT value::uuid FROM jsonb_array_elements_text(p_payload->'recipes')) ORDER BY id FOR SHARE LOOP
   IF NOT ref.active AND NOT EXISTS(SELECT 1 FROM cookbook_recipes cr JOIN cookbooks c ON c.id=cr.cookbook_id
    WHERE c.public_id=p_target AND c.location_id=p_location AND cr.recipe_id=ref.id) THEN
    RAISE EXCEPTION 'Archived recipe.' USING ERRCODE='55000';
   END IF;
  END LOOP;
  SELECT array_agg(r.id ORDER BY j.n) INTO ids FROM jsonb_array_elements_text(p_payload->'recipes') WITH ORDINALITY j(value,n)
   JOIN recipes r ON r.public_id=j.value::uuid AND r.location_id=p_location;
  ids:=COALESCE(ids,ARRAY[]::bigint[]);
  IF cardinality(ids)<>jsonb_array_length(p_payload->'recipes') THEN RAISE EXCEPTION 'Unknown recipe.' USING ERRCODE='22023'; END IF;
 ELSIF p_action IN ('create','update') THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['name','description']);
  name_value:=master_text(p_payload->>'name',120);
  description_value:=recipe_text_v22(p_payload->>'description',2000,false);
 ELSIF p_action='active' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['active']);
  IF jsonb_typeof(p_payload->'active')<>'boolean' THEN RAISE EXCEPTION 'Boolean required.' USING ERRCODE='P1901'; END IF;
 ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
 END IF;
 IF p_action='create' THEN
  IF p_target IS NOT NULL OR p_version IS NOT NULL THEN RAISE EXCEPTION 'Unexpected target.' USING ERRCODE='P1901'; END IF;
  INSERT INTO cookbooks(location_id,name,description,created_by,updated_by)
  VALUES(p_location,name_value,description_value,p_actor,p_actor) RETURNING * INTO book;
  version_before:=0;
 ELSE
  PERFORM master_expectation(p_target,p_version);
  SELECT * INTO book FROM cookbooks WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown cookbook.' USING ERRCODE='22023'; END IF;
  IF book.row_version<>p_version THEN RAISE EXCEPTION 'Stale cookbook.' USING ERRCODE='55000'; END IF;
  version_before:=book.row_version;
  audit_before:=jsonb_build_object('name',book.name,'description',book.description,'active',book.active,
   'recipe_public_ids',COALESCE((SELECT jsonb_agg(r.public_id ORDER BY cr.sort_order)
    FROM cookbook_recipes cr JOIN recipes r ON r.id=cr.recipe_id WHERE cr.cookbook_id=book.id),'[]'::jsonb));
  IF NOT book.active AND NOT (p_action='active' AND (p_payload->>'active')::boolean) THEN
   RAISE EXCEPTION 'Archived cookbook.' USING ERRCODE='55000';
  END IF;
  IF p_action='active' THEN
   IF book.active=(p_payload->>'active')::boolean THEN RAISE EXCEPTION 'No state transition.' USING ERRCODE='55000'; END IF;
   UPDATE cookbooks SET active=(p_payload->>'active')::boolean,updated_by=p_actor WHERE id=book.id RETURNING * INTO book;
  ELSIF p_action='update' THEN
   IF (book.name,book.description) IS NOT DISTINCT FROM (name_value,description_value) THEN
    RETURN jsonb_build_object('public_id',book.public_id,'row_version',book.row_version);
   END IF;
   UPDATE cookbooks SET name=name_value,description=description_value,updated_by=p_actor WHERE id=book.id RETURNING * INTO book;
  ELSE
   SELECT COALESCE(array_agg(recipe_id ORDER BY sort_order),ARRAY[]::bigint[]) INTO before_ids FROM cookbook_recipes WHERE cookbook_id=book.id;
   IF ids=before_ids THEN RETURN jsonb_build_object('public_id',book.public_id,'row_version',book.row_version); END IF;
   DELETE FROM cookbook_recipes WHERE cookbook_id=book.id;
   INSERT INTO cookbook_recipes(location_id,cookbook_id,recipe_id,sort_order)
    SELECT p_location,book.id,value,n FROM unnest(ids) WITH ORDINALITY j(value,n);
   UPDATE cookbooks SET updated_by=p_actor WHERE id=book.id RETURNING * INTO book;
  END IF;
 END IF;
 audit_after:=jsonb_build_object('name',book.name,'description',book.description,'active',book.active,
  'recipe_public_ids',COALESCE((SELECT jsonb_agg(r.public_id ORDER BY cr.sort_order)
   FROM cookbook_recipes cr JOIN recipes r ON r.id=cr.recipe_id WHERE cr.cookbook_id=book.id),'[]'::jsonb));
 INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
 VALUES(p_actor,'recipe.cookbook_'||p_action,'cookbook',book.public_id,jsonb_build_object('actor_authz_version',p_authz,
 'changes',COALESCE((SELECT jsonb_object_agg(key,jsonb_build_object('before',audit_before->key,'after',value))
  FROM jsonb_each(audit_after) WHERE audit_before->key IS DISTINCT FROM value),'{}'::jsonb),
 'location_id',p_location,'row_version_before',version_before,'row_version_after',book.row_version));
 RETURN jsonb_build_object('public_id',book.public_id,'row_version',book.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
 RAISE EXCEPTION 'Invalid cookbook input.' USING ERRCODE='P1901';
END;$fn$;

CREATE FUNCTION create_recipe_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('create',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION update_recipe_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('update',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION set_recipe_active_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('active',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION freeze_recipe_revision_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('freeze',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION add_recipe_image_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('image',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION create_cookbook_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_cookbook_v22('create',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION update_cookbook_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_cookbook_v22('update',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION set_cookbook_active_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_cookbook_v22('active',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION replace_cookbook_recipes_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_cookbook_v22('assign',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
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

COMMIT;
