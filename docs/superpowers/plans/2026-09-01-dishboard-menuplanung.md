# Dishboard Menüplanung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or the host work-package workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das vorhandene Flask/PostgreSQL-Paket als lauffähige, profilgetrennte Menüplanung unter `dishboard.joelduss.xyz` ausliefern, inklusive lokaler Benutzer neben Entra, Live-DB-Beweisen, Screenshots und validiertem ZIP.

**Architecture:** Ein Flask/Gunicorn-Prozess bleibt einziger Applikationsstack. PostgreSQL hält Draft-Raster und immutable Publikationsrevisionen je Profil; öffentliche Renderer lesen ausschließlich aktive Snapshots. Redis hält Sessions und lokale Login-Limits. Zwei Küchenraster schreiben über kleine Services in dieselben relationalen Tabellen, erzeugen jedoch strikt getrennte Profil-Snapshots.

**Tech Stack:** Python 3.13, Flask 3, Jinja, SQLAlchemy Core, psycopg, PostgreSQL, Redis, Docker Compose, Playwright, pytest.

**Spec:** `review/Grok_Kritik_original.txt`, `docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.md`, `design/DESIGN.md`, Nutzerauftrag vom 2026-09-01.

## Global Constraints

- Patienten: Montag bis Sonntag, `LUNCH` und `DINNER`, je `MENU_1` und `VEGGIE`; keine Preisfelder oder Preisbegriffe in HTML, JSON, Snapshot, CSV oder Template.
- Cafeteria: Montag bis Freitag, nur `LUNCH`, je `MENU_1` und `VEGGIE`; Mitarbeiter- und Externenpreis; Wochenende immer „Cafeteria geschlossen“, niemals Profilfallback.
- Vier feste Player-Routen: `/signage/cafeteria/tag`, `/signage/cafeteria/woche`, `/signage/patienten/tag`, `/signage/patienten/woche`; keine Query-Parameter, Navigation oder Scrollbars.
- Patienten-Wochenplayer: 3840×2160 Mindestauflösung; 1920×1080 nur explizite Vorschau/QA.
- Publikation, Revision und Last-Good je Profil getrennt; Draft-Inhalte gelangen nie in öffentliche Antworten.
- Lokale Benutzer koexistieren mit Entra; kein Self-Signup, keine Default-Accounts, keine Passwörter in Argumenten/Logs/Session; Redis-Ausfall sperrt lokalen Login.
- Keine neue Dependency, kein Framework, kein Microservice. Neue Module bleiben unter 400 Zeilen.
- UI folgt `design/DESIGN.md`; keine neuen harten Hexfarben, nur bestehende CSS-Tokens; Skip-Link, sichtbarer Fokus und semantische Formulare sind Pflicht.
- Jede Verhaltensänderung beginnt mit rotem Test. Live-DB-Tests dürfen nicht übersprungen und trotzdem als Erfolg gewertet werden.
- Alle Shell-Kommandos verwenden `rtk`; ein Shell-Aufruf enthält genau einen RTK-Befehl.
- Writer arbeiten in eigenen Worktrees, committen nur eigene Branches, pushen/mergen nicht. Orchestrator prüft und merged.

## Locked Interfaces

```python
# cafeteria/menu_service.py
def load_admin_week(engine: Engine, profile_code: str, week_start: date) -> dict[str, Any]: ...
def save_draft(engine: Engine, profile_code: str, week_start: date, form: Mapping[str, str], actor_id: int) -> dict[str, Any]: ...
def import_draft_csv(engine: Engine, profile_code: str, csv_text: str, actor_id: int) -> dict[str, Any]: ...
def publish_profile(engine: Engine, profile_code: str, week_start: date, actor_id: int) -> str: ...

# cafeteria/local_auth.py
def authenticate_local(engine: Engine, redis_client: Redis, username: str, password: str, client_ip: str) -> LocalAuthResult: ...
def provision_local_user(engine: Engine, username: str, display_name: str, password: str, roles: Sequence[str], actor: str) -> int: ...
def current_authorization(engine: Engine, user_public_id: str) -> tuple[bool, list[str], int]: ...
```

`publish_profile` erstellt Snapshot ausschließlich aus relationalem Draft desselben Profils, setzt Woche innerhalb derselben Transaktion auf `published` und fügt genau eine neue immutable `publication_revisions`-Zeile ein. Bestehende aktive Revision des anderen Profils bleibt bytegleich.

## Wave A — Contracts and Independent Runtime Edges

### Task 1: PostgreSQL constraints, real migrations, immutable publications

