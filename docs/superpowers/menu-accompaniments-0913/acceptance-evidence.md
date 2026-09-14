# MP-REC-ACC-ACCEPT — Abnahmebelege

Stand: 2026-09-14  
Basis: `4a808f8e2e82dbc68f2deba9b956918d651a8f39`  
Branch/Worktree: `test/acc-accept-0914`, `/nvmetank1/projects/menuplan/.claude/worktrees/acc-accept-0914`  
Test: `reference_scaffold/tests/test_menu_accompaniment_flow_accept.py`

## Ergebnis A1–A16

| Fall | Status | Test oder Beleg |
|---|---|---|
| A1 | bestanden — durch Root-Release belegt | `/nvmetank1/projects/rag-stack/.claude/reports/wp-e0eee83ad0e4-deploy.md`, Schritte 2, 6 und Root-Gates; Migration auf Schema 32, Backup und Katalogprüfung. Die dort ausdrücklich nicht gefahrene isolierte Restore-Probe wurde in diesem WP gemäss Auftrag nicht wiederholt. |
| A2 | bestanden | `test_editor_to_publish_all_consumers_and_legacy_week` legt eine Vorlage mit `accompaniment_default='salad'` per UI an und liest den Vorschlag im Editor; DB-Vertrag: `test_menu_accompaniment_migration_db.py::test_v32_template_defaults_validation_cas_audit_v26_compatibility_and_acl` und `test_dish_template_accompaniment_db.py::test_store_uses_v32_optional_default_and_preserves_noop_cas`. |
| A3 | bestanden | `test_template_none_validation_viewports_keyboard_and_focus[js]`, `[nojs]`: `none`, Rücklesen, fremder Wert, HTTP 400 am Feld und erhaltene Eingaben; Hauptfluss prüft `soup`/`salad` in beiden Rastern. |
| A4 | bestanden | Root-Gate „Recipeprint MENU-CORE/SNAPSHOT/Patienten-E2E: 2252 passed“ im Releasebericht; Einzelbeleg `test_menu_accompaniment_db.py::test_accompaniment_only_change_has_one_version_step_and_review_payload_delta`. |
| A5 | bestanden | `test_csv_three_roundtrip_schema_two_replacement_and_previous_week_copy`: Vorwochenkopie behält Beilage; Schema 2 setzt gesetzte Beilagen nach sichtbarem Vorschauhinweis auf `none`. |
| A6 | bestanden | `test_template_none_validation_viewports_keyboard_and_focus[js]` und `[nojs]`: Vorschlag „Salat“ vorbelegt, Wahl „Keine“ als `none` gespeichert; Konfliktvertrag: `test_menu_accompaniment_form.py::test_template_default_change_after_proposal_returns_409_without_menu_write`. |
| A7 | bestanden | `test_editor_to_publish_all_consumers_and_legacy_week`: alte publizierte Woche vor/nach Gesamtablauf bytegleich, SHA-256 gleich und Status weiter `live`; neue Snapshot-Paare über HTML, PDF, API und FHIR gelesen. Validatorbeleg im Root-MENU-CORE-Gate. |
| A8 | bestanden | Root-MENU-CORE-Gate; Einzelbelege `test_menu_accompaniment_snapshot.py::test_read_last_good_accepts_legacy_snapshot_without_accompaniment` und `::test_active_snapshot_reads_legacy_revision_without_mutating_it`. |
| A9 | bestanden | `test_editor_to_publish_all_consumers_and_legacy_week`: Public heute/Woche/Druck-HTML und Signage Tag/Woche für Patienten/Cafeteria; `Dazu:` genau einmal je gewähltem Menü, keine Zeile bei `none`; 1920×1080 und 3840×2160 ohne horizontalen oder vertikalen Überlauf. |
| A10 | bestanden | `test_editor_to_publish_all_consumers_and_legacy_week`: echte Wochen-PDFs für Patienten und Cafeteria per `pypdf` rückgelesen; gewählte Zeilen exakt einmal, Menü ohne Wahl ohne `Dazu:`. Layout-/Bytevertrag zusätzlich im Root-MENU-CORE-Gate. |
| A11 | bestanden | `test_editor_to_publish_all_consumers_and_legacy_week`: OpenAPI, API `weeks`/`weeks_preview`, FHIR `NutritionProduct.note` und MCP `get_week_menu`/`get_week_preview`/`list_weeks`; Datensatzname ohne `Dazu:`-Präfix. |
| A12 | bestanden | `test_editor_to_publish_all_consumers_and_legacy_week`: Vorlagenformular/-liste, Radiowahl und Leseransicht ohne Schreibaktion; `test_csv_three_roundtrip_schema_two_replacement_and_previous_week_copy` führt Importwerkzeug aus. |
| A13 | bestanden | `test_editor_to_publish_all_consumers_and_legacy_week`: Kartenansicht der Menüsammlung zeigt `Dazu: Suppe` bei Wahl und keine `.menu-accompaniment`-Zeile bei `none`, in beiden Familien. |
| A14 | bestanden | `test_csv_three_roundtrip_schema_two_replacement_and_previous_week_copy`: publizierte Woche mit `soup`/`salad`/`none`, Schema-3-Export, Import in leere Woche, identische Werte; Schema-2-Vorschauhinweis und vollständiger Reset auf `none`. |
| A15 | bestanden | `test_template_none_validation_viewports_keyboard_and_focus[js]`, `[nojs]`, `test_editor_real_browser_zoom_two_hundred_percent` und Hauptfluss: 1440×900, 390×844, 1024×768, 768×1024, 1920×1080, native 200-%-Zoom, Tastaturpfeil, sichtbarer Fokus, 48-px-Ziele, Kontrast ≥ 4,5:1, beide Raster. Icons werden mit sichtbarem Text verwendet. |
| A16 | bestanden — durch Root-Release belegt | `/nvmetank1/projects/rag-stack/.claude/reports/wp-e0eee83ad0e4-deploy.md`, Schritt 7 und Abschnitt „Rollback“: v31-App gegen Schema 32 healthy, Readiness und öffentliche Smokes 200; I10 und Restore-Regel dokumentiert. Gemäss Auftrag nicht wiederholt. |

