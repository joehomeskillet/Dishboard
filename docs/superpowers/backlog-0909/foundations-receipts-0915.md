# MP-BAS-FOUNDATIONS — Belegebündel 2026-09-15

live: e0da7ab74ec5c0d5b9bc751cb3a09c2633e530f4
worktree: /nvmetank1/projects/menuplan/.claude/worktrees/bas-foundations-0915
branch: feat/bas-foundations-0915
prior_author_freeze: 4d5074e3d8e9249ffa51733fa5fbcd3af781ffa0
prior_reports: wp-bc99db27be54.md, Root 114 DB + 35 Browser, Review 12446 CLEAN
gate_command: rtk bash /nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test-recipe-print-0908-gate.sh /nvmetank1/projects/menuplan/.claude/worktrees/bas-foundations-0915 -q -p no:cacheprovider tests/test_master_data_db.py tests/test_master_data_routes.py tests/test_master_data_race_db.py tests/test_master_data_browser.py tests/test_master_data_forms_v27.py tests/test_master_data_wiring_v27.py tests/test_master_data_prepared_db.py tests/test_master_data_prepared_browser.py
gate_summary: 140 passed in 276.56s (0:04:36)
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/bas-foundations-0915/reference_scaffold
shared_owner: grundlagen_food.html remains FOUNDATIONS + MP-OFF-REVIEW-UI; PRICE-UI is a later sibling after ROOT-FREEZE of REG-KK, not this WP

## C1
criterion: Ein Lebensmittel ohne Lagerauswahl kann nicht gespeichert werden
test_anchor: reference_scaffold/tests/test_master_data_forms_v27.py::test_storage_is_required_and_duplicates_do_not_disappear
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0

## C2
criterion: Ein Lebensmittel mit genau einem Lagerort verliert diesen bei reiner Namensaenderung nicht
test_anchor: reference_scaffold/tests/test_master_data_prepared_db.py::test_combined_native_save_is_one_bump_one_audit_and_noop_zero
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0

## C3
criterion: Eine wirksame Aenderung erhoeht die Version genau um 1
test_anchor: reference_scaffold/tests/test_master_data_prepared_db.py::test_combined_native_save_is_one_bump_one_audit_and_noop_zero
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0; bytegleiches Speichern = noop_zero

## C4
criterion: Das Entfernen des letzten Lagerorts wird abgelehnt
test_anchor: reference_scaffold/tests/test_master_data_prepared_db.py::test_storage_crud_archive_guard_and_last_storage_rejection
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0

## C5
criterion: Der vorbereitete Pin zeigt Revisions-UUID und 64-stelligen Hash
test_anchor: reference_scaffold/tests/test_master_data_wiring_v27.py::test_rendered_history_and_storage_links_keep_exact_pin
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0

## C6
criterion: Kein Bestand erfasst
test_anchor: reference_scaffold/tests/test_master_data_prepared_browser.py::test_native_storage_and_preparation_selection_survives_save_and_reload
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0; exact text 'Kein Bestand erfasst'

## C7
criterion: Es entsteht kein zweiter Lagerdienst
test_anchor: reference_scaffold/tests/test_master_data_db.py::test_full_food_vocabulary_metadata_storage_and_proposal_roundtrip
coverage: this Recipeprint gate 2026-09-15 GATE_EXIT=0; single store API, no second storage module in owned_files

## C8
criterion: UI-Master vollständig gelesen
test_anchor: reference_scaffold/tests/test_master_data_browser.py::test_native_food_save_conflict_archive_and_framework
coverage: 390×1100, 820×1100, 1440×1100 this gate; 1024×768, 768×1024, 1920×1080 NICHT GELAUFEN (bestehende Route, keine neue Pattern-Matrix in diesem Belegebündel)

## C9
criterion: keyboard/NoJS/200%Zoom
test_anchor: reference_scaffold/tests/test_master_data_browser.py::test_native_food_save_conflict_archive_and_framework
coverage: NoJS javascript=False this gate; keyboard/200%Zoom/Fontload/Kontrast NICHT GELAUFEN as dedicated a11y pass in this WP