**Files:**
- Modify: `database/schema.sql`, `database/permissions.sql`, `database/README.md`, `database/validate_schema.py`
- Create: `database/migrations/0002_profile_publication_and_local_auth.sql`
- Modify: `reference_scaffold/cafeteria/db.py`, `reference_scaffold/manage.py`
- Test: `reference_scaffold/tests/test_database_invariants.py`

**Produces:** schema version 5, ordered checksum-verified migration runner, local credential schema, immutable revision trigger, exact snapshot validators.

- [ ] Write live PostgreSQL tests for patient price rejection, `staff_guest+DINNER`, cafeteria weekend, draft publication rejection, revision UPDATE/DELETE rejection, profile-independent active revisions and migration checksum drift.
- [ ] Run tests with `TEST_DATABASE_URL`; verify expected failures, not collection errors.
- [ ] Add local-auth-compatible user/role constraints, `local_credentials`, authz version, failure lock state and audit support. Store only Werkzeug-compatible password hashes.
- [ ] Add recursive patient cost-key/value rejection and exact date/weekday/meal/menu-type/price validation for publication snapshots.
- [ ] Make revisions immutable and require `menu_weeks.workflow_state='published'` for revision insertion.
- [ ] Replace baseline replay with ordered, checksum-verified `0001` then `0002` migration execution; preserve existing `0001` bytes.
- [ ] Narrow application grants where current runtime allows; document remaining privilege boundary.
- [ ] Run live DB tests, static schema validator, migration from empty DB and migration from v4 fixture.
- [ ] Commit with prefix `db:` and record verbatim gates.

### Task 2: Domain and production-safe deployment

**Files:**
- Modify: `deployment/.env.example`, `deployment/docker-compose.yml`, `deployment/docker-compose.caddy.yml`, `deployment/caddy/Caddyfile.example`, `deployment/bootstrap.sh`, `deployment/entrypoint.sh`, `deployment/README.md`, `deployment/validate_compose.py`
- Modify: `entra/redirect-uris.txt`, `entra/README.md`
- Test: `reference_scaffold/tests/test_deployment_contracts.py`

**Produces:** `dishboard.joelduss.xyz` defaults, persistent last-good volume, placeholder/default-secret rejection.

- [ ] Write failing deployment tests for exact host/redirect URIs, persistent last-good storage, forbidden production demo/default placeholders and secret-safe healthchecks.
- [ ] Set domain and Entra callback/logout values to `dishboard.joelduss.xyz`; retain operator overrides.
- [ ] Persist last-good snapshots across container restart; never place secret values in process arguments.
- [ ] Make bootstrap generate secrets but leave Entra/local users unprovisioned; production startup rejects placeholder Entra values when Entra enabled.
- [ ] Run Compose validator and `docker compose config` using generated non-secret fixture files.
- [ ] Commit with prefix `deploy:` and record verbatim gates.

### Task 3: Public/API/signage isolation and empty states

**Files:**
- Modify: `reference_scaffold/cafeteria/public/routes.py`, `reference_scaffold/cafeteria/api/routes.py`, `reference_scaffold/cafeteria/signage/routes.py`
- Test: `reference_scaffold/tests/test_public_contracts.py`

**Produces:** strict query rejection, profile-specific renderer context, safe no-publication responses, revision parity.

- [ ] Write failing route tests for every public/API/signage query parameter, no-snapshot responses, weekend cafeteria closed, no cross-profile data, all four day/week revision headers.
- [ ] Centralize public snapshot lookup without combining profile payloads; keep date selection server-side only.
- [ ] Ensure cafeteria day/week never dereference missing snapshot and never fallback to patient or prior weekday.
- [ ] Add explicit no-store failure responses and shared revision headers for day/week of same profile.
- [ ] Run route tests against live DB snapshots.
- [ ] Commit with prefix `public:` and record verbatim gates.

## Wave B — Product Workflows

### Task 4: Draft kitchen grids, complete CSV import and profile publish

**Files:**
- Create: `reference_scaffold/cafeteria/menu_service.py`
- Modify: `reference_scaffold/cafeteria/csvio.py`, `reference_scaffold/cafeteria/admin/routes.py`
- Test: `reference_scaffold/tests/test_menu_workflow.py`

**Consumes:** schema v5 and Locked Interfaces.

- [ ] Write failing service and route tests for two exact grids, create/update draft, full CSV errors, CSRF, capability checks, publication independence and draft invisibility.
- [ ] Reuse `csv/validate_menu_csv.py` rules in runtime path; return row/column errors and reject partial writes transactionally.
- [ ] Implement relational load/save for patient 7×2×2 and cafeteria 5×1×2; no generic CMS entities.
- [ ] Build profile snapshot from saved relational data, validate completeness, publish atomically and audit actor/profile/revision.
- [ ] Confirm publication of one profile leaves other profile revision and bytes unchanged.
- [ ] Run workflow tests against live PostgreSQL.
- [ ] Commit with prefix `workflow:` and record verbatim gates.

