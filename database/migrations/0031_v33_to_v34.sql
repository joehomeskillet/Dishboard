-- Rollback: Die v33-Anwendung kennt shopping_lists, shopping_list_revisions,
-- shopping_list_manual_items und shopping_list_line_status nicht und liest oder schreibt sie nie;
-- ein App-Rollback verliert keine Menüdaten. Einkaufslisten bleiben erhalten, sind für die
-- v33-App aber unsichtbar.
-- App-Rollback mit dem Repo-Compose nicht per `docker compose up`: `app` hängt dort über
-- `service_completed_successfully` an `migrate`, und `migrate` führt `init-db` mit v33-Code aus,
-- der an der unbekannten Schema-Migrationsversion 34 abbricht; die App startet dann nicht.
-- Die alte App deshalb ohne Abhängigkeitsstart hochfahren:
-- `APP_IMAGE=<v33-Digest> docker compose up -d --wait --no-deps app`.
-- Solange v33-Code aktiv ist, kein `docker compose up` ohne `--no-deps` und kein `init-db` oder
-- `run_migrations` mit v33-Code gegen eine v34-Datenbank.
-- Ein Schema-Rollback auf v33 ist ausschliesslich per geprüftem Restore erlaubt.
-- Deploy: Backup abgeschlossen, keine langen Transaktionen (pg_stat_activity), App im
-- Wartungsmodus oder kurzes Fenster.
-- Lock: `SET LOCAL lock_timeout = '5s'` unten lässt die Migration bei einer Lock-Warteschlange
-- (z. B. laufendes Backup) mit SQLSTATE 55P03 abbrechen; lange Transaktionen abwarten und die
-- Migration danach erneut starten.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

