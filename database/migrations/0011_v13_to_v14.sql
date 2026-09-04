BEGIN;

CREATE OR REPLACE FUNCTION cafeteria.lock_component_metadata_masters(
    p_label_codes text[],
    p_allergen_codes text[]
)
RETURNS TABLE (
    master_kind text,
    master_id smallint,
    code text,
    active boolean
)
LANGUAGE plpgsql
SECURITY DEFINER
VOLATILE
PARALLEL UNSAFE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
BEGIN
    IF p_label_codes IS NULL
       OR p_allergen_codes IS NULL
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.unnest(p_label_codes) AS requested(code)
           WHERE requested.code IS NULL
       )
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.unnest(p_allergen_codes) AS requested(code)
           WHERE requested.code IS NULL
       ) THEN
        RAISE EXCEPTION 'metadata code arrays must be non-null and contain no nulls'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT 'label'::text, label.id, label.code, label.active
    FROM cafeteria.dietary_labels AS label
    WHERE label.code = ANY (p_label_codes)
    ORDER BY label.id
    FOR SHARE OF label;

    RETURN QUERY
    SELECT 'allergen'::text, allergen.id, allergen.code, allergen.active
    FROM cafeteria.allergens AS allergen
    WHERE allergen.code = ANY (p_allergen_codes)
    ORDER BY allergen.id
    FOR SHARE OF allergen;
END;
$function$;

REVOKE ALL ON FUNCTION
    cafeteria.lock_component_metadata_masters(text[], text[])
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

GRANT EXECUTE ON FUNCTION
    cafeteria.lock_component_metadata_masters(text[], text[])
TO cafeteria_app;

COMMIT;