### Task 5: Local users alongside Entra

**Files:**
- Create: `reference_scaffold/cafeteria/local_auth.py`, `reference_scaffold/cafeteria/templates/auth/local_login.html`
- Modify: `reference_scaffold/cafeteria/config.py`, `reference_scaffold/cafeteria/auth/routes.py`, `reference_scaffold/cafeteria/roles.py`, `reference_scaffold/cafeteria/security.py`, `reference_scaffold/manage.py`
- Test: `reference_scaffold/tests/test_local_auth.py`

**Consumes:** schema v5 local credential tables.

- [ ] Write failing tests for Entra/local coexistence, generic bad-login responses, disabled/locked users, Redis fail-closed, IP+username rate limits, live role revocation and cookie flags.
- [ ] Add `LOCAL_AUTH_ENABLED=false` default; require Redis whenever local auth is enabled.
- [ ] Authenticate via Werkzeug password hash, rotate session, store no credential material and revalidate enabled/authz-version on protected requests.
- [ ] Add `provision-local-user`, `set-local-password`, `disable-local-user` commands using `getpass`; reject weak/default passwords and unknown roles.
- [ ] Write audit events for provision, password change, role change, lock and disable actions.
- [ ] Run local auth tests with PostgreSQL and Redis.
- [ ] Commit with prefix `auth:` and record verbatim gates.

### Task 6: Production UI for both grids and all channels

**Files:**
- Modify: `reference_scaffold/cafeteria/templates/base.html`
- Modify: all templates under `reference_scaffold/cafeteria/templates/admin`, `public`, `signage`
- Modify: `reference_scaffold/cafeteria/static/app.css`
- Test: `reference_scaffold/tests/test_rendered_ui.py`

**Consumes:** admin route form names from Task 4 and public contexts from Task 3.

- [ ] Write failing rendered-HTML tests for exact slot counts, labelled inputs, no patient cost tokens/fields, cafeteria CHF labels, no signage links/navigation/overflow and required empty states.
- [ ] Implement editable patient grid with seven explicit day sections and Lunch/Dinner columns; implement cafeteria grid with five explicit Lunch rows and price inputs.
- [ ] Replace placeholder `href="#"` actions with real forms/routes; keep profile switches only inside authenticated backend.
- [ ] Add skip-link, `:focus-visible`, labels, errors adjacent to fields and 44px mobile controls using existing CSS variables only.
- [ ] Keep patient templates structurally price-free; do not share price-condition markup with cafeteria.
- [ ] Enforce fixed 16:9 signage and 4K patient-week production layout. Fix clipped headers and include explicit CHF on cafeteria signage.
- [ ] Run rendered UI tests at mobile, 1440px, 1080p and 4K sizes.
- [ ] Commit with prefix `ui:` and record verbatim gates.

## Wave C — Independent Gates, Evidence, Documentation

### Task 7: QA harness and live screenshot capture

**Files:**
- Modify: `reference_scaffold/tests/test_contracts.py`, `reference_scaffold/tests/test_smoke.py`
- Create: `reference_scaffold/tests/test_acceptance.py`, `tools/capture_live_screenshots.py`
- Modify: `tools/validate_package.py`

- [ ] Add acceptance tests for every Pflichtprüfung in user request, including raw patient HTML/JSON/CSV/template scans for `CHF`, `Intern`, `Extern`, `0.00` and price-field patterns.
- [ ] Make missing `TEST_DATABASE_URL` a failing live-gate mode, not a green skip, while retaining explicit offline unit selection.
- [ ] Capture only from running HTTP application: two backend grids, two mobile weeks, two website weeks, four signage players, cafeteria weekend closure, patient week at 3840×2160 and 1080p QA preview.
- [ ] Save console/network errors and fail capture on scroll overflow, navigation links in signage, wrong dimensions or HTTP error.
- [ ] Update package validator to require live screenshot inventory and exclude caches/worktrees/secrets.
- [ ] Run focused acceptance suite and commit with prefix `qa:`.

### Task 8: Security and adversarial review fix wave

**Files:** only files named by confirmed reviewer findings; author must differ from original author.

- [ ] Review authn/authz, CSRF, session fixation, rate limiting, SQL parameters, immutable publications, profile data isolation, secrets, headers and Caddy exposure.
- [ ] Run `bandit`, dependency audit when available, gitleaks, and targeted adversarial tests.
- [ ] Route confirmed HIGH/MEDIUM findings to different fix agent; add regression tests first.
- [ ] Run OCR branch review plus independent whole-branch review; no HIGH finding may proceed.

