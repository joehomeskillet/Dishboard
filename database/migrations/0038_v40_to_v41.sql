-- Rollback: v40-App kennt calculation_receipts nicht.
-- App-Rollback: `APP_IMAGE=<v40-Digest> docker compose up -d --wait --no-deps app`.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

CREATE TABLE calculation_receipts (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    kind text NOT NULL,
    subject_public_id uuid NOT NULL,
    payload jsonb NOT NULL,
    content_hash_sha256 text NOT NULL,
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT calculation_receipts_pkey PRIMARY KEY (id),
    CONSTRAINT calculation_receipts_public_id_key UNIQUE (public_id),
    CONSTRAINT calculation_receipts_location_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT calculation_receipts_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT calculation_receipts_kind_check CHECK (kind IN ('recipe','prepared','menu','shopping')),
    CONSTRAINT calculation_receipts_hash_check CHECK (content_hash_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE FUNCTION calculation_receipt_protect_v41() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    RAISE EXCEPTION 'Kalkulationsbelege sind unveränderlich.' USING ERRCODE='55000';
END;$fn$;
CREATE TRIGGER calculation_receipts_immutable
    BEFORE UPDATE OR DELETE ON calculation_receipts
    FOR EACH ROW EXECUTE FUNCTION calculation_receipt_protect_v41();

GRANT SELECT, INSERT ON calculation_receipts TO cafeteria_app;
REVOKE UPDATE, DELETE ON calculation_receipts FROM cafeteria_app;
GRANT SELECT ON calculation_receipts TO cafeteria_backup;
GRANT SELECT ON SEQUENCE calculation_receipts_id_seq TO cafeteria_backup;
REVOKE ALL ON FUNCTION calculation_receipt_protect_v41() FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

COMMIT;
