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
- Null oder mehrere aktive konfigurierte Locations liefern HTTP 503. Eine
  fehlende gespeicherte Draft-/Preview-Ressource, ein ungültiger Raster-Slot
  oder ein Scope-Leak liefert HTTP 404. Ein gültiger fehlender Item-Slot ist
  dagegen eine virtuelle `row_version=0`-Zeile und kann seine Woche/Service
  beim ersten Save nach dem unten definierten Vertrag anlegen.
- Vor Symboländerungen Impact-Analyse via GitNexus, vor Commit `gitnexus_detect_changes`; vor Abschluss OCR, `claude-wp-verify`, unabhängige AGY- und Grok-Reviews.
- Fehlendes Backup, unklarer Scope, stale Version, HIGH/CRITICAL-Review oder fehlende Auth-/Browser-Evidenz bedeutet BLOCKED; kein Push/Deploy.

## File Map and Shared Interfaces

| Phase | Files | Responsibility / owner boundary |
|---|---|---|
| 1 | `database/schema.sql`, `database/migrations/0010_v12_to_v13.sql`, `database/migrations/0011_v13_to_v14.sql`, `database/permissions.sql`, `database/validate_schema.py`, `database/README.md`, `tools/validate_package.py`, `PACKAGE_CONTENTS.txt`, `MANIFEST_SHA256.txt`, `reference_scaffold/cafeteria/db.py`, `reference_scaffold/tests/test_component_catalog_migration_db.py`, `reference_scaffold/tests/test_component_metadata_master_lock_db.py`, `reference_scaffold/tests/test_auth_database.py`, `reference_scaffold/tests/test_database_invariants.py` | Schema v14, idempotente Migrationen, Restore-ACLs, Validator-/Package-Pins, Migration-Backfill und schmaler Metadata-Master-Lock; je Wave genau ein serialer Owner für `schema.sql` und `db.py`. |
| 2 | `reference_scaffold/cafeteria/component_catalog_store.py`, `reference_scaffold/cafeteria/component_catalog_metadata.py`, `reference_scaffold/cafeteria/component_assignment_store.py`, `reference_scaffold/cafeteria/workflow.py`, `reference_scaffold/cafeteria/workflow_snapshot.py`, `reference_scaffold/tests/test_component_catalog_db.py`, `reference_scaffold/tests/test_component_catalog_metadata_db.py`, `reference_scaffold/tests/test_component_assignment_db.py`, `reference_scaffold/tests/test_admin_workflow_db.py` | Katalog samt atomaren Label-/Allergen-Metadaten, Scope/Location, Assignment, Auto/Manual-Auflösung, Review und Snapshot. Katalog- und Assignment-Operationen bleiben in den jeweiligen Stores; die private Metadatenhilfe hält Produktionsmodule unter 400 Zeilen; `workflow.py` verdrahtet sie. |
| 3 | `reference_scaffold/cafeteria/__init__.py`, `reference_scaffold/cafeteria/admin/routes.py`, `reference_scaffold/cafeteria/admin/workflow_routes.py`, `reference_scaffold/cafeteria/workflow_partial_form.py`, `reference_scaffold/cafeteria/workflow_partial_store.py`, `reference_scaffold/cafeteria/workflow_copy_store.py`, `reference_scaffold/cafeteria/workflow_store.py`, `reference_scaffold/tests/test_component_catalog_routes.py`, `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_admin_week_routes.py`, `reference_scaffold/tests/test_admin_draft_preview.py`, `reference_scaffold/tests/test_workflow_partial_store_db.py`, `reference_scaffold/tests/test_workflow_copy_store_db.py` | URL-Familien, exact Form Keys, scoped Resolver, Partial-Saves, route-unabhängige Vorwochen-Copy, Preview, Publish/PRG, 400/404/409/503/CSRF. `admin/routes.py` ist ein kleiner serieller Adapter; `workflow_routes.py` trägt die neuen Routen und `__init__.py` registriert das Blueprint einmal. CSV-Import/Recovery bleiben erhalten; `persist_draft_connection` nur für vollständigen Import/Recovery. |
| 4 | `reference_scaffold/cafeteria/templates/admin/cafeteria.html`, `reference_scaffold/cafeteria/templates/admin/patienten.html`, `reference_scaffold/cafeteria/templates/admin/components.html`, `reference_scaffold/cafeteria/templates/admin/component_editor.html`, `reference_scaffold/cafeteria/templates/admin/preview.html`, `reference_scaffold/cafeteria/static/admin.js`, `reference_scaffold/cafeteria/static/app.css`, `reference_scaffold/tests/test_rendered_ui.py`, `reference_scaffold/tests/test_admin_ux_browser.py` | Novice-Übersicht/Editor, Templates, JS-State/Dirty-Guard, CSS, Render- und Browser-A11y. Neue Templates nur nach bestehendem Projekt-Generator prüfen. |
| 5 | alle vorgenannten Tests plus `reference_scaffold/tests/test_deployment_compose_probe_live.py`, `reference_scaffold/tests/test_deployment_restore_live.py`, `reference_scaffold/tests/test_deployment_restore_recovery.py`, `reference_scaffold/tests/test_capture_live_screenshots.py`, `reference_scaffold/README.md` | Integration, unabhängige Reviews, Backup/Migration/Restore, Compose, unveränderlicher Digest, Live-Proof. |

Verbindliche Python-Schnittstellen, die nach Phase 1/2 für spätere Phasen gelten. `AdminScope` wird aus der authentifizierten Session und der serverseitigen Location-Auflösung gebaut, nie aus Form oder Query:

```python
@dataclass(frozen=True)
class AdminScope:
    actor_id: int
    location_id: int
    profile_code: str

@dataclass(frozen=True)
class WeekRef:
    week_id: int
    location_id: int
    profile_code: str
    week_start: date
    row_version: int

get_component(engine: Engine, scope: AdminScope, public_id: str, *,
              include_archived: bool = True) -> dict
resolve_week_ref(connection, scope: AdminScope, week_start: date, *,
                 for_update: bool = False) -> WeekRef
resolve_item_id(connection, scope: AdminScope, week_ref: WeekRef, day: str,
                meal: str, option: str, *, for_update: bool = False) -> int
persist_menu_item(engine: Engine, scope: AdminScope, week_start: date, day: str,
                  meal: str, option: str, payload: Mapping[str, object],
                  expected_item_row_version: int) -> int
persist_week_header(engine: Engine, scope: AdminScope, week_start: date,
                    payload: Mapping[str, object], expected_week_row_version: int) -> int
persist_service_state(engine: Engine, scope: AdminScope, week_start: date,
                      day: str, meal: str, payload: Mapping[str, object],
                      expected_service_row_version: int) -> int
assign_component(engine: Engine, scope: AdminScope, item_id: int,
                 component_public_id: str | None, component_text: str | None,
                 expected_item_row_version: int) -> int
replace_component_links(engine: Engine, scope: AdminScope, item_id: int,
                        assignments: Sequence[Mapping[str, object]],
                        expected_item_row_version: int) -> int
replace_component_links_connection(connection, scope: AdminScope, item_id: int,
                                   assignments: Sequence[Mapping[str, object]]) -> None
resolve_component_effects(engine: Engine, scope: AdminScope, item_id: int) -> dict[str, object]
get_component_review_token(engine: Engine, scope: AdminScope, item_id: int) -> str
review_component(engine: Engine, scope: AdminScope, item_id: int,
                 component_version: str, expected_item_row_version: int) -> int
copy_previous_week(engine: Engine, scope: AdminScope, target_week_start: date,
                   target_row_version: int) -> int
build_snapshot(profile_code: str, draft: dict[str, Any], revision_code: str) -> dict[str, Any]
parse_draft_form(profile_code: str, form: Mapping[str, str]) -> ParsedDraft
```

`parse_draft_form(profile_code, form)` and `build_snapshot(profile_code, draft, revision_code)` retain these existing full-form/full-snapshot signatures. They are not reused as partial mutation APIs.

