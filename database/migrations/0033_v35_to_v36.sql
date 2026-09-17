-- Rollback: Die v35-Anwendung kennt food_price_heads und food_purchase_price_revisions nicht
-- und liest oder schreibt sie nie; ein App-Rollback verliert keine Menüdaten. Preisbelege
-- bleiben erhalten, sind für die v35-App aber unsichtbar.
-- App-Rollback: `APP_IMAGE=<v35-Digest> docker compose up -d --wait --no-deps app`.
-- Schema-Rollback auf v35 ausschliesslich per geprüftem Restore.
-- Deploy: Backup abgeschlossen, keine langen Transaktionen, kurzes Fenster.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

CREATE TABLE food_price_heads (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    food_id bigint NOT NULL,
    current_revision_id bigint,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT food_price_heads_pkey PRIMARY KEY (id),
    CONSTRAINT food_price_heads_public_id_key UNIQUE (public_id),
    CONSTRAINT food_price_heads_location_food_key UNIQUE (location_id, food_id),
    CONSTRAINT food_price_heads_id_location_key UNIQUE (id, location_id),
    CONSTRAINT food_price_heads_location_id_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT food_price_heads_food_fkey FOREIGN KEY (location_id, food_id) REFERENCES foods(location_id, id) ON DELETE RESTRICT,
    CONSTRAINT food_price_heads_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT food_price_heads_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT food_price_heads_row_version_check CHECK (row_version > 0)
);

