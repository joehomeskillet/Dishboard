from __future__ import annotations

# ruff: noqa: F401, F811

import hashlib
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import Engine, text

from cafeteria import db as database
from test_admin_workflow_db import WEEK_START, _actor_id, _staff_values
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


def _seed_v15_week(engine: Engine, actor: int) -> tuple[int, dict[str, Any]]:
    # Historical fixture deliberately uses only v15 columns, never current workflow readers.
    values = _staff_values()
    weekdays = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')
    days = []
    with engine.begin() as connection:
        location = connection.execute(text(
            'SELECT id,code,name FROM cafeteria.locations WHERE active'
        )).mappings().one()
        week_id = connection.execute(text('''
            INSERT INTO cafeteria.menu_weeks(location_id,profile_id,week_start,title,shared_note,created_by,updated_by)
            SELECT :location,id,:week,:title,:note,:actor,:actor FROM cafeteria.offer_profiles WHERE code='staff_guest'
            RETURNING id
        '''), {'location': location['id'], 'week': WEEK_START, 'title': values['title'],
               'note': values['shared_note'], 'actor': actor}).scalar_one()
        for offset, weekday in enumerate(weekdays):
            service_date = (WEEK_START + timedelta(days=offset)).isoformat()
            services = []
            if offset < 5:
                service_id = connection.execute(text('''
                    INSERT INTO cafeteria.menu_services(menu_week_id,service_date,meal_period_id,service_state,notice)
                    SELECT :week,:day,id,'open','' FROM cafeteria.meal_periods WHERE code='LUNCH' RETURNING id
                '''), {'week': week_id, 'day': service_date}).scalar_one()
                options = []
                for order, option in enumerate(values['days'][offset]['services'][0]['options'], 1):
                    external_id = f'STAFF-GUEST-{service_date}-LUNCH-{order}'
                    item_id = connection.execute(text('''
                        INSERT INTO cafeteria.menu_items(service_id,menu_type_id,external_id,title,allergen_review_status,sort_order)
                        SELECT :service,id,:external,:title,'checked',:sort FROM cafeteria.menu_types WHERE code=:type
                        RETURNING id
                    '''), {'service': service_id, 'external': external_id, 'title': option['title'],
                           'sort': order, 'type': option['type_code']}).scalar_one()
                    connection.execute(text('''
                        INSERT INTO cafeteria.menu_item_prices(menu_item_id,internal_rappen,external_rappen)
                        VALUES (:item,:internal,:external)
                    '''), {'item': item_id, 'internal': option['internal_rappen'], 'external': option['external_rappen']})
                    connection.execute(text('''
                        INSERT INTO cafeteria.menu_item_components(menu_item_id,sort_order,component_text)
                        VALUES (:item,1,:component)
                    '''), {'item': item_id, 'component': option['components'][0]})
                    options.append({
                        'external_id': external_id, 'type_code': option['type_code'],
                        'type_name': 'Menü 1' if order == 1 else 'Vegetarisch', 'title': option['title'],
                        'description': '', 'components': option['components'], 'labels': [], 'allergens': [],
                        'origins': [], 'note': '', 'allergen_review_status': 'checked',
                        'prices': {'internal_rappen': option['internal_rappen'],
                                   'external_rappen': option['external_rappen'], 'currency': 'CHF'},
                    })
                services.append({'meal_code': 'LUNCH', 'meal_name': 'Mittag', 'service_state': 'open',
                                 'notice': '', 'options': options})
            days.append({'date': service_date, 'weekday': weekday, 'state': 'open' if services else 'closed',
                         'notice': '', 'services': services})
    return int(week_id), {
        'schema_version': 1, 'profile_code': 'staff_guest', 'channel': 'cafeteria',
        'revision_id': 'CAF-2026-KW36-R1', 'location': {'code': location['code'], 'name': location['name']},
        'week_start': WEEK_START.isoformat(), 'week_end': (WEEK_START + timedelta(days=6)).isoformat(),
        'title': values['title'], 'shared_note': values['shared_note'], 'days': days,
    }


def test_v15_upgrade_preserves_checked_work_and_publication_without_fabricating_receipts(pg16):
    plan = database.migration_plan(SCHEMA)
    for migration in plan:
        if migration.version <= 15:
            database._execute_migration(pg16, migration)
    database._execute_script(pg16, str(SCHEMA.parent / 'seed.sql'))
    actor = _actor_id(pg16)
    week_id, snapshot = _seed_v15_week(pg16, actor)
    with pg16.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='cafeteria' AND table_name='menu_services' AND column_name='service_start'")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM cafeteria.menu_items WHERE allergen_review_status='checked'")).scalar_one() == 10
        connection.execute(text("UPDATE cafeteria.menu_items SET note='Bereits persönlich geprüft' WHERE id=(SELECT min(id) FROM cafeteria.menu_items)"))
        connection.execute(text("UPDATE cafeteria.menu_weeks SET workflow_state='published'"))
        connection.execute(text('''
            INSERT INTO cafeteria.publication_revisions(
                menu_week_id,revision_number,revision_code,snapshot_json,published_by
            ) VALUES (:week_id,1,'CAF-2026-KW36-R1',CAST(:snapshot AS jsonb),:actor)
        '''), {'week_id': week_id, 'snapshot': json.dumps(snapshot), 'actor': actor})
        items = connection.execute(text('SELECT to_jsonb(i) FROM cafeteria.menu_items i ORDER BY id')).scalars().all()
        weeks = connection.execute(text('SELECT to_jsonb(w) FROM cafeteria.menu_weeks w ORDER BY id')).scalars().all()
        revisions = connection.execute(text('SELECT to_jsonb(r) FROM cafeteria.publication_revisions r ORDER BY id')).scalars().all()
    applied = database.run_migrations(pg16, SCHEMA)
    assert [entry.version for entry in applied] == list(range(4, 21))
    database._execute_script(pg16, str(PERMISSIONS))
    with pg16.connect() as connection:
        assert connection.execute(text('SELECT to_jsonb(i) FROM cafeteria.menu_items i ORDER BY id')).scalars().all() == items
        assert connection.execute(text("SELECT to_jsonb(w)-'header_revision' FROM cafeteria.menu_weeks w ORDER BY id")).scalars().all() == weeks
        assert connection.execute(text('SELECT to_jsonb(r) FROM cafeteria.publication_revisions r ORDER BY id')).scalars().all() == revisions
        assert connection.execute(text("SELECT count(*) FROM cafeteria.audit_events WHERE action LIKE 'workflow.%'")).scalar_one() == 0
        assert connection.execute(text('SELECT snapshot_json FROM cafeteria.active_publications')).scalar_one() == snapshot
        assert connection.execute(text('SELECT header_revision FROM cafeteria.menu_weeks')).scalar_one() == 1
        row = connection.execute(text('SELECT name,application_version,checksum_sha256 FROM cafeteria.schema_migrations WHERE version=20')).one()
        assert row == ('0017_v19_to_v20.sql', 'dishboard-schema-v20', hashlib.sha256(plan[-1].path.read_bytes()).hexdigest())
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