`WeekRef`, `resolve_week_ref` und `resolve_item_id` liegen in
`workflow_partial_store.py`. Sie prüfen ISO-Montag, Location,
URL-abgeleitetes Profil und Profilraster. Routes leiten Wochen- und
Item-Identität serverseitig ab; Formulare liefern weder `week_id` noch
`item_id` oder andere interne IDs.

Location resolution is fail-closed under the current single-location contract: `resolve_single_active_location_connection` returns the sole active location globally; zero or multiple active locations fail. Capability gates still validate the actor separately. For every operation on an existing week, load that week's `location_id` and require it to equal that sole active location.

`workflow_copy_store.py` owns the route-independent
`copy_previous_week` transaction and returns the committed target week
`row_version` as `int`. It derives the source as exactly
`target_week_start - 7 days` in the same Location and URL-derived profile; the
source is the latest committed saved draft and has no caller token. The route
may accept `source_week` only as an exact confirmation of the derived prior
Monday; a mismatch is 400 and never changes the store call. The complete Copy
matrix is specified in T6 and the SDD.

One global hierarchy governs every transaction:
`menu_weeks → menu_services → menu_items → menu_components →
menu_item_components → publication_revisions`. A transaction completes the
entire multirow set for one class before acquiring any lock in the next class;
caller/form order never changes acquisition. Within a class the order is:
weeks `(location_id, profile_id, week_start, id)`, services
`(menu_week_id, service_date, meal_period_id, id)`, items numeric `id ASC`,
components numeric `id ASC`, links `(menu_item_id, sort_order)`, and
publications `(menu_week_id, id)`.

Operation modes are binding: Header locks its week `FOR UPDATE`; Service locks
week → service → every affected item `FOR UPDATE`; Item create/update locks
week → service → item `FOR UPDATE`, then the component union `FOR SHARE`
and links `FOR UPDATE` if assignments change. Assign, Unassign and Replace lock
week → owning service → item → the complete existing-plus-requested
component union `FOR SHARE` → links `FOR UPDATE`. Review uses the same
sequence, locks week and service before the item, and its later week-actor
update is reentrant. Full
Import/Recovery locks week → all services → all items → the full component
union → all links. Publish locks week → all services → all items → the
full component union → all links → the active publication row. Copy locks
source and target weeks together in canonical week order, then all relevant
source/target services as one complete canonical set, all relevant
source/target items as one complete numeric-ID set, the source component
union, source links, and finally the target active-publication row. Catalog update/archive/unarchive locks only its
component `FOR UPDATE` and metadata children and never later acquires an
earlier-class lock; Create inserts only its new component/children. Standalone withdrawal locks only its publication row
and never later a week. Publish capability lookup may be nonlocking before the
transaction, but the transaction locks and revalidates the active publication
state last.

For every link writer the component union includes existing, archived,
removed and requested catalog references; free text has no component row.
Public IDs are resolved under Location plus `common`/current profile, new
archived assignments are rejected, and no caller supplies or receives an
internal component ID. Multi-item Import/Recovery prelocks week and all
services, all items, then the union, then **all** existing links before the
first helper call. Locks remain until commit/rollback.

`create_component` receives `engine`, `scope`, category, name and origin plus
`target_scope: Literal['common', 'current']`, `label_codes: Sequence[str]` and
`allergens: Sequence[tuple[str, Literal['contains', 'may_contain']]]`;
`current` maps only to the URL-derived `scope.profile_code`, and no API accepts
another concrete profile. Update receives the complete category/name/origin/
labels/allergens payload plus the expected version. Create, Find and Get
return records with exactly
`public_id,profile_scope,category,name,origin_country_code,active,row_version,usage_count,labels,allergens`.
A label has exactly `code,name`; an allergen has exactly
`code,name,presence`. Records and children use stable ordering and expose no
internal IDs or timestamps.

Catalog create/update rejects duplicate, unknown or invalid codes and validates
the complete replacement before deleting a child row. New child links require
active masters; an already-linked inactive master may remain unchanged, but
cannot be newly added or have its allergen presence changed. Parent and child
writes are atomic. A changed payload increments component `row_version`
exactly once; an identical complete payload is a true no-op and returns the
unchanged version.

Master validation uses exactly one call per outer catalog transaction to
`cafeteria.lock_component_metadata_masters(label_codes text[], allergen_codes
text[])`, with bound arrays. Schema v14 owns that SECURITY-DEFINER function;
it returns exactly `master_kind,master_id,code,active`, locks every requested
label by numeric ID before every requested allergen by numeric ID, and exposes
only `EXECUTE` to `cafeteria_app`. No App-role receives direct Master-`UPDATE`
or direct Master-`FOR SHARE` permission. T3b compares the complete returned
code set and evaluates inactive retention while keeping every internal
`master_id` DB-only.

Architecture A is binding. A catalog metadata update, archive or unarchive
mutates only the component and its child metadata and advances only the
component version. It never mutates linked items, reviews, weeks or any
materialized auto/manual item values. Existing assignments retain their stored
component version; a dynamic mismatch means `needs-review` and blocks publish.
Per-item review rematerializes auto effects, preserves every manual class
byte-identically, advances stored assignment versions and clears the mismatch.
The UI warns that affected dishes require review.
Every component API receives an engine/connection and `AdminScope`; assignment,
effects and review never accept an unscoped `item_id`. Review writes
`menu_weeks.updated_by=scope.actor_id` in derselben Transaktion; es ergänzt
keine unveränderliche Per-Item-Audit-Historie. Cross-location and cross-profile
attempts return 404.

### Dependency DAG and shared-file ownership

`T1 → T2 → T3 → T3a → T3b → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 → T12`. A task may start only after all predecessors have their committed receipt; review lanes are read-only and never unblock a failed prerequisite. T7, T8 and T9 form one serialized integration wave. No intermediate full-suite or deploy-ready claim is permitted after T7 removes legacy routes and before T9 lands the complete replacement surface.

| Shared file | Sole serial implementation owner and prerequisite |
|---|---|
| `database/schema.sql`, `database/permissions.sql`, `reference_scaffold/cafeteria/db.py` | T1, then T3a; T2 is tests-only and T3b never modifies schema/grants |
| `database/migrations/0010_v12_to_v13.sql` | T1 only; T3a and every later task preserve its bytes and registered checksum |
| `database/migrations/0011_v13_to_v14.sql` | T3a only |
| `reference_scaffold/cafeteria/component_catalog_store.py` | T3, then T3b; no parallel writer |
| `reference_scaffold/cafeteria/component_catalog_metadata.py` | T3b only; private helper, production modules each remain under 400 lines |
| `reference_scaffold/cafeteria/component_assignment_store.py` | T4, then T5; no parallel writer |
| `reference_scaffold/cafeteria/workflow.py` | T4, then T5, then T8; no parallel writer |
| `reference_scaffold/cafeteria/workflow_store.py` | T6 only; minimal Full-Import/Recovery compatibility edits, never Partial-Store |
| `reference_scaffold/cafeteria/workflow_partial_store.py`, `reference_scaffold/cafeteria/workflow_copy_store.py` | T6 only; scoped identity/persistence and route-independent Copy |
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

- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_migration_db.py tests/test_auth_database.py tests/test_database_invariants.py -k 'schema or migration or grant'`; expected initial FAIL naming missing migration/schema-13 contract.
- [ ] Implement only migration/schema/grant/validator/package-contract changes.
  Preserve `0001`–`0009` byte-identically. Migration `0010` itself must, in
  this order: create the tables; add mode/link columns nullable or with a safe
  default; set every legacy `allergen_mode`, `origin_mode` and `label_mode` to
  `manual`; backfill exact legacy text deterministically per Location/Profile/
  `other` component and exact links/versions; dedupe legacy allergens with
  `contains` winning. Project legacy allergen/label metadata only when an item
  has exactly one component row; multi-component items get no component
  metadata projection, while their item rows, `manual` modes and origins stay
  unchanged; run completeness checks; then add constraints, FKs,
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
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_migration_db.py tests/test_auth_database.py tests/test_database_invariants.py -v`; expected PASS.
- [ ] Stage: `rtk git add database/schema.sql database/migrations/0010_v12_to_v13.sql database/permissions.sql database/validate_schema.py database/README.md tools/validate_package.py PACKAGE_CONTENTS.txt MANIFEST_SHA256.txt reference_scaffold/cafeteria/db.py reference_scaffold/tests/test_component_catalog_migration_db.py reference_scaffold/tests/test_auth_database.py reference_scaffold/tests/test_database_invariants.py`.
- [ ] Commit: `rtk git commit -m 'feat: add v13 component catalog migration'`.

