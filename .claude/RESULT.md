# WP-972f785f0b97: schema27 database slice

Status: author-verified DB-FREEZE, ready for Root's independent review and integration. Not a complete BAS/REC, UI, PDF or deployed feature.
Worktree: /nvmetank1/projects/menuplan/.claude/worktrees/prepared-food-schema27-0909
Branch: feat/prepared-food-schema27-0909
Base: e813806b51fb5efaef5d5755c292f8027ce1b2eb; fetch github main completed before worktree creation.
Native SQL/PG capability assignment was Root's explicit decision; no invented provider failure.

## Result and consumer contract

The four public APIs and exact v2 metadata/index are in IMPLEMENTATION.md, FULLREAD and accepted by Root before implementation. No signature changed afterwards. Food saves require real same-site storage, preserve omitted existing preparation pins, accept only a complete explicit revision/hash pair, keep source provenance immutable, and write one version/audit or no-op zero. Recipe drafts may remain incomplete; v27 freeze rejects incomplete quantities/Food links and stale original dependency state.

Migration 0024 has 509 lines and SHA256 5503b214a9957a09345d3301526797ca8fa2deb146fd6bdced6875ebd86635f2. Root authorized a necessary SQL-only >600-line exception, but this implementation did not need it. New Python modules remain below400 lines. All 23 earlier migration blobs equal Base. Canonical migration block equals the migration body. Source manifest records 15 owned source hashes, including only necessary existing version/ACL fixture changes.

The migration locks Storage references SHARE, then Food/link tables ACCESS EXCLUSIVE, before reading missing-storage state. This avoids a later DDL lock upgrade and prevents an old writer from committing a gap between preflight and DDL. Missing assignments stop before DDL, sequences or ledger updates, with bounded count and up to20 Food UUIDs. Explicit old-v21 app-role storage assignment is tested separately before retry; no fabricated storage/backfill is introduced.

Current semantic Food traversal uses v1 root ingredient identities and today's selected Food edges solely for write validation. Immutable render closure follows stored pins only; v1 is terminal. Original Actor/Roles/Location locks precede the location-specific graph advisory lock; references/Storage precede Foods and Recipe heads. Deferred final-state constraints enforce storage/quantity compatibility and acquire no graph lock. The old protect_master_data trigger keeps every original identity/provenance check and adds only prepared_recipe_revision_id to the mutable Food projections.

## Exact ACL decisions

All following public signatures are App-only; no PUBLIC, backup or auth-issuer EXECUTE:
- create_food_v27(bigint,bigint,bigint,jsonb)
- update_food_v27(bigint,bigint,bigint,uuid,bigint,jsonb)
- freeze_recipe_v27(bigint,bigint,bigint,uuid,bigint,text)
- recipe_dependency_preview_v27(bigint,uuid,bigint)

Revoked legacy App signatures (also PUBLIC/backup/issuer): create_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb), freeze_recipe_revision_v22(bigint,bigint,bigint,uuid,bigint,jsonb). These otherwise permit incomplete create or old freeze. Owner-only immutable v1 fixture creation demonstrates historical-reader compatibility; App cannot call it.

Retained Food-affecting v21 signatures each take (bigint,bigint,bigint,uuid,bigint,jsonb): update_food_v21, set_food_active_v21, replace_food_tags_v21, replace_food_metadata_v21, set_food_allergen_review_v21, replace_food_storage_locations_v21, create_proposal_v21, accept_proposal_v21, reject_proposal_v21. Core update cannot edit the pin and now meets the deferred prepared-yield/storage checks. Active/archive retains required storage. Child replacements cannot remove final storage; tags/metadata/review do not alter pins. Proposal accept only updates an existing target's permitted factors/metadata and meets the same final Food constraints. Proposal create/reject do not create or alter a Food. No table DML grants were added. Existing vocabulary APIs are unchanged; their storage updates also meet deferred final invariants.

