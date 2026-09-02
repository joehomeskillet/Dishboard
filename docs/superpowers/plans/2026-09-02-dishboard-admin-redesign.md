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
| 1 | `database/schema.sql`, `database/migrations/0010_v12_to_v13.sql`, `reference_scaffold/cafeteria/db.py`, `reference_scaffold/cafeteria/database_roles.py`, `reference_scaffold/tests/test_component_catalog_migration_db.py`, `reference_scaffold/tests/test_database_invariants.py` | Schema v13, idempotente Migration, Grants, Validator, Legacy-Backfill; je Wave genau ein serialer Owner für `schema.sql` und `db.py`. |
| 2 | `reference_scaffold/cafeteria/workflow_store.py`, `reference_scaffold/cafeteria/workflow.py`, `reference_scaffold/cafeteria/workflow_snapshot.py`, `reference_scaffold/tests/test_component_catalog_db.py`, `reference_scaffold/tests/test_component_assignment_db.py`, `reference_scaffold/tests/test_admin_workflow_db.py` | Katalog, Scope/Location, Assignment, Auto/Manual-Auflösung, Review und Snapshot; je Wave genau ein serialer Owner pro Shared-Datei. |
| 3 | `reference_scaffold/cafeteria/admin/routes.py`, `reference_scaffold/cafeteria/workflow_form.py`, `reference_scaffold/tests/test_component_catalog_routes.py`, `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_admin_week_routes.py`, `reference_scaffold/tests/test_admin_draft_preview.py` | URL-Familien, exact Form Keys, Partial-Saves, Copy, Preview, Publish/PRG, 400/409/CSRF; serialer Owner von `admin/routes.py`. |
| 4 | `reference_scaffold/cafeteria/templates/admin/cafeteria.html`, `reference_scaffold/cafeteria/templates/admin/patienten.html`, `reference_scaffold/cafeteria/templates/admin/components.html`, `reference_scaffold/cafeteria/templates/admin/component_editor.html`, `reference_scaffold/cafeteria/templates/admin/preview.html`, `reference_scaffold/cafeteria/static/admin.js`, `reference_scaffold/cafeteria/static/app.css`, `reference_scaffold/tests/test_admin_ux_browser.py` | Novice-Übersicht/Editor, Templates, JS-State/Dirty-Guard, CSS und Browser-A11y. Neue Templates nur nach bestehendem Projekt-Generator prüfen. |
| 5 | alle vorgenannten Tests plus `reference_scaffold/tests/test_deployment_compose_probe_live.py`, `test_deployment_restore_live.py`, `test_deployment_restore_recovery.py`, `test_capture_live_screenshots.py`, `reference_scaffold/README.md` | Integration, unabhängige Reviews, Backup/Migration/Restore, Compose, unveränderlicher Digest, Live-Proof. |

Verbindliche Python-Schnittstellen, die nach Phase 1/2 für spätere Phasen gelten:

```python
persist_menu_item(week_id: int, profile: str, day: str, meal: str,
                  option: str, payload: dict[str, object], version: int) -> int
persist_week_header(week_id: int, profile: str, payload: dict[str, object], version: int) -> int
persist_service_state(week_id: int, profile: str, payload: dict[str, object], version: int) -> int
resolve_component_effects(item_id: int) -> dict[str, list[str]]
build_snapshot(week_id: int, profile: str) -> dict[str, object]
parse_draft_form(profile_code: str, form: Mapping[str, str]) -> ParsedDraft
```

## Wave 1 — Schema v13, Location, Migration and Tests

### Task 1: Red migration contract

**Files:** Create `database/migrations/0010_v12_to_v13.sql`; modify `database/schema.sql`, `reference_scaffold/cafeteria/db.py`, `reference_scaffold/cafeteria/database_roles.py`; create `reference_scaffold/tests/test_component_catalog_migration_db.py`.