## Gate

Exklusiver PG/Redis-Pool, vorab `pgrep -fc "python -m pytest"` = `1` (< 10):

```text
$ rtk /nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test-recipe-print-0908-gate.sh /nvmetank1/projects/menuplan/.claude/worktrees/acc-accept-0914 -q -p no:cacheprovider tests/test_menu_accompaniment_flow_accept.py
.....                                                                    [100%]
5 passed in 47.46s
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/acc-accept-0914/reference_scaffold
```

```text
$ rtk ruff check reference_scaffold/tests/test_menu_accompaniment_flow_accept.py
Ruff: No issues found
EXIT=0
```

Keine `xfail`-Markierung. Keine abgeschwächte Assertion. Keine Produktfehler P1/P2/P3 gefunden.

## Browserbelege

Nicht versioniert; alle Dateien liegen unter `.claude/evidence/acc-accept-0914/`:

- `patienten-grid-editor.png`, `cafeteria-grid-editor.png`
- `editor-1440x900-js.png`, `editor-1440x900-nojs.png`
- `editor-390x844-js.png`, `editor-390x844-nojs.png`
- `editor-1024x768-js.png`, `editor-1024x768-nojs.png`
- `editor-768x1024-js.png`, `editor-768x1024-nojs.png`
- `editor-1920x1080-js.png`, `editor-1920x1080-nojs.png`
- `editor-native-zoom-two-hundred.png`
- `signage-cafeteria-tag-1920x1080.png`, `signage-cafeteria-tag-3840x2160.png`
- `signage-cafeteria-woche-1920x1080.png`, `signage-cafeteria-woche-3840x2160.png`
- `signage-patienten-tag-1920x1080.png`, `signage-patienten-tag-3840x2160.png`
- `signage-patienten-woche-1920x1080.png`, `signage-patienten-woche-3840x2160.png`

Stichprobe visuell geprüft: Patientenraster, mobiler NoJS-Editor, Cafeteria-Wochensignage 1920×1080 und Patienten-Tagesignage 3840×2160. Keine Baseline ersetzt.

## Vorschlag für Root: UI-Inventar

Keine Inventardatei wurde in diesem WP geändert. Folgende bestehenden Routen sollten konkrete Abnahmezeilen erhalten:

| Route | Rolle/Zustand | Muster | Tatsächliche Tests/Belege |
|---|---|---|---|
| `/admin/gerichtvorlagen/neu`, `/admin/gerichtvorlagen/<public_id>` | `Cafeteria.Editor`, default; Leser ohne Schreibaktion | kompakte Radiogruppe „Suppe oder Salat dazu“, sichtbares Label | Hauptfluss; `patienten-grid-editor.png` als Folgebeleg |
| `/admin/gerichtvorlagen/<public_id>/einplanen` | `Cafeteria.Editor`, default/proposal | Vorlagenvorschlag „Salat“, Übergabe in Menüeditor | Hauptfluss; JS- und NoJS-Parametertest |
| `/admin/<any(cafeteria, patienten):family>/menu` | `Cafeteria.Editor`, default/invalid | direkt bedienbare Radiogruppe, Feldfehler, Werteerhalt, 48-px-Ziele, Fokus | Viewport-, Tastatur-, NoJS- und Zoomtests; `editor-*.png` |
| `/admin/<any(cafeteria, patienten):family>` | Editor und Leser, reviewed/live | kompakte Kartenzeile `Dazu: …`, keine Zeile bei `none` | Hauptfluss; `patienten-grid-editor.png`, `cafeteria-grid-editor.png` |
| `/admin/<any(cafeteria, patienten):family>/menues` | Editor und Leser, default | Kartenansicht mit optionaler `Dazu:`-Zeile | Hauptfluss A13 |
| `/signage/{cafeteria,patienten}/{tag,woche}` | anonym/live | optionale `Dazu:`-Zeile, Fit ohne Überlauf | Hauptfluss A9; acht `signage-*.png` in beiden Zielauflösungen |

Empfohlene Feldänderungen je HTML-Route: `density.state_evidence.default = "passed_acc_accept_0914"`, `density.browser_status = "passed"`, `density.usability_status = "passed"`, `density.notes` um Testnamen und Screenshotpfad ergänzen. Invalid-State des Menüeditors zusätzlich auf `passed_acc_accept_0914` setzen.

## Nicht ausgeführt

- Physischer Player: nicht ausgeführt — getrennte Abnahme.
- Küchendruck auf physischem Drucker: nicht ausgeführt — getrennte Abnahme.
- Isolierte Restore-Probe und erneuter v31-App/v32-Schema-Smoke: gemäss Auftrag nicht wiederholt; Root-Release-Beleg oben.
- Keine Gesamtsuite, keine anderen Pools/Container, kein Deploy.
