BEGIN;

ALTER TABLE cafeteria.menu_items
    ADD COLUMN accompaniment text NOT NULL DEFAULT 'none'
    CONSTRAINT menu_items_accompaniment_check
    CHECK (accompaniment IN ('none', 'soup', 'salad'));

ALTER TABLE cafeteria.dish_templates
    ADD COLUMN accompaniment_default text NOT NULL DEFAULT 'none'
    CONSTRAINT dish_templates_accompaniment_default_check
    CHECK (accompaniment_default IN ('none', 'soup', 'salad'));

-- Row-locking SELECTs need UPDATE on one column. Keep that narrow privilege
-- while rejecting every direct app UPDATE, including statements matching no rows.
CREATE FUNCTION cafeteria.reject_direct_dish_template_update_v32() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v_table_owner name;
BEGIN
    SELECT pg_get_userbyid(c.relowner) INTO v_table_owner
    FROM pg_class c WHERE c.oid=TG_RELID;
    IF current_user IS DISTINCT FROM v_table_owner THEN
        RAISE EXCEPTION 'Direct dish template update is not permitted.' USING ERRCODE='42501';
    END IF;
    RETURN NULL;
END;$fn$;

CREATE TRIGGER dish_templates_owner_update_v32
BEFORE UPDATE ON cafeteria.dish_templates
FOR EACH STATEMENT EXECUTE FUNCTION cafeteria.reject_direct_dish_template_update_v32();

