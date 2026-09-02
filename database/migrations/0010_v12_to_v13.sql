BEGIN;

SET search_path TO cafeteria, public;

CREATE TABLE IF NOT EXISTS menu_components (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid DEFAULT gen_random_uuid(),
    location_id bigint,
    profile_scope text,
    category text,
    name text,
    origin_country_code char(2),
    active boolean DEFAULT true,
    row_version bigint DEFAULT 1,
    created_at timestamptz DEFAULT clock_timestamp(),
    updated_at timestamptz DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS component_allergens (
    component_id bigint,
    allergen_id smallint,
    presence text
);

CREATE TABLE IF NOT EXISTS component_labels (
    component_id bigint,
    label_id smallint
);

ALTER TABLE menu_items
    ADD COLUMN IF NOT EXISTS allergen_mode text;
ALTER TABLE menu_items
    ADD COLUMN IF NOT EXISTS origin_mode text;
ALTER TABLE menu_items
    ADD COLUMN IF NOT EXISTS label_mode text;
ALTER TABLE menu_item_components
    ADD COLUMN IF NOT EXISTS component_id bigint;
ALTER TABLE menu_item_components
    ADD COLUMN IF NOT EXISTS component_row_version bigint;

UPDATE menu_items
SET allergen_mode='manual'
WHERE allergen_mode IS NULL;
UPDATE menu_items
SET origin_mode='manual'
WHERE origin_mode IS NULL;
UPDATE menu_items
SET label_mode='manual'
WHERE label_mode IS NULL;

DO $v13_legacy_origin_conflicts$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM menu_item_components mic
        JOIN menu_items i ON i.id=mic.menu_item_id
        JOIN menu_services s ON s.id=i.service_id
        JOIN menu_weeks w ON w.id=s.menu_week_id
        JOIN offer_profiles p ON p.id=w.profile_id
        JOIN origin_declarations o
          ON o.menu_item_id=i.id
         AND lower(btrim(o.ingredient))=lower(btrim(mic.component_text))
        GROUP BY w.location_id, p.code, lower(btrim(mic.component_text))
        HAVING count(DISTINCT o.country_code) > 1
    ) THEN
        RAISE EXCEPTION 'v13 conflicting legacy origin country codes';
    END IF;
END;
$v13_legacy_origin_conflicts$;

WITH legacy_components AS (
    SELECT
        w.location_id,
        p.code AS profile_scope,
        lower(btrim(mic.component_text)) AS normalized_name,
        min(btrim(mic.component_text) COLLATE "C") AS name
    FROM menu_item_components mic
    JOIN menu_items i ON i.id=mic.menu_item_id
    JOIN menu_services s ON s.id=i.service_id
    JOIN menu_weeks w ON w.id=s.menu_week_id
    JOIN offer_profiles p ON p.id=w.profile_id
    GROUP BY w.location_id, p.code, lower(btrim(mic.component_text))
), legacy_origins AS (
    SELECT
        w.location_id,
        p.code AS profile_scope,
        lower(btrim(mic.component_text)) AS normalized_name,
        min(o.country_code) AS origin_country_code
    FROM menu_item_components mic
    JOIN menu_items i ON i.id=mic.menu_item_id
    JOIN menu_services s ON s.id=i.service_id
    JOIN menu_weeks w ON w.id=s.menu_week_id
    JOIN offer_profiles p ON p.id=w.profile_id
    JOIN origin_declarations o
      ON o.menu_item_id=i.id
     AND lower(btrim(o.ingredient))=lower(btrim(mic.component_text))
    GROUP BY w.location_id, p.code, lower(btrim(mic.component_text))
    HAVING count(DISTINCT o.country_code)=1
)
INSERT INTO menu_components(
    location_id, profile_scope, category, name, origin_country_code
)
SELECT
    legacy.location_id,
    legacy.profile_scope,
    'other',
    legacy.name,
    origins.origin_country_code
FROM legacy_components legacy
LEFT JOIN legacy_origins origins
  ON origins.location_id=legacy.location_id
 AND origins.profile_scope=legacy.profile_scope
 AND origins.normalized_name=legacy.normalized_name
WHERE NOT EXISTS (
    SELECT 1
    FROM menu_components existing
    WHERE existing.location_id=legacy.location_id
      AND existing.profile_scope=legacy.profile_scope
      AND lower(btrim(existing.name))=legacy.normalized_name
);

UPDATE menu_item_components mic
SET component_id=component.id,
    component_row_version=component.row_version
