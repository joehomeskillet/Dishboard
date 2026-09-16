# MP-REC-BINDINGS — Belegebündel 2026-09-15

live: e0da7ab74ec5c0d5b9bc751cb3a09c2633e530f4
worktree: /nvmetank1/projects/menuplan/.claude/worktrees/rec-bindings-0915
branch: feat/rec-bindings-0915
register_note: 2026-09-13-sdd-work-package-register.md nannte eine Menübindungsregression im Release. bindings26-Gate auf e0da7ab ist grün; keine reproduzierbare DB-Regression in den Writer-Tests. Drei UI-Wege bleiben MP-REC-BINDINGS-ACCEPT.
gate_command: rtk bash /nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test-recipe-bindings26-0908-gate.sh /nvmetank1/projects/menuplan/.claude/worktrees/rec-bindings-0915 -q -p no:cacheprovider tests/test_recipe_menu_binding_db.py tests/test_menu_recipe_bindings_db.py tests/test_menu_recipe_binding_races_db.py
gate_summary: 30 passed in 48.05s
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/rec-bindings-0915/reference_scaffold

## C1
criterion: Nicht-NULL-Roundtrip fuer menu_item_components.recipe_revision_id
test_anchor: reference_scaffold/tests/test_menu_recipe_bindings_db.py::test_exact_recipe_roundtrip_append_legacy_refusal_and_explicit_detach
coverage: this bindings26 gate 2026-09-15 GATE_EXIT=0

## C2
criterion: Legacy-Zweifeldersatz verliert keine vorhandene Rezeptreferenz
test_anchor: reference_scaffold/tests/test_menu_recipe_bindings_db.py::test_exact_recipe_roundtrip_append_legacy_refusal_and_explicit_detach
coverage: this bindings26 gate 2026-09-15 GATE_EXIT=0

## C3
criterion: Standortfremde Revision wird mit 23514
test_anchor: reference_scaffold/tests/test_menu_recipe_bindings_db.py::test_archived_recipe_preserve_increase_detach_and_foreign_scope
coverage: this bindings26 gate 2026-09-15 GATE_EXIT=0

## C4
criterion: Akteurs- und Positions-CAS greifen
test_anchor: reference_scaffold/tests/test_menu_recipe_bindings_db.py::test_original_actor_required_before_any_menu_mutation
coverage: this bindings26 gate 2026-09-15 GATE_EXIT=0

## C5
criterion: Textgleicher Revisionswechsel und Wechsel zurueck verwerfen alte Reviewtokens
test_anchor: reference_scaffold/tests/test_menu_recipe_bindings_db.py::test_partial_readback_review_change_revert_and_unknown_recipe_effects
coverage: this bindings26 gate 2026-09-15 GATE_EXIT=0

## C6
criterion: Vorwochenkopie erhaelt die exakte Revision
test_anchor: reference_scaffold/tests/test_menu_recipe_bindings_db.py::test_exact_archived_copy_keeps_source_text_version_and_revision
coverage: this bindings26 gate 2026-09-15 GATE_EXIT=0

## C7
criterion: Vollstaendiger Menue-CSV-Ersatz loescht eine reine Rezeptbindung nicht still
test_anchor: reference_scaffold/tests/test_menu_recipe_bindings_db.py::test_bulk_preserves_identity_version_and_blocks_recipe_only_csv
coverage: this bindings26 gate 2026-09-15 GATE_EXIT=0

## C8
criterion: Bereits veroeffentlichte Wochen behalten ihren Publikationshash
test_anchor: reference_scaffold/tests/test_menu_recipe_bindings_db.py
coverage: NICHT GELAUFEN in diesem Writer-Gate; Gesamtabnahme inkl. Publikationshash ist MP-REC-BINDINGS-ACCEPT
