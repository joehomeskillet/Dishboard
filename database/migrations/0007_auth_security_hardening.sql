-- Schema v10: attributable identity administration and strict issuer grants.
BEGIN;
SET search_path TO cafeteria, public;

DO $require_auth_issuer$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cafeteria_auth_issuer') THEN
        RAISE EXCEPTION 'Rolle cafeteria_auth_issuer muss vor Migration 0007 provisioniert sein.';
    END IF;
END;
$require_auth_issuer$;

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

DROP FUNCTION provision_local_user(text, text, text, text[]);
DROP FUNCTION set_local_password(text, text);
DROP FUNCTION disable_local_user(text);

CREATE FUNCTION provision_local_user(
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

CREATE FUNCTION set_local_password(
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

CREATE FUNCTION disable_local_user(p_actor_identifier text, p_username text)
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

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cafeteria FROM PUBLIC, cafeteria_auth_issuer;
GRANT USAGE ON SCHEMA cafeteria TO cafeteria_auth_issuer;
REVOKE ALL ON ALL TABLES IN SCHEMA cafeteria FROM cafeteria_auth_issuer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA cafeteria FROM cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    sync_entra_user(uuid, uuid, text, text, text, text, text[]),
    issue_publication_capability(bigint, bigint, interval),
    provision_local_user(text, text, text, text, text[]),
    set_local_password(text, text, text),
    disable_local_user(text, text)
TO cafeteria_auth_issuer;
REVOKE EXECUTE ON FUNCTION resolve_auth_actor(text) FROM PUBLIC, cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria REVOKE ALL ON TABLES FROM cafeteria_auth_issuer;
ALTER DEFAULT PRIVILEGES IN SCHEMA cafeteria REVOKE ALL ON SEQUENCES FROM cafeteria_auth_issuer;

COMMIT;
