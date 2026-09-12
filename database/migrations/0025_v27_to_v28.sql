BEGIN;
SET search_path TO cafeteria, public;

CREATE TABLE recipe_import_batches (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    location_id bigint NOT NULL REFERENCES locations(id),
    UNIQUE(location_id,id),
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','imported','cancelled')),
    adapter_kind text NOT NULL CHECK(adapter_kind IN ('file_import','url','ai_assisted')),
    source_filename text CHECK(source_filename=master_text(source_filename,200,false)),
    source_sha256 text CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),
    content_type text CHECK(content_type IN ('text/csv','application/json')),
    source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
    source_note text CHECK(source_note=master_text(source_note,500,false)),
    fetched_at timestamptz,
    candidate_hash_sha256 text NOT NULL CHECK(candidate_hash_sha256 ~ '^[0-9a-f]{64}$'),
    confirmation_hash_sha256 text CHECK(confirmation_hash_sha256 ~ '^[0-9a-f]{64}$'),
    annotations jsonb NOT NULL DEFAULT '[]'::jsonb,
    duplicate_groups jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by bigint NOT NULL REFERENCES users(id),
    updated_by bigint NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK(jsonb_typeof(annotations)='array' AND jsonb_typeof(duplicate_groups)='array'),
    CHECK(adapter_kind<>'file_import' OR (
        nullif(source_filename,'') IS NOT NULL AND source_sha256 IS NOT NULL
        AND content_type IS NOT NULL AND fetched_at IS NOT NULL)),
    CHECK(adapter_kind<>'url' OR (nullif(source_url,'') IS NOT NULL AND fetched_at IS NOT NULL)),
    CHECK(adapter_kind<>'ai_assisted' OR (nullif(source_note,'') IS NOT NULL AND fetched_at IS NOT NULL))
);
CREATE TABLE recipe_import_candidates (
    location_id bigint NOT NULL,
    batch_id bigint NOT NULL,
    row_number integer NOT NULL CHECK(row_number BETWEEN 1 AND 2000),
    origin_ref text NOT NULL CHECK(origin_ref=master_text(origin_ref,80)),
    original_payload jsonb NOT NULL CHECK(jsonb_typeof(original_payload)='object'),
    original_source_kind text NOT NULL CHECK(original_source_kind IN ('manual','url','file_import','ai_assisted')),
    original_source_reference text CHECK(original_source_reference=master_text(original_source_reference,200,false)),
    original_source_url text CHECK(original_source_url=master_text(original_source_url,2048,false)
        AND original_source_url ~ '^https?://'),
    original_source_note text CHECK(original_source_note=master_text(original_source_note,500,false)),
    original_fetched_at timestamptz,
    source_line integer CHECK(source_line IS NULL OR source_line>0),
    candidate_payload jsonb NOT NULL CHECK(jsonb_typeof(candidate_payload)='object'),
    duplicate_decision text NOT NULL DEFAULT 'undecided'
        CHECK(duplicate_decision IN ('undecided','create_new','skip_existing')),
    target_recipe_public_id uuid,
    target_row_version bigint CHECK(target_row_version IS NULL OR target_row_version>0),
    parse_errors jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(parse_errors)='array'),
    PRIMARY KEY(batch_id,row_number),
    FOREIGN KEY(location_id,batch_id) REFERENCES recipe_import_batches(location_id,id) ON DELETE RESTRICT,
    CHECK(NOT (original_payload ?| ARRAY['unreviewed','proposed_not_measured','allergen_not_checked'])),
    CHECK(NOT (candidate_payload ?| ARRAY['unreviewed','proposed_not_measured','allergen_not_checked'])),
    CHECK((duplicate_decision='skip_existing')=(target_recipe_public_id IS NOT NULL
        AND target_row_version IS NOT NULL)),
    CHECK(duplicate_decision='skip_existing' OR (target_recipe_public_id IS NULL AND target_row_version IS NULL))
);
CREATE INDEX recipe_import_batches_location_idx ON recipe_import_batches(location_id,created_at DESC);
CREATE TRIGGER recipe_import_batches_version BEFORE UPDATE ON recipe_import_batches
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE FUNCTION recipe_import_protect_v28() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'Importstapel darf nicht gelöscht werden.' USING ERRCODE='55000';
    END IF;
    IF TG_TABLE_NAME='recipe_import_batches' THEN
        IF NEW.public_id<>OLD.public_id OR NEW.location_id<>OLD.location_id
            OR NEW.adapter_kind<>OLD.adapter_kind
            OR NEW.source_filename IS DISTINCT FROM OLD.source_filename
            OR NEW.source_sha256 IS DISTINCT FROM OLD.source_sha256
            OR NEW.content_type IS DISTINCT FROM OLD.content_type
            OR NEW.source_url IS DISTINCT FROM OLD.source_url
            OR NEW.fetched_at IS DISTINCT FROM OLD.fetched_at
            OR NEW.duplicate_groups IS DISTINCT FROM OLD.duplicate_groups
            OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at THEN
            RAISE EXCEPTION 'Importursprung ist unveränderlich.' USING ERRCODE='55000';
        END IF;
        IF OLD.status<>'draft' AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Importstapel ist nicht mehr bearbeitbar.' USING ERRCODE='55000';
        END IF;
    ELSE
        IF NEW.batch_id<>OLD.batch_id OR NEW.location_id<>OLD.location_id
            OR NEW.row_number<>OLD.row_number OR NEW.origin_ref<>OLD.origin_ref
            OR NEW.original_payload IS DISTINCT FROM OLD.original_payload
            OR NEW.original_source_kind<>OLD.original_source_kind
            OR NEW.original_source_reference IS DISTINCT FROM OLD.original_source_reference
            OR NEW.original_source_url IS DISTINCT FROM OLD.original_source_url
            OR NEW.original_source_note IS DISTINCT FROM OLD.original_source_note
            OR NEW.original_fetched_at IS DISTINCT FROM OLD.original_fetched_at
            OR NEW.source_line IS DISTINCT FROM OLD.source_line
            OR NEW.parse_errors IS DISTINCT FROM OLD.parse_errors THEN
            RAISE EXCEPTION 'Importursprung ist unveränderlich.' USING ERRCODE='55000';
        END IF;
    END IF;
    RETURN NEW;
