BEGIN;
SET search_path TO cafeteria, public;

CREATE FUNCTION activate_screen_assignment_v23(
 p_actor bigint,p_authz bigint,p_profile text,p_expected_version bigint,
 p_template_id text,p_renderer_revision integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE
 v_key text; v_prefix text; v_before jsonb; v_after jsonb; v_version bigint;
BEGIN
 -- Canonical role-before-actor locks, current capability and 5-second timeout.
 PERFORM cafeteria.lock_operations_actor(p_actor,p_authz);
 IF p_profile IS NULL OR p_profile NOT IN ('staff_guest','patient')
    OR p_expected_version IS NULL OR p_expected_version<0 OR p_expected_version>9223372036854775806
    OR p_renderer_revision IS DISTINCT FROM 1 THEN
  RAISE EXCEPTION 'Invalid screen assignment.' USING ERRCODE='P2001';
 END IF;
 v_prefix:=CASE p_profile WHEN 'staff_guest' THEN 'cafeteria' ELSE 'patient' END;
 IF p_template_id IS NULL OR p_template_id NOT IN (v_prefix||'-week-photo',v_prefix||'-week-text') THEN
  RAISE EXCEPTION 'Incompatible screen template.' USING ERRCODE='P2001';
 END IF;
 v_key:='screen_assignment.v1.'||p_profile||'.web.week';
 v_before:=jsonb_build_object('schema_version',1,'version',0,
   'template_id',v_prefix||'-week-photo','renderer_revision',1);
 INSERT INTO cafeteria.settings(setting_key,setting_value,updated_by)
 VALUES(v_key,v_before,p_actor)
 ON CONFLICT(location_id,profile_id,setting_key) DO NOTHING;
 SELECT setting_value INTO STRICT v_before FROM cafeteria.settings
 WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=v_key FOR UPDATE;
 IF jsonb_typeof(v_before) IS DISTINCT FROM 'object' THEN
  RAISE EXCEPTION 'Invalid stored screen assignment.' USING ERRCODE='P2004';
 END IF;
 IF NOT (v_before ?& ARRAY['schema_version','version','template_id','renderer_revision'])
    OR v_before-ARRAY['schema_version','version','template_id','renderer_revision']<>'{}'::jsonb
    OR v_before->>'schema_version' IS DISTINCT FROM '1'
    OR jsonb_typeof(v_before->'schema_version') IS DISTINCT FROM 'number'
    OR v_before->>'renderer_revision' IS DISTINCT FROM '1'
    OR jsonb_typeof(v_before->'renderer_revision') IS DISTINCT FROM 'number'
    OR jsonb_typeof(v_before->'template_id') IS DISTINCT FROM 'string'
    OR NOT coalesce(v_before->>'template_id' IN (v_prefix||'-week-photo',v_prefix||'-week-text'),false)
    OR jsonb_typeof(v_before->'version') IS DISTINCT FROM 'number' THEN
  RAISE EXCEPTION 'Invalid stored screen assignment.' USING ERRCODE='P2004';
 END IF;
 IF (v_before->>'version') !~ '^(0|[1-9][0-9]{0,18})$' THEN
  RAISE EXCEPTION 'Invalid stored screen version.' USING ERRCODE='P2004';
 END IF;
 IF (v_before->>'version')::numeric>9223372036854775806 THEN
  RAISE EXCEPTION 'Invalid stored screen version.' USING ERRCODE='P2004';
 END IF;
 v_version:=(v_before->>'version')::bigint;
 IF v_version<>p_expected_version OR v_version=9223372036854775806
    OR v_before->>'template_id'=p_template_id THEN
  RAISE EXCEPTION 'Screen assignment conflict.' USING ERRCODE='55000';
 END IF;
 v_after:=jsonb_build_object('schema_version',1,'version',v_version+1,
   'template_id',p_template_id,'renderer_revision',1);
 UPDATE cafeteria.settings SET setting_value=v_after,updated_by=p_actor,updated_at=clock_timestamp()
 WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=v_key;
 INSERT INTO cafeteria.audit_events(actor_user_id,action,entity_type,profile_code,details)
 VALUES(p_actor,'screen_assignment.activate','screen_assignment',p_profile,jsonb_build_object(
  'actor_authz_version',p_authz,'profile',p_profile,'target','public.'||v_prefix||'_week',
  'before',v_before,'after',v_after));
 RETURN v_after;
END;$fn$;
REVOKE ALL ON FUNCTION activate_screen_assignment_v23(bigint,bigint,text,bigint,text,integer)
FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION activate_screen_assignment_v23(bigint,bigint,text,bigint,text,integer) TO cafeteria_app;

COMMIT;
