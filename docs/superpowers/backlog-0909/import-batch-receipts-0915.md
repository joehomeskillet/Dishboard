# MP-REC-IMPORT-BATCH — Belegebündel 2026-09-15

live: e0da7ab74ec5c0d5b9bc751cb3a09c2633e530f4
worktree: /nvmetank1/projects/menuplan/.claude/worktrees/rec-import-batch-0915
branch: feat/rec-import-batch-0915
schema: bestehende Import-Batch-Tabellen und Verben (Schema 34); keine neue Migration
gate_command: rtk bash /nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test-recipe-template-editor-0908-gate.sh /nvmetank1/projects/menuplan/.claude/worktrees/rec-import-batch-0915 -q -p no:cacheprovider tests/test_recipe_import_batch_db.py tests/test_recipe_import_routes.py
gate_summary: 9 passed in 13.38s
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/rec-import-batch-0915/reference_scaffold
browser: tests/test_recipe_import_browser.py NICHT GELAUFEN in diesem WP

## C1
criterion: Quelldokument/hash/Originalrow bleiben bei Kandidatenedit unverändert
test_anchor: reference_scaffold/tests/test_recipe_import_batch_db.py::test_candidate_edit_preserves_origin_and_invalidates_confirmation
coverage: this Templateeditor gate 2026-09-15 GATE_EXIT=0

## C2
criterion: neuer Kandidatenhash/Batchversion invalidiert vorherige Bestätigung
test_anchor: reference_scaffold/tests/test_recipe_import_batch_db.py::test_candidate_edit_preserves_origin_and_invalidates_confirmation
coverage: this Templateeditor gate 2026-09-15 GATE_EXIT=0

## C3
criterion: unaufgelöste Food-/Unitzeilen können als Import-draft gespeichert werden
test_anchor: reference_scaffold/tests/test_recipe_import_batch_db.py::test_create_keeps_origin_and_unresolved_food
coverage: this Templateeditor gate 2026-09-15 GATE_EXIT=0

## C4
criterion: keine automatische Veröffentlichung
test_anchor: reference_scaffold/tests/test_recipe_import_batch_db.py::test_create_does_not_write_recipes_or_relabel_source
coverage: this Templateeditor gate 2026-09-15 GATE_EXIT=0

## C5
criterion: GET no-store
test_anchor: reference_scaffold/tests/test_recipe_import_routes.py::test_get_is_no_store_and_write_free
coverage: this Templateeditor gate 2026-09-15 GATE_EXIT=0