### Task 2: Legacy backfill and invariants

**Files:** Test `reference_scaffold/tests/test_database_invariants.py` and
`reference_scaffold/tests/test_public_isolation_homoglyphs.py`; migration
backfill remains in `database/migrations/0010_v12_to_v13.sql`, not `db.py`.

**Interfaces:** Legacy text becomes one exact component per location/profile/category `other`; unmatched references remain valid free text. Existing menus use `manual` for all three classes; duplicate legacy allergens prefer `contains`. Legacy allergen/label metadata is projected only for an item with exactly one component row; multi-component items receive no component metadata projection, and their item rows, `manual` modes and origins remain unchanged.

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

**Interfaces:** Catalog-store functions take `engine: Engine` and
`scope: AdminScope`; they never accept a caller-supplied location/profile. For
existing-week operations, the scope's location must equal the loaded week
location. Catalog create/search require the sole active location globally;
zero/multiple active locations are errors, and capability gates validate the
actor separately. `create_component(engine, scope, category, name,
origin_country_code, target_scope: Literal['common', 'current']) -> dict` maps
`current` only to the URL-derived `scope.profile_code` and never accepts
another concrete profile. `find_components`, `update_component`,
`archive_component` and `unarchive_component` all receive the same scoped
engine contract. `get_component(engine, scope, public_id, *,
include_archived=True) -> dict` is the sole scoped detail API consumed by T7.
Create, Find and Get return exactly
`public_id,profile_scope,category,name,origin_country_code,active,row_version,usage_count,labels,allergens`,
with no internal IDs or timestamps. T3 establishes base CRUD and empty child
arrays; T3b adds atomically managed metadata without changing the record shape.

- [ ] Add RED CRUD/search/usage/archive tests, including the exact uniform
  Create/Find/Get record keys, empty ordered `labels`/`allergens`,
  archived-detail default, reserved archived names, exact category
  filtering, sorting, 409 stale updates, `common|current` target-scope mapping
  and cross-location/profile 404.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_db.py`; expected FAIL with missing catalog operations.
- [ ] Implement row locks, exact keys, location/profile filtering and public-ID lookup; return usage counts without exposing internal IDs.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/component_catalog_store.py reference_scaffold/tests/test_component_catalog_db.py`.
- [ ] Commit: `rtk git commit -m 'feat: add scoped component catalog store'`.

### Task 3a: Schema-v14 metadata-master lock capability

**Files:** Create `database/migrations/0011_v13_to_v14.sql` and
`reference_scaffold/tests/test_component_metadata_master_lock_db.py`; modify
`database/schema.sql`, `database/permissions.sql`, `database/validate_schema.py`,
`database/README.md`, `tools/validate_package.py`, `PACKAGE_CONTENTS.txt`,
`MANIFEST_SHA256.txt`, `reference_scaffold/cafeteria/db.py`,
`reference_scaffold/tests/test_component_catalog_migration_db.py`,
`reference_scaffold/tests/test_auth_database.py` and
`reference_scaffold/tests/test_database_invariants.py`. Migration
`database/migrations/0010_v12_to_v13.sql` and its registered checksum are
immutable.

**Interfaces:** Register `SCHEMA_VERSION = 14`, `APPLICATION_VERSION =
'dishboard-schema-v14'` and migration `0011`. Fresh schema and migration create
exactly the SDD-defined
`cafeteria.lock_component_metadata_masters(text[], text[]) RETURNS TABLE
(master_kind text, master_id smallint, code text, active boolean)`. It is
`LANGUAGE plpgsql SECURITY DEFINER VOLATILE PARALLEL UNSAFE`, has fixed
`search_path = pg_catalog, cafeteria, pg_temp`, uses only fully qualified
static SQL, rejects null arrays and null elements with SQLSTATE `22023`, and
locks label rows by `id ASC` before allergen rows by `id ASC`. The function
owner equals the `cafeteria` schema owner and is never `cafeteria_app`.
`PUBLIC`, `cafeteria_backup` and `cafeteria_auth_issuer` have no Execute;
`cafeteria_app` has only Execute on the helper and receives no Master-table
Update grant. Internal IDs returned by the helper never cross an HTTP or
public Store boundary.

- [ ] Add RED real-PG16 tests for v13→v14 migration, fresh-schema and restore
  parity: exact version/application/registry values, function definition,
  owner, fixed search path, volatility/parallel flags, return columns and
  ACLs. Assert the v13 migration file and registered checksum remain
  byte-identical.
- [ ] Prove direct `cafeteria_app` Master `UPDATE` and direct `SELECT ... FOR
  SHARE` stay denied, while exact helper Execute succeeds. Prove
  `PUBLIC`, `cafeteria_backup` and `cafeteria_auth_issuer` cannot execute it;
  rerunning `database/permissions.sql` idempotently removes accidental broad
  grants and restores only the narrow App Execute grant.
- [ ] With two independently synchronized PG16 connections and no timing
  sleeps, pass reversed requested-code arrays and prove locks are nevertheless
  acquired as all labels by `id ASC`, then all allergens by `id ASC`. A schema-
  owner update to one requested Master must block until the App transaction
  commits, while an unrelated Master stays writable; opposite-order calls must
  complete without `40P01`.
