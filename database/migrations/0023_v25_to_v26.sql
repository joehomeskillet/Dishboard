BEGIN;
SET search_path TO cafeteria, public;

ALTER TABLE menu_components ADD COLUMN food_id bigint;
ALTER TABLE menu_components ADD CONSTRAINT menu_components_food_scope_fk
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT;
ALTER TABLE menu_item_components ADD COLUMN recipe_revision_id bigint
    REFERENCES recipe_revisions(id) ON DELETE RESTRICT;
ALTER TABLE dish_templates ADD COLUMN recipe_id bigint REFERENCES recipes(id) ON DELETE RESTRICT;
CREATE INDEX menu_components_food_idx ON menu_components(food_id) WHERE food_id IS NOT NULL;
CREATE INDEX menu_item_components_recipe_idx ON menu_item_components(recipe_revision_id)
    WHERE recipe_revision_id IS NOT NULL;
CREATE INDEX dish_templates_recipe_idx ON dish_templates(recipe_id) WHERE recipe_id IS NOT NULL;
CREATE INDEX menu_items_dish_template_idx ON menu_items(dish_template_id) WHERE dish_template_id IS NOT NULL;

-- Immutable revision/parent locations need SELECT, not privileged row locks.
-- Existing triggers prohibit moving items, services and weeks to new parents.
CREATE FUNCTION validate_menu_recipe_scope_v26() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF NEW.recipe_revision_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM menu_items i JOIN menu_services s ON s.id=i.service_id
        JOIN menu_weeks w ON w.id=s.menu_week_id
        JOIN recipe_revisions r ON r.id=NEW.recipe_revision_id
        WHERE i.id=NEW.menu_item_id AND r.location_id<>w.location_id) THEN
        RAISE EXCEPTION 'Rezeptrevision gehört zu einem anderen Standort.'
            USING ERRCODE='23514',CONSTRAINT='menu_item_components_recipe_scope';
    END IF;
    RETURN NEW;
END;$fn$;
CREATE TRIGGER menu_item_components_recipe_scope BEFORE INSERT OR UPDATE OF menu_item_id,recipe_revision_id
ON menu_item_components FOR EACH ROW EXECUTE FUNCTION validate_menu_recipe_scope_v26();

CREATE FUNCTION validate_dish_recipe_scope_v26() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF NEW.recipe_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM menu_items i JOIN menu_services s ON s.id=i.service_id
        JOIN menu_weeks w ON w.id=s.menu_week_id JOIN recipes r ON r.id=NEW.recipe_id
        WHERE i.dish_template_id=NEW.id AND w.location_id<>r.location_id) THEN
        RAISE EXCEPTION 'Rezept passt nicht zu den verwendenden Menüwochen.'
            USING ERRCODE='23514',CONSTRAINT='dish_templates_recipe_scope';
    END IF;
    RETURN NEW;
END;$fn$;
CREATE TRIGGER dish_templates_recipe_scope BEFORE INSERT OR UPDATE OF recipe_id ON dish_templates
FOR EACH ROW EXECUTE FUNCTION validate_dish_recipe_scope_v26();

CREATE FUNCTION validate_menu_dish_scope_v26() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v_recipe bigint;
BEGIN
    -- SHARE conflicts with a concurrent template recipe_id (non-key) UPDATE.
    SELECT recipe_id INTO v_recipe FROM dish_templates WHERE id=NEW.dish_template_id FOR SHARE;
    IF v_recipe IS NOT NULL AND EXISTS (
        SELECT 1 FROM menu_services s JOIN menu_weeks w ON w.id=s.menu_week_id
        JOIN recipes r ON r.id=v_recipe WHERE s.id=NEW.service_id AND r.location_id<>w.location_id) THEN
        RAISE EXCEPTION 'Gerichtvorlage gehört zu einem anderen Standort.'
            USING ERRCODE='23514',CONSTRAINT='menu_items_dish_recipe_scope';
    END IF;
    RETURN NEW;
END;$fn$;
CREATE TRIGGER menu_items_dish_recipe_scope BEFORE INSERT OR UPDATE OF dish_template_id,service_id ON menu_items
FOR EACH ROW EXECUTE FUNCTION validate_menu_dish_scope_v26();