**Interfaces:** Migration registers version 13, is one transaction, idempotent and rollback-safe. `menu_components.id` is `bigint GENERATED ALWAYS AS IDENTITY`, `public_id uuid UNIQUE`; scopes are `common|patient|staff_guest`; categories are `meat|side|vegetable|sauce|dessert|other`.

- [ ] Write RED tests against real PG16 for schema version 13, all columns/constraints, grants, rerun idempotence and rollback on injected failure:

```python
def test_v13_migration_is_idempotent_and_exposes_internal_and_public_component_ids(pg16):
    run_migrations(pg16, SCHEMA)
    run_migrations(pg16, SCHEMA)
    row = pg16.execute("select version from schema_migrations order by version desc limit 1").scalar_one()
    assert row == 13
    assert pg16.execute("select data_type from information_schema.columns where table_name='menu_components' and column_name='id'").scalar_one() == "bigint"
```

- [ ] Run: `cd reference_scaffold && pytest -q tests/test_component_catalog_migration_db.py -k 'schema or migration'`; expected initial FAIL naming missing migration/schema-13 contract.
- [ ] Implement only migration/schema/grant/validator changes. Preserve `0001`–`0009` byte-identically; add `profile_scope`, location-scoped unique lower(trim(name)), child FKs to internal IDs, `presence`, nullable item component link/version, and three independent item modes.
- [ ] Add named PostgreSQL backup and down-probe instructions to the migration test fixture; down-probe restores v12 copy and does not claim magical reversibility.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_component_catalog_migration_db.py -v`; expected PASS.
- [ ] Commit: `git add database/schema.sql database/migrations/0010_v12_to_v13.sql reference_scaffold/cafeteria/db.py reference_scaffold/cafeteria/database_roles.py reference_scaffold/tests/test_component_catalog_migration_db.py && git commit -m 'feat: add v13 component catalog migration'`.

### Task 2: Legacy backfill and invariants

**Files:** Modify `reference_scaffold/cafeteria/db.py`; test `reference_scaffold/tests/test_database_invariants.py`, `reference_scaffold/tests/test_public_isolation_homoglyphs.py`.

**Interfaces:** Legacy text becomes one exact component per location/profile/category `other`; unmatched references remain valid free text. Existing menus use `manual` for all three classes; duplicate legacy allergens prefer `contains`.

- [ ] Add RED fixtures for two locations, both profiles, homoglyph public IDs, unmatched text and duplicate allergen precedence.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_database_invariants.py tests/test_public_isolation_homoglyphs.py`; expected FAIL on isolation/backfill assertions.
- [ ] Implement transactional, rerunnable backfill and validator checks: same-location/common-or-matching-scope only, archived assigned visibility, no delete, no internal ID in external response.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_database_invariants.py tests/test_public_isolation_homoglyphs.py -v`; expected PASS.
- [ ] Commit: `git add reference_scaffold/cafeteria/db.py reference_scaffold/tests/test_database_invariants.py reference_scaffold/tests/test_public_isolation_homoglyphs.py && git commit -m 'feat: backfill v13 legacy component data'`.

## Wave 2 — Component Catalog, Store, Assignment, Inheritance and Snapshot

### Task 3: Catalog store and route-independent isolation

**Files:** Modify `reference_scaffold/cafeteria/workflow_store.py`; test `reference_scaffold/tests/test_component_catalog_db.py`.

**Interfaces:** Store functions `create_component(location_id: int, profile_scope: str, category: str, name: str, origin_country_code: str | None) -> dict`, `find_components(location_id: int, profile: str, query: str, category: str | None, include_archived: bool) -> list[dict]`, `update_component(public_id: str, payload: dict, version: int) -> int`, `archive_component(public_id: str, version: int) -> int`, `unarchive_component(public_id: str, version: int) -> int`.

- [ ] Add RED CRUD/search/usage/archive tests, including reserved archived names, exact category filtering, sorting and 409 stale updates.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_component_catalog_db.py`; expected FAIL with missing catalog operations.
- [ ] Implement row locks, exact keys, location/profile filtering and public-ID lookup; return usage counts without exposing internal IDs.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_component_catalog_db.py -v`; expected PASS.
- [ ] Commit with `git add reference_scaffold/cafeteria/workflow_store.py reference_scaffold/tests/test_component_catalog_db.py && git commit -m 'feat: add scoped component catalog store'`.

### Task 4: Assignment resolution and independent modes

**Files:** Modify `reference_scaffold/cafeteria/workflow_store.py`, `reference_scaffold/cafeteria/workflow.py`; test `reference_scaffold/tests/test_component_assignment_db.py`.

**Interfaces:** `assign_component(item_id: int, component_public_id: str | None, component_text: str | None, version: int) -> int`; `resolve_component_effects(item_id) -> {'allergens': list[str], 'origins': list[str], 'labels': list[str]}`; modes are independently `allergen_mode`, `origin_mode`, `label_mode`.

- [ ] Add RED tests for same-location/common-or-profile scope, 404 cross-scope assignment, allergen union with `contains` winning, origin conflict, diet intersection, nullable/free-text non-inheritance, and auto-only rematerialization.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_component_assignment_db.py`; expected FAIL.
- [ ] Implement assignment validation and deterministic effects. Reject injected patient prices before any write. On component/link change rematerialize only auto classes and reset review; manual values remain untouched.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_component_assignment_db.py -v`; expected PASS.
- [ ] Commit: `git add reference_scaffold/cafeteria/workflow_store.py reference_scaffold/cafeteria/workflow.py reference_scaffold/tests/test_component_assignment_db.py && git commit -m 'feat: resolve scoped component assignments'`.

### Task 5: Exact immutable snapshots and review gate

**Files:** Modify `reference_scaffold/cafeteria/workflow_snapshot.py`, `reference_scaffold/cafeteria/workflow.py`, `reference_scaffold/cafeteria/workflow_store.py`; test `reference_scaffold/tests/test_admin_workflow_db.py`.

**Interfaces:** `build_snapshot(week_id, profile)` emits existing external keys and `list[str]` values only; no internal IDs, modes or versions. `review_component(item_id, component_version, actor_id) -> None`; `publish_draft(...)` rejects unreviewed/stale components and stores immutable revision.

- [ ] Add RED tests asserting exact snapshot keys/types, no forbidden metadata, immutability after source edits, review invalidation and stale publish rejection.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_admin_workflow_db.py`; expected FAIL.
- [ ] Implement deterministic snapshot materialization and publish transaction; every reviewed concrete component version must match at publish, and any 400/409 leaves all tables unchanged.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_admin_workflow_db.py -v`; expected PASS.
- [ ] Commit: `git add reference_scaffold/cafeteria/workflow_snapshot.py reference_scaffold/cafeteria/workflow.py reference_scaffold/cafeteria/workflow_store.py reference_scaffold/tests/test_admin_workflow_db.py && git commit -m 'feat: enforce reviewed immutable menu snapshots'`.

## Wave 3 — Partial Parser, Store Routes, Copy, Preview and Publish Security

### Task 6: Exact forms and partial persistence

**Files:** Modify `reference_scaffold/cafeteria/workflow_form.py`, `reference_scaffold/cafeteria/workflow_store.py`; test `reference_scaffold/tests/test_workflow_form.py`.

**Interfaces:** `parse_draft_form(profile_code, form)` returns `ParsedDraft`; menu POST accepts `_csrf,week,day,meal,option,row_version,fields`; header/service parsers reject unknown keys and patient price keys.

- [ ] Add RED parser tests for CHF dot/comma normalization to positive Decimal Rappen, patient price rejection, exact optional fields, profile raster rejection and German field-path errors.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_workflow_form.py`; expected FAIL.
- [ ] Implement whitelist parsing and route-derived raster validation. Partial handlers call only `persist_menu_item`, `persist_week_header` or `persist_service_state`; never `persist_draft`/full replace.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_workflow_form.py -v`; expected PASS.
- [ ] Commit: `git add reference_scaffold/cafeteria/workflow_form.py reference_scaffold/cafeteria/workflow_store.py reference_scaffold/tests/test_workflow_form.py && git commit -m 'feat: parse exact partial admin forms'`.

### Task 7: URL families, capabilities, Copy and Preview

**Files:** Modify `reference_scaffold/cafeteria/admin/routes.py`; test `reference_scaffold/tests/test_admin_week_routes.py`, `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_admin_draft_preview.py`.

**Interfaces:** Register GET/POST routes exactly as specified in the SDD. `profile_from_endpoint('cafeteria') == 'staff_guest'`, `profile_from_endpoint('patienten') == 'patient'`; copy accepts `_csrf,source_week,target_week,target_row_version`; preview renders last-saved draft only.

- [ ] Add RED route tests for auth/capabilities, fixed URL profiles, no body/query profile override, `_csrf` spelling, `Cache-Control: no-store`, 400/409 no mutation, same-profile empty-copy lock/409/new IDs, and preview dirty guard/banner/target blank.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_admin_week_routes.py tests/test_admin_workflow_routes.py tests/test_admin_draft_preview.py`; expected FAIL.
- [ ] Implement route decorators and handlers for dashboard, menu, header, service, component CRUD/search, copy and preview. Enforce `draft.read`, `draft.write`, `publication.publish`; use public IDs; copy excludes patient prices, resets reviews and never publishes.
- [ ] Run the same command with `-v`; expected PASS.
- [ ] Commit: `git add reference_scaffold/cafeteria/admin/routes.py reference_scaffold/tests/test_admin_week_routes.py reference_scaffold/tests/test_admin_workflow_routes.py reference_scaffold/tests/test_admin_draft_preview.py && git commit -m 'feat: add secure scoped admin routes'`.

