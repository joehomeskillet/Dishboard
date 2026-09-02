# Dishboard-Admin-Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flask/Jinja/PostgreSQL/Vanilla-JS-Admin für getrennte Patienten- und Cafeteria-Wochenmenüs mit Katalog, partiellen Saves, Review, Preview, Copy und unveränderlichen Publish-Snapshots liefern.

**Architecture:** Das Datenbank- und Profil-Raster ist der zentrale Contract. Ein serieller Store-/Workflow-Kern validiert Location, Scope, Version und exact keys; dünne, URL-abgeleitete Flask-Routen orchestrieren Auth/CSRF/PRG. Jinja, Vanilla JS und CSS bilden ausschließlich den zuletzt gespeicherten Draft ab und verwenden bestehende `--sh-*`-Tokens und Fira Sans.

**Tech Stack:** Python, Flask, SQLAlchemy/psycopg PostgreSQL 16, Jinja, Vanilla JS/CSS, pytest, Ruff, Bandit, bestehende Compose-/Browser-Harnesses; keine neue Dependency.

**Spec:** `docs/superpowers/specs/2026-09-02-dishboard-admin-redesign-design.md`

## Global Constraints

- `patient`: exakt 7 Tage × Lunch/Dinner × 2 Optionen = 28 Einträge; `staff_guest`: exakt 5 Tage × Lunch × 2 Optionen = 10 Einträge.
- Patienten haben keine Preisfelder; Cafeteria hat keine Nächte/Wochenenden; Server und UI lehnen Zeilen außerhalb des Rasters ab.
- `dish_templates` bleibt unverändert. Full-Week-Replace bleibt nur für expliziten Import/Recovery; Partial-Saves dürfen ihn nie aufrufen.
- Keine neue Dependency, keine harten Hex-Farben und keine ungemappten Arbitrary-Klassen; bestehende `--sh-*`-Tokens und Fira Sans verwenden.
- Profil kommt ausschließlich aus `/admin/cafeteria` (`staff_guest`) bzw. `/admin/patienten` (`patient`), nie aus Body oder Query.
- Jede POST-Form nutzt `_csrf`, nur exact erlaubte Felder und bei Writes die erwartete `row_version`; CSRF, `no-store`, Auth und bestehende Capabilities bleiben Pflicht.
- Konflikte sind 409 ohne Mutation, Validierungsfehler 400 mit Feldpfad; deutsche Novice-Fehlertexte nennen Tag, Mahlzeit, Option und Feld.
- Archivieren statt Löschen; `public_id` ist extern, interne Bigint-IDs bleiben intern.
- Vor Symboländerungen Impact-Analyse via GitNexus, vor Commit `gitnexus_detect_changes`; vor Abschluss OCR, `claude-wp-verify`, unabhängige AGY- und Grok-Reviews.
- Fehlendes Backup, unklarer Scope, stale Version, HIGH/CRITICAL-Review oder fehlende Auth-/Browser-Evidenz bedeutet BLOCKED; kein Push/Deploy.

## File Map and Shared Interfaces