FROM menu_items item
JOIN menu_services service ON service.id=item.service_id
JOIN menu_weeks week_row ON week_row.id=service.menu_week_id
JOIN offer_profiles profile ON profile.id=week_row.profile_id
JOIN menu_components component
  ON component.location_id=week_row.location_id
 AND component.profile_scope=profile.code
WHERE item.id=mic.menu_item_id
  AND lower(btrim(component.name))=lower(btrim(mic.component_text))
  AND mic.component_id IS NULL;

UPDATE menu_item_components mic
SET component_row_version=component.row_version
FROM menu_components component
WHERE component.id=mic.component_id
  AND mic.component_row_version IS NULL;

WITH legacy_component_allergens AS (
    SELECT
        mic.component_id,
        mia.allergen_id,
        CASE
            WHEN bool_or(mia.presence='contains') THEN 'contains'
            ELSE 'may_contain'
        END AS presence
    FROM menu_item_components mic
    JOIN menu_item_allergens mia ON mia.menu_item_id=mic.menu_item_id
    WHERE mic.component_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM menu_item_components sibling
          WHERE sibling.menu_item_id=mic.menu_item_id
            AND sibling.sort_order<>mic.sort_order
      )
    GROUP BY mic.component_id, mia.allergen_id
)
INSERT INTO component_allergens(component_id, allergen_id, presence)
SELECT legacy.component_id, legacy.allergen_id, legacy.presence
FROM legacy_component_allergens legacy
WHERE NOT EXISTS (
    SELECT 1
    FROM component_allergens existing
    WHERE existing.component_id=legacy.component_id
      AND existing.allergen_id=legacy.allergen_id
);

WITH legacy_component_labels AS (
    SELECT DISTINCT mic.component_id, mil.label_id
    FROM menu_item_components mic
    JOIN menu_item_labels mil ON mil.menu_item_id=mic.menu_item_id
    WHERE mic.component_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM menu_item_components sibling
          WHERE sibling.menu_item_id=mic.menu_item_id
            AND sibling.sort_order<>mic.sort_order
      )
)
INSERT INTO component_labels(component_id, label_id)
SELECT legacy.component_id, legacy.label_id
FROM legacy_component_labels legacy
WHERE NOT EXISTS (
    SELECT 1
    FROM component_labels existing
    WHERE existing.component_id=legacy.component_id
      AND existing.label_id=legacy.label_id
);

DO $v13_completeness$
BEGIN
    IF EXISTS (
        SELECT 1 FROM menu_items
        WHERE allergen_mode IS NULL OR origin_mode IS NULL OR label_mode IS NULL
    ) THEN
        RAISE EXCEPTION 'v13 mode backfill incomplete';
    END IF;
    IF EXISTS (
        SELECT 1 FROM menu_item_components
        WHERE component_id IS NOT NULL AND component_row_version IS NULL
    ) THEN
        RAISE EXCEPTION 'v13 component version backfill incomplete';
    END IF;
    IF EXISTS (
        SELECT 1 FROM menu_components
        WHERE public_id IS NULL OR location_id IS NULL OR profile_scope IS NULL
           OR category IS NULL OR name IS NULL OR active IS NULL OR row_version IS NULL
           OR created_at IS NULL OR updated_at IS NULL
    ) THEN
        RAISE EXCEPTION 'v13 component catalog backfill incomplete';
    END IF;
END;
$v13_completeness$;

