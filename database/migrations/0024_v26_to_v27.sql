BEGIN;
SET search_path TO cafeteria, public;

-- Fail before DDL, sequences or ledger writes; an explicit v21 backfill is separate.
-- Reference class before aggregates; take the final DDL mode now, avoiding upgrades.
LOCK TABLE storage_locations IN SHARE MODE;
LOCK TABLE foods, food_storage_locations IN ACCESS EXCLUSIVE MODE;
DO $preflight$
DECLARE missing bigint; examples text;
BEGIN
    SELECT count(*) INTO missing FROM foods f WHERE NOT EXISTS (
        SELECT 1 FROM food_storage_locations l JOIN storage_locations s
          ON s.id=l.storage_location_id AND s.location_id=l.location_id
        WHERE l.food_id=f.id AND l.location_id=f.location_id AND s.active);
    IF missing>0 THEN
        SELECT string_agg(public_id::text, ', ' ORDER BY public_id) INTO examples FROM (
            SELECT f.public_id FROM foods f WHERE NOT EXISTS (
                SELECT 1 FROM food_storage_locations l JOIN storage_locations s
                  ON s.id=l.storage_location_id AND s.location_id=l.location_id
                WHERE l.food_id=f.id AND l.location_id=f.location_id AND s.active)
            ORDER BY f.public_id LIMIT 20) gaps;
        RAISE EXCEPTION 'Lagerzuordnung fehlt für % Zutaten. Beispiele: %', missing, examples
            USING ERRCODE='55000', DETAIL='food_storage_preflight';
    END IF;
END;$preflight$;

ALTER TABLE foods ADD COLUMN prepared_recipe_revision_id bigint;
ALTER TABLE foods ADD CONSTRAINT foods_prepared_recipe_scope_fk
    FOREIGN KEY(location_id,prepared_recipe_revision_id)
    REFERENCES recipe_revisions(location_id,id) ON DELETE RESTRICT;
CREATE INDEX foods_prepared_recipe_idx ON foods(prepared_recipe_revision_id)
    WHERE prepared_recipe_revision_id IS NOT NULL;

CREATE OR REPLACE FUNCTION protect_master_data() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'Archive instead of deleting master data.' USING ERRCODE='55000';
    END IF;
    IF NEW.id<>OLD.id OR NEW.public_id<>OLD.public_id OR NEW.created_at<>OLD.created_at
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR to_jsonb(NEW)->'location_id' IS DISTINCT FROM to_jsonb(OLD)->'location_id'
       OR to_jsonb(NEW)->'code' IS DISTINCT FROM to_jsonb(OLD)->'code' THEN
        RAISE EXCEPTION 'Immutable master identity.' USING ERRCODE='55000';
    END IF;
    IF TG_TABLE_NAME='measurement_units' THEN
        IF NEW.dimension<>OLD.dimension OR NEW.base_factor IS DISTINCT FROM OLD.base_factor
            OR (OLD.code IN ('G','ML','STK') AND NOT NEW.active) THEN
            RAISE EXCEPTION 'Immutable unit semantics.' USING ERRCODE='55000';
        END IF;
    ELSIF TG_TABLE_NAME='foods' THEN
        IF (to_jsonb(NEW)-ARRAY['name','category_id','base_unit_id','density_g_per_ml','piece_weight_g',
            'note','active','allergen_review_status','updated_at','updated_by','row_version','prepared_recipe_revision_id'])
            IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['name','category_id','base_unit_id','density_g_per_ml',
            'piece_weight_g','note','active','allergen_review_status','updated_at','updated_by','row_version','prepared_recipe_revision_id']) THEN
            RAISE EXCEPTION 'Immutable food origin.' USING ERRCODE='55000';
        END IF;
    END IF;
    RETURN NEW;
END;
$fn$;
CREATE FUNCTION lock_prepared_graph_v27(p_location bigint) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    -- Only called after the original actor/location guard, before all row locks.
    PERFORM pg_advisory_xact_lock(hashtextextended('cafeteria.prepared_food_graph:'||p_location::text,2700909));
END;$fn$;

