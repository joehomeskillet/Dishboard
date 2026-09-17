-- Rollback: Die v37-Anwendung kennt suppliers/order_baskets nicht.
-- App-Rollback: `APP_IMAGE=<v37-Digest> docker compose up -d --wait --no-deps app`.
-- Schema-Rollback auf v37 nur per Restore.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET search_path TO cafeteria, public;

CREATE TABLE suppliers (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT suppliers_pkey PRIMARY KEY (id),
    CONSTRAINT suppliers_public_id_key UNIQUE (public_id),
    CONSTRAINT suppliers_location_id_key UNIQUE (location_id, id),
    CONSTRAINT suppliers_location_code_key UNIQUE (location_id, code),
    CONSTRAINT suppliers_location_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT suppliers_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT suppliers_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT suppliers_code_check CHECK (code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    CONSTRAINT suppliers_name_check CHECK (name = btrim(name, E' \t\r\n') AND length(name) BETWEEN 1 AND 120),
    CONSTRAINT suppliers_row_version_check CHECK (row_version > 0)
);

CREATE TABLE supplier_articles (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    supplier_id bigint NOT NULL,
    food_id bigint,
    article_code text NOT NULL,
    name text NOT NULL,
    order_unit_id bigint NOT NULL,
    pack_size numeric(18,6) NOT NULL DEFAULT 1,
    preferred boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true,
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT supplier_articles_pkey PRIMARY KEY (id),
    CONSTRAINT supplier_articles_public_id_key UNIQUE (public_id),
    CONSTRAINT supplier_articles_location_id_key UNIQUE (location_id, id),
    CONSTRAINT supplier_articles_supplier_code_key UNIQUE (supplier_id, article_code),
    CONSTRAINT supplier_articles_location_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT supplier_articles_supplier_fkey FOREIGN KEY (location_id, supplier_id) REFERENCES suppliers(location_id, id) ON DELETE RESTRICT,
    CONSTRAINT supplier_articles_food_fkey FOREIGN KEY (location_id, food_id) REFERENCES foods(location_id, id) ON DELETE RESTRICT,
    CONSTRAINT supplier_articles_unit_fkey FOREIGN KEY (order_unit_id) REFERENCES measurement_units(id) ON DELETE RESTRICT,
    CONSTRAINT supplier_articles_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT supplier_articles_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT supplier_articles_code_check CHECK (length(btrim(article_code, E' \t\r\n')) BETWEEN 1 AND 64 AND article_code = btrim(article_code, E' \t\r\n')),
    CONSTRAINT supplier_articles_name_check CHECK (name = btrim(name, E' \t\r\n') AND length(name) BETWEEN 1 AND 120),
    CONSTRAINT supplier_articles_pack_size_check CHECK (pack_size > 0),
    CONSTRAINT supplier_articles_row_version_check CHECK (row_version > 0)
);

CREATE UNIQUE INDEX supplier_articles_preferred_food_idx
    ON supplier_articles(location_id, food_id)
    WHERE preferred AND active AND food_id IS NOT NULL;

CREATE TABLE order_baskets (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    location_id bigint NOT NULL,
    supplier_id bigint NOT NULL,
    status text NOT NULL DEFAULT 'draft',
    row_version bigint NOT NULL DEFAULT 1,
    created_by bigint NOT NULL,
    updated_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT order_baskets_pkey PRIMARY KEY (id),
    CONSTRAINT order_baskets_public_id_key UNIQUE (public_id),
    CONSTRAINT order_baskets_location_fkey FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT,
    CONSTRAINT order_baskets_supplier_fkey FOREIGN KEY (location_id, supplier_id) REFERENCES suppliers(location_id, id) ON DELETE RESTRICT,
    CONSTRAINT order_baskets_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT order_baskets_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT order_baskets_status_check CHECK (status IN ('draft', 'abandoned', 'send_pending', 'sent', 'send_unknown')),
    CONSTRAINT order_baskets_row_version_check CHECK (row_version > 0)
);

CREATE TABLE order_basket_lines (
    id bigint GENERATED ALWAYS AS IDENTITY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    basket_id bigint NOT NULL,
    article_id bigint NOT NULL,
    quantity numeric(18,6) NOT NULL,
    sort_order smallint NOT NULL,
    CONSTRAINT order_basket_lines_pkey PRIMARY KEY (id),
    CONSTRAINT order_basket_lines_public_id_key UNIQUE (public_id),
    CONSTRAINT order_basket_lines_basket_sort_key UNIQUE (basket_id, sort_order),
    CONSTRAINT order_basket_lines_basket_fkey FOREIGN KEY (basket_id) REFERENCES order_baskets(id) ON DELETE RESTRICT,
    CONSTRAINT order_basket_lines_article_fkey FOREIGN KEY (article_id) REFERENCES supplier_articles(id) ON DELETE RESTRICT,
    CONSTRAINT order_basket_lines_quantity_check CHECK (quantity > 0),
    CONSTRAINT order_basket_lines_sort_check CHECK (sort_order BETWEEN 1 AND 64)
);

CREATE TRIGGER trg_suppliers_version BEFORE UPDATE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();
CREATE TRIGGER trg_supplier_articles_version BEFORE UPDATE ON supplier_articles
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();
CREATE TRIGGER trg_order_baskets_version BEFORE UPDATE ON order_baskets
    FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE FUNCTION supplier_mutate_v38(p_action text, p_actor bigint, p_actor_version bigint, p_location bigint, p_target uuid, p_target_version bigint, p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v suppliers%ROWTYPE; old_version bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor, p_actor_version, 'masterdata.write');
    PERFORM master_location(p_location);
    PERFORM master_payload(p_payload, ARRAY['code','name','active']);
    IF p_action = 'create' THEN
        INSERT INTO suppliers(location_id, code, name, created_by, updated_by)
        VALUES (p_location, p_payload->>'code', btrim(p_payload->>'name'), p_actor, p_actor)
        RETURNING * INTO v;
        old_version := NULL;
    ELSE
        PERFORM master_expectation(p_target, p_target_version);
        SELECT * INTO v FROM suppliers WHERE public_id = p_target AND location_id = p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        IF v.row_version <> p_target_version THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000', DETAIL='stale_object';
        END IF;
        old_version := v.row_version;
        UPDATE suppliers SET name = COALESCE(btrim(p_payload->>'name'), name),
            active = COALESCE((p_payload->>'active')::boolean, active), updated_by = p_actor
        WHERE id = v.id RETURNING * INTO v;
    END IF;
    PERFORM master_audit(p_actor, p_actor_version, p_location, 'supplier', v.public_id, p_action, old_version, v.row_version, '{}'::jsonb);
    RETURN jsonb_build_object('public_id', v.public_id, 'row_version', v.row_version);
END;$fn$;

CREATE FUNCTION supplier_article_mutate_v38(p_action text, p_actor bigint, p_actor_version bigint, p_location bigint, p_target uuid, p_target_version bigint, p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v supplier_articles%ROWTYPE; s suppliers%ROWTYPE; u measurement_units%ROWTYPE; f foods%ROWTYPE; old_version bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor, p_actor_version, 'masterdata.write');
    PERFORM master_location(p_location);
    PERFORM master_payload(p_payload, ARRAY['supplier_public_id','food_public_id','article_code','name','order_unit_code','pack_size','preferred','active']);
    IF p_action = 'create' THEN
        SELECT * INTO s FROM suppliers WHERE public_id = CAST(p_payload->>'supplier_public_id' AS uuid) AND location_id = p_location FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        SELECT * INTO u FROM measurement_units WHERE code = p_payload->>'order_unit_code';
        IF NOT FOUND THEN RAISE EXCEPTION 'Unbekannte Einheit.' USING ERRCODE='P1901'; END IF;
        IF p_payload->>'food_public_id' IS NOT NULL AND p_payload->>'food_public_id' <> '' THEN
            SELECT * INTO f FROM foods WHERE public_id = CAST(p_payload->>'food_public_id' AS uuid) AND location_id = p_location FOR SHARE;
            IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        END IF;
        INSERT INTO supplier_articles(location_id, supplier_id, food_id, article_code, name, order_unit_id, pack_size, preferred, created_by, updated_by)
        VALUES (p_location, s.id, f.id, btrim(p_payload->>'article_code'), btrim(p_payload->>'name'), u.id,
                COALESCE((p_payload->>'pack_size')::numeric, 1), COALESCE((p_payload->>'preferred')::boolean, false), p_actor, p_actor)
        RETURNING * INTO v;
        old_version := NULL;
    ELSE
        PERFORM master_expectation(p_target, p_target_version);
        SELECT * INTO v FROM supplier_articles WHERE public_id = p_target AND location_id = p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        IF v.row_version <> p_target_version THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000', DETAIL='stale_object';
        END IF;
        old_version := v.row_version;
        UPDATE supplier_articles SET name = COALESCE(btrim(p_payload->>'name'), name),
            preferred = COALESCE((p_payload->>'preferred')::boolean, preferred),
            active = COALESCE((p_payload->>'active')::boolean, active),
            pack_size = COALESCE((p_payload->>'pack_size')::numeric, pack_size),
            updated_by = p_actor
        WHERE id = v.id RETURNING * INTO v;
    END IF;
    PERFORM master_audit(p_actor, p_actor_version, p_location, 'supplier_article', v.public_id, p_action, old_version, v.row_version, '{}'::jsonb);
    RETURN jsonb_build_object('public_id', v.public_id, 'row_version', v.row_version);
END;$fn$;

REVOKE ALL ON FUNCTION supplier_mutate_v38(text, bigint, bigint, bigint, uuid, bigint, jsonb),
    supplier_article_mutate_v38(text, bigint, bigint, bigint, uuid, bigint, jsonb)
FROM PUBLIC, cafeteria_backup, cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION supplier_mutate_v38(text, bigint, bigint, bigint, uuid, bigint, jsonb),
    supplier_article_mutate_v38(text, bigint, bigint, bigint, uuid, bigint, jsonb)
TO cafeteria_app;
GRANT SELECT, INSERT, UPDATE ON suppliers, supplier_articles, order_baskets, order_basket_lines TO cafeteria_app;
REVOKE DELETE ON suppliers, supplier_articles, order_baskets, order_basket_lines FROM cafeteria_app;
GRANT SELECT ON suppliers, supplier_articles, order_baskets, order_basket_lines TO cafeteria_backup;
GRANT SELECT ON SEQUENCE suppliers_id_seq, supplier_articles_id_seq, order_baskets_id_seq, order_basket_lines_id_seq TO cafeteria_backup;

COMMIT;
