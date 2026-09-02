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
    v_week_start date;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.menu_week_id IS DISTINCT FROM OLD.menu_week_id THEN
        RAISE EXCEPTION 'Ein Service kann nicht in eine andere Woche verschoben werden.' USING ERRCODE = '23514';
    END IF;

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
            'sharednote', 'weekend', 'weekstart', 'servicestate'
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
        ELSIF jsonb_array_length(v_day->'services') <> 0 THEN
            RAISE EXCEPTION 'Cafeteria-Snapshot darf am Wochenende keine Services enthalten.' USING ERRCODE = '23514';
        END IF;

        FOR v_service IN SELECT value FROM jsonb_array_elements(v_day->'services')
        LOOP
            v_state := COALESCE(NULLIF(v_service->>'service_state', ''), 'open');
            IF v_state NOT IN ('open', 'closed', 'holiday', 'company_holiday') THEN
                RAISE EXCEPTION 'service_state muss open, closed, holiday oder company_holiday sein.' USING ERRCODE = '23514';
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
    SELECT authz_version, disabled_at
      INTO v_authz_version, v_disabled_at
      FROM users
     WHERE id = p_actor_user_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Rückzugsakteur ist nicht aktiv oder nicht zur Publikation berechtigt.'
            USING ERRCODE = '42501';
    END IF;
    PERFORM 1 FROM user_role_cache WHERE user_id = p_actor_user_id FOR UPDATE;
    SELECT withdrawn_at
      INTO v_withdrawn_at
      FROM publication_revisions
     WHERE id = p_revision_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Publikationsrevision.' USING ERRCODE = 'P0002';
    END IF;
    IF v_withdrawn_at IS NOT NULL THEN
        RAISE EXCEPTION 'Publikationsrevision wurde bereits zurückgezogen.' USING ERRCODE = '55000';
    END IF;
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

    BEGIN
        INSERT INTO auth_capability_nonces(nonce, actor_user_id, revision_id)
        VALUES (decode(v_nonce_hex, 'hex'), v_actor_id, v_token_revision);
    EXCEPTION WHEN unique_violation THEN
        RAISE EXCEPTION 'Capability-Nonce wurde bereits verwendet.' USING ERRCODE = '42501';
    END;

    SELECT authz_version, disabled_at
      INTO v_authz_version, v_disabled_at
      FROM users
     WHERE id = v_actor_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;
    PERFORM 1 FROM user_role_cache WHERE user_id = v_actor_id FOR UPDATE;
    SELECT withdrawn_at
      INTO v_existing_withdrawal
      FROM publication_revisions
     WHERE id = p_revision_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Publikationsrevision.' USING ERRCODE = 'P0002';
    END IF;
    IF v_existing_withdrawal IS NOT NULL THEN
        RAISE EXCEPTION 'Publikationsrevision wurde bereits zurückgezogen.' USING ERRCODE = '55000';
    END IF;
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

COMMIT;
