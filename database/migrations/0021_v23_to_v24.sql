BEGIN;
SET search_path TO cafeteria, public;

CREATE OR REPLACE FUNCTION ensure_auth_capability_state()
RETURNS smallint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
DECLARE
    v_schema_owner text;
BEGIN
    SELECT pg_get_userbyid(nspowner)
      INTO v_schema_owner
      FROM pg_namespace
     WHERE nspname='cafeteria';
    IF session_user IS DISTINCT FROM v_schema_owner THEN
        RAISE EXCEPTION 'Capability-Zustand darf nur der Schema-Owner reparieren.'
            USING ERRCODE = '42501';
    END IF;
    CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
    IF to_regprocedure('public.gen_random_bytes(integer)') IS NULL
       OR to_regprocedure('public.hmac(bytea,bytea,text)') IS NULL THEN
        RAISE EXCEPTION 'pgcrypto ist nicht kanonisch im public-Schema verfügbar.'
            USING ERRCODE = '55000';
    END IF;
    CREATE TABLE IF NOT EXISTS auth_capability_secrets (
        id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        secret bytea NOT NULL CHECK (octet_length(secret) = 32),
        active boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        retired_at timestamptz,
        CHECK (active OR retired_at IS NOT NULL),
        CHECK (NOT active OR retired_at IS NULL)
    );
    CREATE TABLE IF NOT EXISTS auth_capability_nonces (
        nonce bytea PRIMARY KEY CHECK (octet_length(nonce) = 16),
        actor_user_id bigint NOT NULL REFERENCES users(id),
        revision_id bigint NOT NULL REFERENCES publication_revisions(id),
        consumed_at timestamptz NOT NULL DEFAULT clock_timestamp()
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_auth_capability_one_active
        ON auth_capability_secrets ((true)) WHERE active;
    IF pg_get_serial_sequence('cafeteria.auth_capability_secrets', 'id')
       IS DISTINCT FROM 'cafeteria.auth_capability_secrets_id_seq' THEN
        RAISE EXCEPTION 'Capability-Secret-Identity-Sequenz ist nicht kanonisch.'
            USING ERRCODE = '55000';
    END IF;
    -- PG18 also stores NOT NULL in pg_constraint. Check its representation
    -- separately; accepting a matching total would hide malformed constraints.
    IF EXISTS (
        WITH actual AS (
            SELECT c.conrelid, c.contype, c.conkey,
                   regexp_replace(pg_get_expr(c.conbin,c.conrelid), '\s', '', 'g') AS expression,
                   c.confrelid, c.confkey
            FROM pg_constraint c
            WHERE c.conrelid IN ('auth_capability_secrets'::regclass,
                                'auth_capability_nonces'::regclass)
              AND c.contype <> 'n'
        ), expected (conrelid,contype,conkey,expression,confrelid,confkey) AS (
            VALUES
              ('auth_capability_secrets'::regclass,'p'::"char",ARRAY[1]::smallint[],NULL,0::oid,NULL::smallint[]),
              ('auth_capability_secrets'::regclass,'c',ARRAY[2]::smallint[],'(octet_length(secret)=32)',0,NULL),
              ('auth_capability_secrets'::regclass,'c',ARRAY[3,5]::smallint[],'(activeOR(retired_atISNOTNULL))',0,NULL),
              ('auth_capability_secrets'::regclass,'c',ARRAY[3,5]::smallint[],'((NOTactive)OR(retired_atISNULL))',0,NULL),
              ('auth_capability_nonces'::regclass,'p',ARRAY[1]::smallint[],NULL,0,NULL),
              ('auth_capability_nonces'::regclass,'c',ARRAY[1]::smallint[],'(octet_length(nonce)=16)',0,NULL),
              ('auth_capability_nonces'::regclass,'f',ARRAY[2]::smallint[],NULL,'users'::regclass,ARRAY[1]::smallint[]),
              ('auth_capability_nonces'::regclass,'f',ARRAY[3]::smallint[],NULL,'publication_revisions'::regclass,ARRAY[1]::smallint[])
        )
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
        UNION ALL
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
    ) OR EXISTS (
        SELECT 1 FROM pg_constraint c
        WHERE c.conrelid IN ('auth_capability_secrets'::regclass,
                            'auth_capability_nonces'::regclass)
          AND (c.connamespace <> 'cafeteria'::regnamespace
               OR NOT c.convalidated OR c.condeferrable OR c.condeferred
               OR NOT c.conislocal OR c.coninhcount <> 0
               OR NOT coalesce((to_jsonb(c)->>'conenforced')::boolean,
                               current_setting('server_version_num')::integer < 180000)
               OR (c.contype='f' AND (c.confupdtype <> 'a' OR c.confdeltype <> 'a'
                                     OR c.confmatchtype <> 's')))
    ) OR EXISTS (
        SELECT c.oid FROM pg_class c
        LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
        WHERE c.oid IN ('auth_capability_secrets'::regclass,'auth_capability_nonces'::regclass)
        GROUP BY c.oid
        HAVING array_agg(a.attnum ORDER BY a.attnum) FILTER (WHERE a.attnotnull)
               IS DISTINCT FROM ARRAY[1,2,3,4]::smallint[]
    ) OR (current_setting('server_version_num')::integer >= 180000 AND EXISTS (
        WITH actual AS (
            SELECT c.conrelid,c.conkey FROM pg_constraint c
            WHERE c.conrelid IN ('auth_capability_secrets'::regclass,'auth_capability_nonces'::regclass)
              AND c.contype='n'
        ), expected AS (
            SELECT t.relid,ARRAY[a.attnum]::smallint[]
            FROM (VALUES ('auth_capability_secrets'::regclass),
                         ('auth_capability_nonces'::regclass)) t(relid)
            CROSS JOIN generate_series(1,4) a(attnum)
        )
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
        UNION ALL
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
    )) THEN
        RAISE EXCEPTION 'Capability-Zustand besitzt nicht die kanonischen Constraints.'
            USING ERRCODE = '55000';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
        JOIN pg_am am ON am.oid=c.relam
        WHERE i.indexrelid='uq_auth_capability_one_active'::regclass
          AND i.indrelid='auth_capability_secrets'::regclass
          AND i.indisunique AND NOT i.indisprimary AND i.indisvalid AND i.indisready AND i.indislive
          AND i.indnkeyatts=1 AND i.indnatts=1 AND i.indkey::text='0' AND am.amname='btree'
          AND pg_get_expr(i.indexprs,i.indrelid)='true'
          AND pg_get_expr(i.indpred,i.indrelid)='active'
    ) THEN
        RAISE EXCEPTION 'Capability-Secret-Aktivindex ist nicht kanonisch.' USING ERRCODE='55000';
    END IF;
    REVOKE ALL ON auth_capability_secrets, auth_capability_nonces FROM PUBLIC;
    REVOKE ALL ON SEQUENCE auth_capability_secrets_id_seq FROM PUBLIC;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cafeteria_app') THEN
        REVOKE ALL ON auth_capability_secrets, auth_capability_nonces FROM cafeteria_app;
        REVOKE ALL ON SEQUENCE auth_capability_secrets_id_seq FROM cafeteria_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cafeteria_backup') THEN
        REVOKE ALL ON auth_capability_secrets, auth_capability_nonces FROM cafeteria_backup;
        REVOKE ALL ON SEQUENCE auth_capability_secrets_id_seq FROM cafeteria_backup;
    END IF;
    RETURN 1;
END;
$$;

COMMIT;