END;$fn$;
CREATE TRIGGER recipe_import_batches_protect BEFORE UPDATE OR DELETE ON recipe_import_batches
    FOR EACH ROW EXECUTE FUNCTION recipe_import_protect_v28();
CREATE TRIGGER recipe_import_candidates_protect BEFORE UPDATE OR DELETE ON recipe_import_candidates
    FOR EACH ROW EXECUTE FUNCTION recipe_import_protect_v28();

CREATE FUNCTION recipe_import_hash_v28(p_annotations jsonb, p_rows jsonb) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
SELECT encode(public.digest(convert_to(jsonb_build_object(
    'annotations',COALESCE(p_annotations,'[]'::jsonb),'rows',COALESCE(p_rows,'[]'::jsonb)
)::text,'UTF8'),'sha256'),'hex');
$fn$;

CREATE FUNCTION recipe_import_visible_note_v28(p_base text, p_annotations jsonb) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE labels text;
BEGIN
    SELECT string_agg(label, '; ' ORDER BY ord) INTO labels FROM (
        SELECT CASE value
            WHEN 'unreviewed' THEN 'ungeprüft'
            WHEN 'proposed_not_measured' THEN 'vorgeschlagen, nicht gemessen'
            WHEN 'allergen_not_checked' THEN 'Allergene nicht geprüft'
        END AS label, ordinality AS ord
        FROM jsonb_array_elements_text(COALESCE(p_annotations,'[]'::jsonb)) WITH ORDINALITY
    ) s WHERE label IS NOT NULL;
    IF labels IS NULL THEN
        RETURN master_text(p_base,500,false);
    END IF;
    IF NULLIF(btrim(COALESCE(p_base,'')),'') IS NULL THEN
        RETURN master_text('Import: '||labels,500,false);
    END IF;
    RETURN master_text(btrim(p_base)||' [Import: '||labels||']',500,false);