Private signatures, all EXECUTE revoked from PUBLIC/App/backup/issuer: lock_prepared_graph_v27(bigint); recipe_snapshot_complete_v27(jsonb); check_prepared_graph_v27(bigint,uuid,bigint); assert_food_complete_v27(bigint); enforce_food_complete_v27(); food_save_v27(boolean,bigint,bigint,bigint,uuid,bigint,jsonb); check_prepared_snapshot_v27(jsonb,uuid); merge_prepared_node_v27(jsonb,jsonb). Existing private master_food_mutate/recipe_write_v22 ACLs remain unchanged. Every new function retains pg_catalog,cafeteria,pg_temp search_path and owner identity; actual ACL/replay/direct-DML tests pass.

## Actual verification

Exclusive pool: PG16 port32835 / Redis32836. Wrapper and complete argument arrays are recorded in each gate-*.log. No other pool, production, browser, login or container was touched. Protected environment was used only by the existing wrapper; URLs are redacted in private captures.

Final full focused command and verbatim output: gate-1788907950602422498.log. It runs the five new test_prepared_food_* modules plus the existing migration-plan, v4 upgrade/withdrawal, exact App grants, R5 migration/history-permissions, and full live-schema-validator checks.

```text
..........................................................               [100%]
58 passed in 91.11s (0:01:31)
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/prepared-food-schema27-0909/reference_scaffold
```

Coverage: actual same-transaction atomic save/no-op/audit; original actor/site/row-version/hash and provenance rejection; direct App DML/private execution denial; permission replay; read-only RR preview with unchanged rows/sequences; incomplete drafts retained but freeze refused; exact physical/contextual/density eligibility; legacy core cannot bypass compatibility; archived new selection refused but existing pin preserved/explicitly removed; foreign pin/storage and composite-FK rejection; explicit old-schema backfill and fresh/migrated catalog equality; unchanged old ledger/business rows and sequences; v1 JSON/hash retention; exact reconstruction of every stored v2 child snapshot/hash with sibling-shared grandchildren; repeated ingredient quantities retained; direct/indirect Food and repeated Recipe identity cycles; bounds8/9 edges,64/65 closure entries,4033 vs >4096 current graph work,3615 vs >4096 expanded occurrences and2MiB rejection.

Concurrency tests measure actual pg_blocking_pids while the blocker transaction is open: both opposite v1 Food-pin writer orders, pin-versus-freeze both orders, original actor/role revocation, storage archive/assignment both orders, old writer before migration gap check, and R5 Food→Recipe shared locks versus freeze. They assert resulting commits/rollback state; a status-only race substitute is not used.

Final static validator command: rtk /tmp/dishboard-shared-venv/bin/python -B database/validate_schema.py. Exit0, artifact_check passed, live_postgresql_executed false, schema_version27, tables52, schema_sha256 b683e586ee16890b0a7369a03bbd5b1301eb50b11969bc3d215d806aba5aa365. It ran again after pinning the exact final migration checksum in both validators. The actual --live validator ran inside the58-case PG gate before this checksum-only addition.

Final Ruff: rtk /root/.local/bin/ruff check database/validate_schema.py reference_scaffold/cafeteria/db.py tools/validate_package.py reference_scaffold/tests/prepared_food_fixtures.py reference_scaffold/tests/test_prepared_food_db.py reference_scaffold/tests/test_prepared_food_closure_db.py reference_scaffold/tests/test_prepared_food_migration_db.py reference_scaffold/tests/test_prepared_food_race_db.py reference_scaffold/tests/test_prepared_food_security_db.py reference_scaffold/tests/test_database_invariants.py reference_scaffold/tests/test_recipe_binding_migration_db.py reference_scaffold/tests/test_master_data_db.py .claude/run_gate.py .claude/audit_source.py
```text
All checks passed!
```
Exit0.

Final real Mypy: rtk /root/.local/bin/mypy --python-executable /tmp/dishboard-shared-venv/bin/python --follow-imports=silent --disable-error-code=import-untyped database/validate_schema.py reference_scaffold/cafeteria/db.py tools/validate_package.py reference_scaffold/tests/prepared_food_fixtures.py reference_scaffold/tests/test_prepared_food_db.py reference_scaffold/tests/test_prepared_food_closure_db.py reference_scaffold/tests/test_prepared_food_migration_db.py reference_scaffold/tests/test_prepared_food_race_db.py reference_scaffold/tests/test_prepared_food_security_db.py
```text
Success: no issues found in 9 source files
```
Exit0. Existing untyped installed-dependency boundary only; no dependency install or ignore-missing-imports.

