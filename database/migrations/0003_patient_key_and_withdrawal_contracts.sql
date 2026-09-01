BEGIN;
SET search_path TO cafeteria, public;

ALTER TABLE publication_revisions
    ADD COLUMN IF NOT EXISTS withdrawn_by bigint REFERENCES users(id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_lifecycle_once
    ON publication_lifecycle_events(revision_id, event_type);

-- v5 konnte den ursprünglichen Publisher fälschlich als Rückzugsakteur backfillen.
-- Ohne belastbare Identität bleibt der historische Akteur bewusst unbekannt.
DROP TRIGGER IF EXISTS trg_publication_lifecycle_immutable ON publication_lifecycle_events;
UPDATE publication_lifecycle_events e
SET actor_user_id = NULL
FROM publication_revisions r
WHERE e.revision_id = r.id
  AND e.event_type = 'withdrawn'
  AND r.withdrawn_by IS NULL;

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
       AND NEW.workflow_state IS DISTINCT FROM OLD.workflow_state
       AND EXISTS (
           SELECT 1 FROM publication_revisions
           WHERE menu_week_id = OLD.id AND withdrawn_at IS NULL
       ) THEN
        RAISE EXCEPTION 'Eine publizierte Woche mit aktiver Publikationsrevision kann nicht zurückgestuft werden.'
            USING ERRCODE = '55000';
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
    SELECT trim(
        both '_' FROM lower(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        k,
                        U&'[\00AD\0600-\0605\061C\06DD\070F\0890-\0891\08E2\180E\200B-\200F\202A-\202E\2060-\2064\2066-\206F\FEFF\FFF9-\FFFB\+0110BD\+0110CD\+013430-\+01343F\+01BCA0-\+01BCA3\+01D173-\+01D17A\+0E0001\+0E0020-\+0E007F]',
                        '',
                        'g'
                    ),
                    '([[:lower:][:digit:]])([[:upper:]])',
                    '\1_\2',
                    'g'
                ),
                '[^[:alnum:]]+',
                '_',
                'g'
            )
        )
    );
$$;

CREATE OR REPLACE FUNCTION jsonb_has_patient_forbidden_key(v jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    k text;
    normalized_k text;
    child jsonb;
BEGIN
    IF jsonb_typeof(v) = 'object' THEN
        FOR k, child IN SELECT key, value FROM jsonb_each(v)
        LOOP
            normalized_k := normalize_patient_key(k);
            IF normalized_k ~ '(^|_)(price|prices|preis|preise|cost|costs|amount|amounts|kosten|betrag|rappen|currency|chf|fee|tarif|tariff|charge)(_|$)' THEN
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

CREATE OR REPLACE FUNCTION withdraw_publication_revision(
    p_revision_id bigint,
    p_actor_user_id bigint,
    p_reason text
)
RETURNS timestamptz
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_existing_withdrawal timestamptz;
    v_withdrawn_at timestamptz;
BEGIN
    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'Ein Rückzugsgrund ist erforderlich.' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM users u
        JOIN user_role_cache ur ON ur.user_id = u.id
        JOIN application_roles ar ON ar.role_code = ur.role_code AND ar.active
        WHERE u.id = p_actor_user_id
          AND u.disabled_at IS NULL
          AND ur.role_code IN ('Cafeteria.Publisher', 'Cafeteria.Admin')
    ) THEN
        RAISE EXCEPTION 'Rückzugsakteur ist nicht aktiv oder nicht zur Publikation berechtigt.'
            USING ERRCODE = '42501';
    END IF;

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

    v_withdrawn_at := clock_timestamp();
    INSERT INTO publication_lifecycle_events(
        revision_id, event_type, reason, actor_user_id, occurred_at
    ) VALUES (
        p_revision_id, 'withdrawn', btrim(p_reason), p_actor_user_id, v_withdrawn_at
    );
    UPDATE publication_revisions
       SET withdrawn_at = v_withdrawn_at,
           withdrawal_reason = btrim(p_reason),
           withdrawn_by = p_actor_user_id
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

DROP TRIGGER IF EXISTS trg_publication_lifecycle_immutable ON publication_lifecycle_events;
CREATE TRIGGER trg_publication_lifecycle_immutable BEFORE UPDATE OR DELETE ON publication_lifecycle_events
FOR EACH ROW EXECUTE FUNCTION protect_publication_lifecycle_event();

ALTER FUNCTION validate_menu_week() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION normalize_patient_key(text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION jsonb_has_patient_forbidden_key(jsonb) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION jsonb_has_patient_forbidden_value(jsonb) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION protect_publication_revision() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION record_publication_lifecycle() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION withdraw_publication_revision(bigint, bigint, text) SET search_path = cafeteria, pg_temp;
ALTER FUNCTION protect_publication_lifecycle_event() SET search_path = cafeteria, pg_temp;

REVOKE EXECUTE ON FUNCTION withdraw_publication_revision(bigint, bigint, text) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cafeteria_app') THEN
        EXECUTE 'REVOKE UPDATE (withdrawn_at, withdrawal_reason, withdrawn_by) '
                'ON cafeteria.publication_revisions FROM cafeteria_app';
        EXECUTE 'REVOKE INSERT ON cafeteria.publication_lifecycle_events FROM cafeteria_app';
        EXECUTE 'GRANT EXECUTE ON FUNCTION '
                'cafeteria.withdraw_publication_revision(bigint, bigint, text) TO cafeteria_app';
    END IF;
END;
$$;

COMMIT;