END;$fn$;

CREATE FUNCTION recipe_import_save_v28(p_create boolean,p_actor bigint,p_authz bigint,p_location bigint,
    p_target uuid,p_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE batch recipe_import_batches%ROWTYPE; item jsonb; origin jsonb; candidate jsonb; source jsonb;
    v_ann jsonb; rows jsonb; action text; digest_value text; version_before bigint:=0;
    food_ids uuid[]:=ARRAY[]::uuid[]; unit_codes text[]:=ARRAY[]::text[]; ingredient jsonb;
    rownum integer; n integer:=0; decision text; target_id uuid; target_version bigint;
    kind text; reference text; note text; fetched timestamptz; adapter text; sha text;
    v_source_url text; v_source_note text; food_id text; unit_code text;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_authz,'recipe.write');
    PERFORM master_location(p_location);
    IF p_payload IS NULL OR jsonb_typeof(p_payload)<>'object' OR octet_length(p_payload::text)>8388608 THEN
        RAISE EXCEPTION 'Ungültige Importfelder.' USING ERRCODE='P1901';
    END IF;
    IF p_create THEN
        PERFORM master_payload(p_payload,ARRAY['adapter_kind','source_filename','source_sha256','content_type',
            'source_url','source_note','fetched_at','annotations','duplicate_groups','rows']);
        IF p_target IS NOT NULL OR p_version IS NOT NULL THEN
            RAISE EXCEPTION 'Ungültiger neuer Importstapel.' USING ERRCODE='P1901';
        END IF;
        adapter:=p_payload->>'adapter_kind';
        v_ann:=COALESCE(p_payload->'annotations','[]'::jsonb);
        rows:=p_payload->'rows';
        v_source_url:=NULLIF(p_payload->>'source_url','');
        v_source_note:=p_payload->>'source_note';
    ELSE
        PERFORM master_expectation(p_target,p_version);
        PERFORM master_payload(p_payload,ARRAY['action','annotations','rows']);
        SELECT * INTO batch FROM recipe_import_batches
            WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannter Importstapel.' USING ERRCODE='22023'; END IF;
        IF batch.row_version<>p_version THEN
            RAISE EXCEPTION 'Importstapel wurde geändert.' USING ERRCODE='55000';
        END IF;
        IF batch.status<>'draft' THEN
            RAISE EXCEPTION 'Importstapel ist nicht mehr bearbeitbar.' USING ERRCODE='55000';
        END IF;
        version_before:=batch.row_version;
        adapter:=batch.adapter_kind;
        v_source_url:=batch.source_url;
        v_source_note:=batch.source_note;
        action:=COALESCE(p_payload->>'action','save');
        IF action NOT IN ('save','acknowledge','cancel') THEN
            RAISE EXCEPTION 'Ungültige Importfelder.' USING ERRCODE='P1901';
        END IF;
        IF action='cancel' THEN
            UPDATE recipe_import_batches SET status='cancelled',updated_by=p_actor WHERE id=batch.id
                RETURNING * INTO batch;
            INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
                VALUES(p_actor,'recipe.import_batch','recipe_import_batch',batch.public_id,
                    jsonb_build_object('actor_authz_version',p_authz,'location_id',p_location,
                        'row_version_before',version_before,'row_version_after',batch.row_version,
                        'action','cancel'));
            RETURN jsonb_build_object('public_id',batch.public_id,'row_version',batch.row_version,
                'candidate_hash_sha256',batch.candidate_hash_sha256,
                'confirmation_hash_sha256',batch.confirmation_hash_sha256,'status',batch.status);
        END IF;
        IF action='acknowledge' THEN
            IF batch.confirmation_hash_sha256 IS NOT DISTINCT FROM batch.candidate_hash_sha256 THEN
                RETURN jsonb_build_object('public_id',batch.public_id,'row_version',batch.row_version,
                    'candidate_hash_sha256',batch.candidate_hash_sha256,
                    'confirmation_hash_sha256',batch.confirmation_hash_sha256,'status',batch.status);
            END IF;
            UPDATE recipe_import_batches SET confirmation_hash_sha256=candidate_hash_sha256,updated_by=p_actor
                WHERE id=batch.id RETURNING * INTO batch;
            INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
                VALUES(p_actor,'recipe.import_batch','recipe_import_batch',batch.public_id,
                    jsonb_build_object('actor_authz_version',p_authz,'location_id',p_location,
                        'row_version_before',version_before,'row_version_after',batch.row_version,
                        'action','acknowledge','candidate_hash_sha256',batch.candidate_hash_sha256));
            RETURN jsonb_build_object('public_id',batch.public_id,'row_version',batch.row_version,
                'candidate_hash_sha256',batch.candidate_hash_sha256,
                'confirmation_hash_sha256',batch.confirmation_hash_sha256,'status',batch.status);
        END IF;
        v_ann:=COALESCE(p_payload->'annotations',batch.annotations);
        rows:=p_payload->'rows';
        sha:=batch.source_sha256;
        fetched:=batch.fetched_at;
    END IF;
    IF v_ann IS NULL OR jsonb_typeof(v_ann)<>'array' THEN
        RAISE EXCEPTION 'Ungültige Importannotation.' USING ERRCODE='P1901';
    END IF;
    IF jsonb_array_length(v_ann)>3
        OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(v_ann) a
            WHERE a NOT IN ('unreviewed','proposed_not_measured','allergen_not_checked'))
        OR (SELECT count(*) FROM jsonb_array_elements_text(v_ann))
            <>(SELECT count(DISTINCT value) FROM jsonb_array_elements_text(v_ann)) THEN
        RAISE EXCEPTION 'Ungültige Importannotation.' USING ERRCODE='P1901';
    END IF;
    IF rows IS NULL OR jsonb_typeof(rows)<>'array' OR jsonb_array_length(rows) NOT BETWEEN 1 AND 2000 THEN
        RAISE EXCEPTION 'Die Datei muss zwischen 1 und 2000 Rezeptzeilen enthalten.' USING ERRCODE='P1901';
    END IF;
    IF p_create THEN
        sha:=p_payload->>'source_sha256';
        IF p_payload->>'fetched_at' IS NULL THEN
            RAISE EXCEPTION 'Abrufzeit mit Zeitzone erforderlich.' USING ERRCODE='P1901';
        END IF;
        fetched:=(p_payload->>'fetched_at')::timestamptz;
    ELSE
        IF jsonb_array_length(rows)<>(SELECT count(*) FROM recipe_import_candidates WHERE batch_id=batch.id)
            OR EXISTS(
                SELECT 1 FROM jsonb_array_elements(rows) r
                WHERE NOT EXISTS(
                    SELECT 1 FROM recipe_import_candidates c
                    WHERE c.batch_id=batch.id AND c.row_number=(r.value->>'row_number')::integer)) THEN
            RAISE EXCEPTION 'Importzeilen dürfen nicht hinzugefügt oder entfernt werden.' USING ERRCODE='P1901';
        END IF;
    END IF;
    FOR item IN SELECT value FROM jsonb_array_elements(rows) LOOP
        n:=n+1;
        IF jsonb_typeof(item)<>'object' OR item ?| ARRAY['unreviewed','proposed_not_measured','allergen_not_checked'] THEN
            RAISE EXCEPTION 'Ungültige Importfelder.' USING ERRCODE='P1901';
        END IF;
        rownum:=(item->>'row_number')::integer;
        IF rownum IS DISTINCT FROM n THEN
            RAISE EXCEPTION 'Ungültige Importfelder.' USING ERRCODE='P1901';
        END IF;
        IF p_create THEN
            origin:=COALESCE(item->'original_payload','{}'::jsonb);
            candidate:=COALESCE(NULLIF(item->'candidate_payload','null'::jsonb),origin);
        ELSE
            SELECT original_payload INTO origin FROM recipe_import_candidates
                WHERE batch_id=batch.id AND row_number=rownum;
            candidate:=COALESCE(NULLIF(item->'candidate_payload','null'::jsonb),origin);
        END IF;
        IF jsonb_typeof(origin)<>'object' OR jsonb_typeof(candidate)<>'object'
            OR origin ?| ARRAY['unreviewed','proposed_not_measured','allergen_not_checked']
            OR candidate ?| ARRAY['unreviewed','proposed_not_measured','allergen_not_checked']
            OR EXISTS(SELECT 1 FROM jsonb_object_keys(candidate) k WHERE k NOT IN
                ('title','description','servings','servings_unit_code','prep_minutes','cook_minutes',
                 'source','ingredients','steps','tag_public_ids','images'))
            OR octet_length(candidate::text)>524288 THEN
            RAISE EXCEPTION 'Ungültige Importfelder.' USING ERRCODE='P1901';
        END IF;
        IF origin ? 'source' AND jsonb_typeof(origin->'source')='object' THEN
            kind:=origin->'source'->>'kind';
            reference:=origin->'source'->>'reference';
            note:=origin->'source'->>'note';
        ELSE
            kind:=adapter;
            reference:=CASE WHEN adapter='file_import' AND sha IS NOT NULL
                THEN 'sha256:'||sha||':row:'||rownum::text ELSE NULL END;
            note:=CASE WHEN adapter='file_import' AND sha IS NOT NULL THEN 'sha256:'||sha
                ELSE v_source_note END;
        END IF;
        IF kind IS NULL OR kind NOT IN ('manual','url','file_import','ai_assisted') THEN
            RAISE EXCEPTION 'Ungültige Quelle.' USING ERRCODE='P1901';
        END IF;
        source:=jsonb_build_object(
            'kind',kind,
            'reference',to_jsonb(reference),
            'url',to_jsonb(COALESCE(NULLIF(origin->'source'->>'url',''),v_source_url)),
            'note',to_jsonb(recipe_import_visible_note_v28(note,v_ann)),
            'fetched_at',to_jsonb(COALESCE(NULLIF(origin->'source'->>'fetched_at',''),fetched::text)));
        candidate:=candidate||jsonb_build_object('source',source);
        decision:=COALESCE(item->>'duplicate_decision','undecided');
        IF decision NOT IN ('undecided','create_new','skip_existing') THEN
            RAISE EXCEPTION 'Ungültige Dublettenentscheidung.' USING ERRCODE='P1901';
        END IF;
        target_id:=NULLIF(item->>'target_recipe_public_id','')::uuid;
        target_version:=NULLIF(item->>'target_row_version','')::bigint;
        IF decision='skip_existing' THEN
            IF target_id IS NULL OR target_version IS NULL THEN
                RAISE EXCEPTION 'Überspringen braucht Zielrezept und Version.' USING ERRCODE='P1901';
            END IF;
            IF NOT EXISTS(SELECT 1 FROM recipes r WHERE r.public_id=target_id AND r.location_id=p_location) THEN
                RAISE EXCEPTION 'Unbekanntes Rezept.' USING ERRCODE='22023';
            END IF;
        ELSIF target_id IS NOT NULL OR target_version IS NOT NULL THEN
            RAISE EXCEPTION 'Ungültige Dublettenentscheidung.' USING ERRCODE='P1901';
        END IF;
        IF candidate ? 'ingredients' AND jsonb_typeof(candidate->'ingredients')='array' THEN
            FOR ingredient IN SELECT value FROM jsonb_array_elements(candidate->'ingredients') LOOP
                food_id:=NULLIF(ingredient->>'food_public_id','');
                IF food_id IS NOT NULL THEN
                    IF food_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
                        RAISE EXCEPTION 'Ungültige Importfelder.' USING ERRCODE='P1901';
                    END IF;
                    food_ids:=food_ids||food_id::uuid;
                END IF;
                unit_code:=NULLIF(ingredient->>'unit_code','');
                IF unit_code IS NOT NULL THEN
                    IF unit_code !~ '^[A-Z][A-Z0-9_]{0,15}$' THEN
                        RAISE EXCEPTION 'Ungültige Importfelder.' USING ERRCODE='P1901';
                    END IF;
                    unit_codes:=unit_codes||unit_code;
                END IF;
            END LOOP;
        END IF;
        item:=item||jsonb_build_object('candidate_payload',candidate,'duplicate_decision',decision,
            'original_payload',origin);
        rows:=jsonb_set(rows,ARRAY[(n-1)::text],item);
    END LOOP;
    IF cardinality(food_ids)>0 THEN
        PERFORM f.id FROM foods f WHERE f.location_id=p_location AND f.public_id=ANY(food_ids) ORDER BY f.id FOR SHARE;
        IF (SELECT count(DISTINCT x) FROM unnest(food_ids) x)
            <>(SELECT count(*) FROM foods f WHERE f.location_id=p_location AND f.public_id=ANY(food_ids)) THEN
            RAISE EXCEPTION 'Unbekannte Zutat.' USING ERRCODE='22023';
        END IF;
    END IF;
    IF cardinality(unit_codes)>0 THEN
        PERFORM u.id FROM measurement_units u WHERE u.code=ANY(unit_codes) ORDER BY u.id FOR SHARE;
        IF (SELECT count(DISTINCT x) FROM unnest(unit_codes) x)
            <>(SELECT count(*) FROM measurement_units u WHERE u.code=ANY(unit_codes)) THEN
            RAISE EXCEPTION 'Unbekannte Einheit.' USING ERRCODE='22023';
        END IF;
    END IF;
    digest_value:=recipe_import_hash_v28(v_ann,(
        SELECT jsonb_agg(jsonb_build_object(
            'row_number',(value->>'row_number')::int,
            'candidate_payload',value->'candidate_payload',
            'duplicate_decision',value->>'duplicate_decision',
            'target_recipe_public_id',value->'target_recipe_public_id',
            'target_row_version',value->'target_row_version') ORDER BY (value->>'row_number')::int)
        FROM jsonb_array_elements(rows)));
    IF p_create THEN
        INSERT INTO recipe_import_batches(location_id,adapter_kind,source_filename,source_sha256,content_type,
            source_url,source_note,fetched_at,candidate_hash_sha256,annotations,duplicate_groups,
            created_by,updated_by)
        VALUES(p_location,adapter,NULLIF(p_payload->>'source_filename',''),sha,
            NULLIF(p_payload->>'content_type',''),v_source_url,
            master_text(v_source_note,500,false),fetched,digest_value,v_ann,
            COALESCE(p_payload->'duplicate_groups','[]'::jsonb),p_actor,p_actor)
        RETURNING * INTO batch;
        INSERT INTO recipe_import_candidates(location_id,batch_id,row_number,origin_ref,original_payload,
            original_source_kind,original_source_reference,original_source_url,original_source_note,
            original_fetched_at,source_line,candidate_payload,duplicate_decision,target_recipe_public_id,
            target_row_version,parse_errors)
        SELECT p_location,batch.id,(value->>'row_number')::int,
            batch.public_id::text||':'||(value->>'row_number'),
            COALESCE(value->'original_payload','{}'::jsonb),
            COALESCE(NULLIF(value->'original_payload'->'source'->>'kind',''),adapter),
            NULLIF(value->'original_payload'->'source'->>'reference',''),
            NULLIF(value->'original_payload'->'source'->>'url',''),
            NULLIF(value->'original_payload'->'source'->>'note',''),
            COALESCE(NULLIF(value->'original_payload'->'source'->>'fetched_at','')::timestamptz,fetched),
            NULLIF(value->>'source_line','')::int,
            value->'candidate_payload',
            value->>'duplicate_decision',
            NULLIF(value->>'target_recipe_public_id','')::uuid,
            NULLIF(value->>'target_row_version','')::bigint,
            COALESCE(value->'parse_errors','[]'::jsonb)
        FROM jsonb_array_elements(rows);
        INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
            VALUES(p_actor,'recipe.import_batch','recipe_import_batch',batch.public_id,
                jsonb_build_object('actor_authz_version',p_authz,'location_id',p_location,
                    'row_version_before',0,'row_version_after',batch.row_version,
                    'action','create','candidate_hash_sha256',digest_value));
    ELSE
        IF digest_value=batch.candidate_hash_sha256 AND v_ann=batch.annotations THEN
            RETURN jsonb_build_object('public_id',batch.public_id,'row_version',batch.row_version,
                'candidate_hash_sha256',batch.candidate_hash_sha256,
                'confirmation_hash_sha256',batch.confirmation_hash_sha256,'status',batch.status);
        END IF;
        UPDATE recipe_import_candidates c SET
            candidate_payload=r.payload->'candidate_payload',
            duplicate_decision=r.payload->>'duplicate_decision',
            target_recipe_public_id=NULLIF(r.payload->>'target_recipe_public_id','')::uuid,
            target_row_version=NULLIF(r.payload->>'target_row_version','')::bigint
        FROM jsonb_array_elements(rows) r(payload)
        WHERE c.batch_id=batch.id AND c.row_number=(r.payload->>'row_number')::int;
        UPDATE recipe_import_batches SET annotations=v_ann,
            candidate_hash_sha256=digest_value,confirmation_hash_sha256=NULL,updated_by=p_actor
            WHERE id=batch.id RETURNING * INTO batch;
        INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
            VALUES(p_actor,'recipe.import_batch','recipe_import_batch',batch.public_id,
                jsonb_build_object('actor_authz_version',p_authz,'location_id',p_location,
                    'row_version_before',version_before,'row_version_after',batch.row_version,
                    'action','save','candidate_hash_sha256',digest_value));
    END IF;
    RETURN jsonb_build_object('public_id',batch.public_id,'row_version',batch.row_version,
        'candidate_hash_sha256',batch.candidate_hash_sha256,
        'confirmation_hash_sha256',batch.confirmation_hash_sha256,'status',batch.status);