DO $v13_constraints$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_components'::regclass AND conname='menu_components_pkey'
    ) THEN
        ALTER TABLE menu_components
            ADD CONSTRAINT menu_components_pkey PRIMARY KEY (id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_components'::regclass
          AND conname='menu_components_public_id_key'
    ) THEN
        ALTER TABLE menu_components
            ADD CONSTRAINT menu_components_public_id_key UNIQUE (public_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_components'::regclass
          AND conname='menu_components_location_id_fkey'
    ) THEN
        ALTER TABLE menu_components
            ADD CONSTRAINT menu_components_location_id_fkey
            FOREIGN KEY (location_id) REFERENCES locations(id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_components'::regclass
          AND conname='menu_components_profile_scope_check'
    ) THEN
        ALTER TABLE menu_components
            ADD CONSTRAINT menu_components_profile_scope_check
            CHECK (profile_scope IN ('common', 'patient', 'staff_guest'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_components'::regclass
          AND conname='menu_components_category_check'
    ) THEN
        ALTER TABLE menu_components
            ADD CONSTRAINT menu_components_category_check
            CHECK (category IN ('meat', 'side', 'vegetable', 'sauce', 'dessert', 'other'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_components'::regclass
          AND conname='menu_components_name_check'
    ) THEN
        ALTER TABLE menu_components
            ADD CONSTRAINT menu_components_name_check CHECK (btrim(name) <> '');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_components'::regclass
          AND conname='menu_components_origin_country_code_check'
    ) THEN
        ALTER TABLE menu_components
            ADD CONSTRAINT menu_components_origin_country_code_check
            CHECK (origin_country_code ~ '^[A-Z]{2}$');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_components'::regclass
          AND conname='menu_components_row_version_check'
    ) THEN
        ALTER TABLE menu_components
            ADD CONSTRAINT menu_components_row_version_check CHECK (row_version > 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='component_allergens'::regclass
          AND conname='component_allergens_pkey'
    ) THEN
        ALTER TABLE component_allergens
            ADD CONSTRAINT component_allergens_pkey PRIMARY KEY (component_id, allergen_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='component_allergens'::regclass
          AND conname='component_allergens_component_id_fkey'
    ) THEN
        ALTER TABLE component_allergens
            ADD CONSTRAINT component_allergens_component_id_fkey
            FOREIGN KEY (component_id) REFERENCES menu_components(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='component_allergens'::regclass
          AND conname='component_allergens_allergen_id_fkey'
    ) THEN
        ALTER TABLE component_allergens
            ADD CONSTRAINT component_allergens_allergen_id_fkey
            FOREIGN KEY (allergen_id) REFERENCES allergens(id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='component_allergens'::regclass
          AND conname='component_allergens_presence_check'
    ) THEN
        ALTER TABLE component_allergens
            ADD CONSTRAINT component_allergens_presence_check
            CHECK (presence IN ('contains', 'may_contain'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='component_labels'::regclass
          AND conname='component_labels_pkey'
    ) THEN
        ALTER TABLE component_labels
            ADD CONSTRAINT component_labels_pkey PRIMARY KEY (component_id, label_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='component_labels'::regclass
          AND conname='component_labels_component_id_fkey'
    ) THEN
        ALTER TABLE component_labels
            ADD CONSTRAINT component_labels_component_id_fkey
            FOREIGN KEY (component_id) REFERENCES menu_components(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='component_labels'::regclass
          AND conname='component_labels_label_id_fkey'
    ) THEN
        ALTER TABLE component_labels
            ADD CONSTRAINT component_labels_label_id_fkey
            FOREIGN KEY (label_id) REFERENCES dietary_labels(id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_items'::regclass
          AND conname='menu_items_allergen_mode_check'
    ) THEN
        ALTER TABLE menu_items
            ADD CONSTRAINT menu_items_allergen_mode_check
            CHECK (allergen_mode IN ('auto', 'manual'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_items'::regclass
          AND conname='menu_items_origin_mode_check'
    ) THEN
        ALTER TABLE menu_items
            ADD CONSTRAINT menu_items_origin_mode_check
            CHECK (origin_mode IN ('auto', 'manual'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_items'::regclass
          AND conname='menu_items_label_mode_check'
    ) THEN
        ALTER TABLE menu_items
            ADD CONSTRAINT menu_items_label_mode_check
            CHECK (label_mode IN ('auto', 'manual'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_item_components'::regclass
          AND conname='menu_item_components_component_id_fkey'
    ) THEN
        ALTER TABLE menu_item_components
            ADD CONSTRAINT menu_item_components_component_id_fkey
            FOREIGN KEY (component_id) REFERENCES menu_components(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_item_components'::regclass
          AND conname='menu_item_components_component_row_version_check'
    ) THEN
        ALTER TABLE menu_item_components
            ADD CONSTRAINT menu_item_components_component_row_version_check
            CHECK (component_row_version > 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='menu_item_components'::regclass
          AND conname='menu_item_components_component_link_check'
    ) THEN
        ALTER TABLE menu_item_components
            ADD CONSTRAINT menu_item_components_component_link_check CHECK (
                (component_id IS NULL AND component_row_version IS NULL)
                OR (component_id IS NOT NULL AND component_row_version IS NOT NULL)
            );
    END IF;
END;
$v13_constraints$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_menu_components_location_scope_name
    ON menu_components(location_id, profile_scope, lower(btrim(name)));

ALTER TABLE menu_components
    ALTER COLUMN public_id SET NOT NULL,
    ALTER COLUMN location_id SET NOT NULL,
    ALTER COLUMN profile_scope SET NOT NULL,
    ALTER COLUMN category SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN active SET NOT NULL,
    ALTER COLUMN row_version SET NOT NULL,
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE component_allergens
    ALTER COLUMN component_id SET NOT NULL,
    ALTER COLUMN allergen_id SET NOT NULL,
    ALTER COLUMN presence SET NOT NULL;
ALTER TABLE component_labels
    ALTER COLUMN component_id SET NOT NULL,
    ALTER COLUMN label_id SET NOT NULL;
ALTER TABLE menu_items
    ALTER COLUMN allergen_mode SET DEFAULT 'manual',
    ALTER COLUMN allergen_mode SET NOT NULL,
    ALTER COLUMN origin_mode SET DEFAULT 'manual',
    ALTER COLUMN origin_mode SET NOT NULL,
    ALTER COLUMN label_mode SET DEFAULT 'manual',
    ALTER COLUMN label_mode SET NOT NULL;

CREATE OR REPLACE FUNCTION validate_menu_item_component_scope()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = cafeteria, pg_temp
AS $validate_menu_item_component_scope$
DECLARE
    item_location_id bigint;
    item_profile_scope text;
    component_location_id bigint;
    component_profile_scope text;
BEGIN
    IF NEW.component_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT week_row.location_id, profile.code
    INTO item_location_id, item_profile_scope
    FROM menu_items item
    JOIN menu_services service ON service.id=item.service_id
    JOIN menu_weeks week_row ON week_row.id=service.menu_week_id
    JOIN offer_profiles profile ON profile.id=week_row.profile_id
    WHERE item.id=NEW.menu_item_id
    FOR KEY SHARE OF item, service, week_row;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    SELECT component.location_id, component.profile_scope
    INTO component_location_id, component_profile_scope
    FROM menu_components component
    WHERE component.id=NEW.component_id
    FOR KEY SHARE OF component;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    IF component_location_id IS DISTINCT FROM item_location_id THEN
        RAISE EXCEPTION
            'Komponenten-Location % passt nicht zur Menue-Location %.',
            component_location_id,
            item_location_id
            USING ERRCODE='23514',
                  CONSTRAINT='menu_item_components_scope';
    END IF;

    IF component_profile_scope <> 'common'
       AND component_profile_scope IS DISTINCT FROM item_profile_scope THEN
        RAISE EXCEPTION
            'Komponenten-Profil-Scope % ist fuer Menueprofil % nicht erlaubt.',
            component_profile_scope,
            item_profile_scope
            USING ERRCODE='23514',
                  CONSTRAINT='menu_item_components_scope';
    END IF;

    RETURN NEW;
END;
$validate_menu_item_component_scope$;

DROP TRIGGER IF EXISTS trg_menu_item_components_scope ON menu_item_components;
CREATE TRIGGER trg_menu_item_components_scope
BEFORE INSERT OR UPDATE OF menu_item_id, component_id ON menu_item_components
FOR EACH ROW
EXECUTE FUNCTION validate_menu_item_component_scope();

CREATE OR REPLACE FUNCTION protect_menu_component_identity()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = cafeteria, pg_temp
AS $protect_menu_component_identity$
BEGIN
    IF NEW.location_id IS DISTINCT FROM OLD.location_id THEN
        RAISE EXCEPTION 'Die Komponenten-Location ist unveraenderlich.'
            USING ERRCODE='23514',
                  CONSTRAINT='menu_components_location_identity';
    END IF;
    IF NEW.profile_scope IS DISTINCT FROM OLD.profile_scope THEN
        RAISE EXCEPTION 'Der Komponenten-Profil-Scope ist unveraenderlich.'
            USING ERRCODE='23514',
                  CONSTRAINT='menu_components_profile_scope_identity';
    END IF;
    RETURN NEW;
END;
$protect_menu_component_identity$;

CREATE OR REPLACE FUNCTION protect_menu_week_location_identity()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = cafeteria, pg_temp
AS $protect_menu_week_location_identity$
BEGIN
    IF NEW.location_id IS DISTINCT FROM OLD.location_id THEN
        RAISE EXCEPTION 'Die Wochen-Location ist unveraenderlich.'
            USING ERRCODE='23514',
                  CONSTRAINT='menu_weeks_location_identity';
    END IF;
    RETURN NEW;
END;
$protect_menu_week_location_identity$;

DROP TRIGGER IF EXISTS trg_menu_components_identity ON menu_components;
CREATE TRIGGER trg_menu_components_identity
BEFORE UPDATE OF location_id, profile_scope ON menu_components
FOR EACH ROW
EXECUTE FUNCTION protect_menu_component_identity();

DROP TRIGGER IF EXISTS trg_menu_weeks_location_identity ON menu_weeks;
CREATE TRIGGER trg_menu_weeks_location_identity
BEFORE UPDATE OF location_id ON menu_weeks
FOR EACH ROW
EXECUTE FUNCTION protect_menu_week_location_identity();

COMMIT;
