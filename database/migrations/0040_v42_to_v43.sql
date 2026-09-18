-- Rollback: v42-App kennt menu_service_courses nicht.
-- App-Rollback: `APP_IMAGE=<v42-Digest> docker compose up -d --wait --no-deps app`.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

CREATE TABLE menu_service_courses (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    service_id bigint NOT NULL,
    course_kind text NOT NULL,
    planning_state text NOT NULL,
    recipe_revision_id bigint,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT menu_service_courses_pkey PRIMARY KEY (id),
    CONSTRAINT menu_service_courses_public_id_key UNIQUE (public_id),
    CONSTRAINT menu_service_courses_service_kind_key UNIQUE (service_id, course_kind),
    CONSTRAINT menu_service_courses_location_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT menu_service_courses_service_fkey FOREIGN KEY (service_id) REFERENCES menu_services(id) ON DELETE CASCADE,
    CONSTRAINT menu_service_courses_revision_fkey FOREIGN KEY (recipe_revision_id) REFERENCES recipe_revisions(id) ON DELETE RESTRICT,
    CONSTRAINT menu_service_courses_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT menu_service_courses_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT menu_service_courses_kind_check CHECK (course_kind IN ('soup', 'dessert')),
    CONSTRAINT menu_service_courses_state_check CHECK (planning_state IN ('planned', 'not_offered')),
    CONSTRAINT menu_service_courses_row_version_check CHECK (row_version > 0),
    CONSTRAINT menu_service_courses_content_check CHECK (
        (planning_state = 'planned' AND recipe_revision_id IS NOT NULL)
        OR (planning_state = 'not_offered' AND recipe_revision_id IS NULL)
    )
);

CREATE TABLE menu_item_course_exceptions (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    menu_item_id bigint NOT NULL,
    course_kind text NOT NULL,
    planning_state text NOT NULL,
    recipe_revision_id bigint,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT menu_item_course_exceptions_pkey PRIMARY KEY (id),
    CONSTRAINT menu_item_course_exceptions_public_id_key UNIQUE (public_id),
    CONSTRAINT menu_item_course_exceptions_item_kind_key UNIQUE (menu_item_id, course_kind),
    CONSTRAINT menu_item_course_exceptions_item_fkey FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE,
    CONSTRAINT menu_item_course_exceptions_revision_fkey FOREIGN KEY (recipe_revision_id) REFERENCES recipe_revisions(id) ON DELETE RESTRICT,
    CONSTRAINT menu_item_course_exceptions_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT menu_item_course_exceptions_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT menu_item_course_exceptions_kind_check CHECK (course_kind IN ('soup', 'dessert')),
    CONSTRAINT menu_item_course_exceptions_state_check CHECK (planning_state IN ('planned', 'not_offered')),
    CONSTRAINT menu_item_course_exceptions_row_version_check CHECK (row_version > 0),
    CONSTRAINT menu_item_course_exceptions_content_check CHECK (
        (planning_state = 'planned' AND recipe_revision_id IS NOT NULL)
        OR (planning_state = 'not_offered' AND recipe_revision_id IS NULL)
    )
);

GRANT SELECT, INSERT, UPDATE, DELETE ON menu_service_courses, menu_item_course_exceptions TO cafeteria_app;
GRANT SELECT ON menu_service_courses, menu_item_course_exceptions TO cafeteria_backup;
GRANT SELECT ON SEQUENCE menu_service_courses_id_seq, menu_item_course_exceptions_id_seq TO cafeteria_backup;

CREATE OR REPLACE FUNCTION patient_key_is_forbidden(k text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT compact = ''
        OR compact <> ALL (ARRAY[
            'channel', 'days', 'date', 'notice', 'services', 'mealcode', 'mealname',
            'options', 'allergenreviewstatus', 'allergens', 'components', 'description',
            'externalid', 'labels', 'note', 'origins', 'title', 'typecode', 'typename',
            'code', 'name', 'presence', 'countrycode', 'ingredient', 'text', 'state',
            'weekday', 'location', 'profilecode', 'revisionid', 'schemaversion',
            'sharednote', 'weekend', 'weekstart', 'servicestate',
            'servicestart', 'serviceend', 'areaname',
            'accompanimentcode', 'accompanimentname',
            'carbohydrates', 'dessert', 'dessertoverride', 'fat', 'fiber', 'kcal', 'kj',
            'nutrition', 'protein', 'recipepublicid', 'salt', 'saturatedfat', 'soup',
            'soupoverride', 'sugar'
        ]::text[])
        OR compact ~ '(price|prices|preis|preise|cost|costs|amount|amounts|kosten|betrag|rappen|currency|chf|fee|tarif|tariff|charge)'
    FROM (SELECT cafeteria.normalize_patient_key(k) AS compact) s;
$$;

COMMIT;
