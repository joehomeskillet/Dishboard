BEGIN;

CREATE TABLE IF NOT EXISTS cafeteria.api_keys (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    label text NOT NULL CHECK (btrim(label) <> '' AND length(label) <= 80),
    key_prefix text NOT NULL UNIQUE CHECK (key_prefix ~ '^dbk_[A-Za-z0-9_-]{8}$'),
    key_hash text NOT NULL UNIQUE CHECK (key_hash ~ '^sha256:[0-9a-f]{64}$'),
    scopes text[] NOT NULL CHECK (
        cardinality(scopes) >= 1 AND scopes <@ ARRAY['preview.read']::text[]
    ),
    created_by bigint NOT NULL REFERENCES cafeteria.users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz CHECK (expires_at IS NULL OR expires_at > created_at),
    last_used_at timestamptz,
    revoked_at timestamptz,
    revoked_by bigint REFERENCES cafeteria.users(id),
    CHECK ((revoked_at IS NULL) = (revoked_by IS NULL))
);

CREATE OR REPLACE FUNCTION cafeteria.require_api_key_admin(p_actor_id bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_disabled_at timestamptz;
BEGIN
    SELECT disabled_at INTO v_disabled_at FROM cafeteria.users
    WHERE id=p_actor_id FOR SHARE;
    IF NOT FOUND OR v_disabled_at IS NOT NULL THEN
        RAISE EXCEPTION 'API-Schlüssel-Akteur ist nicht berechtigt.' USING ERRCODE='42501';
    END IF;
    PERFORM role_code FROM cafeteria.user_role_cache
    WHERE user_id=p_actor_id ORDER BY role_code FOR SHARE;
    IF NOT EXISTS (
        SELECT 1 FROM cafeteria.user_role_cache ur
        JOIN cafeteria.application_roles ar ON ar.role_code=ur.role_code AND ar.active
        WHERE ur.user_id=p_actor_id AND ur.role_code='Cafeteria.Admin'
    ) THEN
        RAISE EXCEPTION 'API-Schlüssel-Akteur ist nicht berechtigt.' USING ERRCODE='42501';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.create_api_key(
    p_actor_id bigint, p_label text, p_key_prefix text, p_key_hash text,
    p_scopes text[], p_expires_at timestamptz
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_public_id uuid;
BEGIN
    PERFORM cafeteria.require_api_key_admin(p_actor_id);
    INSERT INTO cafeteria.api_keys(
        label, key_prefix, key_hash, scopes, created_by, expires_at
    ) VALUES (
        p_label, p_key_prefix, p_key_hash, p_scopes, p_actor_id, p_expires_at
    ) RETURNING public_id INTO v_public_id;
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, details
    ) VALUES (
        p_actor_id, 'api.key_created', 'api_key', v_public_id,
        jsonb_build_object(
            'label', p_label,
            'key_prefix', p_key_prefix,
            'scopes', p_scopes,
            'expires_at', p_expires_at
        )
    );
    RETURN v_public_id;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.revoke_api_key(p_actor_id bigint, p_public_id uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_key cafeteria.api_keys%ROWTYPE;
BEGIN
    PERFORM cafeteria.require_api_key_admin(p_actor_id);
    SELECT * INTO v_key FROM cafeteria.api_keys
    WHERE public_id=p_public_id FOR UPDATE;
    IF NOT FOUND OR v_key.revoked_at IS NOT NULL THEN
        RETURN false;
    END IF;
    UPDATE cafeteria.api_keys
    SET revoked_at=clock_timestamp(), revoked_by=p_actor_id
    WHERE id=v_key.id;
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, details
    ) VALUES (
        p_actor_id, 'api.key_revoked', 'api_key', v_key.public_id,
        jsonb_build_object('label', v_key.label, 'key_prefix', v_key.key_prefix)
    );
    RETURN true;
END;
$function$;

REVOKE ALL ON cafeteria.api_keys FROM PUBLIC;
GRANT SELECT ON cafeteria.api_keys TO cafeteria_app;
GRANT UPDATE (last_used_at) ON cafeteria.api_keys TO cafeteria_app;
GRANT SELECT ON cafeteria.api_keys TO cafeteria_backup;

REVOKE ALL ON FUNCTION
    cafeteria.require_api_key_admin(bigint),
    cafeteria.create_api_key(bigint, text, text, text, text[], timestamptz),
    cafeteria.revoke_api_key(bigint, uuid)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    cafeteria.create_api_key(bigint, text, text, text, text[], timestamptz),
    cafeteria.revoke_api_key(bigint, uuid)
TO cafeteria_app;

COMMIT;
