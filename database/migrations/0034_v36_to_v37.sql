-- Rollback: Die v36-Anwendung kennt kitchen_event_demand_items nicht.
-- App-Rollback: `APP_IMAGE=<v36-Digest> docker compose up -d --wait --no-deps app`.
-- Schema-Rollback auf v36 nur per Restore.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

CREATE TABLE kitchen_event_demand_items (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    event_id bigint NOT NULL,
    sort_order integer NOT NULL,
    recipe_revision_id bigint NOT NULL,
    recipe_content_hash_sha256 text NOT NULL,
    target_quantity numeric(18,6) NOT NULL,
    target_quantity_unit_id bigint NOT NULL,
    component_text text NOT NULL,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT kitchen_event_demand_items_pkey PRIMARY KEY (id),
    CONSTRAINT kitchen_event_demand_items_public_id_key UNIQUE (public_id),
    CONSTRAINT kitchen_event_demand_items_event_sort_key UNIQUE (event_id, sort_order),
    CONSTRAINT kitchen_event_demand_items_event_fkey FOREIGN KEY (event_id) REFERENCES kitchen_events(id) ON DELETE RESTRICT,
    CONSTRAINT kitchen_event_demand_items_revision_fkey FOREIGN KEY (recipe_revision_id) REFERENCES recipe_revisions(id) ON DELETE RESTRICT,
    CONSTRAINT kitchen_event_demand_items_unit_fkey FOREIGN KEY (target_quantity_unit_id) REFERENCES measurement_units(id) ON DELETE RESTRICT,
    CONSTRAINT kitchen_event_demand_items_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT kitchen_event_demand_items_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT kitchen_event_demand_items_sort_check CHECK (sort_order > 0),
    CONSTRAINT kitchen_event_demand_items_hash_check CHECK (recipe_content_hash_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT kitchen_event_demand_items_quantity_check CHECK (target_quantity > 0),
    CONSTRAINT kitchen_event_demand_items_text_check CHECK (component_text = btrim(component_text, E' \t\r\n') AND length(component_text) BETWEEN 1 AND 200),
    CONSTRAINT kitchen_event_demand_items_row_version_check CHECK (row_version > 0)
);

CREATE INDEX kitchen_event_demand_items_event_id_idx ON kitchen_event_demand_items(event_id);

CREATE TRIGGER trg_kitchen_event_demand_items_version BEFORE UPDATE ON kitchen_event_demand_items
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

GRANT SELECT, INSERT, UPDATE, DELETE ON kitchen_event_demand_items TO cafeteria_app;
GRANT SELECT ON kitchen_event_demand_items TO cafeteria_backup;
GRANT SELECT ON SEQUENCE kitchen_event_demand_items_id_seq TO cafeteria_backup;

COMMIT;
