BEGIN;
SET search_path TO cafeteria, public;

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

COMMIT;