rtk /tmp/dishboard-shared-venv/bin/python -B .claude/audit_source.py
```text
PASS: 15 owned source hashes; 23 historical migration blobs equal; canonical migration block equal; no outside-scope tracked diff.
```
Exit0. rtk git diff --check exit0 with empty output. GitNexus unique alias menuplan-prepared-food-schema27-0909: prior impact LOW for registration/validator/test consumers; SQL unindexed UNKNOWN, manual HIGH warning sent before edits. Final detect reports19 symbols/1 validator process, medium; gitnexus-detect.json contains raw result. Adjacent unchanged constants appear in graph hunks; source diff remains scoped. SQL HIGH remains a separate manual assessment, not downgraded by graph absence.

Private evidence Gitleaks: rtk gitleaks detect --redact --no-banner --no-git --source .claude --report-path .claude/gitleaks-private.json
```text
12:53AM INF scan completed in 11.7ms
12:53AM INF no leaks found
```
Exit0 (terminal color escapes omitted). Commit-range Gitleaks receipt follows in central report after commit.

## Preserved failed attempts

Every actual test failure had exactly one identical retry, then an explained scope-preserving correction. Raw command/output/exit are retained in the linked private captures; none is relabelled PASS.
- gate-1788906998840417678.log / gate-1788907134548791531.log:2 failed,23 passed,49.96s/56.99s. Existing protect_master_data origin projection rejected new pin; fixed only that new mutable field, then provenance-negative checks added.
- gate-1788907305151221563.log / gate-1788907456068795518.log:5 failed,32 passed,82.51s/85.67s. New test fixtures corrected actual set_food_active name, bound JSON payload instead of SQLAlchemy :false parsing, actual revision ID for R5 helper and raw psycopg exception from migration driver. No assertions removed.
- gate-1788907673737239839.log / gate-1788907787210604845.log:2 failed,15 passed,26.05s/26.51s. Historical permissions projection now preserves original COMMIT bytes when excluding the new block; NULL location expects existing inherited22023 rather than inventedP1901. Product status unchanged.
- Initial Ruff original+identical retry: six F811 fixture import bindings; explicit fixture re-export fixed. Tool-transcript outputs retained; final Ruff passes.
- Two exploratory rg commands failed with guessed missing test filenames (exit2, identical retry) and a no-match CREATE FUNCTION search for an actual CREATE OR REPLACE declaration (exit1, identical retry). Then listed paths/read actual declaration. No CLI/provider switch.
- Staged git diff --check returned exit2 with empty RTK output on original and identical retry; a single extra EOF blank line in private gitnexus-detect.json was removed. A second original/retry pair still returned2: exactly four trailing-space lines in the preserved original pytest FAIL outputs (gate-1788907673737239839.log and gate-1788907787210604845.log, each lines8/15). These original logs are not edited. Product/test scoped command rtk git diff --cached --check -- database reference_scaffold tools returned0. Global raw-evidence whitespace FAIL remains explicitly separate; no config exception was introduced.
- Earlier successful gates remain:1 passed4.37s;19 passed32.00s;37 passed57.48s. They are superseded by the58-case final receipt, not added together.

## Remaining gates and integration boundary

NOT RUN: PG18 (Root's separate predeployment proof); full application/package pytest run; package manifest regeneration/full validate_package; browser/native PDF paint; deployment/image/roundtrip; independent external security review. These are deferred for integrated consumers and Root review, not asserted passed here. OCR NOT RUN because original+identical retry429 had already established unavailability in this session; no new provider call. No separate secret-scan-check was claimed.

MasterData service/UI writer34b1b5212bfd must consume the four exact APIs. Its test_master_data_db.py fixture edits coexist with this branch's one-line schema26→27 assertion; use the narrow diff, not whole-file replacement. Versioned RecipeReader/closed-index hash verification, preview+signed original dependency form/freeze wiring, prepared Decimal yield scaling and PDF v2 consumers remain required separate slices. This migration is not deployable alone with old App create/freeze consumers. No general R6 import/plan scope was implemented.