| Phase | Files | Responsibility / owner boundary |
|---|---|---|
| 1 | `database/schema.sql`, `database/migrations/0010_v12_to_v13.sql`, `database/permissions.sql`, `database/validate_schema.py`, `database/README.md`, `tools/validate_package.py`, `PACKAGE_CONTENTS.txt`, `MANIFEST_SHA256.txt`, `reference_scaffold/cafeteria/db.py`, `reference_scaffold/tests/test_component_catalog_migration_db.py`, `reference_scaffold/tests/test_auth_database.py`, `reference_scaffold/tests/test_database_invariants.py` | Schema v13, idempotente Migration, Restore-ACLs, Validator-/Package-Pins und Migration-Backfill; je Wave genau ein serialer Owner für `schema.sql` und `db.py`. |
| 2 | `reference_scaffold/cafeteria/component_catalog_store.py`, `reference_scaffold/cafeteria/component_assignment_store.py`, `reference_scaffold/cafeteria/workflow.py`, `reference_scaffold/cafeteria/workflow_snapshot.py`, `reference_scaffold/tests/test_component_catalog_db.py`, `reference_scaffold/tests/test_component_assignment_db.py`, `reference_scaffold/tests/test_admin_workflow_db.py` | Katalog, Scope/Location, Assignment, Auto/Manual-Auflösung, Review und Snapshot. Katalog- und Assignment-Operationen bleiben in den jeweiligen Stores; `workflow.py` verdrahtet sie. |
| 3 | `reference_scaffold/cafeteria/__init__.py`, `reference_scaffold/cafeteria/admin/routes.py`, `reference_scaffold/cafeteria/admin/workflow_routes.py`, `reference_scaffold/cafeteria/workflow_partial_form.py`, `reference_scaffold/cafeteria/workflow_partial_store.py`, `reference_scaffold/cafeteria/workflow_store.py`, `reference_scaffold/tests/test_component_catalog_routes.py`, `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_admin_week_routes.py`, `reference_scaffold/tests/test_admin_draft_preview.py`, `reference_scaffold/tests/test_admin_ux_browser.py` | URL-Familien, exact Form Keys, Partial-Saves, Copy, Preview, Publish/PRG, 400/409/CSRF. `admin/routes.py` ist ein kleiner serieller Adapter; `workflow_routes.py` trägt die neuen Routen und `__init__.py` registriert das Blueprint einmal. CSV-Import/Recovery bleiben erhalten; `persist_draft_connection` nur für vollständigen Import/Recovery. |
| 4 | `reference_scaffold/cafeteria/templates/admin/cafeteria.html`, `reference_scaffold/cafeteria/templates/admin/patienten.html`, `reference_scaffold/cafeteria/templates/admin/components.html`, `reference_scaffold/cafeteria/templates/admin/component_editor.html`, `reference_scaffold/cafeteria/templates/admin/preview.html`, `reference_scaffold/cafeteria/static/admin.js`, `reference_scaffold/cafeteria/static/app.css`, `reference_scaffold/tests/test_admin_ux_browser.py` | Novice-Übersicht/Editor, Templates, JS-State/Dirty-Guard, CSS und Browser-A11y. Neue Templates nur nach bestehendem Projekt-Generator prüfen. |
| 5 | alle vorgenannten Tests plus `reference_scaffold/tests/test_deployment_compose_probe_live.py`, `test_deployment_restore_live.py`, `test_deployment_restore_recovery.py`, `test_capture_live_screenshots.py`, `reference_scaffold/README.md` | Integration, unabhängige Reviews, Backup/Migration/Restore, Compose, unveränderlicher Digest, Live-Proof. |

Verbindliche Python-Schnittstellen, die nach Phase 1/2 für spätere Phasen gelten. `AdminScope` wird aus der authentifizierten Session und der serverseitigen Location-Auflösung gebaut, nie aus Form oder Query:

```python
@dataclass(frozen=True)
class AdminScope:
    actor_id: int
    location_id: int
    profile_code: str

persist_menu_item(engine: Engine, scope: AdminScope, week_id: int, day: str,
                  meal: str, option: str, payload: Mapping[str, object],
                  version: int) -> int
persist_week_header(engine: Engine, scope: AdminScope, week_id: int,
                    payload: Mapping[str, object], version: int) -> int
persist_service_state(engine: Engine, scope: AdminScope, week_id: int,
                      payload: Mapping[str, object], version: int) -> int
assign_component(engine: Engine, scope: AdminScope, item_id: int,
                 component_public_id: str | None, component_text: str | None,
                 version: int) -> int
resolve_component_effects(engine: Engine, scope: AdminScope, item_id: int) -> dict[str, object]
review_component(engine: Engine, scope: AdminScope, item_id: int,
                 component_version: int) -> None
build_snapshot(profile_code: str, draft: dict[str, Any], revision_code: str) -> dict[str, Any]
parse_draft_form(profile_code: str, form: Mapping[str, str]) -> ParsedDraft
```

`parse_draft_form(profile_code, form)` and `build_snapshot(profile_code, draft, revision_code)` retain these existing full-form/full-snapshot signatures. They are not reused as partial mutation APIs.

Location resolution is fail-closed under the current single-location contract: `resolve_single_active_location_connection` returns the sole active location globally; zero or multiple active locations fail. Capability gates still validate the actor separately. For every operation on an existing week, load that week's `location_id` and require it to equal that sole active location.

