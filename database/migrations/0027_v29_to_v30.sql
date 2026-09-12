BEGIN;

-- Preserve existing access only during migration; new keys have no channel default.
ALTER TABLE cafeteria.api_keys ADD COLUMN channels text[];
UPDATE cafeteria.api_keys SET channels=ARRAY['cafeteria', 'patienten']::text[];
ALTER TABLE cafeteria.api_keys ALTER COLUMN channels SET NOT NULL;
ALTER TABLE cafeteria.api_keys ADD CONSTRAINT api_keys_channels_check CHECK (
    channels = ARRAY['cafeteria']::text[]
    OR channels = ARRAY['patienten']::text[]
    OR channels = ARRAY['cafeteria', 'patienten']::text[]
);

DROP FUNCTION cafeteria.create_api_key(bigint, text, text, text, text[], timestamptz);

CREATE FUNCTION cafeteria.create_api_key(
    p_actor_id bigint, p_label text, p_key_prefix text, p_key_hash text,
    p_scopes text[], p_expires_at timestamptz, p_channels text[]
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_public_id uuid;
    v_now timestamptz := clock_timestamp();
BEGIN
    PERFORM cafeteria.require_api_key_admin(p_actor_id);
    IF p_expires_at IS NULL OR NOT isfinite(p_expires_at)
        OR p_expires_at <= v_now OR p_expires_at > v_now + interval '2160 hours' THEN
        RAISE EXCEPTION 'Ablaufzeit muss in der Zukunft und innerhalb von 90 Tagen liegen.'
            USING ERRCODE='22023';
    END IF;
    INSERT INTO cafeteria.api_keys(
        label, key_prefix, key_hash, scopes, channels, created_by, expires_at
    ) VALUES (
        p_label, p_key_prefix, p_key_hash, p_scopes, p_channels, p_actor_id, p_expires_at
    ) RETURNING public_id INTO v_public_id;
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, details
    ) VALUES (
        p_actor_id, 'api.key_created', 'api_key', v_public_id,
        jsonb_build_object(
            'label', p_label,
            'key_prefix', p_key_prefix,
            'scopes', p_scopes,
            'channels', p_channels,
            'expires_at', p_expires_at
        )
    );
    RETURN v_public_id;
END;
$function$;

REVOKE ALL ON FUNCTION cafeteria.create_api_key(bigint, text, text, text, text[], timestamptz, text[])
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION cafeteria.create_api_key(bigint, text, text, text, text[], timestamptz, text[])
TO cafeteria_app;

COMMIT;
