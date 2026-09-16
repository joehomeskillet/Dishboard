-- Rollback: Die v34-Anwendung kennt kitchen_events nicht und liest oder schreibt sie nie;
-- ein App-Rollback verliert keine Menüdaten. Anlässe bleiben erhalten, sind für die
-- v34-App aber unsichtbar.
-- App-Rollback mit dem Repo-Compose nicht per `docker compose up`: `app` hängt dort über
-- `service_completed_successfully` an `migrate`, und `migrate` führt `init-db` mit v34-Code aus,
-- der an der unbekannten Schema-Migrationsversion 35 abbricht; die App startet dann nicht.
-- Die alte App deshalb ohne Abhängigkeitsstart hochfahren:
-- `APP_IMAGE=<v34-Digest> docker compose up -d --wait --no-deps app`.
-- Solange v34-Code aktiv ist, kein `docker compose up` ohne `--no-deps` und kein `init-db` oder
-- `run_migrations` mit v34-Code gegen eine v35-Datenbank.
-- Ein Schema-Rollback auf v34 ist ausschliesslich per geprüftem Restore erlaubt.
-- Deploy: Backup abgeschlossen, keine langen Transaktionen (pg_stat_activity), App im
-- Wartungsmodus oder kurzes Fenster.
-- Lock: `SET LOCAL lock_timeout = '5s'` unten lässt die Migration bei einer Lock-Warteschlange
-- (z. B. laufendes Backup) mit SQLSTATE 55P03 abbrechen; lange Transaktionen abwarten und die
-- Migration danach erneut starten.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

-- R3 Anlass-Kopf ohne Bausteine. Gästezahl skaliert nichts. Kein Einfluss auf menu_weeks.
CREATE TABLE kitchen_events (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    event_date date NOT NULL,
    starts_at time,
    ends_at time,
    profile_scope text NOT NULL,
    title text NOT NULL,
    guest_count integer NOT NULL DEFAULT 0,
    note text,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    archived_at timestamptz,
    CONSTRAINT kitchen_events_pkey PRIMARY KEY (id),
    CONSTRAINT kitchen_events_public_id_key UNIQUE (public_id),
    CONSTRAINT kitchen_events_location_id_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT kitchen_events_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT kitchen_events_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT kitchen_events_profile_scope_check CHECK (profile_scope IN ('patient', 'staff_guest', 'both')),
    CONSTRAINT kitchen_events_title_check CHECK (title = btrim(title, E' \t\r\n') AND length(title) BETWEEN 1 AND 120),
    CONSTRAINT kitchen_events_note_check CHECK (note IS NULL OR (note = btrim(note, E' \t\r\n') AND length(note) <= 2000)),
    CONSTRAINT kitchen_events_guest_count_check CHECK (guest_count >= 0),
    CONSTRAINT kitchen_events_row_version_check CHECK (row_version > 0),
    CONSTRAINT kitchen_events_time_window_check CHECK (starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at)
);

CREATE INDEX kitchen_events_location_date_idx
    ON kitchen_events(location_id, event_date)
    WHERE archived_at IS NULL;

CREATE TRIGGER trg_kitchen_events_version BEFORE UPDATE ON kitchen_events
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE FUNCTION kitchen_event_scope_protect_v35() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF NEW.location_id IS DISTINCT FROM OLD.location_id THEN
        RAISE EXCEPTION 'Der Standort eines Anlasses ist unveränderlich.' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END;$fn$;
CREATE TRIGGER kitchen_events_scope_protect BEFORE UPDATE ON kitchen_events
    FOR EACH ROW EXECUTE FUNCTION kitchen_event_scope_protect_v35();

REVOKE ALL ON FUNCTION kitchen_event_scope_protect_v35()
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

GRANT SELECT, INSERT, UPDATE, DELETE ON kitchen_events TO cafeteria_app;
GRANT SELECT ON kitchen_events TO cafeteria_backup;
GRANT SELECT ON SEQUENCE kitchen_events_id_seq TO cafeteria_backup;

COMMIT;