`create_component` receives `engine`, `scope`, category, name and origin plus
`target_scope: Literal['common', 'current']`; `current` maps only to the
URL-derived `scope.profile_code`, and no API accepts another concrete profile.
Every component API receives an engine/connection and `AdminScope`; assignment,
effects and review never accept an unscoped `item_id`, and review writes
`scope.actor_id` as reviewer. Cross-location and cross-profile attempts return
404.

### Dependency DAG and shared-file ownership

`T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 → T12`. A task may start only after all predecessors have their committed receipt; review lanes are read-only and never unblock a failed prerequisite.

| Shared file | Sole serial implementation owner and prerequisite |
|---|---|
| `database/schema.sql`, `reference_scaffold/cafeteria/db.py` | T1, then T2 only after T1 commits |
| `reference_scaffold/cafeteria/component_catalog_store.py` | T3 only |
| `reference_scaffold/cafeteria/component_assignment_store.py` | T4, then T5; no parallel writer |
| `reference_scaffold/cafeteria/workflow.py` | T4, then T5, then T8; no parallel writer |
| `reference_scaffold/cafeteria/workflow_store.py` | T6 only; minimal Full-Import/Recovery compatibility edits, never Partial-Store |
| `reference_scaffold/cafeteria/workflow_snapshot.py` | T5 only |
| `reference_scaffold/cafeteria/admin/routes.py` | T7 owns the small serial adapter; remove/disable old user-facing mega-form GET/save/publish endpoints without route collisions, preserve CSV Import/Recovery, and keep `persist_draft_connection` only for complete Import/Recovery |
| `reference_scaffold/cafeteria/admin/workflow_routes.py` | T7, then T8; no parallel writer |

## Wave 1 — Schema v13, Location, Migration and Tests

### Task 1: Red migration contract

**Files:** Create `database/migrations/0010_v12_to_v13.sql`; modify
`database/schema.sql`, `database/permissions.sql`, `database/validate_schema.py`,
`database/README.md`, `tools/validate_package.py`, `PACKAGE_CONTENTS.txt`,
`MANIFEST_SHA256.txt`, `reference_scaffold/cafeteria/db.py`,
`reference_scaffold/tests/test_component_catalog_migration_db.py`,
`reference_scaffold/tests/test_auth_database.py` and
`reference_scaffold/tests/test_database_invariants.py`. Do not use or modify
`reference_scaffold/cafeteria/database_roles.py` for these grants.

**Interfaces:** Migration registers `SCHEMA_VERSION = 13`,
`APPLICATION_VERSION = 'dishboard-schema-v13'` and registry entry `0010`; it
is one transaction, idempotent and rollback-safe. `menu_components.id` is
`bigint GENERATED ALWAYS AS IDENTITY`, `public_id uuid UNIQUE`; scopes are
`common|patient|staff_guest`; categories are
`meat|side|vegetable|sauce|dessert|other`. Schema- and package-validator lists,
table count, checksums and manifests pin the same v13 package.

- [ ] Write RED tests against real PG16 for schema version 13, all columns/constraints, grants, rerun idempotence and rollback on injected failure:

```python
def test_v13_migration_is_idempotent_and_exposes_internal_and_public_component_ids(pg16):
    run_migrations(pg16, SCHEMA)
    run_migrations(pg16, SCHEMA)
    row = pg16.execute("select version from schema_migrations order by version desc limit 1").scalar_one()
    assert row == 13
    assert pg16.execute("select data_type from information_schema.columns where table_name='menu_components' and column_name='id'").scalar_one() == "bigint"
```

- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_migration_db.py -k 'schema or migration'`; expected initial FAIL naming missing migration/schema-13 contract.
- [ ] Implement only migration/schema/grant/validator/package-contract changes.
  Preserve `0001`–`0009` byte-identically. Migration `0010` itself must, in
  this order: create the tables; add mode/link columns nullable or with a safe
  default; set every legacy `allergen_mode`, `origin_mode` and `label_mode` to
  `manual`; backfill exact legacy text deterministically per Location/Profile/
  `other` component and exact links/versions; dedupe legacy allergens with
  `contains` winning; run completeness checks; then add constraints, FKs,
  functional unique index on `(location_id, profile_scope, lower(trim(name)))`
  and NOT NULL rules. `public_id` is `uuid UNIQUE DEFAULT gen_random_uuid()`
  generated by PostgreSQL, not application code. Start with `BEGIN;` and end
  in a non-whitespace `COMMIT;` with no trailing comment. Do not put any
  backfill into `db.py`.
- [ ] In `database/permissions.sql`, grant the app and backup roles the required
  ACLs for all three new tables plus `menu_components` sequence usage, and
  reapply permissions in the existing restore order. Extend the real-PG tests
  for empty and populated v12 data, rerun idempotence, injected-failure
  rollback, and final-terminator shape; preserve named backup/down-probe
  instructions in `database/README.md`.
- [ ] Add named PostgreSQL backup and down-probe instructions to the migration test fixture; down-probe restores v12 copy and does not claim magical reversibility.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_migration_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add database/schema.sql database/migrations/0010_v12_to_v13.sql database/permissions.sql database/validate_schema.py database/README.md tools/validate_package.py PACKAGE_CONTENTS.txt MANIFEST_SHA256.txt reference_scaffold/cafeteria/db.py reference_scaffold/tests/test_component_catalog_migration_db.py reference_scaffold/tests/test_auth_database.py reference_scaffold/tests/test_database_invariants.py`.
- [ ] Commit: `rtk git commit -m 'feat: add v13 component catalog migration'`.

### Task 2: Legacy backfill and invariants

**Files:** Test `reference_scaffold/tests/test_database_invariants.py` and
`reference_scaffold/tests/test_public_isolation_homoglyphs.py`; migration
backfill remains in `database/migrations/0010_v12_to_v13.sql`, not `db.py`.

**Interfaces:** Legacy text becomes one exact component per location/profile/category `other`; unmatched references remain valid free text. Existing menus use `manual` for all three classes; duplicate legacy allergens prefer `contains`.

- [ ] Add RED fixtures for two locations, both profiles, homoglyph public IDs, unmatched text and duplicate allergen precedence.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_database_invariants.py tests/test_public_isolation_homoglyphs.py`; expected FAIL on isolation/backfill assertions.
- [ ] Implement validation/invariant checks only: same-location/common-or-
  matching-scope only, archived assigned visibility, no delete, no internal ID
  in external response. Do not add a second backfill path outside migration
  `0010`.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_database_invariants.py tests/test_public_isolation_homoglyphs.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/tests/test_database_invariants.py reference_scaffold/tests/test_public_isolation_homoglyphs.py`.
- [ ] Commit: `rtk git commit -m 'test: verify v13 legacy migration invariants'`.

## Wave 2 — Component Catalog, Store, Assignment, Inheritance and Snapshot

### Task 3: Catalog store and route-independent isolation

**Files:** Create `reference_scaffold/cafeteria/component_catalog_store.py`; test `reference_scaffold/tests/test_component_catalog_db.py`.

**Interfaces:** Catalog-store functions take `engine: Engine` and `scope: AdminScope`; they never accept a caller-supplied location/profile. For existing-week operations the scope's location must equal the loaded week location. Catalog create/search require the sole active location globally; zero/multiple active locations are errors, and capability gates validate the actor separately. `create_component(engine, scope, category, name, origin_country_code, target_scope: Literal['common', 'current']) -> dict` maps `current` only to the URL-derived `scope.profile_code` and never accepts another concrete profile. `find_components(engine, scope, query, category, include_archived) -> list[dict]`, `update_component(engine, scope, public_id, payload, version) -> int`, `archive_component(engine, scope, public_id, version) -> int`, `unarchive_component(engine, scope, public_id, version) -> int` all receive the same scoped engine contract.

- [ ] Add RED CRUD/search/usage/archive tests, including reserved archived names,
  exact category filtering, sorting, 409 stale updates, `common|current`
  target-scope mapping and cross-location/profile 404.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_db.py`; expected FAIL with missing catalog operations.
- [ ] Implement row locks, exact keys, location/profile filtering and public-ID lookup; return usage counts without exposing internal IDs.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/component_catalog_store.py reference_scaffold/tests/test_component_catalog_db.py`.
- [ ] Commit: `rtk git commit -m 'feat: add scoped component catalog store'`.

