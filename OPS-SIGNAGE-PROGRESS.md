# OPS Signage correction — wp-b0352bc25fc5

Owner: Astra; branch `fix/ops-signage-astra-0907`.
Base: `f84f7ca5bf054241eab84c47b2630e8075a787cb`.

Status: Implementation and local browser gates complete. G1: 206 passed in 125.65s; G2: 92 passed, 14 skipped in 43.66s (all skipped require isolated PostgreSQL); final strengthened OPS suite: 26 passed in 29.87s. Whole-tree Ruff clean. Normal Mypy blocked only by imported unchanged capture_admin_live_proof.py317-319 (3 errors), reported to Root; OCR unavailable from prior repeated 429, not retried.

Final rotation: legacy 2 pages (Monday–Wednesday, Thursday–Sunday), both meals; OPS 4 pages (Lunch Monday–Thursday, Lunch Friday–Sunday, Dinner Monday–Thursday, Dinner Friday–Sunday). Exactly 28 menus, original quarter-width cards. OPS cards 462.95×366.09 px at FHD and 925.92×794.45 px at 4K, equal across all pages. Three-page full-warning draft measured clipping at both resolutions and rejected.
Operator proof checks both contracts and cafeteria 5/6/7, including every rotated page. Patient menu symbols retain existing 1.2em/1.6em flag contract; legend remains 1.5em/2em, with dedicated negative tests.
Root explicitly extended ownership for the legacy assertion corrections in test_food_legends_signage.py and test_rendered_ui.py, plus operator legend context sizing. No unrelated changes.
Artifacts: /tmp/dishboard-ops-signage-astra-0907/{initial,rotation,g1,g2-final,ops-final}. Full handoff report: /nvmetank1/projects/rag-stack/.claude/reports/wp-b0352bc25fc5.md.
Scope: patient rotation, patient browser regressions, operator proof contracts including cafeteria 5/6/7.
Legacy without area_name (schema 1 and 2): exact two pages, 3+4 days and original quarter-width cards.
OPS page count will be selected by full-content FHD/4K measurement.
No push, merge, deployment, DB access, or dependency installations authorized for this lane.
