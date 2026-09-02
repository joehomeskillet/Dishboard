-- Schema v9: dedicated authentication issuer and local-user provisioning.
BEGIN;
SET search_path TO cafeteria, public;

CREATE OR REPLACE FUNCTION provision_local_user(
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
    v_roles text[];
    v_role_count integer;
    v_user_id bigint;
BEGIN
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
        NULL,
        'auth.local_user_provisioned',
        'user',
        jsonb_build_object('user_id', v_user_id, 'role_count', cardinality(v_roles))
    );
    INSERT INTO audit_events(actor_user_id, action, entity_type, details)
    SELECT NULL, 'auth.local_role_granted', 'user',
           jsonb_build_object('user_id', v_user_id, 'role_code', requested.role_code)
    FROM unnest(v_roles) AS requested(role_code);
    RETURN v_user_id;
END;
$$;

CREATE OR REPLACE FUNCTION set_local_password(p_username text, p_password_hash text)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_user_id bigint;
BEGIN
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
        NULL,
        'auth.local_password_changed',
        'user',
        jsonb_build_object('user_id', v_user_id)
    );
    RETURN v_user_id;
END;
$$;

CREATE OR REPLACE FUNCTION disable_local_user(p_username text)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_user_id bigint;
    v_disabled_at timestamptz;
BEGIN
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
            NULL,
            'auth.local_user_disabled',
            'user',
            jsonb_build_object('user_id', v_user_id)
        );
    END IF;
    RETURN v_user_id;
END;
$$;

ALTER FUNCTION provision_local_user(text, text, text, text[])
    SET search_path = cafeteria, pg_temp;
ALTER FUNCTION set_local_password(text, text)
    SET search_path = cafeteria, pg_temp;
ALTER FUNCTION disable_local_user(text)
    SET search_path = cafeteria, pg_temp;
REVOKE EXECUTE ON FUNCTION provision_local_user(text, text, text, text[]) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION set_local_password(text, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION disable_local_user(text) FROM PUBLIC;

DO $auth_issuer_privileges$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cafeteria_auth_issuer') THEN
        GRANT USAGE ON SCHEMA cafeteria TO cafeteria_auth_issuer;
        REVOKE ALL ON ALL TABLES IN SCHEMA cafeteria FROM cafeteria_auth_issuer;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA cafeteria FROM cafeteria_auth_issuer;
        GRANT EXECUTE ON FUNCTION
            sync_entra_user(uuid, uuid, text, text, text, text, text[]),
            issue_publication_capability(bigint, bigint, interval),
            provision_local_user(text, text, text, text[]),
            set_local_password(text, text),
            disable_local_user(text)
        TO cafeteria_auth_issuer;
        REVOKE EXECUTE ON FUNCTION
            ensure_auth_capability_state(),
            hard_reset_auth_capability_state(),
            bootstrap_auth_capability_secret(),
            rotate_auth_capability_secret(),
            withdraw_publication_revision(bigint, text, text)
        FROM cafeteria_auth_issuer;
        ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
            REVOKE ALL ON TABLES FROM cafeteria_auth_issuer;
        ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria
            REVOKE ALL ON SEQUENCES FROM cafeteria_auth_issuer;
    END IF;
END;
$auth_issuer_privileges$;
COMMIT;
