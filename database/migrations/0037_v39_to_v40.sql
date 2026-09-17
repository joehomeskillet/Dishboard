-- Rollback: v39-App kennt prepared_batch_runs nicht.
-- App-Rollback: `APP_IMAGE=<v39-Digest> docker compose up -d --wait --no-deps app`.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

CREATE TABLE prepared_batch_runs (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    recipe_revision_id bigint NOT NULL,
    output_food_id bigint NOT NULL,
    output_storage_id bigint NOT NULL,
    output_quantity numeric(18,6) NOT NULL,
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT prepared_batch_runs_pkey PRIMARY KEY (id),
    CONSTRAINT prepared_batch_runs_public_id_key UNIQUE (public_id),
    CONSTRAINT prepared_batch_runs_location_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT prepared_batch_runs_revision_fkey FOREIGN KEY (recipe_revision_id) REFERENCES recipe_revisions(id) ON DELETE RESTRICT,
    CONSTRAINT prepared_batch_runs_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT prepared_batch_runs_qty_check CHECK (output_quantity > 0)
);

GRANT SELECT, INSERT ON prepared_batch_runs TO cafeteria_app;
GRANT SELECT ON prepared_batch_runs TO cafeteria_backup;
GRANT SELECT ON SEQUENCE prepared_batch_runs_id_seq TO cafeteria_backup;

COMMIT;
