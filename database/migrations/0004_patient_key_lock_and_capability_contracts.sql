BEGIN;
SET search_path TO cafeteria, public;

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
    IF p_ttl IS NULL OR p_ttl <= interval '0' THEN
        RAISE EXCEPTION 'Capability-Gültigkeit muss positiv sein.' USING ERRCODE = '22023';
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

DROP FUNCTION IF EXISTS withdraw_publication_revision(bigint, bigint, text);

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

ALTER FUNCTION normalize_patient_key(text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION patient_key_is_forbidden(text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION jsonb_has_patient_forbidden_key(jsonb) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_menu_week() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_publication_revision() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION bootstrap_auth_capability_secret() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION rotate_auth_capability_secret() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION issue_publication_capability(bigint, bigint, interval) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION withdraw_publication_revision(bigint, text, text) SET search_path = cafeteria, pg_temp;

REVOKE EXECUTE ON FUNCTION bootstrap_auth_capability_secret() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION rotate_auth_capability_secret() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION issue_publication_capability(bigint, bigint, interval) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION withdraw_publication_revision(bigint, text, text) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cafeteria_app') THEN
        EXECUTE 'REVOKE ALL ON cafeteria.auth_capability_secrets FROM cafeteria_app';
        EXECUTE 'REVOKE ALL ON cafeteria.auth_capability_nonces FROM cafeteria_app';
        EXECUTE 'REVOKE EXECUTE ON FUNCTION cafeteria.bootstrap_auth_capability_secret() FROM cafeteria_app';
        EXECUTE 'REVOKE EXECUTE ON FUNCTION cafeteria.rotate_auth_capability_secret() FROM cafeteria_app';
        EXECUTE 'REVOKE EXECUTE ON FUNCTION cafeteria.issue_publication_capability(bigint, bigint, interval) FROM cafeteria_app';
        EXECUTE 'GRANT EXECUTE ON FUNCTION cafeteria.withdraw_publication_revision(bigint, text, text) TO cafeteria_app';
    END IF;
END;
$$;

COMMIT;
