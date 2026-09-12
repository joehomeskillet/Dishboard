BEGIN;
SET search_path TO cafeteria, public;

ALTER TABLE recipe_import_batches ADD COLUMN imported_result jsonb;

CREATE FUNCTION recipe_import_head_source_v29(p_batch recipe_import_batches, p_row recipe_import_candidates)
RETURNS jsonb
LANGUAGE plpgsql STABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE note text; fetched text; reference text;
BEGIN
    fetched:=COALESCE(NULLIF(p_row.original_payload->'source'->>'fetched_at',''),
        to_char(p_row.original_fetched_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS"+00:00"'));
    IF p_row.original_source_kind='file_import' THEN
        note:=COALESCE(NULLIF(p_row.candidate_payload->'source'->>'note',''),
            recipe_import_visible_note_v28(
                NULLIF('sha256:'||COALESCE(p_batch.source_sha256,''),'sha256:'), p_batch.annotations));
        RETURN jsonb_build_object('kind','file_import','reference',to_jsonb(p_row.origin_ref),
            'url',to_jsonb(p_row.original_source_url),'note',to_jsonb(note),'fetched_at',to_jsonb(fetched));
    END IF;
    reference:=COALESCE(NULLIF(p_row.original_source_reference,''),p_row.origin_ref);
    RETURN jsonb_build_object('kind',p_row.original_source_kind,'reference',to_jsonb(reference),
        'url',to_jsonb(p_row.original_source_url),'note',to_jsonb(p_row.original_source_note),
        'fetched_at',to_jsonb(fetched));
END;$fn$;

CREATE FUNCTION recipe_import_recipe_payload_v29(p_batch recipe_import_batches, p_row recipe_import_candidates)
RETURNS jsonb
LANGUAGE plpgsql STABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE payload jsonb; ingredients jsonb:='[]'::jsonb; item jsonb; ing jsonb; src jsonb;
BEGIN
    src:=recipe_import_head_source_v29(p_batch,p_row);
    payload:=p_row.candidate_payload;
    FOR item IN SELECT value FROM jsonb_array_elements(COALESCE(payload->'ingredients','[]'::jsonb)) LOOP
        ing:=jsonb_build_object(
            'line_public_id',NULL,
            'group_label',item->'group_label',
            'ingredient_text',item->'ingredient_text',
            'food_public_id',item->'food_public_id',
            'quantity',item->'quantity',
            'unit_code',item->'unit_code',
            'note',item->'note',
            'source_kind',to_jsonb(CASE WHEN p_row.original_source_kind='file_import'
                THEN 'file_import' ELSE COALESCE(item->>'source_kind',p_row.original_source_kind) END),
            'source_reference',to_jsonb(CASE WHEN p_row.original_source_kind='file_import'
                THEN p_row.origin_ref ELSE COALESCE(NULLIF(item->>'source_reference',''),
                    p_row.original_source_reference,p_row.origin_ref) END),
            'fetched_at',COALESCE(item->'fetched_at',src->'fetched_at'));
        ingredients:=ingredients||jsonb_build_array(ing);
    END LOOP;
    RETURN jsonb_build_object(
        'title',payload->'title','description',payload->'description','servings',payload->'servings',
        'servings_unit_code',payload->'servings_unit_code','prep_minutes',payload->'prep_minutes',
        'cook_minutes',payload->'cook_minutes','source',src,'ingredients',ingredients,
        'steps',COALESCE(payload->'steps','[]'::jsonb),
        'tag_public_ids',COALESCE(payload->'tag_public_ids','[]'::jsonb),
        'images',COALESCE(payload->'images','[]'::jsonb));
END;$fn$;

CREATE FUNCTION commit_recipe_import_batch_v29(p_actor bigint,p_authz bigint,p_location bigint,
    p_target uuid,p_version bigint,p_payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE batch recipe_import_batches%ROWTYPE; cand recipe_import_candidates%ROWTYPE;
    recipe recipes%ROWTYPE; payload jsonb; item jsonb; created jsonb; results jsonb:='[]'::jsonb;
    version_before bigint; food_ids uuid[]:=ARRAY[]::uuid[]; unit_codes text[]:=ARRAY[]::text[];
    tag_ids uuid[]:=ARRAY[]::uuid[]; skip_ids uuid[]:=ARRAY[]::uuid[];
BEGIN
    PERFORM require_master_data_actor(p_actor,p_authz,'recipe.import');
    PERFORM master_location(p_location);
    PERFORM master_expectation(p_target,p_version);
    PERFORM master_payload(p_payload,ARRAY['candidate_hash_sha256']);
    IF p_payload->>'candidate_hash_sha256' IS NULL
        OR p_payload->>'candidate_hash_sha256' !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Ursprüngliche Bestätigung erforderlich.' USING ERRCODE='P1901';
    END IF;
    SELECT * INTO batch FROM recipe_import_batches
        WHERE public_id=p_target AND location_id=p_location;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannter Importstapel.' USING ERRCODE='22023'; END IF;
    IF batch.status<>'draft' THEN
        RAISE EXCEPTION 'Importstapel ist nicht mehr bearbeitbar.' USING ERRCODE='55000';
    END IF;
    FOR cand IN SELECT * FROM recipe_import_candidates WHERE batch_id=batch.id ORDER BY row_number LOOP
        IF cand.duplicate_decision='skip_existing' AND cand.target_recipe_public_id IS NOT NULL THEN
            skip_ids:=skip_ids||cand.target_recipe_public_id;
        ELSIF cand.duplicate_decision='create_new' THEN
            payload:=recipe_import_recipe_payload_v29(batch,cand);
            IF NULLIF(payload->>'servings_unit_code','') IS NOT NULL THEN
                unit_codes:=unit_codes||(payload->>'servings_unit_code');
            END IF;
            FOR item IN SELECT value FROM jsonb_array_elements(COALESCE(payload->'ingredients','[]'::jsonb)) LOOP
                IF NULLIF(item->>'unit_code','') IS NOT NULL THEN
                    unit_codes:=unit_codes||(item->>'unit_code');
                END IF;
                IF NULLIF(item->>'food_public_id','') IS NOT NULL
                    AND item->>'food_public_id' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
                    food_ids:=food_ids||(item->>'food_public_id')::uuid;
                END IF;
            END LOOP;
            FOR item IN SELECT to_jsonb(value) FROM jsonb_array_elements_text(
                COALESCE(payload->'tag_public_ids','[]'::jsonb)) LOOP
                IF (item#>>'{}') ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
                    tag_ids:=tag_ids||(item#>>'{}')::uuid;
                END IF;
            END LOOP;
        END IF;
    END LOOP;
    IF cardinality(unit_codes)>0 THEN
        PERFORM u.id FROM measurement_units u WHERE u.code=ANY(unit_codes) ORDER BY u.id FOR SHARE;
    END IF;
    IF cardinality(tag_ids)>0 THEN
        PERFORM t.id FROM tags t WHERE t.location_id=p_location AND t.public_id=ANY(tag_ids)
            ORDER BY t.id FOR SHARE;
    END IF;
    IF cardinality(food_ids)>0 THEN
        PERFORM s.id FROM storage_locations s
            JOIN food_storage_locations l ON l.storage_location_id=s.id AND l.location_id=s.location_id
            JOIN foods f ON f.id=l.food_id AND f.location_id=l.location_id
            WHERE f.location_id=p_location AND f.public_id=ANY(food_ids) ORDER BY s.id FOR SHARE;
        PERFORM f.id FROM foods f WHERE f.location_id=p_location AND f.public_id=ANY(food_ids)
            ORDER BY f.id FOR SHARE;
    END IF;
    IF cardinality(skip_ids)>0 THEN
        PERFORM r.id FROM recipes r WHERE r.location_id=p_location AND r.public_id=ANY(skip_ids)
            ORDER BY r.id FOR UPDATE;
    END IF;
    SELECT * INTO batch FROM recipe_import_batches WHERE id=batch.id FOR UPDATE;
    IF batch.row_version<>p_version THEN
        RAISE EXCEPTION 'Importstapel wurde geändert.' USING ERRCODE='55000';
    END IF;
    IF batch.status<>'draft' THEN
        RAISE EXCEPTION 'Importstapel ist nicht mehr bearbeitbar.' USING ERRCODE='55000';
    END IF;
    IF batch.confirmation_hash_sha256 IS NULL
        OR batch.confirmation_hash_sha256 IS DISTINCT FROM batch.candidate_hash_sha256
        OR batch.candidate_hash_sha256 IS DISTINCT FROM p_payload->>'candidate_hash_sha256' THEN
        RAISE EXCEPTION 'Ursprüngliche Bestätigung erforderlich.' USING ERRCODE='55000';
    END IF;
    version_before:=batch.row_version;
    FOR cand IN SELECT * FROM recipe_import_candidates WHERE batch_id=batch.id ORDER BY row_number LOOP
        IF jsonb_array_length(COALESCE(cand.parse_errors,'[]'::jsonb))>0 THEN
            RAISE EXCEPTION 'Importzeile ist unvollständig.' USING ERRCODE='P1901';
        END IF;
        IF cand.duplicate_decision NOT IN ('create_new','skip_existing') THEN
            RAISE EXCEPTION 'Jede Zeile braucht eine Dublettenentscheidung.' USING ERRCODE='P1901';
        END IF;
        IF cand.duplicate_decision='skip_existing' THEN
            SELECT * INTO recipe FROM recipes
                WHERE public_id=cand.target_recipe_public_id AND location_id=p_location;
            IF NOT FOUND OR NOT recipe.active
                OR recipe.row_version IS DISTINCT FROM cand.target_row_version THEN
                RAISE EXCEPTION 'Übersprungenes Rezept ist nicht mehr das geprüfte Ziel.'
                    USING ERRCODE='55000';
            END IF;
            results:=results||jsonb_build_array(jsonb_build_object(
                'row_number',cand.row_number,'decision','skip_existing',
                'recipe_public_id',recipe.public_id,'recipe_row_version',recipe.row_version));
            CONTINUE;
        END IF;
        payload:=recipe_import_recipe_payload_v29(batch,cand);
        IF jsonb_typeof(payload->'ingredients') IS DISTINCT FROM 'array'
            OR jsonb_array_length(payload->'ingredients')<1 THEN
            RAISE EXCEPTION 'Importzeile ist unvollständig.' USING ERRCODE='P1901';
        END IF;
        FOR item IN SELECT value FROM jsonb_array_elements(payload->'ingredients') LOOP
            IF NULLIF(item->>'food_public_id','') IS NULL OR NULLIF(item->>'unit_code','') IS NULL
                OR NOT master_quantity((item->>'quantity')::numeric) THEN
                RAISE EXCEPTION 'Importzeile ist unvollständig.' USING ERRCODE='P1901';
            END IF;
            IF NOT EXISTS(
                SELECT 1 FROM foods f
                    JOIN food_storage_locations l ON l.food_id=f.id AND l.location_id=f.location_id
                    JOIN storage_locations s ON s.id=l.storage_location_id AND s.location_id=l.location_id
                WHERE f.public_id=(item->>'food_public_id')::uuid AND f.location_id=p_location
                    AND s.active) THEN
                RAISE EXCEPTION 'Importzeile ist unvollständig.' USING ERRCODE='P1901';
            END IF;
        END LOOP;
        created:=create_recipe_v22(p_actor,p_authz,p_location,NULL,NULL,payload);
        INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
            VALUES(p_actor,'recipe.import','recipe',(created->>'public_id')::uuid,
                jsonb_build_object('actor_authz_version',p_authz,'location_id',p_location,
                    'batch_public_id',batch.public_id,'origin_ref',cand.origin_ref,
                    'row_number',cand.row_number,'adapter_kind',batch.adapter_kind,
                    'candidate_hash_sha256',batch.candidate_hash_sha256,
                    'recipe_row_version',created->'row_version'));
        results:=results||jsonb_build_array(jsonb_build_object(
            'row_number',cand.row_number,'decision','create_new',
            'recipe_public_id',created->>'public_id',
            'recipe_row_version',created->'row_version'));
    END LOOP;
    UPDATE recipe_import_batches SET status='imported',imported_result=results,updated_by=p_actor
        WHERE id=batch.id RETURNING * INTO batch;
    INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
        VALUES(p_actor,'recipe.import_batch','recipe_import_batch',batch.public_id,
            jsonb_build_object('actor_authz_version',p_authz,'location_id',p_location,
                'row_version_before',version_before,'row_version_after',batch.row_version,
                'action','commit','candidate_hash_sha256',batch.candidate_hash_sha256,
                'imported_result',results));
    RETURN jsonb_build_object('public_id',batch.public_id,'row_version',batch.row_version,
        'status',batch.status,'imported_result',results,
        'candidate_hash_sha256',batch.candidate_hash_sha256);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation
    OR not_null_violation OR invalid_datetime_format OR datetime_field_overflow THEN
    RAISE EXCEPTION 'Importzeile ist unvollständig.' USING ERRCODE='P1901';
END;$fn$;

REVOKE ALL ON FUNCTION recipe_import_head_source_v29(recipe_import_batches,recipe_import_candidates),
    recipe_import_recipe_payload_v29(recipe_import_batches,recipe_import_candidates),
    commit_recipe_import_batch_v29(bigint,bigint,bigint,uuid,bigint,jsonb)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION commit_recipe_import_batch_v29(bigint,bigint,bigint,uuid,bigint,jsonb)
    TO cafeteria_app;

COMMIT;