### Task 4: Assignment resolution and independent modes

**Files:** Create `reference_scaffold/cafeteria/component_assignment_store.py`; modify `reference_scaffold/cafeteria/workflow.py`; test `reference_scaffold/tests/test_component_assignment_db.py`.

**Interfaces:** `assign_component(engine: Engine, scope: AdminScope, item_id: int, component_public_id: str | None, component_text: str | None, version: int) -> int`; `resolve_component_effects(engine: Engine, scope: AdminScope, item_id: int) -> dict[str, object]`; modes are independently `allergen_mode`, `origin_mode`, `label_mode`. No assignment/effects API accepts an unscoped `item_id`.

- [ ] Add RED tests for same-location/common-or-profile scope, cross-location/
  profile 404 assignment and effects, allergen union with `contains` winning,
  origin conflict, diet intersection, nullable/free-text non-inheritance, and
  auto-only rematerialization.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_assignment_db.py`; expected FAIL.
- [ ] Implement assignment validation and deterministic effects. Reject injected patient prices before any write. On component/link change rematerialize only auto classes and reset review; manual values remain untouched.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_assignment_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/component_assignment_store.py reference_scaffold/cafeteria/workflow.py reference_scaffold/tests/test_component_assignment_db.py`.
- [ ] Commit: `rtk git commit -m 'feat: resolve scoped component assignments'`.

### Task 5: Exact immutable snapshots and review gate

**Files:** Modify `reference_scaffold/cafeteria/workflow_snapshot.py`, `reference_scaffold/cafeteria/workflow.py`, `reference_scaffold/cafeteria/component_assignment_store.py`; test `reference_scaffold/tests/test_admin_workflow_db.py`.

**Interfaces:** The existing `build_snapshot(profile_code, draft, revision_code)`
emits exactly `components: list[str]`, `labels: list[{code,name}]`,
`allergens: list[{code,name,presence}]`,
`origins: list[{ingredient,country_code,text}]` and
`allergen_review_status: string`; it contains no internal IDs, modes or
component versions. `review_component(engine: Engine, scope: AdminScope,
item_id: int, component_version: int) -> None` records `scope.actor_id` and
never accepts an unscoped item. The existing full
`publish_draft(engine, profile_code, week_start, *, expected_row_version,
actor_id, issuer_engine)` signature, replacement-publication capability flow,
503 configuration behavior and App-role test remain preserved; it rejects
unreviewed/stale components and stores an immutable revision.

- [ ] Add RED tests asserting exact snapshot keys/types, no forbidden metadata,
  immutability after source edits, scoped review actor, cross-location/profile
  404, review invalidation, stale publish rejection, replacement-publication
  capability/503 behavior and the existing App-role flow.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_workflow_db.py`; expected FAIL.
- [ ] Implement deterministic snapshot materialization and publish transaction; every reviewed concrete component version must match at publish, and any 400/409 leaves all tables unchanged.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_workflow_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/workflow_snapshot.py reference_scaffold/cafeteria/workflow.py reference_scaffold/cafeteria/component_assignment_store.py reference_scaffold/tests/test_admin_workflow_db.py`.
- [ ] Commit: `rtk git commit -m 'feat: enforce reviewed immutable menu snapshots'`.

## Wave 3 — Partial Parser, Store Routes, Copy, Preview and Publish Security

### Task 6: Exact forms and partial persistence

**Files:** Create `reference_scaffold/cafeteria/workflow_partial_form.py` and
`reference_scaffold/cafeteria/workflow_partial_store.py`; minimally modify
the 454-line `reference_scaffold/cafeteria/workflow_store.py`; test
`reference_scaffold/tests/test_workflow_form.py`. T6 is the sole serial owner
of `workflow_store.py`: retain full-form/full-replace Import/Recovery behavior,
replace its `ORDER BY ... LIMIT 1` location selection with
`resolve_single_active_location_connection` requiring exactly one globally
active location, make `_insert_item` explicitly write all three modes
`manual` for CSV/Recovery, and make `load_draft_connection` load all three
modes. Do not grow `workflow_form.py`; partial modules never call full replace.

