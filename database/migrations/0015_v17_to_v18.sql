BEGIN;
SET search_path TO cafeteria, public;

-- Immutable normalized logos are included in the existing PostgreSQL backup.
-- Content hashes are primary keys: no sequence needs backup privileges.
CREATE TABLE IF NOT EXISTS branding_assets (
    sha256 text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    png_data bytea NOT NULL CHECK (
        octet_length(png_data) BETWEEN 8 AND 1048576
        AND substring(png_data FROM 1 FOR 8) = decode('89504e470d0a1a0a', 'hex')
        AND sha256 = encode(pg_catalog.sha256(png_data), 'hex')
    ),
    width integer NOT NULL CHECK (width BETWEEN 1 AND 2048),
    height integer NOT NULL CHECK (height BETWEEN 1 AND 2048),
    created_by bigint NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

REVOKE ALL ON branding_assets FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT SELECT, INSERT ON branding_assets TO cafeteria_app;
GRANT SELECT ON branding_assets TO cafeteria_backup;

COMMIT;
