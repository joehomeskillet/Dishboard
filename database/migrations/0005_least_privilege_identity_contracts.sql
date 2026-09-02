-- Schema v8: least-privilege identity boundary and bounded withdrawal capabilities.
BEGIN;
SET search_path TO cafeteria, public;
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
    v_role_count integer;
    v_user_id bigint;
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
    RETURN v_user_id;
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

ALTER FUNCTION validate_user_auth_provider() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION bump_user_authz_version() SET search_path = cafeteria, pg_temp;
ALTER FUNCTION sync_entra_user(uuid, uuid, text, text, text, text, text[])
    SET search_path = cafeteria, pg_temp;
ALTER FUNCTION ensure_auth_capability_state()
    SET search_path = cafeteria, pg_temp;
ALTER FUNCTION hard_reset_auth_capability_state()
    SET search_path = cafeteria, pg_temp;
ALTER FUNCTION issue_publication_capability(bigint, bigint, interval)
    SET search_path = cafeteria, pg_temp;

REVOKE EXECUTE ON FUNCTION sync_entra_user(uuid, uuid, text, text, text, text, text[]) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION record_publication_lifecycle() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION bootstrap_auth_capability_secret() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION rotate_auth_capability_secret() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION ensure_auth_capability_state() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION hard_reset_auth_capability_state() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION issue_publication_capability(bigint, bigint, interval) FROM PUBLIC;

DO $least_privilege$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cafeteria_app') THEN
        EXECUTE 'REVOKE ALL ON cafeteria.users, cafeteria.user_role_cache, '
                'cafeteria.local_credentials, cafeteria.auth_capability_secrets, '
                'cafeteria.auth_capability_nonces FROM cafeteria_app';
        EXECUTE 'REVOKE ALL ON SEQUENCE cafeteria.auth_capability_secrets_id_seq '
                'FROM cafeteria_app';
        EXECUTE 'GRANT SELECT ON cafeteria.users, cafeteria.user_role_cache, '
                'cafeteria.local_credentials TO cafeteria_app';
        EXECUTE 'GRANT UPDATE (last_login_at) ON cafeteria.users TO cafeteria_app';
        EXECUTE 'GRANT UPDATE (failed_login_count, locked_until, last_failed_at) '
                'ON cafeteria.local_credentials TO cafeteria_app';
        EXECUTE 'REVOKE EXECUTE ON FUNCTION '
                'cafeteria.sync_entra_user(uuid, uuid, text, text, text, text, text[]), '
                'cafeteria.record_publication_lifecycle(), '
                'cafeteria.bootstrap_auth_capability_secret(), '
                'cafeteria.rotate_auth_capability_secret(), '
                'cafeteria.ensure_auth_capability_state(), '
                'cafeteria.hard_reset_auth_capability_state(), '
                'cafeteria.issue_publication_capability(bigint, bigint, interval) '
                'FROM cafeteria_app';
        EXECUTE 'GRANT EXECUTE ON FUNCTION '
                'cafeteria.withdraw_publication_revision(bigint, text, text) '
                'TO cafeteria_app';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cafeteria_backup') THEN
        EXECUTE 'REVOKE ALL ON cafeteria.auth_capability_secrets, '
                'cafeteria.auth_capability_nonces FROM cafeteria_backup';
        EXECUTE 'REVOKE ALL ON SEQUENCE cafeteria.auth_capability_secrets_id_seq '
                'FROM cafeteria_backup';
        EXECUTE 'REVOKE EXECUTE ON FUNCTION '
                'cafeteria.hard_reset_auth_capability_state(), '
                'cafeteria.ensure_auth_capability_state(), '
                'cafeteria.record_publication_lifecycle(), '
                'cafeteria.bootstrap_auth_capability_secret(), '
                'cafeteria.rotate_auth_capability_secret(), '
                'cafeteria.sync_entra_user(uuid, uuid, text, text, text, text, text[]), '
                'cafeteria.issue_publication_capability(bigint, bigint, interval), '
                'cafeteria.withdraw_publication_revision(bigint, text, text) '
                'FROM cafeteria_backup';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria '
                'REVOKE ALL ON TABLES FROM cafeteria_backup';
    END IF;
END;
$least_privilege$;
COMMIT;
