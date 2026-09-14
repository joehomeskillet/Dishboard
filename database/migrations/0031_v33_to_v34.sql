-- Rollback: Die v33-Anwendung kennt cafeteria.shopping_lists/-revisions/-manual_items/
-- -line_status nicht; ein Ruckfall auf v33-Code lauft unverandert weiter und verliert keine
-- bestehenden Menuedaten. Einkaufslisten bleiben fur die v33-App unsichtbar (kein Menue-,
-- Publikations- oder Snapshot-Schreibpfad beruhrt diese Tabellen). Ein Schema-Rollback auf v33
-- ist ausschliesslich per gepruftem Restore erlaubt; kein `init-db` oder `run_migrations` mit
-- v33-Code gegen eine v34-Datenbank (kennt Schema-Migrationsversion 34 nicht und bricht ab).
-- Deploy: Backup abgeschlossen, keine langen Transaktionen (pg_stat_activity), App im
-- Wartungsmodus oder kurzes Fenster.
-- Lock: `SET LOCAL lock_timeout = '5s'` unten laesst die Migration bei einer Lock-Warteschlange
-- (z. B. laufendes Backup) mit SQLSTATE 55P03 abbrechen; lange Transaktionen abwarten und die
-- Migration danach erneut starten.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

CREATE TABLE shopping_lists (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    location_id bigint NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
    menu_week_id bigint REFERENCES menu_weeks(id) ON DELETE RESTRICT,
    title text NOT NULL CHECK (btrim(title) <> '' AND length(title) <= 120),
    note text CHECK (note IS NULL OR length(note) <= 2000),
    row_version bigint NOT NULL DEFAULT 1 CHECK (row_version > 0),
    created_by bigint NOT NULL REFERENCES users(id),
    updated_by bigint NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    archived_at timestamptz
);

-- Berechnungsrevisionen sind append-only (Muster recipe_revisions): Quellrevision+Hash,
-- Zielausbeute, Bedarfspolitik, Childpins und erfasste Unit-/Faktorwerte sind Teil des
-- gespeicherten snapshot_json ({"inputs": [...], "result": {...}}); niemals live neu
-- berechnet.
CREATE TABLE shopping_list_revisions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    shopping_list_id bigint NOT NULL REFERENCES shopping_lists(id) ON DELETE RESTRICT,
    revision_number integer NOT NULL CHECK (revision_number > 0),
    policy text NOT NULL CHECK (policy IN ('leaf', 'prepared')),
    snapshot_json jsonb NOT NULL CHECK (jsonb_typeof(snapshot_json) = 'object'),
    content_hash_sha256 text NOT NULL,
    CONSTRAINT shopping_list_revisions_content_hash_sha256_check CHECK (
        content_hash_sha256 = encode(public.digest(convert_to(snapshot_json::text, 'UTF8'), 'sha256'), 'hex')
    ),
    computed_by bigint NOT NULL REFERENCES users(id),
    computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (shopping_list_id, revision_number)
);

CREATE TABLE shopping_list_manual_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    shopping_list_id bigint NOT NULL REFERENCES shopping_lists(id) ON DELETE RESTRICT,
    sort_order integer NOT NULL CHECK (sort_order > 0),
    item_text text NOT NULL CHECK (btrim(item_text) <> '' AND length(item_text) <= 200),
    quantity numeric(18,6) CHECK (quantity IS NULL OR quantity > 0),
    unit_id bigint REFERENCES measurement_units(id) ON DELETE RESTRICT,
    checked boolean NOT NULL DEFAULT false,
    row_version bigint NOT NULL DEFAULT 1 CHECK (row_version > 0),
    created_by bigint NOT NULL REFERENCES users(id),
    updated_by bigint NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((quantity IS NULL) = (unit_id IS NULL)),
    UNIQUE (shopping_list_id, sort_order)
);

-- Abhakstatus je stabiler Aggregatzeile (Food-Identitaet + Einheiten-/Faktorprovenienz),
-- von der Store-Schicht berechnet; kein eigener row_version-Vertrag, App ueberschreibt per
-- INSERT ... ON CONFLICT (shopping_list_id, line_key) DO UPDATE.
CREATE TABLE shopping_list_line_status (
    shopping_list_id bigint NOT NULL REFERENCES shopping_lists(id) ON DELETE RESTRICT,
    line_key text NOT NULL CHECK (btrim(line_key) <> '' AND length(line_key) <= 300),
    revision_id bigint NOT NULL REFERENCES shopping_list_revisions(id) ON DELETE RESTRICT,
    checked_quantity text NOT NULL CHECK (btrim(checked_quantity) <> '' AND length(checked_quantity) <= 100),
    checked_by bigint NOT NULL REFERENCES users(id),
    checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (shopping_list_id, line_key)
);

-- Bindungsmuster schema26/schema33, RESTRICT-Pruefung beim Loeschen einer Einheit
CREATE INDEX shopping_list_manual_items_unit_id_idx
    ON shopping_list_manual_items(unit_id)
    WHERE unit_id IS NOT NULL;

CREATE TRIGGER trg_shopping_lists_version BEFORE UPDATE ON shopping_lists
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();
CREATE TRIGGER trg_shopping_list_manual_items_version BEFORE UPDATE ON shopping_list_manual_items
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE FUNCTION shopping_list_revision_protect_v34() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    RAISE EXCEPTION 'Einkaufslisten-Berechnungsrevisionen sind unveraenderlich.' USING ERRCODE='55000';
END;$fn$;
CREATE TRIGGER shopping_list_revisions_immutable BEFORE UPDATE OR DELETE ON shopping_list_revisions
    FOR EACH ROW EXECUTE FUNCTION shopping_list_revision_protect_v34();
CREATE TRIGGER shopping_list_revisions_no_truncate BEFORE TRUNCATE ON shopping_list_revisions
    FOR EACH STATEMENT EXECUTE FUNCTION shopping_list_revision_protect_v34();

-- Postgres grantet neuen Funktionen sonst EXECUTE an PUBLIC per Default; die
-- Trigger-Funktion wird nie direkt aufgerufen (nur implizit ueber die Trigger oben).
REVOKE ALL ON FUNCTION shopping_list_revision_protect_v34()
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;

-- ACL: reine Tabellenrechte, keine SECURITY-DEFINER-Funktion. Listen/manuelle Zeilen/Status
-- sind app-seitig CAS-gefuehrt (row_version bzw. Upsert); Revisionen sind append-only
-- (SELECT/INSERT, kein UPDATE/DELETE, zusaetzlich durch den Immutability-Trigger erzwungen).
GRANT SELECT, INSERT, UPDATE, DELETE ON
    shopping_lists, shopping_list_manual_items, shopping_list_line_status
TO cafeteria_app;
GRANT SELECT, INSERT ON shopping_list_revisions TO cafeteria_app;
GRANT SELECT ON
    shopping_lists, shopping_list_revisions, shopping_list_manual_items, shopping_list_line_status
TO cafeteria_backup;
GRANT SELECT ON SEQUENCE
    shopping_lists_id_seq, shopping_list_revisions_id_seq, shopping_list_manual_items_id_seq
TO cafeteria_backup;

COMMIT;
