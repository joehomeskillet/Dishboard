# MP-REC-SNAPSHOT-V2 — Belegebündel 2026-09-15

live: e0da7ab74ec5c0d5b9bc751cb3a09c2633e530f4
worktree: /nvmetank1/projects/menuplan/.claude/worktrees/rec-snapshot-v2-0915
branch: feat/rec-snapshot-v2-0915
gate_command: rtk bash /nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test-recipe-print-0908-gate.sh /nvmetank1/projects/menuplan/.claude/worktrees/rec-snapshot-v2-0915 -q -p no:cacheprovider tests/test_recipe_snapshot_v2_db.py tests/test_recipe_pdf.py tests/test_recipe_scaling.py
gate_summary: 88 passed in 26.67s
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/rec-snapshot-v2-0915/reference_scaffold
pg18: Recipeprint-Pool ist PostgreSQL 16. PG18-spezifische Historienbelege NICHT GELAUFEN in diesem WP.
pdf_count: test_real_v2_pdf_prints_both_uses_and_original_child_content zählt Titel plus Fortsetzungskopf wie test_recipe_pdf.py (kein abgeschwächter Inhalt).

## C1
criterion: v1-PDFbytes und v1-Snapshot-/Hashbelege bleiben bytegleich
test_anchor: reference_scaffold/tests/test_recipe_snapshot_v2_db.py::test_v1_terminal_and_parent_bytes_survive_current_food_pin_and_name_changes
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0

## C2
criterion: zwei Geschwister mit gemeinsamen Enkeln
test_anchor: reference_scaffold/tests/test_recipe_snapshot_v2_db.py::test_reader_reconstructs_shared_grandchild_against_original_pg_bytes
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0

## C3
criterion: fehlende/zusätzliche/falsche IDs
test_anchor: reference_scaffold/tests/test_recipe_snapshot_v2_db.py::test_real_reader_rejects_self_hashed_but_inconsistent_stored_closure
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0

## C4
criterion: v2-PDF und Skalierungsdarstellung
test_anchor: reference_scaffold/tests/test_recipe_snapshot_v2_db.py::test_real_v2_pdf_prints_both_uses_and_original_child_content
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0; Fortsetzungsköpfe wie test_recipe_pdf.py

## C5
criterion: exakte Recipe/Revision/Assetauswahl
test_anchor: reference_scaffold/tests/test_recipe_snapshot_v2_db.py::test_canonical_dto_text_body_and_child_original_hash_cannot_be_replaced
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0