### Task 9: SDD, README and operating evidence

**Files:**
- Modify: `README.md`, `VALIDATION.md`, `CHANGELOG.md`, `docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.md`, `docs/GROK_KRITIK_UMSETZUNG.md`, `docs/ABNAHME_CHECKLISTE.md`, `docs/DOCKER_COMPOSE_RUNBOOK.md`, `docs/ENTRA_SSO_BETRIEBSKONZEPT.md`, `design/SCREENSHOT_INDEX.md`
- Regenerate: `docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.docx`, diagrams only if sources changed.

- [ ] Replace Entra-only decision with Entra plus opt-in local users and secure provisioning limits.
- [ ] Document actual routes, commands, migrations, domain, 4K minimum, tests and unresolved operational/fachliche acceptance only.
- [ ] Remove claims based solely on static validators or skipped DB tests.
- [ ] Regenerate DOCX and verify it opens.
- [ ] Commit with prefix `docs:`.

### Task 10: Integration, deployment, package and revalidation

**Files:** generated evidence and package artifacts only; do not modify product code unless routed through reviewed fix WP.

- [ ] Start PostgreSQL and Redis, run migrations from empty volume, seed demo explicitly and verify schema version/checksums.
- [ ] Start application and Caddy configuration for `dishboard.joelduss.xyz`; prove local health and all core routes.
- [ ] After each fully reviewed, secret-scanned and green integration checkpoint, deploy `main` to `https://dishboard.joelduss.xyz/`, verify health plus core public routes, and roll back immediately on failure; never deploy a branch with relevant skipped live gates.
- [ ] Run full unit, rendered, live DB, local auth, security and acceptance suites. Report passed/failed/skipped counts; any relevant skip blocks completion.
- [ ] Capture required live screenshots, open every image, log visual defects, route fixes, recapture and re-open.
- [ ] Run package validator, regenerate `PACKAGE_CONTENTS.txt` and `MANIFEST_SHA256.txt`, then verify both.
- [ ] Create ZIP outside repository, extract into fresh directory, run validators/tests against extracted copy and verify no secrets/caches/worktrees.
- [ ] Compute final ZIP SHA-256 and record exact path, size, commit and runtime evidence.

### Task 11: Public GitHub repository and GitHub Pages

**Files:**
- Create: `.github/workflows/pages.yml`, `site/index.html`, `site/styles.css`
- Generated during workflow: `site/assets/` copies of selected checked-in screenshots

- [ ] Keep `joehomeskillet/Dishboard` public and push only orchestrator-reviewed `main` commits; worker branches never push.
- [ ] Build a framework-free, responsive landing page in the existing clinic visual language: clear patient/cafeteria split, signage gallery, architecture summary, security boundaries and source link.
- [ ] Use mapped CSS custom properties with no hard-coded hex colors, semantic headings, skip-link, visible focus, descriptive image alt text and reduced-motion support.
- [ ] Add official GitHub Pages custom workflow using current major actions, minimal `pages: write`/`id-token: write` permissions and `main`-only deployment.
- [ ] Validate HTML/CSS, scan workflow permissions, deploy Pages, open desktop/mobile screenshots and fix visual defects.
- [ ] Set repository homepage URL and topics through GitHub API; verify public Pages URL and latest workflow conclusion.
- [ ] Commit with prefix `pages:`; orchestrator pushes after review.

## Preflight Dependency Table

| Producer | Consumer | Contract | Ruling |
|---|---|---|---|
| Task 1 | Tasks 4–5 | schema v5, migrations, local credential tables | Task 1 merges before Wave B. |
| Task 3 | Task 6 | renderer context and revision headers | Python routes own context; UI owns templates/CSS. |
| Task 4 | Task 6 | form field names and route endpoints | Locked by tests before UI worker starts. |
| Tasks 1–6 | Task 7 | observable behavior | QA edits only dedicated tests/tools, no product modules. |
| Tasks 1–7 | Task 8 | reviewed combined diff | Reviewer is read-only; fixes use different author. |
| Tasks 1–8 | Task 9 | actual behavior/evidence | Docs run after implementation and review. |
| Tasks 1–9 | Task 10 | release candidate | Integration cannot waive failed/skipped live gates. |
| Tasks 6–7 | Task 11 | visual language and live screenshots | Pages uses reviewed screenshots and ships before final package. |

No task may weaken profile separation, draft privacy, password handling or production secret checks to make tests pass.
