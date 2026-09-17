-- Rollback: Die v38-Anwendung kennt inventory_* nicht.
-- App-Rollback: `APP_IMAGE=<v38-Digest> docker compose up -d --wait --no-deps app`.
-- Schema-Rollback auf v38 nur per Restore.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

CREATE TABLE inventory_accounts (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    food_id bigint NOT NULL,
    storage_location_id bigint NOT NULL,
    base_unit_id bigint NOT NULL,
    base_unit_snapshot jsonb NOT NULL,
    food_factors_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT inventory_accounts_pkey PRIMARY KEY (id),
    CONSTRAINT inventory_accounts_public_id_key UNIQUE (public_id),
    CONSTRAINT inventory_accounts_slot_key UNIQUE (location_id, food_id, storage_location_id),
    CONSTRAINT inventory_accounts_food_fkey FOREIGN KEY (location_id, food_id) REFERENCES foods(location_id, id) ON DELETE RESTRICT,
    CONSTRAINT inventory_accounts_storage_fkey FOREIGN KEY (location_id, storage_location_id) REFERENCES storage_locations(location_id, id) ON DELETE RESTRICT,
    CONSTRAINT inventory_accounts_unit_fkey FOREIGN KEY (base_unit_id) REFERENCES measurement_units(id) ON DELETE RESTRICT
);

CREATE TABLE inventory_movements (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    account_id bigint NOT NULL,
    kind text NOT NULL,
    quantity numeric(18,6) NOT NULL,
    sign smallint NOT NULL,
    unit_id bigint NOT NULL,
    unit_snapshot jsonb NOT NULL,
    normalized_base_quantity numeric(18,6) NOT NULL,
    note text,
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT inventory_movements_pkey PRIMARY KEY (id),
    CONSTRAINT inventory_movements_public_id_key UNIQUE (public_id),
    CONSTRAINT inventory_movements_account_fkey FOREIGN KEY (account_id) REFERENCES inventory_accounts(id) ON DELETE RESTRICT,
    CONSTRAINT inventory_movements_unit_fkey FOREIGN KEY (unit_id) REFERENCES measurement_units(id) ON DELETE RESTRICT,
    CONSTRAINT inventory_movements_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT inventory_movements_kind_check CHECK (kind IN ('receipt','issue','transfer_out','transfer_in','count_adjust','correction')),
    CONSTRAINT inventory_movements_quantity_check CHECK (quantity > 0),
    CONSTRAINT inventory_movements_sign_check CHECK (sign IN (-1, 1)),
    CONSTRAINT inventory_movements_kind_sign_check CHECK (
        (kind IN ('receipt','transfer_in') AND sign = 1) OR
        (kind IN ('issue','transfer_out') AND sign = -1) OR
        (kind IN ('count_adjust','correction'))
    ),
    CONSTRAINT inventory_movements_base_qty_check CHECK (normalized_base_quantity > 0)
);

CREATE INDEX inventory_movements_account_id_idx ON inventory_movements(account_id, created_at);

CREATE FUNCTION inventory_movement_protect_v39() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    RAISE EXCEPTION 'Bestandsbewegungen sind unveränderlich.' USING ERRCODE='55000';
END;$fn$;
CREATE TRIGGER inventory_movements_immutable
    BEFORE UPDATE OR DELETE ON inventory_movements
    FOR EACH ROW EXECUTE FUNCTION inventory_movement_protect_v39();
CREATE TRIGGER inventory_movements_no_truncate
    BEFORE TRUNCATE ON inventory_movements
    FOR EACH STATEMENT EXECUTE FUNCTION inventory_movement_protect_v39();

GRANT SELECT, INSERT, UPDATE ON inventory_accounts TO cafeteria_app;
GRANT SELECT, INSERT ON inventory_movements TO cafeteria_app;
REVOKE UPDATE, DELETE ON inventory_movements FROM cafeteria_app;
GRANT SELECT ON inventory_accounts, inventory_movements TO cafeteria_backup;
GRANT SELECT ON SEQUENCE inventory_accounts_id_seq, inventory_movements_id_seq TO cafeteria_backup;
REVOKE ALL ON FUNCTION inventory_movement_protect_v39() FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

COMMIT;
