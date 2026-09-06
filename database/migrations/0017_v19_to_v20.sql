BEGIN;
SET search_path TO cafeteria, public;

-- Schema v20: Servicezeiten je Mahlzeit, geschützte Bereichsnamen und Snapshot-Schema 2.
-- Alle Änderungen sind additiv: bestehende Servicezeilen bleiben ohne Zeiten, alle neuen
-- Snapshot-Schlüssel sind optional, Schema-1-Snapshots bleiben gültig.
ALTER TABLE menu_services
    ADD COLUMN IF NOT EXISTS service_start time,
    ADD COLUMN IF NOT EXISTS service_end time;

ALTER TABLE menu_services
    DROP CONSTRAINT IF EXISTS menu_services_time_window_check;
ALTER TABLE menu_services
    ADD CONSTRAINT menu_services_time_window_check
    CHECK (service_start IS NULL OR service_end IS NULL OR service_end > service_start);

ALTER TABLE offer_profiles
    DROP CONSTRAINT IF EXISTS offer_profiles_display_name_check;
ALTER TABLE offer_profiles
    ADD CONSTRAINT offer_profiles_display_name_check
    CHECK (btrim(display_name) <> '' AND length(display_name) <= 80);

DO $profile_contract$
DECLARE v_name text;
BEGIN
    SELECT conname INTO STRICT v_name FROM pg_constraint
    WHERE conrelid='cafeteria.offer_profiles'::regclass AND contype='c'
      AND pg_get_constraintdef(oid) LIKE '%allows_prices%'
      AND pg_get_constraintdef(oid) LIKE '%allows_weekend%'
      AND pg_get_constraintdef(oid) LIKE '%allowed_meals%';
    EXECUTE format('ALTER TABLE cafeteria.offer_profiles DROP CONSTRAINT %I', v_name);
END;
$profile_contract$;
ALTER TABLE offer_profiles ADD CONSTRAINT offer_profiles_profile_contract_check CHECK (
    (code = 'patient' AND allows_prices = false AND allows_weekend = true AND allowed_meals @> ARRAY['LUNCH','DINNER']::text[])
    OR (code = 'staff_guest' AND allows_prices = true AND allowed_meals = ARRAY['LUNCH']::text[])
);

-- Only display names and the Cafeteria weekend switch are mutable profile fields.
GRANT UPDATE (display_name, allows_weekend) ON offer_profiles TO cafeteria_app;

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
ALTER FUNCTION validate_menu_service() SET search_path = cafeteria, pg_temp;

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

ALTER FUNCTION patient_key_is_forbidden(text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION validate_publication_revision() SET search_path = cafeteria, pg_temp;

-- Zeiten liegen innerhalb von jsonb_strip_nulls: Servicezeilen ohne Zeiten liefern
-- byteidentisches JSON wie in v19, damit bestehende Prüfbelege gültig bleiben.
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

COMMIT;