CREATE FUNCTION begin_menu_binding_write_v26(p_actor bigint,p_authz bigint,p_location bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v users%ROWTYPE;
BEGIN
    IF current_setting('transaction_isolation')<>'read committed' OR p_actor IS NULL OR p_actor<=0
       OR p_authz IS NULL OR p_authz<=0 THEN
        RAISE EXCEPTION 'Ungültige ursprüngliche Berechtigung.' USING ERRCODE='P1901';
    END IF;
    PERFORM set_config('lock_timeout','5s',true);
    PERFORM role_code FROM application_roles ORDER BY role_code FOR SHARE;
    SELECT * INTO v FROM users WHERE id=p_actor FOR SHARE;
    IF NOT FOUND OR v.disabled_at IS NOT NULL THEN
        RAISE EXCEPTION 'Aktiver Benutzer erforderlich.' USING ERRCODE='P1902';
    END IF;
    IF v.authz_version<>p_authz THEN
        RAISE EXCEPTION 'Berechtigung wurde geändert.' USING ERRCODE='P1903';
    END IF;
    -- Fixed draft.write, matching roles.py; caller cannot select a capability.
    IF NOT EXISTS(SELECT 1 FROM user_role_cache r JOIN application_roles a USING(role_code)
        WHERE r.user_id=p_actor AND a.active
        AND r.role_code IN ('Cafeteria.Editor','Cafeteria.Publisher','Cafeteria.Admin')) THEN
        RAISE EXCEPTION 'Menübearbeitung nicht erlaubt.' USING ERRCODE='P1902';
    END IF;
    PERFORM master_location(p_location);
END;$fn$;

-- Caller order: begin guard, scoped pre-read, sorted old/new heads, then
-- Week/Service/Item (or component), original CAS and reference-state recheck.
-- Never acquire a newly discovered head after the aggregate: conflict instead.
-- Repeat guards below assume those same original actor/location locks are held.
CREATE FUNCTION lock_menu_recipe_revisions_v26(
    p_actor bigint,p_authz bigint,p_location bigint,p_ids bigint[])
RETURNS TABLE(revision_id bigint,revision_public_id uuid,recipe_id bigint,
    recipe_public_id uuid,active boolean,content_hash_sha256 text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    PERFORM begin_menu_binding_write_v26(p_actor,p_authz,p_location);
    IF p_ids IS NULL OR cardinality(p_ids)>32767 OR array_ndims(p_ids)>1
       OR EXISTS(SELECT 1 FROM unnest(p_ids) x WHERE x IS NULL OR x<=0)
       OR cardinality(p_ids)<>(SELECT count(DISTINCT x) FROM unnest(p_ids) x)
       OR cardinality(p_ids)<>(SELECT count(*) FROM recipe_revisions r
           WHERE r.id=ANY(p_ids) AND r.location_id=p_location) THEN
        RAISE EXCEPTION 'Ungültige Rezeptrevisionen.' USING ERRCODE='P1901';
    END IF;
    PERFORM h.id FROM recipes h WHERE h.id IN (
        SELECT r.recipe_id FROM recipe_revisions r WHERE r.id=ANY(p_ids)) ORDER BY h.id FOR SHARE;
    RETURN QUERY SELECT r.id,r.public_id,h.id,h.public_id,h.active,r.content_hash_sha256
        FROM recipe_revisions r JOIN recipes h ON h.id=r.recipe_id
        WHERE r.id=ANY(p_ids) AND r.location_id=p_location ORDER BY r.id;
END;$fn$;

CREATE FUNCTION lock_component_foods_v26(p_actor bigint,p_authz bigint,p_location bigint,p_ids bigint[])
RETURNS TABLE(food_id bigint,food_public_id uuid,active boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    PERFORM begin_menu_binding_write_v26(p_actor,p_authz,p_location);
    IF p_ids IS NULL OR cardinality(p_ids)>32767 OR array_ndims(p_ids)>1
       OR EXISTS(SELECT 1 FROM unnest(p_ids) x WHERE x IS NULL OR x<=0)
       OR cardinality(p_ids)<>(SELECT count(DISTINCT x) FROM unnest(p_ids) x)
       OR cardinality(p_ids)<>(SELECT count(*) FROM foods f WHERE f.id=ANY(p_ids) AND f.location_id=p_location) THEN
        RAISE EXCEPTION 'Ungültige Zutaten.' USING ERRCODE='P1901';
    END IF;
    RETURN QUERY SELECT f.id,f.public_id,f.active FROM foods f
        WHERE f.id=ANY(p_ids) AND f.location_id=p_location ORDER BY f.id FOR SHARE;
END;$fn$;

-- Receipts never bump aggregates. The writer holds original actor/target locks,
-- performs exactly one aggregate write and invokes the receipt in that SAME TX.
CREATE UNIQUE INDEX audit_binding_entity_version_v26 ON audit_events
    (entity_type,entity_public_id,(details->>'row_version_after'))
    WHERE action IN ('workflow.menu_saved','component.food_saved') AND details ? 'row_version_after';

CREATE FUNCTION record_menu_binding_write_v26(p_actor bigint,p_authz bigint,p_location bigint,
    p_item bigint,p_before bigint,p_after bigint) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v menu_items%ROWTYPE; v_profile text; v_links jsonb; v_event uuid;
BEGIN
    PERFORM begin_menu_binding_write_v26(p_actor,p_authz,p_location);
    IF p_before IS NULL OR p_after IS NULL OR p_before<0 OR p_after<=0 OR p_after-1<>p_before THEN
        RAISE EXCEPTION 'Ungültiger Versionswechsel.' USING ERRCODE='P1901';
    END IF;
    SELECT i.* INTO v FROM menu_items i JOIN menu_services s ON s.id=i.service_id
        JOIN menu_weeks w ON w.id=s.menu_week_id WHERE i.id=p_item AND w.location_id=p_location FOR UPDATE OF i;
    IF NOT FOUND OR v.row_version<>p_after THEN
        RAISE EXCEPTION 'Menüposition wurde geändert.' USING ERRCODE='55000';
    END IF;
    IF EXISTS(SELECT 1 FROM audit_events WHERE entity_type='menu_item' AND entity_public_id=v.public_id
        AND action='workflow.menu_saved' AND details->>'row_version_after'=p_after::text) THEN
        RAISE EXCEPTION 'Versionswechsel bereits protokolliert.' USING ERRCODE='55000';
    END IF;
    SELECT p.code INTO v_profile FROM menu_services s JOIN menu_weeks w ON w.id=s.menu_week_id
        JOIN offer_profiles p ON p.id=w.profile_id WHERE s.id=v.service_id;
    SELECT COALESCE(jsonb_agg(jsonb_build_object('sort_order',l.sort_order,
        'revision_public_id',r.public_id,'content_hash_sha256',r.content_hash_sha256) ORDER BY l.sort_order),'[]')
        INTO v_links FROM menu_item_components l JOIN recipe_revisions r ON r.id=l.recipe_revision_id
        WHERE l.menu_item_id=v.id;
    INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,profile_code,details)
    VALUES(p_actor,'workflow.menu_saved','menu_item',v.public_id,v_profile,jsonb_build_object(
        'actor_authz_version',p_authz,'location_id',p_location,'row_version_before',p_before,
        'row_version_after',p_after,'recipe_revisions',v_links)) RETURNING public_id INTO v_event;
    RETURN v_event;
END;$fn$;

CREATE FUNCTION record_component_food_write_v26(p_actor bigint,p_authz bigint,p_location bigint,
    p_component bigint,p_before bigint,p_after bigint) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v menu_components%ROWTYPE; v_food uuid; v_event uuid;
BEGIN
    PERFORM begin_menu_binding_write_v26(p_actor,p_authz,p_location);
    IF p_before IS NULL OR p_after IS NULL OR p_before<0 OR p_after<=0 OR p_after-1<>p_before THEN
        RAISE EXCEPTION 'Ungültiger Versionswechsel.' USING ERRCODE='P1901';
    END IF;
    SELECT * INTO v FROM menu_components WHERE id=p_component AND location_id=p_location FOR UPDATE;
    IF NOT FOUND OR v.row_version<>p_after THEN
        RAISE EXCEPTION 'Komponente wurde geändert.' USING ERRCODE='55000';
    END IF;
    IF EXISTS(SELECT 1 FROM audit_events WHERE entity_type='menu_component' AND entity_public_id=v.public_id
        AND action='component.food_saved' AND details->>'row_version_after'=p_after::text) THEN
        RAISE EXCEPTION 'Versionswechsel bereits protokolliert.' USING ERRCODE='55000';
    END IF;
    SELECT public_id INTO v_food FROM foods WHERE id=v.food_id;
    INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
    VALUES(p_actor,'component.food_saved','menu_component',v.public_id,jsonb_build_object(
        'actor_authz_version',p_authz,'location_id',p_location,'row_version_before',p_before,
        'row_version_after',p_after,'food_public_id',v_food)) RETURNING public_id INTO v_event;
    RETURN v_event;
END;$fn$;

-- Private implementation: only literal-action wrappers below are app-callable.
CREATE FUNCTION dish_template_mutate_v26(p_action text,p_actor bigint,p_authz bigint,p_location bigint,
    p_target uuid,p_expected timestamptz,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v dish_templates%ROWTYPE; old_recipe bigint; next_recipe bigint; next_type smallint;
    next_title text; next_description text; next_scope text; v_recipe uuid; before_time timestamptz; verb text;
BEGIN
    PERFORM begin_menu_binding_write_v26(p_actor,p_authz,p_location);
    IF p_action NOT IN ('create','update','active') OR p_action IS NULL THEN
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
    IF p_action='active' THEN
        PERFORM master_payload(p_payload,ARRAY['active']);
        IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
            RAISE EXCEPTION 'Aktivstatus erforderlich.' USING ERRCODE='P1901';
        END IF;
        next_recipe:=old_recipe;
    ELSE
        PERFORM master_payload(p_payload,ARRAY['menu_type_code','profile_scope','title','description','recipe_public_id']);
        IF NOT p_payload ?& ARRAY['menu_type_code','profile_scope','title','description','recipe_public_id']
           OR EXISTS(SELECT 1 FROM jsonb_each(p_payload) f WHERE jsonb_typeof(f.value) NOT IN ('string','null'))
           OR p_payload->>'profile_scope' IS NULL
           OR p_payload->>'profile_scope' NOT IN ('common','patient','staff_guest') THEN
            RAISE EXCEPTION 'Ungültige Vorlagenfelder.' USING ERRCODE='P1901';
        END IF;
        next_title:=master_text(p_payload->>'title',120);
        next_description:=master_text(p_payload->>'description',2000,false);
        next_scope:=p_payload->>'profile_scope';
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
    END IF;
    PERFORM id FROM recipes WHERE id IN (old_recipe,next_recipe) ORDER BY id FOR SHARE;
    IF p_action<>'create' THEN
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
        INSERT INTO dish_templates(menu_type_id,profile_scope,title,description,recipe_id)
        VALUES(next_type,next_scope,next_title,next_description,next_recipe) RETURNING * INTO v;
        verb:='created';
    ELSIF p_action='update' THEN
        IF (v.menu_type_id,v.profile_scope,v.title,v.description,v.recipe_id) IS NOT DISTINCT FROM
            (next_type,next_scope,next_title,next_description,next_recipe) THEN
            RETURN jsonb_build_object('public_id',v.public_id,'updated_at',v.updated_at,'active',v.active);
        END IF;
        UPDATE dish_templates SET menu_type_id=next_type,profile_scope=next_scope,title=next_title,
            description=next_description,recipe_id=next_recipe WHERE id=v.id RETURNING * INTO v;
        verb:='updated';
    ELSE
        IF v.active=(p_payload->>'active')::boolean THEN
            RAISE EXCEPTION 'Aktivstatus ist unverändert.' USING ERRCODE='55000';
        END IF;
        UPDATE dish_templates SET active=(p_payload->>'active')::boolean WHERE id=v.id RETURNING * INTO v;
        verb:=CASE WHEN v.active THEN 'reactivated' ELSE 'archived' END;
    END IF;
    SELECT public_id INTO v_recipe FROM recipes WHERE id=v.recipe_id;
    INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
    VALUES(p_actor,'dish_template.'||verb,'dish_template',v.public_id,jsonb_build_object(
        'actor_authz_version',p_authz,'location_id',p_location,'updated_at_before',before_time,
        'updated_at_after',v.updated_at,'recipe_public_id',v_recipe));
    RETURN jsonb_build_object('public_id',v.public_id,'updated_at',v.updated_at,'active',v.active);
END;$fn$;

CREATE FUNCTION create_dish_template_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
    SELECT dish_template_mutate_v26('create',$1,$2,$3,$4,$5,$6);
$fn$;
CREATE FUNCTION update_dish_template_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
    SELECT dish_template_mutate_v26('update',$1,$2,$3,$4,$5,$6);
$fn$;
CREATE FUNCTION set_dish_template_active_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
    SELECT dish_template_mutate_v26('active',$1,$2,$3,$4,$5,$6);
$fn$;

REVOKE ALL ON FUNCTION validate_menu_recipe_scope_v26(),validate_dish_recipe_scope_v26(),
    validate_menu_dish_scope_v26(),begin_menu_binding_write_v26(bigint,bigint,bigint),
    lock_menu_recipe_revisions_v26(bigint,bigint,bigint,bigint[]),
    lock_component_foods_v26(bigint,bigint,bigint,bigint[]),
    record_menu_binding_write_v26(bigint,bigint,bigint,bigint,bigint,bigint),
    record_component_food_write_v26(bigint,bigint,bigint,bigint,bigint,bigint),
    dish_template_mutate_v26(text,bigint,bigint,bigint,uuid,timestamptz,jsonb),
    create_dish_template_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb),
    update_dish_template_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb),
    set_dish_template_active_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION begin_menu_binding_write_v26(bigint,bigint,bigint),
    lock_menu_recipe_revisions_v26(bigint,bigint,bigint,bigint[]),
    lock_component_foods_v26(bigint,bigint,bigint,bigint[]),
    record_menu_binding_write_v26(bigint,bigint,bigint,bigint,bigint,bigint),
    record_component_food_write_v26(bigint,bigint,bigint,bigint,bigint,bigint),
    create_dish_template_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb),
    update_dish_template_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb),
    set_dish_template_active_v26(bigint,bigint,bigint,uuid,timestamptz,jsonb)
TO cafeteria_app;

COMMIT;