**Interfaces:** Keep the existing full-form `parse_draft_form(profile_code, form) -> ParsedDraft` unchanged. `workflow_partial_form.py` provides separate exact partial parsers. `workflow_partial_store.py` provides `persist_menu_item(engine, scope, week_id, day, meal, option, payload, version)`, `persist_week_header(engine, scope, week_id, payload, version)`, and `persist_service_state(engine, scope, week_id, payload, version)`. Menu requires exactly `_csrf,week,day,meal,option,row_version,title,allergen_mode,origin_mode,label_mode`; permitted optional keys are `description,note,component_public_id[],component_text[],allergen_code[],allergen_presence[],origin_ingredient[],origin_country_code[],label_code[]`; cafeteria additionally requires `internal_chf,external_chf`, while patient rejects every price key. Header requires exactly `_csrf,week,row_version,title,shared_note`. Service requires exactly `_csrf,week,day,meal,row_version,service_state,notice`.

- [ ] Add RED parser tests for CHF dot/comma normalization to positive Decimal
  Rappen, patient price rejection, the exact required/optional keysets,
  unknown or duplicate scalar keys and misaligned list pairs as 400, profile
  raster rejection and German field-path errors.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_workflow_form.py`; expected FAIL.
- [ ] Implement whitelist parsing and route-derived raster validation in the new
  partial modules. Each partial handler derives the existing week's location,
  checks it against `scope.location_id`, and calls only `persist_menu_item`,
  `persist_week_header` or `persist_service_state`; never `persist_draft`/full
  replace. A closing nonempty service returns 409 and never silently deletes.
  Each partial mutation touches only its addressed entity and explicit child
  classes, byte-compares neighbours, header and publication as unchanged,
  bumps the week `row_version`, and resets relevant review atomically. Schema
  defaults are safely `manual` for all three modes.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_workflow_form.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/workflow_partial_form.py reference_scaffold/cafeteria/workflow_partial_store.py reference_scaffold/cafeteria/workflow_store.py reference_scaffold/tests/test_workflow_form.py`.
- [ ] Commit: `rtk git commit -m 'feat: parse exact partial admin forms'`.

### Task 7: URL families, capabilities, Copy and Preview

**Files:** Modify `reference_scaffold/cafeteria/__init__.py` and
`reference_scaffold/cafeteria/admin/routes.py` as a small serial adapter,
create `reference_scaffold/cafeteria/admin/workflow_routes.py` and
`reference_scaffold/tests/test_admin_ux_browser.py`; test
`reference_scaffold/tests/test_component_catalog_routes.py`,
`reference_scaffold/tests/test_admin_week_routes.py`,
`reference_scaffold/tests/test_admin_workflow_routes.py`,
`reference_scaffold/tests/test_admin_draft_preview.py` and the browser test.
`__init__.py` registers the new blueprint exactly once. Remove/disable duplicate
old mega-form GET/save/publish routes without collisions, preserve CSV
Import/Recovery, and create the browser test by reusing the existing
Playwright patterns and fixtures in `test_rendered_ui.py` with no dependency.

**Interfaces:** Register GET/POST routes exactly as specified in the SDD. `profile_from_endpoint('cafeteria') == 'staff_guest'`, `profile_from_endpoint('patienten') == 'patient'`; copy accepts `_csrf,source_week,target_week,target_row_version`; preview renders last-saved draft only.

