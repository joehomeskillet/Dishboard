BEGIN;
SET search_path TO cafeteria, public;

CREATE FUNCTION recipe_text_v22(p_value text,p_max integer,p_required boolean DEFAULT true)
RETURNS text LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v text;
BEGIN
 IF p_value IS NULL THEN
  IF p_required THEN RAISE EXCEPTION 'Missing text.' USING ERRCODE='P1901'; END IF;
  RETURN NULL;
 END IF;
 v:=normalize(replace(replace(p_value,E'\r\n',E'\n'),E'\r',E'\n'),NFC);
 PERFORM master_text(replace(v,E'\n',''),2147483647,false);
 v:=regexp_replace(v,U&'^[\000A \00A0\1680\2000-\200A\2028\2029\202F\205F\3000]+|[\000A \00A0\1680\2000-\200A\2028\2029\202F\205F\3000]+$','','g');
 IF length(v)>p_max OR (p_required AND v='') THEN
  RAISE EXCEPTION 'Invalid text length.' USING ERRCODE='P1901';
 END IF;
 RETURN v;
END;$fn$;

CREATE TABLE recipes (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
 location_id bigint NOT NULL REFERENCES locations(id), UNIQUE(location_id,id),
 row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 created_by bigint NOT NULL REFERENCES users(id), updated_by bigint NOT NULL REFERENCES users(id),
 title text NOT NULL CHECK(title=master_text(title,120)),
 description text CHECK(description=recipe_text_v22(description,2000,false)),
 servings numeric NOT NULL CHECK(master_quantity(servings)),
 servings_unit_id bigint NOT NULL REFERENCES measurement_units(id) ON DELETE RESTRICT,
 prep_minutes integer CHECK(prep_minutes BETWEEN 0 AND 10080),
 cook_minutes integer CHECK(cook_minutes BETWEEN 0 AND 10080),
 source_kind text NOT NULL CHECK(source_kind IN ('manual','url','file_import','ai_assisted')),
 source_reference text CHECK(source_reference=master_text(source_reference,200,false)),
 source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
 source_note text CHECK(source_note=master_text(source_note,500,false)), fetched_at timestamptz,
 active boolean NOT NULL DEFAULT true,
 CHECK(source_kind='manual' OR (nullif(source_reference,'') IS NOT NULL AND fetched_at IS NOT NULL)),
 CHECK(source_kind<>'url' OR nullif(source_url,'') IS NOT NULL),
 CHECK(source_kind NOT IN ('file_import','ai_assisted') OR nullif(source_note,'') IS NOT NULL)
);
CREATE TABLE recipe_assets (
 location_id bigint NOT NULL REFERENCES locations(id),
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 image_data bytea NOT NULL CHECK(octet_length(image_data) BETWEEN 1 AND 1048576),
 content_type text NOT NULL CHECK(content_type IN ('image/png','image/jpeg')),
 width integer NOT NULL CHECK(width BETWEEN 1 AND 10000),
 height integer NOT NULL CHECK(height BETWEEN 1 AND 10000),
 created_by bigint NOT NULL REFERENCES users(id),created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(location_id,sha256),
 CHECK(sha256=encode(public.digest(image_data,'sha256'),'hex')),
 CHECK((content_type='image/png' AND substring(image_data FROM 1 FOR 8)=decode('89504e470d0a1a0a','hex'))
    OR (content_type='image/jpeg' AND substring(image_data FROM 1 FOR 3)=decode('ffd8ff','hex')))
);
CREATE TABLE recipe_ingredients (
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,sort_order smallint NOT NULL CHECK(sort_order BETWEEN 1 AND 64),
 line_public_id uuid NOT NULL DEFAULT gen_random_uuid(),UNIQUE(recipe_id,line_public_id),
 group_label text CHECK(group_label=master_text(group_label,120,false)),
 ingredient_text text NOT NULL CHECK(ingredient_text=master_text(ingredient_text,500)),
 food_id bigint, quantity numeric CHECK(quantity IS NULL OR master_quantity(quantity)),unit_id bigint REFERENCES measurement_units(id) ON DELETE RESTRICT,
 note text CHECK(note=master_text(note,500,false)),
 source_kind text NOT NULL CHECK(source_kind IN ('manual','url','file_import','ai_assisted')),
 source_reference text CHECK(source_reference=master_text(source_reference,200,false)),fetched_at timestamptz,
 PRIMARY KEY(recipe_id,sort_order),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT,
 CHECK((quantity IS NULL)=(unit_id IS NULL)),
 CHECK(source_kind='manual' OR (nullif(source_reference,'') IS NOT NULL AND fetched_at IS NOT NULL))
);
CREATE TABLE recipe_steps (
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,step_number smallint NOT NULL CHECK(step_number BETWEEN 1 AND 64),
 instruction text NOT NULL CHECK(instruction=recipe_text_v22(instruction,8000)),
 duration_minutes integer CHECK(duration_minutes BETWEEN 0 AND 10080),image_sha256 text,
 PRIMARY KEY(recipe_id,step_number),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,image_sha256) REFERENCES recipe_assets(location_id,sha256) ON DELETE RESTRICT
);
CREATE TABLE recipe_images (
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,sort_order smallint NOT NULL CHECK(sort_order BETWEEN 1 AND 64),
 sha256 text NOT NULL,caption text CHECK(caption=master_text(caption,500,false)),
 source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
 source_license text CHECK(source_license=master_text(source_license,500,false)),fetched_at timestamptz,
 PRIMARY KEY(recipe_id,sort_order),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,sha256) REFERENCES recipe_assets(location_id,sha256) ON DELETE RESTRICT,
 CHECK(source_url IS NULL OR (nullif(source_license,'') IS NOT NULL AND fetched_at IS NOT NULL))
);
CREATE TABLE recipe_tags (
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,tag_id bigint NOT NULL,
 PRIMARY KEY(recipe_id,tag_id),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,tag_id) REFERENCES tags(location_id,id) ON DELETE RESTRICT
);
CREATE TABLE recipe_revisions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
 location_id bigint NOT NULL,recipe_id bigint NOT NULL,revision_number bigint NOT NULL CHECK(revision_number>0),
 snapshot_json jsonb NOT NULL CHECK(jsonb_typeof(snapshot_json)='object'),
 content_hash_sha256 text NOT NULL CHECK(content_hash_sha256 ~ '^[0-9a-f]{64}$'),
 created_by bigint NOT NULL REFERENCES users(id),created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(location_id,id),UNIQUE(recipe_id,revision_number),
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT,
 CHECK(content_hash_sha256=encode(public.digest(convert_to(snapshot_json::text,'UTF8'),'sha256'),'hex'))
);
CREATE TABLE cookbooks (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
 location_id bigint NOT NULL REFERENCES locations(id),UNIQUE(location_id,id),
 name text NOT NULL CHECK(name=master_text(name,120)),description text CHECK(description=recipe_text_v22(description,2000,false)),
 active boolean NOT NULL DEFAULT true,row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_by bigint NOT NULL REFERENCES users(id),updated_by bigint NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE cookbook_recipes (
 location_id bigint NOT NULL,cookbook_id bigint NOT NULL,recipe_id bigint NOT NULL,
 sort_order smallint NOT NULL CHECK(sort_order BETWEEN 1 AND 9999),
 PRIMARY KEY(cookbook_id,sort_order),UNIQUE(cookbook_id,recipe_id),
 FOREIGN KEY(location_id,cookbook_id) REFERENCES cookbooks(location_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id,recipe_id) REFERENCES recipes(location_id,id) ON DELETE RESTRICT
);
CREATE FUNCTION recipe_protect_v22() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
 IF TG_OP IN ('DELETE','TRUNCATE') OR TG_TABLE_NAME IN ('recipe_assets','recipe_revisions') THEN
  RAISE EXCEPTION 'Immutable recipe history.' USING ERRCODE='55000';
 END IF;
 IF NEW.location_id<>OLD.location_id THEN RAISE EXCEPTION 'Immutable scope.' USING ERRCODE='55000'; END IF;
 IF TG_TABLE_NAME='recipes' AND (to_jsonb(NEW)->'source_kind',to_jsonb(NEW)->'source_reference',
 to_jsonb(NEW)->'source_url',to_jsonb(NEW)->'source_note',to_jsonb(NEW)->'fetched_at') IS DISTINCT FROM
 (to_jsonb(OLD)->'source_kind',to_jsonb(OLD)->'source_reference',to_jsonb(OLD)->'source_url',
 to_jsonb(OLD)->'source_note',to_jsonb(OLD)->'fetched_at') THEN
  RAISE EXCEPTION 'Immutable provenance.' USING ERRCODE='55000';
 END IF;
 RETURN NEW;
END;$fn$;
CREATE TRIGGER recipes_protect BEFORE UPDATE OR DELETE ON recipes FOR EACH ROW EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipes_version BEFORE UPDATE ON recipes FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();
CREATE TRIGGER recipes_no_truncate BEFORE TRUNCATE ON recipes FOR EACH STATEMENT EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER cookbooks_protect BEFORE UPDATE OR DELETE ON cookbooks FOR EACH ROW EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER cookbooks_version BEFORE UPDATE ON cookbooks FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();
CREATE TRIGGER cookbooks_no_truncate BEFORE TRUNCATE ON cookbooks FOR EACH STATEMENT EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipe_assets_immutable BEFORE UPDATE OR DELETE ON recipe_assets FOR EACH ROW EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipe_assets_no_truncate BEFORE TRUNCATE ON recipe_assets FOR EACH STATEMENT EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipe_revisions_immutable BEFORE UPDATE OR DELETE ON recipe_revisions FOR EACH ROW EXECUTE FUNCTION recipe_protect_v22();
CREATE TRIGGER recipe_revisions_no_truncate BEFORE TRUNCATE ON recipe_revisions FOR EACH STATEMENT EXECUTE FUNCTION recipe_protect_v22();

CREATE FUNCTION recipe_payload_v22(p_id bigint) RETURNS jsonb LANGUAGE sql STABLE
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT jsonb_build_object(
 'title',r.title,'description',r.description,'servings',trim_scale(r.servings)::text,'servings_unit_code',u.code,
 'prep_minutes',r.prep_minutes,'cook_minutes',r.cook_minutes,
 'source',jsonb_build_object('kind',r.source_kind,'reference',r.source_reference,'url',r.source_url,'note',r.source_note,'fetched_at',r.fetched_at),
 'ingredients',COALESCE((SELECT jsonb_agg(jsonb_build_object('line_public_id',i.line_public_id,'group_label',i.group_label,'ingredient_text',i.ingredient_text,
 'food_public_id',f.public_id,'quantity',trim_scale(i.quantity)::text,'unit_code',iu.code,'note',i.note,
 'source_kind',i.source_kind,'source_reference',i.source_reference,'fetched_at',i.fetched_at) ORDER BY i.sort_order)
 FROM recipe_ingredients i LEFT JOIN foods f ON f.id=i.food_id AND f.location_id=i.location_id
 LEFT JOIN measurement_units iu ON iu.id=i.unit_id WHERE i.recipe_id=r.id AND i.location_id=r.location_id),'[]'::jsonb),
 'steps',COALESCE((SELECT jsonb_agg(jsonb_build_object('instruction',s.instruction,'duration_minutes',s.duration_minutes,
 'image_sha256',s.image_sha256) ORDER BY s.step_number) FROM recipe_steps s WHERE s.recipe_id=r.id AND s.location_id=r.location_id),'[]'::jsonb),
 'tag_public_ids',COALESCE((SELECT jsonb_agg(t.public_id ORDER BY t.public_id) FROM recipe_tags rt JOIN tags t ON t.id=rt.tag_id
 AND t.location_id=rt.location_id WHERE rt.recipe_id=r.id AND rt.location_id=r.location_id),'[]'::jsonb),
 'images',COALESCE((SELECT jsonb_agg(jsonb_build_object('sha256',i.sha256,'caption',i.caption,'source_url',i.source_url,
 'source_license',i.source_license,'fetched_at',i.fetched_at) ORDER BY i.sort_order)
 FROM recipe_images i WHERE i.recipe_id=r.id AND i.location_id=r.location_id),'[]'::jsonb))
 FROM recipes r JOIN measurement_units u ON u.id=r.servings_unit_id WHERE r.id=p_id;
$fn$;
CREATE FUNCTION recipe_fields_v22(p_value jsonb,p_keys text[]) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE field record;
BEGIN
 PERFORM master_payload(p_value,p_keys);
 FOR field IN SELECT key,value FROM jsonb_each(p_value) LOOP
  IF field.value='null'::jsonb THEN CONTINUE; END IF;
  IF field.key IN ('ingredients','steps','tag_public_ids','images','recipes') THEN
   IF jsonb_typeof(field.value)<>'array' THEN RAISE EXCEPTION 'Array required.' USING ERRCODE='P1901'; END IF;
  ELSIF field.key='source' THEN
   IF jsonb_typeof(field.value)<>'object' THEN RAISE EXCEPTION 'Source required.' USING ERRCODE='P1901'; END IF;
  ELSIF field.key='active' THEN
   IF jsonb_typeof(field.value)<>'boolean' THEN RAISE EXCEPTION 'Boolean required.' USING ERRCODE='P1901'; END IF;
  ELSIF field.key IN ('prep_minutes','cook_minutes','duration_minutes','width','height') THEN
   IF jsonb_typeof(field.value)<>'number' OR field.value::text !~ '^[0-9]+$' THEN
    RAISE EXCEPTION 'Integer required.' USING ERRCODE='P1901';
   END IF;
  ELSIF jsonb_typeof(field.value)<>'string' THEN RAISE EXCEPTION 'Text required.' USING ERRCODE='P1901';
  END IF;
  IF field.key='fetched_at' AND (field.value#>>'{}') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
   RAISE EXCEPTION 'Timestamp requires offset.' USING ERRCODE='P1901';
  END IF;
 END LOOP;
 IF (SELECT count(*) FROM jsonb_object_keys(p_value))<>cardinality(p_keys) THEN
  RAISE EXCEPTION 'Missing fields.' USING ERRCODE='P1901';
 END IF;
END;$fn$;
CREATE FUNCTION recipe_snapshot_v22(p_id bigint) RETURNS jsonb LANGUAGE sql STABLE
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT jsonb_build_object('schema_version',1,'recipe',recipe_payload_v22(r.id),
 'calculation',jsonb_build_object('precision',50,'rounding','ROUND_HALF_UP','quantity_places',6,
 'bases',jsonb_build_object('mass','G','volume','ML','count','STK'),'contextual','same-code-only'),
 'units',COALESCE((SELECT jsonb_agg(jsonb_build_object('public_id',u.public_id,'code',u.code,
 'display_name',u.display_name,'dimension',u.dimension,'base_factor',trim_scale(u.base_factor)::text) ORDER BY u.id)
 FROM measurement_units u WHERE u.id=r.servings_unit_id OR u.id IN
 (SELECT unit_id FROM recipe_ingredients WHERE recipe_id=r.id AND location_id=r.location_id)),'[]'::jsonb),
 'foods',COALESCE((SELECT jsonb_agg(jsonb_build_object('public_id',f.public_id,'name',f.name,'row_version',f.row_version,
 'density_g_per_ml',trim_scale(f.density_g_per_ml)::text,'piece_weight_g',trim_scale(f.piece_weight_g)::text,
 'source_kind',f.source_kind,'source_reference',f.source_reference,'source_url',f.source_url,'source_note',f.source_note,
 'fetched_at',f.fetched_at,'factor_decisions',COALESCE((SELECT jsonb_agg(p.decision_detail ORDER BY p.id)
 FROM food_data_proposals p WHERE p.food_id=f.id AND p.location_id=f.location_id AND p.status='accepted'),'[]'::jsonb))
 ORDER BY f.id) FROM foods f WHERE f.location_id=r.location_id AND f.id IN
 (SELECT food_id FROM recipe_ingredients WHERE recipe_id=r.id AND location_id=r.location_id)),'[]'::jsonb))
 FROM recipes r WHERE r.id=p_id;
$fn$;

CREATE FUNCTION recipe_refs_v22(p_location bigint,p_id bigint,p_payload jsonb) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE item jsonb; ref record; field_name text;
BEGIN
 PERFORM recipe_fields_v22(p_payload,ARRAY['title','description','servings','servings_unit_code','prep_minutes','cook_minutes','source','ingredients','steps','tag_public_ids','images']);
 FOREACH field_name IN ARRAY ARRAY['ingredients','steps','tag_public_ids','images'] LOOP
  IF jsonb_typeof(p_payload->field_name)<>'array' OR jsonb_array_length(p_payload->field_name)>64 THEN
   RAISE EXCEPTION 'Invalid recipe list.' USING ERRCODE='P1901';
  END IF;
 END LOOP;
 PERFORM recipe_fields_v22(p_payload->'source',ARRAY['kind','reference','url','note','fetched_at']);
 FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'ingredients') LOOP
  PERFORM recipe_fields_v22(item,ARRAY['line_public_id','group_label','ingredient_text','food_public_id','quantity','unit_code','note','source_kind','source_reference','fetched_at']);
  IF (item->>'quantity' IS NULL)<>(item->>'unit_code' IS NULL) THEN
   RAISE EXCEPTION 'Quantity requires unit.' USING ERRCODE='P1901';
  END IF;
 END LOOP;
 FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'steps') LOOP
  PERFORM recipe_fields_v22(item,ARRAY['instruction','duration_minutes','image_sha256']);
 END LOOP;
 FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'images') LOOP
  PERFORM recipe_fields_v22(item,ARRAY['sha256','caption','source_url','source_license','fetched_at']);
 END LOOP;
 -- Lock existing and requested references before the recipe aggregate.
 FOR ref IN SELECT * FROM measurement_units WHERE code=p_payload->>'servings_unit_code'
 OR code IN (SELECT value->>'unit_code' FROM jsonb_array_elements(p_payload->'ingredients'))
 OR id IN (SELECT servings_unit_id FROM recipes WHERE id=p_id)
 OR id IN (SELECT unit_id FROM recipe_ingredients WHERE recipe_id=p_id) ORDER BY id FOR SHARE LOOP
  IF NOT ref.active AND NOT EXISTS(SELECT 1 FROM recipes WHERE id=p_id AND servings_unit_id=ref.id)
   AND NOT EXISTS(SELECT 1 FROM recipe_ingredients WHERE recipe_id=p_id AND unit_id=ref.id) THEN
   RAISE EXCEPTION 'Archived unit.' USING ERRCODE='55000';
  END IF;
 END LOOP;
 IF NOT EXISTS(SELECT 1 FROM measurement_units WHERE code=p_payload->>'servings_unit_code') OR
 EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'ingredients') i WHERE i->>'unit_code' IS NOT NULL
 AND NOT EXISTS(SELECT 1 FROM measurement_units WHERE code=i->>'unit_code')) THEN
  RAISE EXCEPTION 'Unknown unit.' USING ERRCODE='22023';
 END IF;
 FOR ref IN SELECT * FROM tags WHERE location_id=p_location AND (public_id IN
 (SELECT value::text::uuid FROM jsonb_array_elements_text(p_payload->'tag_public_ids'))
 OR id IN(SELECT tag_id FROM recipe_tags WHERE recipe_id=p_id)) ORDER BY id FOR SHARE LOOP
  IF NOT ref.active AND NOT EXISTS(SELECT 1 FROM recipe_tags WHERE recipe_id=p_id AND tag_id=ref.id) THEN
   RAISE EXCEPTION 'Archived tag.' USING ERRCODE='55000';
  END IF;
 END LOOP;
 IF (SELECT count(DISTINCT value) FROM jsonb_array_elements_text(p_payload->'tag_public_ids'))<>jsonb_array_length(p_payload->'tag_public_ids')
 OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(p_payload->'tag_public_ids') i WHERE NOT EXISTS
 (SELECT 1 FROM tags WHERE public_id=i.value::uuid AND location_id=p_location)) THEN
  RAISE EXCEPTION 'Unknown or duplicate tag.' USING ERRCODE='22023';
 END IF;
 FOR ref IN SELECT * FROM foods WHERE location_id=p_location AND (public_id IN
 (SELECT (value->>'food_public_id')::uuid FROM jsonb_array_elements(p_payload->'ingredients'))
 OR id IN(SELECT food_id FROM recipe_ingredients WHERE recipe_id=p_id)) ORDER BY id FOR SHARE LOOP
  IF NOT ref.active AND NOT EXISTS(SELECT 1 FROM recipe_ingredients WHERE recipe_id=p_id AND food_id=ref.id) THEN
   RAISE EXCEPTION 'Archived food.' USING ERRCODE='55000';
  END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'ingredients') i WHERE i->>'food_public_id' IS NOT NULL
 AND NOT EXISTS(SELECT 1 FROM foods WHERE public_id=(i->>'food_public_id')::uuid AND location_id=p_location)) THEN
  RAISE EXCEPTION 'Unknown food.' USING ERRCODE='22023';
 END IF;
