-- Rollback: Die v32-Anwendung bleibt wegen nullable Spalten kompatibel.
-- Ein Schema-Rollback auf v32 ist ausschliesslich per geprüftem Restore erlaubt.
BEGIN;

ALTER TABLE cafeteria.menu_item_components
    ADD COLUMN target_quantity numeric(18,6),
    ADD COLUMN target_quantity_unit_id bigint
        REFERENCES cafeteria.measurement_units(id) ON DELETE RESTRICT,
    ADD CONSTRAINT menu_item_components_target_quantity_check CHECK (
        (target_quantity IS NULL AND target_quantity_unit_id IS NULL)
        OR (
            target_quantity IS NOT NULL
            AND target_quantity_unit_id IS NOT NULL
            AND target_quantity > 0
            AND recipe_revision_id IS NOT NULL
        )
    );

CREATE INDEX menu_item_components_target_quantity_unit_idx
    ON cafeteria.menu_item_components(target_quantity_unit_id)
    WHERE target_quantity_unit_id IS NOT NULL;

COMMIT;
