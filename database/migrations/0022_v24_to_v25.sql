BEGIN;
SET search_path TO cafeteria, public;

CREATE FUNCTION record_auth_access_v25(
    p_event uuid, p_provider text, p_action text, p_reason text,
    p_actor bigint, p_authz bigint
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE
    v_existing cafeteria.audit_events%ROWTYPE;
    v_identity cafeteria.users%ROWTYPE;
    v_details jsonb;
BEGIN
    IF p_event IS NULL OR p_provider IS NULL OR p_provider NOT IN ('local','entra')
       OR p_action IS NULL OR p_action NOT IN (
           'auth.login.accepted','auth.login.rejected','auth.login.unavailable',
           'auth.logout.requested','auth.frontchannel.requested')
       OR (p_actor IS NULL) <> (p_authz IS NULL)
       OR p_actor <= 0 OR p_authz <= 0 THEN
        RAISE EXCEPTION 'Invalid authentication event.' USING ERRCODE='P2501';
    END IF;
    IF (p_action='auth.login.rejected' AND (
            p_reason IS NULL OR p_reason NOT IN ('credentials','role','flow','throttled')
            OR p_actor IS NOT NULL))
       OR (p_action='auth.login.unavailable' AND (
            p_reason IS DISTINCT FROM 'unavailable' OR p_actor IS NOT NULL))
       OR (p_action IN ('auth.login.accepted','auth.logout.requested','auth.frontchannel.requested')
            AND p_reason IS NOT NULL)
       OR (p_action='auth.login.accepted' AND p_actor IS NULL) THEN
        RAISE EXCEPTION 'Invalid authentication outcome.' USING ERRCODE='P2501';
    END IF;
    v_details:=jsonb_build_object('provider',p_provider,'reason',p_reason,'authz_version',p_authz);
    -- Serialize this server UUID before inspecting it: a retry never invokes INSERT
    -- or advances the audit sequence. A hash collision only serializes unrelated events.
    PERFORM pg_advisory_xact_lock(hashtextextended(p_event::text,2500908));
    SELECT * INTO v_existing FROM cafeteria.audit_events WHERE public_id=p_event;
    IF FOUND THEN
        IF v_existing.entity_type IS DISTINCT FROM 'authentication'
           OR v_existing.action IS DISTINCT FROM p_action
           OR v_existing.actor_user_id IS DISTINCT FROM p_actor
           OR v_existing.details IS DISTINCT FROM v_details
           OR v_existing.entity_public_id IS NOT NULL OR v_existing.profile_code IS NOT NULL THEN
            RAISE EXCEPTION 'Conflicting authentication event.' USING ERRCODE='P2501';
        END IF;
        RETURN v_existing.public_id;
    END IF;
    IF p_actor IS NOT NULL THEN
        -- Match existing identity mutation lock order: user before credentials/roles.
        SELECT * INTO v_identity FROM cafeteria.users WHERE id=p_actor FOR SHARE;
        IF NOT FOUND OR v_identity.disabled_at IS NOT NULL
           OR v_identity.auth_provider IS DISTINCT FROM p_provider
           OR v_identity.authz_version IS DISTINCT FROM p_authz
           OR NOT EXISTS (
               SELECT 1 FROM cafeteria.user_role_cache r
               JOIN cafeteria.application_roles a ON a.role_code=r.role_code AND a.active
               WHERE r.user_id=p_actor
           ) THEN
            RAISE EXCEPTION 'Authentication identity is no longer current.' USING ERRCODE='42501';
        END IF;
        IF p_provider='local' AND NOT EXISTS (
            SELECT 1 FROM cafeteria.local_credentials WHERE user_id=p_actor
        ) THEN
            RAISE EXCEPTION 'Authentication identity is no longer current.' USING ERRCODE='42501';
        END IF;
    END IF;
    INSERT INTO cafeteria.audit_events(public_id,actor_user_id,action,entity_type,details)
    VALUES(p_event,p_actor,p_action,'authentication',v_details);
    RETURN p_event;
END;$fn$;

REVOKE ALL ON FUNCTION record_auth_access_v25(uuid,text,text,text,bigint,bigint)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION record_auth_access_v25(uuid,text,text,text,bigint,bigint)
TO cafeteria_auth_issuer;

COMMIT;
