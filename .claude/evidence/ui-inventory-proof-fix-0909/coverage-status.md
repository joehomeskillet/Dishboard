# Abdeckungs- und Statusmatrix — WP wp-d7589450daee

Belegstand: neuer Aufnahmesatz
`.claude/evidence/ui-inventory-proof-fix-0909/capture/` mit 115 Aufnahmen und
115 PNG. Der ursprüngliche Satz mit 111 PNG unter
`.claude/evidence/ui-inventory-grok-0909/screenshots/` bleibt unverändert als
historischer Beleg; die versionierte Matrix und das versionierte Manifest sind
byteidentisch geblieben.

Ein Screenshot ist **keine** Funktions-, Barrierefreiheits- oder vollständige
Routenabnahme. Die folgenden Zeilen sagen nur, was tatsächlich mit welchem
Ergebnis ausgeführt wurde.

## Roots fünf Befunde

| # | Befund | Status | Beleg |
|---|---|---|---|
| 1 | Listener werden direkt nach DOMContentLoaded entfernt, spätere Fehler fehlen | **bestanden** | `regression-proof.py`: Originalrecorder `console=[]`, korrigierter Recorder `['error: late console failure']` und `['late page error']`; Test `test_console_failure_after_dom_content_loaded_is_recorded` |
| 2 | Feste Verzögerung statt Schrift-/Bildbereitschaft, nur deklarierte CSS-Familie | **bestanden** | `await_ready` wartet auf `load`, Lazy-Sweep, `document.fonts.status==='loaded'` und alle `img.complete`; `rendered_fonts` liest zusätzlich den tatsächlich gerenderten Plattformfont über CDP `CSS.getPlatformFontsForNode` (115 von 115 Aufnahmen mit `platform_source='cdp:CSS.getPlatformFontsForNode'`); Test `test_readiness_waits_for_late_image_instead_of_a_fixed_delay` |
| 3 | Publish-Dialog mit hartkodiertem Status 200, `overflow=false`, leeren Fehlern | **bestanden** | `capture_publish_dialog` misst mit demselben Recorder, verlangt sichtbares und geöffnetes Modal und liefert bei fehlendem Auslöser einen `blocked_modal_not_open`-Eintrag statt einer Erfolgszeile; Test `test_absent_publish_modal_produces_a_blocked_record_not_a_success` |
| 4 | Tests überschrieben Matrix, Manifest und private Belege bedingungslos | **bestanden** | `Outputs`/`Outputs.into`, `build_matrix.write_matrix(--out)`; der Regressionslauf schreibt nach `tmp_path` und prüft Matrix, Manifest und alle Original-PNG auf Unverändertheit; nur `UI_CAPTURE_OUT` erzeugt einen getrennten neuen Satz; Test `test_redirected_run_leaves_versioned_outputs_untouched` |
| 5 | Kopier-Erfolg und Revisionsdetail angeblich mangels Fixture nicht belegbar | **bestanden** | Revisionsdetail über echte `recipe_store.create_recipe` + `freeze_revision` in allen fünf Master-Viewports mit Status 200; Kopieransicht mit Status 200 bei 1440×900 und 390×844; erwartete Fehlervarianten 404/400 bleiben erhalten |

## Ausgeführte Gates

| Gate | Ergebnis |
|---|---|
| `tests/test_ui_inventory_capture.py` (zugewiesener Pool PG32831/Redis32833) | **bestanden**, `5 passed in 5.24s`, `GATE_EXIT=0` |
| `tests/test_ui_route_inventory.py` (zugewiesener Pool) | **bestanden**, `5 passed in 105.12s`, `GATE_EXIT=0` |
| Beide Module gemeinsam nach dem Lazy-Sweep | **bestanden**, `10 passed in 57.77s`, `GATE_EXIT=0` |
| Ausdrücklicher Aufnahmelauf mit `UI_CAPTURE_OUT` | **bestanden**, `1 passed in 100.01s` bzw. im Gesamtlauf enthalten |
| `regression-proof.py` | **bestanden**, `REGRESSION_PROOF=PASS` |
| Ruff über alle geänderten eigenen Dateien | **bestanden**, `All checks passed!` |

## Aufnahmematrix des neuen Satzes

| Kombination | Anzahl | Status |
|---|---|---|
| 1440 × 900 | 53 | bestanden |
| 390 × 844 | 46 | bestanden |
| 1920 × 1080 | 6 | bestanden |
| 1024 × 768 | 5 | bestanden |
| 768 × 1024 | 5 | bestanden |
| Aufnahmen mit vollständiger Bereitschaft | 115 von 115 | bestanden |
| Aufnahmen mit erfasstem Plattformfont | 115 von 115 | bestanden |
| Revisionsdetail in allen fünf Viewports | 5 | bestanden |
| Kopieransicht mit Erfolg, Desktop und Mobil | 2 | bestanden |
| Publish-Dialog, gemessen statt behauptet | 1 | bestanden |

## Neuer Befund aus der echten Bereitschaftsprüfung

Der erste korrigierte Lauf meldete für `/cafeteria/wochenangebot/` und
`/patienten/wochenplan/` in beiden Viewports `rendered=false` mit
`TimeoutError` und offenen Bildern. Ursache ist
`templates/_menu_image.html:4` mit `loading="lazy"`: bei einem
Ganzseiten-Screenshot werden Bilder unterhalb des Sichtfensters nie angefordert.
Der ursprüngliche Recorder hat diese vier Seiten nach 250 ms trotzdem
fotografiert und als `rendered=true` geführt — die betreffenden Baselines
enthielten also leere Bildflächen, ohne dass es sichtbar war.

Behoben durch einen begrenzten Scroll-Durchlauf vor der Bildprüfung
(`readiness.lazy_sweep`). Danach sind alle 115 Aufnahmen vollständig bereit.
Dieser Befund war ohne die Korrektur aus Befund 2 nicht sichtbar.

Sieben Aufnahmen tragen jetzt Konsolenmeldungen. Alle sieben sind die erwarteten
Fehlervarianten 401, 403, 404 und 400 der bewusst aufgenommenen Negativfälle,
keine neuen Defekte. Der ursprüngliche Recorder meldete für sämtliche Seiten eine
leere Konsole.

## Nicht ausgeführt oder blockiert

| Punkt | Status | Grund |
|---|---|---|
| Entra-Callback gegen echten Tenant | **blockiert** | Kein realer Tenant und keine Produktivperson darf synthetisiert werden. Nicht gefälscht. |
| Physischer Yodeck-Player | **nicht ausgeführt** | Externe Hardware, ausserhalb dieses WP. Keine Behauptung. |
| Native PDF-Bytes und Papierlayout | **nicht ausgeführt** | Als Download klassifiziert; die HTML-Druckrouten sind aufgenommen. |
| Barrierefreiheitsabnahme, Kontrast, Tastaturbedienung | **nicht ausgeführt** | Ein Screenshot ersetzt sie nicht; gehört in die Migrationspakete. |
| Vollständige Routenabdeckung aller registrierten Endpunkte | **nicht ausgeführt** | Der Satz deckt die aufnehmbaren HTML-Oberflächen ab, nicht jede Route. |
| GitNexus `detect_changes` für diesen Worktree | **blockiert** | Kein Alias vorhanden; siehe zentralen Bericht. |
| OCR | **nicht ausgeführt** | Zweimal echtes HTTP 429; auftragsgemäss kein weiterer Versuch. |

Die Referenzen dieses Satzes sind **vorgeschlagen** und ausdrücklich nicht vom
Auftraggeber freigegeben (`meta.baseline_status = proposed_never_user_approved`).