-- Private implementation: only literal-action wrappers below are app-callable.
CREATE FUNCTION cafeteria.dish_template_mutate_v32(
    p_action text,p_actor bigint,p_authz bigint,p_location bigint,
    p_target uuid,p_expected timestamptz,p_payload jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v dish_templates%ROWTYPE; old_recipe bigint; next_recipe bigint; next_type smallint;
    next_title text; next_description text; next_scope text; next_accompaniment text;
    v_recipe uuid; before_time timestamptz; verb text;
BEGIN
    PERFORM begin_menu_binding_write_v26(p_actor,p_authz,p_location);
    IF p_action NOT IN ('create','update') OR p_action IS NULL THEN
        RAISE EXCEPTION 'Ungültige Aktion.' USING ERRCODE='P1901';
    END IF;
    IF p_action='create' THEN
        IF p_target IS NOT NULL OR p_expected IS NOT NULL THEN
            RAISE EXCEPTION 'Ungültige neue Gerichtvorlage.' USING ERRCODE='P1901';
        END IF;
    ELSE
        IF p_target IS NULL OR p_expected IS NULL OR NOT isfinite(p_expected) THEN
            RAISE EXCEPTION 'Ursprünglicher Stand erforderlich.' USING ERRCODE='P1901';
        END IF;
        SELECT d.* INTO v FROM dish_templates d LEFT JOIN recipes r ON r.id=d.recipe_id
            WHERE d.public_id=p_target AND (d.recipe_id IS NULL OR r.location_id=p_location);
        IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannte Gerichtvorlage.' USING ERRCODE='22023'; END IF;
        old_recipe:=v.recipe_id;
    END IF;
    PERFORM master_payload(p_payload,ARRAY['menu_type_code','profile_scope','title','description',
        'recipe_public_id','accompaniment_default']);
    IF NOT p_payload ?& ARRAY['menu_type_code','profile_scope','title','description','recipe_public_id']
       OR EXISTS(SELECT 1 FROM jsonb_each(p_payload) f WHERE jsonb_typeof(f.value) NOT IN ('string','null'))
       OR p_payload->>'profile_scope' IS NULL
       OR p_payload->>'profile_scope' NOT IN ('common','patient','staff_guest')
       OR (p_payload ? 'accompaniment_default' AND (
           jsonb_typeof(p_payload->'accompaniment_default') IS DISTINCT FROM 'string'
           OR p_payload->>'accompaniment_default' NOT IN ('none','soup','salad')
       )) THEN
        RAISE EXCEPTION 'Ungültige Vorlagenfelder.' USING ERRCODE='P1901';
    END IF;
    next_title:=master_text(p_payload->>'title',120);
    next_description:=master_text(p_payload->>'description',2000,false);
    next_scope:=p_payload->>'profile_scope';
    next_accompaniment:=CASE
        WHEN p_payload ? 'accompaniment_default' THEN p_payload->>'accompaniment_default'
        WHEN p_action='create' THEN 'none'
        ELSE v.accompaniment_default
    END;
    IF p_payload->>'menu_type_code' IS NOT NULL THEN
        SELECT id INTO next_type FROM menu_types WHERE code=p_payload->>'menu_type_code';
        IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannte Menüart.' USING ERRCODE='P1901'; END IF;
    END IF;
    IF p_payload->>'recipe_public_id' IS NOT NULL THEN
        IF p_payload->>'recipe_public_id' !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
            RAISE EXCEPTION 'Ungültige Rezeptreferenz.' USING ERRCODE='P1901';
        END IF;
        SELECT id INTO next_recipe FROM recipes WHERE public_id=(p_payload->>'recipe_public_id')::uuid
            AND location_id=p_location;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unbekanntes Rezept.' USING ERRCODE='22023'; END IF;
    END IF;
    PERFORM id FROM recipes WHERE id IN (old_recipe,next_recipe) ORDER BY id FOR SHARE;
    IF p_action='update' THEN
        SELECT * INTO v FROM dish_templates WHERE public_id=p_target FOR UPDATE;
        IF NOT FOUND OR v.updated_at IS DISTINCT FROM p_expected OR v.recipe_id IS DISTINCT FROM old_recipe THEN
            RAISE EXCEPTION 'Gerichtvorlage wurde geändert.' USING ERRCODE='55000';
        END IF;
        before_time:=v.updated_at;
    END IF;
    IF next_recipe IS DISTINCT FROM old_recipe AND EXISTS(SELECT 1 FROM recipes WHERE id=next_recipe AND NOT active) THEN
        RAISE EXCEPTION 'Archiviertes Rezept kann nicht neu zugeordnet werden.' USING ERRCODE='55000';
    END IF;
    IF p_action='create' THEN
        INSERT INTO dish_templates(
            menu_type_id,profile_scope,title,description,recipe_id,accompaniment_default
        ) VALUES(
            next_type,next_scope,next_title,next_description,next_recipe,next_accompaniment
        ) RETURNING * INTO v;
        verb:='created';
    ELSE
        IF (v.menu_type_id,v.profile_scope,v.title,v.description,v.recipe_id,v.accompaniment_default)
            IS NOT DISTINCT FROM
            (next_type,next_scope,next_title,next_description,next_recipe,next_accompaniment) THEN
            RETURN jsonb_build_object('public_id',v.public_id,'updated_at',v.updated_at,'active',v.active);
        END IF;
        UPDATE dish_templates SET menu_type_id=next_type,profile_scope=next_scope,title=next_title,
            description=next_description,recipe_id=next_recipe,accompaniment_default=next_accompaniment
            WHERE id=v.id RETURNING * INTO v;
        verb:='updated';
    END IF;
    SELECT public_id INTO v_recipe FROM recipes WHERE id=v.recipe_id;
    INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
    VALUES(p_actor,'dish_template.'||verb,'dish_template',v.public_id,jsonb_build_object(
        'actor_authz_version',p_authz,'location_id',p_location,'updated_at_before',before_time,
        'updated_at_after',v.updated_at,'recipe_public_id',v_recipe,
        'accompaniment_default',v.accompaniment_default));
    RETURN jsonb_build_object('public_id',v.public_id,'updated_at',v.updated_at,'active',v.active);
END;$fn$;

CREATE FUNCTION cafeteria.create_dish_template_v32(
    bigint,bigint,bigint,uuid,timestamptz,jsonb
) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
    SELECT dish_template_mutate_v32('create',$1,$2,$3,$4,$5,$6);
$fn$;

CREATE FUNCTION cafeteria.update_dish_template_v32(
    bigint,bigint,bigint,uuid,timestamptz,jsonb
) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
    SELECT dish_template_mutate_v32('update',$1,$2,$3,$4,$5,$6);
$fn$;

REVOKE ALL ON FUNCTION
    cafeteria.reject_direct_dish_template_update_v32(),
    cafeteria.dish_template_mutate_v32(text,bigint,bigint,bigint,uuid,timestamptz,jsonb),
    cafeteria.create_dish_template_v32(bigint,bigint,bigint,uuid,timestamptz,jsonb),
    cafeteria.update_dish_template_v32(bigint,bigint,bigint,uuid,timestamptz,jsonb)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
    cafeteria.create_dish_template_v32(bigint,bigint,bigint,uuid,timestamptz,jsonb),
    cafeteria.update_dish_template_v32(bigint,bigint,bigint,uuid,timestamptz,jsonb)
TO cafeteria_app;

REVOKE INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES
ON TABLE cafeteria.dish_templates FROM cafeteria_app;
GRANT UPDATE(id) ON TABLE cafeteria.dish_templates TO cafeteria_app;

COMMIT;
