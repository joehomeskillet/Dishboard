# Admin go-live: browser form repair and deployment ledger

Scope: continue `UEBERGABE-CODEX-2026-09-05.md`, then improve `/admin/…` in small verified deployment waves. Public pages and signage retain their contracts.

## Design and acceptance

Purpose: kitchen staff can save week metadata, service state, menus and catalog metadata through the actual rendered controls without losing existing values. Primary actions remain explicit German save buttons. Tone: calm, practical institutional interface, using the existing `--sh-*` tokens and native controls. Preserve 44 px touch targets, keyboard operation, visible focus, CSP and reduced motion. Distinction comes from clear week/status/action hierarchy rather than new decoration.

The existing SDD, strict parsers and authorization rules remain authoritative. Do not loosen input validation to accept broken HTML. Frozen migrations remain unchanged. DOM context additions and canonical form-name corrections must be documented with their implementation.

## Recovery evidence

- Actual main/github-main: `f6a07e435592d2352e016d2fbab470a2c13c4811`; RTK log omits merge commits. Use `rev-parse` for identity.
- Production: `39123e79c3e9b7d0860a48feee321c594ec2220c`, schema 12, health/live and health/ready 200.
- Candidate: `fd15aa7ef76ce4b9f02522b16d5b6761b0118358`; only manifest files changed since `9865d03`.
- Recovered suite: `2517 passed, 15 skipped, 22 warnings in 288.75s (0:04:48)`; `GATE_EXIT=0`. Skips: 14 opt-in restore drills and one opt-in compose probe. Commit association is filename-derived; final candidate requires a fresh suite after fixes.
- Grok review at `9865d03`: 11 HIGH, 7 MEDIUM, 5 LOW. Confirmed form and render defects below. Historical 0011 claims are already adjudicated in the binding handover; do not change pins to satisfy those false positives.

## Repair wave and ownership

1. `wp-5bd1e451fbfc`: rendering/data contracts. Own `admin/rendering.py`, `admin/workflow_routes.py`, overview templates `cafeteria.html`/`patienten.html`, `docs/design/admin-redesign-ui.md`, and focused rendering/overview tests. Supply service CAS/notice independently of item versions; supply catalog master choices; canonical unsuffixed menu form values; explicit header/service saves. All shared Python/context files have this single writer. Also implement the currently missing Copy GET form through the existing `_page` surface, using the exact SDD POST fields.
2. `wp-71b71a889110`: menu controls and shared browser behavior. Own `menu_editor.html`, `static/admin.js`, and `tests/test_admin_ux_browser.py`. Repeat canonical unsuffixed names, omit inactive auto-mode payloads and empty optional rows, pair allergen codes/presences, support adding/removing optional component/origin rows, protect every preview link on dirty pages. Strict server errors remain intact. Shared JS must also handle catalog allergen rows using existing `.allergen-row` structure.
3. `wp-1e97d85ef5d4`: catalog markup and tests. Own `components.html`, `component_editor.html`, `tests/test_component_catalog_routes.py`, and focused catalog browser test file if needed. `target_scope=current`; canonical parser names; checked metadata survives save; unchecked allergen rows do not emit presence. Coordinate shared JS with WP2 and master-choice context with WP1; do not edit their files.

Workers use separate worktrees based on `fd15aa7`. Shared contracts are owned by WP1; dependent gates run after integration. At most one pytest/Playwright heavy run at once. Every symbol edit gets GitNexus impact first; commits require detect_changes. Workers commit, never push/merge. Root reviews diffs and independently runs the integrated gates.

## Gate and deploy sequence

- Focused actual-browser round trips at 390×844 and 1440×1100, then final complete suite. Test actual rendered successful controls, not hand-built payloads. No DOM injection or xfail.
- Independent review of corrected findings; OCR availability must be recorded honestly. At recovery, OCR/Anthropic providers were unavailable; never report missing review as passed.
- Regenerate and validate manifest, schema validation, Ruff and usable Bandit under Python 3.13. Record known worktree-only package checks separately from real defects.
- Root fast-forwards integration to main only after gates, pushes `github main`, creates fresh verified backup, builds immutable image, migrates 12→15, cuts over, checks public/signage/auth health, and captures authenticated live screenshots.
- Correct migration evidence query uses `checksum_sha256`, not the handover's invalid `checksum` column.
- Rollback image: `sha256:db62bebdd4657e011606b470c4f8604a16678963675a0441b1bda64ea5d6b790`; fresh dump path must be recorded at deployment.
- Live proof must assert preview banner and actual new-tab behavior, both viewport slot counts, editor, catalog and CSP. Credentials are consumed only by protected runtime helpers and never shown in logs or reports.
- Rotate the previously compromised local administrator password after go-live through the supported management command; store it only in the protected credential location.

## Subsequent UI waves

After first verified deployment, assess before/after screenshots against handover §6. Specify and deliver each page's remaining information hierarchy, states and ergonomics in small independently reviewed changes. Deploy after each completed and gated wave; do not accumulate an unverified large redesign.
