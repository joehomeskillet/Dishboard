"""REG-KK contract tests for the Küchenkalender registry rewrite (WAVES.md R1–R12)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


def _load_validate_plan() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        'validate_plan', Path(__file__).resolve().parent / 'validate-plan.py'
    )
    if spec is None or spec.loader is None:
        raise ImportError('validate-plan.py is not loadable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_VALIDATE = _load_validate_plan()
PACKAGE_ID = _VALIDATE.PACKAGE_ID
SLICE_ID_PREFIXES = _VALIDATE.SLICE_ID_PREFIXES
validate_main = _VALIDATE.main

BACKLOG = Path(__file__).resolve().parent
LIVE = 'e0da7ab74ec5c0d5b9bc751cb3a09c2633e530f4'
SOURCE = 'e813806b51fb5efaef5d5755c292f8027ce1b2eb'
MANIFESTS = (
    BACKLOG / 'operations-wps.json',
    BACKLOG / 'recipes-wps.json',
    BACKLOG / 'surfaces-wps.json',
)

SCHEMA_FILES = frozenset({
    'database/schema.sql',
    'database/permissions.sql',
    'database/validate_schema.py',
    'reference_scaffold/cafeteria/db.py',
    'tools/validate_package.py',
})
INVARIANT_FILES = frozenset({
    'reference_scaffold/tests/test_database_invariants.py',
    'reference_scaffold/tests/test_master_data_db.py',
})

NEW_IDS = {
    'MP-CAL-READ': 'operations',
    'MP-CAL-DESIGN': 'operations',
    'MP-CAL-MONTH': 'operations',
    'MP-CAL-NAV': 'operations',
    'MP-CAL-EVENTS-SCHEMA': 'operations',
    'MP-CAL-EVENTS-UI': 'operations',
    'MP-CAL-EVENT-DEMAND': 'operations',
    'MP-CAL-DAY': 'operations',
    'MP-CAL-LIST': 'operations',
    'MP-CALC-PRICE-UI': 'operations',
    'MP-CALC-SHOPPING-COST': 'operations',
    'MP-ORD-SCHEMA': 'operations',
    'MP-INV-SCHEMA': 'operations',
    'MP-REC-SHOPPING-PERIOD': 'recipes',
}

SCHEMA_WRITERS = {
    'MP-CAL-EVENTS-SCHEMA': 'database/migrations/<ROOT_RESERVED_MP-CAL-EVENTS-SCHEMA>.sql',
    'MP-CALC-PRICE-LEDGER': 'database/migrations/<ROOT_RESERVED_MP-CALC-PRICE-LEDGER>.sql',
    'MP-CAL-EVENT-DEMAND': 'database/migrations/<ROOT_RESERVED_MP-CAL-EVENT-DEMAND>.sql',
    'MP-ORD-SCHEMA': 'database/migrations/<ROOT_RESERVED_MP-ORD-SCHEMA>.sql',
    'MP-INV-SCHEMA': 'database/migrations/<ROOT_RESERVED_MP-INV-SCHEMA>.sql',
    'MP-INV-PREPARED-BATCH-PRODUCTION': (
        'database/migrations/<ROOT_RESERVED_MP-INV-PREPARED-BATCH-PRODUCTION>.sql'
    ),
    'MP-CALC-RULES-SUGGEST': 'database/migrations/<ROOT_RESERVED_MP-CALC-RULES-SUGGEST>.sql',
}

SCHEMA_SIBLINGS = {
    'MP-ORD-SUPPLIER-ARTICLE': 'MP-ORD-SCHEMA',
    'MP-ORD-BASKET-DRAFT': 'MP-ORD-SCHEMA',
    'MP-INV-MOVEMENT-CORE': 'MP-INV-SCHEMA',
    'MP-INV-TRANSFER': 'MP-INV-SCHEMA',
    'MP-INV-COUNT-CORRECTION': 'MP-INV-SCHEMA',
    'MP-CALC-CALCULATION-RECEIPTS': 'MP-CALC-RULES-SUGGEST',
}

DEPENDS = {
    'MP-CAL-MONTH': ('MP-CAL-READ', 'MP-CAL-DESIGN'),
    'MP-CAL-NAV': ('MP-CAL-MONTH',),
    'MP-CAL-EVENTS-UI': ('MP-CAL-EVENTS-SCHEMA', 'MP-CAL-MONTH'),
    'MP-CALC-PRICE-UI': ('MP-CALC-PRICE-LEDGER',),
    'MP-CALC-SHOPPING-COST': (
        'MP-CALC-PRICE-LEDGER',
        'MP-CALC-PATIENT-GUARD',
        'MP-REC-SHOPPING-PERIOD',
    ),
    'MP-CAL-EVENT-DEMAND': ('MP-CAL-EVENTS-SCHEMA', 'MP-REC-SHOPPING-PERIOD'),
    'MP-CAL-DAY': ('MP-CAL-NAV',),
    'MP-CAL-LIST': ('MP-CAL-NAV',),
    'MP-INV-SCHEMA': ('MP-BAS-FOUNDATIONS',),
    'MP-INV-MOVEMENT-CORE': ('MP-INV-SCHEMA',),
    'MP-ORD-SUPPLIER-ARTICLE': ('MP-ORD-SCHEMA',),
    'MP-ORD-BASKET-DRAFT': ('MP-ORD-SUPPLIER-ARTICLE',),
    'MP-REC-SHOPPING-PERIOD': ('MP-REC-SHOPPING-PERSIST',),
    'MP-INV-NO-PLAN-DEBIT': (
        'MP-INV-MOVEMENT-CORE',
        'MP-REC-BINDINGS',
        'MP-REC-IMPORT-BATCH',
        'MP-CAL-EVENTS-SCHEMA',
    ),
}

R2 = 'R2: line_cost(Rohmenge in Basiseinheit'
R3_HEAD = 'R3: Anlass-Kopf'
R3_DEMAND = 'R3: Bedarf aus Anlässen'
R5 = 'R5: candidate_components(engine, scope, *, date_from, date_to)'
R6 = 'R6: Kalender-heute'
R7_READ = 'R7: Kalender lesen draft.read'
R7_EVENT = 'R7: Anlass schreiben draft.write'
R7_MASTER = 'R7: Preise, Lieferanten, Artikel masterdata.write'
R7_BASKET = 'R7: Korb draft.write'
R8 = 'R8: cost_total und rappen_suggestion'
R9 = 'R9: partieller Unique-Index supplier_articles'
R10 = 'R10: Anlass-Writes buchen keinen Bestand'
R11 = 'layout_variant=calendar'
R12 = 'R12: Migration mit Backup-Owner Root'


@pytest.fixture(scope='module')
def packages() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for path in MANIFESTS:
        plan = json.loads(path.read_text(encoding='utf-8'))
        for wp in plan['work_packages']:
            wp_id = wp['id']
            assert wp_id not in found, wp_id
            found[wp_id] = wp
            found[wp_id]['_slice'] = plan['slice']
    return found


def _owned(wp: dict) -> set[str]:
    return set(wp.get('owned_files') or ())


def _readonly(wp: dict) -> set[str]:
    return set(wp.get('read_only_contract_files') or ())


def _criteria(wp: dict) -> str:
    return '\n'.join(wp.get('acceptance_criteria') or ())


def test_validate_plan_full_pass() -> None:
    argv = ['--source-commit', SOURCE, '--quiet', *(str(path) for path in MANIFESTS)]
    assert validate_main(argv) == 0


def test_mp_cal_prefix_is_operations() -> None:
    assert 'MP-CAL-' in SLICE_ID_PREFIXES['operations']


def test_new_ids_exist_in_declared_slice(packages: dict[str, dict]) -> None:
    for wp_id, slice_name in NEW_IDS.items():
        assert PACKAGE_ID.fullmatch(wp_id)
        assert wp_id in packages, wp_id
        wp = packages[wp_id]
        assert wp['_slice'] == slice_name
        assert wp['status'] == 'PLANNED'
        assert wp['kind'] in {'implementation', 'research', 'verification'}


def test_r1_schema_writers_own_five_plus_migration(packages: dict[str, dict]) -> None:
    for wp_id, migration in SCHEMA_WRITERS.items():
        wp = packages[wp_id]
        owned = _owned(wp)
        assert SCHEMA_FILES <= owned, wp_id
        assert migration in owned
        assert wp['migration_group'] == 'root-serialized-after-schema27'
        assert R12 in _criteria(wp)


def test_r1_siblings_lose_schema_and_read_migration(packages: dict[str, dict]) -> None:
    for sibling, writer in SCHEMA_SIBLINGS.items():
        wp = packages[sibling]
        owned = _owned(wp)
        assert owned.isdisjoint(SCHEMA_FILES), sibling
        assert owned.isdisjoint(INVARIANT_FILES), sibling
        assert not any('ROOT_RESERVED_' in path for path in owned)
        assert not any(path.endswith('_migration_db.py') for path in owned)
        assert SCHEMA_WRITERS[writer] in _readonly(wp)
        assert wp['migration_group'] is None


def test_import_batch_placeholder_cleared(packages: dict[str, dict]) -> None:
    wp = packages['MP-REC-IMPORT-BATCH']
    blob = json.dumps(wp)
    assert 'ROOT_RESERVED_MP-REC-IMPORT-BATCH' not in blob
    assert _owned(wp).isdisjoint(SCHEMA_FILES)
    assert wp['migration_group'] is None
    assert 'keine neue Migration' in _criteria(wp)


def test_shopping_pdf_deployed_on_live(packages: dict[str, dict]) -> None:
    wp = packages['MP-REC-SHOPPING-PDF']
    assert wp['status'] == 'DEPLOYED'
    evidence = '\n'.join(wp.get('completion_evidence') or ())
    assert 'e0da7ab' in evidence
    assert LIVE[:7] in evidence or 'e0da7ab' in evidence


def test_confirm_send_keeps_own_migration(packages: dict[str, dict]) -> None:
    owned = _owned(packages['MP-ORD-CONFIRM-SEND'])
    assert any('ROOT_RESERVED_MP-ORD-CONFIRM-SEND' in path for path in owned)


def test_depends_on_matches_r4(packages: dict[str, dict]) -> None:
    for wp_id, needed in DEPENDS.items():
        have = set(packages[wp_id]['depends_on'])
        assert set(needed) <= have, wp_id
    assert 'MP-REC-BINDINGS-ACCEPT' not in packages['MP-INV-MOVEMENT-CORE']['depends_on']
    assert 'MP-REC-SNAPSHOT-V2' in packages['MP-CALC-PREPARED-GRAPH']['depends_on']
    assert 'MP-REC-BINDINGS' in packages['MP-CALC-MENU-PROJECTION']['depends_on']
    assert 'MP-REC-SNAPSHOT-V2' in packages['MP-INV-PREPARED-BATCH-PRODUCTION']['depends_on']


def test_r2_r10_acceptance_phrases(packages: dict[str, dict]) -> None:
    assert R2 in _criteria(packages['MP-CALC-SHOPPING-COST'])
    assert R2 in _criteria(packages['MP-ORD-EXPORT-PREVIEW'])
    assert R2 in _criteria(packages['MP-ORD-ADMIN-PREVIEW'])
    assert R2 in _criteria(packages['MP-ORD-BASKET-DRAFT'])
    assert R3_HEAD in _criteria(packages['MP-CAL-EVENTS-SCHEMA'])
    assert R3_DEMAND in _criteria(packages['MP-CAL-EVENT-DEMAND'])
    assert R5 in _criteria(packages['MP-REC-SHOPPING-PERIOD'])
    assert R6 in _criteria(packages['MP-CAL-READ'])
    assert R6 in _criteria(packages['MP-CALC-PRICE-LEDGER'])
    assert R7_READ in _criteria(packages['MP-CAL-READ'])
    assert R7_EVENT in _criteria(packages['MP-CAL-EVENTS-SCHEMA'])
    assert R7_MASTER in _criteria(packages['MP-CALC-PRICE-LEDGER'])
    assert R7_MASTER in _criteria(packages['MP-ORD-SCHEMA'])
    assert R7_BASKET in _criteria(packages['MP-ORD-BASKET-DRAFT'])
    assert R8 in _criteria(packages['MP-CALC-PATIENT-GUARD'])
    assert R9 in _criteria(packages['MP-ORD-SCHEMA'])
    assert R10 in _criteria(packages['MP-INV-NO-PLAN-DEBIT'])
    for wp_id in (
        'MP-CAL-DESIGN',
        'MP-CAL-MONTH',
        'MP-CAL-NAV',
        'MP-CAL-EVENTS-UI',
        'MP-CAL-DAY',
        'MP-CAL-LIST',
    ):
        assert R11 in _criteria(packages[wp_id])


def test_cal_nav_is_sole_new_sidebar_writer(packages: dict[str, dict]) -> None:
    sidebar = 'reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html'
    cal_owners = [
        wp_id for wp_id, wp in packages.items()
        if wp_id.startswith('MP-CAL-') and not wp_id.startswith('MP-CALC-')
        and sidebar in _owned(wp)
    ]
    assert cal_owners == ['MP-CAL-NAV']


def test_bindings_accept_is_not_a_wave_gate(packages: dict[str, dict]) -> None:
    text = _criteria(packages['MP-REC-BINDINGS-ACCEPT'])
    assert 'kein Wellentor' in text
    assert packages['MP-REC-BINDINGS-ACCEPT']['kind'] == 'verification'