END;$fn$;

CREATE FUNCTION create_recipe_import_batch_v28(p_actor bigint,p_authz bigint,p_location bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
SELECT recipe_import_save_v28(true,p_actor,p_authz,p_location,NULL,NULL,p_payload);
$fn$;
CREATE FUNCTION update_recipe_import_batch_v28(p_actor bigint,p_authz bigint,p_location bigint,
    p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
SELECT recipe_import_save_v28(false,p_actor,p_authz,p_location,p_target,p_version,p_payload);
$fn$;

REVOKE ALL ON FUNCTION recipe_import_protect_v28(),recipe_import_hash_v28(jsonb,jsonb),
    recipe_import_visible_note_v28(text,jsonb),
    recipe_import_save_v28(boolean,bigint,bigint,bigint,uuid,bigint,jsonb),
    create_recipe_import_batch_v28(bigint,bigint,bigint,jsonb),
    update_recipe_import_batch_v28(bigint,bigint,bigint,uuid,bigint,jsonb)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION create_recipe_import_batch_v28(bigint,bigint,bigint,jsonb),
    update_recipe_import_batch_v28(bigint,bigint,bigint,uuid,bigint,jsonb) TO cafeteria_app;
GRANT SELECT ON recipe_import_batches,recipe_import_candidates TO cafeteria_app,cafeteria_backup;
GRANT SELECT ON SEQUENCE recipe_import_batches_id_seq TO cafeteria_backup;

COMMIT;
