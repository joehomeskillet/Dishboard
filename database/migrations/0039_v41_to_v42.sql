-- Rollback: v41-App kennt Beleg-Unique und raw_quantity nicht.
-- App-Rollback: `APP_IMAGE=<v41-Digest> docker compose up -d --wait --no-deps app`.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

ALTER TABLE order_basket_lines
    ADD COLUMN raw_quantity numeric(18,6);
ALTER TABLE order_basket_lines
    ADD CONSTRAINT order_basket_lines_raw_qty_check CHECK (raw_quantity IS NULL OR raw_quantity >= 0);

ALTER TABLE calculation_receipts
    ADD CONSTRAINT calculation_receipts_subject_key UNIQUE (location_id, kind, subject_public_id);

COMMIT;