### Task 8: Publish PRG and status/error contract

**Files:** Modify `reference_scaffold/cafeteria/admin/routes.py`, `reference_scaffold/cafeteria/workflow.py`; test `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_workflow_form.py`.

- [ ] Add RED tests for native-confirm publish POST with exactly `_csrf,week,row_version`, review/stale guards, PRG revision/flash in `aria-live`, exact statuses `empty|incomplete|review_open|ready|live|changed`, and 400/409 atomicity.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_admin_workflow_routes.py tests/test_workflow_form.py`; expected FAIL.
- [ ] Implement server-side validation of saved draft, raster, reviews and component versions; use `confirm()` only as pre-submit UX, never as server security. Error text includes e.g. `Mittwoch, Abend, Vegetarisch: Preis darf höchstens zwei Nachkommastellen haben.`
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_admin_workflow_routes.py tests/test_workflow_form.py -v`; expected PASS.
- [ ] Commit: `git add reference_scaffold/cafeteria/admin/routes.py reference_scaffold/cafeteria/workflow.py reference_scaffold/tests/test_admin_workflow_routes.py reference_scaffold/tests/test_workflow_form.py && git commit -m 'feat: gate publish with review and PRG'`.

## Wave 4 — Novice Overview, Editor, Templates, JavaScript, CSS and A11y

