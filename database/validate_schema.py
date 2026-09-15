#!/usr/bin/env python3
"""Statische Prüfung der SQL-Baseline und der zwei Demo-Snapshots.

Eine laufende PostgreSQL-Instanz wird damit nicht ersetzt. Das Ergebnis trennt
bewusst statische Artefaktprüfung von Live-Ausführung.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'database' / 'schema.sql'
MIGRATION_0001 = ROOT / 'database' / 'migrations' / '0001_initial_postgresql.sql'
MIGRATION_0002 = ROOT / 'database' / 'migrations' / '0002_profile_publication_and_local_auth.sql'
MIGRATION_0003 = ROOT / 'database' / 'migrations' / '0003_patient_key_and_withdrawal_contracts.sql'
MIGRATION_0004 = ROOT / 'database' / 'migrations' / '0004_patient_key_lock_and_capability_contracts.sql'
MIGRATION_0005 = ROOT / 'database' / 'migrations' / '0005_least_privilege_identity_contracts.sql'
MIGRATION_0006 = ROOT / 'database' / 'migrations' / '0006_auth_issuer_and_local_login.sql'
MIGRATION_0007 = ROOT / 'database' / 'migrations' / '0007_auth_security_hardening.sql'
MIGRATION_0009 = ROOT / 'database' / 'migrations' / '0009_bootstrap_first_local_admin.sql'
MIGRATION_0008 = ROOT / 'database' / 'migrations' / '0008_auth_final_hardening.sql'
MIGRATION_0010 = ROOT / 'database' / 'migrations' / '0010_v12_to_v13.sql'
MIGRATION_0011 = ROOT / 'database' / 'migrations' / '0011_v13_to_v14.sql'
MIGRATION_0012 = ROOT / 'database' / 'migrations' / '0012_v14_to_v15.sql'
MIGRATION_0013 = ROOT / 'database' / 'migrations' / '0013_v15_to_v16.sql'
MIGRATION_0014 = ROOT / 'database' / 'migrations' / '0014_v16_to_v17.sql'
MIGRATION_0015 = ROOT / 'database' / 'migrations' / '0015_v17_to_v18.sql'
MIGRATION_0016 = ROOT / 'database' / 'migrations' / '0016_v18_to_v19.sql'
MIGRATION_0017 = ROOT / 'database' / 'migrations' / '0017_v19_to_v20.sql'
MIGRATION_0018 = ROOT / 'database' / 'migrations' / '0018_v20_to_v21.sql'
MIGRATION_0019 = ROOT / 'database' / 'migrations' / '0019_v21_to_v22.sql'
MIGRATION_0020 = ROOT / 'database' / 'migrations' / '0020_v22_to_v23.sql'
MIGRATION_0021 = ROOT / 'database' / 'migrations' / '0021_v23_to_v24.sql'
MIGRATION_0022 = ROOT / 'database' / 'migrations' / '0022_v24_to_v25.sql'
MIGRATION_0023 = ROOT / 'database' / 'migrations' / '0023_v25_to_v26.sql'
MIGRATION_0024 = ROOT / 'database' / 'migrations' / '0024_v26_to_v27.sql'
MIGRATION_0025 = ROOT / 'database' / 'migrations' / '0025_v27_to_v28.sql'
MIGRATION_0026 = ROOT / 'database' / 'migrations' / '0026_v28_to_v29.sql'
MIGRATION_0027 = ROOT / 'database' / 'migrations' / '0027_v29_to_v30.sql'
MIGRATION_0028 = ROOT / 'database' / 'migrations' / '0028_v30_to_v31.sql'
MIGRATION_0029 = ROOT / 'database' / 'migrations' / '0029_v31_to_v32.sql'
MIGRATION_0030 = ROOT / 'database' / 'migrations' / '0030_v32_to_v33.sql'
MIGRATION_0031 = ROOT / 'database' / 'migrations' / '0031_v33_to_v34.sql'
PERMISSIONS = ROOT / 'database' / 'permissions.sql'
SEED = ROOT / 'database' / 'seed.sql'
CAF_JSON = ROOT / 'demo' / 'snapshots' / 'cafeteria_kw36.json'
PAT_JSON = ROOT / 'demo' / 'snapshots' / 'patienten_kw36.json'

FORBIDDEN_PATIENT_COMPACT_TOKENS = (
    'price', 'prices', 'preis', 'preise', 'cost', 'costs', 'amount', 'amounts',
    'kosten', 'betrag', 'rappen', 'currency', 'chf', 'fee', 'tarif', 'tariff', 'charge',
)
ALLOWED_PATIENT_COMPACT_KEYS = frozenset({
    'channel', 'days', 'date', 'notice', 'services', 'mealcode', 'mealname',
    'options', 'allergenreviewstatus', 'allergens', 'components', 'description',
    'externalid', 'labels', 'note', 'origins', 'title', 'typecode', 'typename',
    'code', 'name', 'presence', 'countrycode', 'ingredient', 'text', 'state',
    'weekday', 'location', 'profilecode', 'revisionid', 'schemaversion',
    'sharednote', 'weekend', 'weekstart', 'servicestate',
    'servicestart', 'serviceend', 'areaname',
    'accompanimentcode', 'accompanimentname',
})


def fail(message: str) -> NoReturn:
    raise ValueError(message)


# Schema34-Einkaufslistenvertrag: eine Quelle für Artefaktmodus (Quelltext in 0031, schema.sql,
# permissions.sql) und Live-Modus (Katalog nach run_migrations, PostgreSQL 16).
SHOPPING_TABLES = (
    'shopping_lists', 'shopping_list_revisions', 'shopping_list_manual_items', 'shopping_list_line_status',
)
SHOPPING_SEQUENCES = (
    'shopping_lists_id_seq', 'shopping_list_revisions_id_seq', 'shopping_list_manual_items_id_seq',
)
# (Spaltenquelltext, (data_type, is_nullable, column_default, identity_generation, precision, scale))
_IDENTITY = ('bigint', 'NO', None, 'ALWAYS', 64, 0)
_PUBLIC_ID = ('uuid', 'NO', 'gen_random_uuid()', None, None, None)
_BIGINT_NOT_NULL = ('bigint', 'NO', None, None, 64, 0)
_TEXT_NOT_NULL = ('text', 'NO', None, None, None, None)
_ROW_VERSION = ('bigint', 'NO', '1', None, 64, 0)
_CLOCK = ('timestamp with time zone', 'NO', 'clock_timestamp()', None, None, None)
SHOPPING_COLUMNS: dict[str, tuple[tuple[str, tuple[Any, ...]], ...]] = {
    'shopping_lists': (
        ('id bigint GENERATED ALWAYS AS IDENTITY', _IDENTITY),
        ('public_id uuid NOT NULL DEFAULT gen_random_uuid()', _PUBLIC_ID),
        ('location_id bigint NOT NULL', _BIGINT_NOT_NULL),
        ('menu_week_id bigint', ('bigint', 'YES', None, None, 64, 0)),
        ('title text NOT NULL', _TEXT_NOT_NULL),
        ('note text', ('text', 'YES', None, None, None, None)),
        ('row_version bigint NOT NULL DEFAULT 1', _ROW_VERSION),
        ('created_by bigint NOT NULL', _BIGINT_NOT_NULL),
        ('updated_by bigint NOT NULL', _BIGINT_NOT_NULL),
        ('created_at timestamptz NOT NULL DEFAULT clock_timestamp()', _CLOCK),
        ('updated_at timestamptz NOT NULL DEFAULT clock_timestamp()', _CLOCK),
        ('archived_at timestamptz', ('timestamp with time zone', 'YES', None, None, None, None)),
    ),
    'shopping_list_revisions': (
        ('id bigint GENERATED ALWAYS AS IDENTITY', _IDENTITY),
        ('public_id uuid NOT NULL DEFAULT gen_random_uuid()', _PUBLIC_ID),
        ('shopping_list_id bigint NOT NULL', _BIGINT_NOT_NULL),
        ('revision_number integer NOT NULL', ('integer', 'NO', None, None, 32, 0)),
        ('policy text NOT NULL', _TEXT_NOT_NULL),
        ('snapshot_json jsonb NOT NULL', ('jsonb', 'NO', None, None, None, None)),
        ('content_hash_sha256 text NOT NULL', _TEXT_NOT_NULL),
        ('computed_by bigint NOT NULL', _BIGINT_NOT_NULL),
        ('computed_at timestamptz NOT NULL DEFAULT clock_timestamp()', _CLOCK),
    ),
    'shopping_list_manual_items': (
        ('id bigint GENERATED ALWAYS AS IDENTITY', _IDENTITY),
        ('public_id uuid NOT NULL DEFAULT gen_random_uuid()', _PUBLIC_ID),
        ('shopping_list_id bigint NOT NULL', _BIGINT_NOT_NULL),
        ('sort_order integer NOT NULL', ('integer', 'NO', None, None, 32, 0)),
        ('item_text text NOT NULL', _TEXT_NOT_NULL),
        ('quantity numeric(18,6)', ('numeric', 'YES', None, None, 18, 6)),
        ('unit_id bigint', ('bigint', 'YES', None, None, 64, 0)),
        ('checked boolean NOT NULL DEFAULT false', ('boolean', 'NO', 'false', None, None, None)),
        ('row_version bigint NOT NULL DEFAULT 1', _ROW_VERSION),
        ('created_by bigint NOT NULL', _BIGINT_NOT_NULL),
        ('updated_by bigint NOT NULL', _BIGINT_NOT_NULL),
        ('created_at timestamptz NOT NULL DEFAULT clock_timestamp()', _CLOCK),
        ('updated_at timestamptz NOT NULL DEFAULT clock_timestamp()', _CLOCK),
    ),
    'shopping_list_line_status': (
        ('shopping_list_id bigint NOT NULL', _BIGINT_NOT_NULL),
        ('line_key text NOT NULL', _TEXT_NOT_NULL),
        ('revision_id bigint NOT NULL', _BIGINT_NOT_NULL),
        ('checked_quantity text NOT NULL', _TEXT_NOT_NULL),
        ('checked_by bigint NOT NULL', _BIGINT_NOT_NULL),
        ('checked_at timestamptz NOT NULL DEFAULT clock_timestamp()', _CLOCK),
    ),
}


def _restrict_fk(columns: str, target: str, target_columns: str = 'id') -> tuple[str, str, str]:
    clause = f'FOREIGN KEY ({columns}) REFERENCES {{schema}}{target}({target_columns}) ON DELETE RESTRICT'
    return 'f', clause.format(schema=''), clause.format(schema='cafeteria.')


def _check(source: str, live: str) -> tuple[str, str, str]:
    return 'c', f'CHECK ({source})', f'CHECK ({live})'


def _trimmed_text_check(column: str, maximum: int) -> tuple[str, str, str]:
    return _check(
        f"{column} = btrim({column}, E' \\t\\r\\n') AND length({column}) BETWEEN 1 AND {maximum}",
        f"{column} = btrim({column}, ' \t\r\n'::text) AND length({column}) >= 1 AND length({column}) <= {maximum}",
    )


# (Tabelle, Constraint) -> (contype, Quelltext, pg_get_constraintdef(oid, true)); Reihenfolge = Quelltext.
SHOPPING_CONSTRAINTS: dict[tuple[str, str], tuple[str, str, str]] = {
    ('shopping_lists', 'shopping_lists_pkey'): ('p', 'PRIMARY KEY (id)', 'PRIMARY KEY (id)'),
    ('shopping_lists', 'shopping_lists_public_id_key'): ('u', 'UNIQUE (public_id)', 'UNIQUE (public_id)'),
    ('shopping_lists', 'shopping_lists_location_id_fkey'): _restrict_fk('location_id', 'locations'),
    ('shopping_lists', 'shopping_lists_menu_week_id_fkey'): _restrict_fk('menu_week_id', 'menu_weeks'),
    ('shopping_lists', 'shopping_lists_created_by_fkey'): _restrict_fk('created_by', 'users'),
    ('shopping_lists', 'shopping_lists_updated_by_fkey'): _restrict_fk('updated_by', 'users'),
    ('shopping_lists', 'shopping_lists_title_check'): _trimmed_text_check('title', 120),
    ('shopping_lists', 'shopping_lists_note_check'): _check(
        "note IS NULL OR (note = btrim(note, E' \\t\\r\\n') AND length(note) <= 2000)",
        "note IS NULL OR note = btrim(note, ' \t\r\n'::text) AND length(note) <= 2000",
    ),
    ('shopping_lists', 'shopping_lists_row_version_check'): _check('row_version > 0', 'row_version > 0'),
    ('shopping_list_revisions', 'shopping_list_revisions_pkey'): ('p', 'PRIMARY KEY (id)', 'PRIMARY KEY (id)'),
    ('shopping_list_revisions', 'shopping_list_revisions_public_id_key'): (
        'u', 'UNIQUE (public_id)', 'UNIQUE (public_id)',
    ),
    ('shopping_list_revisions', 'shopping_list_revisions_id_shopping_list_id_key'): (
        'u', 'UNIQUE (id, shopping_list_id)', 'UNIQUE (id, shopping_list_id)',
    ),
    ('shopping_list_revisions', 'shopping_list_revisions_shopping_list_id_revision_number_key'): (
        'u', 'UNIQUE (shopping_list_id, revision_number)', 'UNIQUE (shopping_list_id, revision_number)',
    ),
    ('shopping_list_revisions', 'shopping_list_revisions_shopping_list_id_fkey'): _restrict_fk(
        'shopping_list_id', 'shopping_lists',
    ),
    ('shopping_list_revisions', 'shopping_list_revisions_computed_by_fkey'): _restrict_fk('computed_by', 'users'),
    ('shopping_list_revisions', 'shopping_list_revisions_revision_number_check'): _check(
        'revision_number > 0', 'revision_number > 0',
    ),
    ('shopping_list_revisions', 'shopping_list_revisions_policy_check'): _check(
        "policy IN ('leaf', 'prepared')", "policy = ANY (ARRAY['leaf'::text, 'prepared'::text])",
    ),
    ('shopping_list_revisions', 'shopping_list_revisions_snapshot_json_check'): _check(
        "jsonb_typeof(snapshot_json) = 'object' AND snapshot_json ?& ARRAY['inputs', 'result'] "
        "AND jsonb_typeof(snapshot_json -> 'inputs') = 'array' "
        "AND jsonb_typeof(snapshot_json -> 'result') = 'object'",
        "jsonb_typeof(snapshot_json) = 'object'::text AND snapshot_json ?& ARRAY['inputs'::text, 'result'::text] "
        "AND jsonb_typeof(snapshot_json -> 'inputs'::text) = 'array'::text "
        "AND jsonb_typeof(snapshot_json -> 'result'::text) = 'object'::text",
    ),
    ('shopping_list_revisions', 'shopping_list_revisions_content_hash_sha256_check'): _check(
        "content_hash_sha256 = encode(public.digest(convert_to(snapshot_json::text, 'UTF8'), 'sha256'), 'hex')",
        "content_hash_sha256 = encode(digest(convert_to(snapshot_json::text, 'UTF8'::name), 'sha256'::text), 'hex'::text)",
    ),
    ('shopping_list_manual_items', 'shopping_list_manual_items_pkey'): ('p', 'PRIMARY KEY (id)', 'PRIMARY KEY (id)'),
    ('shopping_list_manual_items', 'shopping_list_manual_items_public_id_key'): (
        'u', 'UNIQUE (public_id)', 'UNIQUE (public_id)',
    ),
    ('shopping_list_manual_items', 'shopping_list_manual_items_shopping_list_id_sort_order_key'): (
        'u', 'UNIQUE (shopping_list_id, sort_order)', 'UNIQUE (shopping_list_id, sort_order)',
    ),
    ('shopping_list_manual_items', 'shopping_list_manual_items_shopping_list_id_fkey'): _restrict_fk(
        'shopping_list_id', 'shopping_lists',
    ),
    ('shopping_list_manual_items', 'shopping_list_manual_items_unit_id_fkey'): _restrict_fk(
        'unit_id', 'measurement_units',
    ),
    ('shopping_list_manual_items', 'shopping_list_manual_items_created_by_fkey'): _restrict_fk('created_by', 'users'),
    ('shopping_list_manual_items', 'shopping_list_manual_items_updated_by_fkey'): _restrict_fk('updated_by', 'users'),
    ('shopping_list_manual_items', 'shopping_list_manual_items_sort_order_check'): _check(
        'sort_order > 0', 'sort_order > 0',
    ),
    ('shopping_list_manual_items', 'shopping_list_manual_items_item_text_check'): _trimmed_text_check('item_text', 200),
    ('shopping_list_manual_items', 'shopping_list_manual_items_quantity_check'): _check(
        'quantity IS NULL OR quantity > 0', 'quantity IS NULL OR quantity > 0::numeric',
    ),
    ('shopping_list_manual_items', 'shopping_list_manual_items_quantity_unit_check'): _check(
        '(quantity IS NULL) = (unit_id IS NULL)', '(quantity IS NULL) = (unit_id IS NULL)',
    ),
    ('shopping_list_manual_items', 'shopping_list_manual_items_row_version_check'): _check(
        'row_version > 0', 'row_version > 0',
    ),
    ('shopping_list_line_status', 'shopping_list_line_status_pkey'): (
        'p', 'PRIMARY KEY (shopping_list_id, line_key)', 'PRIMARY KEY (shopping_list_id, line_key)',
    ),
    ('shopping_list_line_status', 'shopping_list_line_status_revision_id_fkey'): _restrict_fk(
        'revision_id, shopping_list_id', 'shopping_list_revisions', 'id, shopping_list_id',
    ),
    ('shopping_list_line_status', 'shopping_list_line_status_checked_by_fkey'): _restrict_fk('checked_by', 'users'),
    ('shopping_list_line_status', 'shopping_list_line_status_line_key_check'): _trimmed_text_check('line_key', 300),
    ('shopping_list_line_status', 'shopping_list_line_status_checked_quantity_check'): _trimmed_text_check(
        'checked_quantity', 100,
    ),
}
# Index -> (Tabelle, Quelltext, pg_indexes.indexdef); PK-/UNIQUE-Indizes folgen aus SHOPPING_CONSTRAINTS.
SHOPPING_INDEXES: dict[str, tuple[str, str, str]] = {
    'shopping_lists_location_id_idx': (
        'shopping_lists', 'ON shopping_lists(location_id)', 'ON cafeteria.shopping_lists USING btree (location_id)',
    ),
    'shopping_lists_menu_week_id_idx': (
        'shopping_lists',
        'ON shopping_lists(menu_week_id) WHERE menu_week_id IS NOT NULL',
        'ON cafeteria.shopping_lists USING btree (menu_week_id) WHERE (menu_week_id IS NOT NULL)',
    ),
    'shopping_list_manual_items_unit_id_idx': (
        'shopping_list_manual_items',
        'ON shopping_list_manual_items(unit_id) WHERE unit_id IS NOT NULL',
        'ON cafeteria.shopping_list_manual_items USING btree (unit_id) WHERE (unit_id IS NOT NULL)',
    ),
}
# Trigger-Funktion -> plpgsql-Rumpf; beide SECURITY INVOKER mit festem search_path, ohne EXECUTE-Grant.
SHOPPING_FUNCTIONS: dict[str, str] = {
    'shopping_list_scope_protect_v34': (
        'BEGIN IF NEW.location_id IS DISTINCT FROM OLD.location_id THEN '
        "RAISE EXCEPTION 'Der Standort einer Einkaufsliste ist unveränderlich.' USING ERRCODE='55000'; "
        'END IF; RETURN NEW; END;'
    ),
    'shopping_list_revision_protect_v34': (
        "BEGIN RAISE EXCEPTION 'Einkaufslisten-Berechnungsrevisionen sind unveränderlich.' "
        "USING ERRCODE='55000'; END;"
    ),
}
# Trigger -> (Tabelle, Zeitpunkt im Quelltext, Zeitpunkt im Katalog, Ebene, Funktion)
SHOPPING_TRIGGERS: dict[str, tuple[str, str, str, str, str]] = {
    'trg_shopping_lists_version': (
        'shopping_lists', 'BEFORE UPDATE', 'BEFORE UPDATE', 'ROW', 'bump_row_version_and_updated_at',
    ),
    'trg_shopping_list_manual_items_version': (
        'shopping_list_manual_items', 'BEFORE UPDATE', 'BEFORE UPDATE', 'ROW', 'bump_row_version_and_updated_at',
    ),
    'shopping_lists_scope_protect': (
        'shopping_lists', 'BEFORE UPDATE', 'BEFORE UPDATE', 'ROW', 'shopping_list_scope_protect_v34',
    ),
    'shopping_list_revisions_immutable': (
        'shopping_list_revisions', 'BEFORE UPDATE OR DELETE', 'BEFORE DELETE OR UPDATE', 'ROW',
        'shopping_list_revision_protect_v34',
    ),
    'shopping_list_revisions_no_truncate': (
        'shopping_list_revisions', 'BEFORE TRUNCATE', 'BEFORE TRUNCATE', 'STATEMENT',
        'shopping_list_revision_protect_v34',
    ),
}
SHOPPING_ACL_STATEMENTS = (
    'REVOKE ALL ON FUNCTION shopping_list_scope_protect_v34(), shopping_list_revision_protect_v34() '
    'FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;',
    'GRANT SELECT, INSERT, UPDATE, DELETE ON shopping_lists, shopping_list_manual_items, '
    'shopping_list_line_status TO cafeteria_app;',
    'GRANT SELECT, INSERT ON shopping_list_revisions TO cafeteria_app;',
    'GRANT SELECT ON shopping_lists, shopping_list_revisions, shopping_list_manual_items, '
    'shopping_list_line_status TO cafeteria_backup;',
    'GRANT SELECT ON SEQUENCE shopping_lists_id_seq, shopping_list_revisions_id_seq, '
    'shopping_list_manual_items_id_seq TO cafeteria_backup;',
)
# Exakte Nicht-Owner-ACL (Relation, Grantee, Recht, grantable) nach Migration bzw. Bootstrap.
SHOPPING_LIVE_ACL = frozenset({
    *(
        (table, 'cafeteria_app', privilege, False)
        for table in ('shopping_lists', 'shopping_list_manual_items', 'shopping_list_line_status')
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
    ),
    ('shopping_list_revisions', 'cafeteria_app', 'SELECT', False),
    ('shopping_list_revisions', 'cafeteria_app', 'INSERT', False),
    *((relation, 'cafeteria_backup', 'SELECT', False) for relation in (*SHOPPING_TABLES, *SHOPPING_SEQUENCES)),
})
SHOPPING_SCHEMA_BLOCK = ('-- schema34: shopping lists.\n', '-- schema34: shopping lists end.\n')
SHOPPING_PERMISSIONS_BLOCK = (
    '-- Schema34 shopping list grants begin.\n', '-- Schema34 shopping list grants end.\n',
)
SHOPPING_ROLLBACK_COMMAND = '`APP_IMAGE=<v33-Digest> docker compose up -d --wait --no-deps app`'


def shopping_live_guard_mismatches(connection: Any) -> list[dict[str, object]]:
    """Live-Abweichungen der Schema-34-Schutz-Trigger (tgenabled) und Spalten-ACL (attacl).

    Eigenständig gegen jede Verbindung mit bereits migriertem `cafeteria`-Schema aufrufbar
    (auch mit manipuliertem Zustand für Tests); `run_live_check` ruft dieselbe Funktion
    nach dem frischen Migrationslauf auf.
    """
    from sqlalchemy import text

    mismatches: list[dict[str, object]] = []
    tables = list(SHOPPING_TABLES)
    triggers = connection.execute(
        text(
            '''
            SELECT rel.relname, trg.tgname, trg.tgenabled
            FROM pg_trigger trg
            JOIN pg_class rel ON rel.oid=trg.tgrelid
            WHERE NOT trg.tgisinternal AND rel.relnamespace='cafeteria'::regnamespace
              AND rel.relname=ANY(:tables)
            ORDER BY rel.relname, trg.tgname
            '''
        ),
        {'tables': tables},
    ).tuples().all()
    seen = {name for _, name, _ in triggers}
    for table, name, tgenabled in triggers:
        if name in SHOPPING_TRIGGERS and tgenabled != 'O':
            mismatches.append({
                'object': f'trigger_enabled:{table}.{name}', 'actual': tgenabled, 'expected': 'O',
            })
    for name in sorted(set(SHOPPING_TRIGGERS) - seen):
        table = SHOPPING_TRIGGERS[name][0]
        mismatches.append({
            'object': f'trigger_enabled:{table}.{name}', 'actual': None, 'expected': 'O',
        })
    column_acl = connection.execute(
        text(
            '''
            SELECT c.relname, a.attname, a.attacl::text
            FROM pg_attribute a
            JOIN pg_class c ON c.oid=a.attrelid
            WHERE c.relnamespace='cafeteria'::regnamespace AND c.relname=ANY(:tables)
              AND a.attnum>0 AND NOT a.attisdropped AND a.attacl IS NOT NULL
            ORDER BY c.relname, a.attname
            '''
        ),
        {'tables': tables},
    ).tuples().all()
    for table, column, acl in column_acl:
        mismatches.append({'object': f'column_acl:{table}.{column}', 'actual': acl, 'expected': None})
    return mismatches


def disabled_trigger_mismatches(connection: Any) -> list[dict[str, object]]:
    """Live-Abweichungen: nicht-interne Trigger im Schema cafeteria mit tgenabled <> 'O'.

    Shopping-Trigger werden von shopping_live_guard_mismatches separat geprüft
    (inkl. fehlender Trigger); hier nur die übrigen Schutz-Trigger.
    """
    from sqlalchemy import text

    mismatches: list[dict[str, object]] = []
    disabled = connection.execute(
        text(
            '''
            SELECT rel.relname, trg.tgname, trg.tgenabled
            FROM pg_trigger trg
            JOIN pg_class rel ON rel.oid=trg.tgrelid
            WHERE NOT trg.tgisinternal
              AND rel.relnamespace='cafeteria'::regnamespace
              AND trg.tgenabled <> 'O'
              AND trg.tgname <> ALL(:shopping_triggers)
            ORDER BY rel.relname, trg.tgname
            '''
        ),
        {'shopping_triggers': list(SHOPPING_TRIGGERS)},
    ).tuples().all()
    for table, name, tgenabled in disabled:
        mismatches.append({
            'object': f'trigger_enabled:{table}.{name}',
            'actual': tgenabled,
            'expected': 'O',
        })
    return mismatches


def normalize_sql(value: str) -> str:
    """Whitespace-Läufe zu einem Leerzeichen, keine Leerzeichen an Klammern und Kommas."""
    return re.sub(r' ?([(),]) ?', r'\1', ' '.join(value.split()))


def sql_statements(script: str) -> list[str]:
    """Normalisierte Anweisungen ohne Ganzzeilen-Kommentare; $fn$-Rümpfe bleiben zusammen."""
    body = '\n'.join(line for line in script.splitlines() if not line.lstrip().startswith('--'))
    statements: list[str] = []
    start = index = 0
    while index < len(body):
        if body.startswith('$fn$', index):
            index = body.index('$fn$', index + 4) + 4
            continue
        if body[index] == ';':
            statements.append(normalize_sql(body[start:index + 1]))
            start = index + 1
        index += 1
    if body[start:].strip():
        fail(f'SQL endet ohne Semikolon: {normalize_sql(body[start:])[:80]}')
    return statements


def shopping_ddl_statements(create_table: str) -> list[str]:
    statements = []
    for table in SHOPPING_TABLES:
        items = [source for source, _ in SHOPPING_COLUMNS[table]] + [
            f'CONSTRAINT {name} {source}'
            for (owner, name), (_, source, _) in SHOPPING_CONSTRAINTS.items()
            if owner == table
        ]
        statements.append(f'{create_table} {table} ({", ".join(items)});')
    statements.extend(f'CREATE INDEX {name} {source};' for name, (_, source, _) in SHOPPING_INDEXES.items())

    def trigger(name: str) -> str:
        table, timing, _, level, function = SHOPPING_TRIGGERS[name]
        return f'CREATE TRIGGER {name} {timing} ON {table} FOR EACH {level} EXECUTE FUNCTION {function}();'

    statements.extend(
        trigger(name) for name, spec in SHOPPING_TRIGGERS.items() if spec[4] not in SHOPPING_FUNCTIONS
    )
    for function, body in SHOPPING_FUNCTIONS.items():
        statements.append(
            f'CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql '
            f'SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$ {body}$fn$;'
        )
        statements.extend(trigger(name) for name, spec in SHOPPING_TRIGGERS.items() if spec[4] == function)
    return [normalize_sql(statement) for statement in statements]


def _statement_diff(actual: list[str], expected: list[str]) -> str:
    return json.dumps({
        'unexpected': [statement for statement in actual if statement not in expected],
        'missing': [statement for statement in expected if statement not in actual],
    }, ensure_ascii=False)


def check_shopping_list_artifacts(migration_0031: str, sql: str, permissions: str) -> None:
    ddl = shopping_ddl_statements('CREATE TABLE')
    acl = [normalize_sql(statement) for statement in SHOPPING_ACL_STATEMENTS]
    expected_migration = [
        'BEGIN;', "SET LOCAL lock_timeout = '5s';", normalize_sql('SET search_path TO cafeteria, public;'),
        *ddl, *acl, 'COMMIT;',
    ]
    migration_statements = sql_statements(migration_0031)
    if migration_statements != expected_migration:
        fail('Einkaufslistenvertrag v34 (Migration 0031) weicht ab: '
             + _statement_diff(migration_statements, expected_migration))
    if SHOPPING_ROLLBACK_COMMAND not in migration_0031:
        fail('Einkaufslistenvertrag v34 (Migration 0031) ohne Compose-Rollbackbefehl.')
    for label, text_value, (begin_marker, end_marker), expected in (
        ('schema.sql', sql, SHOPPING_SCHEMA_BLOCK, shopping_ddl_statements('CREATE TABLE IF NOT EXISTS')),
        ('permissions.sql', permissions, SHOPPING_PERMISSIONS_BLOCK, acl),
    ):
        if text_value.count(begin_marker) != 1 or text_value.count(end_marker) != 1:
            fail(f'Einkaufslistenvertrag v34 ({label}) hat keinen eindeutigen Block.')
        prefix, rest = text_value.split(begin_marker, 1)
        block, suffix = rest.split(end_marker, 1)
        if 'shopping_' in prefix or 'shopping_' in suffix:
            fail(f'Einkaufslistenvertrag v34 ({label}) hat Objekte ausserhalb des Blocks.')
        block_statements = sql_statements(block)
        if block_statements != expected:
            fail(f'Einkaufslistenvertrag v34 ({label}) weicht ab: '
                 + _statement_diff(block_statements, expected))


def table_block(sql: str, name: str) -> str:
    match = re.search(
        rf'CREATE TABLE IF NOT EXISTS\s+{re.escape(name)}\s*\((.*?)\n\);',
        sql,
        re.S | re.I,
    )
    if not match:
        fail(f'Tabelle fehlt oder kann nicht gelesen werden: {name}')
    return match.group(1)


def normalize_patient_key(key: str) -> str:
    without_format_chars = ''.join(char for char in key if unicodedata.category(char) != 'Cf')
    return re.sub(r'[^A-Za-z0-9]+', '', without_format_chars).lower()


def patient_key_is_forbidden(key: str) -> bool:
    compact = normalize_patient_key(key)
    return compact not in ALLOWED_PATIENT_COMPACT_KEYS or any(
        token in compact for token in FORBIDDEN_PATIENT_COMPACT_TOKENS
    )


def forbidden_key_paths(value: Any, path: str = '$') -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if patient_key_is_forbidden(key):
                found.append(f'{path}.{key}')
            found.extend(forbidden_key_paths(child, f'{path}.{key}'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_key_paths(child, f'{path}[{index}]'))
    return found


def run_live_check() -> dict[str, Any]:
    database_url = os.getenv('TEST_DATABASE_URL', '').strip()
    if not database_url:
        fail('TEST_DATABASE_URL fehlt für --live.')
    sys.path.insert(0, str(ROOT / 'reference_scaffold'))
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    from cafeteria.db import _execute_script, run_migrations

    catalog_queries = {
        'columns': '''
            SELECT table_name, ordinal_position, column_name, data_type, udt_name,
                   is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema=:schema_name
            ORDER BY table_name, ordinal_position
        ''',
        'constraints': '''
            SELECT rel.relname, con.conname, con.contype, pg_get_constraintdef(con.oid, true)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid=con.conrelid
            JOIN pg_namespace ns ON ns.oid=rel.relnamespace
            WHERE ns.nspname=:schema_name
            ORDER BY rel.relname, con.conname
        ''',
        'indexes': '''
            SELECT tab.relname, idx.relname, pg_get_indexdef(i.indexrelid)
            FROM pg_index i
            JOIN pg_class tab ON tab.oid=i.indrelid
            JOIN pg_class idx ON idx.oid=i.indexrelid
            JOIN pg_namespace ns ON ns.oid=tab.relnamespace
            WHERE ns.nspname=:schema_name
            ORDER BY tab.relname, idx.relname
        ''',
        'functions': '''
            SELECT p.proname, pg_get_function_identity_arguments(p.oid), p.prokind,
                   p.prosecdef, p.proconfig, p.prosrc
            FROM pg_proc p
            JOIN pg_namespace ns ON ns.oid=p.pronamespace
            WHERE ns.nspname=:schema_name
            ORDER BY p.proname, pg_get_function_identity_arguments(p.oid)
        ''',
        'triggers': '''
            SELECT rel.relname, trg.tgname, pg_get_triggerdef(trg.oid, true)
            FROM pg_trigger trg
            JOIN pg_class rel ON rel.oid=trg.tgrelid
            JOIN pg_namespace ns ON ns.oid=rel.relnamespace
            WHERE ns.nspname=:schema_name AND NOT trg.tgisinternal
            ORDER BY rel.relname, trg.tgname
        ''',
        'views': '''
            SELECT viewname, definition FROM pg_views
            WHERE schemaname=:schema_name ORDER BY viewname
        ''',
    }

    def structure(schema_name: str) -> dict[str, list[tuple[Any, ...]]]:
        result: dict[str, list[tuple[Any, ...]]] = {}
        with engine.connect() as connection:
            for name, query in catalog_queries.items():
                rows = connection.execute(text(query), {'schema_name': schema_name}).tuples().all()
                result[name] = [
                    tuple(
                        value.replace(f'{schema_name}.', '<schema>.')
                        if isinstance(value, str)
                        else value
                        for value in row
                    )
                    for row in rows
                ]
        return result

    engine = create_engine(database_url, poolclass=NullPool, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
        run_migrations(engine, SCHEMA)
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    '''
                    SELECT
                        current_setting('server_version') AS server_version,
                        (SELECT max(version) FROM cafeteria.schema_migrations) AS schema_version,
                        (
                            SELECT count(*)
                            FROM pg_proc p
                            JOIN pg_namespace n ON n.oid = p.pronamespace
                            WHERE n.nspname='cafeteria'
                              AND p.proname='validate_publication_revision'
                        ) AS revision_fn_count
                    '''
                )
            ).mappings().one()
            v32_acl = connection.execute(
                text(
                    '''
                    SELECT p.proname, p.prosecdef, p.proconfig,
                           p.proowner=c.relowner AS same_owner,
                           has_function_privilege('cafeteria_app',p.oid,'EXECUTE') AS app,
                           has_function_privilege('cafeteria_backup',p.oid,'EXECUTE') AS backup,
                           has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE') AS issuer,
                           EXISTS(
                               SELECT 1
                               FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) acl
                               WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE'
                           ) AS public
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid=p.pronamespace
                    CROSS JOIN pg_class c
                    WHERE n.nspname='cafeteria'
                      AND c.oid='cafeteria.dish_templates'::regclass
                      AND p.proname IN (
                          'dish_template_mutate_v32',
                          'create_dish_template_v32',
                          'update_dish_template_v32',
                          'reject_direct_dish_template_update_v32'
                      )
                    ORDER BY p.proname
                    '''
                )
            ).mappings().all()
            writer_owners = connection.execute(
                text(
                    '''
                    SELECT p.proname, p.proowner=c.relowner AS owner_matches
                    FROM pg_proc p
                    CROSS JOIN pg_class c
                    WHERE c.oid='cafeteria.dish_templates'::regclass
                      AND p.pronamespace='cafeteria'::regnamespace
                      AND p.proname IN (
                          'dish_template_mutate_v26','dish_template_mutate_v32',
                          'reject_direct_dish_template_update_v32'
                      )
                    ORDER BY p.proname
                    '''
                )
            ).mappings().all()
            guard_contract = connection.execute(
                text(
                    '''
                    SELECT NOT has_table_privilege(
                               'cafeteria_app','cafeteria.dish_templates','UPDATE'
                           ) AS no_table_update,
                           has_column_privilege(
                               'cafeteria_app','cafeteria.dish_templates','id','UPDATE'
                           ) AS lock_column_update,
                           NOT EXISTS (
                               SELECT 1
                               FROM pg_attribute a
                               WHERE a.attrelid='cafeteria.dish_templates'::regclass
                                 AND a.attnum>0
                                 AND NOT a.attisdropped
                                 AND a.attname<>'id'
                                 AND has_column_privilege(
                                     'cafeteria_app',a.attrelid,a.attnum,'UPDATE'
                                 )
                           ) AS no_other_column_update,
                           NOT has_table_privilege(
                               'cafeteria_app','cafeteria.dish_templates',
                               'INSERT,DELETE,TRUNCATE,TRIGGER,REFERENCES'
                           ) AS no_other_dml,
                           t.tgenabled='O' AS trigger_enabled,
                           t.tgtype=18 AS before_statement_update,
                           NOT p.prosecdef AS security_invoker,
                           p.proowner=c.relowner AS owner_matches,
                           p.proconfig=ARRAY['search_path=pg_catalog, cafeteria, pg_temp'] AS safe_path,
                           NOT pg_has_role(
                               'cafeteria_app',c.relowner,'MEMBER'
                           ) AS app_not_owner_member
                    FROM pg_trigger t
                    JOIN pg_proc p ON p.oid=t.tgfoid
                    JOIN pg_class c ON c.oid=t.tgrelid
                    WHERE NOT t.tgisinternal
                      AND c.oid='cafeteria.dish_templates'::regclass
                      AND p.proname='reject_direct_dish_template_update_v32'
                    '''
                )
            ).mappings().one_or_none()
            patient_key_decisions = dict(
                connection.execute(
                    text(
                        '''
                        SELECT key, cafeteria.patient_key_is_forbidden(key)
                        FROM (VALUES
                            ('accompaniment_code'), ('accompaniment_name'),
                            ('accompaniment_price'), ('accompanimentkosten'), ('rappen')
                        ) AS keys(key)
                        '''
                    )
                ).all()
            )
            target_columns = connection.execute(
                text(
                    '''
                    SELECT column_name,data_type,is_nullable,numeric_precision,numeric_scale
                    FROM information_schema.columns
                    WHERE table_schema='cafeteria'
                      AND table_name='menu_item_components'
                      AND column_name IN ('target_quantity','target_quantity_unit_id')
                    ORDER BY ordinal_position
                    '''
                )
            ).tuples().all()
            target_constraints = connection.execute(
                text(
                    '''
                    SELECT con.conname,con.contype,con.confdeltype,
                           con.confrelid::regclass::text,pg_get_constraintdef(con.oid,true)
                    FROM pg_constraint con
                    WHERE con.conrelid='cafeteria.menu_item_components'::regclass
                      AND con.conname IN (
                          'menu_item_components_target_quantity_check',
                          'menu_item_components_target_quantity_unit_id_fkey'
                      )
                    ORDER BY con.conname
                    '''
                )
            ).tuples().all()
            target_indexes = connection.execute(
                text(
                    '''
                    SELECT indexname,indexdef FROM pg_indexes
                    WHERE schemaname='cafeteria' AND tablename='menu_item_components'
                      AND indexname='menu_item_components_target_quantity_unit_idx'
                    '''
                )
            ).tuples().all()
            shopping_parameters = {'tables': list(SHOPPING_TABLES)}
            shopping_columns = connection.execute(
                text(
                    '''
                    SELECT table_name,column_name,data_type,is_nullable,column_default,
                           identity_generation,numeric_precision,numeric_scale
                    FROM information_schema.columns
                    WHERE table_schema='cafeteria' AND table_name=ANY(:tables)
                    ORDER BY table_name,ordinal_position
                    '''
                ),
                shopping_parameters,
            ).tuples().all()
            shopping_constraints = connection.execute(
                text(
                    '''
                    SELECT rel.relname,con.conname,con.contype,pg_get_constraintdef(con.oid,true)
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid=con.conrelid
                    WHERE rel.relnamespace='cafeteria'::regnamespace AND rel.relname=ANY(:tables)
                      AND con.contype<>'n'
                    ORDER BY rel.relname,con.conname
                    '''
                ),
                shopping_parameters,
            ).tuples().all()
            shopping_indexes = connection.execute(
                text(
                    '''
                    SELECT tablename,indexname,indexdef FROM pg_indexes
                    WHERE schemaname='cafeteria' AND tablename=ANY(:tables)
                    ORDER BY tablename,indexname
                    '''
                ),
                shopping_parameters,
            ).tuples().all()
            shopping_triggers = connection.execute(
                text(
                    '''
                    SELECT rel.relname,trg.tgname,pg_get_triggerdef(trg.oid,true)
                    FROM pg_trigger trg
                    JOIN pg_class rel ON rel.oid=trg.tgrelid
                    WHERE NOT trg.tgisinternal AND rel.relnamespace='cafeteria'::regnamespace
                      AND rel.relname=ANY(:tables)
                    ORDER BY rel.relname,trg.tgname
                    '''
                ),
                shopping_parameters,
            ).tuples().all()
            shopping_functions = connection.execute(
                text(
                    '''
                    SELECT p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,
                           p.prokind,p.prosecdef,p.proconfig,p.prosrc,
                           p.prorettype='trigger'::regtype AS returns_trigger,
                           p.proowner=c.relowner AS same_owner,
                           p.proacl IS NOT NULL AND NOT EXISTS (
                               SELECT 1 FROM aclexplode(p.proacl) acl WHERE acl.grantee<>p.proowner
                           ) AS owner_only_acl,
                           has_function_privilege('public',p.oid,'EXECUTE') AS public,
                           has_function_privilege('cafeteria_app',p.oid,'EXECUTE') AS app,
                           has_function_privilege('cafeteria_backup',p.oid,'EXECUTE') AS backup,
                           has_function_privilege('cafeteria_auth_issuer',p.oid,'EXECUTE') AS issuer
                    FROM pg_proc p
                    CROSS JOIN pg_class c
                    WHERE p.pronamespace='cafeteria'::regnamespace AND p.proname LIKE 'shopping%'
                      AND c.oid='cafeteria.shopping_lists'::regclass
                    ORDER BY p.proname
                    '''
                )
            ).mappings().all()
            shopping_relations = connection.execute(
                text(
                    '''
                    SELECT relname,relkind::text FROM pg_class
                    WHERE relnamespace='cafeteria'::regnamespace AND relkind IN ('r','S')
                      AND relname LIKE 'shopping%'
                    ORDER BY relname
                    '''
                )
            ).tuples().all()
            shopping_acl = connection.execute(
                text(
                    '''
                    SELECT rel.relname,COALESCE(role.rolname,'PUBLIC'),acl.privilege_type,acl.is_grantable
                    FROM pg_class rel
                    CROSS JOIN LATERAL aclexplode(rel.relacl) acl
                    LEFT JOIN pg_roles role ON role.oid=acl.grantee
                    WHERE rel.relnamespace='cafeteria'::regnamespace AND rel.relkind IN ('r','S')
                      AND rel.relname LIKE 'shopping%' AND acl.grantee<>rel.relowner
                    '''
                )
            ).tuples().all()
            shopping_guard_mismatches = shopping_live_guard_mismatches(connection)
            disabled_guard_mismatches = disabled_trigger_mismatches(connection)
        if int(row['schema_version']) != 34:
            fail(f"Live-Schema-Version ist {row['schema_version']}, erwartet 34.")
        if int(row['revision_fn_count']) != 1:
            fail('Live-Datenbank hat nicht genau eine validate_publication_revision-Funktion.')
        if {item['proname'] for item in v32_acl} != {
            'dish_template_mutate_v32',
            'create_dish_template_v32',
            'update_dish_template_v32',
            'reject_direct_dish_template_update_v32',
        }:
            fail('Live-Datenbank hat nicht genau die vier Vorlagenfunktionen v32.')
        for item in v32_acl:
            is_guard = item['proname'] == 'reject_direct_dish_template_update_v32'
            expected_app = item['proname'] in {
                'create_dish_template_v32', 'update_dish_template_v32',
            }
            if (
                item['prosecdef'] == is_guard
                or not item['same_owner']
                or item['proconfig'] != ['search_path=pg_catalog, cafeteria, pg_temp']
                or item['app'] != expected_app
                or item['backup']
                or item['issuer']
                or item['public']
            ):
                fail(f"Live-ACL der Vorlagenfunktion ist ungültig: {item['proname']}")
        if {item['proname'] for item in writer_owners} != {
            'dish_template_mutate_v26',
            'dish_template_mutate_v32',
            'reject_direct_dish_template_update_v32',
        } or not all(item['owner_matches'] for item in writer_owners):
            fail('Live-Owner der Vorlagen-Schreibfunktionen ist ungültig.')
        if guard_contract is None:
            fail('Live-Owner-Guard für dish_templates fehlt.')
        if not all(guard_contract.values()):
            fail('Live-ACL oder Owner-Guard für dish_templates ist ungültig.')
        if patient_key_decisions != {
            'accompaniment_code': False,
            'accompaniment_name': False,
            'accompaniment_price': True,
            'accompanimentkosten': True,
            'rappen': True,
        }:
            fail('Live-Patientenschlüsselvertrag für Beilagen ist ungültig.')
        if target_columns != [
            ('target_quantity', 'numeric', 'YES', 18, 6),
            ('target_quantity_unit_id', 'bigint', 'YES', 64, 0),
        ]:
            fail('Live-Spaltenvertrag für Zielmengen ist ungültig.')
        target_constraints_by_name = {item[0]: item[1:] for item in target_constraints}
        if set(target_constraints_by_name) != {
            'menu_item_components_target_quantity_check',
            'menu_item_components_target_quantity_unit_id_fkey',
        }:
            fail('Live-Constraints für Zielmengen fehlen.')
        target_fk = target_constraints_by_name['menu_item_components_target_quantity_unit_id_fkey']
        target_fk_def = re.sub(r'\s+', ' ', target_fk[3]).strip()
        if target_fk_def != 'FOREIGN KEY (target_quantity_unit_id) REFERENCES cafeteria.measurement_units(id) ON DELETE RESTRICT':
            fail(f'Live-FK für Zielmengeneinheit ist ungültig: {target_fk_def}')
        target_check_def = ''.join(target_constraints_by_name['menu_item_components_target_quantity_check'][3].split()).lower()
        if target_check_def not in (
            'check(target_quantityisnullandtarget_quantity_unit_idisnullortarget_quantityisnotnullandtarget_quantity_unit_idisnotnullandtarget_quantity>0::numericandrecipe_revision_idisnotnull)',
            'check(((target_quantityisnull)and(target_quantity_unit_idisnull))or((target_quantityisnotnull)and(target_quantity_unit_idisnotnull)and(target_quantity>0::numeric)and(recipe_revision_idisnotnull)))'
        ):
            fail(f'Live-CHECK für Zielmengen ist ungültig: {target_check_def}')
        if (
            len(target_indexes) != 1
            or '(target_quantity_unit_id)' not in target_indexes[0][1]
            or 'WHERE (target_quantity_unit_id IS NOT NULL)' not in target_indexes[0][1]
        ):
            fail('Live-Index für Zielmengeneinheit ist ungültig.')
        shopping_mismatches: list[object] = []

        def expect(label: str, actual: object, expected: object) -> None:
            if actual == expected:
                return
            if isinstance(actual, dict) and isinstance(expected, dict):
                for key in sorted(set(actual) | set(expected)):
                    if actual.get(key) != expected.get(key):
                        shopping_mismatches.append({
                            'object': f'{label}:{key}', 'actual': actual.get(key), 'expected': expected.get(key),
                        })
                return
            shopping_mismatches.append({'object': label, 'actual': actual, 'expected': expected})

        for table_name in SHOPPING_TABLES:
            expect(
                f'columns:{table_name}',
                [list(item[1:]) for item in shopping_columns if item[0] == table_name],
                [[source.split()[0], *live] for source, live in SHOPPING_COLUMNS[table_name]],
            )
        expect(
            'constraints',
            {f'{table}.{name}': [contype, condef] for table, name, contype, condef in shopping_constraints},
            {f'{table}.{name}': [contype, live] for (table, name), (contype, _, live) in SHOPPING_CONSTRAINTS.items()},
        )
        # Indexmenge exakt: PK-/UNIQUE-Indizes (Definition über die Constraints geprüft) plus
        # die expliziten Indizes mit exakter Definition.
        expect(
            'index names',
            sorted(f'{table}.{name}' for table, name, _ in shopping_indexes),
            sorted([
                *(
                    f'{table}.{name}'
                    for (table, name), (contype, _, _) in SHOPPING_CONSTRAINTS.items()
                    if contype in ('p', 'u')
                ),
                *(f'{table}.{name}' for name, (table, _, _) in SHOPPING_INDEXES.items()),
            ]),
        )
        expect(
            'indexes',
            {name: indexdef for _, name, indexdef in shopping_indexes if name in SHOPPING_INDEXES},
            {name: f'CREATE INDEX {name} {live}' for name, (_, _, live) in SHOPPING_INDEXES.items()},
        )
        expect(
            'triggers',
            {f'{table}.{name}': triggerdef for table, name, triggerdef in shopping_triggers},
            {
                f'{table}.{name}': (
                    f'CREATE TRIGGER {name} {timing} ON cafeteria.{table} '
                    f'FOR EACH {level} EXECUTE FUNCTION cafeteria.{function}()'
                )
                for name, (table, _, timing, level, function) in SHOPPING_TRIGGERS.items()
            },
        )
        expect(
            'functions',
            {
                item['proname']: {
                    'arguments': item['arguments'], 'prokind': item['prokind'],
                    'security_definer': item['prosecdef'], 'config': item['proconfig'],
                    'source': normalize_sql(item['prosrc']), 'returns_trigger': item['returns_trigger'],
                    'same_owner': item['same_owner'], 'owner_only_acl': item['owner_only_acl'],
                    'execute': [item['public'], item['app'], item['backup'], item['issuer']],
                }
                for item in shopping_functions
            },
            {
                name: {
                    'arguments': '', 'prokind': 'f', 'security_definer': False,
                    'config': ['search_path=pg_catalog, cafeteria, pg_temp'],
                    'source': normalize_sql(body), 'returns_trigger': True, 'same_owner': True,
                    'owner_only_acl': True, 'execute': [False, False, False, False],
                }
                for name, body in SHOPPING_FUNCTIONS.items()
            },
        )
        expect(
            'relations',
            sorted([name, kind] for name, kind in shopping_relations),
            sorted(
                [*([name, 'r'] for name in SHOPPING_TABLES), *([name, 'S'] for name in SHOPPING_SEQUENCES)]
            ),
        )
        expect(
            'acl',
            sorted(list(item) for item in shopping_acl),
            sorted(list(item) for item in SHOPPING_LIVE_ACL),
        )
        shopping_mismatches.extend(shopping_guard_mismatches)
        if shopping_mismatches:
            fail('Live-Einkaufslistenvertrag v34 ist ungültig: '
                 + json.dumps(shopping_mismatches, ensure_ascii=False, default=str))
        if disabled_guard_mismatches:
            fail('Live-Schutz-Trigger sind deaktiviert: '
                 + json.dumps(disabled_guard_mismatches, ensure_ascii=False, default=str))
        migrated_structure = structure('cafeteria')
        with engine.begin() as connection:
            connection.execute(text('ALTER SCHEMA cafeteria RENAME TO cafeteria_migrated_contract'))
        _execute_script(engine, str(SCHEMA))
        baseline_structure = structure('cafeteria')
        for object_type, expected in migrated_structure.items():
            actual = baseline_structure[object_type]
            if actual != expected:
                fail(f'Schema-Baseline weicht bei {object_type} vom Migrationsergebnis ab.')
        return {
            'live_postgresql_executed': True,
            'server_version': row['server_version'],
            'live_schema_version': int(row['schema_version']),
            'baseline_migration_equivalent': True,
        }
    finally:
        with engine.begin() as connection:
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))
            connection.execute(text('DROP SCHEMA IF EXISTS cafeteria_migrated_contract CASCADE'))
        engine.dispose()


def validate_snapshots() -> tuple[dict[str, Any], dict[str, Any]]:
    caf = json.loads(CAF_JSON.read_text(encoding='utf-8'))
    pat = json.loads(PAT_JSON.read_text(encoding='utf-8'))

    if caf.get('profile_code') != 'staff_guest':
        fail('Cafeteria-Snapshot hat falsches Profil.')
    if pat.get('profile_code') != 'patient':
        fail('Patienten-Snapshot hat falsches Profil.')
    if len(caf.get('days', [])) != 7 or len(pat.get('days', [])) != 7:
        fail('Beide Snapshots müssen sieben Kalendertage enthalten.')

    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    for snapshot in (caf, pat):
        week_start = date.fromisoformat(snapshot['week_start'])
        if snapshot.get('week_end') != (week_start + timedelta(days=6)).isoformat():
            fail('Snapshot-Wochenende stimmt nicht mit week_start überein.')
        for index, day in enumerate(snapshot['days']):
            if day.get('date') != (week_start + timedelta(days=index)).isoformat():
                fail('Snapshot-Kalendertage sind nicht lückenlos.')
            if day.get('weekday') != weekdays[index]:
                fail(f"Falscher Wochentag für {day.get('date')}.")

    caf_services = [service for day in caf['days'] for service in day.get('services', [])]
    if len(caf_services) != 5:
        fail(f'Cafeteria-Snapshot hat {len(caf_services)} statt fünf Werktage.')
    if any(service.get('meal_code') != 'LUNCH' for service in caf_services):
        fail('Cafeteria-Snapshot enthält eine andere Mahlzeit als LUNCH.')
    if any(len(service.get('options', [])) != 2 for service in caf_services):
        fail('Cafeteria-Service ohne genau zwei Menükarten.')
    for service in caf_services:
        if {option.get('type_code') for option in service.get('options', [])} != {'MENU_1', 'VEGGIE'}:
            fail('Cafeteria-Service ohne exakt MENU_1 und VEGGIE.')
        for option in service['options']:
            costs = option.get('prices')
            if not isinstance(costs, dict) or set(costs) != {'internal_rappen', 'external_rappen', 'currency'}:
                fail('Cafeteria-Menü ohne vollständige interne/externe Kostenstruktur.')
            if type(costs.get('internal_rappen')) is not int or type(costs.get('external_rappen')) is not int:
                fail('Cafeteria-Rappen müssen JSON-Ganzzahlen sein.')

    bad_paths = forbidden_key_paths(pat)
    if bad_paths:
        fail('Patienten-Snapshot enthält Kosten-Schlüssel: ' + ', '.join(bad_paths[:8]))
    patient_text = json.dumps(pat, ensure_ascii=False)
    for token in ('CHF', '0.00', 'Mitarbeitende 11.00', 'Externe 16.60'):
        if token.lower() in patient_text.lower():
            fail(f'Patienten-Snapshot enthält unzulässigen Inhalt: {token}')
    for day in pat['days']:
        services = day.get('services', [])
        if {service.get('meal_code') for service in services} != {'LUNCH', 'DINNER'}:
            fail(f"Patiententag {day.get('date')} hat nicht Mittag und Abend.")
        if any(len(service.get('options', [])) != 2 for service in services):
            fail(f"Patiententag {day.get('date')} hat keine zwei Optionen je Mahlzeit.")
        if any(
            {option.get('type_code') for option in service.get('options', [])} != {'MENU_1', 'VEGGIE'}
            for service in services
        ):
            fail(f"Patiententag {day.get('date')} hat nicht exakt MENU_1 und VEGGIE.")

    return caf, pat


def main() -> int:
    try:
        sql = SCHEMA.read_text(encoding='utf-8')
        migration_0002 = MIGRATION_0002.read_text(encoding='utf-8')
        migration_0003 = MIGRATION_0003.read_text(encoding='utf-8')
        migration_0005 = MIGRATION_0005.read_text(encoding='utf-8')
        migration_0006 = MIGRATION_0006.read_text(encoding='utf-8')
        migration_0007 = MIGRATION_0007.read_text(encoding='utf-8')
        migration_0008 = MIGRATION_0008.read_text(encoding='utf-8')
        migration_0010 = MIGRATION_0010.read_text(encoding='utf-8')
        migration_0011 = MIGRATION_0011.read_text(encoding='utf-8')
        migration_0012 = MIGRATION_0012.read_text(encoding='utf-8')
        migration_0013 = MIGRATION_0013.read_text(encoding='utf-8')
        migration_0014 = MIGRATION_0014.read_text(encoding='utf-8')
        migration_0015 = MIGRATION_0015.read_text(encoding='utf-8')
        migration_0016 = MIGRATION_0016.read_text(encoding='utf-8')
        migration_0017 = MIGRATION_0017.read_text(encoding='utf-8')
        migration_0018 = MIGRATION_0018.read_text(encoding='utf-8')
        migration_0020 = MIGRATION_0020.read_text(encoding='utf-8')
        migration_0024 = MIGRATION_0024.read_text(encoding='utf-8')
        migration_0028 = MIGRATION_0028.read_text(encoding='utf-8')
        if not migration_0028.startswith('BEGIN;') or not migration_0028.rstrip().endswith('COMMIT;'):
            fail('Migration 0028 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('lock_menu_recipe_sources_v31', 'UNION SELECT v_source',
                         'cafeteria.begin_menu_binding_write_v26(p_actor,p_authz,p_location)',
                         'h.id=v_source AND h.public_id=p_source AND h.location_id=p_location'):
            if fragment not in migration_0028 or fragment not in sql:
                fail(f'Menü-Quellrezept-Sperrvertrag fehlt: {fragment}')
        migration_0029 = MIGRATION_0029.read_text(encoding='utf-8')
        migration_0030 = MIGRATION_0030.read_text(encoding='utf-8')
        migration_0031 = MIGRATION_0031.read_text(encoding='utf-8')
        permissions = PERMISSIONS.read_text(encoding='utf-8')
        if not migration_0029.startswith('BEGIN;') or not migration_0029.rstrip().endswith('COMMIT;'):
            fail('Migration 0029 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in (
            'menu_items_accompaniment_check',
            'dish_templates_accompaniment_default_check',
            "accompaniment IN ('none', 'soup', 'salad')",
            "accompaniment_default IN ('none', 'soup', 'salad')",
            'dish_template_mutate_v32',
            'create_dish_template_v32',
            'update_dish_template_v32',
            'reject_direct_dish_template_update_v32',
            'CREATE TRIGGER dish_templates_owner_update_v32',
            'current_user IS DISTINCT FROM v_table_owner',
            "USING ERRCODE='42501'",
            'FOR EACH STATEMENT EXECUTE FUNCTION',
            "'accompaniment_default',v.accompaniment_default",
            "'accompanimentcode'",
            "'accompanimentname'",
        ):
            if fragment not in migration_0029 or fragment not in sql:
                fail(f'Beilagenvertrag v32 fehlt: {fragment}')
        if (
            'BEFORE UPDATE ON cafeteria.dish_templates' not in migration_0029
            or 'BEFORE UPDATE ON dish_templates' not in sql
        ):
            fail('Beilagenvertrag v32 fehlt: BEFORE UPDATE.')
        for fragment in (
            'REVOKE INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES',
            'GRANT UPDATE(id) ON TABLE cafeteria.dish_templates TO cafeteria_app',
        ):
            if fragment not in migration_0029:
                fail(f'Beilagen-Migrations-ACL v32 fehlt: {fragment}')
        for fragment in (
            'REVOKE INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES',
            'GRANT UPDATE (id) ON dish_templates TO cafeteria_app',
            'reject_direct_dish_template_update_v32()',
        ):
            if fragment not in permissions:
                fail(f'Beilagen-ACL v32 fehlt: {fragment}')
        mig_30_lines = [line.strip() for line in migration_0030.splitlines() if line.strip() and not line.strip().startswith('--')]
        if not mig_30_lines or mig_30_lines[0] != 'BEGIN;' or not migration_0030.rstrip().endswith('COMMIT;'):
            fail('Migration 0030 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        m30_norm = ''.join(migration_0030.split()).lower()
        sql_norm = ''.join(sql.split()).lower()
        if 'target_quantity_unit_idbigintreferencescafeteria.measurement_units(id)ondeleterestrict' not in m30_norm:
            fail('Zielmengenvertrag v33 (FK) fehlt in Migration 0030.')
        if 'target_quantity_unit_idbigintreferencesmeasurement_units(id)ondeleterestrict' not in sql_norm:
            fail('Zielmengenvertrag v33 (FK) fehlt in schema.sql.')
        check_str = 'check((target_quantityisnullandtarget_quantity_unit_idisnull)or(target_quantityisnotnullandtarget_quantity_unit_idisnotnullandtarget_quantity>0andrecipe_revision_idisnotnull))'
        if check_str not in m30_norm:
            fail('Zielmengenvertrag v33 (CHECK) fehlt in Migration 0030.')
        if check_str not in sql_norm:
            fail('Zielmengenvertrag v33 (CHECK) fehlt in schema.sql.')
        for fragment in (
            'target_quantity numeric(18,6)',
            'target_quantity_unit_id bigint',
            'menu_item_components_target_quantity_check',
            'menu_item_components_target_quantity_unit_idx',
        ):
            if fragment not in migration_0030 or fragment not in sql:
                fail(f'Zielmengenvertrag v33 fehlt: {fragment}')
        mig_31_lines = [line.strip() for line in migration_0031.splitlines() if line.strip() and not line.strip().startswith('--')]
        if not mig_31_lines or mig_31_lines[0] != 'BEGIN;' or not migration_0031.rstrip().endswith('COMMIT;'):
            fail('Migration 0031 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        check_shopping_list_artifacts(migration_0031, sql, permissions)
        migration_0026 = MIGRATION_0026.read_text(encoding='utf-8')
        if not migration_0026.startswith('BEGIN;') or not migration_0026.rstrip().endswith('COMMIT;'):
            fail('Migration 0026 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('commit_recipe_import_batch_v29', 'create_recipe_v22',
                         'require_master_data_actor(p_actor,p_authz,\'recipe.import\')',
                         'imported_result'):
            if fragment not in migration_0026 or fragment not in sql:
                fail(f'Import-Commit-Vertrag fehlt: {fragment}')
        if not migration_0024.startswith('BEGIN;') or not migration_0024.rstrip().endswith('COMMIT;'):
            fail('Migration 0024 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('foods_prepared_recipe_scope_fk', 'food_storage_preflight', 'foods_complete_v27',
                         'create_food_v27', 'update_food_v27', 'recipe_dependency_preview_v27', 'freeze_recipe_v27',
                         'lock_prepared_graph_v27', 'check_prepared_graph_v27', 'check_prepared_snapshot_v27'):
            if fragment not in migration_0024 or fragment not in sql:
                fail(f'Vertrag für vorbereitete Zutaten fehlt: {fragment}')
        migration_0023 = MIGRATION_0023.read_text(encoding='utf-8')
        if not migration_0023.startswith('BEGIN;') or not migration_0023.rstrip().endswith('COMMIT;'):
            fail('Migration 0023 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('menu_components_food_scope_fk', 'recipe_revision_id', 'validate_menu_recipe_scope_v26',
                         'validate_dish_recipe_scope_v26', 'validate_menu_dish_scope_v26',
                         'begin_menu_binding_write_v26', 'lock_menu_recipe_revisions_v26',
                         'lock_component_foods_v26', 'record_menu_binding_write_v26',
                         'record_component_food_write_v26', 'audit_binding_entity_version_v26',
                         'create_dish_template_v26', 'update_dish_template_v26', 'set_dish_template_active_v26'):
            if fragment not in migration_0023 or fragment not in sql:
                fail(f'Rezeptbindungsvertrag fehlt: {fragment}')
        migration_0022 = MIGRATION_0022.read_text(encoding='utf-8')
        if not migration_0022.startswith('BEGIN;') or not migration_0022.rstrip().endswith('COMMIT;'):
            fail('Migration 0022 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('record_auth_access_v25', 'auth.login.accepted', 'auth.login.rejected',
                         'auth.login.unavailable', 'auth.logout.requested', 'auth.frontchannel.requested',
                         "'authentication'", "ERRCODE='P2501'", 'v_existing.details IS DISTINCT FROM v_details'):
            if fragment not in migration_0022 or fragment not in sql:
                fail(f'Authentifizierungsereignis-Vertrag fehlt: {fragment}')
        if not migration_0020.startswith('BEGIN;') or not migration_0020.rstrip().endswith('COMMIT;'):
            fail('Migration 0020 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('activate_screen_assignment_v23', 'screen_assignment.activate',
                         'lock_operations_actor(p_actor,p_authz)', "ERRCODE='P2004'"):
            if fragment not in migration_0020 or fragment not in sql:
                fail(f'Screen-Zuordnungsvertrag fehlt: {fragment}')
        migration_0019 = MIGRATION_0019.read_text(encoding='utf-8')
        if not migration_0019.startswith('BEGIN;') or not migration_0019.rstrip().endswith('COMMIT;'):
            fail('Migration 0019 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('line_public_id', 'recipe_protect_v22', 'recipe_snapshot_v22',
                         'create_recipe_v22', 'freeze_recipe_revision_v22', 'add_recipe_image_v22',
                         'replace_cookbook_recipes_v22'):
            if fragment not in migration_0019 or fragment not in sql:
                fail(f'Rezeptvertrag fehlt: {fragment}')
        if not migration_0018.startswith('BEGIN;') or not migration_0018.rstrip().endswith('COMMIT;'):
            fail('Migration 0018 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('master_factor', 'master_quantity', 'require_master_data_actor',
                         'protect_food_proposal', 'master_lock_food_refs', 'master_audit',
                         'SELECT * INTO v FROM users WHERE id=p_actor FOR SHARE',
                         "'masterdata.write'", "'recipe.import'", 'food_storage_locations',
                         'accept_proposal_v21', 'reject_proposal_v21'):
            if fragment not in migration_0018 or fragment not in sql:
                fail(f'Stammdaten-Vertrag fehlt: {fragment}')
        for fragment in ('menu_services_time_window_check', 'offer_profiles_display_name_check',
                         'GRANT UPDATE (display_name, allows_weekend) ON offer_profiles TO cafeteria_app',
                         'offer_profiles_profile_contract_check',
                         'lock_operations_actor(p_actor bigint, p_actor_version bigint)',
                         'ORDER BY role_code FOR SHARE',
                         'WHERE id=p_actor ORDER BY id FOR UPDATE',
                         'Cafeteria-Wochenende erlaubt höchstens einen Mittagsservice.',
                         'Kosten sind nur im Cafeteria-Mittag zulässig.',
                         "'servicestart', 'serviceend', 'areaname'",
                         'jsonb_strip_nulls(jsonb_build_object(',
                         "to_char(s.service_start, 'HH24:MI')",
                         "to_char(s.service_end, 'HH24:MI')"):
            if fragment not in migration_0017 or fragment not in sql:
                fail(f'Betriebszeiten-Vertrag fehlt: {fragment}')
        if not migration_0017.startswith('BEGIN;') or not migration_0017.rstrip().endswith('COMMIT;'):
            fail('Migration 0017 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('local_user_command_context_v19(bigint,text,uuid,text)',
                         'create_local_user_v19(bigint,bigint,text,text,text,text[])',
                         'replace_local_roles_v19(bigint,bigint,uuid,bigint,text[])',
                         'reset_local_password_v19(bigint,bigint,uuid,bigint,text)',
                         'deactivate_local_user_v19(bigint,bigint,uuid,bigint)',
                         'reactivate_local_user_v19(bigint,bigint,uuid,bigint)',
                         'require_remaining_local_admin_v19', 'trg_audit_events_immutable',
                         'trg_audit_events_no_truncate', '2903847293::bigint',
                         "current_setting('transaction_isolation') <> 'read committed'"):
            if fragment not in migration_0016 or fragment not in sql:
                fail(f'Lokaler IAM-Vertrag fehlt: {fragment}')
        if not migration_0016.startswith('BEGIN;') or not migration_0016.rstrip().endswith('COMMIT;'):
            fail('Migration 0016 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('branding_assets', 'pg_catalog.sha256(png_data)', '1048576',
                         'GRANT SELECT, INSERT ON branding_assets TO cafeteria_app',
                         'GRANT SELECT ON branding_assets TO cafeteria_backup'):
            if fragment not in migration_0015 or fragment not in sql:
                fail(f'Marken-Asset-Vertrag fehlt: {fragment}')
        if not migration_0015.startswith('BEGIN;') or not migration_0015.rstrip().endswith('COMMIT;'):
            fail('Migration 0015 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        for fragment in ('header_revision', 'record_menu_review', 'record_week_context_review',
                         'require_workflow_review_actor', 'uq_workflow_review_submission'):
            if fragment not in migration_0013 or fragment not in sql:
                fail(f'Prüfbeleg-Vertrag fehlt: {fragment}')
        for fragment in ('api_keys', 'create_api_key', 'revoke_api_key', 'require_api_key_admin'):
            if fragment not in migration_0014 or fragment not in sql:
                fail(f'API-Schlüssel-Vertrag fehlt: {fragment}')
        if not migration_0014.startswith('BEGIN;') or not migration_0014.rstrip().endswith('COMMIT;'):
            fail('Migration 0014 hat keinen strikten BEGIN/COMMIT-Vertrag.')
        seed = SEED.read_text(encoding='utf-8')
        immutable_migration_checksums = {
            MIGRATION_0001: 'd1001f657858b4fec9a466517bf4117add8b28160dda7aebf7c43c21e6e6fff0',
            MIGRATION_0002: '7f8696eb886a99d841ac82be1e4b3abf1b51080c18aac07ea5290325f3e5e863',
            MIGRATION_0003: 'eda9c5e851525367af62a3f056b3592a521d871f6ac818d4d50c18d8f720d1de',
            MIGRATION_0004: '7309069f1b52d41a756a315af8b6ccf0771afe113875a6c5f82d42775f74b066',
            MIGRATION_0005: 'b33bdfebe621adfca3da98c85a1b0e8316040c55cf62542eda138099362f1818',
            MIGRATION_0006: '60897aea8c7096f449a43a6cd2b79452f943cbbec75cc74a0bcf4514baaac233',
            MIGRATION_0007: 'a25d5b6ca71bc11c582eef6e90f792979a88aa86dcc444b7b1ab1db90967595f',
            MIGRATION_0008: '4311165d2dcd763cf9a462906d044000956eb11d16ac847ecf9351facae21e45',
            MIGRATION_0009: '1b988c75b7ef3f333045d738fa29cd210a367eeaf30825a3005873cafc3b65ed',
            MIGRATION_0010: 'dba21c2ba10406985a0069d193e1f08e65aaa9c0a27b04102b2626003d83dd8f',
            MIGRATION_0011: '75c6d6cc777f1dbf3d2bb914688b8ff9529ddca51fc9250ea91170b5482d0953',
            MIGRATION_0012: '3ff265067a1119f927d995251386a58ba648c4f26f9d4ff6059cce4d97bb9140',
            MIGRATION_0013: 'f1582e226ee1150bfc83c31427ae08fc82f3f939809fa588f53d0e1532c2219a',
            MIGRATION_0014: 'd767c2446e6cfab10daf073056ec1f9a9570293e76ee0a8f9638036f5460dae0',
            MIGRATION_0015: 'da49d671a6dbfef768330a894f217f5ec4d37addf9bd3c2064ae60a815f8ac9e',
            MIGRATION_0016: 'e195aac3c6b53fb08f733723cd8ef12e6e40fb7abdc5fe58bf1f88585015c6c1',
            MIGRATION_0017: '186422d38d9094751f4a55086876bbdada32d8b16b4deed758ab3446eec03228',
            MIGRATION_0018: '34c27cf999fef7c50e8a1a8b50f9f1c94d2d2ac1bb2a4b31fb13f109482b1c01',
            MIGRATION_0019: 'e23a1dbef11dd81a57476af148fdcaf2a8ee18f88a26f0dcd2d30e428ed5f349',
            MIGRATION_0020: '996ae384a0c589b98429f8f520cf175631c17557ffe74221e9f46dd144e7771f',
            MIGRATION_0021: 'fc91851728fc7257cfa0ae098b8d9c94575f2ecd42f0568146e188514dfd13f6',
            MIGRATION_0022: '33d2bb0e556c9065f2cde096a9f58482cdd40f5e2fb7b56b331d4e9d8a402a07',
            MIGRATION_0023: '24ac85b6833ac03b04a18eec238dde2bab1a51403f48b3baf7a9f56ac290cc58',
            MIGRATION_0024: '5503b214a9957a09345d3301526797ca8fa2deb146fd6bdced6875ebd86635f2',
            MIGRATION_0025: '136dbf46688490a46018d158acbe11a89fbd186164659c145e256f92df69399c',
            MIGRATION_0026: '9740215a04c93a3093543c585c8c0c700eae625f5b94837527f9da97f9259259',
            MIGRATION_0027: '410374a06b46f45c3578dc4cd114e32af71ff7a2649d65a4273c976148b0c05b',
            MIGRATION_0028: 'd8ab456b75926a21088680bb8b1c8cfcf7a1966b4b2de2e8dae48ded7593bb4d',
            MIGRATION_0029: '55c703040fe2461654d869be983548bf6d1c40ce5ce769c3dedddaf6146dd2da',
            MIGRATION_0030: 'df6363e0d5539afa0cc67bed192e32d1bcb38a8f531bd2ebc28835118c7a32c2',
            MIGRATION_0031: '3aeb090c46b080a65eb0d4c548b982f05eadca6807c0e8ede3f772d0f88f4a3c',
        }
        for migration_path, expected_checksum in immutable_migration_checksums.items():
            actual_checksum = hashlib.sha256(migration_path.read_bytes()).hexdigest()
            if actual_checksum != expected_checksum:
                fail(f'{migration_path.name} wurde nachträglich verändert.')
        baseline_checksum = immutable_migration_checksums[MIGRATION_0001]

        tables = re.findall(r'^CREATE TABLE IF NOT EXISTS\s+([a-z_]+)', sql, re.M | re.I)
        required_tables = {
            'offer_profiles', 'menu_weeks', 'menu_services', 'menu_items',
            'menu_item_prices', 'publication_revisions', 'publication_lifecycle_events',
            'audit_events', 'local_credentials', 'auth_capability_secrets', 'auth_capability_nonces',
            'menu_components', 'component_allergens', 'component_labels',
            'api_keys', 'branding_assets',
            'measurement_units', 'food_categories', 'foods', 'tags', 'food_tags',
            'food_labels', 'food_allergens', 'storage_locations',
            'food_storage_locations', 'food_data_proposals',
            'recipes', 'recipe_ingredients', 'recipe_steps', 'recipe_tags', 'recipe_images',
            'recipe_assets', 'recipe_revisions', 'cookbooks', 'cookbook_recipes',
            'recipe_import_batches', 'recipe_import_candidates',
            'shopping_lists', 'shopping_list_revisions', 'shopping_list_manual_items',
            'shopping_list_line_status',
        }
        missing = required_tables - set(tables)
        if missing:
            fail('Pflichttabellen fehlen: ' + ', '.join(sorted(missing)))

        for fragment in (
            "code IN ('patient', 'staff_guest')",
            "code IN ('LUNCH', 'DINNER')",
            'validate_menu_service()',
            'validate_menu_item_price()',
            'validate_publication_revision()',
            'jsonb_has_patient_forbidden_key',
            'uq_publication_one_active_per_profile_week',
            'CREATE OR REPLACE VIEW active_publications',
            'authz_version',
            'protect_publication_revision()',
            'publication_lifecycle_events',
            'validate_menu_week()',
            'r.profile_id',
            "w.workflow_state = 'published'",
            'withdraw_publication_revision',
            'issue_publication_capability',
            'auth_capability_secrets',
            'FOR UPDATE OF w',
            'patient_key_is_forbidden',
            'withdrawn_by',
            'sync_entra_user',
            'ensure_auth_capability_state',
            'hard_reset_auth_capability_state',
            "interval '15 minutes'",
            'provision_local_user',
            'set_local_password',
            'disable_local_user',
            'record_local_login_lock',
            'trg_local_credentials_login_lock_audit',
            'REVOKE ALL ON SCHEMA cafeteria',
            'REVOKE CREATE ON SCHEMA public FROM PUBLIC',
            "profile_scope IN ('common', 'patient', 'staff_guest')",
            "category IN ('meat', 'side', 'vegetable', 'sauce', 'dessert', 'other')",
            'uq_menu_components_location_scope_name',
            "allergen_mode IN ('auto', 'manual')",
            "origin_mode IN ('auto', 'manual')",
            "label_mode IN ('auto', 'manual')",
            'lock_component_metadata_masters',
            'lock_expected_active_location',
            'lock_active_publication',
            'ORDER BY role_code',
            'SET search_path = pg_catalog, cafeteria, pg_temp',
            'create_recipe_import_batch_v28',
            'update_recipe_import_batch_v28',
            'commit_recipe_import_batch_v29',
            'recipe_import_batches',
            'recipe_import_candidates',
            'imported_result',
        ):
            if fragment not in sql:
                fail(f'Pflichtfragment fehlt: {fragment}')
        if sql.count('CREATE OR REPLACE FUNCTION validate_publication_revision()') != 1:
            fail('validate_publication_revision muss genau einmal definiert sein.')

        for fragment in (
            'CREATE TABLE IF NOT EXISTS local_credentials',
            'jsonb_has_patient_forbidden_value',
            'trg_publication_immutable',
            "workflow_state <> 'published'",
            'publication_lifecycle_events',
            'v4-Entwurf darf nicht öffentlich bleiben',
            'JSON-Ganzzahlen',
            'validate_menu_week()',
        ):
            if fragment not in migration_0002:
                fail(f'Pflichtfragment in 0002 fehlt: {fragment}')

        for fragment in (
            'normalize_patient_key',
            'withdraw_publication_revision',
            'withdrawn_by',
            'Publikationsrevision kann nicht zurückgestuft werden',
            'SECURITY DEFINER',
        ):
            if fragment not in migration_0003:
                fail(f'Pflichtfragment in 0003 fehlt: {fragment}')

        migration_0004 = MIGRATION_0004.read_text(encoding='utf-8')
        for fragment in (
            'auth_capability_secrets',
            'issue_publication_capability',
            'public.hmac',
            'FOR UPDATE OF w',
            'patient_key_is_forbidden',
            '[^A-Za-z0-9]+',
            'Capability-Nonce wurde bereits verwendet',
        ):
            if fragment not in migration_0004:
                fail(f'Pflichtfragment in 0004 fehlt: {fragment}')

        for fragment in (
            'sync_entra_user',
            'ensure_auth_capability_state',
            'hard_reset_auth_capability_state',
            "interval '15 minutes'",
            'authz_version darf nicht zurückgesetzt werden',
            'REVOKE ALL ON cafeteria.users',
            'cafeteria.auth_capability_secrets',
        ):
            if fragment not in migration_0005:
                fail(f'Pflichtfragment in 0005 fehlt: {fragment}')

        for fragment in (
            'cafeteria_auth_issuer',
            'provision_local_user',
            'set_local_password',
            'disable_local_user',
            'sync_entra_user',
            'issue_publication_capability',
            'REVOKE ALL ON ALL TABLES',
            'Lokale Rollenliste enthält unbekannte, inaktive oder doppelte Rollen',
            'auth.local_role_granted',
            'auth.local_password_changed',
            'auth.local_user_disabled',
        ):
            if fragment not in migration_0006:
                fail(f'Pflichtfragment in 0006 fehlt: {fragment}')

        for fragment in (
            'Rolle cafeteria_auth_issuer muss vor Migration 0007 provisioniert sein',
            'resolve_auth_actor',
            'auth.entra_roles_changed',
            "'target_user_id'",
            'REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cafeteria',
            'provision_local_user(text, text, text, text, text[])',
            'set_local_password(text, text, text)',
            'disable_local_user(text, text)',
        ):
            if fragment not in migration_0007:
                fail(f'Pflichtfragment in 0007 fehlt: {fragment}')

        for fragment in (
            'record_local_login_lock',
            'SECURITY DEFINER',
            'trg_local_credentials_login_lock_audit',
            'REVOKE INSERT ON audit_events FROM cafeteria_app',
            'REVOKE USAGE, SELECT, UPDATE ON SEQUENCE audit_events_id_seq FROM cafeteria_app',
            'REVOKE ALL ON SCHEMA cafeteria',
            'REVOKE CREATE ON SCHEMA public FROM PUBLIC',
        ):
            if fragment not in migration_0008:
                fail(f'Pflichtfragment in 0008 fehlt: {fragment}')

        migration_0009 = MIGRATION_0009.read_text(encoding='utf-8')
        for fragment in (
            'bootstrap_first_local_admin',
            'pg_advisory_xact_lock',
            'auth.local_admin_bootstrapped',
        ):
            if fragment not in migration_0009:
                fail(f'Pflichtfragment in 0009 fehlt: {fragment}')
                fail(f'Pflichtfragment in 0008 fehlt: {fragment}')

        for fragment in (
            'CREATE TABLE IF NOT EXISTS menu_components',
            'CREATE TABLE IF NOT EXISTS component_allergens',
            'CREATE TABLE IF NOT EXISTS component_labels',
            "SET allergen_mode='manual'",
            "SET origin_mode='manual'",
            "SET label_mode='manual'",
            "bool_or(mia.presence='contains')",
            'v13 conflicting legacy origin country codes',
            'uq_menu_components_location_scope_name',
            'menu_item_components_component_link_check',
        ):
            if fragment not in migration_0010:
                fail(f'Pflichtfragment in 0010 fehlt: {fragment}')
        if not migration_0010.startswith('BEGIN;') or not migration_0010.rstrip().endswith('COMMIT;'):
            fail('Migration 0010 hat keinen strikten BEGIN/COMMIT-Vertrag.')

        for fragment in (
            'cafeteria.lock_component_metadata_masters',
            'RETURNS TABLE (',
            'SECURITY DEFINER',
            'SET search_path = pg_catalog, cafeteria, pg_temp',
            "USING ERRCODE = '22023'",
            'ORDER BY label.id',
            'FOR SHARE OF label',
            'ORDER BY allergen.id',
            'FOR SHARE OF allergen',
            'TO cafeteria_app',
        ):
            if fragment not in migration_0011:
                fail(f'Pflichtfragment in 0011 fehlt: {fragment}')
        if not migration_0011.startswith('BEGIN;') or not migration_0011.rstrip().endswith('COMMIT;'):
            fail('Migration 0011 hat keinen strikten BEGIN/COMMIT-Vertrag.')

        for fragment in (
            'cafeteria.lock_expected_active_location',
            'cafeteria.lock_active_publication',
            'cafeteria.issue_publication_capability',
            'cafeteria.withdraw_publication_revision',
            'LOCK TABLE cafeteria.locations IN SHARE MODE',
            'ORDER BY role_code',
            'SECURITY DEFINER',
            'TO cafeteria_app',
            'TO cafeteria_auth_issuer',
        ):
            if fragment not in migration_0012:
                fail(f'Pflichtfragment in 0012 fehlt: {fragment}')
        if not migration_0012.startswith('BEGIN;') or not migration_0012.rstrip().endswith('COMMIT;'):
            fail('Migration 0012 hat keinen strikten BEGIN/COMMIT-Vertrag.')

        for name in ('menu_weeks', 'menu_services', 'menu_items', 'dish_templates'):
            block = table_block(sql, name).lower()
            if re.search(r'\b(price|preis|internal_rappen|external_rappen)\b', block):
                fail(f'Kostenfeld liegt am falschen Objekt: {name}')
        price_block = table_block(sql, 'menu_item_prices').lower()
        for field in ('internal_rappen', 'external_rappen', "currency char(3)"):
            if field not in price_block:
                fail(f'Kostenfeld fehlt in menu_item_prices: {field}')

        role_values = set(re.findall(r"\('?(Cafeteria\.[A-Za-z]+)'?,", seed))
        expected_roles = {'Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin'}
        if role_values != expected_roles:
            fail(f'Rollen im Seed abweichend: {sorted(role_values)}')
        allergen_seed = seed.split('INSERT INTO allergens', 1)[1].split('ON CONFLICT (code)', 1)[0]
        allergens = re.findall(r"\('([A-Z_]+)',\s*'[^']+',\s*(\d+)\)", allergen_seed)
        allergen_rows = [(code, int(number)) for code, number in allergens]
        if len(allergen_rows) != 14:
            fail(f'Erwartet 14 Allergene, gefunden {len(allergen_rows)}.')

        caf, pat = validate_snapshots()
        live_info = {'live_postgresql_executed': False}
        if '--live' in sys.argv:
            live_info = run_live_check()
        result = {
            'artifact_check': 'passed',
            **live_info,
            'tables': len(tables),
            'table_names': tables,
            'application_roles': len(expected_roles),
            'offer_profiles': 2,
            'allergens': 14,
            'cafeteria_services': sum(len(day['services']) for day in caf['days']),
            'patient_services': sum(len(day['services']) for day in pat['days']),
            'patient_menu_options': sum(len(service['options']) for day in pat['days'] for service in day['services']),
            'schema_sha256': hashlib.sha256(SCHEMA.read_bytes()).hexdigest(),
            'schema_version': 34,
            'migration_checksums': {
                '0001_initial_postgresql.sql': baseline_checksum,
                '0002_profile_publication_and_local_auth.sql': hashlib.sha256(MIGRATION_0002.read_bytes()).hexdigest(),
                '0003_patient_key_and_withdrawal_contracts.sql': hashlib.sha256(MIGRATION_0003.read_bytes()).hexdigest(),
                '0004_patient_key_lock_and_capability_contracts.sql': hashlib.sha256(MIGRATION_0004.read_bytes()).hexdigest(),
                '0005_least_privilege_identity_contracts.sql': hashlib.sha256(MIGRATION_0005.read_bytes()).hexdigest(),
                '0006_auth_issuer_and_local_login.sql': hashlib.sha256(MIGRATION_0006.read_bytes()).hexdigest(),
                '0007_auth_security_hardening.sql': hashlib.sha256(MIGRATION_0007.read_bytes()).hexdigest(),
                '0008_auth_final_hardening.sql': hashlib.sha256(MIGRATION_0008.read_bytes()).hexdigest(),
                '0009_bootstrap_first_local_admin.sql': hashlib.sha256(MIGRATION_0009.read_bytes()).hexdigest(),
                '0010_v12_to_v13.sql': hashlib.sha256(MIGRATION_0010.read_bytes()).hexdigest(),
                '0011_v13_to_v14.sql': hashlib.sha256(MIGRATION_0011.read_bytes()).hexdigest(),
                '0012_v14_to_v15.sql': hashlib.sha256(MIGRATION_0012.read_bytes()).hexdigest(),
                '0013_v15_to_v16.sql': hashlib.sha256(MIGRATION_0013.read_bytes()).hexdigest(),
                '0014_v16_to_v17.sql': hashlib.sha256(MIGRATION_0014.read_bytes()).hexdigest(),
                '0015_v17_to_v18.sql': hashlib.sha256(MIGRATION_0015.read_bytes()).hexdigest(),
                '0016_v18_to_v19.sql': hashlib.sha256(MIGRATION_0016.read_bytes()).hexdigest(),
                '0017_v19_to_v20.sql': hashlib.sha256(MIGRATION_0017.read_bytes()).hexdigest(),
                '0018_v20_to_v21.sql': hashlib.sha256(MIGRATION_0018.read_bytes()).hexdigest(),
                '0019_v21_to_v22.sql': hashlib.sha256(MIGRATION_0019.read_bytes()).hexdigest(),
                '0020_v22_to_v23.sql': hashlib.sha256(MIGRATION_0020.read_bytes()).hexdigest(),
                '0021_v23_to_v24.sql': hashlib.sha256(MIGRATION_0021.read_bytes()).hexdigest(),
                '0022_v24_to_v25.sql': hashlib.sha256(MIGRATION_0022.read_bytes()).hexdigest(),
                '0023_v25_to_v26.sql': hashlib.sha256(MIGRATION_0023.read_bytes()).hexdigest(),
                '0024_v26_to_v27.sql': hashlib.sha256(MIGRATION_0024.read_bytes()).hexdigest(),
                '0025_v27_to_v28.sql': hashlib.sha256(MIGRATION_0025.read_bytes()).hexdigest(),
                '0026_v28_to_v29.sql': hashlib.sha256(MIGRATION_0026.read_bytes()).hexdigest(),
                '0027_v29_to_v30.sql': hashlib.sha256(MIGRATION_0027.read_bytes()).hexdigest(),
                '0028_v30_to_v31.sql': hashlib.sha256(MIGRATION_0028.read_bytes()).hexdigest(),
                '0029_v31_to_v32.sql': hashlib.sha256(MIGRATION_0029.read_bytes()).hexdigest(),
                '0030_v32_to_v33.sql': hashlib.sha256(MIGRATION_0030.read_bytes()).hexdigest(),
                '0031_v33_to_v34.sql': hashlib.sha256(MIGRATION_0031.read_bytes()).hexdigest(),
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'artifact_check': 'failed', 'error': str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