CREATE TABLE food_purchase_price_revisions (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    head_id bigint NOT NULL,
    location_id bigint NOT NULL,
    food_id bigint NOT NULL,
    revision_number integer NOT NULL,
    edition_json jsonb NOT NULL,
    content_hash_sha256 text NOT NULL,
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT food_purchase_price_revisions_pkey PRIMARY KEY (id),
    CONSTRAINT food_purchase_price_revisions_public_id_key UNIQUE (public_id),
    CONSTRAINT food_purchase_price_revisions_head_number_key UNIQUE (head_id, revision_number),
    CONSTRAINT food_purchase_price_revisions_id_head_key UNIQUE (id, head_id),
    CONSTRAINT food_purchase_price_revisions_head_fkey FOREIGN KEY (head_id) REFERENCES food_price_heads(id) ON DELETE RESTRICT,
    CONSTRAINT food_purchase_price_revisions_food_fkey FOREIGN KEY (location_id, food_id) REFERENCES foods(location_id, id) ON DELETE RESTRICT,
    CONSTRAINT food_purchase_price_revisions_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT food_purchase_price_revisions_revision_number_check CHECK (revision_number > 0),
    CONSTRAINT food_purchase_price_revisions_hash_check CHECK (content_hash_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT food_purchase_price_revisions_edition_check CHECK (jsonb_typeof(edition_json) = 'object' AND edition_json ? 'intervals' AND jsonb_typeof(edition_json -> 'intervals') = 'array')
);

ALTER TABLE food_price_heads
    ADD CONSTRAINT food_price_heads_current_revision_fkey
    FOREIGN KEY (current_revision_id, id) REFERENCES food_purchase_price_revisions(id, head_id) ON DELETE RESTRICT;

CREATE INDEX food_price_heads_food_id_idx ON food_price_heads(food_id);
CREATE INDEX food_purchase_price_revisions_head_id_idx ON food_purchase_price_revisions(head_id);

CREATE TRIGGER trg_food_price_heads_version BEFORE UPDATE ON food_price_heads
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE FUNCTION food_price_head_scope_protect_v36() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF NEW.location_id IS DISTINCT FROM OLD.location_id OR NEW.food_id IS DISTINCT FROM OLD.food_id THEN
        RAISE EXCEPTION 'Standort und Zutat eines Preisheads sind unveränderlich.' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END;$fn$;
CREATE TRIGGER food_price_heads_scope_protect BEFORE UPDATE ON food_price_heads
    FOR EACH ROW EXECUTE FUNCTION food_price_head_scope_protect_v36();

CREATE FUNCTION food_purchase_price_revision_protect_v36() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    RAISE EXCEPTION 'Einkaufspreisrevisionen sind unveränderlich.' USING ERRCODE='55000';
END;$fn$;
CREATE TRIGGER food_purchase_price_revisions_immutable
    BEFORE UPDATE OR DELETE ON food_purchase_price_revisions
    FOR EACH ROW EXECUTE FUNCTION food_purchase_price_revision_protect_v36();
CREATE TRIGGER food_purchase_price_revisions_no_truncate
    BEFORE TRUNCATE ON food_purchase_price_revisions
    FOR EACH STATEMENT EXECUTE FUNCTION food_purchase_price_revision_protect_v36();

CREATE FUNCTION food_price_edition_build_v36(p_location bigint, p_intervals jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE
    item jsonb;
    built jsonb := '[]'::jsonb;
    entry jsonb;
    v_from date;
    v_to date;
    v_price numeric;
    v_yield numeric;
    v_code text;
    v_unit measurement_units%ROWTYPE;
    ranges daterange[] := ARRAY[]::daterange[];
    r daterange;
    existing daterange;
BEGIN
    IF p_intervals IS NULL OR jsonb_typeof(p_intervals) <> 'array' OR jsonb_array_length(p_intervals) < 1 THEN
        RAISE EXCEPTION 'Mindestens ein Preisintervall.' USING ERRCODE='P1901';
    END IF;
    FOR item IN SELECT value FROM jsonb_array_elements(p_intervals)
    LOOP
        IF jsonb_typeof(item) <> 'object' THEN
            RAISE EXCEPTION 'Ungültiges Intervall.' USING ERRCODE='P1901';
        END IF;
        IF EXISTS (
            SELECT 1 FROM jsonb_object_keys(item) k
            WHERE k NOT IN ('valid_from', 'valid_to', 'unit_price', 'unit_code', 'yield_factor')
        ) THEN
            RAISE EXCEPTION 'Ungültige Intervallfelder.' USING ERRCODE='P1901';
        END IF;
        BEGIN
            v_from := (item ->> 'valid_from')::date;
        EXCEPTION WHEN others THEN
            RAISE EXCEPTION 'Ungültiges Gültig-ab.' USING ERRCODE='P1901';
        END;
        IF item ->> 'valid_to' IS NULL OR item ->> 'valid_to' = '' THEN
            v_to := NULL;
        ELSE
            BEGIN
                v_to := (item ->> 'valid_to')::date;
            EXCEPTION WHEN others THEN
                RAISE EXCEPTION 'Ungültiges Gültig-bis.' USING ERRCODE='P1901';
            END;
        END IF;
        IF v_to IS NOT NULL AND v_to <= v_from THEN
            RAISE EXCEPTION 'Gültig-bis muss nach Gültig-ab liegen.' USING ERRCODE='P1901';
        END IF;
        BEGIN
            v_price := (item ->> 'unit_price')::numeric;
        EXCEPTION WHEN others THEN
            RAISE EXCEPTION 'Ungültiger Preis.' USING ERRCODE='P1901';
        END;
        IF NOT master_quantity(v_price) THEN
            RAISE EXCEPTION 'Ungültiger Preis.' USING ERRCODE='P1901';
        END IF;
        IF item ->> 'yield_factor' IS NULL OR item ->> 'yield_factor' = '' THEN
            v_yield := NULL;
        ELSE
            BEGIN
                v_yield := (item ->> 'yield_factor')::numeric;
            EXCEPTION WHEN others THEN
                RAISE EXCEPTION 'Ungültiger Ausbeutefaktor.' USING ERRCODE='P1901';
            END;
            IF NOT master_factor(v_yield) OR v_yield > 1 THEN
                RAISE EXCEPTION 'Ungültiger Ausbeutefaktor.' USING ERRCODE='P1901';
            END IF;
        END IF;
        v_code := item ->> 'unit_code';
        SELECT * INTO v_unit FROM measurement_units WHERE code = v_code;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Unbekannte Einheit.' USING ERRCODE='P1901';
        END IF;
        r := daterange(v_from, v_to, '[)');
        FOREACH existing IN ARRAY ranges LOOP
            IF existing && r THEN
                RAISE EXCEPTION 'Preisintervalle überlappen.' USING ERRCODE='P1901';
            END IF;
        END LOOP;
        ranges := ranges || r;
        entry := jsonb_build_object(
            'entry_id', gen_random_uuid(),
            'valid_from', v_from,
            'valid_to', to_jsonb(v_to),
            'unit_price', v_price,
            'currency', 'CHF',
            'yield_factor', to_jsonb(v_yield),
            'unit', jsonb_build_object(
                'public_id', v_unit.public_id,
                'code', v_unit.code,
                'dimension', v_unit.dimension,
                'base_factor', to_jsonb(v_unit.base_factor)
            )
        );
        built := built || jsonb_build_array(entry);
    END LOOP;
    RETURN jsonb_build_object('intervals', built);
END;$fn$;

CREATE FUNCTION append_food_price_revision_v36(
    p_actor bigint, p_actor_version bigint, p_location bigint,
    p_food uuid, p_head_version bigint, p_payload jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE
    v_food foods%ROWTYPE;
    v_head food_price_heads%ROWTYPE;
    v_current food_purchase_price_revisions%ROWTYPE;
    v_edition jsonb;
    v_hash text;
    v_rev food_purchase_price_revisions%ROWTYPE;
    v_next integer;
    old_version bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor, p_actor_version, 'masterdata.write');
    PERFORM master_location(p_location);
    PERFORM master_payload(p_payload, ARRAY['intervals']);
    SELECT * INTO v_food FROM foods WHERE public_id = p_food AND location_id = p_location FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023';
    END IF;
    SELECT * INTO v_head FROM food_price_heads
        WHERE location_id = p_location AND food_id = v_food.id FOR UPDATE;
    IF NOT FOUND THEN
        IF p_head_version IS NOT NULL THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000', DETAIL='stale_object';
        END IF;
        INSERT INTO food_price_heads(location_id, food_id, created_by, updated_by)
        VALUES (p_location, v_food.id, p_actor, p_actor)
        RETURNING * INTO v_head;
    ELSIF p_head_version IS NULL OR v_head.row_version <> p_head_version THEN
        RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000', DETAIL='stale_object';
    END IF;
    v_edition := food_price_edition_build_v36(p_location, p_payload -> 'intervals');
    v_hash := encode(pg_catalog.sha256(convert_to(v_edition::text, 'UTF8')), 'hex');
    IF v_head.current_revision_id IS NOT NULL THEN
        SELECT * INTO v_current FROM food_purchase_price_revisions WHERE id = v_head.current_revision_id;
        IF v_current.content_hash_sha256 = v_hash THEN
            RETURN jsonb_build_object(
                'public_id', v_head.public_id, 'row_version', v_head.row_version,
                'revision_public_id', v_current.public_id, 'noop', true
            );
        END IF;
        v_next := v_current.revision_number + 1;
    ELSE
        v_next := 1;
    END IF;
    old_version := v_head.row_version;
    INSERT INTO food_purchase_price_revisions(
        head_id, location_id, food_id, revision_number, edition_json, content_hash_sha256, created_by)
    VALUES (v_head.id, p_location, v_food.id, v_next, v_edition, v_hash, p_actor)
    RETURNING * INTO v_rev;
    UPDATE food_price_heads
        SET current_revision_id = v_rev.id, updated_by = p_actor
        WHERE id = v_head.id
        RETURNING * INTO v_head;
    PERFORM master_audit(p_actor, p_actor_version, p_location, 'food_price', v_head.public_id, 'append_revision',
        old_version, v_head.row_version,
        jsonb_build_object('revision_public_id', v_rev.public_id, 'food_public_id', v_food.public_id));
    RETURN jsonb_build_object(
        'public_id', v_head.public_id, 'row_version', v_head.row_version,
        'revision_public_id', v_rev.public_id, 'noop', false
    );
END;$fn$;

REVOKE ALL ON FUNCTION food_price_head_scope_protect_v36(), food_purchase_price_revision_protect_v36(),
    food_price_edition_build_v36(bigint, jsonb)
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE ALL ON FUNCTION append_food_price_revision_v36(bigint, bigint, bigint, uuid, bigint, jsonb)
FROM PUBLIC, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION append_food_price_revision_v36(bigint, bigint, bigint, uuid, bigint, jsonb)
TO cafeteria_app;
GRANT SELECT ON food_price_heads, food_purchase_price_revisions TO cafeteria_app;
GRANT SELECT ON food_price_heads, food_purchase_price_revisions TO cafeteria_backup;
GRANT SELECT ON SEQUENCE food_price_heads_id_seq, food_purchase_price_revisions_id_seq TO cafeteria_backup;

COMMIT;