- [ ] Add RED route tests for auth/capabilities, fixed URL profiles, no body/query
  profile override, unchanged login/session-cookie/`csrf_token` Auth contract,
  `_csrf` Admin spelling, `Cache-Control: no-store`, 400/409 no mutation,
  same-profile empty-copy lock/409/new IDs, and preview's LAST-SAVED source,
  no-store, and no-live-data fallback. Test empty copy as zero items and no
  active publication. Dirty-state and `target="_blank"` assertions belong to
  the reused rendered/browser harness, not route-preview tests.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_routes.py tests/test_admin_week_routes.py tests/test_admin_workflow_routes.py tests/test_admin_draft_preview.py`; expected FAIL.
- [ ] Implement the separate workflow blueprint and handlers for dashboard, menu, header, service, component CRUD/search, copy and preview. Resolve `AdminScope` server-side; existing-week handlers derive and verify the week's location, while catalog/create fail if globally active locations are zero or multiple under the current single-location contract. Keep the capability gate separate. Enforce `draft.read`, `draft.write`, `publication.publish`; use public IDs; copy excludes patient prices, resets reviews and never publishes.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_routes.py tests/test_admin_week_routes.py tests/test_admin_workflow_routes.py tests/test_admin_draft_preview.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/__init__.py reference_scaffold/cafeteria/admin/routes.py reference_scaffold/cafeteria/admin/workflow_routes.py reference_scaffold/tests/test_component_catalog_routes.py reference_scaffold/tests/test_admin_week_routes.py reference_scaffold/tests/test_admin_workflow_routes.py reference_scaffold/tests/test_admin_draft_preview.py reference_scaffold/tests/test_admin_ux_browser.py`.
- [ ] Commit: `rtk git commit -m 'feat: add secure scoped admin routes'`.

### Task 8: Publish PRG and status/error contract

**Files:** Modify `reference_scaffold/cafeteria/admin/workflow_routes.py`,
`reference_scaffold/cafeteria/workflow.py`; test
`reference_scaffold/tests/test_admin_workflow_routes.py`,
`reference_scaffold/tests/test_workflow_form.py`.

- [ ] Add RED tests for native-confirm publish POST with exactly
  `_csrf,week,row_version`, review/stale guards, PRG revision/flash in
  `aria-live`, and `derive_admin_status` independent of DB enum: empty is zero
  items and no active publication; incomplete is failed saved-draft validation;
  review_open is complete but unchecked/stale; live is an active snapshot equal
  to a freshly built saved snapshot using the same revision identity; changed
  is an active differing publication; ready is the remaining state. DB
  `workflow_state` stays `draft|ready|published|archived`. Cover 400/409
  atomicity.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_workflow_routes.py tests/test_workflow_form.py`; expected FAIL.
- [ ] Implement server-side validation of saved draft, raster, reviews and component versions; use `confirm()` only as pre-submit UX, never as server security. Error text includes e.g. `Mittwoch, Abend, Vegetarisch: Preis darf höchstens zwei Nachkommastellen haben.`
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_workflow_routes.py tests/test_workflow_form.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/admin/workflow_routes.py reference_scaffold/cafeteria/workflow.py reference_scaffold/tests/test_admin_workflow_routes.py reference_scaffold/tests/test_workflow_form.py`.
- [ ] Commit: `rtk git commit -m 'feat: gate publish with review and PRG'`.

## Wave 4 — Novice Overview, Editor, Templates, JavaScript, CSS and A11y

### Task 9: Server-rendered overview, editor and catalog templates

**Files:** Create/modify `reference_scaffold/cafeteria/templates/admin/cafeteria.html`, `patienten.html`, `components.html`, `component_editor.html`, `preview.html`.

- [ ] Add RED rendered tests in `reference_scaffold/tests/test_rendered_ui.py` for exact 28/10-cell grids, no patient cost vocabulary, component usage/archive state, German labels and PREVIEW banner.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_rendered_ui.py`; expected FAIL.
- [ ] Render the route-provided profile and saved data only; include native checkbox + visible `label` inside `fieldset/legend`, 44px label hit area, explicit status/error/retry regions and no hard-coded hex values.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_rendered_ui.py -v`; expected PASS.
- [ ] Stage with: `rtk git add reference_scaffold/cafeteria/templates/admin/cafeteria.html reference_scaffold/cafeteria/templates/admin/patienten.html reference_scaffold/cafeteria/templates/admin/components.html reference_scaffold/cafeteria/templates/admin/component_editor.html reference_scaffold/cafeteria/templates/admin/preview.html reference_scaffold/tests/test_rendered_ui.py`.
- [ ] Commit: `rtk git commit -m 'feat: add novice admin templates'`.

### Task 10: Dirty/loading/error/dense client behavior and responsive a11y

**Files:** Create/modify `reference_scaffold/cafeteria/static/admin.js`, `reference_scaffold/cafeteria/static/app.css`; modify the T7-created `reference_scaffold/tests/test_admin_ux_browser.py`.

