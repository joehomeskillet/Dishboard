BEGIN;

-- Lock the immutable proposal source together with every old/new revision head.
-- Call before aggregate/template locks; never discover another head afterwards.
CREATE FUNCTION cafeteria.lock_menu_recipe_sources_v31(
    p_actor bigint,p_authz bigint,p_location bigint,p_ids bigint[],p_source uuid)
RETURNS TABLE(revision_id bigint,revision_public_id uuid,recipe_id bigint,
    recipe_public_id uuid,active boolean,content_hash_sha256 text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v_source bigint;
BEGIN
    PERFORM cafeteria.begin_menu_binding_write_v26(p_actor,p_authz,p_location);
    IF p_ids IS NULL OR cardinality(p_ids)>32767 OR array_ndims(p_ids)>1
       OR EXISTS(SELECT 1 FROM unnest(p_ids) x WHERE x IS NULL OR x<=0)
       OR cardinality(p_ids)<>(SELECT count(DISTINCT x) FROM unnest(p_ids) x)
       OR cardinality(p_ids)<>(SELECT count(*) FROM cafeteria.recipe_revisions r
           WHERE r.id=ANY(p_ids) AND r.location_id=p_location) THEN
        RAISE EXCEPTION 'Ungültige Rezeptrevisionen.' USING ERRCODE='P1901';
    END IF;
    SELECT h.id INTO v_source FROM cafeteria.recipes h
        WHERE h.public_id=p_source AND h.location_id=p_location;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Ungültiges ursprüngliches Rezept.' USING ERRCODE='P1901';
    END IF;
    -- IN deduplicates the union; ORDER BY precedes row-lock acquisition.
    PERFORM h.id FROM cafeteria.recipes h WHERE h.id IN (
        SELECT r.recipe_id FROM cafeteria.recipe_revisions r WHERE r.id=ANY(p_ids)
        UNION SELECT v_source) ORDER BY h.id FOR SHARE;
    IF NOT EXISTS(SELECT 1 FROM cafeteria.recipes h
        WHERE h.id=v_source AND h.public_id=p_source AND h.location_id=p_location) THEN
        RAISE EXCEPTION 'Ursprüngliches Rezept wurde geändert.' USING ERRCODE='55000';
    END IF;
    -- An archived source is valid; the caller rechecks its original active state.
    RETURN QUERY SELECT r.id,r.public_id,h.id,h.public_id,h.active,r.content_hash_sha256
        FROM cafeteria.recipe_revisions r JOIN cafeteria.recipes h ON h.id=r.recipe_id
        WHERE r.id=ANY(p_ids) AND r.location_id=p_location ORDER BY r.id;
END;$fn$;

REVOKE ALL ON FUNCTION cafeteria.lock_menu_recipe_sources_v31(bigint,bigint,bigint,bigint[],uuid)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION cafeteria.lock_menu_recipe_sources_v31(bigint,bigint,bigint,bigint[],uuid)
TO cafeteria_app;

COMMIT;
