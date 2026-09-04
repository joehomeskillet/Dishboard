BEGIN;

CREATE OR REPLACE FUNCTION cafeteria.lock_expected_active_location(
    p_expected_location_id bigint
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
VOLATILE
PARALLEL UNSAFE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_active_count bigint;
    v_active_id bigint;
BEGIN
    IF p_expected_location_id IS NULL OR p_expected_location_id <= 0 THEN
        RAISE EXCEPTION 'expected location id must be a positive bigint'
            USING ERRCODE = '22023';
    END IF;

    LOCK TABLE cafeteria.locations IN SHARE MODE;
    SELECT count(*), min(location.id)
      INTO v_active_count, v_active_id
      FROM cafeteria.locations AS location
     WHERE location.active;
    RETURN v_active_count = 1 AND v_active_id = p_expected_location_id;
END;
$function$;

REVOKE ALL ON FUNCTION
    cafeteria.lock_expected_active_location(bigint)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

GRANT EXECUTE ON FUNCTION
    cafeteria.lock_expected_active_location(bigint)
TO cafeteria_app;

CREATE OR REPLACE FUNCTION cafeteria.lock_active_publication(
    p_menu_week_id bigint
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
VOLATILE
PARALLEL UNSAFE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_revision_id bigint;
BEGIN
    IF p_menu_week_id IS NULL OR p_menu_week_id <= 0 THEN
        RAISE EXCEPTION 'menu week id must be a positive bigint'
            USING ERRCODE = '22023';
    END IF;

    SELECT revision.id
      INTO v_revision_id
      FROM cafeteria.publication_revisions AS revision
     WHERE revision.menu_week_id = p_menu_week_id
       AND revision.withdrawn_at IS NULL
     ORDER BY revision.id
     LIMIT 1
     FOR UPDATE;
    RETURN v_revision_id;
END;
$function$;

REVOKE ALL ON FUNCTION
    cafeteria.lock_active_publication(bigint)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

GRANT EXECUTE ON FUNCTION
    cafeteria.lock_active_publication(bigint)
TO cafeteria_app;

CREATE OR REPLACE FUNCTION cafeteria.issue_publication_capability(
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
    v_revision_found boolean;
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
    SELECT withdrawn_at
      INTO v_withdrawn_at
      FROM publication_revisions
     WHERE id = p_revision_id
     FOR UPDATE;
    v_revision_found := FOUND;
    SELECT authz_version, disabled_at
      INTO v_authz_version, v_disabled_at
      FROM users
     WHERE id = p_actor_user_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Rückzugsakteur ist nicht aktiv oder nicht zur Publikation berechtigt.'
            USING ERRCODE = '42501';
    END IF;
    PERFORM 1
      FROM user_role_cache
     WHERE user_id = p_actor_user_id
     ORDER BY role_code
     FOR UPDATE;
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
    IF NOT v_revision_found THEN
        RAISE EXCEPTION 'Unbekannte Publikationsrevision.' USING ERRCODE = 'P0002';
    END IF;
    IF v_withdrawn_at IS NOT NULL THEN
        RAISE EXCEPTION 'Publikationsrevision wurde bereits zurückgezogen.' USING ERRCODE = '55000';
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

REVOKE EXECUTE ON FUNCTION
    cafeteria.issue_publication_capability(bigint, bigint, interval)
FROM PUBLIC, cafeteria_app, cafeteria_backup;

GRANT EXECUTE ON FUNCTION
    cafeteria.issue_publication_capability(bigint, bigint, interval)
TO cafeteria_auth_issuer;

CREATE OR REPLACE FUNCTION cafeteria.withdraw_publication_revision(
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

    SELECT withdrawn_at
      INTO v_existing_withdrawal
      FROM publication_revisions
     WHERE id = p_revision_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unbekannte Publikationsrevision.' USING ERRCODE = 'P0002';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM auth_capability_nonces
        WHERE nonce = decode(v_nonce_hex, 'hex')
    ) THEN
        RAISE EXCEPTION 'Capability-Nonce wurde bereits verwendet.' USING ERRCODE = '42501';
    END IF;
    IF v_existing_withdrawal IS NOT NULL THEN
        RAISE EXCEPTION 'Publikationsrevision wurde bereits zurückgezogen.' USING ERRCODE = '55000';
    END IF;

    SELECT authz_version, disabled_at
      INTO v_authz_version, v_disabled_at
      FROM users
     WHERE id = v_actor_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Capability ist ungültig oder abgelaufen.' USING ERRCODE = '42501';
    END IF;
    PERFORM 1
      FROM user_role_cache
     WHERE user_id = v_actor_id
     ORDER BY role_code
     FOR UPDATE;
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

    BEGIN
        INSERT INTO auth_capability_nonces(nonce, actor_user_id, revision_id)
        VALUES (decode(v_nonce_hex, 'hex'), v_actor_id, v_token_revision);
    EXCEPTION WHEN unique_violation THEN
        RAISE EXCEPTION 'Capability-Nonce wurde bereits verwendet.' USING ERRCODE = '42501';
    END;

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

REVOKE EXECUTE ON FUNCTION
    cafeteria.withdraw_publication_revision(bigint, text, text)
FROM PUBLIC, cafeteria_backup, cafeteria_auth_issuer;

GRANT EXECUTE ON FUNCTION
    cafeteria.withdraw_publication_revision(bigint, text, text)
TO cafeteria_app;

COMMIT;