- [ ] Add RED browser tests at 390×844, 1440×1100, 2560×1440 and 50% zoom for keyboard order/focus, Escape cancel, `aria-busy` skeleton, retry error, dense state, sticky safe-area actions, dirty Preview/Publish block, Preview `target="_blank"`, Copy and Publish flow.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_ux_browser.py`; expected FAIL.
- [ ] Implement Vanilla JS state machine for `empty/loading/error/dense`, dirty tracking, exact last-saved preview guard, native `confirm()` and field focus. Implement token-based CSS, 18–24px checkbox, visible focus, non-color status, safe-area inset and Fira Sans.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_ux_browser.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/static/admin.js reference_scaffold/cafeteria/static/app.css reference_scaffold/tests/test_admin_ux_browser.py`.
- [ ] Commit: `rtk git commit -m 'feat: make admin editor responsive and accessible'`.

## Wave 5 — Integration, Reviews, Migration/Restore, Compose and Live Proof

### Task 11: Contract and full regression gates

**Files:** Existing implementation/test files only; no new production dependencies.

- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q`; preserve verbatim output and exit code.
- [ ] Discovery gate: from the repository root run `rtk rg --files -g 'pyproject.toml' -g 'pytest.ini' -g 'tox.ini' -g '.ruff.toml' -g '.bandit' -g 'Makefile' -g 'package.json' -g 'requirements*.txt' -g '*secret*'`. For every discovered project-configured schema/package validator, Ruff, Bandit, or secret-scan command, run its exact configured command and retain its verbatim receipt. If a required validator has no discovered configuration or executable command, mark that gate BLOCKED with the missing configuration or executable named; do not claim the gate passed.
- [ ] Run `gitnexus_detect_changes()` and confirm only planned symbols/flows changed. Run `rtk ocr review --repo /nvmetank1/projects/menuplan --from github/main --to docs/admin-redesign-plan-v1 --format json --audience agent` and record `OCR:` summary.
- [ ] Obtain independent read-only AGY and Grok reviews of the diff/plan; HIGH/CRITICAL finding blocks progression.

### Task 12: PG16 migration, restore and deployment proof

**Files:** `reference_scaffold/tests/test_deployment_compose_probe_live.py`, `reference_scaffold/tests/test_deployment_restore_live.py`, `reference_scaffold/tests/test_deployment_restore_recovery.py`, `reference_scaffold/tests/test_capture_live_screenshots.py`, `reference_scaffold/README.md`.

- [ ] Take and record a named PostgreSQL backup plus a down-probe copy before migration; execute Compose PG16 migration and verify schema 13, grants, idempotence and rollback.
- [ ] Restore v12 probe data, run the documented restore path, verify exact legacy/free-text behavior and no accidental `dish_templates` change.
- [ ] Run Chromium and existing CI-browser checks over all four viewports, keyboard/focus, errors/retry, Copy/Preview/Publish; capture authenticated admin smoke screenshots and a proof ZIP.
- [ ] Deploy only after all receipts exist: backup ID, schema-13 migration, immutable image digest, healthcheck and authenticated admin smoke. Record rollback/restore probe; no claim from `pytest` alone.
- [ ] Final verification: `rtk claude-wp-verify --branch docs/admin-redesign-plan-v1 --base github/main`; confirm non-empty plan diff, no staged-leak, and exact ownership.

## Self-review checklist

- [ ] Cross-check every SDD section: 28/10 raster, no patient prices, full-replace exception, three modes, location/profile isolation, migration/backfill/down-probe, exact routes/keys/statuses, last-saved Preview, review/stale immutable Snapshot, A11y viewport matrix, backup/restore and stop conditions.
- [ ] Scan this plan for vague or undefined instructions; replace each with exact keys, signatures, test names and commands before commit; configured fallback wording must name the concrete fallback and its trigger.
- [ ] Verify shared-file serial ownership: `schema.sql`, `db.py`, `component_catalog_store.py`, `component_assignment_store.py`, `workflow.py`, `workflow_snapshot.py`, and the `admin/routes.py` adapter plus `admin/workflow_routes.py` have one owner per wave; review lanes are read-only.
