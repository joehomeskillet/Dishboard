from __future__ import annotations

# ruff: noqa: F401, F811

import hashlib
import json

from sqlalchemy import text

from cafeteria import db as database
from cafeteria.workflow import load_draft
from cafeteria.workflow_snapshot import build_snapshot
from test_admin_workflow_db import WEEK_START, _actor_id, _save, _staff_values
from test_component_metadata_master_lock_db import SCHEMA, PERMISSIONS, _drop_schema, pg16


def _functions(connection):
    return connection.execute(text('''
        SELECT proname,prosrc,prosecdef,proconfig,
               has_function_privilege('cafeteria_app',oid,'EXECUTE') AS app,
               has_function_privilege('cafeteria_backup',oid,'EXECUTE') AS backup,
               has_function_privilege('cafeteria_auth_issuer',oid,'EXECUTE') AS issuer,
               has_function_privilege('public',oid,'EXECUTE') AS public
        FROM pg_proc WHERE pronamespace='cafeteria'::regnamespace
          AND proname IN ('bump_week_header_revision','workflow_week_context',
              'require_workflow_review_actor','record_menu_review','record_week_context_review')
        ORDER BY proname
    ''')).all()


def test_v15_upgrade_preserves_checked_work_and_publication_without_fabricating_receipts(pg16):
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 15:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    _save(pg16, 'staff_guest', _staff_values())
    actor = _actor_id(pg16)
    draft = load_draft(pg16, 'staff_guest', WEEK_START, actor_id=actor)
    snapshot = build_snapshot('staff_guest', draft, 'CAF-2026-KW36-R1')
    with pg16.begin() as connection:
        connection.execute(text("UPDATE cafeteria.menu_items SET note='Bereits persönlich geprüft' WHERE id=(SELECT min(id) FROM cafeteria.menu_items)"))
        connection.execute(text("UPDATE cafeteria.menu_weeks SET workflow_state='published'"))
        connection.execute(text('''
            INSERT INTO cafeteria.publication_revisions(
                menu_week_id,revision_number,revision_code,snapshot_json,published_by
            ) VALUES (:week_id,1,'CAF-2026-KW36-R1',CAST(:snapshot AS jsonb),:actor)
        '''), {'week_id': draft['id'], 'snapshot': json.dumps(snapshot), 'actor': actor})
        items = connection.execute(text('SELECT to_jsonb(i) FROM cafeteria.menu_items i ORDER BY id')).scalars().all()
        weeks = connection.execute(text('SELECT to_jsonb(w) FROM cafeteria.menu_weeks w ORDER BY id')).scalars().all()
        revisions = connection.execute(text('SELECT to_jsonb(r) FROM cafeteria.publication_revisions r ORDER BY id')).scalars().all()
    applied = database.run_migrations(pg16, SCHEMA)
    assert [entry.version for entry in applied] == list(range(4, 17))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert connection.execute(text('SELECT to_jsonb(i) FROM cafeteria.menu_items i ORDER BY id')).scalars().all() == items
        assert connection.execute(text("SELECT to_jsonb(w)-'header_revision' FROM cafeteria.menu_weeks w ORDER BY id")).scalars().all() == weeks
        assert connection.execute(text('SELECT to_jsonb(r) FROM cafeteria.publication_revisions r ORDER BY id')).scalars().all() == revisions
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE 'workflow.%'")).scalar_one() == 0
        assert connection.execute(text('SELECT snapshot_json FROM cafeteria.active_publications')).scalar_one() == snapshot
        assert connection.execute(text('SELECT header_revision FROM cafeteria.menu_weeks')).scalar_one() == 1
        row = connection.execute(text('SELECT name,application_version,checksum_sha256 FROM cafeteria.schema_migrations WHERE version=16')).one()
        assert row == ('0013_v15_to_v16.sql', 'dishboard-schema-v16', hashlib.sha256(plan[-1].path.read_bytes()).hexdigest())
        migrated = _functions(connection)
        for info in migrated:
            assert not info.backup and not info.issuer and not info.public
            assert info.app == (info.proname in {'workflow_week_context', 'record_menu_review', 'record_week_context_review'})
            assert info.proconfig == ['search_path=pg_catalog, cafeteria, pg_temp']
        ledger = connection.execute(text('SELECT * FROM cafeteria.schema_migrations ORDER BY version')).all()
    database.run_migrations(pg16, SCHEMA)
    with pg16.connect() as connection:
        assert connection.execute(text('SELECT * FROM cafeteria.schema_migrations ORDER BY version')).all() == ledger
    _drop_schema(pg16)
    database._execute_script(pg16, str(SCHEMA))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert _functions(connection) == migrated