END;$fn$;

CREATE FUNCTION recipe_location_v22(p_location bigint) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
 IF p_location IS NULL OR p_location<=0 THEN RAISE EXCEPTION 'Original location required.' USING ERRCODE='P1901'; END IF;
 IF NOT lock_expected_active_location(p_location) THEN
  IF (SELECT count(*) FROM locations WHERE active)<>1 THEN
   RAISE EXCEPTION 'Ambiguous active location.' USING ERRCODE='P1904';
  END IF;
  RAISE EXCEPTION 'Original location changed.' USING ERRCODE='55000';
 END IF;
END;$fn$;

CREATE FUNCTION recipe_write_v22(p_action text,p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE recipe recipes%ROWTYPE; original jsonb; item jsonb; origin recipe_ingredients%ROWTYPE;
 audit_before jsonb; audit_after jsonb;
 version_before bigint; new_snapshot jsonb; revision recipe_revisions%ROWTYPE; digest_value text;
 n integer; line_ids uuid[]:=ARRAY[]::uuid[]; line_id uuid; ingredient_ids jsonb:='[]'::jsonb;
BEGIN
 PERFORM require_master_data_actor(p_actor,p_authz,'recipe.write');
 PERFORM recipe_location_v22(p_location);
 IF p_action='create' THEN
  IF p_target IS NOT NULL OR p_version IS NOT NULL THEN RAISE EXCEPTION 'Unexpected target.' USING ERRCODE='P1901'; END IF;
 ELSE
  PERFORM master_expectation(p_target,p_version);
  SELECT * INTO recipe FROM recipes WHERE public_id=p_target AND location_id=p_location;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown recipe.' USING ERRCODE='22023'; END IF;
 END IF;
 IF p_action IN ('create','update') THEN
  PERFORM recipe_refs_v22(p_location,recipe.id,p_payload);
 ELSIF p_action='freeze' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY[]::text[]);
  PERFORM recipe_refs_v22(p_location,recipe.id,recipe_payload_v22(recipe.id));
 ELSIF p_action='active' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['active']);
  IF jsonb_typeof(p_payload->'active')<>'boolean' THEN RAISE EXCEPTION 'Boolean required.' USING ERRCODE='P1901'; END IF;
 ELSIF p_action='image' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['sha256','data','content_type','width','height','caption','source_url','source_license','fetched_at']);
 ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
 END IF;
 IF p_action<>'create' THEN
  SELECT * INTO recipe FROM recipes WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
  IF recipe.row_version<>p_version THEN RAISE EXCEPTION 'Stale recipe.' USING ERRCODE='55000'; END IF;
  IF NOT recipe.active AND NOT (p_action='active' AND (p_payload->>'active')::boolean) THEN
   RAISE EXCEPTION 'Archived recipe.' USING ERRCODE='55000';
  END IF;
  original:=recipe_payload_v22(recipe.id);
  audit_before:=original||jsonb_build_object('active',recipe.active);
  version_before:=recipe.row_version;
 ELSE version_before:=0;
 END IF;
 IF p_action IN ('create','update') THEN
  IF p_action='update' AND original->'source' IS DISTINCT FROM p_payload->'source' THEN
   -- Compare timestamp instants, not equivalent JSON timestamp spellings.
   IF (original->'source'-'fetched_at') IS DISTINCT FROM (p_payload->'source'-'fetched_at') OR
    (original->'source'->>'fetched_at')::timestamptz IS DISTINCT FROM (p_payload->'source'->>'fetched_at')::timestamptz THEN
    RAISE EXCEPTION 'Immutable provenance.' USING ERRCODE='55000';
   END IF;
  END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'ingredients') LOOP
   line_id:=(item->>'line_public_id')::uuid;
   IF line_id IS NULL THEN line_id:=gen_random_uuid();
   ELSE
    SELECT * INTO origin FROM recipe_ingredients WHERE recipe_id=recipe.id AND line_public_id=line_id;
    IF NOT FOUND OR line_id=ANY(line_ids) THEN RAISE EXCEPTION 'Unknown or duplicate ingredient identity.' USING ERRCODE='P1901'; END IF;
    IF (origin.source_kind,origin.source_reference,origin.fetched_at) IS DISTINCT FROM
     (item->>'source_kind',item->>'source_reference',(item->>'fetched_at')::timestamptz) THEN
     RAISE EXCEPTION 'Immutable ingredient provenance.' USING ERRCODE='55000';
    END IF;
   END IF;
   line_ids:=array_append(line_ids,line_id);
   ingredient_ids:=ingredient_ids||jsonb_build_array(item||jsonb_build_object('line_public_id',line_id));
  END LOOP;
  p_payload:=jsonb_set(p_payload,'{ingredients}',ingredient_ids);
  -- An archived reference may remain only on its original logical association.
  IF EXISTS(SELECT 1 FROM measurement_units u WHERE NOT u.active AND u.code=p_payload->>'servings_unit_code'
   AND u.id IS DISTINCT FROM recipe.servings_unit_id) OR EXISTS(
   SELECT 1 FROM jsonb_array_elements(p_payload->'ingredients') i
    LEFT JOIN recipe_ingredients old ON old.recipe_id=recipe.id AND old.line_public_id=(i->>'line_public_id')::uuid
    LEFT JOIN measurement_units u ON u.code=i->>'unit_code'
    LEFT JOIN foods f ON f.public_id=(i->>'food_public_id')::uuid AND f.location_id=p_location
   WHERE (NOT u.active AND u.id IS DISTINCT FROM old.unit_id) OR (NOT f.active AND f.id IS DISTINCT FROM old.food_id)) THEN
   RAISE EXCEPTION 'New archived association.' USING ERRCODE='55000';
  END IF;
  -- Existing assets must already belong to this recipe, including its immutable history.
  IF EXISTS(SELECT 1 FROM (
    SELECT value->>'sha256' AS sha FROM jsonb_array_elements(p_payload->'images')
    UNION SELECT value->>'image_sha256' FROM jsonb_array_elements(p_payload->'steps')) requested
   WHERE sha IS NOT NULL AND NOT EXISTS(SELECT 1 FROM recipe_images WHERE recipe_id=recipe.id AND sha256=sha)
   AND NOT EXISTS(SELECT 1 FROM recipe_steps WHERE recipe_id=recipe.id AND image_sha256=sha)
   AND NOT EXISTS(SELECT 1 FROM recipe_revisions h WHERE h.recipe_id=recipe.id AND
    (EXISTS(SELECT 1 FROM jsonb_array_elements(h.snapshot_json->'recipe'->'images') i WHERE i->>'sha256'=sha)
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(h.snapshot_json->'recipe'->'steps') s WHERE s->>'image_sha256'=sha)))) THEN
   RAISE EXCEPTION 'Unknown recipe asset.' USING ERRCODE='22023';
  END IF;
  -- A step reference needs its provenance in this self-contained aggregate.
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'steps') s
   WHERE s->>'image_sha256' IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM jsonb_array_elements(p_payload->'images') i WHERE i->>'sha256'=s->>'image_sha256')) THEN
   RAISE EXCEPTION 'Step image requires its provenance.' USING ERRCODE='55000';
  END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'images') LOOP
   IF NOT EXISTS(SELECT 1 FROM (
    SELECT value AS image FROM jsonb_array_elements(original->'images')
    UNION ALL SELECT image FROM recipe_revisions h,
     LATERAL jsonb_array_elements(h.snapshot_json->'recipe'->'images') image WHERE h.recipe_id=recipe.id) origins
    WHERE image->>'sha256'=item->>'sha256' AND
     (image->>'source_url',image->>'source_license',(image->>'fetched_at')::timestamptz) IS NOT DISTINCT FROM
     (item->>'source_url',item->>'source_license',(item->>'fetched_at')::timestamptz)) THEN
    RAISE EXCEPTION 'Immutable image provenance.' USING ERRCODE='55000';
   END IF;
  END LOOP;
  IF p_action='create' THEN
   INSERT INTO recipes(location_id,title,description,servings,servings_unit_id,prep_minutes,cook_minutes,
    source_kind,source_reference,source_url,source_note,fetched_at,created_by,updated_by)
   VALUES(p_location,master_text(p_payload->>'title',120),recipe_text_v22(p_payload->>'description',2000,false),
    (p_payload->>'servings')::numeric,(SELECT id FROM measurement_units WHERE code=p_payload->>'servings_unit_code'),
    (p_payload->>'prep_minutes')::integer,(p_payload->>'cook_minutes')::integer,p_payload->'source'->>'kind',
    p_payload->'source'->>'reference',p_payload->'source'->>'url',p_payload->'source'->>'note',
    (p_payload->'source'->>'fetched_at')::timestamptz,p_actor,p_actor) RETURNING * INTO recipe;
  END IF;
  DELETE FROM recipe_ingredients WHERE recipe_id=recipe.id;
  INSERT INTO recipe_ingredients(location_id,recipe_id,sort_order,line_public_id,group_label,ingredient_text,food_id,quantity,unit_id,note,source_kind,source_reference,fetched_at)
   SELECT p_location,recipe.id,j.n,(i->>'line_public_id')::uuid,master_text(i->>'group_label',120,false),
   master_text(i->>'ingredient_text',500),(SELECT id FROM foods WHERE public_id=(i->>'food_public_id')::uuid AND location_id=p_location),
   (i->>'quantity')::numeric,(SELECT id FROM measurement_units WHERE code=i->>'unit_code'),master_text(i->>'note',500,false),
   i->>'source_kind',master_text(i->>'source_reference',200,false),(i->>'fetched_at')::timestamptz
   FROM jsonb_array_elements(p_payload->'ingredients') WITH ORDINALITY j(i,n);
  DELETE FROM recipe_steps WHERE recipe_id=recipe.id;
  INSERT INTO recipe_steps(location_id,recipe_id,step_number,instruction,duration_minutes,image_sha256)
   SELECT p_location,recipe.id,j.n,recipe_text_v22(i->>'instruction',8000),(i->>'duration_minutes')::integer,i->>'image_sha256'
   FROM jsonb_array_elements(p_payload->'steps') WITH ORDINALITY j(i,n);
  DELETE FROM recipe_images WHERE recipe_id=recipe.id;
  INSERT INTO recipe_images(location_id,recipe_id,sort_order,sha256,caption,source_url,source_license,fetched_at)
   SELECT p_location,recipe.id,j.n,i->>'sha256',master_text(i->>'caption',500,false),master_text(i->>'source_url',2048,false),
   master_text(i->>'source_license',500,false),(i->>'fetched_at')::timestamptz
   FROM jsonb_array_elements(p_payload->'images') WITH ORDINALITY j(i,n);
  DELETE FROM recipe_tags WHERE recipe_id=recipe.id;
  INSERT INTO recipe_tags(location_id,recipe_id,tag_id) SELECT p_location,recipe.id,t.id FROM tags t
   WHERE t.location_id=p_location AND t.public_id IN(SELECT value::uuid FROM jsonb_array_elements_text(p_payload->'tag_public_ids'));
  IF p_action='update' THEN
   IF original=recipe_payload_v22(recipe.id) AND
    (recipe.title,recipe.description,recipe.servings,recipe.servings_unit_id,recipe.prep_minutes,recipe.cook_minutes) IS NOT DISTINCT FROM
    (master_text(p_payload->>'title',120),recipe_text_v22(p_payload->>'description',2000,false),(p_payload->>'servings')::numeric,
    (SELECT id FROM measurement_units WHERE code=p_payload->>'servings_unit_code'),(p_payload->>'prep_minutes')::integer,(p_payload->>'cook_minutes')::integer) THEN
    RETURN jsonb_build_object('public_id',recipe.public_id,'row_version',recipe.row_version);
   END IF;
   UPDATE recipes SET title=master_text(p_payload->>'title',120),description=recipe_text_v22(p_payload->>'description',2000,false),
    servings=(p_payload->>'servings')::numeric,servings_unit_id=(SELECT id FROM measurement_units WHERE code=p_payload->>'servings_unit_code'),
    prep_minutes=(p_payload->>'prep_minutes')::integer,cook_minutes=(p_payload->>'cook_minutes')::integer,updated_by=p_actor
    WHERE id=recipe.id RETURNING * INTO recipe;
  END IF;
 ELSIF p_action='active' THEN
  IF recipe.active=(p_payload->>'active')::boolean THEN RAISE EXCEPTION 'No state transition.' USING ERRCODE='55000'; END IF;
  UPDATE recipes SET active=(p_payload->>'active')::boolean,updated_by=p_actor WHERE id=recipe.id RETURNING * INTO recipe;
 ELSIF p_action='freeze' THEN
  new_snapshot:=recipe_snapshot_v22(recipe.id);
  digest_value:=encode(public.digest(convert_to(new_snapshot::text,'UTF8'),'sha256'),'hex');
  SELECT * INTO revision FROM recipe_revisions WHERE recipe_id=recipe.id ORDER BY revision_number DESC LIMIT 1;
  IF FOUND AND revision.snapshot_json=new_snapshot THEN RAISE EXCEPTION 'Identical revision.' USING ERRCODE='55000'; END IF;
  INSERT INTO recipe_revisions(location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
   VALUES(p_location,recipe.id,COALESCE(revision.revision_number,0)+1,new_snapshot,digest_value,p_actor) RETURNING * INTO revision;
  UPDATE recipes SET updated_by=p_actor WHERE id=recipe.id RETURNING * INTO recipe;
 ELSE
  SELECT count(*) INTO n FROM recipe_images WHERE recipe_id=recipe.id;
  IF n>=64 THEN RAISE EXCEPTION 'Image limit.' USING ERRCODE='P1901'; END IF;
  INSERT INTO recipe_assets(location_id,sha256,image_data,content_type,width,height,created_by)
   VALUES(p_location,p_payload->>'sha256',decode(p_payload->>'data','base64'),p_payload->>'content_type',
   (p_payload->>'width')::integer,(p_payload->>'height')::integer,p_actor) ON CONFLICT DO NOTHING;
  INSERT INTO recipe_images(location_id,recipe_id,sort_order,sha256,caption,source_url,source_license,fetched_at)
   VALUES(p_location,recipe.id,n+1,p_payload->>'sha256',master_text(p_payload->>'caption',500,false),
   master_text(p_payload->>'source_url',2048,false),master_text(p_payload->>'source_license',500,false),(p_payload->>'fetched_at')::timestamptz);
  UPDATE recipes SET updated_by=p_actor WHERE id=recipe.id RETURNING * INTO recipe;
 END IF;
 audit_after:=recipe_payload_v22(recipe.id)||jsonb_build_object('active',recipe.active);
 INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
 VALUES(p_actor,'recipe.'||p_action,'recipe',recipe.public_id,jsonb_build_object('actor_authz_version',p_authz,
  'changes',COALESCE((SELECT jsonb_object_agg(key,jsonb_build_object('before',audit_before->key,'after',value))
   FROM jsonb_each(audit_after) WHERE audit_before->key IS DISTINCT FROM value),'{}'::jsonb),
  'location_id',p_location,'row_version_before',version_before,'row_version_after',recipe.row_version,
  'ingredient_line_ids',line_ids,'ingredients_before',original->'ingredients',
  'ingredients_after',recipe_payload_v22(recipe.id)->'ingredients',
  'images_before',original->'images','images_after',recipe_payload_v22(recipe.id)->'images',
  'revision_public_id',revision.public_id,'content_hash_sha256',digest_value));
 IF p_action='freeze' THEN
  RETURN jsonb_build_object('public_id',revision.public_id,'recipe_public_id',recipe.public_id,
   'revision_number',revision.revision_number,'recipe_row_version',recipe.row_version,'content_hash_sha256',digest_value);
 END IF;
 RETURN jsonb_build_object('public_id',recipe.public_id,'row_version',recipe.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation OR invalid_datetime_format OR datetime_field_overflow THEN
 RAISE EXCEPTION 'Invalid recipe input.' USING ERRCODE='P1901';
END;$fn$;

CREATE FUNCTION recipe_cookbook_v22(p_action text,p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE book cookbooks%ROWTYPE; ref record; ids bigint[]; before_ids bigint[]; name_value text; description_value text; version_before bigint;
 audit_before jsonb; audit_after jsonb;
BEGIN
 PERFORM require_master_data_actor(p_actor,p_authz,'recipe.write');
 PERFORM recipe_location_v22(p_location);
 IF p_action='assign' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['recipes']);
  IF jsonb_typeof(p_payload->'recipes')<>'array' OR jsonb_array_length(p_payload->'recipes')>64 OR
  (SELECT count(DISTINCT value) FROM jsonb_array_elements_text(p_payload->'recipes'))<>jsonb_array_length(p_payload->'recipes') THEN
   RAISE EXCEPTION 'Invalid recipe list.' USING ERRCODE='P1901';
  END IF;
  FOR ref IN SELECT * FROM recipes WHERE location_id=p_location AND public_id IN
  (SELECT value::uuid FROM jsonb_array_elements_text(p_payload->'recipes')) ORDER BY id FOR SHARE LOOP
   IF NOT ref.active AND NOT EXISTS(SELECT 1 FROM cookbook_recipes cr JOIN cookbooks c ON c.id=cr.cookbook_id
    WHERE c.public_id=p_target AND c.location_id=p_location AND cr.recipe_id=ref.id) THEN
    RAISE EXCEPTION 'Archived recipe.' USING ERRCODE='55000';
   END IF;
  END LOOP;
  SELECT array_agg(r.id ORDER BY j.n) INTO ids FROM jsonb_array_elements_text(p_payload->'recipes') WITH ORDINALITY j(value,n)
   JOIN recipes r ON r.public_id=j.value::uuid AND r.location_id=p_location;
  ids:=COALESCE(ids,ARRAY[]::bigint[]);
  IF cardinality(ids)<>jsonb_array_length(p_payload->'recipes') THEN RAISE EXCEPTION 'Unknown recipe.' USING ERRCODE='22023'; END IF;
 ELSIF p_action IN ('create','update') THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['name','description']);
  name_value:=master_text(p_payload->>'name',120);
  description_value:=recipe_text_v22(p_payload->>'description',2000,false);
 ELSIF p_action='active' THEN
  PERFORM recipe_fields_v22(p_payload,ARRAY['active']);
  IF jsonb_typeof(p_payload->'active')<>'boolean' THEN RAISE EXCEPTION 'Boolean required.' USING ERRCODE='P1901'; END IF;
 ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
 END IF;
 IF p_action='create' THEN
  IF p_target IS NOT NULL OR p_version IS NOT NULL THEN RAISE EXCEPTION 'Unexpected target.' USING ERRCODE='P1901'; END IF;
  INSERT INTO cookbooks(location_id,name,description,created_by,updated_by)
  VALUES(p_location,name_value,description_value,p_actor,p_actor) RETURNING * INTO book;
  version_before:=0;
 ELSE
  PERFORM master_expectation(p_target,p_version);
  SELECT * INTO book FROM cookbooks WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown cookbook.' USING ERRCODE='22023'; END IF;
  IF book.row_version<>p_version THEN RAISE EXCEPTION 'Stale cookbook.' USING ERRCODE='55000'; END IF;
  version_before:=book.row_version;
  audit_before:=jsonb_build_object('name',book.name,'description',book.description,'active',book.active,
   'recipe_public_ids',COALESCE((SELECT jsonb_agg(r.public_id ORDER BY cr.sort_order)
    FROM cookbook_recipes cr JOIN recipes r ON r.id=cr.recipe_id WHERE cr.cookbook_id=book.id),'[]'::jsonb));
  IF NOT book.active AND NOT (p_action='active' AND (p_payload->>'active')::boolean) THEN
   RAISE EXCEPTION 'Archived cookbook.' USING ERRCODE='55000';
  END IF;
  IF p_action='active' THEN
   IF book.active=(p_payload->>'active')::boolean THEN RAISE EXCEPTION 'No state transition.' USING ERRCODE='55000'; END IF;
   UPDATE cookbooks SET active=(p_payload->>'active')::boolean,updated_by=p_actor WHERE id=book.id RETURNING * INTO book;
  ELSIF p_action='update' THEN
   IF (book.name,book.description) IS NOT DISTINCT FROM (name_value,description_value) THEN
    RETURN jsonb_build_object('public_id',book.public_id,'row_version',book.row_version);
   END IF;
   UPDATE cookbooks SET name=name_value,description=description_value,updated_by=p_actor WHERE id=book.id RETURNING * INTO book;
  ELSE
   SELECT COALESCE(array_agg(recipe_id ORDER BY sort_order),ARRAY[]::bigint[]) INTO before_ids FROM cookbook_recipes WHERE cookbook_id=book.id;
   IF ids=before_ids THEN RETURN jsonb_build_object('public_id',book.public_id,'row_version',book.row_version); END IF;
   DELETE FROM cookbook_recipes WHERE cookbook_id=book.id;
   INSERT INTO cookbook_recipes(location_id,cookbook_id,recipe_id,sort_order)
    SELECT p_location,book.id,value,n FROM unnest(ids) WITH ORDINALITY j(value,n);
   UPDATE cookbooks SET updated_by=p_actor WHERE id=book.id RETURNING * INTO book;
  END IF;
 END IF;
 audit_after:=jsonb_build_object('name',book.name,'description',book.description,'active',book.active,
  'recipe_public_ids',COALESCE((SELECT jsonb_agg(r.public_id ORDER BY cr.sort_order)
   FROM cookbook_recipes cr JOIN recipes r ON r.id=cr.recipe_id WHERE cr.cookbook_id=book.id),'[]'::jsonb));
 INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
 VALUES(p_actor,'recipe.cookbook_'||p_action,'cookbook',book.public_id,jsonb_build_object('actor_authz_version',p_authz,
 'changes',COALESCE((SELECT jsonb_object_agg(key,jsonb_build_object('before',audit_before->key,'after',value))
  FROM jsonb_each(audit_after) WHERE audit_before->key IS DISTINCT FROM value),'{}'::jsonb),
 'location_id',p_location,'row_version_before',version_before,'row_version_after',book.row_version));
 RETURN jsonb_build_object('public_id',book.public_id,'row_version',book.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
 RAISE EXCEPTION 'Invalid cookbook input.' USING ERRCODE='P1901';
END;$fn$;

CREATE FUNCTION create_recipe_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('create',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION update_recipe_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('update',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION set_recipe_active_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('active',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION freeze_recipe_revision_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('freeze',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION add_recipe_image_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_write_v22('image',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION create_cookbook_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_cookbook_v22('create',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION update_cookbook_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_cookbook_v22('update',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION set_cookbook_active_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_cookbook_v22('active',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
CREATE FUNCTION replace_cookbook_recipes_v22(p_actor bigint,p_authz bigint,p_location bigint,p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT recipe_cookbook_v22('assign',p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;
REVOKE ALL ON FUNCTION recipe_location_v22(bigint),recipe_text_v22(text,integer,boolean),recipe_protect_v22(),recipe_fields_v22(jsonb,text[]),
 recipe_payload_v22(bigint),recipe_snapshot_v22(bigint),recipe_refs_v22(bigint,bigint,jsonb),
 recipe_write_v22(text,bigint,bigint,bigint,uuid,bigint,jsonb),recipe_cookbook_v22(text,bigint,bigint,bigint,uuid,bigint,jsonb),
 create_recipe_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 update_recipe_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 set_recipe_active_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 freeze_recipe_revision_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 add_recipe_image_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 create_cookbook_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 update_cookbook_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 set_cookbook_active_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 replace_cookbook_recipes_v22(bigint,bigint,bigint,uuid,bigint,jsonb) FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION recipe_payload_v22(bigint),
 create_recipe_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 update_recipe_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 set_recipe_active_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 freeze_recipe_revision_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 add_recipe_image_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 create_cookbook_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 update_cookbook_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 set_cookbook_active_v22(bigint,bigint,bigint,uuid,bigint,jsonb),
 replace_cookbook_recipes_v22(bigint,bigint,bigint,uuid,bigint,jsonb) TO cafeteria_app;
GRANT SELECT ON recipes,recipe_ingredients,recipe_steps,recipe_tags,recipe_images,recipe_assets,recipe_revisions,cookbooks,cookbook_recipes TO cafeteria_app,cafeteria_backup;
GRANT SELECT ON SEQUENCE recipes_id_seq,recipe_revisions_id_seq,cookbooks_id_seq TO cafeteria_backup;
COMMIT;