-- Texte sind in gespeicherter Normalform: an den Rändern ohne Leerzeichen, Tab, CR und LF.
CREATE TABLE shopping_lists (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    menu_week_id bigint,
    title text NOT NULL,
    note text,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    archived_at timestamptz,
    CONSTRAINT shopping_lists_pkey PRIMARY KEY (id),
    CONSTRAINT shopping_lists_public_id_key UNIQUE (public_id),
    CONSTRAINT shopping_lists_location_id_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_lists_menu_week_id_fkey FOREIGN KEY (menu_week_id) REFERENCES menu_weeks(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_lists_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_lists_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_lists_title_check CHECK (title = btrim(title, E' \t\r\n') AND length(title) BETWEEN 1 AND 120),
    CONSTRAINT shopping_lists_note_check CHECK (note IS NULL OR (note = btrim(note, E' \t\r\n') AND length(note) <= 2000)),
    CONSTRAINT shopping_lists_row_version_check CHECK (row_version > 0)
);

-- Berechnungsrevisionen sind append-only (Muster recipe_revisions): Quellrevision+Hash,
-- Zielausbeute, Bedarfspolitik, Childpins und erfasste Unit-/Faktorwerte sind Teil des
-- gespeicherten snapshot_json ({"inputs": [...], "result": {...}}); niemals live neu
-- berechnet. UNIQUE (id, shopping_list_id) trägt den Listen-Scope-FK des Abhakstatus.
CREATE TABLE shopping_list_revisions (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    shopping_list_id bigint NOT NULL,
    revision_number integer NOT NULL,
    policy text NOT NULL,
    snapshot_json jsonb NOT NULL,
    content_hash_sha256 text NOT NULL,
    computed_by bigint NOT NULL,
    computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT shopping_list_revisions_pkey PRIMARY KEY (id),
    CONSTRAINT shopping_list_revisions_public_id_key UNIQUE (public_id),
    CONSTRAINT shopping_list_revisions_id_shopping_list_id_key UNIQUE (id, shopping_list_id),
    CONSTRAINT shopping_list_revisions_shopping_list_id_revision_number_key UNIQUE (shopping_list_id, revision_number),
    CONSTRAINT shopping_list_revisions_shopping_list_id_fkey FOREIGN KEY (shopping_list_id) REFERENCES shopping_lists(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_list_revisions_computed_by_fkey FOREIGN KEY (computed_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_list_revisions_revision_number_check CHECK (revision_number > 0),
    CONSTRAINT shopping_list_revisions_policy_check CHECK (policy IN ('leaf', 'prepared')),
    CONSTRAINT shopping_list_revisions_snapshot_json_check CHECK (jsonb_typeof(snapshot_json) = 'object' AND snapshot_json ?& ARRAY['inputs', 'result'] AND jsonb_typeof(snapshot_json -> 'inputs') = 'array' AND jsonb_typeof(snapshot_json -> 'result') = 'object'),
    CONSTRAINT shopping_list_revisions_content_hash_sha256_check CHECK (content_hash_sha256 = encode(public.digest(convert_to(snapshot_json::text, 'UTF8'), 'sha256'), 'hex'))
);

CREATE TABLE shopping_list_manual_items (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    shopping_list_id bigint NOT NULL,
    sort_order integer NOT NULL,
    item_text text NOT NULL,
    quantity numeric(18,6),
    unit_id bigint,
    checked boolean NOT NULL DEFAULT false,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT shopping_list_manual_items_pkey PRIMARY KEY (id),
    CONSTRAINT shopping_list_manual_items_public_id_key UNIQUE (public_id),
    CONSTRAINT shopping_list_manual_items_shopping_list_id_sort_order_key UNIQUE (shopping_list_id, sort_order),
    CONSTRAINT shopping_list_manual_items_shopping_list_id_fkey FOREIGN KEY (shopping_list_id) REFERENCES shopping_lists(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_list_manual_items_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES measurement_units(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_list_manual_items_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_list_manual_items_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_list_manual_items_sort_order_check CHECK (sort_order > 0),
    CONSTRAINT shopping_list_manual_items_item_text_check CHECK (item_text = btrim(item_text, E' \t\r\n') AND length(item_text) BETWEEN 1 AND 200),
    CONSTRAINT shopping_list_manual_items_quantity_check CHECK (quantity IS NULL OR quantity > 0),
    CONSTRAINT shopping_list_manual_items_quantity_unit_check CHECK ((quantity IS NULL) = (unit_id IS NULL)),
    CONSTRAINT shopping_list_manual_items_row_version_check CHECK (row_version > 0)
);

-- Abhakstatus je stabiler Aggregatzeile (Food-Identität + Einheiten-/Faktorprovenienz),
-- von der Store-Schicht berechnet; kein eigener row_version-Vertrag, die App überschreibt per
-- INSERT ... ON CONFLICT (shopping_list_id, line_key) DO UPDATE. Der zusammengesetzte FK
-- erzwingt, dass die Revision zur selben Liste gehört (und damit, dass die Liste existiert).
CREATE TABLE shopping_list_line_status (
    shopping_list_id bigint NOT NULL,
    line_key text NOT NULL,
    revision_id bigint NOT NULL,
    checked_quantity text NOT NULL,
    checked_by bigint NOT NULL,
    checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT shopping_list_line_status_pkey PRIMARY KEY (shopping_list_id, line_key),
    CONSTRAINT shopping_list_line_status_revision_id_fkey FOREIGN KEY (revision_id, shopping_list_id) REFERENCES shopping_list_revisions(id, shopping_list_id) ON DELETE RESTRICT,
    CONSTRAINT shopping_list_line_status_checked_by_fkey FOREIGN KEY (checked_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT shopping_list_line_status_line_key_check CHECK (line_key = btrim(line_key, E' \t\r\n') AND length(line_key) BETWEEN 1 AND 300),
    CONSTRAINT shopping_list_line_status_checked_quantity_check CHECK (checked_quantity = btrim(checked_quantity, E' \t\r\n') AND length(checked_quantity) BETWEEN 1 AND 100)
);

-- Hauptzugriff «Listen eines Standorts» und RESTRICT-Prüfung beim Löschen eines Standorts.
CREATE INDEX shopping_lists_location_id_idx
    ON shopping_lists(location_id);
-- Bindungsmuster schema26/schema33, RESTRICT-Prüfung beim Löschen einer Woche bzw. Einheit.
CREATE INDEX shopping_lists_menu_week_id_idx
    ON shopping_lists(menu_week_id)
    WHERE menu_week_id IS NOT NULL;
CREATE INDEX shopping_list_manual_items_unit_id_idx
    ON shopping_list_manual_items(unit_id)
    WHERE unit_id IS NOT NULL;

CREATE TRIGGER trg_shopping_lists_version BEFORE UPDATE ON shopping_lists
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();
CREATE TRIGGER trg_shopping_list_manual_items_version BEFORE UPDATE ON shopping_list_manual_items
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

-- Standort-Scope ist unveränderlich (Muster recipe_protect_v22 «Immutable scope», ERRCODE 55000).
CREATE FUNCTION shopping_list_scope_protect_v34() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF NEW.location_id IS DISTINCT FROM OLD.location_id THEN
        RAISE EXCEPTION 'Der Standort einer Einkaufsliste ist unveränderlich.' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END;$fn$;
CREATE TRIGGER shopping_lists_scope_protect BEFORE UPDATE ON shopping_lists
    FOR EACH ROW EXECUTE FUNCTION shopping_list_scope_protect_v34();

CREATE FUNCTION shopping_list_revision_protect_v34() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    RAISE EXCEPTION 'Einkaufslisten-Berechnungsrevisionen sind unveränderlich.' USING ERRCODE='55000';
END;$fn$;
CREATE TRIGGER shopping_list_revisions_immutable BEFORE UPDATE OR DELETE ON shopping_list_revisions
    FOR EACH ROW EXECUTE FUNCTION shopping_list_revision_protect_v34();
CREATE TRIGGER shopping_list_revisions_no_truncate BEFORE TRUNCATE ON shopping_list_revisions
    FOR EACH STATEMENT EXECUTE FUNCTION shopping_list_revision_protect_v34();

-- Postgres grantet neuen Funktionen sonst EXECUTE an PUBLIC; die Trigger-Funktionen werden
-- nie direkt aufgerufen, nur implizit über die Trigger oben.
REVOKE ALL ON FUNCTION shopping_list_scope_protect_v34(), shopping_list_revision_protect_v34()
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

-- ACL: reine Tabellenrechte, keine SECURITY-DEFINER-Funktion. Listen/manuelle Zeilen/Status
-- sind app-seitig CAS-geführt (row_version bzw. Upsert); Revisionen sind append-only
-- (SELECT/INSERT, kein UPDATE/DELETE, zusätzlich durch den Immutability-Trigger erzwungen).
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
