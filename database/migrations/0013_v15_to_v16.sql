BEGIN;

-- Existing checked flags are preserved; no historical approval is inferred.
ALTER TABLE cafeteria.menu_weeks ADD COLUMN IF NOT EXISTS
    header_revision bigint NOT NULL DEFAULT 1 CHECK (header_revision > 0);

CREATE OR REPLACE FUNCTION cafeteria.bump_week_header_revision()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
BEGIN
    NEW.header_revision := OLD.header_revision +
        CASE WHEN (NEW.title, NEW.shared_note) IS DISTINCT FROM
                       (OLD.title, OLD.shared_note) THEN 1 ELSE 0 END;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_week_header_revision ON cafeteria.menu_weeks;
CREATE TRIGGER trg_week_header_revision BEFORE UPDATE ON cafeteria.menu_weeks
FOR EACH ROW EXECUTE FUNCTION cafeteria.bump_week_header_revision();

CREATE OR REPLACE FUNCTION cafeteria.workflow_week_context(p_week_id bigint)
RETURNS jsonb LANGUAGE sql STABLE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
    SELECT jsonb_build_object(
        'week_public_id', w.public_id::text, 'location_id', w.location_id,
        'profile_code', p.code, 'week_start', w.week_start::text,
        'header_revision', w.header_revision,
        'title', COALESCE(w.title, ''), 'shared_note', COALESCE(w.shared_note, ''),
        'services', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'public_id', s.public_id::text, 'date', s.service_date::text,
                'meal', mp.code, 'row_version', s.row_version,
                'state', s.service_state, 'notice', COALESCE(s.notice, '')
            ) ORDER BY s.service_date, mp.sort_order, s.id)
            FROM cafeteria.menu_services s
            JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
            WHERE s.menu_week_id=w.id
        ), '[]'::jsonb)
    )
    FROM cafeteria.menu_weeks w
    JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
    WHERE w.id=p_week_id;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.require_workflow_review_actor(p_actor_id bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_disabled_at timestamptz;
BEGIN
    SELECT disabled_at INTO v_disabled_at FROM cafeteria.users
    WHERE id=p_actor_id FOR SHARE;
    IF NOT FOUND OR v_disabled_at IS NOT NULL THEN
        RAISE EXCEPTION 'Prüfer ist nicht berechtigt.' USING ERRCODE='42501';
    END IF;
    PERFORM role_code FROM cafeteria.user_role_cache
    WHERE user_id=p_actor_id ORDER BY role_code FOR SHARE;
    IF NOT EXISTS (
        SELECT 1 FROM cafeteria.user_role_cache ur
        JOIN cafeteria.application_roles ar ON ar.role_code=ur.role_code AND ar.active
        WHERE ur.user_id=p_actor_id
          AND ur.role_code IN ('Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin')
    ) THEN
        RAISE EXCEPTION 'Prüfer ist nicht berechtigt.' USING ERRCODE='42501';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.record_menu_review(
    p_actor_id bigint, p_location_id bigint, p_profile text, p_item_id bigint,
    p_source_version bigint, p_submitted_token text, p_reviewed_token text
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_week_id bigint;
    v_service_id bigint;
    v_item cafeteria.menu_items%ROWTYPE;
    v_receipt uuid;
BEGIN
    IF p_source_version IS NULL OR p_source_version < 1
       OR p_submitted_token IS NULL OR p_submitted_token !~ '^sha256:[0-9a-f]{64}$'
       OR p_reviewed_token IS NULL OR p_reviewed_token !~ '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Prüfbeleg ist ungültig.' USING ERRCODE='22023';
    END IF;
    IF NOT cafeteria.lock_expected_active_location(p_location_id) THEN
        RAISE EXCEPTION 'Standort wurde geändert.' USING ERRCODE='55000';
    END IF;
    SELECT w.id, s.id INTO v_week_id, v_service_id
    FROM cafeteria.menu_weeks w
    JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
    JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
    JOIN cafeteria.menu_items i ON i.service_id=s.id
    WHERE i.id=p_item_id AND w.location_id=p_location_id AND p.code=p_profile
    FOR UPDATE OF w;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Menü nicht gefunden.' USING ERRCODE='22023';
    END IF;
    PERFORM id FROM cafeteria.menu_services WHERE id=v_service_id FOR UPDATE;
    SELECT * INTO v_item FROM cafeteria.menu_items WHERE id=p_item_id FOR UPDATE;
    IF v_item.row_version <> p_source_version + 1
       OR v_item.allergen_review_status <> 'checked'
       OR EXISTS (
            SELECT 1 FROM cafeteria.menu_item_components mic
            JOIN cafeteria.menu_components c ON c.id=mic.component_id
            WHERE mic.menu_item_id=p_item_id
              AND mic.component_row_version IS DISTINCT FROM c.row_version
       ) THEN
        RAISE EXCEPTION 'Die Menüprüfung ist veraltet.' USING ERRCODE='55000';
    END IF;
    PERFORM cafeteria.require_workflow_review_actor(p_actor_id);
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, profile_code, details
    ) VALUES (
        p_actor_id, 'workflow.menu_reviewed', 'menu_item', v_item.public_id, p_profile,
        jsonb_build_object(
            'source_item_row_version', p_source_version,
            'reviewed_item_row_version', v_item.row_version,
            'submitted_token', p_submitted_token, 'reviewed_token', p_reviewed_token,
            'week_public_id', (SELECT public_id::text FROM cafeteria.menu_weeks WHERE id=v_week_id)
        )
    ) RETURNING public_id INTO v_receipt;
    RETURN v_receipt;
END;
$function$;

CREATE OR REPLACE FUNCTION cafeteria.record_week_context_review(
    p_actor_id bigint, p_location_id bigint, p_profile text, p_week_id bigint,
    p_token text, p_context jsonb
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
DECLARE
    v_week_uuid uuid;
    v_context jsonb;
    v_receipt uuid;
BEGIN
    IF p_token IS NULL OR p_token !~ '^sha256:[0-9a-f]{64}$'
       OR p_context IS NULL OR jsonb_typeof(p_context) <> 'object' THEN
        RAISE EXCEPTION 'Prüfbeleg ist ungültig.' USING ERRCODE='22023';
    END IF;
    IF NOT cafeteria.lock_expected_active_location(p_location_id) THEN
        RAISE EXCEPTION 'Standort wurde geändert.' USING ERRCODE='55000';
    END IF;
    SELECT w.public_id INTO v_week_uuid
    FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
    WHERE w.id=p_week_id AND w.location_id=p_location_id AND p.code=p_profile
    FOR UPDATE OF w;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Woche nicht gefunden.' USING ERRCODE='22023';
    END IF;
    PERFORM s.id FROM cafeteria.menu_services s
    JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
    WHERE s.menu_week_id=p_week_id
    ORDER BY s.service_date, mp.sort_order, s.id FOR UPDATE OF s;
    v_context := cafeteria.workflow_week_context(p_week_id);
    IF v_context IS DISTINCT FROM p_context THEN
        RAISE EXCEPTION 'Die Wochenprüfung ist veraltet.' USING ERRCODE='55000';
    END IF;
    PERFORM cafeteria.require_workflow_review_actor(p_actor_id);
    INSERT INTO cafeteria.audit_events(
        actor_user_id, action, entity_type, entity_public_id, profile_code, details
    ) VALUES (
        p_actor_id, 'workflow.week_context_reviewed', 'menu_week', v_week_uuid, p_profile,
        jsonb_build_object('submitted_token', p_token, 'reviewed_token', p_token,
                           'context', v_context)
    ) RETURNING public_id INTO v_receipt;
    RETURN v_receipt;
END;
$function$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_review_submission
ON cafeteria.audit_events(action, entity_public_id, (details->>'submitted_token'))
WHERE action IN ('workflow.menu_reviewed', 'workflow.week_context_reviewed');

CREATE INDEX IF NOT EXISTS ix_workflow_review_receipts
ON cafeteria.audit_events(entity_public_id, action, id DESC)
WHERE action IN ('workflow.menu_reviewed', 'workflow.week_context_reviewed');

REVOKE ALL ON FUNCTION
    cafeteria.bump_week_header_revision(),
    cafeteria.workflow_week_context(bigint),
    cafeteria.require_workflow_review_actor(bigint),
    cafeteria.record_menu_review(bigint, bigint, text, bigint, bigint, text, text),
    cafeteria.record_week_context_review(bigint, bigint, text, bigint, text, jsonb)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    cafeteria.workflow_week_context(bigint),
    cafeteria.record_menu_review(bigint, bigint, text, bigint, bigint, text, text),
    cafeteria.record_week_context_review(bigint, bigint, text, bigint, text, jsonb)
TO cafeteria_app;

COMMIT;
