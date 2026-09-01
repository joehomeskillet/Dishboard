-- Schema v5: lokale Anmeldedaten, exakte Snapshots und unveränderliche Publikationen.
BEGIN;

SET search_path TO cafeteria, public;

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_auth_provider_check;
ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_check;
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS authz_version bigint NOT NULL DEFAULT 1 CHECK (authz_version > 0),
    ADD CONSTRAINT users_auth_provider_check
        CHECK (auth_provider IN ('entra', 'local', 'system', 'demo')),
    ADD CONSTRAINT users_provider_identity_check CHECK (
        (auth_provider = 'entra' AND entra_tenant_id IS NOT NULL AND entra_object_id IS NOT NULL)
        OR
        (auth_provider IN ('local', 'system', 'demo')
         AND entra_tenant_id IS NULL AND entra_object_id IS NULL AND entra_subject_id IS NULL)
    );

ALTER TABLE user_role_cache
    DROP CONSTRAINT IF EXISTS user_role_cache_source_check;
ALTER TABLE user_role_cache
    ADD CONSTRAINT user_role_cache_source_check
        CHECK (source IN ('entra_token', 'local', 'demo'));

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
    IF TG_OP = 'UPDATE' AND NEW.user_id IS DISTINCT FROM OLD.user_id THEN
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
            IF lower(k) IN (
                    'price', 'prices', 'preis', 'preise', 'internal_rappen', 'external_rappen',
                    'preis_intern', 'preis_extern', 'currency', 'chf', 'rappen',
                    'cost', 'costs', 'amount', 'amounts', 'kosten', 'betrag', 'fee', 'tarif', 'tariff', 'charge'
               )
               OR lower(k) ~ '(^|_)(price|preis|cost|amount|kosten|betrag)(_|$)'
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
            '([01]?[0-9]|2[0-3])[.:]([1-5][0-9]|0[1-9])( Uhr)?',
            '',
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
     WHERE w.id = NEW.menu_week_id;

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
    IF NEW.withdrawn_at IS NULL OR NEW.withdrawal_reason IS NULL OR btrim(NEW.withdrawal_reason) = '' THEN
        RAISE EXCEPTION 'Nur ein Rückzug ist als Änderung einer Publikationsrevision zulässig.' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION record_publication_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO publication_lifecycle_events(revision_id, event_type, actor_user_id, occurred_at)
        VALUES (NEW.id, 'activated', NEW.published_by, NEW.published_at);
    ELSIF TG_OP = 'UPDATE' AND OLD.withdrawn_at IS NULL AND NEW.withdrawn_at IS NOT NULL THEN
        INSERT INTO publication_lifecycle_events(revision_id, event_type, reason, actor_user_id, occurred_at)
        VALUES (NEW.id, 'withdrawn', NEW.withdrawal_reason, NEW.published_by, NEW.withdrawn_at);
    END IF;
    RETURN NULL;
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

DROP TRIGGER IF EXISTS trg_publication_validate ON publication_revisions;

ALTER TABLE publication_revisions
    ADD COLUMN IF NOT EXISTS profile_id smallint REFERENCES offer_profiles(id),
    ADD COLUMN IF NOT EXISTS location_id bigint REFERENCES locations(id),
    ADD COLUMN IF NOT EXISTS week_start date;

UPDATE publication_revisions r
SET profile_id = w.profile_id,
    location_id = w.location_id,
    week_start = w.week_start
FROM menu_weeks w
WHERE w.id = r.menu_week_id
  AND (r.profile_id IS NULL OR r.location_id IS NULL OR r.week_start IS NULL);

ALTER TABLE publication_revisions
    ALTER COLUMN profile_id SET NOT NULL,
    ALTER COLUMN location_id SET NOT NULL,
    ALTER COLUMN week_start SET NOT NULL;

ALTER TABLE publication_revisions
    DROP CONSTRAINT IF EXISTS publication_revisions_menu_week_id_fkey;
ALTER TABLE publication_revisions
    ADD CONSTRAINT publication_revisions_menu_week_id_fkey
        FOREIGN KEY (menu_week_id) REFERENCES menu_weeks(id) ON DELETE RESTRICT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_one_active_per_frozen_identity
    ON publication_revisions(profile_id, location_id, week_start)
    WHERE withdrawn_at IS NULL;

UPDATE publication_revisions r
SET withdrawn_at = clock_timestamp(),
    withdrawal_reason = 'v4-Entwurf darf nicht öffentlich bleiben'
FROM menu_weeks w
WHERE w.id = r.menu_week_id
  AND w.workflow_state IS DISTINCT FROM 'published'
  AND r.withdrawn_at IS NULL;

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

INSERT INTO publication_lifecycle_events(revision_id, event_type, actor_user_id, occurred_at)
SELECT id, 'activated', published_by, published_at
FROM publication_revisions
WHERE NOT EXISTS (
    SELECT 1 FROM publication_lifecycle_events e
    WHERE e.revision_id = publication_revisions.id AND e.event_type = 'activated'
);

INSERT INTO publication_lifecycle_events(revision_id, event_type, reason, actor_user_id, occurred_at)
SELECT id, 'withdrawn', withdrawal_reason, published_by, withdrawn_at
FROM publication_revisions
WHERE withdrawn_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM publication_lifecycle_events e
      WHERE e.revision_id = publication_revisions.id AND e.event_type = 'withdrawn'
  );

DROP TRIGGER IF EXISTS trg_local_credentials_validate ON local_credentials;
CREATE TRIGGER trg_local_credentials_validate BEFORE INSERT OR UPDATE ON local_credentials
FOR EACH ROW EXECUTE FUNCTION validate_local_credential();

DROP TRIGGER IF EXISTS trg_local_credentials_updated_at ON local_credentials;
CREATE TRIGGER trg_local_credentials_updated_at BEFORE UPDATE ON local_credentials
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_users_auth_provider ON users;
CREATE TRIGGER trg_users_auth_provider BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION validate_user_auth_provider();

DROP TRIGGER IF EXISTS trg_user_role_source ON user_role_cache;
CREATE TRIGGER trg_user_role_source BEFORE INSERT OR UPDATE ON user_role_cache
FOR EACH ROW EXECUTE FUNCTION validate_user_role_source();

DROP TRIGGER IF EXISTS trg_user_role_authz_version ON user_role_cache;
CREATE TRIGGER trg_user_role_authz_version AFTER INSERT OR UPDATE OR DELETE ON user_role_cache
FOR EACH ROW EXECUTE FUNCTION bump_user_authz_version();

DROP TRIGGER IF EXISTS trg_menu_weeks_identity ON menu_weeks;
CREATE TRIGGER trg_menu_weeks_identity BEFORE UPDATE ON menu_weeks
FOR EACH ROW EXECUTE FUNCTION validate_menu_week();

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

ALTER FUNCTION set_updated_at() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION bump_row_version_and_updated_at() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_week() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_service() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_item() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_item_price() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION jsonb_has_patient_forbidden_key(jsonb) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION jsonb_has_patient_forbidden_value(jsonb) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_publication_revision() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION protect_publication_revision() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION record_publication_lifecycle() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION protect_publication_lifecycle_event() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION protect_audit_event() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_local_credential() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_user_auth_provider() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_user_role_source() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION bump_user_authz_version() SET search_path = cafeteria, pg_temp;

COMMIT;
