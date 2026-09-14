-- Rollback: Die v32-Anwendung bleibt wegen nullable Spalten technisch startbar, aber:
-- a) v32-Writer verwerfen Zielmengen beim Speichern und Kopieren still.
-- b) Vor App-Rollback Zielmengen sichern oder Verlust ausdrücklich akzeptieren, sonst Forward-Fix.
-- c) Kein `init-db` oder `run_migrations` mit v32-Code gegen eine v33-DB.
-- Ein Schema-Rollback auf v32 ist ausschliesslich per geprüftem Restore erlaubt.
-- Deploy: Backup abgeschlossen, keine langen Transaktionen (pg_stat_activity), App im Wartungsmodus oder kurzes Fenster.
BEGIN;
SET LOCAL lock_timeout = '5s';

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

-- Bindungsmuster schema26, RESTRICT-Prüfung beim Löschen einer Einheit
CREATE INDEX menu_item_components_target_quantity_unit_idx
    ON cafeteria.menu_item_components(target_quantity_unit_id)
    WHERE target_quantity_unit_id IS NOT NULL;

COMMIT;