CREATE FUNCTION recipe_snapshot_complete_v27(p_snapshot jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE item jsonb;
BEGIN
    IF COALESCE(p_snapshot->>'schema_version','') NOT IN ('1','2') OR
       jsonb_typeof(p_snapshot->'recipe'->'ingredients') IS DISTINCT FROM 'array' THEN
        RETURN false;
    END IF;
    IF jsonb_array_length(p_snapshot->'recipe'->'ingredients') NOT BETWEEN 1 AND 64 THEN RETURN false; END IF;
    FOR item IN SELECT value FROM jsonb_array_elements(p_snapshot->'recipe'->'ingredients') LOOP
        IF item->>'food_public_id' IS NULL OR
           item->>'food_public_id' !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' OR
           item->>'unit_code' IS NULL OR item->>'unit_code' !~ '^[A-Z][A-Z0-9_]{0,15}$' OR
           NOT master_quantity((item->>'quantity')::numeric) THEN RETURN false; END IF;
    END LOOP;
    RETURN true;
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN RETURN false;
END;$fn$;

-- Current semantic Food graph, deliberately distinct from frozen rendering.
CREATE FUNCTION check_prepared_graph_v27(p_location bigint,p_food uuid,p_revision bigint) RETURNS void
LANGUAGE plpgsql STABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE queue jsonb:=jsonb_build_array(jsonb_build_object('food',p_food,'foods','[]'::jsonb,
        'recipes','[]'::jsonb,'depth',0)); cursor_pos integer:=0; work integer:=1;
    node jsonb; ingredient jsonb; current_food foods%ROWTYPE; revision recipe_revisions%ROWTYPE;
    seen jsonb:='{}'; next_revision bigint;
BEGIN
    WHILE cursor_pos<jsonb_array_length(queue) LOOP
        node:=queue->cursor_pos; cursor_pos:=cursor_pos+1;
        IF node->'foods' ? (node->>'food') THEN
            RAISE EXCEPTION 'Zutatenkreis ist nicht erlaubt.' USING ERRCODE='55000';
        END IF;
        SELECT * INTO current_food FROM foods WHERE public_id=(node->>'food')::uuid AND location_id=p_location;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannte verknüpfte Zutat.' USING ERRCODE='22023'; END IF;
        next_revision:=CASE WHEN current_food.public_id=p_food THEN p_revision ELSE current_food.prepared_recipe_revision_id END;
        IF next_revision IS NULL THEN CONTINUE; END IF;
        SELECT * INTO revision FROM recipe_revisions WHERE id=next_revision AND location_id=p_location;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannte Zubereitungsrevision.' USING ERRCODE='22023'; END IF;
        IF node->'recipes' ? revision.recipe_id::text THEN
            RAISE EXCEPTION 'Rezeptkreis ist nicht erlaubt.' USING ERRCODE='55000';
        END IF;
        IF NOT recipe_snapshot_complete_v27(revision.snapshot_json) THEN
            RAISE EXCEPTION 'Zubereitung benötigt vollständige Mengen und Zutaten.' USING ERRCODE='P1901';
        END IF;
        IF NOT seen ? revision.public_id::text THEN
            IF (SELECT count(*) FROM jsonb_object_keys(seen))>=64 THEN
                RAISE EXCEPTION 'Höchstens 64 Unterrevisionen.' USING ERRCODE='P1901';
            END IF;
            seen:=seen||jsonb_build_object(revision.public_id::text,true);
        END IF;
        FOR ingredient IN SELECT value FROM jsonb_array_elements(revision.snapshot_json->'recipe'->'ingredients') LOOP
            IF (node->>'depth')::integer>=8 OR work>=4096 THEN
                RAISE EXCEPTION 'Zubereitungsgraph überschreitet die Grenze.' USING ERRCODE='P1901';
            END IF;
            work:=work+1;
            queue:=queue||jsonb_build_array(jsonb_build_object('food',ingredient->>'food_public_id',
                'foods',(node->'foods')||jsonb_build_array(current_food.public_id::text),
                'recipes',(node->'recipes')||jsonb_build_array(revision.recipe_id::text),
                'depth',(node->>'depth')::integer+1));
        END LOOP;
    END LOOP;
END;$fn$;

CREATE FUNCTION assert_food_complete_v27(p_food bigint) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE food foods%ROWTYPE; base measurement_units%ROWTYPE; revision recipe_revisions%ROWTYPE; unit jsonb;
BEGIN
    -- The public writer already owns this row. Deferred checks also serialize direct privileged DML.
    SELECT * INTO food FROM foods WHERE id=p_food FOR UPDATE;
    IF NOT FOUND THEN RETURN; END IF;
    IF NOT EXISTS(SELECT 1 FROM food_storage_locations l JOIN storage_locations s
        ON s.id=l.storage_location_id AND s.location_id=l.location_id
        WHERE l.food_id=food.id AND l.location_id=food.location_id AND s.active) THEN
        RAISE EXCEPTION 'Mindestens ein aktiver Lagerort ist erforderlich.' USING ERRCODE='55000';
    END IF;
    IF food.prepared_recipe_revision_id IS NULL THEN RETURN; END IF;
    SELECT * INTO revision FROM recipe_revisions WHERE id=food.prepared_recipe_revision_id AND location_id=food.location_id;
    IF NOT FOUND OR NOT recipe_snapshot_complete_v27(revision.snapshot_json) THEN
        RAISE EXCEPTION 'Vollständige standortgleiche Zubereitungsrevision erforderlich.' USING ERRCODE='P1901';
    END IF;
    PERFORM check_prepared_snapshot_v27(revision.snapshot_json,
        (SELECT public_id FROM recipes WHERE id=revision.recipe_id));
    SELECT * INTO base FROM measurement_units WHERE id=food.base_unit_id;
    SELECT value INTO unit FROM jsonb_array_elements(revision.snapshot_json->'units')
        WHERE value->>'code'=revision.snapshot_json->'recipe'->>'servings_unit_code';
    IF unit IS NULL OR NOT (
        (base.dimension<>'contextual' AND base.dimension=unit->>'dimension') OR
        (base.dimension='contextual' AND unit->>'dimension'='contextual' AND base.code=unit->>'code') OR
        (base.dimension IN ('mass','volume') AND unit->>'dimension' IN ('mass','volume') AND
         master_factor(food.density_g_per_ml))) THEN
        RAISE EXCEPTION 'Ausbeute passt nicht zur Basiseinheit der Zutat.' USING ERRCODE='P1901';
    END IF;
END;$fn$;

CREATE FUNCTION enforce_food_complete_v27() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE target bigint;
BEGIN
    IF TG_TABLE_NAME='foods' THEN
        PERFORM assert_food_complete_v27(NEW.id);
    ELSIF TG_TABLE_NAME='food_storage_locations' THEN
        IF TG_OP<>'INSERT' THEN PERFORM assert_food_complete_v27(OLD.food_id); END IF;
        IF TG_OP<>'DELETE' THEN PERFORM assert_food_complete_v27(NEW.food_id); END IF;
    ELSE
        FOR target IN SELECT food_id FROM food_storage_locations
            WHERE storage_location_id=NEW.id ORDER BY food_id LOOP
            PERFORM assert_food_complete_v27(target);
        END LOOP;
    END IF;
    RETURN NULL;
END;$fn$;
CREATE CONSTRAINT TRIGGER foods_complete_v27 AFTER INSERT OR UPDATE ON foods
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_food_complete_v27();
CREATE CONSTRAINT TRIGGER food_storage_complete_v27 AFTER INSERT OR UPDATE OR DELETE ON food_storage_locations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_food_complete_v27();
CREATE CONSTRAINT TRIGGER storage_food_complete_v27 AFTER UPDATE ON storage_locations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_food_complete_v27();

CREATE FUNCTION food_save_v27(p_create boolean,p_actor bigint,p_authz bigint,p_location bigint,
    p_target uuid,p_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE food foods%ROWTYPE; previous foods%ROWTYPE; refs jsonb; original_links jsonb;
    revision recipe_revisions%ROWTYPE; source_fields text[]:=ARRAY['source_kind','source_reference','source_url','source_note','fetched_at'];
    old_version bigint:=0; old_pin bigint; supplied_pin boolean; after_state jsonb; before_state jsonb;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_authz,'masterdata.write');
    PERFORM master_location(p_location);
    PERFORM lock_prepared_graph_v27(p_location);
    PERFORM master_payload(p_payload,ARRAY['name','category_public_id','base_unit_code','density_g_per_ml',
        'piece_weight_g','note','source_kind','source_reference','source_url','source_note','fetched_at',
        'storage_location_public_ids','prepared_recipe_revision_public_id','prepared_recipe_content_hash_sha256']);
    IF NOT p_payload ?& ARRAY['name','base_unit_code','storage_location_public_ids'] OR
       jsonb_typeof(p_payload->'storage_location_public_ids') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Zutat, Basiseinheit und Lagerorte sind erforderlich.' USING ERRCODE='P1901';
    END IF;
    IF jsonb_array_length(p_payload->'storage_location_public_ids') NOT BETWEEN 1 AND 64 OR
       EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'storage_location_public_ids') x WHERE jsonb_typeof(x)<>'string') OR
       jsonb_array_length(p_payload->'storage_location_public_ids')<>(SELECT count(DISTINCT x)
           FROM jsonb_array_elements(p_payload->'storage_location_public_ids') x) OR
       EXISTS(SELECT 1 FROM jsonb_each(p_payload-'storage_location_public_ids') f WHERE jsonb_typeof(f.value) NOT IN ('string','null')) THEN
        RAISE EXCEPTION 'Ungültige Zutatenfelder.' USING ERRCODE='P1901';
    END IF;
    supplied_pin:=p_payload ? 'prepared_recipe_revision_public_id';
    IF supplied_pin<>(p_payload ? 'prepared_recipe_content_hash_sha256') OR
       ((p_payload->>'prepared_recipe_revision_public_id' IS NULL)<>(p_payload->>'prepared_recipe_content_hash_sha256' IS NULL)) THEN
        RAISE EXCEPTION 'Vollständige Zubereitungsreferenz erforderlich.' USING ERRCODE='P1901';
    END IF;
    IF NOT p_create THEN
        PERFORM master_expectation(p_target,p_version);
        IF p_payload ?| source_fields THEN RAISE EXCEPTION 'Ursprung bleibt unverändert.' USING ERRCODE='P1901'; END IF;
    END IF;
    refs:=master_lock_food_refs((p_payload-ARRAY['prepared_recipe_revision_public_id','prepared_recipe_content_hash_sha256'])||
        jsonb_build_object('location_id',p_location,'storage_locations',p_payload->'storage_location_public_ids'));
    IF NOT p_create THEN
        SELECT * INTO food FROM foods WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannte Zutat.' USING ERRCODE='22023'; END IF;
        IF food.row_version<>p_version THEN RAISE EXCEPTION 'Zutat wurde geändert.' USING ERRCODE='55000'; END IF;
        previous:=food; old_version:=food.row_version; old_pin:=food.prepared_recipe_revision_id;
        original_links:=master_food_links(food.id);
        before_state:=to_jsonb(food)||original_links;
    END IF;
    IF supplied_pin OR p_create THEN
        food.prepared_recipe_revision_id:=NULL;
        IF p_payload->>'prepared_recipe_revision_public_id' IS NOT NULL THEN
            IF p_payload->>'prepared_recipe_content_hash_sha256' !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'Ungültiger Revisionshash.' USING ERRCODE='P1901';
            END IF;
            SELECT * INTO revision FROM recipe_revisions
                WHERE public_id=(p_payload->>'prepared_recipe_revision_public_id')::uuid AND location_id=p_location;
            IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannte Zubereitungsrevision.' USING ERRCODE='22023'; END IF;
            IF revision.content_hash_sha256<>p_payload->>'prepared_recipe_content_hash_sha256' THEN
                RAISE EXCEPTION 'Zubereitungsreferenz wurde geändert.' USING ERRCODE='55000';
            END IF;
            PERFORM id FROM recipes WHERE id=revision.recipe_id FOR SHARE;
            IF revision.id IS DISTINCT FROM old_pin AND EXISTS(SELECT 1 FROM recipes WHERE id=revision.recipe_id AND NOT active) THEN
                RAISE EXCEPTION 'Archivierte Zubereitung kann nicht neu gewählt werden.' USING ERRCODE='55000';
            END IF;
            food.prepared_recipe_revision_id:=revision.id;
        END IF;
    END IF;
    food.name:=master_text(p_payload->>'name',120);
    food.base_unit_id:=(refs->>'base_unit_id')::bigint;
    food.category_id:=(refs->>'category_id')::bigint;
    food.density_g_per_ml:=(p_payload->>'density_g_per_ml')::numeric;
    food.piece_weight_g:=(p_payload->>'piece_weight_g')::numeric;
    food.note:=master_text(COALESCE(p_payload->>'note',''),500,false);
    IF p_create THEN
        INSERT INTO foods(location_id,name,base_unit_id,category_id,density_g_per_ml,piece_weight_g,note,
            source_kind,source_reference,source_url,source_note,fetched_at,prepared_recipe_revision_id,created_by,updated_by)
        VALUES(p_location,food.name,food.base_unit_id,food.category_id,food.density_g_per_ml,food.piece_weight_g,food.note,
            COALESCE(p_payload->>'source_kind','manual'),master_text(p_payload->>'source_reference',200,false),
            master_text(p_payload->>'source_url',2048,false),master_text(p_payload->>'source_note',500,false),
            (p_payload->>'fetched_at')::timestamptz,food.prepared_recipe_revision_id,p_actor,p_actor) RETURNING * INTO food;
    ELSE
        IF food IS NOT DISTINCT FROM previous AND original_links->'storage_locations'=refs->'storage_locations' THEN
            PERFORM assert_food_complete_v27(food.id);
            RETURN jsonb_build_object('public_id',food.public_id,'row_version',food.row_version);
        END IF;
        UPDATE foods SET name=food.name,base_unit_id=food.base_unit_id,category_id=food.category_id,
            density_g_per_ml=food.density_g_per_ml,piece_weight_g=food.piece_weight_g,note=food.note,
            prepared_recipe_revision_id=food.prepared_recipe_revision_id,updated_by=p_actor
            WHERE id=food.id RETURNING * INTO food;
    END IF;
    PERFORM master_replace_food_links(food.id,p_location,jsonb_build_object('storage_locations',refs->'storage_locations'));
    PERFORM assert_food_complete_v27(food.id);
    PERFORM check_prepared_graph_v27(p_location,food.public_id,food.prepared_recipe_revision_id);
    after_state:=to_jsonb(food)||master_food_links(food.id);
    PERFORM master_audit(p_actor,p_authz,p_location,'food',food.public_id,
        CASE WHEN p_create THEN 'create' ELSE 'update' END,old_version,food.row_version,
        jsonb_build_object('before',before_state,'after',after_state));
    RETURN jsonb_build_object('public_id',food.public_id,'row_version',food.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR
    not_null_violation OR invalid_datetime_format THEN
    RAISE EXCEPTION 'Ungültige vollständige Zutat.' USING ERRCODE='P1901';
END;$fn$;

CREATE FUNCTION create_food_v27(bigint,bigint,bigint,jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
    SELECT food_save_v27(true,$1,$2,$3,NULL,NULL,$4);
$fn$;
CREATE FUNCTION update_food_v27(bigint,bigint,bigint,uuid,bigint,jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
    SELECT food_save_v27(false,$1,$2,$3,$4,$5,$6);
$fn$;

-- Worklist entries contain identities/path metadata, not repeated snapshot bodies.
CREATE FUNCTION check_prepared_snapshot_v27(p_snapshot jsonb,p_recipe uuid) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE queue jsonb:=jsonb_build_array(jsonb_build_object('revision',NULL,'recipes',jsonb_build_array(p_recipe::text),
        'foods','[]'::jsonb,'depth',0)); cursor_pos integer:=0; work integer:=1; expanded integer:=0;
    index_nodes jsonb:='{}'; used jsonb:='{}'; node jsonb; body jsonb; entry jsonb; ingredient jsonb; food jsonb; pin jsonb;
BEGIN
    IF octet_length(p_snapshot::text)>2097152 THEN
        RAISE EXCEPTION 'Rezeptabbild überschreitet 2 MiB.' USING ERRCODE='P1901';
    END IF;
    IF p_snapshot->>'schema_version'='2' THEN
        IF jsonb_typeof(p_snapshot->'prepared_revisions') IS DISTINCT FROM 'array' OR
           jsonb_array_length(p_snapshot->'prepared_revisions')>64 THEN
            RAISE EXCEPTION 'Ungültiger Unterrevisionsindex.' USING ERRCODE='P1901';
        END IF;
        FOR entry IN SELECT value FROM jsonb_array_elements(p_snapshot->'prepared_revisions') LOOP
            IF entry->>'revision_public_id' IS NULL OR index_nodes ? (entry->>'revision_public_id') THEN
                RAISE EXCEPTION 'Doppelte oder fehlende Unterrevision.' USING ERRCODE='P1901';
            END IF;
            index_nodes:=index_nodes||jsonb_build_object(entry->>'revision_public_id',entry);
        END LOOP;
    END IF;
    WHILE cursor_pos<jsonb_array_length(queue) LOOP
        node:=queue->cursor_pos; cursor_pos:=cursor_pos+1;
        body:=CASE WHEN node->>'revision' IS NULL THEN p_snapshot ELSE index_nodes->(node->>'revision')->'snapshot' END;
        IF NOT recipe_snapshot_complete_v27(body) THEN
            RAISE EXCEPTION 'Zutaten und Mengen müssen vollständig sein.' USING ERRCODE='P1901';
        END IF;
        expanded:=expanded+jsonb_array_length(body->'recipe'->'ingredients');
        IF expanded>4096 THEN RAISE EXCEPTION 'Mehr als 4096 Zutatenverwendungen.' USING ERRCODE='P1901'; END IF;
        FOR ingredient IN SELECT value FROM jsonb_array_elements(body->'recipe'->'ingredients') LOOP
            IF node->'foods' ? (ingredient->>'food_public_id') THEN
                RAISE EXCEPTION 'Zutatenkreis im Rezeptabbild.' USING ERRCODE='55000';
            END IF;
            -- Old v1 is terminal: never reinterpret its Foods using current pins.
            IF body->>'schema_version'='1' THEN CONTINUE; END IF;
            SELECT value INTO food FROM jsonb_array_elements(body->'foods')
                WHERE value->>'public_id'=ingredient->>'food_public_id';
            IF NOT FOUND THEN RAISE EXCEPTION 'Zutat fehlt im Rezeptabbild.' USING ERRCODE='P1901'; END IF;
            pin:=food->'prepared_recipe';
            IF pin IS NULL OR pin='null'::jsonb THEN CONTINUE; END IF;
            entry:=index_nodes->(pin->>'revision_public_id');
            IF entry IS NULL OR entry->>'recipe_public_id' IS DISTINCT FROM pin->>'recipe_public_id' OR
               entry->>'content_hash_sha256' IS DISTINCT FROM pin->>'content_hash_sha256' THEN
                RAISE EXCEPTION 'Unterrevisionsindex passt nicht zum Pin.' USING ERRCODE='P1901';
            END IF;
            IF node->'recipes' ? (pin->>'recipe_public_id') THEN
                RAISE EXCEPTION 'Rezeptkreis im Rezeptabbild.' USING ERRCODE='55000';
            END IF;
            IF (node->>'depth')::integer>=8 OR work>=4096 THEN
                RAISE EXCEPTION 'Rezeptverschachtelung überschreitet die Grenze.' USING ERRCODE='P1901';
            END IF;
            used:=used||jsonb_build_object(pin->>'revision_public_id',true);
            work:=work+1;
            queue:=queue||jsonb_build_array(jsonb_build_object('revision',pin->>'revision_public_id',
                'recipes',(node->'recipes')||jsonb_build_array(pin->>'recipe_public_id'),
                'foods',(node->'foods')||jsonb_build_array(ingredient->>'food_public_id'),
                'depth',(node->>'depth')::integer+1));
        END LOOP;
    END LOOP;
    IF (SELECT count(*) FROM jsonb_object_keys(used))<>(SELECT count(*) FROM jsonb_object_keys(index_nodes)) THEN
        RAISE EXCEPTION 'Unterrevisionsindex enthält unbenutzte Einträge.' USING ERRCODE='P1901';
    END IF;
END;$fn$;

CREATE FUNCTION merge_prepared_node_v27(p_nodes jsonb,p_node jsonb) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE key text:=p_node->>'revision_public_id';
BEGIN
    IF key IS NULL OR octet_length(p_node::text)>2097152 THEN
        RAISE EXCEPTION 'Ungültiges Unterrezeptabbild.' USING ERRCODE='P1901';
    END IF;
    IF p_nodes ? key THEN
        IF p_nodes->key IS DISTINCT FROM p_node THEN
            RAISE EXCEPTION 'Widersprüchliche Unterrevision.' USING ERRCODE='55000';
        END IF;
        RETURN p_nodes;
    END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(p_nodes))>=64 OR
       octet_length(p_nodes::text)+octet_length(p_node::text)>2097152 THEN
        RAISE EXCEPTION 'Unterrevisionsindex überschreitet die Grenze.' USING ERRCODE='P1901';
    END IF;
    RETURN p_nodes||jsonb_build_object(key,p_node);
END;$fn$;

CREATE FUNCTION recipe_dependency_preview_v27(p_location bigint,p_target uuid,p_version bigint) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE recipe recipes%ROWTYPE; snapshot jsonb; food_json jsonb; food foods%ROWTYPE;
    revision recipe_revisions%ROWTYPE; child_recipe uuid; prepared jsonb; entry jsonb;
    food_rows jsonb:='[]'; nodes jsonb:='{}'; issues jsonb:='[]'; unit_rows jsonb; result jsonb;
BEGIN
    PERFORM master_expectation(p_target,p_version);
    IF p_location IS NULL OR NOT EXISTS(SELECT 1 FROM locations WHERE id=p_location AND active) OR
       (SELECT count(*) FROM locations WHERE active)<>1 THEN
        RAISE EXCEPTION 'Ursprünglicher Standort ist nicht mehr aktiv.' USING ERRCODE='55000';
    END IF;
    SELECT * INTO recipe FROM recipes WHERE public_id=p_target AND location_id=p_location;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unbekanntes Rezept.' USING ERRCODE='22023'; END IF;
    IF recipe.row_version<>p_version THEN RAISE EXCEPTION 'Rezept wurde geändert.' USING ERRCODE='55000'; END IF;
    snapshot:=recipe_snapshot_v22(recipe.id);
    IF NOT recipe_snapshot_complete_v27(snapshot) THEN
        issues:=jsonb_build_array(jsonb_build_object('field','ingredients','code','incomplete'));
    END IF;
    SELECT COALESCE(jsonb_agg(jsonb_build_object('public_id',u.public_id,'code',u.code,
        'display_name',u.display_name,'dimension',u.dimension,'base_factor',trim_scale(u.base_factor)::text)
        ORDER BY u.public_id),'[]') INTO unit_rows FROM measurement_units u WHERE u.id=recipe.servings_unit_id OR
        u.id IN(SELECT i.unit_id FROM recipe_ingredients i WHERE i.recipe_id=recipe.id) OR
        u.id IN(SELECT f.base_unit_id FROM foods f JOIN recipe_ingredients i ON i.food_id=f.id WHERE i.recipe_id=recipe.id);
    FOR food_json IN SELECT value FROM jsonb_array_elements(snapshot->'foods') ORDER BY value->>'public_id' LOOP
        SELECT * INTO food FROM foods WHERE public_id=(food_json->>'public_id')::uuid AND location_id=p_location;
        prepared:='null'::jsonb;
        IF food.prepared_recipe_revision_id IS NOT NULL THEN
            SELECT * INTO revision FROM recipe_revisions WHERE id=food.prepared_recipe_revision_id AND location_id=p_location;
            IF NOT FOUND THEN RAISE EXCEPTION 'Zubereitungsrevision fehlt.' USING ERRCODE='22023'; END IF;
            SELECT public_id INTO child_recipe FROM recipes WHERE id=revision.recipe_id;
            PERFORM check_prepared_snapshot_v27(revision.snapshot_json,child_recipe);
            prepared:=jsonb_build_object('recipe_public_id',child_recipe,'revision_public_id',revision.public_id,
                'content_hash_sha256',revision.content_hash_sha256);
            entry:=prepared||jsonb_build_object('snapshot',revision.snapshot_json-'prepared_revisions');
            nodes:=merge_prepared_node_v27(nodes,entry);
            IF revision.snapshot_json->>'schema_version'='2' THEN
                FOR entry IN SELECT value FROM jsonb_array_elements(revision.snapshot_json->'prepared_revisions') LOOP
                    nodes:=merge_prepared_node_v27(nodes,entry);
                END LOOP;
            END IF;
        END IF;
        food_json:=food_json||jsonb_build_object('prepared_recipe',prepared,'base_unit',(
            SELECT jsonb_build_object('public_id',u.public_id,'code',u.code,'display_name',u.display_name,
                'dimension',u.dimension,'base_factor',trim_scale(u.base_factor)::text) FROM measurement_units u WHERE id=food.base_unit_id),
            'storage_locations',(SELECT COALESCE(jsonb_agg(jsonb_build_object('public_id',s.public_id,
                'row_version',s.row_version,'code',s.code,'name',s.name,'active',s.active) ORDER BY s.public_id),'[]')
                FROM food_storage_locations l JOIN storage_locations s ON s.id=l.storage_location_id AND s.location_id=l.location_id
                WHERE l.food_id=food.id AND l.location_id=p_location));
        food_rows:=food_rows||jsonb_build_array(food_json);
    END LOOP;
    snapshot:=snapshot||jsonb_build_object('schema_version',2,'units',unit_rows,'foods',food_rows,
        'prepared_revisions',(SELECT COALESCE(jsonb_agg(value ORDER BY key),'[]') FROM jsonb_each(nodes)));
    IF octet_length(snapshot::text)>2097152 THEN RAISE EXCEPTION 'Rezeptabbild überschreitet 2 MiB.' USING ERRCODE='P1901'; END IF;
    IF issues='[]'::jsonb THEN PERFORM check_prepared_snapshot_v27(snapshot,recipe.public_id); END IF;
    result:=jsonb_build_object('recipe_public_id',recipe.public_id,'recipe_row_version',recipe.row_version,
        'complete',issues='[]'::jsonb,'issues',issues,'snapshot',snapshot);
    RETURN result||jsonb_build_object('dependency_hash_sha256',encode(public.digest(convert_to(result::text,'UTF8'),'sha256'),'hex'));
END;$fn$;

CREATE FUNCTION freeze_recipe_v27(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,
    p_version bigint,p_dependency text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE recipe recipes%ROWTYPE; preview jsonb; snapshot jsonb; revision recipe_revisions%ROWTYPE;
    previous recipe_revisions%ROWTYPE; food foods%ROWTYPE; digest_value text;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_authz,'recipe.write');
    PERFORM master_location(p_location);
    PERFORM lock_prepared_graph_v27(p_location);
    PERFORM master_expectation(p_target,p_version);
    IF p_dependency IS NULL OR p_dependency !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Ursprünglicher Abhängigkeitshash erforderlich.' USING ERRCODE='P1901';
    END IF;
    SELECT * INTO recipe FROM recipes WHERE public_id=p_target AND location_id=p_location;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unbekanntes Rezept.' USING ERRCODE='22023'; END IF;
    -- Base units and recorded storage names are dependencies too; lock before Foods.
    PERFORM u.id FROM measurement_units u WHERE u.id=recipe.servings_unit_id OR
        u.id IN(SELECT unit_id FROM recipe_ingredients WHERE recipe_id=recipe.id) OR
        u.id IN(SELECT f.base_unit_id FROM foods f JOIN recipe_ingredients i ON i.food_id=f.id WHERE i.recipe_id=recipe.id)
        ORDER BY u.id FOR SHARE;
    PERFORM t.id FROM tags t JOIN recipe_tags rt ON rt.tag_id=t.id
        WHERE rt.recipe_id=recipe.id ORDER BY t.id FOR SHARE OF t;
    PERFORM s.id FROM storage_locations s JOIN food_storage_locations l ON l.storage_location_id=s.id
        WHERE l.food_id IN(SELECT food_id FROM recipe_ingredients WHERE recipe_id=recipe.id) ORDER BY s.id FOR SHARE OF s;
    PERFORM recipe_refs_v22(p_location,recipe.id,recipe_payload_v22(recipe.id));
    SELECT * INTO recipe FROM recipes WHERE id=recipe.id FOR UPDATE;
    IF recipe.row_version<>p_version OR NOT recipe.active THEN
        RAISE EXCEPTION 'Rezept wurde geändert oder archiviert.' USING ERRCODE='55000';
    END IF;
    preview:=recipe_dependency_preview_v27(p_location,p_target,p_version);
    IF preview->>'dependency_hash_sha256'<>p_dependency THEN
        RAISE EXCEPTION 'Zutatenabhängigkeiten wurden geändert.' USING ERRCODE='55000';
    END IF;
    IF NOT (preview->>'complete')::boolean THEN
        RAISE EXCEPTION 'Rezept benötigt vollständige Zutaten und Mengen.' USING ERRCODE='P1901';
    END IF;
    FOR food IN SELECT f.* FROM foods f WHERE f.id IN(
        SELECT food_id FROM recipe_ingredients WHERE recipe_id=recipe.id) ORDER BY f.id LOOP
        PERFORM check_prepared_graph_v27(p_location,food.public_id,food.prepared_recipe_revision_id);
    END LOOP;
    snapshot:=preview->'snapshot';
    digest_value:=encode(public.digest(convert_to(snapshot::text,'UTF8'),'sha256'),'hex');
    SELECT * INTO previous FROM recipe_revisions WHERE recipe_id=recipe.id ORDER BY revision_number DESC LIMIT 1;
    IF FOUND AND previous.snapshot_json=snapshot THEN
        RAISE EXCEPTION 'Identische Revision bereits vorhanden.' USING ERRCODE='55000';
    END IF;
    INSERT INTO recipe_revisions(location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
        VALUES(p_location,recipe.id,COALESCE(previous.revision_number,0)+1,snapshot,digest_value,p_actor) RETURNING * INTO revision;
    UPDATE recipes SET updated_by=p_actor WHERE id=recipe.id RETURNING * INTO recipe;
    INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
        VALUES(p_actor,'recipe.freeze','recipe',recipe.public_id,jsonb_build_object('actor_authz_version',p_authz,
            'location_id',p_location,'row_version_before',p_version,'row_version_after',recipe.row_version,
            'revision_public_id',revision.public_id,'content_hash_sha256',digest_value,'dependency_hash_sha256',p_dependency));
    RETURN jsonb_build_object('public_id',revision.public_id,'recipe_public_id',recipe.public_id,
        'revision_number',revision.revision_number,'recipe_row_version',recipe.row_version,'content_hash_sha256',digest_value);
END;$fn$;

REVOKE ALL ON FUNCTION lock_prepared_graph_v27(bigint),recipe_snapshot_complete_v27(jsonb),
    check_prepared_graph_v27(bigint,uuid,bigint),assert_food_complete_v27(bigint),enforce_food_complete_v27(),
    food_save_v27(boolean,bigint,bigint,bigint,uuid,bigint,jsonb),check_prepared_snapshot_v27(jsonb,uuid),
    merge_prepared_node_v27(jsonb,jsonb),create_food_v27(bigint,bigint,bigint,jsonb),
    update_food_v27(bigint,bigint,bigint,uuid,bigint,jsonb),recipe_dependency_preview_v27(bigint,uuid,bigint),
    freeze_recipe_v27(bigint,bigint,bigint,uuid,bigint,text)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
REVOKE ALL ON FUNCTION create_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
    freeze_recipe_revision_v22(bigint,bigint,bigint,uuid,bigint,jsonb)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION create_food_v27(bigint,bigint,bigint,jsonb),
    update_food_v27(bigint,bigint,bigint,uuid,bigint,jsonb),recipe_dependency_preview_v27(bigint,uuid,bigint),
    freeze_recipe_v27(bigint,bigint,bigint,uuid,bigint,text) TO cafeteria_app;

COMMIT;