- [ ] Cover empty arrays, duplicates (one result per matching Master row),
  unknown codes (omitted for T3b's full-set comparison), inactive rows
  (returned for T3b's retention policy), null arrays/elements, SQL-looking code
  strings and `pg_temp` shadow objects. Calls bind arrays and never interpolate
  code text. Update the SECURITY-DEFINER allowlist to contain this exact
  signature and no wildcard.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_metadata_master_lock_db.py tests/test_component_catalog_migration_db.py tests/test_auth_database.py tests/test_database_invariants.py`; expected initial FAIL, then PASS after implementation.
- [ ] Implement migration, fresh-schema function, narrow Restore permissions,
  v14 registry/validators/package metadata and owner parity. Callers are not
  added here; T3b consumes the helper once per outer transaction. Never grant
  Master `UPDATE`, never weaken row security, and never edit migration `0010`.
- [ ] Stage: `rtk git add database/schema.sql database/migrations/0011_v13_to_v14.sql database/permissions.sql database/validate_schema.py database/README.md tools/validate_package.py PACKAGE_CONTENTS.txt MANIFEST_SHA256.txt reference_scaffold/cafeteria/db.py reference_scaffold/tests/test_component_metadata_master_lock_db.py reference_scaffold/tests/test_component_catalog_migration_db.py reference_scaffold/tests/test_auth_database.py reference_scaffold/tests/test_database_invariants.py`.
- [ ] Commit: `rtk git commit -m 'feat: add narrow component metadata master locks'`.

### Task 3b: Atomic component labels and allergens

**Files:** Modify
`reference_scaffold/cafeteria/component_catalog_store.py` and
`reference_scaffold/tests/test_component_catalog_db.py`; create the private
`reference_scaffold/cafeteria/component_catalog_metadata.py`; create
`reference_scaffold/tests/test_component_catalog_metadata_db.py`. Keep each
production module below 400 lines.

**Interfaces:** Extend `create_component` with
`label_codes: Sequence[str]` and
`allergens: Sequence[tuple[str, Literal['contains', 'may_contain']]]`.
`update_component(engine, scope, public_id, payload, version) -> int` accepts
one complete payload with exactly
`category,name,origin_country_code,label_codes,allergens`. Create, Find and Get
all return the same exact public keys:
`public_id,profile_scope,category,name,origin_country_code,active,row_version,usage_count,labels,allergens`.
Each label is exactly `code,name`; each allergen exactly
`code,name,presence`. Sort labels by `(code ASC, name ASC)` and allergens by
`(code ASC, presence ASC, name ASC)`; expose no internal IDs or timestamps.
For Create and Update, invoke
`cafeteria.lock_component_metadata_masters(:label_codes, :allergen_codes)`
exactly once with bound arrays in the same outer transaction. Before that call,
reject duplicate Label request codes and duplicate Allergen request codes
independently; an identical code occurring once in each namespace remains
valid. Partition returned rows by `master_kind`; reject every kind except
`label|allergen` and every duplicate `(master_kind, code)`. Compare requested
Label codes exactly to returned Label codes and, separately, requested Allergen
codes exactly to returned Allergen codes before applying inactive-master
retention rules or deleting any child. T3b may not edit schema, migration or
grant files.

- [ ] Migrate `reference_scaffold/tests/test_component_catalog_db.py`:
  expand `OUTPUT_KEYS` from 8 to the exact 10 public keys above, update
  expected records and `create_component` helper calls, and add `label_codes`
  and `allergens` to every old 3-field update payload.
- [ ] Add focused RED real-PG16 tests for parent-plus-children atomicity,
  stable ordering, exact public keysets, duplicate/unknown/invalid labels,
  duplicate/unknown/invalid allergen pairs and stale update 409. Include one
  valid request whose Label and Allergen namespaces contain the identical code,
  plus controlled failures for an unknown `master_kind` and duplicate
  `(master_kind, code)` helper rows; prove the two exact per-kind returned sets
  are compared independently. Every metadata child writer locks its parent
  component `FOR UPDATE`, validates the complete replacement before any delete
  and replaces children deterministically. New links require active masters;
  already-linked inactive masters may remain unchanged but cannot be added or
  have presence changed.
- [ ] Add tests proving a changed full payload increments component
  `row_version` exactly once, while an identical full payload is a true no-op
  with the same returned version. Cover exact scoped output and active/inactive
  master retention/add/change validation. Add synchronized catalog-only
  create/update/archive/unarchive races in both winner orders, without timing
  sleeps, proving deterministic parent/child state, no `40P01` and no partial
  mutation. Assignment, Unassignment, Review, item healing and Publish are
  deliberately absent from T3b and deferred to T4, T5 and T8, where those APIs
  exist.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_metadata_db.py`; expected FAIL.
- [ ] Implement the private metadata resolver/validator and transactional
  parent/child replacement. Reject duplicates, unknown codes, invalid presence
  and inactive-master changes before deleting. Use only T3a's helper for the
  privileged Master locks; do not add a direct `FOR SHARE`, grant or schema
  edit. Remove any fanout or
  rematerialization-on-catalog-edit behavior; catalog writes touch only the
  locked component and child rows and advance the parent version once.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_db.py tests/test_component_catalog_metadata_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/component_catalog_store.py reference_scaffold/cafeteria/component_catalog_metadata.py reference_scaffold/tests/test_component_catalog_db.py reference_scaffold/tests/test_component_catalog_metadata_db.py`.
- [ ] Commit: `rtk git commit -m 'feat: add atomic component metadata'`.

### Task 4: Assignment resolution and independent modes

**Files:** Create `reference_scaffold/cafeteria/component_assignment_store.py`; modify `reference_scaffold/cafeteria/workflow.py`; test `reference_scaffold/tests/test_component_assignment_db.py`.

**Interfaces:** `assign_component(engine: Engine, scope: AdminScope, item_id: int, component_public_id: str | None, component_text: str | None, expected_item_row_version: int) -> int`; `replace_component_links(engine: Engine, scope: AdminScope, item_id: int, assignments: Sequence[Mapping[str, object]], expected_item_row_version: int) -> int`; `replace_component_links_connection(connection, scope, item_id, assignments) -> None`; `resolve_component_effects(engine: Engine, scope: AdminScope, item_id: int) -> dict[str, object]`; modes are independently `allergen_mode`, `origin_mode`, `label_mode`. No assignment/effects API accepts an unscoped `item_id`. The engine-level replace API starts one transaction, locks the scoped week, then its owning service, then the scoped item, version-checks the item, calls the connection helper, rematerializes auto classes, resets review, bumps the item version exactly once and returns the new version. The connection helper validates every assignment, enforces location/profile scope and replaces all links inside its caller's transaction; it never commits or updates the item/review/version. T4 single-link/full-replace assignment and T6 partial/full Import/Recovery persistence use this helper; each one-item caller performs exactly one locked item update, review reset and version bump.

Every `assignments` element has exactly the two keys
`component_public_id` and `component_text`, with exactly one non-null value. A
catalog entry is `{"component_public_id": str, "component_text": None}`; the
server resolves it under scope and stores the component's current `name` and
`row_version`. A free-text entry is `{"component_public_id": None,
"component_text": str}`; `btrim(component_text)` must be nonblank, but the
original string is stored byte-identically. Reject both/neither values and all
unexpected keys, including internal IDs, supplied component versions, prices
and `sort_order`. Sequence position alone maps to persisted `sort_order` 1..n.
`assign_component` atomically appends exactly one valid entry to the existing
ordered list. Unassign is a full `replace_component_links` whose target list
omits the entry; `[]` removes all links. Reject duplicate newly requested
active catalog components. For an already-linked archived component, requested
multiplicity may not exceed its existing multiplicity, so no new archived
assignment can be introduced.

Every one-item engine caller locks the scoped week, its owning service, the
item, the complete existing-plus-requested component union, then links. On
success it updates links, rematerializes auto classes, resets review and bumps
only the item `row_version` exactly once. It never updates week/service rows or
versions and never changes a component. The connection helper performs only
validated link replacement inside those caller-held locks.

Auto origins exclude catalog components whose `origin_country_code` is
`NULL` and every free-text link. Each remaining component yields exactly
`ingredient = current component.name`, `country_code = origin_country_code`
using the canonical ISO code, and
`text = f"{component.name}: {origin_country_code}"`. Equal current component
names with different countries abort the whole mutation; no partial link,
effect, review or version write survives.

- [ ] Add RED tests for same-location/common-or-profile scope, cross-location/
  profile 404 assignment and effects, allergen union with `contains` winning,
  exact origin mapping/NULL exclusion and atomic same-name/different-country
  conflict, diet intersection, nullable/free-text non-inheritance, and
  auto-only rematerialization. Directly test the connection helper inside one
  caller-owned transaction and prove it neither commits nor changes
  item/review/version itself.
- [ ] Test the exact two-key assignment mapping, exactly-one-non-null rule,
  byte-preserved nonblank free text, current catalog name/version capture,
  sequence-to-`sort_order` mapping, rejection of every extra/internal/version/
  price/sort key, atomic append, omission/empty-list Unassign, active duplicate
  rejection and archived-multiplicity cap. Assert invalid inputs cause zero
  mutation.
- [ ] For `replace_component_links`, assert the winner returns exactly
  `old_row_version + 1`, resets review, rematerializes every auto effect and
  preserves every manual class byte-identically.
- [ ] Add separate mandatory real-PG16 synchronized two-connection SAME-item
  races for `assign_component` and `replace_component_links`. Use no
  timing sleeps. Both calls submit the same expected row version. Each proves
  exactly one winner, no deadlock/`40P01`; the loser waits, then returns stale
  409 with zero mutation, and final links exactly match the winner.
- [ ] Add synchronized barrier/event real-PG16 catalog-edit versus Assign and
  catalog-edit versus Unassign tests in both winner orders. Assert the loser
  blocks at the week lock where applicable, no `40P01`, no mixed link/catalog
  state and no partial mutation under the global hierarchy; catalog edit never
  fans out to an item/week, and surviving assignments retain the version they
  actually bound.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_assignment_db.py`; expected FAIL.
- [ ] Implement assignment validation and deterministic effects. Reject injected patient prices before any write. Route `assign_component` and `replace_component_links` through `replace_component_links_connection`; each engine-level caller locks the scoped week, owning service and scoped item in that order, checks `expected_item_row_version`, then performs exactly one review reset and item-version bump and returns the new version. Before link locks or writes, resolve the complete existing-plus-requested component set, lock it by numeric internal ID, then lock and mutate links in the global order above; caller-supplied internal IDs are forbidden. On component/link change rematerialize only auto classes; manual values remain untouched. Assert the week, service and component rows remain byte- and version-identical.
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
component versions. `get_component_review_token(engine: Engine, scope:
AdminScope, item_id: int) -> str` returns a Single-Use-Pre-Review-Token:
`sha256:` followed by exactly 64 lowercase hex characters. It is an optimistic
concurrency value, not an authorization secret. Its object has exactly these
eight top-level keys and types: `item_row_version: int > 0`,
`allergen_mode|origin_mode|label_mode: 'auto'|'manual'`, plus the four lists
`components`, `labels`, `allergens`, `origins`. A component has exactly
`sort_order: int > 0,component_public_id: str|null,component_text: str,stored_component_row_version: int|null,current_component_row_version: int|null`;
a label exactly `code: str,name: str`; an allergen exactly
`code: str,name: str,presence: 'contains'|'may_contain'`; an origin exactly
`ingredient: str,country_code: str,text: str`. No other `null` is allowed.
Components are ordered by `sort_order ASC`, labels by `(code ASC, name ASC)`,
allergens by `(code ASC, presence ASC, name ASC)`, and origins by
`(ingredient ASC, country_code ASC, text ASC)`. UUIDs use canonical lowercase;
other strings are not trimmed, case-folded or Unicode-normalized. Digest bytes
are exactly
`json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')`
without BOM/trailing newline; prefix `sha256:` is not hashed. Review status is
excluded.

The mandatory golden test hashes this exact one-line UTF-8 JSON string:

```json
{"allergen_mode":"auto","allergens":[{"code":"A","name":"Gluten","presence":"contains"},{"code":"B","name":"Milch","presence":"may_contain"}],"components":[{"component_public_id":"11111111-1111-4111-8111-111111111111","component_text":"Rind & Crème","current_component_row_version":4,"sort_order":1,"stored_component_row_version":3},{"component_public_id":null,"component_text":"Freitext","current_component_row_version":null,"sort_order":2,"stored_component_row_version":null}],"item_row_version":7,"label_mode":"manual","labels":[{"code":"L1","name":"Hausgemacht"}],"origin_mode":"auto","origins":[{"country_code":"CH","ingredient":"Rind","text":"Rind: CH"}]}
```

Expected result is exactly
`sha256:b3526f90550974218338f0f890d8f02a524cfad0dee40ae387074883691e7428`.

`review_component(engine: Engine, scope: AdminScope, item_id: int,
component_version: str, expected_item_row_version: int) -> int` interprets
`component_version` as that pre-review token. In one transaction it locks in
this order: the scoped week `FOR UPDATE`; its owning scoped
`menu_services` row `FOR UPDATE`; the scoped `menu_items` row `FOR UPDATE`;
all components resolved
from its current links, including archived components, by numeric
`menu_components.id ASC FOR SHARE`; then all current
`menu_item_components` rows via
`ORDER BY menu_item_id, sort_order FOR UPDATE`. This is the same
`week → service → item → components → links` order and compatible component-lock mode required
of every link writer. The item lock prevents phantom link insertion while
review derives the component set and verifies the token. Locks remain through
commit/rollback. Only after all locks does review reread scope, expected item
version, current component versions and effective Auto/Manual values, then
recompute/compare the token. A concurrent write that wins before a required
lock yields atomic 409; a later writer waits. Foreign scope yields atomic 404.
On success review rematerializes current auto classes, advances stored link
versions, refreshes each catalog-linked `component_text` from the current
catalog name while preserving free text byte-identically, marks checked,
increments item row version exactly once, updates
`menu_weeks.updated_by=scope.actor_id`, and returns the new row version. The
route responds 303/PRG to the scoped item GET. Success consumes the submitted
token because item/link versions change; repeating the old body yields 409
without mutation. A component edit after commit makes publish stale until a
new review. No immutable per-item audit history, schema change or permission
expansion is added.

A catalog edit may create two current linked components with the same name but
different origin countries without touching the linked item. The stored/current
component-version mismatch still yields dynamic `needs_review` and blocks
Publish. When `origin_mode == 'auto'`, both
`get_component_review_token` and `review_component` raise the named controlled
domain conflict `AutoOriginConflictError` while resolving those current origins.
That failure atomically writes no link, effective value, review, item or week
row. When `origin_mode == 'manual'`, origin resolution is skipped: manual
origins remain byte-identical and Review can succeed despite the same catalog
auto-origin conflict.
The existing full
`publish_draft(engine, profile_code, week_start, *, expected_row_version,
actor_id, issuer_engine)` signature, replacement-publication capability flow,
503 configuration behavior and App-role test remain preserved; it rejects
unreviewed/stale components and stores an immutable revision.

Load, Status and Publish reuse one central predicate:
`review_open/needs_review = allergen_review_status != 'checked' OR EXISTS(stored linked_component_version <> current component row_version)`.
A persisted `checked` value can therefore never conceal a stale component
link. Publish locks the week, every service in canonical order, every scoped
week item by numeric ID ASC, the complete component union by numeric ID ASC
`FOR SHARE`, all links globally by `(menu_item_id, sort_order) FOR UPDATE`, and
the active publication row last. Under those locks it rereads status,
publication state and versions before building the immutable snapshot. T8 owns
this central Publish-lock implementation and its concurrency gates; T5 only
defines the shared predicate and snapshot/review behavior it consumes.

- [ ] Add RED tests asserting exact snapshot keys/types, no forbidden metadata,
  immutability after source edits, the literal golden input/digest above,
  complete-state array ordering and exact key/type rejection. Add two-connection
  races proving deterministic `scoped week FOR UPDATE → owning scoped service
  FOR UPDATE → scoped item FOR UPDATE → complete current referenced component
  union by numeric id ASC FOR SHARE → current links by (menu_item_id ASC,
  sort_order ASC) FOR UPDATE` locking held through commit, atomic 404/409,
  successful new row version plus 303/PRG, old-token repeat-submit 409, atomic
  week actor attribution, cross-location/profile 404, review invalidation,
  and exact predicate results. Assert that review refreshes catalog-backed
  `component_text`, preserves free text and every manual class byte-identically,
  and heals only the reviewed item.
- [ ] Add real-PG16 tests where a catalog edit creates same-name/different-country
  origins on an already linked item. Assert dynamic `needs_review` plus Publish
  block; `get_component_review_token` and `review_component` each raise
  `AutoOriginConflictError` only in Auto mode with zero link/effect/review/item/week
  writes. Assert Manual mode keeps origins byte-identical and Review succeeds.
- [ ] Add synchronized barrier/event real-PG16 catalog-edit versus Review tests
  in both winner orders, including one `common` component shared across
  profiles/weeks. Assert Review first locks the week, no `40P01` or partial
  mutation occurs, only the reviewed item heals, Auto classes rematerialize,
  every Manual class stays byte-identical, and a persisted `checked` value
  never conceals a current/stored component-version mismatch.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_workflow_db.py`; expected FAIL.
- [ ] Implement deterministic snapshot materialization and review transaction.
  Review locks `scoped week FOR UPDATE → owning scoped service FOR UPDATE →
  scoped item FOR UPDATE → complete current referenced component union by
  numeric id ASC FOR SHARE → current links by (menu_item_id ASC, sort_order ASC)
  FOR UPDATE`, holds all locks through commit, rereads state, compares
  `expected_item_row_version` and
  the complete-state token, rematerializes current auto classes, advances
  stored link versions, marks checked, increments item version once and later
  updates the week actor reentrantly. Expose the shared
  `review_open/needs_review` predicate for T8's locked Publish path.
  Leave all tables unchanged on every 400/409; reject exact repeat submission
  with 409.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_workflow_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/workflow_snapshot.py reference_scaffold/cafeteria/workflow.py reference_scaffold/cafeteria/component_assignment_store.py reference_scaffold/tests/test_admin_workflow_db.py`.
- [ ] Commit: `rtk git commit -m 'feat: enforce reviewed immutable menu snapshots'`.

## Wave 3 — Partial Parser, Store Routes, Copy, Preview and Publish Security

### Task 6: Exact forms and partial persistence

**Files:** Create `reference_scaffold/cafeteria/workflow_partial_form.py` and
`reference_scaffold/cafeteria/workflow_partial_store.py`; create
`reference_scaffold/cafeteria/workflow_copy_store.py` and
`reference_scaffold/tests/test_workflow_copy_store_db.py`; minimally modify
the 454-line `reference_scaffold/cafeteria/workflow_store.py`; test
`reference_scaffold/tests/test_workflow_form.py` and create
`reference_scaffold/tests/test_workflow_partial_store_db.py`. T6 is the sole serial owner
of `workflow_store.py`: retain full-form/full-replace Import/Recovery behavior,
replace its `ORDER BY ... LIMIT 1` location selection with
`resolve_single_active_location_connection` requiring exactly one globally
active location, make `_insert_item` explicitly write all three modes
`manual` for CSV/Recovery, and make `load_draft_connection` load all three
modes. Do not grow `workflow_form.py`; partial modules never call full replace.

**Interfaces:** Keep the existing full-form `parse_draft_form(profile_code, form) -> ParsedDraft` unchanged. `workflow_partial_form.py` provides separate exact partial parsers. `workflow_partial_store.py` owns scoped `WeekRef(week_id,location_id,profile_code,week_start,row_version)`, `resolve_week_ref(connection, scope, week_start, *, for_update=False) -> WeekRef`, `resolve_item_id(connection, scope, week_ref, day, meal, option, *, for_update=False) -> int`, and the exact Engine/AdminScope persistence APIs declared above. Resolvers enforce Location, URL-derived profile, ISO-Monday and raster; forms never supply internal week/item IDs. Menu requires exactly `_csrf,week,day,meal,option,row_version,title,allergen_mode,origin_mode,label_mode`; its `row_version` is exclusively the addressed `menu_items.row_version`, named `expected_item_row_version` after parsing. Permitted optional keys are `description,note,component_public_id[],component_text[],allergen_code[],allergen_presence[],origin_ingredient[],origin_country_code[],label_code[]`; cafeteria additionally requires `internal_chf,external_chf`, while patient rejects every price key. Header requires exactly `_csrf,week,row_version,title,shared_note`. Service requires exactly `_csrf,week,day,meal,row_version,service_state,notice`.

The scoped slot identity is derived entirely server-side as
`(location_id, profile_id, week_start, service_date, meal_period_id,
menu_type_id)`; no form contains a week, service, item, profile, meal-period or
menu-type internal ID. A valid raster slot with no item renders as a virtual
item with `row_version=0`, not 404. Invalid or foreign-scope slots remain 404.
Item-write outcomes are exact: expected 0 plus absent inserts version 1 and
returns 1; existing plus 0 is 409; missing plus positive is 404; mismatched
positive is 409; matching positive updates once and returns old+1. A missing
week is inserted in scope at version 1 with `ON CONFLICT`, after which the
winning row is locked; its missing service is created `open` at version 1.
An existing closed service yields atomic 409 and is never reopened. Existing
weeks set `updated_by` exactly once per successful item save; a newly inserted
week receives its actor during insert and is not redundantly updated.

Component Create has exact scalar keys
`_csrf,category,name,origin_country_code,target_scope` and repeated
`label_code,allergen_code,allergen_presence`. Update adds scalar `row_version`
and omits `target_scope`; Archive/Unarchive accept exactly
`_csrf,row_version`. Parsers reject duplicate scalars, mismatched repeated
allergen arrays, unexpected keys, `profile`, `profile_scope`, internal IDs and
master IDs.

`workflow_copy_store.py` provides
`copy_previous_week(engine, scope, target_week_start, target_row_version) -> int`.
It derives the source as the latest committed saved draft for the previous
Monday in the same scope and takes no source token. It copies week `title` and
`shared_note`, forces the target to `draft`, and never copies source IDs,
`public_id`, versions, timestamps, workflow state or actors. It replaces an
item-free target's service skeleton: copied services keep `service_state`,
notice and meal period at date +7, but receive new IDs/public IDs and version
1. Items copy menu type, `dish_template_id`, title, description, note,
`sort_order` and all three modes, but receive new IDs/public IDs, a target
`external_id` and version 1; every review resets to `not_checked`.

Catalog links are re-resolved by public identity under component locks. An
active component produces a new assignment with its current name/version; a
stale active source link is safely rebased but remains unchecked; any archived
source component makes the whole Copy 409. Free text stays byte-identical.
Manual metadata is copied byte-semantically for each class whose mode is
`manual`; Auto metadata is recomputed under the locked component union and is
never cloned. `staff_guest` copies internal/external Rappen and currency;
`patient` creates no price, and an anomalous source patient price is atomic
409. Copy never copies publications or lifecycle state; an active target
publication is 409, while withdrawn target history stays untouched.

Target version results are exact: expected 0 plus absent target returns 1;
expected 0 plus existing target is 409; positive plus absent is 404; exact
positive `v` plus existing item-free target with no active publication updates
the week exactly once and returns `v+1`. Stale, nonempty or otherwise invalid
targets fail atomically. Two concurrent Copies with the same expectation have
exactly one winner. Copy racing the first item save produces one complete
winner with no hybrid target.

- [ ] Add RED parser tests for CHF dot/comma normalization to positive Decimal
  Rappen, patient price rejection, the exact required/optional keysets,
  unknown or duplicate scalar keys and misaligned list pairs as 400, profile
  raster rejection and German field-path errors.
- [ ] Add exact component-form tests for Create, Update, Archive and Unarchive,
  including duplicate scalars, mismatched allergen arrays and every forbidden
  profile/internal/master-ID key.
- [ ] Add RED real-PG16 App-role tests for stale and concurrent partial writes,
  absent/virtual-empty/partial/closed-service slots, exact 0/positive outcome
  matrix, byte-identical neighbours, no implicit deletes, and preserved full
  Import/Recovery behavior in `test_workflow_partial_store_db.py`. When either
  path writes component links, assert it uses the T4 helper and the global
  week/service/item/component/link lock order for existing archived,
  removed and new refs.
  Add the multi-item race here through the actual Full Import/Recovery batch
  implementation: two independent connections submit the same two scoped
  items with reversed item/assignment order and the same expected version,
  synchronized without timing sleeps. Prove exactly one winner; the loser gets
  stale 409 with zero mutation, and no deadlock/`40P01` occurs. Do not invent
  or test a T4 batch API.
- [ ] Add synchronized no-sleep races for the same valid missing slot at
  expected 0 (one version-1 winner, one 409) and two different valid missing
  slots (both serialize at the week lock and succeed). Assert valid absent
  slots render virtual row version 0, invalid/foreign slots 404, closed service
  409 without reopen, missing week/service creation semantics, exact actor
  write count, and no neighbouring mutation.
- [ ] Add route-independent real-PG16 Copy tests for exact prior-week source,
  latest committed draft, same Location/profile, the full target-version
  matrix, week/header/service/item field matrix, new identities, target dates,
  reset reviews, byte-identical free/manual values, recomputed Auto values,
  current active/stale/archived component behavior, exact staff_guest Rappen
  and currency, anomalous patient-price rejection, withdrawn-history
  preservation, active-publication rejection and never-publish behavior.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_workflow_form.py tests/test_workflow_partial_store_db.py tests/test_workflow_copy_store_db.py`; expected FAIL.
- [ ] Implement whitelist parsing and route-derived raster validation in the new
  partial modules. Each partial handler derives the complete scoped raster
  identity, locks week → service → item in the global hierarchy, and calls only `persist_menu_item`,
  `persist_week_header` or `persist_service_state`; never `persist_draft`/full
  replace. A closing nonempty service returns 409 and never silently deletes.
  Each partial mutation touches only its addressed entity and explicit child
  classes, byte-compares neighbours, header and publication as unchanged,
  bumps the week `row_version`, and resets relevant review atomically. Schema
  defaults are safely `manual` for all three modes. Component replacement uses
  T4's `replace_component_links_connection`; T6 duplicates no assignment SQL,
  and its caller performs exactly one locked item update, review reset and
  version bump. Full Import/Recovery locks its week and all services first,
  then pre-resolves and locks all affected items by numeric `menu_items.id ASC`,
  then resolves and locks the full component
  union by numeric `menu_components.id ASC`, then locks **all existing link
  rows for all affected items** globally by `(menu_item_id, sort_order)` before
  invoking the connection helper for the first item. It uses that helper for
  every component link it creates, preserves deterministic mutation order, and
  neither path accepts internal component IDs.
- [ ] With cwd `reference_scaffold` and disposable PG16 App-role fixture configured, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_workflow_form.py tests/test_workflow_partial_store_db.py tests/test_workflow_copy_store_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/workflow_partial_form.py reference_scaffold/cafeteria/workflow_partial_store.py reference_scaffold/cafeteria/workflow_copy_store.py reference_scaffold/cafeteria/workflow_store.py reference_scaffold/tests/test_workflow_form.py reference_scaffold/tests/test_workflow_partial_store_db.py reference_scaffold/tests/test_workflow_copy_store_db.py`.
- [ ] Commit: `rtk git commit -m 'feat: parse exact partial admin forms'`.

### Task 7: URL families, capabilities, Copy and Preview (serialized integration 1/3)

**Files:** Modify `reference_scaffold/cafeteria/__init__.py` and
`reference_scaffold/cafeteria/admin/routes.py` as a small serial adapter,
create `reference_scaffold/cafeteria/admin/workflow_routes.py` and
test `reference_scaffold/tests/test_component_catalog_routes.py`,
`reference_scaffold/tests/test_admin_week_routes.py`,
`reference_scaffold/tests/test_admin_workflow_routes.py`,
and `reference_scaffold/tests/test_admin_draft_preview.py`.
`__init__.py` registers the new blueprint exactly once. Remove/disable duplicate
old mega-form GET/save/publish routes without collisions, preserve CSV
Import/Recovery.

**Interfaces:** Register GET/POST routes exactly as specified in the SDD. `profile_from_endpoint('cafeteria') == 'staff_guest'`, `profile_from_endpoint('patienten') == 'patient'`; copy accepts `_csrf,source_week,target_week,target_row_version`, requires `source_week == target_week - 7 days` and calls only T6's route-independent `copy_previous_week` with the target. Preview renders last-saved draft only. Component detail handlers use only T3/T3b's scoped `get_component`, never route-local detail SQL. Component Create accepts exact scalar `_csrf,category,name,origin_country_code,target_scope` plus repeated `label_code,allergen_code,allergen_presence`; Update adds `row_version`, omits `target_scope` and submits the complete payload; Archive/Unarchive accept exactly `_csrf,row_version`. Reject duplicate scalar keys, mismatched repeated arrays, unexpected keys, `profile`, `profile_scope`, internal IDs and master IDs. T7 calls `get_component_review_token` to render the review token. `POST /admin/{cafeteria|patienten}/menu/review` requires `draft.write`, accepts exactly `_csrf,week,day,meal,option,row_version,component_version`, resolves the scoped item from the raster fields, rejects any `item_id`, and passes both token and row version to `review_component`; missing Review item/scope failures are atomic 404 and stale row/token failures atomic 409. Zero/multiple configured active locations map to 503; missing saved draft/preview resources and invalid/out-of-scope slots map to 404, while a valid missing menu slot renders virtual `row_version=0`.

Both review-token GET rendering and review POST catch only the named
`AutoOriginConflictError` domain error and map it to controlled HTTP 409, never 500.
The rendered error region shows exactly the actionable German recovery
`Herkunftskonflikt: Komponente bearbeiten oder Herkunft dieses Menüs auf manuell stellen.`
and preserves the submitted/saved page context without any write.

- [ ] Add RED route tests for auth/capabilities, fixed URL profiles, no body/query
  profile override, unchanged login/session-cookie/`csrf_token` Auth contract,
  `_csrf` Admin spelling, `Cache-Control: no-store`, 400/409 no mutation,
  exact component form keys/arrays, same-profile exact-prior-week Copy via the
  T6 store, absent/existing-empty target version semantics, lock/409/new IDs,
  and preview's LAST-SAVED source,
  no-store, and no-live-data fallback. Test empty copy as zero items and no
  active publication. Cover a valid missing menu slot rendered with virtual
  `row_version=0`, invalid/out-of-scope slot 404, and the full first-save
  1/404/409 matrix. Cover the review POST's exact keys, server-side item
  resolution, successful 303/PRG with the new checked row version, and
  stale/single-use repeat-token 409 with no mutation. Cover token GET and
  review POST `AutoOriginConflictError` as controlled 409 (never 500), the exact
  German recovery text, zero link/effect/review/item/week mutation, and a
  successful Manual-origin Review with byte-identical origins. Dirty-state and `target="_blank"` assertions belong to
  the reused rendered/browser harness, not route-preview tests.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_routes.py tests/test_admin_week_routes.py tests/test_admin_workflow_routes.py tests/test_admin_draft_preview.py`; expected FAIL.
- [ ] Implement the separate workflow blueprint and handlers for dashboard,
  menu, header, service, review, component CRUD/search, copy and preview.
  Resolve `AdminScope` server-side; existing-week handlers derive and verify
  the week's location, while catalog/create fail if globally active locations
  are zero or multiple under the current single-location contract. Keep the
  capability gate separate. Enforce `draft.read`, `draft.write`,
  `publication.publish`; use public IDs; copy excludes patient prices, resets
  reviews and never publishes. After component edit/archive/unarchive, tell the
  user that affected dishes require review; do not fan out writes to dishes.
  Map only `AutoOriginConflictError` to the specified 409 recovery response in both
  review-token rendering and Review POST; do not convert unexpected failures
  into that response.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_component_catalog_routes.py tests/test_admin_week_routes.py tests/test_admin_workflow_routes.py tests/test_admin_draft_preview.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/__init__.py reference_scaffold/cafeteria/admin/routes.py reference_scaffold/cafeteria/admin/workflow_routes.py reference_scaffold/tests/test_component_catalog_routes.py reference_scaffold/tests/test_admin_week_routes.py reference_scaffold/tests/test_admin_workflow_routes.py reference_scaffold/tests/test_admin_draft_preview.py`.
- [ ] Commit: `rtk git commit -m 'feat: add secure scoped admin routes'`.

Do not run or report a full-suite/deploy-ready gate here. The integration wave
remains incomplete until Tasks 8 and 9 land and legacy removals have complete
route and template replacements.

### Task 8: Publish PRG and status/error contract (serialized integration 2/3)

**Files:** Modify `reference_scaffold/cafeteria/admin/workflow_routes.py`,
`reference_scaffold/cafeteria/workflow.py`; test
`reference_scaffold/tests/test_admin_workflow_routes.py`,
`reference_scaffold/tests/test_workflow_form.py`,
`reference_scaffold/tests/test_admin_workflow_db.py`,
`reference_scaffold/tests/test_workflow_partial_store_db.py` and
`reference_scaffold/tests/test_workflow_copy_store_db.py`.

- [ ] Add RED tests for native-confirm publish POST with exactly
  `_csrf,week,row_version`, review/stale guards, PRG revision/flash in
  `aria-live`, and `derive_admin_status` independent of DB enum: empty is zero
  items and no active publication; incomplete is failed saved-draft validation;
  review_open is complete but unchecked/stale; live is an active snapshot equal
  to a freshly built saved snapshot using the same revision identity; changed
  is an active differing publication; ready is the remaining state. DB
  `workflow_state` stays `draft|ready|published|archived`. Cover 400/409
  atomicity, stale-component Publish rejection, replacement-publication
  capability/503 behavior and the existing App-role flow.
- [ ] Prove `derive_admin_status`, draft load and publish share the exact
  `review_open/needs_review = status != checked OR linked-version mismatch`
  predicate; persisted checked
  never overrides a mismatch. Publish locks the week, all services, all scoped
  items by numeric ID ASC, the component union by numeric ID ASC `FOR SHARE`,
  all links by `(menu_item_id, sort_order) FOR UPDATE`, and the active
  publication row last; it then rechecks every predicate under lock before
  snapshotting. Capability lookup may be nonlocking before the transaction,
  but active publication state is locked and revalidated last.
- [ ] Add synchronized barrier/event real-PG16 both-winner-order tests, without
  timing sleeps, for catalog edit versus Publish, Review versus Publish,
  Partial Save versus Publish, and Copy versus each of source Save, target Save
  and target Publish. Assert no `40P01`, no mixed snapshot/draft state, no
  partial mutation, immutable old snapshot when Publish wins, stale/review
  rejection when the edit wins, and that the loser in every race between two
  week-scoped operations blocks at the canonical week lock. Catalog edit itself owns
  no week lock and contends only after the week-scoped side reaches the
  component class. Preserve the T4 assignment and T6 Import/Recovery races unchanged.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_workflow_routes.py tests/test_workflow_form.py tests/test_admin_workflow_db.py tests/test_workflow_partial_store_db.py tests/test_workflow_copy_store_db.py`; expected FAIL.
- [ ] Implement server-side validation of saved draft, raster, reviews and component versions; use `confirm()` only as pre-submit UX, never as server security. Error text includes e.g. `Mittwoch, Abend, Vegetarisch: Preis darf höchstens zwei Nachkommastellen haben.`
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_admin_workflow_routes.py tests/test_workflow_form.py tests/test_admin_workflow_db.py tests/test_workflow_partial_store_db.py tests/test_workflow_copy_store_db.py -v`; expected PASS.
- [ ] Stage: `rtk git add reference_scaffold/cafeteria/admin/workflow_routes.py reference_scaffold/cafeteria/workflow.py reference_scaffold/tests/test_admin_workflow_routes.py reference_scaffold/tests/test_workflow_form.py reference_scaffold/tests/test_admin_workflow_db.py reference_scaffold/tests/test_workflow_partial_store_db.py reference_scaffold/tests/test_workflow_copy_store_db.py`.
- [ ] Commit: `rtk git commit -m 'feat: gate publish with review and PRG'`.

Do not run or report a full-suite/deploy-ready gate here. Task 9 must complete
the serialized integration wave first.

## Wave 4 — Novice Overview, Editor, Templates, JavaScript, CSS and A11y

### Task 9: Server-rendered overview, editor and catalog templates (serialized integration 3/3)

**Files:** Create/modify `reference_scaffold/cafeteria/templates/admin/cafeteria.html`, `patienten.html`, `components.html`, `component_editor.html`, `preview.html`; test `reference_scaffold/tests/test_rendered_ui.py`.

- [ ] Add RED rendered tests in `reference_scaffold/tests/test_rendered_ui.py` for exact 28/10-cell grids, no patient cost vocabulary, component usage/archive state, German labels and PREVIEW banner.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_rendered_ui.py`; expected FAIL.
- [ ] Render the route-provided profile and saved data only; include native checkbox + visible `label` inside `fieldset/legend`, 44px label hit area, explicit status/error/retry regions and no hard-coded hex values.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_rendered_ui.py -v`; expected PASS.
- [ ] Stage with: `rtk git add reference_scaffold/cafeteria/templates/admin/cafeteria.html reference_scaffold/cafeteria/templates/admin/patienten.html reference_scaffold/cafeteria/templates/admin/components.html reference_scaffold/cafeteria/templates/admin/component_editor.html reference_scaffold/cafeteria/templates/admin/preview.html reference_scaffold/tests/test_rendered_ui.py`.
- [ ] Commit: `rtk git commit -m 'feat: add novice admin templates'`.

Only after this commit may Task 11 claim full regression readiness or Task 12
claim deployment readiness for the T7-T9 integration wave.

### Task 10: Dirty/loading/error/dense client behavior and responsive a11y

**Files:** Create/modify `reference_scaffold/cafeteria/static/admin.js`, `reference_scaffold/cafeteria/static/app.css`; create `reference_scaffold/tests/test_admin_ux_browser.py` by reusing the existing Playwright patterns and fixtures in `test_rendered_ui.py` without a new dependency.

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
- [ ] Run `gitnexus_detect_changes()` and confirm only planned symbols/flows changed. Run `rtk ocr review --repo /nvmetank1/projects/menuplan --from docs/admin-redesign-plan-v1 --to feat/admin-redesign-impl-v1 --format json --audience agent` and record `OCR:` summary; this gate must inspect the implementation diff, never only the docs branch.
- [ ] Obtain independent read-only AGY and Grok reviews of the diff/plan; HIGH/CRITICAL finding blocks progression.

### Task 12: PG16 migration, restore and deployment proof

**Files:** `reference_scaffold/tests/test_deployment_compose_probe_live.py`, `reference_scaffold/tests/test_deployment_restore_live.py`, `reference_scaffold/tests/test_deployment_restore_recovery.py`, `reference_scaffold/tests/test_capture_live_screenshots.py`, `reference_scaffold/README.md`.

- [ ] Take and record a named PostgreSQL backup plus a down-probe copy before migration; execute Compose PG16 migrations through schema 14 and verify versions, narrow helper grants, idempotence and rollback while proving migration 0010's checksum unchanged.
- [ ] Restore v12 probe data, run the documented restore path, verify exact legacy/free-text behavior and no accidental `dish_templates` change.
- [ ] Run Chromium and existing CI-browser checks over all four viewports, keyboard/focus, errors/retry, Copy/Preview/Publish; capture authenticated admin smoke screenshots and a proof ZIP.
- [ ] With cwd `reference_scaffold`, run: `rtk /tmp/dishboard-test-venv/bin/python -m pytest -q tests/test_deployment_compose_probe_live.py tests/test_deployment_restore_live.py tests/test_deployment_restore_recovery.py tests/test_capture_live_screenshots.py -v`; preserve verbatim output and exit code.
- [ ] Deploy only after all receipts exist: backup ID, schema-14 migration including Fresh/Migration/Restore owner-and-ACL parity, immutable image digest, healthcheck and authenticated admin smoke. Record rollback/restore probe; no claim from `pytest` alone.
- [ ] Stage: `rtk git add reference_scaffold/tests/test_deployment_compose_probe_live.py reference_scaffold/tests/test_deployment_restore_live.py reference_scaffold/tests/test_deployment_restore_recovery.py reference_scaffold/tests/test_capture_live_screenshots.py reference_scaffold/README.md`.
- [ ] Commit: `rtk git commit -m 'test: prove admin migration and deployment'`.
- [ ] Final verification: `rtk claude-wp-verify --branch feat/admin-redesign-impl-v1 --base docs/admin-redesign-plan-v1`; confirm a non-empty implementation diff, no staged-leak, and exact ownership. No final gate may verify only the docs branch.

## Self-review checklist

- [ ] Cross-check every SDD section: 28/10 raster, no patient prices, full-replace exception, three modes, location/profile isolation, migration/backfill/down-probe, exact routes/keys/statuses, last-saved Preview, review/stale immutable Snapshot, A11y viewport matrix, backup/restore and stop conditions.
- [ ] Scan this plan for vague or undefined instructions; replace each with exact keys, signatures, test names and commands before commit; configured fallback wording must name the concrete fallback and its trigger.
- [ ] Verify shared-file serial ownership: `schema.sql`, `db.py`, `component_catalog_store.py`, `component_assignment_store.py`, `workflow.py`, `workflow_snapshot.py`, and the `admin/routes.py` adapter plus `admin/workflow_routes.py` have one owner per wave; review lanes are read-only.
