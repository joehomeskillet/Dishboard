BEGIN;
SET search_path TO cafeteria, public;

CREATE OR REPLACE FUNCTION record_local_login_lock()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cafeteria, pg_temp
AS $$
BEGIN
    IF NEW.failed_login_count >= 5
       AND NEW.locked_until IS NOT NULL
       AND NEW.locked_until > clock_timestamp()
       AND (OLD.locked_until IS NULL OR OLD.locked_until <= clock_timestamp()) THEN
        INSERT INTO audit_events(actor_user_id, action, entity_type, details)
        VALUES (
            NULL,
            'auth.local_login_locked',
            'user',
            jsonb_build_object(
                'user_id', NEW.user_id,
                'failed_login_count', NEW.failed_login_count
            )
        );
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_local_credentials_login_lock_audit ON local_credentials;
CREATE TRIGGER trg_local_credentials_login_lock_audit
AFTER UPDATE OF failed_login_count, locked_until ON local_credentials
FOR EACH ROW EXECUTE FUNCTION record_local_login_lock();

REVOKE EXECUTE ON FUNCTION record_local_login_lock()
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE INSERT ON audit_events FROM cafeteria_app;
REVOKE USAGE, SELECT, UPDATE ON SEQUENCE audit_events_id_seq FROM cafeteria_app;

REVOKE ALL ON SCHEMA cafeteria
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public
FROM cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
GRANT USAGE ON SCHEMA cafeteria
TO cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

COMMIT;
