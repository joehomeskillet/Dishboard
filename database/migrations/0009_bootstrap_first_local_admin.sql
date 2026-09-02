-- Schema v12: fail-closed bootstrap path for first local administrator.
BEGIN;
SET search_path TO cafeteria, public;

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
    -- Race-safe via advisory lock on a fixed key for bootstrap
    PERFORM pg_advisory_lock(2903847293::bigint);  -- Fixed key for bootstrap lock

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
        PERFORM pg_advisory_unlock(2903847293::bigint);
        RAISE EXCEPTION 'Es existiert bereits ein aktiver Administrator; Bootstrap ist gesperrt.' USING ERRCODE = '42501';
    END IF;

    -- Get the system user ID for audit
    SELECT id INTO v_system_actor_id
    FROM cafeteria.users
    WHERE auth_provider = 'system'
      AND public_id = '00000000-0000-0000-0000-000000000001';
    IF v_system_actor_id IS NULL THEN
        PERFORM pg_advisory_unlock(2903847293::bigint);
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

    PERFORM pg_advisory_unlock(2903847293::bigint);
    RETURN v_user_id;
END;
$$;

ALTER FUNCTION bootstrap_first_local_admin(text, text, text)
    SET search_path = cafeteria, pg_temp;

REVOKE EXECUTE ON FUNCTION bootstrap_first_local_admin(text, text, text)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

COMMIT;