### Task 9: Server-rendered overview, editor and catalog templates

**Files:** Create/modify `reference_scaffold/cafeteria/templates/admin/cafeteria.html`, `patienten.html`, `components.html`, `component_editor.html`, `preview.html`.

- [ ] Add RED rendered tests in `reference_scaffold/tests/test_rendered_ui.py` for exact 28/10-cell grids, no patient cost vocabulary, component usage/archive state, German labels and PREVIEW banner.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_rendered_ui.py`; expected FAIL.
- [ ] Render the route-provided profile and saved data only; include native checkbox + visible `label` inside `fieldset/legend`, 44px label hit area, explicit status/error/retry regions and no hard-coded hex values.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_rendered_ui.py -v`; expected PASS.
- [ ] Commit template files and test changes with `git commit -m 'feat: add novice admin templates'`.

### Task 10: Dirty/loading/error/dense client behavior and responsive a11y

**Files:** Create/modify `reference_scaffold/cafeteria/static/admin.js`, `reference_scaffold/cafeteria/static/app.css`; test `reference_scaffold/tests/test_admin_ux_browser.py`.

- [ ] Add RED browser tests at 390×844, 1440×1100, 2560×1440 and 50% zoom for keyboard order/focus, Escape cancel, `aria-busy` skeleton, retry error, dense state, sticky safe-area actions, dirty Preview/Publish block, Copy and Publish flow.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_admin_ux_browser.py`; expected FAIL.
- [ ] Implement Vanilla JS state machine for `empty/loading/error/dense`, dirty tracking, exact last-saved preview guard, native `confirm()` and field focus. Implement token-based CSS, 18–24px checkbox, visible focus, non-color status, safe-area inset and Fira Sans.
- [ ] Run: `cd reference_scaffold && pytest -q tests/test_admin_ux_browser.py -v`; expected PASS.
- [ ] Commit: `git add reference_scaffold/cafeteria/static/admin.js reference_scaffold/cafeteria/static/app.css reference_scaffold/tests/test_admin_ux_browser.py && git commit -m 'feat: make admin editor responsive and accessible'`.

## Wave 5 — Integration, Reviews, Migration/Restore, Compose and Live Proof

### Task 11: Contract and full regression gates

**Files:** Existing implementation/test files only; no new production dependencies.

- [ ] Run from `reference_scaffold`: `pytest -q`; preserve verbatim output and exit code.
- [ ] Run schema/package validators, Ruff, Bandit and secret scan as configured by the repository; record each command and verbatim receipt separately, including any unavailable gate as BLOCKED.
- [ ] Run `gitnexus_detect_changes()` and confirm only planned symbols/flows changed. Run `rtk ocr review --repo /nvmetank1/projects/menuplan --from origin/main --to docs/admin-redesign-plan-v1 --format json --audience agent` and record `OCR:` summary.
- [ ] Obtain independent read-only AGY and Grok reviews of the diff/plan; HIGH/CRITICAL finding blocks progression.

### Task 12: PG16 migration, restore and deployment proof

**Files:** `reference_scaffold/tests/test_deployment_compose_probe_live.py`, `test_deployment_restore_live.py`, `test_deployment_restore_recovery.py`, `test_capture_live_screenshots.py`, `reference_scaffold/README.md`.

- [ ] Take and record a named PostgreSQL backup plus a down-probe copy before migration; execute Compose PG16 migration and verify schema 13, grants, idempotence and rollback.
- [ ] Restore v12 probe data, run the documented restore path, verify exact legacy/free-text behavior and no accidental `dish_templates` change.
- [ ] Run Chromium and existing CI-browser checks over all four viewports, keyboard/focus, errors/retry, Copy/Preview/Publish; capture authenticated admin smoke screenshots and a proof ZIP.
- [ ] Deploy only after all receipts exist: backup ID, schema-13 migration, immutable image digest, healthcheck and authenticated admin smoke. Record rollback/restore probe; no claim from `pytest` alone.
- [ ] Final verification: `rtk claude-wp-verify --branch docs/admin-redesign-plan-v1 --base origin/main`; confirm non-empty plan diff, no staged-leak, and exact ownership.
- [ ] Commit the plan-only branch exactly with `git add docs/superpowers/plans/2026-09-02-dishboard-admin-redesign.md && git commit -m 'docs: plan Dishboard admin redesign'`.

## Self-review checklist

- [ ] Cross-check every SDD section: 28/10 raster, no patient prices, full-replace exception, three modes, location/profile isolation, migration/backfill/down-probe, exact routes/keys/statuses, last-saved Preview, review/stale immutable Snapshot, A11y viewport matrix, backup/restore and stop conditions.
- [ ] Scan this plan for vague or undefined instructions; replace each with exact keys, signatures, test names and commands before commit.
- [ ] Verify shared-file serial ownership: `schema.sql`, `db.py`, `workflow_store.py`, `workflow.py`, `workflow_snapshot.py`, and `admin/routes.py` have one owner per wave; review lanes are read-only.
